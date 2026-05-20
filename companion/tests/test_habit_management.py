import pytest
from datetime import date
from companion.server import create_app


@pytest.fixture
def client_with_today(tmp_path):
    vault = tmp_path / "vault"
    (vault / "01-daily").mkdir(parents=True)
    habits = vault / "30-habits"
    habits.mkdir(parents=True)

    today = date.today().isoformat()
    (vault / "01-daily" / f"{today}.md").write_text("# Daily\n")
    (habits / "habits.md").write_text("""# Daily Habits

## Active

- id: walk
  name: Walk
  emoji: 🚶
  target: 30min
  frequency: daily

## Archived

(none yet)
""")
    (habits / "log.md").write_text("# Log\n")

    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield (app.test_client(), vault)
    finally:
        app.config["WATCHER"].stop()


def test_add_habit_writes_to_habits_md(client_with_today):
    client, vault = client_with_today
    resp = client.post("/habit", data={
        "id": "meditate", "name": "Meditate", "emoji": "🧘",
        "target": "10min", "frequency": "daily"
    })
    assert resp.status_code in (200, 204)
    habits_md = (vault / "30-habits" / "habits.md").read_text()
    assert "id: meditate" in habits_md
    assert "name: Meditate" in habits_md


def test_archive_habit_moves_to_archived_section(client_with_today):
    client, vault = client_with_today
    resp = client.post("/habit/archive", data={"habit_id": "walk"})
    assert resp.status_code in (200, 204)
    habits_md = (vault / "30-habits" / "habits.md").read_text()
    # walk should now appear under ## Archived, not ## Active
    archived_idx = habits_md.find("## Archived")
    walk_idx = habits_md.find("id: walk")
    assert walk_idx > archived_idx


def test_add_habit_dedupes_id_when_name_collides(client_with_today):
    """The form now collects only ``name``; id is derived (kebab-case).
    Adding a habit named "Walk" when a habit with id ``walk`` already exists
    should ACCEPT the new habit with a deduped id like ``walk-2`` — not 400.
    Adding "Walking" stays unique."""
    client, vault = client_with_today
    # `walk` already exists in the fixture. Adding name "Walking" -> id walking, unique.
    resp = client.post("/habit", data={"name": "Walking"})
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.data!r}"
    md = (vault / "30-habits" / "habits.md").read_text()
    assert "id: walking" in md
    assert "id: walk" in md  # original preserved
    # Adding "Walk" again -> id collides with the original; gets -2 suffix.
    resp2 = client.post("/habit", data={"name": "Walk"})
    assert resp2.status_code == 200
    md2 = (vault / "30-habits" / "habits.md").read_text()
    assert "id: walk-2" in md2
