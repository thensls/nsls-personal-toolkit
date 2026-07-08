from companion.parsers import parse_habits, parse_log, append_day_to_log
from companion.parsers import parse_habits_from_daily_note


def test_parse_habits_active():
    md = """# Daily Habits

## Active

- id: walk
  name: Walk
  emoji: 🚶
  target: 30min
  frequency: daily

- id: read
  name: Read
  emoji: 📖
  target: 15min
  frequency: daily
"""
    habits = parse_habits(md)
    assert len(habits["active"]) == 2
    assert habits["active"][0] == {
        "id": "walk", "name": "Walk", "emoji": "🚶",
        "target": "30min", "frequency": "daily",
    }


def test_parse_habits_archived():
    md = """# Daily Habits

## Active

(none)

## Archived

- id: meditation
  name: Meditate
  emoji: 🧘
  target: 10min
  frequency: daily
  archived_at: 2026-03-15
"""
    habits = parse_habits(md)
    assert len(habits["archived"]) == 1
    assert habits["archived"][0]["archived_at"] == "2026-03-15"


def test_parse_habits_empty():
    habits = parse_habits("# Daily Habits\n")
    assert habits["active"] == []
    assert habits["archived"] == []


def test_parse_log_single_day():
    md = """# Daily habit log
2026-05-15 · walk:1.0 · read:0.5 · workout:0.0
"""
    log = parse_log(md)
    assert log == [
        {"date": "2026-05-15",
         "ticks": {"walk": 1.0, "read": 0.5, "workout": 0.0}}
    ]


def test_parse_log_multiple_days():
    md = """# Daily habit log
2026-05-14 · walk:1.0 · read:1.0
2026-05-15 · walk:0.5 · read:0.0
"""
    log = parse_log(md)
    assert len(log) == 2
    assert log[1]["ticks"]["walk"] == 0.5


def test_append_day_new_date():
    existing = "# Daily habit log\n2026-05-14 · walk:1.0\n"
    after = append_day_to_log(existing, "2026-05-15", {"walk": 1.0, "read": 0.5})
    assert "2026-05-15 · walk:1.0 · read:0.5" in after
    assert "2026-05-14 · walk:1.0" in after


def test_append_day_replaces_existing_date():
    existing = "# Daily habit log\n2026-05-15 · walk:1.0\n"
    after = append_day_to_log(existing, "2026-05-15", {"walk": 0.5, "read": 0.5})
    # only one row for 2026-05-15
    assert after.count("2026-05-15") == 1
    assert "walk:0.5" in after
    assert "walk:1.0" not in after


ACTIVE = [
    {"id": "walk", "name": "Walk", "emoji": "🚶", "target": "30min", "frequency": "daily"},
    {"id": "read", "name": "Read", "emoji": "📖", "target": "15min", "frequency": "daily"},
]


def test_habits_from_daily_all_unchecked():
    md = "## Morning Check-in\n### Habits\n- [ ] **Walk**\n- [ ] **Read**\n"
    assert parse_habits_from_daily_note(md, ACTIVE) == {"walk": 0.0, "read": 0.0}


def test_habits_from_daily_mixed():
    md = "## Morning Check-in\n### Habits\n- [x] **Walk**\n- [/] **Read**\n"
    assert parse_habits_from_daily_note(md, ACTIVE) == {"walk": 1.0, "read": 0.5}


def test_habits_from_daily_ignores_unknown_name():
    md = "## Morning Check-in\n### Habits\n- [x] **Walk**\n- [x] **Meditate**\n"
    # Meditate isn't in ACTIVE → ignored. Read defaults to 0.
    assert parse_habits_from_daily_note(md, ACTIVE) == {"walk": 1.0, "read": 0.0}


def test_habits_from_daily_missing_section():
    md = "## Morning Check-in\n### My Top 3\n1. Foo\n"
    assert parse_habits_from_daily_note(md, ACTIVE) == {"walk": 0.0, "read": 0.0}


def test_habits_from_daily_stops_at_next_subsection():
    md = ("## Morning Check-in\n### Habits\n- [x] **Walk**\n"
          "### Vitality\n- [x] **Read**\n")
    # Read in Vitality is not in the Habits section
    assert parse_habits_from_daily_note(md, ACTIVE) == {"walk": 1.0, "read": 0.0}
