from datetime import date
import pytest
from companion.server import create_app


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
1. Finish toolkit spec
2. Q3 LOP draft
3. Reply to vendor

### Habits
- [ ] **Walk**
""")
    (habits / "habits.md").write_text("""# Daily Habits

## Active

- id: walk
  name: Walk
  emoji: 🚶
  target: 30min
  frequency: daily
""")
    (habits / "log.md").write_text("# Daily habit log\n")

    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield (app.test_client(), vault)
    finally:
        app.config["WATCHER"].stop()


def test_tick_habit_writes_to_log(client_with_today):
    client, vault = client_with_today
    resp = client.post("/tick", data={"habit_id": "walk", "percent": "1.0"})
    assert resp.status_code == 200
    log = (vault / "30-habits" / "log.md").read_text()
    today = date.today().isoformat()
    assert today in log
    assert "walk:1.0" in log


def test_tick_rejects_bad_habit_id(client_with_today):
    client, _ = client_with_today
    resp = client.post("/tick", data={"habit_id": "../etc", "percent": "1.0"})
    assert resp.status_code == 400


def test_toggle_top_3_checks_then_unchecks(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    # Seed a note with checkbox items in Top 3
    note.write_text(
        "## Morning Check-in\n### My Top 3\n"
        "1. [ ] First priority\n2. [ ] Second\n3. [ ] Third\n"
    )
    resp = client.post("/toggle", data={"section": "top_3", "index": "0"})
    assert resp.status_code == 204
    assert "1. [x] First priority" in note.read_text()
    # The rendered HTML must reflect the toggled (checked) state.
    page = client.get("/").data.decode()
    first_idx = page.index("First priority")
    # The <input type="checkbox"> for this item appears before its label text.
    preceding = page[:first_idx]
    last_input_open = preceding.rfind("<input")
    assert last_input_open != -1
    last_input = preceding[last_input_open:]
    assert "checked" in last_input
    # Toggle back
    client.post("/toggle", data={"section": "top_3", "index": "0"})
    assert "1. [ ] First priority" in note.read_text()
    page = client.get("/").data.decode()
    first_idx = page.index("First priority")
    preceding = page[:first_idx]
    last_input_open = preceding.rfind("<input")
    last_input = preceding[last_input_open:]
    assert "checked" not in last_input


def test_toggle_injects_checkbox_when_missing(client_with_today):
    """Fresh open-day notes seed Top 3 without checkboxes (legacy seed format).
    The toggle should still work — inject [x] on the first click."""
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    # Note: no [ ] markers on the Top 3 items
    note.write_text(
        "## Morning Check-in\n### My Top 3\n"
        "1. Markerless priority\n2. Another\n3. Third\n"
    )
    resp = client.post("/toggle", data={"section": "top_3", "index": "0"})
    assert resp.status_code == 204
    body = note.read_text()
    # First item now has [x] injected after the period
    assert "1. [x] Markerless priority" in body
    # Other items unchanged
    assert "2. Another" in body


def test_toggle_rejects_unknown_section(client_with_today):
    client, _ = client_with_today
    resp = client.post("/toggle", data={"section": "../etc", "index": "0"})
    assert resp.status_code == 400


def test_save_writes_insight_reflection(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text("## Insight Reflection\n\n(empty)\n\n## Gratitude\n\n")
    resp = client.post("/save", data={
        "section": "Insight Reflection",
        "content": "Today I noticed I rush through morning ritual.",
    })
    assert resp.status_code == 204
    body = note.read_text()
    assert "Today I noticed" in body
    assert "## Gratitude" in body  # adjacent section preserved


def test_save_rejects_disallowed_section(client_with_today):
    client, _ = client_with_today
    resp = client.post("/save", data={"section": "Plan", "content": "x"})
    assert resp.status_code == 400


def test_set_top_3_creates_note_on_empty_vault(client_with_today):
    """First /set-top-3 call against a vault with no daily note creates the
    scaffold and writes the user's text. Response is the re-rendered
    plan_your_day partial (200) so the input indices stay in sync."""
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.unlink(missing_ok=True)  # ensure no note exists
    resp = client.post("/set-top-3", data={"index": "0", "text": "Ship companion v1.1"})
    assert resp.status_code == 200
    assert b"plan-your-day" in resp.data
    assert note.exists()
    body = note.read_text()
    assert "### My Top 3" in body
    assert "1. [ ] Ship companion v1.1" in body


def test_set_top_3_updates_existing_item_preserves_checkbox(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n### My Top 3\n"
        "1. [x] Old text\n2. [ ] Second\n3. [ ] Third\n"
    )
    resp = client.post("/set-top-3", data={"index": "0", "text": "New text"})
    assert resp.status_code == 200  # rerendered partial, not 204
    body = note.read_text()
    # Checked state preserved; only text replaced
    assert "1. [x] New text" in body
    assert "2. [ ] Second" in body


def test_set_bonus_updates_nth_item(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n### Bonus\n"
        "1. [ ] First bonus\n2. [ ] Second\n"
    )
    resp = client.post("/set-bonus", data={"index": "1", "text": "Updated second"})
    assert resp.status_code == 200  # rerendered partial, not 204
    body = note.read_text()
    assert "2. [ ] Updated second" in body
    assert "1. [ ] First bonus" in body


def test_set_bonus_grows_with_each_save(client_with_today):
    """The bonus list should accept multiple items. Regression for the bug
    where the input's hx-vals index stayed stale and every save overwrote
    item 0 — user could only ever add one bonus."""
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.unlink(missing_ok=True)
    # First save creates the scaffold + writes index 0
    client.post("/set-bonus", data={"index": "0", "text": "First bonus"})
    # Second save (index 1 from the freshly-rerendered partial) appends.
    client.post("/set-bonus", data={"index": "1", "text": "Second bonus"})
    # Third save (index 2) appends again.
    client.post("/set-bonus", data={"index": "2", "text": "Third bonus"})
    body = note.read_text()
    assert "1. [ ] First bonus" in body
    assert "2. [ ] Second bonus" in body
    assert "3. [ ] Third bonus" in body


def test_set_top_3_rejects_newline_in_text(client_with_today):
    client, _ = client_with_today
    resp = client.post("/set-top-3", data={"index": "0", "text": "line1\n## Hijacked"})
    assert resp.status_code == 400


def test_set_top_3_rejects_out_of_bounds_index(client_with_today):
    client, _ = client_with_today
    resp = client.post("/set-top-3", data={"index": "99", "text": "x"})
    assert resp.status_code == 400
