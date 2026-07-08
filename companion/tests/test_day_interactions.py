from datetime import date
import pytest
from companion.server import create_app


@pytest.fixture
def client_with_today(tmp_path):
    vault = tmp_path / "vault"
    daily = vault / "01-daily"
    daily.mkdir(parents=True)
    habits = vault / "30-habits"
    habits.mkdir(parents=True)

    today = date.today().isoformat()
    (daily / f"{today}.md").write_text("""# Daily Note

## Morning Check-in

### My Top 3
1. Finish toolkit spec
2. Q3 LOP draft
3. Reply to vendor

### Habits
- [ ] **Walk**
""")
    (habits / "habits.md").write_text("""# Daily Habits

## Active

- id: walk
  name: Walk
  emoji: 🚶
  target: 30min
  frequency: daily
""")
    (habits / "log.md").write_text("# Daily habit log\n")

    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield (app.test_client(), vault)
    finally:
        app.config["WATCHER"].stop()


def test_tick_habit_writes_to_log(client_with_today):
    client, vault = client_with_today
    resp = client.post("/tick", data={"habit_id": "walk", "percent": "1.0"})
    assert resp.status_code == 200
    log = (vault / "30-habits" / "log.md").read_text()
    today = date.today().isoformat()
    assert today in log
    assert "walk:1.0" in log


def test_tick_rejects_bad_habit_id(client_with_today):
    client, _ = client_with_today
    resp = client.post("/tick", data={"habit_id": "../etc", "percent": "1.0"})
    assert resp.status_code == 400


def test_tick_rejects_undeclared_habit_id(client_with_today):
    """Well-formed ids that aren't Active habits in habits.md must not enter
    log.md — phantom ids grow streaks and corrupt close-day reconciliation."""
    client, vault = client_with_today
    resp = client.post("/tick", data={"habit_id": "open-day", "percent": "1.0"})
    assert resp.status_code == 400
    log = (vault / "30-habits" / "log.md").read_text()
    assert "open-day" not in log


def test_toggle_top_3_checks_then_unchecks(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    # Seed a note with checkbox items in Top 3
    note.write_text(
        "## Morning Check-in\n### My Top 3\n"
        "1. [ ] First priority\n2. [ ] Second\n3. [ ] Third\n"
    )
    resp = client.post("/toggle", data={"section": "top_3", "index": "0"})
    assert resp.status_code == 204
    assert "1. [x] First priority" in note.read_text()
    # The rendered HTML must reflect the toggled (checked/done) state with the
    # struck-through marker on the row text (.is-done → CSS line-through).
    page = client.get("/").data.decode()
    assert "is-done" in page
    assert "First priority" in page
    # Toggle back
    client.post("/toggle", data={"section": "top_3", "index": "0"})
    assert "1. [ ] First priority" in note.read_text()
    page = client.get("/").data.decode()
    # After un-toggle, the done marker should not appear for this item's text.
    first_idx = page.index("First priority")
    preceding = page[max(0, first_idx - 200):first_idx]
    assert "is-done" not in preceding


def test_toggle_injects_checkbox_when_missing(client_with_today):
    """Fresh open-day notes seed Top 3 without checkboxes (legacy seed format).
    The toggle should still work — inject [x] on the first click."""
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    # Note: no [ ] markers on the Top 3 items
    note.write_text(
        "## Morning Check-in\n### My Top 3\n"
        "1. Markerless priority\n2. Another\n3. Third\n"
    )
    resp = client.post("/toggle", data={"section": "top_3", "index": "0"})
    assert resp.status_code == 204
    body = note.read_text()
    # First item now has [x] injected after the period
    assert "1. [x] Markerless priority" in body
    # Other items unchanged
    assert "2. Another" in body


def test_toggle_rejects_unknown_section(client_with_today):
    client, _ = client_with_today
    resp = client.post("/toggle", data={"section": "../etc", "index": "0"})
    assert resp.status_code == 400


def test_save_writes_insight_reflection(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text("## Insight Reflection\n\n(empty)\n\n## Gratitude\n\n")
    resp = client.post("/save", data={
        "section": "Insight Reflection",
        "content": "Today I noticed I rush through morning ritual.",
    })
    assert resp.status_code == 204
    body = note.read_text()
    assert "Today I noticed" in body
    assert "## Gratitude" in body  # adjacent section preserved


def test_save_rejects_disallowed_section(client_with_today):
    client, _ = client_with_today
    resp = client.post("/save", data={"section": "Plan", "content": "x"})
    assert resp.status_code == 400


def test_set_top_3_creates_note_on_empty_vault(client_with_today):
    """First /set-top-3 call against a vault with no daily note creates the
    scaffold and writes the user's text. Saves silently (204, no DOM swap) —
    re-rendering the form mid-typing wiped the field the user tabbed into."""
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.unlink(missing_ok=True)  # ensure no note exists
    resp = client.post("/set-top-3", data={"index": "0", "text": "Ship companion v1.1"})
    assert resp.status_code == 204
    assert note.exists()
    body = note.read_text()
    assert "### My Top 3" in body
    assert "1. [ ] Ship companion v1.1" in body


def test_set_top_3_updates_existing_item_preserves_checkbox(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n### My Top 3\n"
        "1. [x] Old text\n2. [ ] Second\n3. [ ] Third\n"
    )
    resp = client.post("/set-top-3", data={"index": "0", "text": "New text"})
    assert resp.status_code == 204  # saves silently, no re-render
    body = note.read_text()
    # Checked state preserved; only text replaced
    assert "1. [x] New text" in body
    assert "2. [ ] Second" in body


def test_set_top_3_index_2_does_not_shift_to_earlier_slot(client_with_today):
    """Regression: typing in slot 3 with slots 1-2 empty must stay in slot 3.
    The old form compacted priorities, so slot-3 text re-rendered into slot 1.
    Positional storage + a positional `top3_slots` context keep slot i ↔ index i.
    """
    from companion.server import _build_plan_context
    from companion.parsers import parse_daily_note_sections
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n### My Top 3\n1. [ ]\n2. [ ]\n3. [ ]\n\n### Bonus\n"
    )
    assert client.post("/set-top-3", data={"index": "2", "text": "third only"}).status_code == 204
    body = note.read_text()
    assert "3. [ ] third only" in body
    # And the plan context renders it positionally in slot 3, not slot 1.
    morning = parse_daily_note_sections(body).get("Morning Check-in", "")
    from companion.server import _extract_top_3, _extract_bonus
    plan = _build_plan_context(body, vault, today, _extract_top_3(morning), _extract_bonus(morning))
    assert plan["top3_slots"] == ["", "", "third only"]


def test_set_bonus_updates_nth_item(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n### Bonus\n"
        "1. [ ] First bonus\n2. [ ] Second\n"
    )
    resp = client.post("/set-bonus", data={"index": "1", "text": "Updated second"})
    assert resp.status_code == 200  # re-renders #bonus-list partial
    assert b"bonus-list" in resp.data
    body = note.read_text()
    assert "2. [ ] Updated second" in body
    assert "1. [ ] First bonus" in body


def test_delete_bonus_renumbers_whole_section(client_with_today):
    """Regression: deleting a middle item must renumber the ENTIRE section from
    1, not just from the deletion point. The old loop produced duplicate
    ordinals like '1. A / 1. C' when deleting anything but the first item."""
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n### Bonus\n"
        "1. [ ] Bonus A\n2. [ ] Bonus B\n3. [ ] Bonus C\n4. [ ] Bonus D\n"
    )
    # delete the middle item (index 1 = "Bonus B")
    resp = client.post("/delete-bonus", data={"index": "1"})
    assert resp.status_code == 200
    body = note.read_text()
    assert "Bonus B" not in body
    # survivors renumbered 1..3 with no duplicates / gaps
    assert "1. [ ] Bonus A" in body
    assert "2. [ ] Bonus C" in body
    assert "3. [ ] Bonus D" in body
    # exactly one of each ordinal
    import re as _re
    nums = _re.findall(r"^(\d+)\. ", body, _re.MULTILINE)
    assert nums == ["1", "2", "3"]


def test_ai_suggestions_surface_in_plan_your_day(client_with_today):
    """Items under `### AI Suggested: …` subsections of Morning Check-in
    should appear as suggestions on Step 2, with the source label visible
    and rationale/bold markers stripped. Regression for the original gap
    flagged in server.py:137-139 ('AI suggestions not yet surfaced')."""
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n"
        "### AI Suggested: Top 3 (from yesterday's close)\n"
        "1. **Reply to Joe on PR #142** — Blocks his merge.\n"
        "2. **Q3 LOP draft to Kevin** — Deadline Thursday.\n"
        "\n"
        "### AI Suggested: Delegate These\n"
        "1. **Schedule offsite** → Katie — Operational.\n"
        "\n"
        "### My Top 3\n1. [ ]\n2. [ ]\n3. [ ]\n"
        "\n### Bonus\n"
    )
    resp = client.get("/?mode=coach-morning&step=2")
    assert resp.status_code == 200
    body = resp.data
    # Cleaned titles
    assert b"Reply to Joe on PR #142" in body
    assert b"Q3 LOP draft to Kevin" in body
    assert b"Schedule offsite" in body
    # Source labels visible — both Top 3 and Delegate variants
    assert b"AI: Top 3" in body
    assert b"AI: Delegate These" in body
    # Rationale / bold markers stripped from the visible item text
    assert b"Blocks his merge" not in body  # rationale lives in the note, not the row
    # Taking the suggestion as a priority writes it to Top 3.
    resp2 = client.post("/plan-action", data={
        "text": "Reply to Joe on PR #142", "action": "pri",
    })
    assert resp2.status_code == 200
    assert "1. [ ] Reply to Joe on PR #142" in note.read_text()


def test_set_bonus_grows_with_each_save(client_with_today):
    """The bonus list should accept multiple items. Regression for the bug
    where the input's hx-vals index stayed stale and every save overwrote
    item 0 — user could only ever add one bonus."""
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.unlink(missing_ok=True)
    # First save creates the scaffold + writes index 0
    client.post("/set-bonus", data={"index": "0", "text": "First bonus"})
    # Second save (index 1 from the freshly-rerendered partial) appends.
    client.post("/set-bonus", data={"index": "1", "text": "Second bonus"})
    # Third save (index 2) appends again.
    client.post("/set-bonus", data={"index": "2", "text": "Third bonus"})
    body = note.read_text()
    assert "1. [ ] First bonus" in body
    assert "2. [ ] Second bonus" in body
    assert "3. [ ] Third bonus" in body


def test_set_top_3_rejects_newline_in_text(client_with_today):
    client, _ = client_with_today
    resp = client.post("/set-top-3", data={"index": "0", "text": "line1\n## Hijacked"})
    assert resp.status_code == 400


def test_set_top_3_rejects_out_of_bounds_index(client_with_today):
    client, _ = client_with_today
    resp = client.post("/set-top-3", data={"index": "99", "text": "x"})
    assert resp.status_code == 400


# --- suggestion dedup + deleted-exclusion (no duplicate / no-resurrect) ------

def _yesterday(today):
    from datetime import datetime, timedelta
    return (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).date().isoformat()


def _plan_for(vault, today):
    from companion.server import _build_plan_context, _extract_top_3, _extract_bonus
    from companion.parsers import parse_daily_note_sections
    body = (vault / "01-daily" / f"{today}.md").read_text()
    morning = parse_daily_note_sections(body).get("Morning Check-in", "")
    return _build_plan_context(body, vault, today, _extract_top_3(morning), _extract_bonus(morning))


def test_ai_suggestions_suppress_reworded_carryover_dupes(client_with_today):
    """When close-day seeded AI suggestions, the raw carry-over they were built
    from must NOT also show — that's the reworded duplicate builders hit."""
    client, vault = client_with_today
    today = date.today().isoformat()
    (vault / "01-daily" / f"{_yesterday(today)}.md").write_text(
        "## Morning Check-in\n### My Top 3\n1. [ ] Port PP CLI to Cowork\n### Bonus\n"
    )
    (vault / "01-daily" / f"{today}.md").write_text(
        "## Morning Check-in\n"
        "### AI Suggested: Top 3\n1. Finish the PP CLI Cowork port (~50% done)\n"
        "### My Top 3\n1. [ ]\n2. [ ]\n3. [ ]\n### Bonus\n"
    )
    texts = [s["text"] for s in _plan_for(vault, today)["suggestions"]]
    assert any("Finish the PP CLI Cowork port" in t for t in texts)
    assert all("Port PP CLI to Cowork" not in t for t in texts)  # carry-over suppressed


def test_deleted_items_do_not_carry_over(client_with_today):
    """An item the builder deleted yesterday (in the prior note's ### Deleted)
    must not resurface as a carry-over suggestion today."""
    from companion.server import _extract_carryovers
    client, vault = client_with_today
    today = date.today().isoformat()
    (vault / "01-daily" / f"{_yesterday(today)}.md").write_text(
        "## Morning Check-in\n"
        "### My Top 3\n1. [ ] Keep me\n2. [ ] Delete me\n"
        "### Bonus\n\n### Deleted\n- Delete me\n"
    )
    texts = [c["text"] for c in _extract_carryovers(vault, today)]
    assert "Keep me" in texts
    assert "Delete me" not in texts


# --- per-task estimated hours (timeboxing) ----------------------------------

def test_set_estimate_writes_and_clears_marker(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    assert client.post("/set-estimate", data={"section": "top_3", "index": "0", "hours": "1.5"}).status_code == 200
    assert "<!--e:1.5-->" in note.read_text()
    client.post("/set-estimate", data={"section": "top_3", "index": "0", "hours": ""})
    assert "<!--e:" not in note.read_text()


def test_estimate_survives_progress_change(client_with_today):
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    client.post("/set-estimate", data={"section": "top_3", "index": "1", "hours": "2.25"})
    client.post("/set-progress", data={"section": "top_3", "index": "1", "level": "50"})
    line = [l for l in note.read_text().splitlines() if "<!--e:2.25-->" in l][0]
    assert "<!--p:50-->" in line  # estimate and progress coexist on the same item


def test_estimate_parsed_into_item(client_with_today):
    from companion.server import _extract_top_3
    from companion.parsers import parse_daily_note_sections
    client, vault = client_with_today
    today = date.today().isoformat()
    note = vault / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n### My Top 3\n"
        "1. [ ] Task A <!--e:0.25-->\n"
        "2. [ ] Task B <!--p:50--> <!--e:3-->\n### Bonus\n"
    )
    morning = parse_daily_note_sections(note.read_text()).get("Morning Check-in", "")
    items = _extract_top_3(morning)
    assert items[0]["text"] == "Task A" and items[0]["est"] == 0.25
    assert items[1]["text"] == "Task B" and items[1]["est"] == 3.0 and items[1]["progress"] == 50


def test_set_estimate_rejects_bad_hours(client_with_today):
    client, _ = client_with_today
    assert client.post("/set-estimate", data={"section": "top_3", "index": "0", "hours": "abc"}).status_code == 400
    assert client.post("/set-estimate", data={"section": "top_3", "index": "0", "hours": "99"}).status_code == 400


def test_carryover_normalized_dedup_collapses_near_identical(client_with_today):
    """Tagged / parenthetical variants of the same task collapse to one row."""
    client, vault = client_with_today
    today = date.today().isoformat()
    (vault / "01-daily" / f"{_yesterday(today)}.md").write_text(
        "## Morning Check-in\n### My Top 3\n"
        "1. [ ] Optional NSLS: Finish the draft\n"
        "2. [ ] Finish the draft (~50% done)\n### Bonus\n"
    )
    # today's note has no AI suggestions → carry-over path
    (vault / "01-daily" / f"{today}.md").write_text(
        "## Morning Check-in\n### My Top 3\n1. [ ]\n### Bonus\n"
    )
    sugg = _plan_for(vault, today)["suggestions"]
    assert len(sugg) == 1
