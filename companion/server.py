"""Flask app factory for the NSLS toolkit companion."""

import hashlib
import queue
from datetime import date
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
    validate_save,
    validate_toggle,
)
from companion.watcher import VaultWatcher


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


def _toggle_nth_checkbox(md: str, heading: str, index: int) -> str:
    """Toggle the `- [ ]` / `- [x]` on the Nth (0-indexed) list item under `heading`.

    Items under a level-3 heading like `### My Top 3` are numbered list rows
    starting with a digit then `. [ ]` or `. [x]`. We rewrite only the Nth.
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
        stripped = line.lstrip()
        if not stripped or stripped[0] not in "0123456789-":
            continue
        if "[ ]" not in stripped and "[x]" not in stripped:
            continue
        if seen == index:
            if "[ ]" in line:
                lines[i] = line.replace("[ ]", "[x]", 1)
            else:
                lines[i] = line.replace("[x]", "[ ]", 1)
            break
        seen += 1
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


def create_app(vault_path: str) -> Flask:
    app = Flask(__name__)
    app.config["VAULT_PATH"] = Path(vault_path)

    subscribers: list[queue.Queue] = []
    last_hashes: dict[str, str] = {}  # relpath -> sha256[:16] of last broadcast

    @app.route("/")
    def index():
        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        note_md = note_path.read_text() if note_path.exists() else ""

        # Extract sections from the Morning Check-in block
        sections = parse_daily_note_sections(note_md)
        morning = sections.get("Morning Check-in", "")
        top_3 = _extract_top_3(morning)
        bonus = _extract_bonus(morning)

        # Build habits-today state from habits.md + log.md
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        log_path = app.config["VAULT_PATH"] / "30-habits" / "log.md"
        habits = (
            parse_habits(habits_path.read_text())
            if habits_path.exists()
            else {"active": [], "archived": []}
        )
        log = parse_log(log_path.read_text()) if log_path.exists() else []

        today_row = next((r for r in log if r["date"] == today), {"ticks": {}})
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
                "percent": today_row["ticks"].get(h["id"], 0.0),
                "streak_days": streak_days(habit_log),
                "status": status_for(compute_concern(habit_log)),
            })

        return render_template(
            "day.html",
            today=today,
            note_md=note_md,
            top_3=top_3,
            bonus=bonus,
            habits_today=habits_today,
        )

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

    watcher = VaultWatcher(vault_path, on_change=broadcast)
    watcher.start()
    app.config["WATCHER"] = watcher

    return app
