"""Date-scoped closing: /?date=YYYY-MM-DD serves and writes THAT day's note.

close-day on a past date (e.g. /close-day 2026-07-03 run on 07-05) sends the
builder to /?date=<target>&closing=1. The page must load the past note, force
the closing Command Center view, and every edit must write only that date's
note — never today's.
"""

from datetime import date, timedelta
import pytest
from companion.server import create_app, _extract_top_3
from companion.parsers import parse_daily_note_sections, parse_frontmatter


TODAY = date.today().isoformat()
PAST = (date.today() - timedelta(days=2)).isoformat()


def _note(status: str, task: str) -> str:
    return f"""---
status: {status}
---
# Daily Note

## Morning Check-in

### My Top 3
1. [ ] {task}

### Bonus
1. [ ] bonus for {task}

### Habits
- [ ] **Walk**
"""


@pytest.fixture
def client(tmp_path):
    vault = tmp_path / "vault"
    daily = vault / "01-daily"
    daily.mkdir(parents=True)
    habits = vault / "30-habits"
    habits.mkdir(parents=True)
    (daily / f"{TODAY}.md").write_text(_note("active", "today task"))
    (daily / f"{PAST}.md").write_text(_note("active", "past task"))
    (habits / "habits.md").write_text("# Daily Habits\n\n## Active\n\n- id: walk\n  name: Walk\n")
    (habits / "log.md").write_text("# Daily habit log\n")
    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield (app.test_client(), vault)
    finally:
        app.config["WATCHER"].stop()


def _read(vault, day):
    return (vault / "01-daily" / f"{day}.md").read_text()


def _top3(vault, day):
    morning = parse_daily_note_sections(_read(vault, day)).get("Morning Check-in", "")
    return _extract_top_3(morning)


# --- date-scoped load ---

def test_date_param_loads_that_days_note(client):
    c, _ = client
    html = c.get(f"/?date={PAST}").get_data(as_text=True)
    assert "past task" in html and "today task" not in html


def test_default_loads_today(client):
    c, _ = client
    html = c.get("/").get_data(as_text=True)
    assert "today task" in html and "past task" not in html


def test_page_pins_writes_to_served_date(client):
    """The inherited hx-vals wrapper must carry the served date so every
    HTMX post from the page targets that note."""
    c, _ = client
    html = c.get(f"/?date={PAST}").get_data(as_text=True)
    assert f'hx-vals=\'{{"date": "{PAST}"}}\'' in html


def test_past_date_page_drops_today_framing(client):
    c, _ = client
    html = c.get(f"/?date={PAST}&closing=1").get_data(as_text=True)
    assert "Today —" not in html
    assert "closing out a past day" in html
    today_html = c.get("/").get_data(as_text=True)
    assert "Today —" in today_html
    assert "closing out a past day" not in today_html


# --- date-scoped writes (write-safety) ---

def test_progress_write_touches_only_target_date(client):
    c, vault = client
    before_today = _read(vault, TODAY)
    resp = c.post("/set-progress", data={"section": "top_3", "index": "0",
                                         "level": "75", "date": PAST})
    assert resp.status_code == 200
    assert _top3(vault, PAST)[0]["progress"] == 75
    assert _read(vault, TODAY) == before_today  # today's note untouched


def test_lock_in_done_closes_only_target_date(client):
    c, vault = client
    c.post("/lock-in", data={"phase": "evening", "date": PAST})
    assert parse_frontmatter(_read(vault, PAST)).get("status") == "closed"
    assert parse_frontmatter(_read(vault, TODAY)).get("status") == "active"


# --- closing=1 forces the closing view ---

def test_closing_flag_forces_command_on_planning_note(client):
    """A never-locked-in note (status: planning) must not bounce the builder
    to Plan-your-day mid-close."""
    c, vault = client
    (vault / "01-daily" / f"{PAST}.md").write_text(_note("planning", "past task"))
    html = c.get(f"/?date={PAST}&closing=1").get_data(as_text=True)
    assert 'id="task-table"' in html          # Command Center rendered
    assert "close your day" in html           # in its closing state
    # without the flag, planning still auto-detects to Plan-your-day
    html_plain = c.get(f"/?date={PAST}").get_data(as_text=True)
    assert 'id="task-table"' not in html_plain


def test_closing_flag_on_closed_note_shows_results(client):
    c, vault = client
    note = _note("closed", "past task") + "\n## Insight Reflection\n\nDone well.\n"
    (vault / "01-daily" / f"{PAST}.md").write_text(note)
    html = c.get(f"/?date={PAST}&closing=1").get_data(as_text=True)
    assert "Day closed" in html
    assert 'id="task-table"' not in html


def test_explicit_mode_override_still_wins(client):
    c, _ = client
    html = c.get(f"/?date={PAST}&closing=1&mode=coach-morning").get_data(as_text=True)
    assert 'id="task-table"' not in html
