import pytest
from companion.server import create_app


@pytest.fixture
def client(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "01-daily").mkdir()
    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield app.test_client()
    finally:
        w = app.config.get("WATCHER")
        if w is not None:
            w.stop()


def test_root_renders_day_tab(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Day" in resp.data
    assert b"Week" in resp.data
    assert b"Streaks" in resp.data


def test_root_handles_missing_daily_note(client):
    """With no daily note, state detection picks coach-morning."""
    resp = client.get("/")
    assert resp.status_code == 200
    # State detection routes to the morning Coach Card when no Top 3 exists.
    assert b"Plan your day" in resp.data
    assert b"Command Center" in resp.data
