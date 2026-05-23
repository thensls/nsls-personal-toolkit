"""Flask app factory for the NSLS toolkit companion."""

import hashlib
import queue
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask, Response, render_template, request, stream_with_context

from companion.parsers import (
    append_day_to_log,
    parse_daily_note_sections,
    parse_habits,
    parse_log,
)
from companion.safe_write import safe_modify
from companion.streak import DayResult, compute_concern, status_for, streak_days
from companion.validation import (
    HABIT_ID_RE,
    validate_habit_fields,
    validate_save,
    validate_toggle,
)
from companion.watcher import VaultWatcher


def _serialize_habits(habits: dict) -> str:
    """Write the habits dict back to canonical markdown format.

    Active section first, then Archived. Each habit is a 5- or 6-line
    block (id, name, emoji, target, frequency, optional archived_at).
    """
    out = ["# Daily Habits", ""]
    out.append("## Active")
    out.append("")
    if not habits["active"]:
        out.append("(none)")
        out.append("")
    else:
        for h in habits["active"]:
            out.append(f"- id: {h['id']}")
            for field in ("name", "emoji", "target", "frequency"):
                if field in h:
                    out.append(f"  {field}: {h[field]}")
            out.append("")
    out.append("## Archived")
    out.append("")
    if not habits["archived"]:
        out.append("(none yet)")
        out.append("")
    else:
        for h in habits["archived"]:
            out.append(f"- id: {h['id']}")
            for field in ("name", "emoji", "target", "frequency", "archived_at"):
                if field in h:
                    out.append(f"  {field}: {h[field]}")
            out.append("")
    return "\n".join(out)


def _extract_numbered_checkbox_list(section: str, heading: str) -> list[dict]:
    """Extract `1. [x] Foo` / `1. [ ] Foo` / `1. Foo` items under a `### heading`.

    Returns a list of dicts shaped like ``{"text": str, "checked": bool}``.
    Tolerates both lowercase `[x]` and uppercase `[X]`. Items without a
    checkbox at all are treated as unchecked (backward compat for daily notes
    that omit the box).
    """
    items: list[dict] = []
    in_section = False
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith(heading):
            in_section = True
            continue
        if in_section and stripped.startswith("###"):
            break
        if in_section and stripped and stripped[0].isdigit():
            # Drop the leading "1." / "12." numbering.
            after_num = stripped.split(".", 1)[-1].strip()
            checked = False
            if after_num.startswith("[ ]"):
                text = after_num[3:].strip()
            elif after_num[:3].lower() == "[x]":
                checked = True
                text = after_num[3:].strip()
            else:
                text = after_num
            if text:
                items.append({"text": text, "checked": checked})
    return items


def _extract_numbered_checkbox_list_raw(section: str, heading: str) -> list[dict]:
    """Like _extract_numbered_checkbox_list but includes empty items.

    Used by plan-action to find cleared slots in the raw markdown.
    """
    items: list[dict] = []
    in_section = False
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith(heading):
            in_section = True
            continue
        if in_section and stripped.startswith("###"):
            break
        if in_section and stripped and stripped[0].isdigit():
            after_num = stripped.split(".", 1)[-1].strip()
            checked = False
            if after_num.startswith("[ ]"):
                text = after_num[3:].strip()
            elif after_num[:3].lower() == "[x]":
                checked = True
                text = after_num[3:].strip()
            else:
                text = after_num
            items.append({"text": text, "checked": checked})
    return items


def _extract_top_3(morning_section: str) -> list[dict]:
    return _extract_numbered_checkbox_list(morning_section, "### My Top 3")


def _extract_bonus(morning_section: str) -> list[dict]:
    return _extract_numbered_checkbox_list(morning_section, "### Bonus")


_AI_SUGGEST_HEADING_RE = re.compile(
    r"^###\s*AI Suggested:\s*(.*?)\s*$", re.IGNORECASE
)
# Strip `**bold**` wrappers and `— rationale` / `- rationale` tails so the
# visible suggestion is just the title. Rationale lives in the daily note for
# reference; the Plan-Your-Day row stays tidy.
_AI_ITEM_LEAD_RE = re.compile(r"^\s*\d+\.\s+(.*)$")


def _clean_ai_item(raw: str) -> str:
    text = raw.strip()
    # Strip leading bold wrappers: **text** … → text …
    m = re.match(r"^\*\*(.+?)\*\*(.*)$", text)
    if m:
        text = (m.group(1) + m.group(2)).strip()
    # Drop em-dash / hyphen-led rationale tail
    text = re.split(r"\s+[—–-]\s+", text, maxsplit=1)[0].strip()
    # Drop any trailing markdown bold markers
    text = text.strip("*").strip()
    # Strip surrounding brackets (close-day template uses `[Item]` placeholders)
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    return text


def _extract_ai_suggestions(morning_section: str) -> list[dict]:
    """Pull items from any `### AI Suggested: …` subsection of Morning Check-in.

    Returns: list of {"text": str, "source": str} preserving discovery order.
    Empty/template placeholders (`[Item 1]`, etc.) are filtered out so the
    suggestions table doesn't surface scaffold text.
    """
    items: list[dict] = []
    current_label: str | None = None
    for raw_line in morning_section.splitlines():
        stripped = raw_line.strip()
        m = _AI_SUGGEST_HEADING_RE.match(stripped)
        if m:
            label = m.group(1)
            # Compress verbose suffixes like " (strategic, …)" or " (from … close)"
            label = re.split(r"\s*\(", label, maxsplit=1)[0].strip()
            current_label = label or "Top 3"
            continue
        if stripped.startswith("### ") or stripped.startswith("## "):
            current_label = None
            continue
        if current_label is None:
            continue
        list_m = _AI_ITEM_LEAD_RE.match(raw_line)
        if not list_m:
            continue
        cleaned = _clean_ai_item(list_m.group(1))
        if not cleaned:
            continue
        # Filter pure scaffold placeholders the close-day template leaves
        # behind if /close-day didn't fill them.
        if cleaned.lower().startswith(("item ", "highest-impact item", "task")):
            continue
        items.append({"text": cleaned, "source": f"AI: {current_label}"})
    return items


def _extract_carryovers(vault_path: Path, today: str, lookback_days: int = 7) -> list[dict]:
    """Find the most recent prior daily note (up to ``lookback_days`` back)
    and return its unchecked Top 3 + Bonus items as carry-over suggestions.

    Reads the SINGLE most-recent note rather than concatenating multiple days
    — once a builder has closed Monday's note, Tuesday's open items should
    drive the suggestions for Wednesday, not Monday's. If no note exists in
    the lookback window, returns [].
    """
    try:
        base = datetime.strptime(today, "%Y-%m-%d")
    except ValueError:
        return []
    for offset in range(1, lookback_days + 1):
        candidate = (base - timedelta(days=offset)).date().isoformat()
        note_path = vault_path / "01-daily" / f"{candidate}.md"
        if not note_path.exists():
            continue
        sections = parse_daily_note_sections(note_path.read_text())
        morning = sections.get("Morning Check-in", "")
        items = []
        for it in _extract_top_3(morning) + _extract_bonus(morning):
            if it["text"] and not it["checked"]:
                items.append({"text": it["text"], "source": f"from {candidate}"})
        if items:
            return items
    return []


def _extract_dismissed(morning_section: str) -> set[str]:
    """Pull dismissed item texts from `### Dismissed` in Morning Check-in."""
    items: set[str] = set()
    in_section = False
    for line in morning_section.splitlines():
        stripped = line.strip()
        if stripped == "### Dismissed":
            in_section = True
            continue
        if in_section and stripped.startswith("###"):
            break
        if in_section and stripped.startswith("- "):
            text = stripped[2:].strip()
            if text:
                items.add(text)
    return items


def _build_plan_context(daily_md: str, vault_path: Path, today: str,
                       priorities: list, bonus: list) -> dict:
    """Build the Plan Your Day screen context: suggestions + carry-overs + taken state.

    Suggestion ordering: AI suggestions from /close-day (today's note's
    `### AI Suggested: …` subsections under `## Morning Check-in`) come first,
    then carry-overs (most recent prior daily note within the lookback window).
    Texts dedupe across sources — AI wins if both name the same item.
    Dismissed items are filtered out entirely.
    """
    morning = parse_daily_note_sections(daily_md).get("Morning Check-in", "")
    ai_items = _extract_ai_suggestions(morning)
    carryovers = _extract_carryovers(vault_path, today)
    dismissed = _extract_dismissed(morning)

    seen: set[str] = set()
    suggestions: list[dict] = []
    for item in ai_items + carryovers:
        if item["text"] in seen:
            continue
        seen.add(item["text"])
        suggestions.append(item)

    priority_texts = {p["text"] for p in priorities if p.get("text")}
    bonus_texts = {b["text"] for b in bonus if b.get("text")}

    for s in suggestions:
        if s["text"] in dismissed:
            s["taken"] = "dismissed"
        elif s["text"] in priority_texts:
            s["taken"] = "pri"
        elif s["text"] in bonus_texts:
            s["taken"] = "bonus"
        else:
            s["taken"] = None

    priorities_with_text = [p for p in priorities if p.get("text")]
    bonus_with_text = [b for b in bonus if b.get("text")]
    return {
        "suggestions": suggestions,
        "priorities": priorities_with_text,
        "bonus": bonus_with_text,
    }


def _add_dismissed(md: str, text: str) -> str:
    """Append `text` to the `### Dismissed` section under `## Morning Check-in`.

    Creates the section if it doesn't exist, placing it after the last `###`
    subsection within Morning Check-in.
    """
    lines = md.splitlines()
    # Find ### Dismissed
    dismissed_idx = None
    morning_end = len(lines)
    in_morning = False
    last_subsection_end = None
    for i, line in enumerate(lines):
        if line.strip() == "## Morning Check-in":
            in_morning = True
            continue
        if in_morning and line.startswith("## ") and not line.startswith("### "):
            morning_end = i
            break
        if in_morning and line.strip() == "### Dismissed":
            dismissed_idx = i
        if in_morning and line.startswith("### "):
            last_subsection_end = i

    if dismissed_idx is not None:
        # Find the end of the Dismissed section to append
        insert_at = dismissed_idx + 1
        for j in range(dismissed_idx + 1, morning_end):
            if lines[j].startswith("### ") or lines[j].startswith("## "):
                break
            insert_at = j + 1
        lines.insert(insert_at, f"- {text}")
    else:
        # Create ### Dismissed before the end of Morning Check-in
        insert_at = morning_end
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, "### Dismissed")
        lines.insert(insert_at + 2, f"- {text}")
        lines.insert(insert_at + 3, "")

    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def _remove_dismissed(md: str, text: str) -> str:
    """Remove `text` from the `### Dismissed` section (undo a dismissal)."""
    lines = md.splitlines()
    target = f"- {text}"
    in_section = False
    for i, line in enumerate(lines):
        if line.strip() == "### Dismissed":
            in_section = True
            continue
        if in_section and (line.startswith("### ") or line.startswith("## ")):
            break
        if in_section and line.strip() == target:
            del lines[i]
            # Clean up empty section if no items remain
            remaining_items = False
            for j in range(i if i < len(lines) else len(lines) - 1, -1, -1):
                if lines[j].strip() == "### Dismissed":
                    if not remaining_items:
                        del lines[j]
                        # Also remove trailing blank line if present
                        if j < len(lines) and lines[j].strip() == "":
                            del lines[j]
                        # And preceding blank line
                        if j > 0 and lines[j - 1].strip() == "":
                            del lines[j - 1]
                    break
                if lines[j].strip().startswith("- "):
                    remaining_items = True
            break
    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


_LIST_ITEM_RE = re.compile(r"^(\s*(?:\d+\.|-)\s+)(.*)$")


def _toggle_nth_checkbox(md: str, heading: str, index: int) -> str:
    """Toggle the `[ ]` / `[x]` on the Nth (0-indexed) list item under `heading`.

    Items under a level-3 heading like `### My Top 3` are list rows starting
    with a number-and-period (`1. `) or a dash (`- `). The checkbox marker
    `[ ]` / `[x]` may be present or absent — older /open-day templates seeded
    Top 3 and Bonus as plain numbered lists. If the marker is absent we treat
    the line as unchecked and inject `[x]` (the user just clicked to mark
    done). Markerless lines still count toward the Nth-item index.
    """
    lines = md.splitlines()
    in_section = False
    seen = 0
    for i, line in enumerate(lines):
        if line.strip() == heading:
            in_section = True
            continue
        if in_section and line.startswith("### "):
            break  # next subsection
        if in_section and line.startswith("## "):
            break  # next major section
        if not in_section:
            continue
        m = _LIST_ITEM_RE.match(line)
        if not m:
            continue
        prefix, rest = m.group(1), m.group(2)
        if seen == index:
            if rest.startswith("[ ]"):
                lines[i] = prefix + "[x]" + rest[3:]
            elif rest.startswith("[x]") or rest.startswith("[X]"):
                lines[i] = prefix + "[ ]" + rest[3:]
            else:
                # No marker — inject as checked (user clicked to mark done).
                lines[i] = prefix + "[x] " + rest
            break
        seen += 1
    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


_DAILY_NOTE_SCAFFOLD = """# Daily Note

## Morning Check-in

### My Top 3
1. [ ]
2. [ ]
3. [ ]

### Bonus

### Habits
"""


def _ensure_daily_note_scaffold(path: Path) -> None:
    """Create today's daily note with empty Top 3 / Bonus slots if missing.

    Idempotent — does nothing if the file already exists. Lets the companion
    serve as the morning planning surface for users who haven't run /open-day
    yet (or who prefer to plan visually).
    """
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DAILY_NOTE_SCAFFOLD)


def _set_nth_item_text(md: str, heading: str, index: int, text: str) -> str:
    """Replace the text of the Nth (0-indexed) item under `heading`, preserving
    its `[ ]` / `[x]` checkbox marker. If fewer than N+1 items exist, append
    blank items until index N is present, then set its text.

    Items are numbered list rows (`1. `) or dash rows (`- `). Lines without a
    marker get one injected (`[ ]`) so subsequent toggle clicks work.
    """
    lines = md.splitlines()
    section_start = None
    section_end = len(lines)
    for i, line in enumerate(lines):
        if section_start is None:
            if line.strip() == heading:
                section_start = i
            continue
        if line.startswith("### ") or line.startswith("## "):
            section_end = i
            break

    if section_start is None:
        # Heading missing — append the heading + the item at the end of the note.
        suffix = [heading, f"1. [ ] {text}", ""]
        return md.rstrip("\n") + "\n\n" + "\n".join(suffix) + "\n"

    # Walk items within the section
    item_indices: list[int] = []
    for i in range(section_start + 1, section_end):
        if _LIST_ITEM_RE.match(lines[i]):
            item_indices.append(i)

    def _format_item(n: int, body_text: str) -> str:
        return f"{n}. [ ] {body_text}"

    if index < len(item_indices):
        # Replace existing Nth item; preserve marker (or inject `[ ]` if missing)
        target_line = lines[item_indices[index]]
        m = _LIST_ITEM_RE.match(target_line)
        prefix, rest = m.group(1), m.group(2)
        if rest.startswith("[ ]") or rest.startswith("[x]") or rest.startswith("[X]"):
            marker = rest[:3]
            lines[item_indices[index]] = f"{prefix}{marker} {text}".rstrip()
        else:
            lines[item_indices[index]] = f"{prefix}[ ] {text}".rstrip()
    else:
        # Append blank items up to and including the target index
        insertion_point = item_indices[-1] + 1 if item_indices else section_start + 1
        new_lines = []
        for n in range(len(item_indices), index + 1):
            body = text if n == index else ""
            new_lines.append(_format_item(n + 1, body).rstrip())
        # Insert without trailing blank shift
        lines[insertion_point:insertion_point] = new_lines

    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def _replace_section_body(md: str, section_name: str, new_body: str) -> str:
    """Replace the body of `## <section_name>` with new_body, preserving
    surrounding sections. If section doesn't exist, append it at the end.
    """
    heading = f"## {section_name}"
    lines = md.splitlines()
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i
            continue
        if start is not None and line.startswith("## ") and not line.startswith("### "):
            end = i
            break
    new_block = [heading, "", new_body.rstrip(), ""]
    if start is None:
        return md.rstrip("\n") + "\n\n" + "\n".join(new_block) + "\n"
    return "\n".join(lines[:start] + new_block + lines[end:]) + ("\n" if md.endswith("\n") else "")


def _habit_state_for(app, habit_id: str, today: str, percent: float) -> dict:
    """Build the dict expected by _components/habit_row.html for a single habit."""
    habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
    log_path = app.config["VAULT_PATH"] / "30-habits" / "log.md"
    habits = (
        parse_habits(habits_path.read_text())
        if habits_path.exists()
        else {"active": [], "archived": []}
    )
    log = parse_log(log_path.read_text()) if log_path.exists() else []

    habit = next((h for h in habits["active"] if h["id"] == habit_id), None)
    if habit is None:
        return {
            "id": habit_id, "name": "", "emoji": "", "percent": percent,
            "streak_days": 0, "status": "ok",
        }
    habit_log = [
        DayResult(d["date"], d["ticks"].get(habit_id, 0.0))
        for d in log
        if habit_id in d["ticks"]
    ]
    return {
        "id": habit["id"],
        "name": habit["name"],
        "emoji": habit.get("emoji", ""),
        "percent": percent,
        "streak_days": streak_days(habit_log),
        "status": status_for(compute_concern(habit_log)),
    }


def _detect_day_state(daily_md: str, top_3: list) -> str:
    """Return one of 'coach-morning', 'command', 'coach-evening', 'results'.

    Detection rules:
      - If `## Insight Reflection` body has content → 'results' (day is closed).
      - Else if `## Insight Reflection` heading exists but body is empty → 'coach-evening'.
      - Else if Top 3 has items and all have text → 'command' (Command Center).
      - Else → 'coach-morning' (no note yet, or Top 3 missing/empty).
    """
    sections = parse_daily_note_sections(daily_md)
    insight = sections.get("Insight Reflection", "").strip()
    if insight:
        return "results"
    if "Insight Reflection" in sections:
        return "coach-evening"
    if top_3 and all(item.get("text") for item in top_3):
        return "command"
    return "coach-morning"


def _build_day_context(app, daily_md: str, top_3: list, bonus: list, today: str) -> dict:
    """Assemble template context shared by all four day-tab modes."""
    try:
        today_pretty = datetime.strptime(today, "%Y-%m-%d").strftime("%A, %B %-d, %Y")
    except ValueError:
        today_pretty = datetime.strptime(today, "%Y-%m-%d").strftime("%A, %B %d, %Y")

    habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
    log_path = app.config["VAULT_PATH"] / "30-habits" / "log.md"
    habits = (
        parse_habits(habits_path.read_text())
        if habits_path.exists()
        else {"active": [], "archived": []}
    )
    log = parse_log(log_path.read_text()) if log_path.exists() else []
    today_log = next((r["ticks"] for r in log if r["date"] == today), {})

    habits_today = []
    for h in habits["active"]:
        habit_log = [
            DayResult(d["date"], d["ticks"].get(h["id"], 0.0))
            for d in log
            if h["id"] in d["ticks"]
        ]
        habits_today.append({
            "id": h["id"],
            "name": h["name"],
            "emoji": h.get("emoji", ""),
            "percent": today_log.get(h["id"], 0.0),
            "streak_days": streak_days(habit_log),
            "status": status_for(compute_concern(habit_log)),
        })

    # Stats for evening modes / results
    top_3_done = sum(1 for t in top_3 if t.get("checked"))
    habits_done = sum(1 for h in habits_today if h["percent"] >= 1.0)
    stats = {
        "top_3_done": top_3_done,
        "top_3_total": len(top_3),
        "habits_done": habits_done,
        "habits_total": len(habits["active"]),
        "focus_hours": 0,  # Phase 2 — focus blocks not yet tracked
        "streak_days": max((h["streak_days"] for h in habits_today), default=0),
    }

    try:
        step = int(request.args.get("step", 1))
    except (TypeError, ValueError):
        step = 1

    # Coach Cards always renders 3 Top 3 + 3 Bonus input rows so the user
    # can start typing even on a fresh vault (auto-save creates the note).
    top_3_slots = list(top_3) + [{"text": "", "checked": False}] * max(0, 3 - len(top_3))
    bonus_slots = list(bonus) + [{"text": "", "checked": False}] * max(0, 3 - len(bonus))

    plan = _build_plan_context(daily_md, app.config["VAULT_PATH"], today, top_3, bonus)

    return {
        "today": today,
        "today_pretty": today_pretty,
        "note_md": daily_md,
        "top_3": top_3,
        "top_3_slots": top_3_slots[:3],
        "bonus": bonus,
        "bonus_slots": bonus_slots[:3],
        "bonus_text": "\n".join(b["text"] for b in bonus),
        "habits_today": habits_today,
        "active_habits": habits["active"],
        "focus_blocks": [],  # Phase 2
        "stats": stats,
        "step": step,
        "plan": plan,
    }


def create_app(vault_path: str) -> Flask:
    app = Flask(__name__)
    app.config["VAULT_PATH"] = Path(vault_path)

    subscribers: list[queue.Queue] = []
    last_hashes: dict[str, str] = {}  # relpath -> sha256[:16] of last broadcast

    @app.route("/")
    def index():
        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        daily_md = note_path.read_text() if note_path.exists() else ""

        # Extract sections from the Morning Check-in block
        sections = parse_daily_note_sections(daily_md)
        morning = sections.get("Morning Check-in", "")
        top_3 = _extract_top_3(morning)
        bonus = _extract_bonus(morning)
        insight_reflection_text = sections.get("Insight Reflection", "").strip()
        gratitude_text = sections.get("Gratitude", "").strip()

        # User override → respected; otherwise auto-detect
        mode = request.args.get("mode") or _detect_day_state(daily_md, top_3)

        ctx = _build_day_context(app, daily_md, top_3, bonus, today)
        ctx["insight_reflection_text"] = insight_reflection_text
        ctx["gratitude_text"] = gratitude_text
        ctx["mode"] = mode

        return render_template("day.html", **ctx)

    @app.route("/week")
    def week():
        y, w, _ = date.today().isocalendar()
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{y}-W{w:02d}.md"
        week_md = path.read_text() if path.exists() else ""
        return render_template("week.html", week_md=week_md, week_of=f"{y}-W{w:02d}")

    @app.route("/streaks")
    def streaks():
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        log_path = app.config["VAULT_PATH"] / "30-habits" / "log.md"
        habits = (
            parse_habits(habits_path.read_text())
            if habits_path.exists()
            else {"active": [], "archived": []}
        )
        log = parse_log(log_path.read_text()) if log_path.exists() else []

        today = date.today()
        rows = []
        for h in habits["active"]:
            habit_log = [
                DayResult(d["date"], d["ticks"].get(h["id"], 0.0))
                for d in log
                if h["id"] in d["ticks"]
            ]
            cells = []
            for i in range(29, -1, -1):
                day = (today - timedelta(days=i)).isoformat()
                pct = next(
                    (d["ticks"].get(h["id"]) for d in log if d["date"] == day),
                    None,
                )
                cells.append({"date": day, "percent": pct})
            concern = compute_concern(habit_log)
            rows.append({
                "habit": h,
                "streak_days": streak_days(habit_log),
                "concern": concern,
                "status": status_for(concern),
                "cells": cells,
            })
        return render_template("streaks.html", today=today.isoformat(), rows=rows)

    @app.route("/lock-in", methods=["POST"])
    def lock_in():
        """Transition the view from Coach Cards to the next state. No vault writes."""
        phase = request.form.get("phase", "morning")
        target_mode = "command" if phase == "morning" else "results"

        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        daily_md = note_path.read_text() if note_path.exists() else ""
        sections = parse_daily_note_sections(daily_md)
        morning = sections.get("Morning Check-in", "")
        top_3 = _extract_top_3(morning)
        bonus = _extract_bonus(morning)

        ctx = _build_day_context(app, daily_md, top_3, bonus, today)
        ctx["insight_reflection_text"] = sections.get("Insight Reflection", "").strip()
        ctx["gratitude_text"] = sections.get("Gratitude", "").strip()
        ctx["mode"] = target_mode
        return render_template("day.html", **ctx)

    @app.route("/events")
    def events():
        if len(subscribers) >= 10:
            return ("too many subscribers", 429)
        q: queue.Queue = queue.Queue()
        subscribers.append(q)

        def stream():
            try:
                while True:
                    msg = q.get()
                    yield f"data: {msg}\n\n"
            finally:
                try:
                    subscribers.remove(q)
                except ValueError:
                    pass

        return Response(stream_with_context(stream()), mimetype="text/event-stream")

    def broadcast(relpath: str) -> None:
        # Content-hash dedup: skip if the file's content hasn't changed since
        # the last broadcast. Prevents iCloud-echo reload storms when the
        # same write propagates back through sync.
        full_path = app.config["VAULT_PATH"] / relpath
        try:
            data = full_path.read_bytes()
        except FileNotFoundError:
            return
        digest = hashlib.sha256(data).hexdigest()[:16]
        if last_hashes.get(relpath) == digest:
            return
        last_hashes[relpath] = digest
        for q in list(subscribers):
            try:
                q.put_nowait(relpath)
            except queue.Full:
                pass

    app.config["BROADCAST"] = broadcast

    @app.route("/tick", methods=["POST"])
    def tick():
        habit_id = request.form.get("habit_id", "").strip()
        if not HABIT_ID_RE.fullmatch(habit_id):
            return ("invalid habit_id", 400)
        try:
            percent = float(request.form.get("percent", ""))
        except ValueError:
            return ("invalid percent", 400)
        if percent not in (0.0, 0.5, 1.0):
            return ("percent must be 0.0 / 0.5 / 1.0", 400)

        today = date.today().isoformat()
        log_path = app.config["VAULT_PATH"] / "30-habits" / "log.md"

        def merge(existing: str) -> str:
            rows = parse_log(existing)
            today_ticks = next(
                (r["ticks"] for r in rows if r["date"] == today), {}
            )
            today_ticks[habit_id] = percent
            return append_day_to_log(existing, today, today_ticks)

        safe_modify(log_path, merge)
        broadcast("30-habits/log.md")
        return render_template(
            "_components/habit_row.html",
            h=_habit_state_for(app, habit_id, today, percent),
        )

    @app.route("/toggle", methods=["POST"])
    def toggle():
        try:
            section, index = validate_toggle(request.form)
        except ValueError as e:
            return (str(e), 400)

        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        if not note_path.exists():
            return ("today's note not found", 404)

        heading = "### My Top 3" if section == "top_3" else "### Bonus"

        def toggle_in_section(existing: str) -> str:
            return _toggle_nth_checkbox(existing, heading, index)

        safe_modify(note_path, toggle_in_section)
        broadcast(f"01-daily/{today}.md")
        return ("", 204)

    @app.route("/save", methods=["POST"])
    def save():
        try:
            section, content = validate_save(request.form)
        except ValueError as e:
            return (str(e), 400)

        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        if not note_path.exists():
            return ("today's note not found", 404)

        def replace_section(existing: str) -> str:
            return _replace_section_body(existing, section, content)

        safe_modify(note_path, replace_section)
        broadcast(f"01-daily/{today}.md")
        return ("", 204)

    @app.route("/set-top-3", methods=["POST"])
    def set_top_3():
        return _set_morning_item("### My Top 3", "top_3", rerender_partial=True)

    @app.route("/set-bonus", methods=["POST"])
    def set_bonus():
        return _set_morning_item("### Bonus", "bonus", rerender_partial=True)

    @app.route("/delete-bonus", methods=["POST"])
    def delete_bonus():
        """Remove a bonus item by index and re-render the plan partial."""
        try:
            index = int(request.form.get("index", ""))
        except (TypeError, ValueError):
            return ("invalid index", 400)

        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        if not note_path.exists():
            return ("today's note not found", 404)

        def remove(existing: str) -> str:
            lines = existing.splitlines()
            in_section = False
            seen = 0
            for i, line in enumerate(lines):
                if line.strip() == "### Bonus":
                    in_section = True
                    continue
                if in_section and (line.startswith("### ") or line.startswith("## ")):
                    break
                if in_section and _LIST_ITEM_RE.match(line):
                    if seen == index:
                        del lines[i]
                        # Renumber remaining items
                        remaining_idx = 0
                        for j in range(i, len(lines)):
                            if lines[j].startswith("### ") or lines[j].startswith("## "):
                                break
                            m = _LIST_ITEM_RE.match(lines[j])
                            if m:
                                prefix_m = re.match(r"^(\s*)(\d+\.|-)\s+", lines[j])
                                if prefix_m and prefix_m.group(2) != "-":
                                    rest = lines[j][prefix_m.end():]
                                    lines[j] = f"{remaining_idx + 1}. {rest}"
                                remaining_idx += 1
                        break
                    seen += 1
            return "\n".join(lines) + ("\n" if existing.endswith("\n") else "")

        safe_modify(note_path, remove)
        broadcast(f"01-daily/{today}.md")

        daily_md = note_path.read_text()
        sections = parse_daily_note_sections(daily_md)
        morning = sections.get("Morning Check-in", "")
        top_3 = _extract_top_3(morning)
        bonus_items = _extract_bonus(morning)
        plan = _build_plan_context(daily_md, app.config["VAULT_PATH"], today, top_3, bonus_items)
        return render_template("_components/plan_your_day.html", plan=plan)

    @app.route("/add-bonus-slot", methods=["POST"])
    def add_bonus_slot():
        """Re-render the plan partial — the template always shows one empty
        slot at the end, so this is effectively a no-op that just re-renders."""
        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        daily_md = note_path.read_text() if note_path.exists() else ""
        sections = parse_daily_note_sections(daily_md)
        morning = sections.get("Morning Check-in", "")
        top_3 = _extract_top_3(morning)
        bonus_items = _extract_bonus(morning)
        plan = _build_plan_context(daily_md, app.config["VAULT_PATH"], today, top_3, bonus_items)
        return render_template("_components/plan_your_day.html", plan=plan)

    @app.route("/reset-plan", methods=["POST"])
    def reset_plan():
        """Reset Top 3, Bonus, and Dismissed back to empty scaffold."""
        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        if not note_path.exists():
            return ("no note to reset", 404)

        def reset(existing: str) -> str:
            # Clear Top 3 items
            for heading in ("### My Top 3", "### Bonus", "### Dismissed"):
                lines = existing.splitlines()
                section_start = None
                section_end = len(lines)
                for i, line in enumerate(lines):
                    if line.strip() == heading:
                        section_start = i
                        continue
                    if section_start is not None and (line.startswith("### ") or line.startswith("## ")):
                        section_end = i
                        break
                if section_start is not None:
                    if heading == "### My Top 3":
                        replacement = [heading, "1. [ ]", "2. [ ]", "3. [ ]", ""]
                    elif heading == "### Bonus":
                        replacement = [heading, ""]
                    else:  # Dismissed — remove entirely
                        replacement = []
                    existing = "\n".join(lines[:section_start] + replacement + lines[section_end:])
                    if not existing.endswith("\n"):
                        existing += "\n"
            return existing

        safe_modify(note_path, reset)
        broadcast(f"01-daily/{today}.md")

        daily_md = note_path.read_text()
        sections = parse_daily_note_sections(daily_md)
        morning = sections.get("Morning Check-in", "")
        top_3 = _extract_top_3(morning)
        bonus_items = _extract_bonus(morning)
        plan = _build_plan_context(daily_md, app.config["VAULT_PATH"], today, top_3, bonus_items)
        return render_template("_components/plan_your_day.html", plan=plan)

    @app.route("/empty")
    def empty():
        """Return an empty body. Used as the target of Cancel buttons that
        want to clear a slot without server-side state changes."""
        return ""

    @app.route("/plan-action", methods=["POST"])
    def plan_action():
        """Handle a Plan-Your-Day suggestion-row action: pri / bonus / done.

        Returns the freshly-rendered plan_your_day.html partial for HTMX swap.
        """
        action = (request.form.get("action") or "").strip().lower()
        text = (request.form.get("text") or "").strip()
        if action not in {"pri", "bonus", "done", "delete"}:
            return ("invalid action", 400)
        if not text or "\n" in text or "\r" in text or len(text) > 256:
            return ("invalid text", 400)

        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        _ensure_daily_note_scaffold(note_path)

        def update(existing: str) -> str:
            sections = parse_daily_note_sections(existing)
            morning = sections.get("Morning Check-in", "")
            top_3 = _extract_top_3(morning)
            bonus_items = _extract_bonus(morning)

            # Done / Delete: toggle in ### Dismissed (reversible)
            if action in {"done", "delete"}:
                dismissed_items = _extract_dismissed(
                    parse_daily_note_sections(existing).get("Morning Check-in", "")
                )
                if text in dismissed_items:
                    return _remove_dismissed(existing, text)
                return _add_dismissed(existing, text)

            # If the suggestion already sits in Top 3 / Bonus and the user
            # clicked the same column again, treat it as "untake" — clear it.
            for i, t in enumerate(top_3):
                if t.get("text") == text:
                    if action == "pri":
                        return _set_nth_item_text(existing, "### My Top 3", i, "")
                    existing = _set_nth_item_text(existing, "### My Top 3", i, "")
                    break
            for i, b in enumerate(bonus_items):
                if b.get("text") == text:
                    if action == "bonus":
                        return _set_nth_item_text(existing, "### Bonus", i, "")
                    existing = _set_nth_item_text(existing, "### Bonus", i, "")
                    break

            # Re-read state after any clears so we pick the right empty slot.
            sections = parse_daily_note_sections(existing)
            morning = sections.get("Morning Check-in", "")
            top_3 = _extract_top_3(morning)
            bonus_items = _extract_bonus(morning)

            if action == "pri":
                # Use _extract_numbered_checkbox_list with empty items to find
                # the first empty slot in the raw markdown (not the filtered
                # list which skips blanks and would miss cleared slots).
                raw_items = _extract_numbered_checkbox_list_raw(morning, "### My Top 3")
                for i in range(min(3, len(raw_items))):
                    if not raw_items[i].get("text"):
                        return _set_nth_item_text(existing, "### My Top 3", i, text)
                # All 3 slots occupied — try appending if < 3 raw items
                if len(raw_items) < 3:
                    return _set_nth_item_text(existing, "### My Top 3", len(raw_items), text)
                return existing  # Top 3 full; client respects the disabled attr.
            if action == "bonus":
                for i, b in enumerate(bonus_items):
                    if not b.get("text"):
                        return _set_nth_item_text(existing, "### Bonus", i, text)
                return _set_nth_item_text(existing, "### Bonus", len(bonus_items), text)
            return existing

        safe_modify(note_path, update)
        broadcast(f"01-daily/{today}.md")

        # Re-render the partial with fresh state for HTMX swap.
        daily_md = note_path.read_text()
        sections = parse_daily_note_sections(daily_md)
        morning = sections.get("Morning Check-in", "")
        top_3 = _extract_top_3(morning)
        bonus_items = _extract_bonus(morning)
        plan = _build_plan_context(daily_md, app.config["VAULT_PATH"], today, top_3, bonus_items)
        return render_template("_components/plan_your_day.html", plan=plan)

    def _set_morning_item(heading: str, broadcast_label: str, rerender_partial: bool = False):
        try:
            index = int(request.form.get("index", ""))
        except (TypeError, ValueError):
            return ("invalid index", 400)
        if index < 0 or index > 9:
            return ("index out of bounds", 400)
        text = request.form.get("text", "").rstrip()
        if "\n" in text or "\r" in text or len(text) > 256:
            return ("text must be a single line ≤256 chars", 400)

        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        _ensure_daily_note_scaffold(note_path)

        def update(existing: str) -> str:
            return _set_nth_item_text(existing, heading, index, text)

        safe_modify(note_path, update)
        broadcast(f"01-daily/{today}.md")
        if not rerender_partial:
            return ("", 204)

        # Return the freshly-rendered plan_your_day partial so the input
        # indices advance and a new empty Bonus slot appears as items pile up.
        daily_md = note_path.read_text()
        sections = parse_daily_note_sections(daily_md)
        morning = sections.get("Morning Check-in", "")
        top_3 = _extract_top_3(morning)
        bonus_items = _extract_bonus(morning)
        plan = _build_plan_context(daily_md, app.config["VAULT_PATH"], today, top_3, bonus_items)
        return render_template("_components/plan_your_day.html", plan=plan)

    def _get_active_habits():
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        if habits_path.exists():
            return parse_habits(habits_path.read_text())["active"]
        return []

    @app.route("/add-habit-form")
    def add_habit_form():
        return render_template("_components/add_habit_form.html",
                               habits=_get_active_habits())

    @app.route("/manage-habits")
    def manage_habits():
        return render_template("_components/add_habit_form.html",
                               habits=_get_active_habits())

    @app.route("/habit", methods=["POST"])
    def add_habit():
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        existing_md = habits_path.read_text() if habits_path.exists() else ""
        existing_ids: set[str] = set()
        if existing_md:
            parsed = parse_habits(existing_md)
            existing_ids = {h["id"] for h in parsed["active"]} | {h["id"] for h in parsed["archived"]}

        try:
            fields = validate_habit_fields(request.form, existing_ids=existing_ids)
        except ValueError as e:
            return (str(e), 400)

        new_entry = (
            f"\n- id: {fields['id']}\n"
            f"  name: {fields['name']}\n"
        )
        if fields.get("emoji"):
            new_entry += f"  emoji: {fields['emoji']}\n"
        new_entry += f"  target: {fields['target']}\n"
        new_entry += f"  frequency: {fields['frequency']}\n\n"  # trailing blank separates habits and pushes ## Archived off the last field

        def insert(existing: str) -> str:
            md = existing or "# Daily Habits\n\n## Active\n\n## Archived\n"
            # Replace the "(none yet — add habits …)" placeholder if present so
            # the first habit doesn't sit awkwardly underneath it.
            md = re.sub(
                r"## Active\n+\(none yet[^\n]*\)\n+",
                "## Active\n",
                md,
                count=1,
            )
            if "## Active\n" not in md:
                # Defensive: badly-shaped habits.md — append a heading.
                md = md.rstrip("\n") + "\n\n## Active\n"
            return md.replace("## Active\n", "## Active\n" + new_entry, 1)

        try:
            safe_modify(habits_path, insert)
        except ValueError as e:
            return (str(e), 400)
        broadcast("30-habits/habits.md")
        # Return the manage view with success message + updated habit list.
        return render_template(
            "_components/add_habit_form.html",
            habits=_get_active_habits(),
            success_message=f'Added "{fields["name"]}" to your habits.',
        )

    @app.route("/habit/archive", methods=["POST"])
    def archive_habit():
        habit_id = request.form.get("habit_id", "").strip()
        if not HABIT_ID_RE.fullmatch(habit_id):
            return ("invalid habit_id", 400)
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        if not habits_path.exists():
            return ("", 404)
        found = [False]

        def archive(existing: str) -> str:
            habits = parse_habits(existing)
            active = habits["active"]
            target = next((h for h in active if h["id"] == habit_id), None)
            if target is None:
                return existing  # signal not-found via found[0]
            found[0] = True
            target["archived_at"] = date.today().isoformat()
            habits["active"] = [h for h in active if h["id"] != habit_id]
            habits["archived"].append(target)
            return _serialize_habits(habits)

        safe_modify(habits_path, archive)
        if not found[0]:
            return ("habit not found", 404)
        broadcast("30-habits/habits.md")
        return render_template(
            "_components/add_habit_form.html",
            habits=_get_active_habits(),
        )

    watcher = VaultWatcher(vault_path, on_change=broadcast)
    watcher.start()
    app.config["WATCHER"] = watcher

    return app
