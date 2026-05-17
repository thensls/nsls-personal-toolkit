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
    # Toggle back
    client.post("/toggle", data={"section": "top_3", "index": "0"})
    assert "1. [ ] First priority" in note.read_text()


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
