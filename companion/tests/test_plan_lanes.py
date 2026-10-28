"""Plan-your-day lanes: partials that render the draggable Bonus lane."""
from datetime import date

import pytest


@pytest.fixture
def client_with_today(tmp_path):
    from companion.server import create_app
    vault = tmp_path / "vault"
    (vault / "01-daily").mkdir(parents=True)
    (vault / "30-habits").mkdir(parents=True)
    app = create_app(str(vault))
    app.config["TESTING"] = True
    return app.test_client(), vault


def _note(vault):
    return vault / "01-daily" / f"{date.today().isoformat()}.md"


def test_bonus_routes_still_return_the_bonus_lane_alone(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text("## Morning Check-in\n### My Top 3\n1. [ ]\n2. [ ]\n3. [ ]\n"
                            "### Bonus\n1. [ ] Delta\n2. [ ] Echo\n")
    for route, data in (("/set-bonus", {"index": "1", "text": "Echo 2", "add": "1"}),
                        ("/delete-bonus", {"index": "0"})):
        html = client.post(route, data=data).get_data(as_text=True)
        assert html.lstrip().startswith('<div id="bonus-list"'), route
        assert 'data-drag-item' in html and 'data-lane="bonus"' in html, route


def test_eleventh_bonus_task_can_be_renamed(client_with_today):
    """The drag UI adds Bonus tasks freely, so rename must reach past ten
    (Macroscope, PR #93)."""
    client, vault = client_with_today
    rows = "".join(f"{n}. [ ] Task {n}\n" for n in range(1, 12))
    _note(vault).write_text("## Morning Check-in\n### My Top 3\n1. [ ]\n2. [ ]\n3. [ ]\n"
                            "### Bonus\n" + rows)
    resp = client.post("/set-bonus", data={"index": "10", "text": "Task eleven"})
    assert resp.status_code == 200
    assert "11. [ ] Task eleven" in _note(vault).read_text()


def test_typed_task_set_aside_stays_visible_with_its_undo(client_with_today):
    """Defer / Done / Delete on a typed (non-suggestion) task must leave a
    faded card whose active button undoes it (Macroscope, PR #93)."""
    client, vault = client_with_today
    _note(vault).write_text("## Morning Check-in\n### My Top 3\n1. [ ] Typed task\n2. [ ]\n3. [ ]\n"
                            "### Bonus\n")
    html = client.post("/plan-action", data={"text": "Typed task", "action": "defer"}).get_data(as_text=True)
    assert 'data-lane="pool" data-text="Typed task"' in html
    assert "is-set-aside" in html
    assert 'title="Use Top 3 or Bonus to bring it back"' in html  # lit Defer locked
    client.post("/move-item", data={"text": "Typed task", "to": "bonus", "from": "pool"})
    md = _note(vault).read_text()
    assert "### Deferred" not in md and "1. [ ] Typed task" in md.split("### Bonus", 1)[1]

