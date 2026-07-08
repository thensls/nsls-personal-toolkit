"""Time estimates must survive the carry-forward pipeline.

An incomplete item's <!--e:X--> marker (estimated REMAINING hours, possibly
revised during the day) rides along when the item resurfaces the next day:
carry-over extraction → suggestion rows → taking the suggestion into
My Top 3 / Bonus pre-fills the estimate field.
"""

from datetime import date, timedelta
import pytest
from companion.server import (
    create_app, _extract_ai_suggestions, _extract_carryovers, _extract_top_3,
)
from companion.parsers import parse_daily_note_sections


TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture
def client(tmp_path):
    vault = tmp_path / "vault"
    (vault / "01-daily").mkdir(parents=True)
    habits = vault / "30-habits"
    habits.mkdir(parents=True)
    (habits / "habits.md").write_text("# Daily Habits\n\n## Active\n\n- id: walk\n  name: Walk\n")
    (habits / "log.md").write_text("# Daily habit log\n")
    (vault / "01-daily" / f"{YESTERDAY}.md").write_text("""---
status: closed
---
# Daily Note

## Morning Check-in

### My Top 3
1. [ ] Prep the board update <!--p:75--> <!--e:2.5-->
2. [x] Done thing <!--e:1-->

### Bonus
1. [ ] Send Maya the onboarding doc <!--e:0.5-->
""")
    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield (app.test_client(), vault)
    finally:
        app.config["WATCHER"].stop()


def test_carryovers_carry_estimates(client):
    _, vault = client
    items = _extract_carryovers(vault, TODAY)
    by_text = {i["text"]: i for i in items}
    # incomplete Top 3 AND Bonus items carry, with their remaining estimates
    assert by_text["Prep the board update"]["est"] == 2.5
    assert by_text["Send Maya the onboarding doc"]["est"] == 0.5
    assert "Done thing" not in by_text  # checked items don't carry


def test_ai_suggestions_strip_and_carry_est_marker():
    morning = """### AI Suggested: Top 3
1. **Prep the board update** — it blocks the offsite <!--e:2.5-->
2. Plain item with no estimate
"""
    items = _extract_ai_suggestions(morning)
    assert items[0]["text"] == "Prep the board update"
    assert items[0]["est"] == 2.5
    assert "<!--" not in items[0]["text"]
    assert items[1]["est"] is None


def test_taking_suggestion_prefills_estimate(client):
    c, vault = client
    resp = c.post("/plan-action", data={"action": "pri",
                                        "text": "Prep the board update",
                                        "est": "2.5"})
    assert resp.status_code == 200
    note = (vault / "01-daily" / f"{TODAY}.md").read_text()
    morning = parse_daily_note_sections(note).get("Morning Check-in", "")
    item = next(i for i in _extract_top_3(morning) if i["text"] == "Prep the board update")
    assert item["est"] == 2.5
    assert "<!--e:2.5-->" in note


def test_taking_suggestion_without_est_writes_no_marker(client):
    c, vault = client
    c.post("/plan-action", data={"action": "bonus", "text": "Send Maya the onboarding doc"})
    note = (vault / "01-daily" / f"{TODAY}.md").read_text()
    assert "Send Maya the onboarding doc" in note


def test_plan_page_shows_carried_estimate(client):
    c, _ = client
    html = c.get("/?mode=coach-morning").get_data(as_text=True)
    assert "~2.5h left" in html
    # and the take-buttons pass the estimate along
    assert '"est": "2.5"' in html


def test_bad_carried_est_still_takes_item(client):
    c, vault = client
    resp = c.post("/plan-action", data={"action": "pri",
                                        "text": "Prep the board update",
                                        "est": "nan"})
    assert resp.status_code == 200
    note = (vault / "01-daily" / f"{TODAY}.md").read_text()
    assert "Prep the board update" in note
    assert "<!--e:nan-->" not in note
