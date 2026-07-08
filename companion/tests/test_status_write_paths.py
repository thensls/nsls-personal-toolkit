"""Phase 1.3c: companion write paths set the `status:` frontmatter.

The daily-note lifecycle is planning -> active -> closed. The CLI/web
companion's explicit transition buttons commit those status changes to the
vault so both surfaces (web + cowork artifact) agree on the mode:

  - /lock-in (phase=morning) — "Lock in →"  -> status: active
  - /lock-in (phase=evening) — evening "Done" -> status: closed
  - /reset-plan — back to the morning plan    -> status: planning

These are explicit, user-driven save moments (no autosave). State lives in
the artifact/note; the write happens once on the lock-in.
"""

from datetime import date

import pytest

from companion.parsers import parse_frontmatter
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
2. [ ] Q3 LOP draft
3. [ ] Reply to vendor

### Bonus

### Habits
- [ ] **Walk**

## Insight Reflection

## End of Day
- Energy:
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
        yield (app.test_client(), vault, today)
    finally:
        app.config["WATCHER"].stop()


def _note_text(vault, today):
    return (vault / "01-daily" / f"{today}.md").read_text()


# ---------------------------------------------------------------------------
# /lock-in (morning) -> status: active
# ---------------------------------------------------------------------------

def test_lock_in_morning_sets_status_active(client_with_today):
    client, vault, today = client_with_today
    resp = client.post("/lock-in", data={"phase": "morning"})
    assert resp.status_code == 200
    fm = parse_frontmatter(_note_text(vault, today))
    assert fm["status"] == "active"


def test_lock_in_morning_preserves_top_3(client_with_today):
    client, vault, today = client_with_today
    client.post("/lock-in", data={"phase": "morning"})
    note = _note_text(vault, today)
    assert "Finish toolkit spec" in note
    assert "Q3 LOP draft" in note


# ---------------------------------------------------------------------------
# /lock-in (evening) -> status: closed
# ---------------------------------------------------------------------------

def test_lock_in_evening_sets_status_closed(client_with_today):
    client, vault, today = client_with_today
    resp = client.post("/lock-in", data={"phase": "evening"})
    assert resp.status_code == 200
    fm = parse_frontmatter(_note_text(vault, today))
    assert fm["status"] == "closed"


# ---------------------------------------------------------------------------
# /reset-plan -> status: planning
# ---------------------------------------------------------------------------

def test_reset_plan_sets_status_planning(client_with_today):
    client, vault, today = client_with_today
    # First lock in (active), then reset should pull it back to planning.
    client.post("/lock-in", data={"phase": "morning"})
    resp = client.post("/reset-plan")
    assert resp.status_code == 200
    fm = parse_frontmatter(_note_text(vault, today))
    assert fm["status"] == "planning"


# ---------------------------------------------------------------------------
# Full lifecycle round-trip through the companion
# ---------------------------------------------------------------------------

def test_status_lifecycle_through_companion(client_with_today):
    client, vault, today = client_with_today
    client.post("/lock-in", data={"phase": "morning"})
    assert parse_frontmatter(_note_text(vault, today))["status"] == "active"
    client.post("/lock-in", data={"phase": "evening"})
    assert parse_frontmatter(_note_text(vault, today))["status"] == "closed"


# ---------------------------------------------------------------------------
# Server-side auto-scaffold (the empty note the companion creates when a user
# opens the Command Center without having run open-day) -> status: planning
# ---------------------------------------------------------------------------

def test_auto_scaffold_note_has_status_planning(tmp_path):
    # _ensure_daily_note_scaffold creates a fresh planning note; it must carry
    # status: planning so _detect_day_state routes it to coach-morning instead
    # of falling back to legacy section inference.
    from companion.server import _ensure_daily_note_scaffold

    note = tmp_path / "01-daily" / "2026-06-21.md"
    _ensure_daily_note_scaffold(note)
    fm = parse_frontmatter(note.read_text(encoding="utf-8"))
    assert fm["status"] == "planning"
