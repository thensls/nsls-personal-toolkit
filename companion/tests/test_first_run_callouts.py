"""First-run tips: which screen gets which tips, and dismissals that stick."""
import json
import re
from datetime import date

import pytest


def _vault(tmp_path):
    vault = tmp_path / "vault"
    (vault / "01-daily").mkdir(parents=True)
    (vault / "30-habits").mkdir(parents=True)
    return vault


def _client(vault):
    from companion.server import create_app
    app = create_app(str(vault))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def vault(tmp_path):
    return _vault(tmp_path)


def _note(vault, body):
    (vault / "01-daily" / f"{date.today().isoformat()}.md").write_text(body)


ACTIVE = ("---\nstatus: active\n---\n## Morning Check-in\n"
          "### My Top 3\n1. [ ] Alpha\n2. [ ] Bravo\n"
          "### Bonus\n1. [ ] Delta\n")
PLANNING = ACTIVE.replace("status: active", "status: planning")


def _marker(html):
    m = re.search(r'<div id="nsls-callouts" hidden data-screen="([a-z]*)" data-dismissed=\'([^\']*)\'', html)
    assert m, "no tips marker on the page"
    return m.group(1), json.loads(m.group(2))


def test_plan_screen_carries_its_tip_marker_and_targets(vault):
    _note(vault, PLANNING)
    html = _client(vault).get("/?mode=coach-morning").get_data(as_text=True)
    assert _marker(html) == ("plan", [])
    assert 'data-callout="plan-energy"' in html
    assert 'data-callout="plan-lockin"' in html
    assert 'id="plan-your-day"' in html and "nsls-slot" in html


def test_command_center_carries_its_tip_marker_and_targets(vault):
    _note(vault, ACTIVE)
    html = _client(vault).get("/?mode=command").get_data(as_text=True)
    assert _marker(html) == ("command", [])
    assert 'data-callout="cc-add"' in html
    assert 'data-callout="cc-close"' in html
    assert 'id="task-table"' in html and "nsls-grip" in html and "nsls-seg" in html


def test_closed_day_shows_no_tips(vault):
    _note(vault, ACTIVE.replace("status: active", "status: closed"))
    html = _client(vault).get("/?mode=results").get_data(as_text=True)
    assert 'id="nsls-callouts"' not in html


def test_every_page_loads_the_tips_script(vault):
    _note(vault, ACTIVE)
    html = _client(vault).get("/").get_data(as_text=True)
    assert '<script defer src="/static/callouts.js"></script>' in html


def test_dismissal_is_saved_and_survives_a_restart(vault):
    _note(vault, ACTIVE)
    client = _client(vault)
    resp = client.post("/callouts/dismiss", data={"id": ["cc-drag", "cc-add"]})
    assert resp.status_code == 204
    saved = json.loads((vault / ".toolkit-companion" / "state.json").read_text())
    assert saved["callouts_dismissed"] == ["cc-drag", "cc-add"]
    # A fresh server on the same vault (a restart, or another browser) agrees.
    html = _client(vault).get("/?mode=command").get_data(as_text=True)
    assert _marker(html) == ("command", ["cc-drag", "cc-add"])


def test_dismissing_twice_keeps_one_copy(vault):
    client = _client(vault)
    client.post("/callouts/dismiss", data={"id": "plan-energy"})
    client.post("/callouts/dismiss", data={"id": ["plan-energy", "plan-add"]})
    saved = json.loads((vault / ".toolkit-companion" / "state.json").read_text())
    assert saved["callouts_dismissed"] == ["plan-energy", "plan-add"]


@pytest.mark.parametrize("data", [{}, {"id": ""}, {"id": "Bad Id"}, {"id": "x" * 41},
                                  {"id": ["a"] * 21}, {"id": "<script>"}])
def test_bad_tip_ids_are_refused(vault, data):
    resp = _client(vault).post("/callouts/dismiss", data=data)
    assert resp.status_code == 400
    assert not (vault / ".toolkit-companion" / "state.json").exists()


def test_cross_site_dismiss_is_refused(vault):
    resp = _client(vault).post("/callouts/dismiss", data={"id": "cc-add"},
                               headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403


def test_unreadable_state_reads_as_nothing_dismissed_and_is_repaired(vault):
    _note(vault, ACTIVE)
    state = vault / ".toolkit-companion" / "state.json"
    state.parent.mkdir()
    state.write_text("{not json")
    client = _client(vault)
    assert _marker(client.get("/?mode=command").get_data(as_text=True)) == ("command", [])
    assert client.post("/callouts/dismiss", data={"id": "cc-close"}).status_code == 204
    assert json.loads(state.read_text())["callouts_dismissed"] == ["cc-close"]


def test_state_file_that_is_not_utf8_is_set_aside_not_fatal(vault):
    _note(vault, ACTIVE)
    state = vault / ".toolkit-companion" / "state.json"
    state.parent.mkdir()
    state.write_bytes(b'{"callouts_dismissed": ["cc-add"]}\xff\xfe')
    client = _client(vault)
    assert _marker(client.get("/?mode=command").get_data(as_text=True)) == ("command", [])
    assert client.post("/callouts/dismiss", data={"id": "cc-close"}).status_code == 204
    assert json.loads(state.read_text())["callouts_dismissed"] == ["cc-close"]
    # The unreadable bytes are kept beside it, not thrown away.
    assert (state.parent / "state.json.unreadable").read_bytes().endswith(b"\xff\xfe")


def test_absurdly_nested_state_file_never_breaks_a_page(vault):
    _note(vault, ACTIVE)
    state = vault / ".toolkit-companion" / "state.json"
    state.parent.mkdir()
    state.write_text("[" * 200000)
    client = _client(vault)
    resp = client.get("/?mode=command")
    assert resp.status_code == 200
    assert _marker(resp.get_data(as_text=True)) == ("command", [])
    assert client.post("/callouts/dismiss", data={"id": "cc-add"}).status_code == 204
    assert json.loads(state.read_text())["callouts_dismissed"] == ["cc-add"]


def test_state_file_keeps_other_keys(vault):
    state = vault / ".toolkit-companion" / "state.json"
    state.parent.mkdir()
    state.write_text(json.dumps({"something_else": 1, "callouts_dismissed": ["cc-add", 7, "Bad"]}))
    _client(vault).post("/callouts/dismiss", data={"id": "cc-close"})
    saved = json.loads(state.read_text())
    assert saved == {"something_else": 1, "callouts_dismissed": ["cc-add", "cc-close"]}
