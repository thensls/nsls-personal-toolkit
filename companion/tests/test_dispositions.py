"""Regression tests for Plan-Your-Day dispositions, unplanned items,
energy, daily insight, and habit rename — the paths added/fixed on
2026-06-03 after user-reported bugs."""

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
1. [ ] Finish toolkit spec
2. [ ]
3. [ ]

### Bonus

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


def _note(vault):
    return (vault / "01-daily" / f"{date.today().isoformat()}.md").read_text()


# --- Dispositions: done / delete / defer are mutually exclusive ---

def test_done_and_delete_are_independent(client_with_today):
    """Marking an item Done must NOT also mark it Deleted (the original bug)."""
    client, vault = client_with_today
    client.post("/plan-action", data={"text": "Reply to vendor", "action": "done"})
    note = _note(vault)
    assert "### Done" in note
    assert "- Reply to vendor" in note
    assert "### Deleted" not in note


def test_disposition_moves_not_duplicates(client_with_today):
    """Clicking Delete on a Done item moves it; it shouldn't end up in both."""
    client, vault = client_with_today
    client.post("/plan-action", data={"text": "Ship it", "action": "done"})
    client.post("/plan-action", data={"text": "Ship it", "action": "delete"})
    note = _note(vault)
    # Exactly one membership: in Deleted, not in Done.
    assert "### Deleted" in note
    assert note.count("- Ship it") == 1
    # The Done section should be gone (it was the only item).
    done_idx = note.find("### Done")
    assert done_idx == -1


def test_disposition_untoggle(client_with_today):
    """Clicking the active disposition again removes it."""
    client, vault = client_with_today
    client.post("/plan-action", data={"text": "Maybe later", "action": "defer"})
    assert "- Maybe later" in _note(vault)
    client.post("/plan-action", data={"text": "Maybe later", "action": "defer"})
    note = _note(vault)
    assert "- Maybe later" not in note
    assert "### Deferred" not in note


def test_disposition_vacates_top_3(client_with_today):
    """Marking a Top 3 item Done removes it from the Top 3 list."""
    client, vault = client_with_today
    # "Finish toolkit spec" is item 1 in Top 3.
    client.post("/plan-action", data={"text": "Finish toolkit spec", "action": "done"})
    note = _note(vault)
    assert "### Done" in note
    # The Top 3 slot should be cleared (no longer a live priority).
    top_3_block = note.split("### My Top 3")[1].split("###")[0]
    assert "Finish toolkit spec" not in top_3_block


def test_legacy_dismissed_reads_as_done(client_with_today):
    """Items in a legacy ### Dismissed section render as Done."""
    client, vault = client_with_today
    note_path = vault / "01-daily" / f"{date.today().isoformat()}.md"
    md = note_path.read_text().replace(
        "### Habits", "### Dismissed\n- Old item\n\n### Habits"
    )
    note_path.write_text(md)
    resp = client.get("/")
    assert resp.status_code == 200


# --- Unplanned items ---

def test_unplanned_write_ignores_decoy_heading_outside_morning(client_with_today):
    """A `### Unplanned` under `## End of Day` (left by a close pass) must not
    swallow writes: the reader only looks inside Morning Check-in, so writing
    to the decoy made every added win invisible (2026-07-05, a builder)."""
    client, vault = client_with_today
    note = vault / "01-daily" / f"{date.today().isoformat()}.md"
    note.write_text(note.read_text() + "\n## End of Day\n- Energy: medium\n\n### Unplanned\n1. [ ] stranded win\n")
    resp = client.post("/set-unplanned", data={"index": "0", "text": "pickleball"})
    assert resp.status_code == 200
    from companion.parsers import parse_daily_note_sections
    md = _note(vault)
    morning = parse_daily_note_sections(md).get("Morning Check-in", "")
    assert "pickleball" in morning                       # landed where the UI reads
    end_of_day = md.split("## End of Day", 1)[1]
    assert "pickleball" not in end_of_day                # decoy untouched
    assert "stranded win" in end_of_day
    # and the UI now shows it
    html = client.get("/?mode=command").get_data(as_text=True)
    assert "pickleball" in html


def test_set_unplanned_writes_and_returns_partial(client_with_today):
    client, vault = client_with_today
    resp = client.post("/set-unplanned", data={"index": "0", "text": "Fixed prod bug"})
    assert resp.status_code == 200
    assert "unplanned-section" in resp.get_data(as_text=True)
    note = _note(vault)
    assert "### Unplanned" in note
    assert "Fixed prod bug" in note


def test_unplanned_multi_add_no_overwrite(client_with_today):
    """Two adds at the rendered blank index must not clobber each other.

    The partial re-render advances the index, so the second add lands in a
    fresh slot rather than overwriting the first.
    """
    client, vault = client_with_today
    client.post("/set-unplanned", data={"index": "0", "text": "First win"})
    # After the first add, the blank input's index is now 1.
    client.post("/set-unplanned", data={"index": "1", "text": "Second win"})
    note = _note(vault)
    assert "First win" in note
    assert "Second win" in note


def test_delete_unplanned(client_with_today):
    client, vault = client_with_today
    client.post("/set-unplanned", data={"index": "0", "text": "Temp item"})
    resp = client.post("/delete-unplanned", data={"index": "0"})
    assert resp.status_code == 200
    assert "Temp item" not in _note(vault)


# --- Energy ---

def test_set_energy_writes_and_reads_back(client_with_today):
    client, vault = client_with_today
    resp = client.post("/set-energy", data={"level": "high"})
    assert resp.status_code in (200, 204)
    note = _note(vault)
    assert "Energy: high" in note


def test_morning_and_evening_energy_are_separate(client_with_today):
    """Morning energy → Morning Check-in; evening energy → End of Day."""
    client, vault = client_with_today
    client.post("/set-energy", data={"level": "high", "when": "morning"})
    client.post("/set-energy", data={"level": "low", "when": "evening"})
    note = _note(vault)
    morning_block = note.split("## Morning Check-in")[1].split("\n## ")[0]
    eod_block = note.split("## End of Day")[1]
    assert "Energy: high" in morning_block
    assert "Energy: low" in eod_block


def test_set_energy_replaces_empty_line_no_duplicate(client_with_today):
    """The reported bug: an empty `- Energy:` template line must be replaced,
    not duplicated."""
    client, vault = client_with_today
    note_path = vault / "01-daily" / f"{date.today().isoformat()}.md"
    # Seed an End of Day section with an empty Energy bullet (the template shape).
    note_path.write_text(note_path.read_text() + "\n## End of Day\n- Energy:\n")
    client.post("/set-energy", data={"level": "medium", "when": "evening"})
    note = _note(vault)
    # Exactly one Energy line in End of Day — no duplicate.
    eod_block = note.split("## End of Day")[1]
    assert eod_block.count("- Energy:") == 1
    assert "Energy: medium" in eod_block


# --- Daily Insight must NOT flip the view to results mode ---

def test_daily_insight_does_not_trigger_results_mode(client_with_today):
    """Saving a Command Center insight writes ## Daily Insight, not
    ## Insight Reflection, so the day stays in Command Center."""
    client, vault = client_with_today
    client.post("/save", data={"section": "Daily Insight", "content": "Noticed I focus best at 7am"})
    note = _note(vault)
    assert "## Daily Insight" in note
    # Must NOT have created the day-close section.
    assert "## Insight Reflection" not in note
    # The view should still be Command Center, not results.
    html = client.get("/").get_data(as_text=True)
    assert "Command Center" in html


def test_insight_reflection_still_triggers_results(client_with_today):
    """The real day-close section still flips to results mode."""
    client, vault = client_with_today
    client.post("/save", data={"section": "Insight Reflection", "content": "Day is closed"})
    html = client.get("/").get_data(as_text=True)
    assert "Command Center" not in html


# --- Habit rename preserves id/log ---

def test_habit_rename_preserves_id(client_with_today):
    client, vault = client_with_today
    resp = client.post("/habit/rename", data={"habit_id": "walk", "new_name": "Morning Walk"})
    assert resp.status_code == 200
    habits = (vault / "30-habits" / "habits.md").read_text()
    assert "name: Morning Walk" in habits
    assert "id: walk" in habits  # id unchanged → log history intact


# --- AI-suggested titles must never leak a checkbox or the estimate marker ---

def test_ai_suggestion_strips_leaked_checkbox_and_estimate():
    """open-day sometimes writes suggestions as '1. [ ] text <!--e:X-->';
    neither the checkbox nor the estimate may show in the title (2026-07-13,
    a builder). The estimate is returned as data instead."""
    from companion.server import _extract_ai_suggestions
    md = ("### AI Suggested: Top 3\n"
          "1. [ ] P 3b metrics board <!--e:0.75-->\n"
          "2. [x] Ship the thing\n"
          "3. **Bold item** — rationale tail <!--e:0.5-->\n")
    items = _extract_ai_suggestions(md)
    assert items[0]["text"] == "P 3b metrics board" and items[0]["est"] == 0.75
    assert items[1]["text"] == "Ship the thing"
    assert items[2]["text"] == "Bold item" and items[2]["est"] == 0.5
    assert all("[" not in i["text"] and "<!--" not in i["text"] for i in items)
