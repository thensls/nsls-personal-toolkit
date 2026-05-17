"""Flask app factory for the NSLS toolkit companion."""

import hashlib
import queue
from datetime import date
from pathlib import Path

from flask import Flask, Response, render_template, stream_with_context

from companion.parsers import parse_daily_note_sections, parse_habits, parse_log
from companion.streak import DayResult, compute_concern, status_for, streak_days
from companion.watcher import VaultWatcher


def _extract_top_3(morning_section: str) -> list[str]:
    items: list[str] = []
    in_top_3 = False
    for line in morning_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("### My Top 3"):
            in_top_3 = True
            continue
        if in_top_3 and stripped.startswith("###"):
            break
        if in_top_3 and stripped and stripped[0].isdigit():
            text = stripped.split(".", 1)[-1].strip()
            if text:
                items.append(text)
    return items


def _extract_bonus(morning_section: str) -> list[str]:
    items: list[str] = []
    in_bonus = False
    for line in morning_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("### Bonus"):
            in_bonus = True
            continue
        if in_bonus and stripped.startswith("###"):
            break
        if in_bonus and stripped and stripped[0].isdigit():
            text = stripped.split(".", 1)[-1].strip()
            if text:
                items.append(text)
    return items


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

    watcher = VaultWatcher(vault_path, on_change=broadcast)
    watcher.start()
    app.config["WATCHER"] = watcher

    return app
