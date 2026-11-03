"""Command Center layout: close button placement and the Add an item panel."""
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


ACTIVE = ("---\nstatus: active\n---\n## Morning Check-in\n"
          "### My Top 3\n1. [ ] Alpha\n2. [ ] Bravo\n3. [ ] Charlie\n"
          "### Bonus\n1. [ ] Delta\n")


def test_close_button_sits_at_the_bottom_only_once_locked_in(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE)
    html = client.get("/?mode=command").get_data(as_text=True)
    assert html.count("I'm done — close my day") == 1
    # ...and it comes after the task lanes, not before them
    assert html.index("I'm done — close my day") > html.index('id="task-table"')


def test_unlocked_plan_still_warns_at_the_top(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE.replace("status: active", "status: planning"))
    html = client.get("/?mode=command").get_data(as_text=True)
    assert html.index("Your plan isn't locked in yet") < html.index('id="task-table"')


def test_add_item_panel_confirms_and_names_the_task_it_bumped(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE)
    html = client.post("/move-item", data={
        "text": "Echo", "to": "top_3", "view": "command", "add": "1",
    }).get_data(as_text=True)
    assert 'id="task-table"' in html
    assert 'id="add-item-status"' in html and 'hx-swap-oob="true"' in html
    assert "Added “Echo” to Top 3." in html
    assert "Made room: “Charlie” → Bonus." in html


def test_add_item_to_bonus_bumps_nothing(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE)
    html = client.post("/move-item", data={
        "text": "Echo", "to": "bonus", "view": "command", "add": "1",
    }).get_data(as_text=True)
    assert "Added “Echo” to Bonus." in html and "Made room" not in html


def test_plain_drag_returns_no_add_confirmation(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE)
    html = client.post("/move-item", data={
        "text": "Delta", "to": "top_3", "position": "0", "view": "command",
    }).get_data(as_text=True)
    assert "add-item-status" not in html


def test_command_center_has_column_headings_and_add_panel(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE)
    html = client.get("/?mode=command").get_data(as_text=True)
    for label in ("Task", "Estimated time remaining", "Progress", "Add an item",
                  "What needs to be done?", "Today · Top 3", "Today · Bonus"):
        assert label in html, label


def test_adding_a_title_already_on_the_list_says_moved(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE)
    html = client.post("/move-item", data={
        "text": "Delta", "to": "top_3", "view": "command", "add": "1",
    }).get_data(as_text=True)
    assert "Moved “Delta” to Top 3." in html and "Added" not in html
    assert _note(vault).read_text().count("Delta") == 1



def test_starting_energy_sits_beside_the_day_not_in_its_own_card(client_with_today):
    import re
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE)
    html = client.get("/?mode=command").get_data(as_text=True)
    head = html.index('class="nsls-day-head"')
    assert head < html.index('id="energy-morning"') < html.index('id="task-table"')
    assert re.search(r'nsls-card--row">\s*<div id="energy-morning"', html) is None
    # The end-of-day energy keeps its own card at the bottom.
    assert re.search(r'nsls-card--row">\s*<div id="energy-evening"', html)


def test_add_item_defaults_to_bonus_when_top_3_is_full(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE)
    html = client.get("/?mode=command").get_data(as_text=True)
    assert '<option value="bonus" selected>' in html
    assert '<option value="top_3" selected>' not in html


def test_add_item_defaults_to_top_3_while_it_has_room(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE.replace("3. [ ] Charlie\n", ""))
    html = client.get("/?mode=command").get_data(as_text=True)
    assert '<option value="top_3" selected>' in html
    assert '<option value="bonus" selected>' not in html


def test_lanes_report_the_top_3_count_after_a_move(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(ACTIVE)
    html = client.post("/move-item", data={
        "text": "Charlie", "to": "bonus", "position": "0", "view": "command",
    }).get_data(as_text=True)
    assert 'data-top3-count="2"' in html
