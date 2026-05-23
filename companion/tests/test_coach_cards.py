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

### Bonus
1. Board email

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


def test_morning_coach_renders_plan_and_done(client_with_today):
    """Morning coach shows Plan-your-day (Top 3 + Bonus + suggestions) and
    a Done button to transition to Command Center. No multi-step wizard —
    focus blocks and vitality are handled in chat after the visual handoff."""
    client, _ = client_with_today
    resp = client.get("/?mode=coach-morning")
    assert resp.status_code == 200
    for label in (b"Plan your day", b"Your Top 3",
                  b"Bonus list", b"Command Center"):
        assert label in resp.data, f"missing: {label}"
    # No greeting screen, no multi-step UI, no placeholder features.
    assert b"Good morning" not in resp.data
    assert b"Focus blocks" not in resp.data
    assert b"Vitality" not in resp.data
    assert b"Step" not in resp.data


def test_evening_coach_renders_4_steps(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text("## Morning Check-in\n### My Top 3\n\n## Insight Reflection\n\n")
    resp = client.get("/?mode=coach-evening")
    assert resp.status_code == 200
    for label in (b"Today's stats", b"Insight Reflection",
                  b"Gratitude", b"Done"):
        assert label in resp.data, f"missing: {label}"


def test_state_detection_picks_evening_results_when_insight_filled(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n### My Top 3\n1. [x] Done\n"
        "## Insight Reflection\n\nI noticed something today.\n"
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"I noticed something today" in resp.data


def test_lock_in_morning_writes_nothing_but_returns_command_view(client_with_today):
    client, _ = client_with_today
    resp = client.post("/lock-in", data={"phase": "morning"})
    assert resp.status_code == 200
    # Returns the Command Center HTML for HTMX to swap in
    assert b"Top 3" in resp.data


def test_lock_in_evening_returns_results_view(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n### My Top 3\n1. [x] Done\n"
        "## Insight Reflection\n\nReflected.\n"
        "## Gratitude\n\nGrateful.\n"
    )
    resp = client.post("/lock-in", data={"phase": "evening"})
    assert resp.status_code == 200
    assert b"Day closed" in resp.data
    assert b"Reflected" in resp.data
