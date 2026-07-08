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


def test_day_tab_renders_checked_state(tmp_path):
    """Top 3 items marked `[x]` in the file must render as checked; `[ ]` not."""
    from datetime import date
    vault = tmp_path / "vault"
    daily = vault / "01-daily"
    daily.mkdir(parents=True)
    habits = vault / "30-habits"
    habits.mkdir(parents=True)
    today = date.today().isoformat()
    (daily / f"{today}.md").write_text(
        "## Morning Check-in\n### My Top 3\n"
        "1. [x] Done item\n2. [ ] Pending item\n"
    )
    (habits / "habits.md").write_text("# Daily Habits\n\n## Active\n")
    (habits / "log.md").write_text("# Log\n")

    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        client = app.test_client()
        resp = client.get("/")
        assert resp.status_code == 200
        page = resp.data.decode()
        assert "Done item" in page
        assert "Pending item" in page
        # The checked item has the struck-through marker (.is-done → CSS line-through).
        assert "is-done" in page
        # The pending item's text span is NOT marked done.
        pending_idx = page.index("Pending item")
        pending_span = page[:pending_idx][page[:pending_idx].rfind("<span"):]
        assert "is-done" not in pending_span
    finally:
        app.config["WATCHER"].stop()
