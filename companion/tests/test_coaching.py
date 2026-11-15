"""Claude's coaching in the companion: read from ## Coaching, collapsible on the
working screens, open on the closed day with Open tomorrow."""
from datetime import date, datetime, timedelta, timezone

import pytest

from companion.parsers import parse_coaching


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


TODAY = date.today().isoformat()
COACHING = ("## Coaching\n<!-- from: last night's close -->\n"
            "- Protect the morning for the board update.\n"
            "- You closed three days running: keep it going.\n\n"
            "One more thought as a paragraph.\n")


def _note(vault, status, extra=""):
    (vault / "01-daily" / f"{TODAY}.md").write_text(
        f"---\nstatus: {status}\n{extra}---\n## Morning Check-in\n"
        "### My Top 3\n1. [ ] Alpha\n2. [ ] Bravo\n\n" + COACHING)


def test_parse_coaching_states():
    assert parse_coaching(None)["state"] == "none"
    assert parse_coaching("<!-- coaching: writing -->")["state"] == "writing"
    assert parse_coaching("")["state"] == "writing"
    c = parse_coaching(COACHING.split("\n", 1)[1])
    assert c["state"] == "ready"
    assert c["label"] == "last night's close"
    assert c["blocks"] == [
        {"type": "list", "items": ["Protect the morning for the board update.",
                                   "You closed three days running: keep it going."]},
        {"type": "p", "text": "One more thought as a paragraph."},
    ]


def test_finished_coaching_replaces_the_writing_marker():
    c = parse_coaching("<!-- coaching: writing -->\n- Done now.")
    assert c["state"] == "ready" and c["blocks"][0]["items"] == ["Done now."]


def test_plan_screen_shows_coaching_collapsed(setup):
    client, vault = setup
    _note(vault, "planning")
    html = client.get("/?mode=coach-morning").get_data(as_text=True)
    assert 'class="nsls-coaching"' in html and "<details class=\"nsls-coaching\" open" not in html
    assert "Protect the morning for the board update." in html
    assert "last night&#39;s close" in html


def test_command_center_shows_coaching_collapsed(setup):
    client, vault = setup
    _note(vault, "active")
    html = client.get("/?mode=command").get_data(as_text=True)
    assert 'class="nsls-coaching"' in html and "<details class=\"nsls-coaching\" open" not in html
    assert html.index("nsls-coaching") < html.index('id="task-table"')


def test_closed_day_opens_coaching_and_offers_tomorrow(setup):
    client, vault = setup
    _note(vault, "closed")
    html = client.get("/").get_data(as_text=True)
    assert '<details class="nsls-coaching" open' in html
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert f'href="/?date={tomorrow}"' in html and "Open tomorrow →" in html
    assert html.index("Open tomorrow") < html.index("nsls-coaching")


def test_closing_yesterday_offers_today(setup):
    client, vault = setup
    yday = (date.today() - timedelta(days=1)).isoformat()
    (vault / "01-daily" / f"{yday}.md").write_text("---\nstatus: closed\n---\n" + COACHING)
    html = client.get(f"/?date={yday}").get_data(as_text=True)
    assert f'href="/?date={TODAY}"' in html and "Open today →" in html


def test_a_past_closed_day_offers_the_next_day(setup):
    client, vault = setup
    past = (date.today() - timedelta(days=3)).isoformat()
    (vault / "01-daily" / f"{past}.md").write_text("---\nstatus: closed\n---\n" + COACHING)
    html = client.get(f"/?date={past}").get_data(as_text=True)
    nxt = (date.today() - timedelta(days=2)).isoformat()
    assert f'href="/?date={nxt}"' in html and "Open the next day →" in html


def test_no_coaching_and_no_close_shows_nothing_but_the_slot(setup):
    client, vault = setup
    (vault / "01-daily" / f"{TODAY}.md").write_text("---\nstatus: active\n---\n## Morning Check-in\n")
    html = client.get("/?mode=command").get_data(as_text=True)
    assert f'<div id="coaching-slot" data-date="{TODAY}">' in html
    assert 'class="nsls-coaching"' not in html


def test_a_running_close_says_claude_is_writing(setup):
    client, vault = setup
    now = datetime.now(timezone.utc).isoformat()
    (vault / "01-daily" / f"{TODAY}.md").write_text(
        f'---\nstatus: active\nclose_ready: 1\nclose_ready_at: "{now}"\n---\n## Morning Check-in\n')
    client.post("/listener-heartbeat")
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "Claude is writing…" in html


def test_a_click_with_no_claude_attached_promises_no_coaching(setup):
    client, vault = setup
    now = datetime.now(timezone.utc).isoformat()
    (vault / "01-daily" / f"{TODAY}.md").write_text(
        f'---\nstatus: active\nclose_ready: 1\nclose_ready_at: "{now}"\n---\n## Morning Check-in\n')
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "Claude is writing…" not in html


def test_partial_keeps_the_section_open_when_asked(setup):
    client, vault = setup
    _note(vault, "active")
    closed = client.get(f"/coaching?date={TODAY}").get_data(as_text=True)
    opened = client.get(f"/coaching?date={TODAY}&open=1").get_data(as_text=True)
    assert "<details class=\"nsls-coaching\" open" not in closed
    assert "<details class=\"nsls-coaching\" open" in opened
    assert closed.strip().startswith('<div id="coaching-slot"')


def test_coaching_text_is_escaped(setup):
    client, vault = setup
    (vault / "01-daily" / f"{TODAY}.md").write_text(
        "---\nstatus: active\n---\n## Coaching\n- <script>alert(1)</script>\n")
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_page_refreshes_the_coaching_section_on_a_note_change(setup):
    client, vault = setup
    _note(vault, "active")
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "function refreshCoaching(path)" in html and "refreshCoaching(path);" in html
