import pytest
from datetime import date
from companion.server import create_app


@pytest.fixture
def client_with_today(tmp_path):
    vault = tmp_path / "vault"
    (vault / "01-daily").mkdir(parents=True)
    (vault / "30-habits").mkdir(parents=True)
    (vault / "30-habits" / "habits.md").write_text("# Daily Habits\n## Active\n\n## Archived\n")
    (vault / "30-habits" / "log.md").write_text("# Log\n")
    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield (app.test_client(), vault)
    finally:
        app.config["WATCHER"].stop()


def test_week_tab_renders_weekly_note_as_markdown(client_with_today):
    client, vault = client_with_today
    weekly = vault / "02-weekly"
    weekly.mkdir(parents=True)
    iso_year, iso_week, _ = date.today().isocalendar()
    (weekly / f"{iso_year}-W{iso_week:02d}.md").write_text(
        "# Week\n\n## Week Plan: 2026-05-12 to 2026-05-18\n\n### Recommended Top 3\n1. Ship toolkit\n"
    )
    resp = client.get("/week")
    assert resp.status_code == 200
    assert b"Ship toolkit" in resp.data


def test_week_tab_shows_helpful_empty_state(client_with_today):
    client, _ = client_with_today
    resp = client.get("/week")
    assert resp.status_code == 200
    assert b"No weekly note yet" in resp.data
    assert b"/open-week" in resp.data
