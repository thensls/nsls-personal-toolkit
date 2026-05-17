"""Flask app factory for the NSLS toolkit companion."""

from datetime import date
from pathlib import Path

from flask import Flask, render_template


def create_app(vault_path: str) -> Flask:
    app = Flask(__name__)
    app.config["VAULT_PATH"] = Path(vault_path)

    @app.route("/")
    def index():
        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        note_md = note_path.read_text() if note_path.exists() else ""
        return render_template("day.html", today=today, note_md=note_md)

    return app
