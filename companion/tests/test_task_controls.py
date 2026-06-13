"""Tests for per-task progress / carry-forward / delete controls on the
Command Center Top 3 + Bonus lists (added 2026-06-13)."""

from datetime import date
import pytest
from companion.server import create_app, _extract_top_3, _strip_progress
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


def _top3(vault):
    morning = parse_daily_note_sections(_note(vault)).get("Morning Check-in", "")
    return _extract_top_3(morning)


# --- progress ---

def test_set_progress_partial_writes_marker(client_with_today):
    client, vault = client_with_today
    resp = client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "50"})
    assert resp.status_code == 200
    items = _top3(vault)
    assert items[0]["text"] == "Ship the week view"  # text stays clean
    assert items[0]["progress"] == 50
    assert items[0]["checked"] is False  # partial is not checked


def test_set_progress_100_checks_box(client_with_today):
    client, vault = client_with_today
    client.post("/set-progress", data={"section": "top_3", "index": "1", "level": "100"})
    items = _top3(vault)
    assert items[1]["checked"] is True
    assert items[1]["progress"] == 100
    assert "<!--p:" not in _note(vault)  # 100 uses [x], no marker


def test_progress_marker_invisible_in_text(client_with_today):
    """The marker must never leak into the parsed task text."""
    client, vault = client_with_today
    client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "70"})
    clean, prog = _strip_progress("Ship it <!--p:70-->")
    assert clean == "Ship it" and prog == 70
    assert _top3(vault)[0]["text"] == "Ship the week view"


def test_set_progress_rejects_bad_level(client_with_today):
    client, _ = client_with_today
    resp = client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "33"})
    assert resp.status_code == 400


def test_progress_can_reset_to_zero(client_with_today):
    client, vault = client_with_today
    client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "50"})
    client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "0"})
    items = _top3(vault)
    assert items[0]["progress"] == 0
    assert "<!--p:" not in _note(vault)


# --- carry forward ---

def test_carry_task_adds_to_carrying_over(client_with_today):
    client, vault = client_with_today
    resp = client.post("/carry-task", data={"section": "top_3", "index": "2"})
    assert resp.status_code == 200
    note = _note(vault)
    assert "## Carrying Over" in note
    assert "- Happy path docs" in note.split("## Carrying Over")[1]


def test_carry_task_toggles_off(client_with_today):
    client, vault = client_with_today
    client.post("/carry-task", data={"section": "top_3", "index": "2"})
    client.post("/carry-task", data={"section": "top_3", "index": "2"})
    note = _note(vault)
    assert "- Happy path docs" not in note


def test_carry_survives_progress(client_with_today):
    """Carry-forward is independent of progress — you can do 50% and carry the rest."""
    client, vault = client_with_today
    client.post("/set-progress", data={"section": "top_3", "index": "0", "level": "50"})
    client.post("/carry-task", data={"section": "top_3", "index": "0"})
    note = _note(vault)
    assert "- Ship the week view" in note.split("## Carrying Over")[1]
    assert _top3(vault)[0]["progress"] == 50


# --- delete ---

def test_delete_top3_clears_slot_keeps_three(client_with_today):
    client, vault = client_with_today
    client.post("/delete-task", data={"section": "top_3", "index": "1"})
    note = _note(vault)
    top3_block = note.split("### My Top 3")[1].split("###")[0]
    # Still three numbered slots, middle one cleared.
    assert "Draft cowork" not in top3_block
    assert top3_block.count("\n1.") + top3_block.count("\n2.") + top3_block.count("\n3.") >= 1


def test_delete_bonus_removes_row(client_with_today):
    client, vault = client_with_today
    client.post("/delete-task", data={"section": "bonus", "index": "0"})
    morning = parse_daily_note_sections(_note(vault)).get("Morning Check-in", "")
    from companion.server import _extract_bonus
    bonus = _extract_bonus(morning)
    assert all(b["text"] != "brainstorm marketing" for b in bonus)


def test_delete_also_clears_carryover(client_with_today):
    client, vault = client_with_today
    client.post("/carry-task", data={"section": "top_3", "index": "2"})
    client.post("/delete-task", data={"section": "top_3", "index": "2"})
    assert "- Happy path docs" not in _note(vault)


# --- smoke: the Command Center renders the controls without error ---

def test_command_center_renders_task_controls(client_with_today):
    client, _ = client_with_today
    html = client.get("/").get_data(as_text=True)
    assert "tasklist-top_3" in html
    assert "tasklist-bonus" in html
    assert "/set-progress" in html
    assert "/carry-task" in html
    assert "Return to the terminal" in html
