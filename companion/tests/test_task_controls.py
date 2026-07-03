"""Tests for per-task progress (0/25/50/75/100) and reversible delete-mark on
the Command Center Top 3 + Bonus lists. Redesigned 2026-06-13:
- progress levels 0/25/50/75/100; clicking the active level toggles to 0
- carry button removed (anything <100% auto-carries at close-day)
- delete is a reversible mark (adds/removes from ### Deleted), keeps the row
- progress and delete are independent
"""

from datetime import date
import pytest
from companion.server import (
    create_app, _extract_top_3, _extract_bonus, _strip_progress,
    _extract_subsection_items,
)
from companion.parsers import parse_daily_note_sections


@pytest.fixture
def client_with_today(tmp_path):
    vault = tmp_path / "vault"
    daily = vault / "01-daily"
    daily.mkdir(parents=True)
    habits = vault / "30-habits"
    habits.mkdir(parents=True)

    today = date.today().isoformat()
    (daily / f"{today}.md").write_text("""# Daily Note

## Morning Check-in

### My Top 3
1. [ ] Ship the week view
2. [ ] Draft cowork
3. [ ] Happy path docs

### Bonus
1. [ ] brainstorm marketing
2. [ ] three breaths

### Habits
- [ ] **Walk**
""")
    (habits / "habits.md").write_text("# Daily Habits\n\n## Active\n\n- id: walk\n  name: Walk\n")
    (habits / "log.md").write_text("# Daily habit log\n")

    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield (app.test_client(), vault)
    finally:
        app.config["WATCHER"].stop()


def _note(vault):
    return (vault / "01-daily" / f"{date.today().isoformat()}.md").read_text()


def _morning(vault):
    return parse_daily_note_sections(_note(vault)).get("Morning Check-in", "")


def _top3(vault):
    return _extract_top_3(_morning(vault))


# --- progress: 0 / 25 / 50 / 75 / 100 ---

def test_set_progress_partial_writes_marker(client_with_today):
    client, vault = client_with_today
    resp = client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "50"})
    assert resp.status_code == 200
    items = _top3(vault)
    assert items[0]["text"] == "Ship the week view"   # text stays clean
    assert items[0]["progress"] == 50
    assert items[0]["checked"] is False


def test_75_is_valid_70_is_not(client_with_today):
    client, vault = client_with_today
    assert client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "75"}).status_code == 200
    assert _top3(vault)[0]["progress"] == 75
    assert client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "70"}).status_code == 400


def test_set_progress_100_checks_box_no_marker(client_with_today):
    client, vault = client_with_today
    client.post("/set-progress", data={"section": "top_3", "index": "1", "level": "100"})
    items = _top3(vault)
    assert items[1]["checked"] is True and items[1]["progress"] == 100
    assert "<!--p:" not in _note(vault)


def test_clicking_active_level_toggles_to_zero(client_with_today):
    """Clicking the already-selected level unsets it — including 100%."""
    client, vault = client_with_today
    client.post("/set-progress", data={"section": "top_3", "index": "2", "level": "100"})
    assert _top3(vault)[2]["progress"] == 100
    # click 100 again → back to 0
    client.post("/set-progress", data={"section": "top_3", "index": "2", "level": "100"})
    assert _top3(vault)[2]["progress"] == 0
    assert _top3(vault)[2]["checked"] is False


def test_zero_is_a_real_level(client_with_today):
    client, vault = client_with_today
    client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "50"})
    client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "0"})
    assert _top3(vault)[0]["progress"] == 0
    assert "<!--p:" not in _note(vault)


def test_progress_marker_invisible_in_text(client_with_today):
    client, vault = client_with_today
    clean, prog = _strip_progress("Ship it <!--p:75-->")
    assert clean == "Ship it" and prog == 75
    client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "75"})
    assert _top3(vault)[0]["text"] == "Ship the week view"


def test_set_progress_rejects_bad_level(client_with_today):
    client, _ = client_with_today
    assert client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "33"}).status_code == 400


# --- delete is a reversible mark, not a removal ---

def test_delete_marks_keeps_row(client_with_today):
    client, vault = client_with_today
    resp = client.post("/delete-task", data={"section": "top_3", "index": "1"})
    assert resp.status_code == 200
    # row still present in Top 3
    assert any(i["text"] == "Draft cowork" for i in _top3(vault))
    # and marked in ### Deleted
    assert "Draft cowork" in _extract_subsection_items(_morning(vault), "Deleted")


def test_delete_toggles_off(client_with_today):
    client, vault = client_with_today
    client.post("/delete-task", data={"section": "top_3", "index": "1"})
    client.post("/delete-task", data={"section": "top_3", "index": "1"})
    assert "Draft cowork" not in _extract_subsection_items(_morning(vault), "Deleted")
    assert any(i["text"] == "Draft cowork" for i in _top3(vault))  # still there


def test_progress_and_delete_coexist(client_with_today):
    client, vault = client_with_today
    client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "50"})
    client.post("/delete-task", data={"section": "top_3", "index": "0"})
    items = _top3(vault)
    assert items[0]["progress"] == 50
    assert "Ship the week view" in _extract_subsection_items(_morning(vault), "Deleted")


def test_delete_works_on_bonus(client_with_today):
    client, vault = client_with_today
    client.post("/delete-task", data={"section": "bonus", "index": "0"})
    assert "brainstorm marketing" in _extract_subsection_items(_morning(vault), "Deleted")
    assert any(b["text"] == "brainstorm marketing" for b in _extract_bonus(_morning(vault)))


# --- controls must swap the WHOLE table, not a bare <tbody> ---
# A bare <tbody> fragment gets mangled by the browser/HTMX table-parsing
# rules (tbody/tr/td outside a <table> are stripped), which collapsed the
# Command Center layout after the first click.

@pytest.mark.parametrize("route,data", [
    ("/set-progress", {"section": "top_3", "index": "0", "level": "50"}),
    ("/set-estimate", {"section": "top_3", "index": "0", "hours": "1.5"}),
    ("/delete-task", {"section": "bonus", "index": "0"}),
    ("/add-bonus", {"text": "new bonus item"}),
])
def test_task_controls_return_full_table(client_with_today, route, data):
    client, _ = client_with_today
    html = client.post(route, data=data).get_data(as_text=True)
    assert html.lstrip().startswith("<table"), f"{route} must return the full <table>, got: {html[:80]!r}"
    assert 'id="task-table"' in html
    # both sections come back in one swap
    assert "tasklist-top_3" in html and "tasklist-bonus" in html
    # and every control in the fragment targets the whole table
    assert 'hx-target="#task-table"' in html
    assert "#tasklist-" not in html


# --- smoke: Command Center renders the redesigned controls ---

def test_command_center_renders_task_controls(client_with_today):
    client, _ = client_with_today
    html = client.get("/").get_data(as_text=True)
    assert "tasklist-top_3" in html and "tasklist-bonus" in html
    assert "/set-progress" in html and "/delete-task" in html
    assert "/carry-task" not in html          # carry column removed
    # Default (non-closing) Command Center shows the top "come back any time"
    # banner, not the closing "close your day" line.
    assert "back here any time" in html
    assert "close your day" not in html
    assert "return to the terminal" in html.lower()
    # Both energy rows show on the Command Center now: beginning-of-day at top,
    # end-of-day near Insight so it can be captured before close-day runs.
    assert "energy-morning" in html
    assert "energy-evening" in html


def test_command_center_closing_mode_shows_close_line(client_with_today):
    """?closing=1 (set by close-day) swaps the top banner for the bottom
    'type done to close your day' line."""
    client, _ = client_with_today
    html = client.get("/?closing=1").get_data(as_text=True)
    assert "close your day" in html
    assert "back here any time" not in html


def test_evening_energy_appears_once_set(client_with_today):
    """End-of-day energy stays hidden on the Command Center until a value is
    captured (by close-day), then it surfaces so it can be reviewed/edited."""
    client, vault = client_with_today
    note = vault / "01-daily" / f"{date.today().isoformat()}.md"
    note.write_text(note.read_text() + "\n## End of Day\n- Energy: high\n")
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "energy-evening" in html
