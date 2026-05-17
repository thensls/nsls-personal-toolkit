import pytest
from companion.server import create_app


@pytest.fixture
def client_with_today(tmp_path):
    vault = tmp_path / "vault"
    daily = vault / "01-daily"
    daily.mkdir(parents=True)
    habits = vault / "30-habits"
    habits.mkdir(parents=True)

    from datetime import date
    today = date.today().isoformat()
    (daily / f"{today}.md").write_text("""# Daily Note

## Morning Check-in

### My Top 3
1. Finish toolkit spec
2. Q3 LOP draft
3. Reply to vendor

### Bonus
1. Board email
2. Review Maya's PR

### Habits
- [ ] **Walk**
- [x] **Read 15m**
""")
    (habits / "habits.md").write_text("""# Daily Habits

## Active

- id: walk
  name: Walk
  emoji: 🚶
  target: 30min
  frequency: daily

- id: read
  name: Read 15m
  emoji: 📖
  target: 15min
  frequency: daily
""")
    (habits / "log.md").write_text("# Log\n")

    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield app.test_client()
    finally:
        app.config["WATCHER"].stop()


def test_day_tab_renders_top_3(client_with_today):
    resp = client_with_today.get("/")
    assert b"Finish toolkit spec" in resp.data
    assert b"Q3 LOP draft" in resp.data


def test_day_tab_renders_bonus(client_with_today):
    resp = client_with_today.get("/")
    assert b"Board email" in resp.data


def test_day_tab_renders_habits(client_with_today):
    resp = client_with_today.get("/")
    assert b"Walk" in resp.data
    assert b"Read 15m" in resp.data
