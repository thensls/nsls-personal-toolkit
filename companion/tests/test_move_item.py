"""Drag-and-drop moves (/move-item) and the plan-action raw-index fix.

The vertical drag UI on Plan-your-day and the Command Center sends every
reorder and cross-lane move through one endpoint. These pin the rules:
a task's row (checkbox, progress, estimate) travels with it, Top 3 never
holds more than three, and suggestions dragged in lose any old disposition.
"""
from datetime import date

import pytest

from companion.parsers import parse_daily_note_sections
from companion.server import _extract_bonus, _extract_top_3, _move_task


def _lanes(md: str):
    morning = parse_daily_note_sections(md).get("Morning Check-in", "")
    return ([t["text"] for t in _extract_top_3(morning)],
            [b["text"] for b in _extract_bonus(morning)])


NOTE = (
    "## Morning Check-in\n"
    "### My Top 3\n"
    "1. [ ] Alpha <!--p:50--> <!--e:2-->\n"
    "2. [x] Bravo\n"
    "3. [ ] Charlie\n"
    "\n"
    "### Bonus\n"
    "1. [ ] Delta <!--e:0.5-->\n"
    "2. [ ] Echo\n"
)


def test_reorder_within_top3_keeps_row_markers():
    out = _move_task(NOTE, "Alpha", "top_3", 2)
    top, bonus = _lanes(out)
    assert top == ["Bravo", "Charlie", "Alpha"]
    assert bonus == ["Delta", "Echo"]
    assert "3. [ ] Alpha <!--p:50--> <!--e:2-->" in out
    assert "1. [x] Bravo" in out  # done state travels too


def test_move_bonus_into_full_top3_bumps_last_to_bonus_head():
    out = _move_task(NOTE, "Echo", "top_3", 0)
    top, bonus = _lanes(out)
    assert top == ["Echo", "Alpha", "Bravo"]
    assert bonus == ["Charlie", "Delta"]


def test_move_top3_to_bonus_leaves_blank_slot_padded():
    out = _move_task(NOTE, "Bravo", "bonus", 1)
    top, bonus = _lanes(out)
    assert top == ["Alpha", "Charlie"]
    assert bonus == ["Delta", "Bravo", "Echo"]
    assert "3. [ ]" in out  # Top 3 keeps its three slots


def test_new_task_from_pool_gets_estimate_and_clears_disposition():
    md = NOTE + "\n### Deferred\n- Foxtrot\n"
    out = _move_task(md, "Foxtrot", "bonus", None, est=1.5)
    _, bonus = _lanes(out)
    assert bonus[-1] == "Foxtrot"
    assert "[ ] Foxtrot <!--e:1.5-->" in out
    assert "### Deferred" not in out


def test_moving_a_marked_for_deletion_task_keeps_the_mark():
    md = NOTE + "\n### Deleted\n- Delta\n"
    out = _move_task(md, "Delta", "top_3", 0)
    assert "- Delta" in out.split("### Deleted", 1)[1]


def test_blank_slots_are_compacted_on_move():
    md = ("## Morning Check-in\n### My Top 3\n1. [ ]\n2. [ ] Bravo\n3. [ ]\n"
          "### Bonus\n1. [ ] Delta\n")
    out = _move_task(md, "Delta", "top_3", None)
    top, bonus = _lanes(out)
    assert top == ["Bravo", "Delta"]
    assert bonus == []
    assert "1. [ ] Bravo\n2. [ ] Delta\n3. [ ]\n" in out


def test_missing_headings_are_created_inside_morning_checkin():
    md = "## Morning Check-in\n- Energy: high\n\n## End of Day\n"
    out = _move_task(md, "Golf", "top_3", None)
    top, _ = _lanes(out)
    assert top == ["Golf"]
    assert out.index("### My Top 3") < out.index("## End of Day")


# --- route ---

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


def test_move_item_route_plan_view_returns_plan_partial(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(NOTE)
    resp = client.post("/move-item", data={"text": "Echo", "to": "top_3", "position": "1"})
    assert resp.status_code == 200
    assert 'id="plan-your-day"' in resp.get_data(as_text=True)
    top, bonus = _lanes(_note(vault).read_text())
    assert top == ["Alpha", "Echo", "Bravo"]
    assert bonus == ["Charlie", "Delta"]


def test_move_item_route_command_view_returns_task_table(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(NOTE)
    html = client.post("/move-item", data={
        "text": "Alpha", "to": "bonus", "position": "0", "view": "command",
    }).get_data(as_text=True)
    assert 'id="task-table"' in html and "tasklist-bonus" in html
    _, bonus = _lanes(_note(vault).read_text())
    assert bonus[0] == "Alpha"


def test_move_item_route_rejects_bad_input(client_with_today):
    client, vault = client_with_today
    _note(vault).write_text(NOTE)
    bad = [
        {"text": "Alpha", "to": "deferred"},
        {"text": "", "to": "top_3"},
        {"text": "Alpha", "to": "top_3", "position": "-1"},
        {"text": "Alpha", "to": "top_3", "position": "x"},
        {"text": "Alpha", "to": "top_3", "view": "week"},
        {"text": "a\nb", "to": "top_3"},
    ]
    for data in bad:
        assert client.post("/move-item", data=data).status_code == 400, data
    assert _note(vault).read_text() == NOTE


# --- plan-action writes by raw row, not compacted position ---

def test_plan_action_vacates_the_right_row_when_a_blank_slot_sits_above(client_with_today):
    """Top 3 = [blank, Bravo, Charlie]. Sending Charlie to Bonus must clear
    Charlie's row; the compacted position (1) points at Bravo's row."""
    client, vault = client_with_today
    _note(vault).write_text(
        "## Morning Check-in\n### My Top 3\n1. [ ]\n2. [ ] Bravo\n3. [ ] Charlie\n"
        "### Bonus\n"
    )
    client.post("/plan-action", data={"text": "Charlie", "action": "bonus"})
    top, bonus = _lanes(_note(vault).read_text())
    assert top == ["Bravo"]
    assert bonus == ["Charlie"]


def test_only_the_dragged_row_moves_when_a_title_repeats():
    """Same title in both lanes: moving the Bonus copy must not touch the
    Top 3 copy's state (Codex review, 2026-10-26)."""
    md = ("## Morning Check-in\n### My Top 3\n1. [ ] Alpha <!--p:75-->\n2. [ ]\n3. [ ]\n"
          "### Bonus\n1. [ ] Alpha <!--e:3-->\n2. [ ] Echo\n")
    out = _move_task(md, "Alpha", "bonus", 1, from_lane="bonus")
    assert "1. [ ] Alpha <!--p:75-->" in out          # Top 3 copy untouched
    assert "1. [ ] Echo\n2. [ ] Alpha <!--e:3-->" in out
    out = _move_task(md, "Alpha", "bonus", 0, from_lane="top_3")
    top, bonus = _lanes(out)
    assert top == [] and bonus == ["Alpha", "Alpha", "Echo"]
    assert "1. [ ] Alpha <!--p:75-->\n2. [ ] Alpha <!--e:3-->" in out


def test_dash_row_in_a_lane_survives_and_raw_writes_stay_aligned():
    """A hand-written dash row stays; after the move, the raw index the page
    re-renders for each task still writes to that task."""
    from companion.server import _extract_numbered_checkbox_list, _set_nth_progress
    md = ("## Morning Check-in\n### My Top 3\n1. [ ] Alpha\n- a note to self\n"
          "2. [ ] Bravo\n3. [ ] Charlie\n### Bonus\n")
    out = _move_task(md, "Charlie", "top_3", 0, from_lane="top_3")
    assert "- a note to self" in out
    morning = parse_daily_note_sections(out)["Morning Check-in"]
    items = _extract_numbered_checkbox_list(morning, "### My Top 3")
    assert [i["text"] for i in items] == ["Charlie", "Alpha", "Bravo"]
    bravo = next(i for i in items if i["text"] == "Bravo")
    out2 = _set_nth_progress(out, "### My Top 3", bravo["raw_index"], 50)
    assert "[ ] Bravo <!--p:50-->" in out2
    assert "Charlie <!--p" not in out2 and "Alpha <!--p" not in out2


def test_disposition_cleanup_stays_inside_morning_checkin():
    md = (NOTE + "\n### Deferred\n- Foxtrot\n"
          "\n## End of Day\n### Deferred\n- Foxtrot\n")
    out = _move_task(md, "Foxtrot", "bonus")
    morning, end_of_day = out.split("## End of Day", 1)
    assert "### Deferred" not in morning
    assert "### Deferred\n- Foxtrot" in end_of_day
