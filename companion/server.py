"""Flask app factory for the NSLS toolkit companion."""

import hashlib
import queue
from datetime import date
from pathlib import Path

from flask import Flask, Response, render_template, stream_with_context

from companion.watcher import VaultWatcher


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
        return render_template("day.html", today=today, note_md=note_md)

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
