"""Regression tests for three 2026-07-05 reports:

1. A suggestion deleted (or done) on a PRIOR day resurfaced when close-day
   re-generated it — tombstones now span the last 7 days of notes.
2. A completed item still showed its estimate — done means 0h remaining.
3. Streaks counted log ROWS, not calendar days — three ticks spread over a
   month showed as a 3-day streak.
"""

from datetime import date, timedelta
import pytest
from companion.server import create_app, _recent_dispositions, _build_plan_context
from companion.streak import DayResult, compute_concern, streak_days


TODAY = date.today().isoformat()


def _day(offset: int) -> str:
    return (date.today() - timedelta(days=offset)).isoformat()


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    (v / "01-daily").mkdir(parents=True)
    habits = v / "30-habits"
    habits.mkdir(parents=True)
    (habits / "habits.md").write_text("# Daily Habits\n\n## Active\n\n- id: weights\n  name: weights\n")
    (habits / "log.md").write_text("# Daily habit log\n")
    return v


@pytest.fixture
def client(vault):
    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield app.test_client()
    finally:
        app.config["WATCHER"].stop()


# --- 1. tombstones: deleted/done items stay dead across days ---

def test_recent_dispositions_collects_across_days(vault):
    (vault / "01-daily" / f"{_day(2)}.md").write_text("""# Daily Note

## Morning Check-in

### My Top 3
1. [ ] whatever

### Deleted
- Give 3 Breaths a real project home

### Done
- Ship the deck
""")
    tombs = _recent_dispositions(vault, TODAY)
    assert any("3 breaths" in t.lower() for t in tombs)
    assert any("ship the deck" in t.lower() for t in tombs)


def test_prior_day_deleted_suggestion_stays_buried(client, vault):
    # deleted two days ago…
    (vault / "01-daily" / f"{_day(2)}.md").write_text("""# Daily Note

## Morning Check-in

### Deleted
- Give 3 Breaths a real project home
""")
    # …but close-day re-suggested it in TODAY's AI section
    (vault / "01-daily" / f"{TODAY}.md").write_text("""---
status: planning
---
# Daily Note

## Morning Check-in

### AI Suggested: Top 3
1. **Give 3 Breaths a real project home** — the habit exists without one
2. **Reply to the vendor thread** — blocks legal

### My Top 3
1.
""")
    html = client.get("/?mode=coach-morning").get_data(as_text=True)
    assert "3 Breaths" not in html          # buried
    assert "vendor thread" in html          # untouched suggestions still show


def test_prior_day_done_suggestion_stays_buried(client, vault):
    (vault / "01-daily" / f"{_day(1)}.md").write_text("""# Daily Note

## Morning Check-in

### Done
- Ship the deck
""")
    (vault / "01-daily" / f"{TODAY}.md").write_text("""---
status: planning
---
# Daily Note

## Morning Check-in

### AI Suggested: Top 3
1. Ship the deck

### My Top 3
1.
""")
    html = client.get("/?mode=coach-morning").get_data(as_text=True)
    assert "Ship the deck" not in html


def test_today_deleted_item_still_renders_as_toggle_state(client, vault):
    """Deleting TODAY must keep the row visible (struck through) so the
    builder can untoggle a mis-click — only PRIOR days tombstone."""
    (vault / "01-daily" / f"{TODAY}.md").write_text("""---
status: planning
---
# Daily Note

## Morning Check-in

### AI Suggested: Top 3
1. Ship the deck

### Deleted
- Ship the deck

### My Top 3
1.
""")
    html = client.get("/?mode=coach-morning").get_data(as_text=True)
    assert "Ship the deck" in html


# --- 2. done ⇒ 0h remaining ---

def test_done_item_shows_zero_remaining_and_drops_from_total(client, vault):
    (vault / "01-daily" / f"{TODAY}.md").write_text("""---
status: active
---
# Daily Note

## Morning Check-in

### My Top 3
1. [x] Finished thing <!--e:2-->
2. [ ] Open thing <!--e:1.5-->
""")
    html = client.get("/?mode=command").get_data(as_text=True)
    # planned total counts only the open item
    assert "1.5h" in html and "3.5h" not in html
    # the done row's estimate input reads 0; the file keeps the marker
    assert 'value="0"' in html
    assert "<!--e:2-->" in (vault / "01-daily" / f"{TODAY}.md").read_text()


# --- 3. streaks over calendar days, not log rows ---

def test_gap_days_break_streak():
    """Davo's weights log: ticks on 3 days spread over a month showed '3d'."""
    log = [
        DayResult("2026-06-03", 1.0),
        DayResult("2026-06-28", 1.0),
        DayResult("2026-07-03", 1.0),
    ]
    assert streak_days(log, "2026-07-03") == 1   # today's tick only
    assert compute_concern(log, "2026-07-03") == 0.0  # today done → ok


def test_unlogged_days_since_last_entry_count_as_misses():
    log = [DayResult("2026-06-28", 1.0)]
    # five unlogged days since → concern ≥ 2, streak dead
    assert compute_concern(log, "2026-07-03") >= 2.0
    assert streak_days(log, "2026-07-03") == 0


def test_today_unticked_is_not_a_miss():
    log = [DayResult("2026-07-02", 1.0)]
    assert compute_concern(log, "2026-07-03") == 0.0
    assert streak_days(log, "2026-07-03") == 1


def test_consecutive_days_still_count():
    log = [DayResult(f"2026-07-0{i}", 1.0) for i in range(1, 4)]
    assert streak_days(log, "2026-07-03") == 3


def test_single_gap_day_tolerated_but_not_counted():
    log = [DayResult("2026-07-01", 1.0), DayResult("2026-07-03", 1.0)]
    # one missed day (07-02) doesn't reset (concern 1.0), but only the
    # two active days count
    assert streak_days(log, "2026-07-03") == 2
