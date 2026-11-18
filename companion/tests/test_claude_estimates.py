"""Claude's progress estimates (`<!--c:NN-->`), written by the midnight sweep
when a day wasn't closed: shown light blue until the builder marks the task,
never counted as the builder's own progress, never leaked as text."""
from datetime import date

import pytest

from companion.server import (_extract_ai_suggestions, _extract_carryover_texts,
                              _extract_numbered_checkbox_list)

TODAY = date.today().isoformat()


def _client(tmp_path):
    from companion.server import create_app
    vault = tmp_path / "vault"
    (vault / "01-daily").mkdir(parents=True)
    (vault / "30-habits").mkdir(parents=True)
    app = create_app(str(vault))
    app.config["TESTING"] = True
    return app.test_client(), vault


@pytest.fixture
def setup(tmp_path):
    return _client(tmp_path)


def _items(body):
    return _extract_numbered_checkbox_list("### My Top 3\n" + body, "### My Top 3")


def _note(vault, top3, extra=""):
    path = vault / "01-daily" / f"{TODAY}.md"
    path.write_text(
        "---\nstatus: active\n---\n## Morning Check-in\n### My Top 3\n"
        + top3 + "\n### Bonus\n" + extra + "\n")
    return path


def test_estimate_is_read_and_stripped_from_the_text():
    [it] = _items("1. [ ] Alpha <!--c:50-->")
    assert it["text"] == "Alpha"
    assert it["progress"] == 0 and it["claude"] == 50


def test_estimate_sits_happily_beside_a_time_estimate():
    [it] = _items("1. [ ] Alpha <!--c:75--> <!--e:1.5-->")
    assert it["text"] == "Alpha" and it["claude"] == 75 and it["est"] == 1.5


def test_the_builders_own_mark_wins():
    [partial] = _items("1. [ ] Alpha <!--p:25--> <!--c:50-->")
    assert partial["progress"] == 25 and partial["claude"] is None
    [done] = _items("1. [x] Alpha <!--c:50-->")
    assert done["progress"] == 100 and done["claude"] is None


def test_an_invalid_estimate_is_ignored_but_still_hidden():
    [it] = _items("1. [ ] Alpha <!--c:40-->")
    assert it["text"] == "Alpha" and it["claude"] is None
    [zero] = _items("1. [ ] Alpha <!--c:0-->")
    assert zero["text"] == "Alpha" and zero["claude"] is None


def test_command_center_shows_the_estimate_light_blue_with_a_legend(setup):
    client, vault = setup
    _note(vault, "1. [ ] Alpha <!--c:50-->\n2. [ ] Bravo")
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "nsls-disc--claude" in html and 'style="--p: 50"' in html
    assert "is-claude-current" in html
    assert "Light blue is Claude's estimate" in html
    assert "c:50" not in html


def test_no_estimates_no_legend(setup):
    client, vault = setup
    _note(vault, "1. [ ] Alpha\n2. [ ] Bravo <!--p:50-->")
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "nsls-claude-legend" not in html and "nsls-disc--claude" not in html


def test_a_deleted_task_shows_no_estimate(setup):
    client, vault = setup
    _note(vault, "1. [ ] Alpha <!--c:50-->", extra="\n### Deleted\n- Alpha\n")
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "nsls-disc--claude" not in html and "nsls-claude-legend" not in html


def test_marking_progress_retires_the_estimate(setup):
    client, vault = setup
    path = _note(vault, "1. [ ] Alpha <!--c:50--> <!--e:2-->")
    r = client.post("/set-progress", data={"section": "top_3", "index": 0, "level": 50})
    assert r.status_code == 200
    line = next(l for l in path.read_text().splitlines() if "Alpha" in l)
    assert "<!--p:50-->" in line and "<!--e:2-->" in line and "c:" not in line
    assert "nsls-disc--claude" not in r.get_data(as_text=True)


def test_changing_the_time_estimate_keeps_claudes_estimate(setup):
    client, vault = setup
    path = _note(vault, "1. [ ] Alpha <!--c:50--> <!--e:2-->")
    client.post("/set-estimate", data={"section": "top_3", "index": 0, "hours": "1"})
    line = next(l for l in path.read_text().splitlines() if "Alpha" in l)
    assert "<!--c:50-->" in line and "<!--e:1-->" in line


def test_markers_never_leak_into_suggestions_or_carry_overs():
    sugg = _extract_ai_suggestions(
        "### AI Suggested: Top 3\n1. Alpha <!--c:50--> <!--e:1-->\n")
    assert sugg[0]["text"] == "Alpha" and sugg[0]["est"] == 1.0
    carried = _extract_carryover_texts("## Carrying Over\n- Bravo <!--c:25-->\n")
    assert carried == {"Bravo"}
