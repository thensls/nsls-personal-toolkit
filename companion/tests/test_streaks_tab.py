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
        yield (app.test_client(), vault)
    finally:
        app.config["WATCHER"].stop()


def test_streaks_tab_renders_habits(client_with_today):
    client, _ = client_with_today
    resp = client.get("/streaks")
    assert resp.status_code == 200
    assert b"Walk" in resp.data
    assert b"Read 15m" in resp.data


def test_streaks_tab_shows_heatmap_cells(client_with_today):
    client, _ = client_with_today
    resp = client.get("/streaks")
    # 30-day heatmap = 30 cells per habit, 2 habits => 60 cells
    assert resp.data.count(b'class="hm-cell') >= 60
