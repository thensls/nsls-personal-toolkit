"""The centered progress card while Claude closes the day, and holding
"Open tomorrow" until tomorrow's suggestions are written."""
from datetime import date, datetime, timezone

import pytest

TODAY = date.today().isoformat()


@pytest.fixture
def setup(tmp_path):
    from companion.server import create_app
    vault = tmp_path / "vault"
    (vault / "01-daily").mkdir(parents=True)
    (vault / "30-habits").mkdir(parents=True)
    app = create_app(str(vault))
    app.config["TESTING"] = True
    return app.test_client(), vault


def _note(vault, fm):
    (vault / "01-daily" / f"{TODAY}.md").write_text(
        f"---\n{fm}---\n## Morning Check-in\n### My Top 3\n1. [ ] Alpha\n")


def _clicked(step=""):
    now = datetime.now(timezone.utc).isoformat()
    extra = f"close_step: {step}\n" if step else ""
    return f'status: active\nclose_ready: 1\nclose_ready_at: "{now}"\n{extra}'


def test_no_close_no_card(setup):
    client, vault = setup
    _note(vault, "status: active\n")
    html = client.get("/?mode=command").get_data(as_text=True)
    assert 'id="closing-overlay"' in html and "nsls-closing-card" not in html


def test_a_running_close_shows_the_card_with_its_stage(setup):
    client, vault = setup
    _note(vault, _clicked("writing"))
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "nsls-closing-card" in html and "Claude is closing your day" in html
    assert "Writing your work log" in html and "width: 60%" in html


def test_before_any_stage_the_bar_is_indeterminate(setup):
    client, vault = setup
    _note(vault, _clicked())
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "is-indeterminate" in html and "Starting…" in html


def test_the_click_returns_the_card_when_claude_is_listening(setup):
    client, vault = setup
    _note(vault, "status: active\n")
    client.post("/listener-heartbeat")
    html = client.post("/close-ready").get_data(as_text=True)
    assert 'hx-swap-oob="true"' in html and "nsls-closing-card" in html


def test_no_card_when_nobody_is_listening(setup):
    client, vault = setup
    _note(vault, "status: active\n")
    html = client.post("/close-ready").get_data(as_text=True)
    assert "isn't listening" in html and "nsls-closing-card" not in html


def test_open_tomorrow_waits_while_tomorrow_is_being_set_up(setup):
    client, vault = setup
    _note(vault, "status: closed\nclose_step: seeding\n")
    html = client.get("/").get_data(as_text=True)
    assert html.count("Setting up tomorrow…") == 2 and "Open tomorrow →" not in html
    _note(vault, "status: closed\n")
    html = client.get("/").get_data(as_text=True)
    assert html.count("Open tomorrow →") == 2
