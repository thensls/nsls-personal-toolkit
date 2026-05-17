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


def _extract_top_3(morning_section: str) -> list[dict]:
    return _extract_numbered_checkbox_list(morning_section, "### My Top 3")


def _extract_bonus(morning_section: str) -> list[dict]:
    return _extract_numbered_checkbox_list(morning_section, "### Bonus")


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
1. [ ]
2. [ ]
3. [ ]

### Habits

(Add habits via the companion's Streaks tab, or seed `30-habits/habits.md` from the template.)
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
        return _set_morning_item("### My Top 3", "top_3")

    @app.route("/set-bonus", methods=["POST"])
    def set_bonus():
        return _set_morning_item("### Bonus", "bonus")

    def _set_morning_item(heading: str, broadcast_label: str):
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
        return ("", 204)

    @app.route("/add-habit-form")
    def add_habit_form():
        return render_template("_components/add_habit_form.html")

    @app.route("/habit", methods=["POST"])
    def add_habit():
        try:
            fields = validate_habit_fields(request.form)
        except ValueError as e:
            return (str(e), 400)
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        new_entry = (
            f"\n- id: {fields['id']}\n"
            f"  name: {fields['name']}\n"
            f"  emoji: {fields['emoji']}\n"
            f"  target: {fields['target']}\n"
            f"  frequency: {fields['frequency']}\n"
        )

        def insert(existing: str) -> str:
            md = existing or "# Daily Habits\n\n## Active\n\n## Archived\n"
            parsed = parse_habits(md)
            existing_ids = {h["id"] for h in parsed["active"]} | {h["id"] for h in parsed["archived"]}
            if fields["id"] in existing_ids:
                raise ValueError("habit id already exists")
            return md.replace("## Active\n", "## Active\n" + new_entry, 1)

        try:
            safe_modify(habits_path, insert)
        except ValueError as e:
            return (str(e), 400)
        broadcast("30-habits/habits.md")
        return ("", 204)

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
        return ("", 204)

    watcher = VaultWatcher(vault_path, on_change=broadcast)
    watcher.start()
    app.config["WATCHER"] = watcher

    return app
