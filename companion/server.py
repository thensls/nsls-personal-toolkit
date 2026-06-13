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
from companion.week_parsers import (
    parse_quick_notes,
    parse_stack_rank_table,
    parse_week_top_3,
    parse_weekly_frontmatter,
    parse_weekly_note_sections,
    reorder_stack_rank,
    set_project_status,
    set_section_content,
    set_week_top_3_item,
    set_week_top_3_status,
    set_weekly_frontmatter,
    toggle_week_top_3,
)
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


def _extract_unplanned(morning_section: str) -> list[dict]:
    return _extract_numbered_checkbox_list(morning_section, "### Unplanned")


_ENERGY_RE = re.compile(r"^-\s*Energy:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
# Matches an Energy bullet whether or not it has a value (so we can replace
# the empty `- Energy:` the daily-note template seeds, instead of duplicating).
_ENERGY_LINE_RE = re.compile(r"^\s*-\s*Energy:", re.IGNORECASE)

# The toolkit captures energy twice: morning in Morning Check-in (open-day),
# evening in End of Day (close-day). Keep them distinct — never conflate.
_ENERGY_SECTIONS = {"morning": "Morning Check-in", "evening": "End of Day"}


def _extract_energy_for(daily_md: str, section_name: str) -> str:
    """Read the ``- Energy: <value>`` value from a specific section.

    Returns 'low' / 'medium' / 'high', or '' if absent or empty.
    """
    body = parse_daily_note_sections(daily_md).get(section_name, "")
    m = _ENERGY_RE.search(body)
    if m:
        val = m.group(1).strip().lower()
        if val in ("low", "medium", "high"):
            return val
    return ""


def _set_energy_in_section(md: str, section_name: str, level: str) -> str:
    """Set ``- Energy: <level>`` inside ``## <section_name>``.

    Replaces an existing Energy bullet (empty or filled) within the section;
    inserts one right after the heading if none exists; appends the section
    if it's missing. Never creates a duplicate Energy line.
    """
    heading = f"## {section_name}"
    lines = md.splitlines()
    energy_line = f"- Energy: {level}"
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i
            continue
        if start is not None and line.startswith("## ") and not line.startswith("### "):
            end = i
            break
    if start is None:
        return md.rstrip("\n") + f"\n\n{heading}\n{energy_line}\n"
    for i in range(start + 1, end):
        if _ENERGY_LINE_RE.match(lines[i]):
            lines[i] = energy_line
            return "\n".join(lines) + ("\n" if md.endswith("\n") else "")
    lines.insert(start + 1, energy_line)
    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


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


def _extract_subsection_items(morning_section: str, heading: str) -> set[str]:
    """Pull item texts from a `### <heading>` subsection in Morning Check-in.

    `heading` is the bare title (e.g. "Done", "Deleted", "Deferred").
    """
    full = f"### {heading}"
    items: set[str] = set()
    in_section = False
    for line in morning_section.splitlines():
        stripped = line.strip()
        if stripped == full:
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
    done = _extract_subsection_items(morning, "Done")
    deleted = _extract_subsection_items(morning, "Deleted")
    deferred = _extract_subsection_items(morning, "Deferred")
    # Legacy notes used a single `### Dismissed` section for done+delete;
    # treat those as Done so old items still render.
    done |= _extract_subsection_items(morning, "Dismissed")

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
        if s["text"] in done:
            s["taken"] = "done"
        elif s["text"] in deleted:
            s["taken"] = "deleted"
        elif s["text"] in deferred:
            s["taken"] = "deferred"
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


def _add_to_subsection(md: str, heading: str, text: str) -> str:
    """Append `text` as a `- ` item to `### <heading>` under `## Morning Check-in`.

    Creates the subsection if it doesn't exist, placing it at the end of
    Morning Check-in. `heading` is the bare title (e.g. "Done", "Deferred").
    """
    full = f"### {heading}"
    lines = md.splitlines()
    section_idx = None
    morning_end = len(lines)
    in_morning = False
    for i, line in enumerate(lines):
        if line.strip() == "## Morning Check-in":
            in_morning = True
            continue
        if in_morning and line.startswith("## ") and not line.startswith("### "):
            morning_end = i
            break
        if in_morning and line.strip() == full:
            section_idx = i

    if section_idx is not None:
        insert_at = section_idx + 1
        for j in range(section_idx + 1, morning_end):
            if lines[j].startswith("### ") or lines[j].startswith("## "):
                break
            insert_at = j + 1
        lines.insert(insert_at, f"- {text}")
    else:
        insert_at = morning_end
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, full)
        lines.insert(insert_at + 2, f"- {text}")
        lines.insert(insert_at + 3, "")

    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def _remove_from_subsection(md: str, heading: str, text: str) -> str:
    """Remove `text` from the `### <heading>` subsection; drop the heading if empty."""
    full = f"### {heading}"
    lines = md.splitlines()
    target = f"- {text}"
    section_start = None
    section_end = None
    for i, line in enumerate(lines):
        if line.strip() == full:
            section_start = i
        elif section_start is not None and (line.startswith("### ") or line.startswith("## ")):
            section_end = i
            break
    if section_start is None:
        return "\n".join(lines) + ("\n" if md.endswith("\n") else "")
    if section_end is None:
        section_end = len(lines)

    target_idx = None
    for i in range(section_start + 1, section_end):
        if lines[i].strip() == target:
            target_idx = i
            break
    if target_idx is None:
        return "\n".join(lines) + ("\n" if md.endswith("\n") else "")

    del lines[target_idx]
    section_end -= 1

    remaining = any(
        lines[j].strip().startswith("- ")
        for j in range(section_start + 1, section_end)
    )
    if not remaining:
        del lines[section_start]
        if section_start < len(lines) and lines[section_start].strip() == "":
            del lines[section_start]
        if section_start > 0 and lines[section_start - 1].strip() == "":
            del lines[section_start - 1]

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

    # Unplanned items live under ### Unplanned in Morning Check-in
    sections = parse_daily_note_sections(daily_md)
    morning = sections.get("Morning Check-in", "")
    unplanned = _extract_unplanned(morning)

    # Energy is captured twice: morning (Morning Check-in) and evening (End of Day).
    morning_energy = _extract_energy_for(daily_md, "Morning Check-in")
    evening_energy = _extract_energy_for(daily_md, "End of Day")

    return {
        "today": today,
        "today_pretty": today_pretty,
        "note_md": daily_md,
        "top_3": top_3,
        "top_3_slots": top_3_slots[:3],
        "bonus": bonus,
        "bonus_slots": bonus_slots[:3],
        "bonus_text": "\n".join(b["text"] for b in bonus),
        "unplanned": unplanned,
        "morning_energy": morning_energy,
        "evening_energy": evening_energy,
        "habits_today": habits_today,
        "active_habits": habits["active"],
        "focus_blocks": [],  # Phase 2
        "stats": stats,
        "step": step,
        "plan": plan,
    }


def _detect_week_state(weekly_md: str) -> str:
    """Unified mode detection for weekly companion views.

    Uses frontmatter ``status:`` field:
      - closed    -> week-results (close-week completed)
      - confirmed -> week-command (open-week completed, locked in)
      - anything else (draft, editing, or missing) -> plan-week
    """
    fm = parse_weekly_frontmatter(weekly_md)
    status = fm.get("status", "")
    if status == "closed":
        return "week-results"
    if status == "confirmed":
        return "week-command"
    return "plan-week"


def create_app(vault_path: str) -> Flask:
    app = Flask(__name__)
    app.config["VAULT_PATH"] = Path(vault_path)

    subscribers: list[queue.Queue] = []
    last_hashes: dict[str, str] = {}  # relpath -> sha256[:16] of last broadcast

    def _target_date() -> str:
        """Return the target date from ?date= query param or form field, default today.

        Accepts YYYY-MM-DD format. Invalid values fall back to today.
        """
        raw = request.values.get("date", "").strip()
        if raw:
            try:
                date.fromisoformat(raw)
                return raw
            except ValueError:
                pass
        return date.today().isoformat()

    @app.route("/")
    def index():
        today = _target_date()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        daily_md = note_path.read_text() if note_path.exists() else ""

        # Extract sections from the Morning Check-in block
        sections = parse_daily_note_sections(daily_md)
        morning = sections.get("Morning Check-in", "")
        top_3 = _extract_top_3(morning)
        bonus = _extract_bonus(morning)
        insight_reflection_text = sections.get("Insight Reflection", "").strip()
        gratitude_text = sections.get("Gratitude", "").strip()
        daily_insight_text = sections.get("Daily Insight", "").strip()

        # User override → respected; otherwise auto-detect
        mode = request.args.get("mode") or _detect_day_state(daily_md, top_3)

        ctx = _build_day_context(app, daily_md, top_3, bonus, today)
        ctx["insight_reflection_text"] = insight_reflection_text
        ctx["gratitude_text"] = gratitude_text
        ctx["daily_insight_text"] = daily_insight_text
        ctx["mode"] = mode

        return render_template("day.html", **ctx)

    def _week_of() -> str:
        """Return the week identifier from ?week= query param or derive from target date."""
        week_param = request.values.get("week", "").strip()
        if week_param:
            return week_param
        y, w, _ = date.fromisoformat(_target_date()).isocalendar()
        return f"{y}-W{w:02d}"

    @app.route("/week")
    def week():
        week_of = _week_of()
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{week_of}.md"
        week_md = path.read_text() if path.exists() else ""

        mode_override = request.args.get("mode")
        auto_mode = _detect_week_state(week_md)
        # week-review override is respected UNLESS status: closed (auto-detect wins)
        if mode_override == "week-review" and auto_mode != "week-results":
            mode = "week-review"
        else:
            mode = mode_override or auto_mode

        # Parse weekly note content
        fm = parse_weekly_frontmatter(week_md)
        sections = parse_weekly_note_sections(week_md)
        stack_rank = parse_stack_rank_table(week_md)
        top_3 = parse_week_top_3(week_md)

        # Pad top_3 to 3 slots for the template
        top_3_slots = list(top_3) + [{"text": "", "checked": False}] * max(0, 3 - len(top_3))

        # Previous week data for plan-week step 1
        prev_week_md = ""
        prev_sections: dict = {}
        prev_top_3: list = []
        if mode == "plan-week":
            # Try to find the previous week's note
            try:
                y = int(week_of[:4])
                w = int(week_of.split("W")[1])
                if w > 1:
                    prev_key = f"{y}-W{w - 1:02d}"
                else:
                    prev_key = f"{y - 1}-W52"
                prev_path = app.config["VAULT_PATH"] / "02-weekly" / f"{prev_key}.md"
                if prev_path.exists():
                    prev_week_md = prev_path.read_text()
                    prev_sections = parse_weekly_note_sections(prev_week_md)
                    prev_top_3 = parse_week_top_3(prev_week_md)
            except (ValueError, IndexError):
                pass

        # Mode badge text
        week_mode = fm.get("mode", "")
        mode_labels = {
            "push-to-build": "Push-to-build",
            "push-to-close": "Push-to-close",
            "protect": "Protect",
        }
        mode_badge = mode_labels.get(week_mode, week_mode.replace("-", " ").title() if week_mode else "")

        ctx = {
            "week_md": week_md,
            "week_of": week_of,
            "mode": mode,
            "fm": fm,
            "sections": sections,
            "stack_rank": stack_rank,
            "top_3": top_3,
            "top_3_slots": top_3_slots[:3],
            "week_mode": week_mode,
            "mode_badge": mode_badge,
            "prev_week_md": prev_week_md,
            "prev_sections": prev_sections,
            "prev_top_3": prev_top_3,
        }
        return render_template("week.html", **ctx)

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

        today = date.fromisoformat(_target_date())
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

        today = _target_date()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        daily_md = note_path.read_text() if note_path.exists() else ""
        sections = parse_daily_note_sections(daily_md)
        morning = sections.get("Morning Check-in", "")
        top_3 = _extract_top_3(morning)
        bonus = _extract_bonus(morning)

        ctx = _build_day_context(app, daily_md, top_3, bonus, today)
        ctx["insight_reflection_text"] = sections.get("Insight Reflection", "").strip()
        ctx["gratitude_text"] = sections.get("Gratitude", "").strip()
        ctx["daily_insight_text"] = sections.get("Daily Insight", "").strip()
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
        dead: list[queue.Queue] = []
        for q in list(subscribers):
            try:
                q.put_nowait(relpath)
            except queue.Full:
                dead.append(q)
        for q in dead:
            try:
                subscribers.remove(q)
            except ValueError:
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

        today = _target_date()
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

        today = _target_date()
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

        today = _target_date()
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

        today = _target_date()
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

    def _render_unplanned(today: str):
        """Render the unplanned-section partial with fresh indices."""
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        daily_md = note_path.read_text() if note_path.exists() else ""
        morning = parse_daily_note_sections(daily_md).get("Morning Check-in", "")
        unplanned = _extract_unplanned(morning)
        return render_template("_components/unplanned_section.html", unplanned=unplanned)

    @app.route("/set-unplanned", methods=["POST"])
    def set_unplanned():
        try:
            index = int(request.form.get("index", ""))
        except (TypeError, ValueError):
            return ("invalid index", 400)
        if index < 0 or index > 99:
            return ("index out of bounds", 400)
        text = request.form.get("text", "").rstrip()
        if "\n" in text or "\r" in text or len(text) > 256:
            return ("text must be a single line ≤256 chars", 400)

        today = _target_date()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        _ensure_daily_note_scaffold(note_path)
        safe_modify(note_path, lambda md: _set_nth_item_text(md, "### Unplanned", index, text))
        broadcast(f"01-daily/{today}.md")
        # Return the refreshed partial so the blank input's index advances and
        # a new empty slot appears — prevents the stale-index overwrite bug.
        return _render_unplanned(today)

    @app.route("/delete-unplanned", methods=["POST"])
    def delete_unplanned():
        """Remove an unplanned item by index."""
        try:
            index = int(request.form.get("index", ""))
        except (TypeError, ValueError):
            return ("invalid index", 400)

        today = _target_date()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        if not note_path.exists():
            return ("today's note not found", 404)

        def remove(existing: str) -> str:
            lines = existing.splitlines()
            in_section = False
            seen = 0
            for i, line in enumerate(lines):
                if line.strip() == "### Unplanned":
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
        return _render_unplanned(today)

    @app.route("/set-energy", methods=["POST"])
    def set_energy():
        """Set the energy level. ``when`` picks the section:
        morning -> Morning Check-in, evening -> End of Day. Default morning
        (the Command Center captures the day's energy)."""
        level = request.form.get("level", "").strip().lower()
        if level not in ("low", "medium", "high"):
            return ("level must be low/medium/high", 400)
        when = request.form.get("when", "morning").strip().lower()
        section_name = _ENERGY_SECTIONS.get(when)
        if section_name is None:
            return ("when must be morning/evening", 400)

        today = _target_date()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        _ensure_daily_note_scaffold(note_path)

        safe_modify(note_path, lambda md: _set_energy_in_section(md, section_name, level))
        broadcast(f"01-daily/{today}.md")
        return ("", 204)

    @app.route("/add-bonus-slot", methods=["POST"])
    def add_bonus_slot():
        """Re-render the plan partial — the template always shows one empty
        slot at the end, so this is effectively a no-op that just re-renders."""
        today = _target_date()
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
        """Reset Top 3, Bonus, Dismissed, and Deferred back to empty scaffold."""
        today = _target_date()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        if not note_path.exists():
            return ("no note to reset", 404)

        def reset(existing: str) -> str:
            # Clear Top 3 items
            for heading in ("### My Top 3", "### Bonus", "### Done", "### Deleted",
                            "### Deferred", "### Dismissed", "### Unplanned"):
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
                    else:  # Dismissed / Deferred — remove entirely
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
        if action not in {"pri", "bonus", "done", "delete", "defer"}:
            return ("invalid action", 400)
        if not text or "\n" in text or "\r" in text or len(text) > 256:
            return ("invalid text", 400)

        today = _target_date()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        _ensure_daily_note_scaffold(note_path)

        def update(existing: str) -> str:
            sections = parse_daily_note_sections(existing)
            morning = sections.get("Morning Check-in", "")
            top_3 = _extract_top_3(morning)
            bonus_items = _extract_bonus(morning)

            # Done / Delete / Defer are mutually-exclusive dispositions, each in
            # its own subsection. Clicking the active one untoggles it; clicking
            # a different one moves the item (clears the others first).
            DISPOSITIONS = {"done": "Done", "delete": "Deleted", "defer": "Deferred"}
            if action in DISPOSITIONS:
                m = parse_daily_note_sections(existing).get("Morning Check-in", "")
                current = {
                    act: text in _extract_subsection_items(m, head)
                    for act, head in DISPOSITIONS.items()
                }
                # Legacy: items in `### Dismissed` count as Done.
                if text in _extract_subsection_items(m, "Dismissed"):
                    existing = _remove_from_subsection(existing, "Dismissed", text)
                    current["done"] = True
                if current[action]:
                    # Untoggle: remove from its section.
                    return _remove_from_subsection(existing, DISPOSITIONS[action], text)
                # Clear any other disposition, then set this one.
                for act, head in DISPOSITIONS.items():
                    if current[act]:
                        existing = _remove_from_subsection(existing, head, text)
                # A dispositioned item is no longer a live priority — vacate any
                # Top 3 / Bonus slot it occupies so it doesn't show in both.
                for i, t in enumerate(top_3):
                    if t.get("text") == text:
                        existing = _set_nth_item_text(existing, "### My Top 3", i, "")
                for i, b in enumerate(bonus_items):
                    if b.get("text") == text:
                        existing = _set_nth_item_text(existing, "### Bonus", i, "")
                return _add_to_subsection(existing, DISPOSITIONS[action], text)

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

        today = _target_date()
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

    @app.route("/habit/rename", methods=["POST"])
    def habit_rename():
        """Rename a habit, preserving its ID, streak, and log history."""
        habit_id = request.form.get("habit_id", "").strip()
        new_name = request.form.get("new_name", "").strip()
        if not HABIT_ID_RE.fullmatch(habit_id):
            return ("invalid habit_id", 400)
        if not new_name or "\n" in new_name or "\r" in new_name:
            return ("invalid new_name", 400)

        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        if not habits_path.exists():
            return ("", 404)
        found = [False]

        def rename(existing: str) -> str:
            habits = parse_habits(existing)
            target = next((h for h in habits["active"] if h["id"] == habit_id), None)
            if target is None:
                return existing
            found[0] = True
            target["name"] = new_name
            return _serialize_habits(habits)

        safe_modify(habits_path, rename)
        if not found[0]:
            return ("habit not found", 404)
        broadcast("30-habits/habits.md")
        return render_template(
            "_components/add_habit_form.html",
            habits=_get_active_habits(),
        )

    # ------------------------------------------------------------------
    # Week POST routes
    # ------------------------------------------------------------------

    @app.route("/week/set-rank", methods=["POST"])
    def week_set_rank():
        """Reorder the stack rank table. Accepts JSON {"order": [...]} or
        form field ``order`` as comma-separated project names."""
        week_of = _week_of()
        data = request.get_json(silent=True) or {}
        order = data.get("order") or [
            s.strip() for s in request.form.get("order", "").split(",") if s.strip()
        ]
        if not order:
            return ("missing order", 400)
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{week_of}.md"
        if not path.exists():
            return ("weekly note not found", 404)

        def update(existing: str) -> str:
            return reorder_stack_rank(existing, order)

        safe_modify(path, update)
        broadcast(f"02-weekly/{week_of}.md")

        # Re-read and return the updated stack rank partial
        week_md = path.read_text()
        stack_rank = parse_stack_rank_table(week_md)
        return render_template("_components/week_stack_rank_partial.html",
                               stack_rank=stack_rank, week_of=week_of)

    @app.route("/week/set-mode", methods=["POST"])
    def week_set_mode():
        """Set the week mode (push-to-build / push-to-close / protect)."""
        week_of = _week_of()
        mode_val = request.form.get("mode", "").strip()
        if mode_val not in ("push-to-build", "push-to-close", "protect"):
            return ("invalid mode", 400)
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{week_of}.md"
        if not path.exists():
            return ("weekly note not found", 404)

        def update(existing: str) -> str:
            return set_weekly_frontmatter(existing, "mode", mode_val)

        safe_modify(path, update)
        broadcast(f"02-weekly/{week_of}.md")
        return ("", 204)

    @app.route("/week/set-top-3", methods=["POST"])
    def week_set_top_3():
        """Set a weekly Top 3 item by index."""
        week_of = _week_of()
        try:
            index = int(request.form.get("index", ""))
        except (TypeError, ValueError):
            return ("invalid index", 400)
        if index < 0 or index > 9:
            return ("index out of bounds", 400)
        text = request.form.get("text", "").rstrip()
        if "\n" in text or "\r" in text or len(text) > 256:
            return ("text must be a single line <= 256 chars", 400)
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{week_of}.md"
        if not path.exists():
            return ("weekly note not found", 404)

        def update(existing: str) -> str:
            return set_week_top_3_item(existing, index, text)

        safe_modify(path, update)
        broadcast(f"02-weekly/{week_of}.md")
        return ("", 204)

    @app.route("/week/toggle", methods=["POST"])
    def week_toggle():
        """Toggle a weekly Top 3 checkbox."""
        week_of = _week_of()
        try:
            index = int(request.form.get("index", ""))
        except (TypeError, ValueError):
            return ("invalid index", 400)
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{week_of}.md"
        if not path.exists():
            return ("weekly note not found", 404)

        def update(existing: str) -> str:
            return toggle_week_top_3(existing, index)

        safe_modify(path, update)
        broadcast(f"02-weekly/{week_of}.md")
        return ("", 204)

    @app.route("/week/lock-in", methods=["POST"])
    def week_lock_in():
        """Set status: confirmed and transition to week-command mode."""
        week_of = _week_of()
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{week_of}.md"
        if not path.exists():
            return ("weekly note not found", 404)

        def update(existing: str) -> str:
            return set_weekly_frontmatter(existing, "status", "confirmed")

        safe_modify(path, update)
        broadcast(f"02-weekly/{week_of}.md")

        # Re-render the full week view in command mode
        week_md = path.read_text()
        fm = parse_weekly_frontmatter(week_md)
        sections = parse_weekly_note_sections(week_md)
        stack_rank = parse_stack_rank_table(week_md)
        top_3 = parse_week_top_3(week_md)
        top_3_slots = list(top_3) + [{"text": "", "checked": False}] * max(0, 3 - len(top_3))
        week_mode = fm.get("mode", "")
        mode_labels = {
            "push-to-build": "Push-to-build",
            "push-to-close": "Push-to-close",
            "protect": "Protect",
        }
        mode_badge = mode_labels.get(week_mode, "")
        return render_template("week.html",
                               week_md=week_md, week_of=week_of,
                               mode="week-command", fm=fm, sections=sections,
                               stack_rank=stack_rank, top_3=top_3,
                               top_3_slots=top_3_slots[:3],
                               week_mode=week_mode, mode_badge=mode_badge,
                               prev_week_md="", prev_sections={}, prev_top_3=[])

    @app.route("/week/set-priority-status", methods=["POST"])
    def week_set_priority_status():
        """Set a weekly Top 3 item to done/partial/missed (tri-state)."""
        week_of = _week_of()
        try:
            index = int(request.form.get("index", ""))
        except (TypeError, ValueError):
            return ("invalid index", 400)
        status_val = request.form.get("status", "").strip()
        if status_val not in ("done", "partial", "missed"):
            return ("status must be done/partial/missed", 400)
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{week_of}.md"
        if not path.exists():
            return ("weekly note not found", 404)

        def update(existing: str) -> str:
            return set_week_top_3_status(existing, index, status_val)

        safe_modify(path, update)
        broadcast(f"02-weekly/{week_of}.md")
        return ("", 204)

    @app.route("/week/set-project-status", methods=["POST"])
    def week_set_project_status():
        """Set a stack rank project status (on-track/needs-attention/stalled)."""
        week_of = _week_of()
        project = request.form.get("project", "").strip()
        status_val = request.form.get("status", "").strip()
        if not project:
            return ("missing project", 400)
        if status_val not in ("on-track", "needs-attention", "stalled"):
            return ("status must be on-track/needs-attention/stalled", 400)
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{week_of}.md"
        if not path.exists():
            return ("weekly note not found", 404)

        def update(existing: str) -> str:
            return set_project_status(existing, project, status_val)

        safe_modify(path, update)
        broadcast(f"02-weekly/{week_of}.md")
        return ("", 204)

    @app.route("/week/save-section", methods=["POST"])
    def week_save_section():
        """Save content to a ### section in the weekly note (e.g. Brain Dump)."""
        week_of = _week_of()
        section = request.form.get("section", "").strip()
        content = request.form.get("content", "")
        if not section or len(section) > 64:
            return ("invalid section name", 400)
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{week_of}.md"
        if not path.exists():
            return ("weekly note not found", 404)

        def update(existing: str) -> str:
            return set_section_content(existing, section, content)

        safe_modify(path, update)
        broadcast(f"02-weekly/{week_of}.md")
        return ("", 204)

    watcher = VaultWatcher(vault_path, on_change=broadcast)
    watcher.start()
    app.config["WATCHER"] = watcher

    return app
