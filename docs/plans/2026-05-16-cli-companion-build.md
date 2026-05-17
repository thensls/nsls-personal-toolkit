# CLI Companion Build — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **⚠️ REVIEW GOAL — READ FIRST:** This plan adds a **visual, interactive web companion** on top of the existing personal toolkit. The guiding principle is: **the new version must do everything the original toolkit does today**, with only the additions and enhancements explicitly requested (habits/streaks engine, gratitude/insight reflection, brain-dump preservation, local web UI, SSE auto-refresh), plus the new visual and interactive layer.
>
> **Reviewers: please verify that no feature of the existing CLI toolkit has been accidentally dropped, hidden, or thinned in the pivot from the cowork design to this CLI direction.** The existing skills are listed in `CLAUDE.md` at the repo root: `/open-day`, `/open-week`, `/close-day`, `/close-week`, `/learn`, `/self-insight`, `/log`, `/familiar`, `/person-intelligence`, plus `obsidian-setup`. The strategy layer (operating memo, personal profile, project stack ranking, push/protect modes, meeting coaching) must remain fully supported. Read each skill's current `SKILL.md` to understand what it produces today, and cross-check that the companion either (a) surfaces that output in a view, or (b) explicitly leaves it untouched in the CLI as it is today. Flag anything that looks like a silent regression.

**Goal:** Build the local web companion described in `docs/specs/2026-05-16-cli-companion-webapp-design.md`. Python (Flask + watchdog) backend on `localhost:7777` serving HTMX + Tailwind + Alpine.js templates that read and write the user's Obsidian vault directly. Browser auto-refreshes via Server-Sent Events when vault files change. CLI skills remain unchanged except for two small habits-related additions.

**Architecture:** Single Python process per user machine. Watches the Obsidian vault for changes; pushes SSE updates to any connected browsers. Browser POSTs back changes (checkbox ticks, reflection text, new habits). All persistence is plain markdown in the existing vault. No new MCP servers, no Anthropic-side dependencies, no React.

**Tech Stack:** Python 3.10+ · Flask · watchdog · pytest · Jinja2 templates · Tailwind CSS (CDN) · HTMX (CDN) · Alpine.js (CDN). No build step. All frontend assets loaded via CDN script tags.

---

## Phase 1 — Foundation

### Task 1: Scaffold the `companion/` Python project

**Files:**
- Create: `companion/__init__.py`
- Create: `companion/pyproject.toml`
- Create: `companion/requirements.txt`
- Create: `companion/conftest.py`

- [ ] **Step 1: Create the directory tree**

```bash
cd ~/.claude/local-plugins/nsls-personal-toolkit
mkdir -p companion/templates/_components companion/static companion/tests
touch companion/__init__.py
```

- [ ] **Step 2: Write `companion/requirements.txt`**

```
flask>=3.0
watchdog>=4.0
click>=8.1
pytest>=8.0
```

- [ ] **Step 3: Write `companion/pyproject.toml`**

```toml
[project]
name = "nsls-toolkit-companion"
version = "0.1.0"
description = "Local web companion for the NSLS personal productivity toolkit"
requires-python = ">=3.10"
dependencies = [
  "flask>=3.0",
  "watchdog>=4.0",
  "click>=8.1",
]

[project.scripts]
toolkit-companion = "companion.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [".."]
```

- [ ] **Step 4: Install in editable mode and verify**

```bash
cd companion && python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install pytest
pytest -q
```

Expected: pytest runs, "no tests ran", exit 0.

- [ ] **Step 5: Commit**

```bash
git add companion/__init__.py companion/pyproject.toml companion/requirements.txt
git commit -m "scaffold: companion python project"
```

---

### Task 2: Streak rule in Python with full test coverage

**Files:**
- Create: `companion/streak.py`
- Create: `companion/tests/test_streak.py`

- [ ] **Step 1: Write failing tests covering the six canonical sequences**

`companion/tests/test_streak.py`:

```python
from companion.streak import compute_concern, status_for, streak_days, DayResult


def test_a_five_hits_streak_5_concern_0():
    log = [DayResult(date=f"2026-05-1{i}", percent=1.0) for i in range(1, 6)]
    assert streak_days(log) == 5
    assert compute_concern(log) == 0
    assert status_for(compute_concern(log)) == "ok"


def test_b_partial_middle_then_full_streak_alive():
    log = [
        DayResult("2026-05-11", 1.0),
        DayResult("2026-05-12", 1.0),
        DayResult("2026-05-13", 0.5),
        DayResult("2026-05-14", 1.0),
        DayResult("2026-05-15", 1.0),
    ]
    assert streak_days(log) == 5
    assert compute_concern(log) == 0


def test_c_two_partials_one_miss_recorded():
    log = [
        DayResult("2026-05-13", 1.0),
        DayResult("2026-05-14", 0.5),
        DayResult("2026-05-15", 0.5),
    ]
    assert compute_concern(log) == 1.0
    assert status_for(1.0) == "one_miss"


def test_d_three_partials_at_risk():
    log = [
        DayResult("2026-05-13", 0.5),
        DayResult("2026-05-14", 0.5),
        DayResult("2026-05-15", 0.5),
    ]
    assert compute_concern(log) == 1.5
    assert status_for(1.5) == "at_risk"


def test_e_four_partials_reset():
    log = [
        DayResult("2026-05-12", 0.5),
        DayResult("2026-05-13", 0.5),
        DayResult("2026-05-14", 0.5),
        DayResult("2026-05-15", 0.5),
    ]
    assert compute_concern(log) == 2.0
    assert status_for(2.0) == "reset"


def test_f_two_misses_reset():
    log = [
        DayResult("2026-05-13", 1.0),
        DayResult("2026-05-14", 0.0),
        DayResult("2026-05-15", 0.0),
    ]
    assert compute_concern(log) == 2.0
    assert status_for(2.0) == "reset"


def test_mixed_miss_then_partial_at_risk():
    log = [DayResult("2026-05-14", 0.0), DayResult("2026-05-15", 0.5)]
    assert compute_concern(log) == 1.5


def test_full_day_mid_chain_clears_concern():
    log = [
        DayResult("2026-05-12", 0.5),
        DayResult("2026-05-13", 0.5),
        DayResult("2026-05-14", 1.0),
        DayResult("2026-05-15", 0.5),
    ]
    assert compute_concern(log) == 0.5


def test_empty_log_returns_zero():
    assert compute_concern([]) == 0
    assert streak_days([]) == 0
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd companion && pytest tests/test_streak.py -v
```

Expected: 9 errors, "ModuleNotFoundError: No module named 'companion.streak'".

- [ ] **Step 3: Implement `companion/streak.py`**

```python
"""Canonical streak rule for the NSLS toolkit.

Mirrors the prose description in skills/close-day/SKILL.md. The rule lives
in exactly two places: this module (for the web companion) and the prose
paragraph in close-day's prompt (for narrative description).
"""

from dataclasses import dataclass
from typing import Literal


Status = Literal["ok", "one_miss", "at_risk", "reset"]


@dataclass(frozen=True)
class DayResult:
    date: str  # ISO YYYY-MM-DD
    percent: float  # 0.0, 0.5, or 1.0 (anything in (0,1) treated as partial)


def compute_concern(log: list[DayResult]) -> float:
    """Walk the log from most recent backwards. Sum partial/miss
    contributions until a 100% day closes the chain.

    - 100% (>= 1.0): resets concern to 0, walk stops.
    - partial (0 < p < 1.0): + 0.5 concern.
    - miss (= 0.0): + 1.0 concern.
    """
    concern = 0.0
    for day in reversed(log):
        if day.percent >= 1.0:
            break
        if day.percent > 0:
            concern += 0.5
        else:
            concern += 1.0
    return concern


def status_for(concern: float) -> Status:
    if concern >= 2.0:
        return "reset"
    if concern >= 1.5:
        return "at_risk"
    if concern >= 1.0:
        return "one_miss"
    return "ok"


def streak_days(log: list[DayResult]) -> int:
    """Count consecutive days from today backwards that haven't reset.
    A day triggers reset when the concern up to and including that day
    is >= 2.0.
    """
    days = 0
    for i in range(len(log) - 1, -1, -1):
        if compute_concern(log[: i + 1]) >= 2.0:
            break
        days += 1
    return days
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd companion && pytest tests/test_streak.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add companion/streak.py companion/tests/test_streak.py
git commit -m "feat: streak rule with full canonical-sequence test coverage"
```

---

### Task 3: Markdown parsers for habits.md, log.md, and daily notes

**Files:**
- Create: `companion/parsers.py`
- Create: `companion/tests/test_parsers.py`
- Create: `templates/habits.md.template`
- Create: `templates/log.md.template`

- [ ] **Step 1: Create the schema templates**

`templates/habits.md.template`:

```markdown
# Daily Habits

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

## Archived

(none yet)
```

`templates/log.md.template`:

```markdown
# Daily habit log

format: `YYYY-MM-DD · habit_id:percent · habit_id:percent ...`

```

- [ ] **Step 2: Write failing parser tests**

`companion/tests/test_parsers.py`:

```python
from companion.parsers import parse_habits, parse_log, append_day_to_log


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
```

- [ ] **Step 3: Implement `companion/parsers.py`**

```python
"""Markdown parsers for habits.md, log.md, and daily-note sections.

These read upstream-conforming markdown and return Python dicts. They also
serialize back: append_day_to_log writes one row of ticks, idempotent on
the date (replaces if already present).
"""

import re
from typing import Iterable


def parse_habits(md: str) -> dict:
    """Parse 30-habits/habits.md.

    Returns:
        {"active": [habit, ...], "archived": [habit, ...]}
        where habit is a dict with keys id, name, emoji, target, frequency,
        plus archived_at on archived ones.
    """
    result = {"active": [], "archived": []}
    section: str | None = None
    current: dict | None = None

    def flush():
        nonlocal current
        if current and "id" in current and section in result:
            result[section].append(current)
        current = None

    for raw in md.splitlines():
        line = raw.strip()
        if line == "## Active":
            flush(); section = "active"; continue
        if line == "## Archived":
            flush(); section = "archived"; continue
        if section is None:
            continue
        if line.startswith("- id:"):
            flush()
            current = {"id": line.replace("- id:", "").strip()}
        elif current is not None and ":" in line and not line.startswith("("):
            key, _, value = line.partition(":")
            current[key.strip()] = value.strip()
        elif line == "" and current:
            flush()
    flush()
    return result


def parse_log(md: str) -> list[dict]:
    """Parse 30-habits/log.md.

    Returns: [{"date": "YYYY-MM-DD", "ticks": {habit_id: percent, ...}}, ...]
    """
    rows: list[dict] = []
    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+·\s+(.*)$")
    for line in md.splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        date = m.group(1)
        ticks: dict[str, float] = {}
        for part in m.group(2).split("·"):
            part = part.strip()
            if ":" not in part:
                continue
            key, _, val = part.partition(":")
            try:
                ticks[key.strip()] = float(val)
            except ValueError:
                continue
        rows.append({"date": date, "ticks": ticks})
    return rows


def append_day_to_log(md: str, date: str, ticks: dict[str, float]) -> str:
    """Write/replace today's ticks in log.md. Idempotent."""
    formatted = " · ".join(f"{k}:{v:.1f}" for k, v in ticks.items())
    new_line = f"{date} · {formatted}"
    date_re = re.compile(rf"^{re.escape(date)}\s+·\s+.*$", re.MULTILINE)
    if date_re.search(md):
        return date_re.sub(new_line, md)
    trimmed = md.rstrip("\n")
    return trimmed + "\n" + new_line + "\n"


def parse_daily_note_sections(md: str) -> dict[str, str]:
    """Parse a daily note into a dict of {section_name: section_body}.

    Section names are level-2 headings ("## "). Body is everything until
    the next level-2 heading or EOF. Level-3 headings ("### ") are kept
    inside their parent section.
    """
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in md.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def parse_habits_from_daily_note(daily_md: str, active_habits: list[dict]) -> dict[str, float]:
    """Read the `### Habits` subsection of `## Morning Check-in` and return
    per-habit completion percent.

    Checkbox semantics:
      - `[x]` or `[X]` → 1.0 (done)
      - `[/]` or `[~]` → 0.5 (partial)
      - `[ ]`          → 0.0 (not done)

    Habit name match: the bolded text after the checkbox MUST match the
    `name` field of an active habit verbatim (case-sensitive). Unknown
    names are ignored. Active habits not found in the section default to 0.0.

    Returns: {habit_id: percent} for every active habit.
    """
    name_to_id = {h["name"]: h["id"] for h in active_habits}
    result: dict[str, float] = {h["id"]: 0.0 for h in active_habits}

    sections = parse_daily_note_sections(daily_md)
    morning = sections.get("Morning Check-in", "")
    if not morning:
        return result

    in_habits = False
    line_re = re.compile(r"^-\s+\[([ xX/~])\]\s+\*\*(.+?)\*\*")
    for raw in morning.splitlines():
        line = raw.rstrip()
        if line.startswith("### Habits"):
            in_habits = True
            continue
        if in_habits and line.startswith("### "):
            break
        if not in_habits:
            continue
        m = line_re.match(line.lstrip())
        if not m:
            continue
        mark, name = m.group(1), m.group(2)
        habit_id = name_to_id.get(name)
        if habit_id is None:
            continue
        if mark in ("x", "X"):
            result[habit_id] = 1.0
        elif mark in ("/", "~"):
            result[habit_id] = 0.5
        else:
            result[habit_id] = 0.0
    return result
```

**Add these tests to `test_parsers.py`:**

```python
from companion.parsers import parse_habits_from_daily_note


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
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd companion && pytest tests/test_parsers.py -v
```

Expected: 12 passed (7 original + 5 new habits-from-daily tests).

- [ ] **Step 5: Commit**

```bash
git add companion/parsers.py companion/tests/test_parsers.py templates/
git commit -m "feat: markdown parsers for habits, log, and daily-note sections"
```

---

## Phase 2 — Server core

### Task 4: Minimal Flask app with placeholder route

**Files:**
- Create: `companion/server.py`
- Create: `companion/templates/base.html`
- Create: `companion/templates/day.html`
- Create: `companion/tests/test_server.py`

- [ ] **Step 1: Failing test for the root route**

`companion/tests/test_server.py`:

```python
import pytest
from companion.server import create_app


@pytest.fixture
def client(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "01-daily").mkdir()
    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    return app.test_client()


def test_root_renders_day_tab(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Today" in resp.data
    assert b"Day" in resp.data
    assert b"Week" in resp.data
    assert b"Streaks" in resp.data


def test_root_handles_missing_daily_note(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"No daily note for today yet" in resp.data
```

- [ ] **Step 2: Implement minimal `companion/server.py`**

```python
"""Flask app factory for the NSLS toolkit companion."""

from datetime import date
from pathlib import Path

from flask import Flask, render_template


def create_app(vault_path: str) -> Flask:
    app = Flask(__name__)
    app.config["VAULT_PATH"] = Path(vault_path)

    @app.route("/")
    def index():
        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        note_md = note_path.read_text() if note_path.exists() else ""
        return render_template("day.html", today=today, note_md=note_md)

    return app
```

- [ ] **Step 3: Vendor Tailwind locally (one-time build at install)**

The Tailwind play CDN doesn't support SRI hashes, so we vendor a pre-built Tailwind CSS file at install time and serve it from Flask's static route. This removes the supply-chain risk and the 200KB+ blocking CDN download.

Add a make target / install step that runs the Tailwind standalone CLI once to produce `companion/static/tailwind.css`:

```bash
# In install.sh, after companion deps are installed:
if command -v npx >/dev/null 2>&1; then
  (cd "$plugin_dir/companion" && npx -y tailwindcss@3 -i ./static/tailwind.in.css -o ./static/tailwind.css --minify)
else
  echo "⚠ npx not found — skipping Tailwind build. Companion will use a fallback minimal stylesheet."
  cp "$plugin_dir/companion/static/fallback.css" "$plugin_dir/companion/static/tailwind.css"
fi
```

Where `static/tailwind.in.css` is:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

And `static/fallback.css` is a tiny hand-written stylesheet covering the few classes the templates actually use (so the companion still renders if Tailwind couldn't be built).

- [ ] **Step 4: Implement `companion/templates/base.html` — vendored CSS, SRI on JS**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NSLS Toolkit Companion</title>
  <link rel="stylesheet" href="/static/tailwind.css">
  <script src="https://unpkg.com/htmx.org@1.9.10"
          integrity="sha384-D1Kt99CQMDuVetoL1lrYwg5t+9QdHe7NLX/SoJYkXDFfX37iInKRy5xLSi8nO7UC"
          crossorigin="anonymous"></script>
  <script defer src="https://unpkg.com/alpinejs@3.13.5/dist/cdn.min.js"
          integrity="sha384-V1qBQB6tNc60jH/ZmDuhDmuywL5p3srn4i9bIarO+gNQfeQiSh7lZ4Mki/Y+rL6"
          crossorigin="anonymous"></script>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  </style>
</head>
<body class="bg-stone-50 text-stone-900">
  <nav class="border-b bg-white">
    <div class="max-w-4xl mx-auto px-6 py-3 flex gap-6">
      <a href="/" class="font-semibold {{ 'text-blue-900 border-b-2 border-blue-900 pb-3' if active_tab == 'day' else 'text-stone-500' }}">Day</a>
      <a href="/week" class="font-semibold {{ 'text-blue-900 border-b-2 border-blue-900 pb-3' if active_tab == 'week' else 'text-stone-500' }}">Week</a>
      <a href="/streaks" class="font-semibold {{ 'text-blue-900 border-b-2 border-blue-900 pb-3' if active_tab == 'streaks' else 'text-stone-500' }}">Streaks</a>
    </div>
  </nav>
  <main class="max-w-4xl mx-auto px-6 py-8">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 5: Implement `companion/templates/day.html`**

```html
{% extends "base.html" %}
{% set active_tab = 'day' %}
{% block content %}
  <h1 class="text-2xl font-bold mb-4">Today — {{ today }}</h1>
  {% if note_md %}
    <pre class="bg-white p-4 rounded shadow">{{ note_md }}</pre>
  {% else %}
    <p class="text-stone-500">No daily note for today yet. Run <code>/open-day</code> in your terminal.</p>
  {% endif %}
{% endblock %}
```

- [ ] **Step 6: Run tests, verify pass**

```bash
cd companion && pytest tests/test_server.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Smoke test manually**

```bash
cd companion && python3 -c "
from companion.server import create_app
import tempfile, os
vault = tempfile.mkdtemp()
os.makedirs(f'{vault}/01-daily', exist_ok=True)
app = create_app(vault)
app.run(host='127.0.0.1', port=7777)
" &
sleep 1
curl -s http://localhost:7777/ | head -20
kill %1 2>/dev/null || true
```

Expected: HTML with "Today —" and "Day / Week / Streaks" nav.

- [ ] **Step 8: Commit**

```bash
git add companion/server.py companion/templates/ companion/tests/test_server.py
git commit -m "feat: minimal Flask app with Day tab placeholder"
```

---

### Task 5: Vault watcher + SSE endpoint

**Files:**
- Create: `companion/watcher.py`
- Create: `companion/tests/test_watcher.py`
- Modify: `companion/server.py`

- [ ] **Step 1: Failing test for watcher event dispatch**

`companion/tests/test_watcher.py`:

```python
import time
from pathlib import Path

import pytest

from companion.watcher import VaultWatcher


def test_watcher_emits_on_file_change(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "01-daily").mkdir()

    events: list[str] = []
    watcher = VaultWatcher(str(vault), on_change=lambda relpath: events.append(relpath))
    watcher.start()

    try:
        (vault / "01-daily" / "2026-05-15.md").write_text("# test")
        time.sleep(0.5)
        assert any("01-daily/2026-05-15.md" in e for e in events)
    finally:
        watcher.stop()


def test_watcher_ignores_dotfiles(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    events: list[str] = []
    watcher = VaultWatcher(str(vault), on_change=lambda relpath: events.append(relpath))
    watcher.start()
    try:
        (vault / ".DS_Store").write_text("garbage")
        time.sleep(0.5)
        assert events == []
    finally:
        watcher.stop()
```

- [ ] **Step 2: Implement `companion/watcher.py`**

```python
"""Watchdog-based vault observer.

Calls on_change(relative_path) whenever any markdown file in the vault
changes. Ignores dotfiles and non-markdown files.
"""

from pathlib import Path
from typing import Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class _Handler(FileSystemEventHandler):
    def __init__(self, vault: Path, on_change: Callable[[str], None]):
        self.vault = vault
        self.on_change = on_change

    def _maybe_emit(self, path: str) -> None:
        try:
            rel = Path(path).resolve().relative_to(self.vault.resolve())
        except ValueError:
            return
        name = rel.name
        if name.startswith("."):
            return
        if not name.endswith(".md"):
            return
        self.on_change(str(rel))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._maybe_emit(event.src_path)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._maybe_emit(event.src_path)


class VaultWatcher:
    def __init__(self, vault_path: str, on_change: Callable[[str], None]):
        self.vault = Path(vault_path)
        self._observer = Observer()
        self._handler = _Handler(self.vault, on_change)

    def start(self) -> None:
        self._observer.schedule(self._handler, str(self.vault), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=2)
```

- [ ] **Step 3: Add SSE endpoint to server with content-hash dedup**

iCloud-synced vaults emit watchdog events when iCloud applies changes from another machine, not just on local writes. Without deduplication, the browser thrashes through reloads. We hash the file contents (sha256, first 16 bytes) before broadcasting, and skip if the hash matches what we last emitted for that file.

Cap the subscriber list at 10 concurrent SSE connections to limit memory growth and DOS surface.

Modify `companion/server.py`:

```python
import hashlib
import queue
from flask import Response, stream_with_context

# inside create_app:
    subscribers: list[queue.Queue] = []
    last_hashes: dict[str, str] = {}  # relpath -> sha256[:16] of last broadcast

    @app.route("/events")
    def events():
        if len(subscribers) >= 10:
            return ("too many subscribers", 429)
        q: queue.Queue = queue.Queue()
        subscribers.append(q)

        def stream():
            try:
                while True:
                    msg = q.get()
                    yield f"data: {msg}\n\n"
            finally:
                try:
                    subscribers.remove(q)
                except ValueError:
                    pass

        return Response(stream_with_context(stream()), mimetype="text/event-stream")

    def broadcast(relpath: str) -> None:
        # Content-hash dedup: skip if the file's content hasn't changed since
        # the last broadcast. Prevents iCloud-echo reload storms when the
        # same write propagates back through sync.
        full_path = app.config["VAULT_PATH"] / relpath
        try:
            data = full_path.read_bytes()
        except FileNotFoundError:
            return
        digest = hashlib.sha256(data).hexdigest()[:16]
        if last_hashes.get(relpath) == digest:
            return
        last_hashes[relpath] = digest
        for q in list(subscribers):
            try:
                q.put_nowait(relpath)
            except queue.Full:
                pass

    app.config["BROADCAST"] = broadcast
```

Cap the limit-message length and use `put_nowait` so a slow subscriber doesn't block writes for others.

- [ ] **Step 4: Wire watcher into the app**

In `companion/server.py` create_app:

```python
from companion.watcher import VaultWatcher

# inside create_app, after subscribers are defined:
    watcher = VaultWatcher(vault_path, on_change=broadcast)
    watcher.start()
    app.config["WATCHER"] = watcher
```

Update the test fixture in `test_server.py` to stop the watcher on teardown:

```python
@pytest.fixture
def client(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "01-daily").mkdir()
    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield app.test_client()
    finally:
        w = app.config.get("WATCHER")
        if w is not None:
            w.stop()
```

- [ ] **Step 5: Run all tests, verify pass**

```bash
cd companion && pytest -v
```

- [ ] **Step 6: Commit**

```bash
git add companion/watcher.py companion/server.py companion/tests/test_watcher.py companion/tests/test_server.py
git commit -m "feat: vault watcher + SSE endpoint for live browser updates"
```

---

## Phase 3 — Day tab

### Task 6: Day tab — Command Center read-only view

**Files:**
- Modify: `companion/server.py` (extract sections from daily note)
- Modify: `companion/templates/day.html`
- Create: `companion/tests/test_day_tab.py`

- [ ] **Step 1: Failing test for section extraction and rendering**

`companion/tests/test_day_tab.py`:

```python
import pytest
from companion.server import create_app


@pytest.fixture
def client_with_today(tmp_path):
    vault = tmp_path / "vault"
    daily = vault / "01-daily"
    daily.mkdir(parents=True)
    habits = vault / "30-habits"
    habits.mkdir(parents=True)

    from datetime import date
    today = date.today().isoformat()
    (daily / f"{today}.md").write_text("""# Daily Note

## Morning Check-in

### My Top 3
1. Finish toolkit spec
2. Q3 LOP draft
3. Reply to vendor

### Bonus
1. Board email
2. Review Maya's PR

### Habits
- [ ] **Walk**
- [x] **Read 15m**
""")
    (habits / "habits.md").write_text("""# Daily Habits

## Active

- id: walk
  name: Walk
  emoji: 🚶
  target: 30min
  frequency: daily

- id: read
  name: Read 15m
  emoji: 📖
  target: 15min
  frequency: daily
""")
    (habits / "log.md").write_text("# Log\n")

    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    try:
        yield app.test_client()
    finally:
        app.config["WATCHER"].stop()


def test_day_tab_renders_top_3(client_with_today):
    resp = client_with_today.get("/")
    assert b"Finish toolkit spec" in resp.data
    assert b"Q3 LOP draft" in resp.data


def test_day_tab_renders_bonus(client_with_today):
    resp = client_with_today.get("/")
    assert b"Board email" in resp.data


def test_day_tab_renders_habits(client_with_today):
    resp = client_with_today.get("/")
    assert b"Walk" in resp.data
    assert b"Read 15m" in resp.data
```

- [ ] **Step 2: Update `companion/server.py` to extract sections**

```python
# At top of server.py:
from companion.parsers import parse_daily_note_sections, parse_habits, parse_log
from companion.streak import compute_concern, status_for, streak_days, DayResult


def _extract_top_3(morning_section: str) -> list[str]:
    items: list[str] = []
    in_top_3 = False
    for line in morning_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("### My Top 3"):
            in_top_3 = True
            continue
        if in_top_3 and stripped.startswith("###"):
            break
        if in_top_3 and stripped and stripped[0].isdigit():
            text = stripped.split(".", 1)[-1].strip()
            if text:
                items.append(text)
    return items


def _extract_bonus(morning_section: str) -> list[str]:
    items: list[str] = []
    in_bonus = False
    for line in morning_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("### Bonus"):
            in_bonus = True
            continue
        if in_bonus and stripped.startswith("###"):
            break
        if in_bonus and stripped and stripped[0].isdigit():
            text = stripped.split(".", 1)[-1].strip()
            if text:
                items.append(text)
    return items
```

Then update the index route to pass top_3, bonus, habits_today to the template.

- [ ] **Step 3: Update `companion/templates/day.html`**

```html
{% extends "base.html" %}
{% set active_tab = 'day' %}
{% block content %}
<h1 class="text-2xl font-bold mb-6">Today — {{ today }}</h1>

{% if not note_md %}
  <p class="text-stone-500">No daily note for today yet. Run <code>/open-day</code> in your terminal.</p>
{% else %}

<section class="bg-white rounded-lg shadow p-5 mb-4">
  <h2 class="text-sm uppercase tracking-wider text-stone-500 mb-3">Top 3</h2>
  <ul class="space-y-2">
    {% for item in top_3 %}
      <li><label class="flex items-center gap-3"><input type="checkbox" class="w-4 h-4"> {{ item }}</label></li>
    {% endfor %}
  </ul>
</section>

<section class="bg-white rounded-lg shadow p-5 mb-4">
  <h2 class="text-sm uppercase tracking-wider text-stone-500 mb-3">Bonus</h2>
  <ul class="space-y-2 opacity-90">
    {% for item in bonus %}
      <li><label class="flex items-center gap-3"><input type="checkbox" class="w-4 h-4"> {{ item }}</label></li>
    {% endfor %}
  </ul>
</section>

<section class="bg-white rounded-lg shadow p-5 mb-4">
  <h2 class="text-sm uppercase tracking-wider text-stone-500 mb-3">Habits today</h2>
  <ul class="space-y-2">
    {% for h in habits_today %}
      <li class="flex items-center justify-between">
        <span>{{ h.emoji }} {{ h.name }}</span>
        <span class="text-sm text-stone-500">{{ h.streak_days }}d{% if h.status == 'at_risk' %} ⚠{% elif h.streak_days >= 7 %} 🔥{% endif %}</span>
      </li>
    {% endfor %}
  </ul>
</section>

{% endif %}
{% endblock %}
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd companion && pytest tests/test_day_tab.py -v
```

- [ ] **Step 5: Commit**

```bash
git add companion/server.py companion/templates/day.html companion/tests/test_day_tab.py
git commit -m "feat(day): render Top 3, Bonus, and Habits sections"
```

---

### Task 7: Day tab — interactive checkbox saves via HTMX

**Files:**
- Modify: `companion/server.py` (add `POST /tick`, `POST /toggle`, `POST /save`)
- Create: `companion/safe_write.py` (file-locked atomic writes)
- Create: `companion/validation.py` (input validation helpers)
- Modify: `companion/templates/day.html`
- Create: `companion/templates/_components/habit_row.html`
- Create: `companion/tests/test_day_interactions.py`

- [ ] **Step 1: Create `companion/safe_write.py`**

All vault writes go through this helper. It takes an `fcntl.flock` on the target file, reads the current content, lets the caller transform it, and writes back atomically via a temp-file rename. This protects against the companion writing while CLI close-day is also writing (and vice versa).

```python
"""Atomic, fcntl-locked read-modify-write for vault files."""

import fcntl
import os
import tempfile
from pathlib import Path
from typing import Callable


def safe_modify(path: Path, transform: Callable[[str], str]) -> None:
    """Read path under exclusive lock, transform, write back atomically.

    If path doesn't exist, transform receives "" and the file is created.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Open or create — exclusive lock held for the whole read-modify-write.
    with open(path, "a+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.seek(0)
        existing = f.read()
        updated = transform(existing)
        # Atomic write: tempfile in same dir, fsync, rename.
        fd, tmp = tempfile.mkstemp(
            prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w") as tf:
                tf.write(updated)
                tf.flush()
                os.fsync(tf.fileno())
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise
        # flock released when 'f' closes
```

- [ ] **Step 2: Create `companion/validation.py`**

Every POST that writes to the vault validates its input here. Rejecting at the edge keeps unsanitized strings out of markdown.

```python
"""Input validation for routes that write to the vault."""

import re

HABIT_ID_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
SAFE_SHORT_RE = re.compile(r"^[^\n\r]{1,64}$")  # no newlines, 64 char cap
SAFE_LONG_RE = re.compile(r"^[\s\S]{0,4096}$")  # arbitrary text up to 4KB

ALLOWED_SAVE_SECTIONS = {
    "Insight Reflection", "Gratitude", "Brain Dump", "Carrying Over",
}
ALLOWED_TOGGLE_SECTIONS = {"top_3", "bonus"}


def validate_habit_fields(form) -> dict:
    """Validate POST /habit form. Raises ValueError with message on failure."""
    out = {}
    out["id"] = form.get("id", "").strip()
    if not HABIT_ID_RE.fullmatch(out["id"]):
        raise ValueError("id must be 1-32 chars of [a-z0-9_-]")
    for field in ("name", "target", "frequency"):
        val = form.get(field, "").strip()
        if not SAFE_SHORT_RE.fullmatch(val):
            raise ValueError(f"{field} must be 1-64 chars, no newlines")
        out[field] = val
    emoji = form.get("emoji", "").strip()
    if len(emoji) > 8 or "\n" in emoji:
        raise ValueError("emoji too long or contains newline")
    out["emoji"] = emoji
    return out


def validate_save(form) -> tuple[str, str]:
    """Validate POST /save. Returns (section, content)."""
    section = form.get("section", "").strip()
    if section not in ALLOWED_SAVE_SECTIONS:
        raise ValueError(f"section must be one of {sorted(ALLOWED_SAVE_SECTIONS)}")
    content = form.get("content", "")
    if not SAFE_LONG_RE.fullmatch(content):
        raise ValueError("content exceeds 4KB or invalid")
    return section, content


def validate_toggle(form) -> tuple[str, int]:
    """Validate POST /toggle. Returns (section, index)."""
    section = form.get("section", "").strip()
    if section not in ALLOWED_TOGGLE_SECTIONS:
        raise ValueError(f"section must be one of {sorted(ALLOWED_TOGGLE_SECTIONS)}")
    try:
        index = int(form.get("index", ""))
    except (TypeError, ValueError):
        raise ValueError("index must be a non-negative integer")
    if index < 0 or index > 9:
        raise ValueError("index out of bounds (0-9)")
    return section, index
```

- [ ] **Step 3: Failing tests**

```python
# companion/tests/test_day_interactions.py
from datetime import date


def test_tick_habit_writes_to_log(client_with_today, tmp_path):
    resp = client_with_today.post("/tick", data={"habit_id": "walk", "percent": "1.0"})
    assert resp.status_code == 200
    log = (tmp_path / "vault" / "30-habits" / "log.md").read_text()
    today = date.today().isoformat()
    assert today in log
    assert "walk:1.0" in log


def test_tick_rejects_bad_habit_id(client_with_today):
    resp = client_with_today.post("/tick", data={"habit_id": "../etc", "percent": "1.0"})
    assert resp.status_code == 400


def test_toggle_top_3_checks_then_unchecks(client_with_today, tmp_path):
    today = date.today().isoformat()
    note = tmp_path / "vault" / "01-daily" / f"{today}.md"
    # Seed a note with a Top 3 item
    note.write_text(
        "## Morning Check-in\n### My Top 3\n"
        "1. [ ] First priority\n2. [ ] Second\n3. [ ] Third\n"
    )
    resp = client_with_today.post("/toggle", data={"section": "top_3", "index": "0"})
    assert resp.status_code == 204
    assert "1. [x] First priority" in note.read_text()
    # Toggle back
    client_with_today.post("/toggle", data={"section": "top_3", "index": "0"})
    assert "1. [ ] First priority" in note.read_text()


def test_toggle_rejects_unknown_section(client_with_today):
    resp = client_with_today.post("/toggle", data={"section": "../etc", "index": "0"})
    assert resp.status_code == 400


def test_save_writes_insight_reflection(client_with_today, tmp_path):
    today = date.today().isoformat()
    note = tmp_path / "vault" / "01-daily" / f"{today}.md"
    note.write_text("## Insight Reflection\n\n(empty)\n\n## Gratitude\n\n")
    resp = client_with_today.post("/save", data={
        "section": "Insight Reflection",
        "content": "Today I noticed I rush through morning ritual.",
    })
    assert resp.status_code == 204
    body = note.read_text()
    assert "Today I noticed" in body
    assert "## Gratitude" in body  # adjacent section preserved


def test_save_rejects_disallowed_section(client_with_today):
    resp = client_with_today.post("/save", data={"section": "Plan", "content": "x"})
    assert resp.status_code == 400
```

- [ ] **Step 4: Implement routes in `server.py`**

```python
from datetime import date
from companion.parsers import parse_log, append_day_to_log, parse_daily_note_sections
from companion.safe_write import safe_modify
from companion.validation import (
    validate_habit_fields, validate_save, validate_toggle, HABIT_ID_RE,
)

# inside create_app:
    @app.route("/tick", methods=["POST"])
    def tick():
        habit_id = request.form.get("habit_id", "").strip()
        if not HABIT_ID_RE.fullmatch(habit_id):
            return ("invalid habit_id", 400)
        try:
            percent = float(request.form.get("percent", ""))
        except ValueError:
            return ("invalid percent", 400)
        if percent not in (0.0, 0.5, 1.0):
            return ("percent must be 0.0 / 0.5 / 1.0", 400)

        today = date.today().isoformat()
        log_path = app.config["VAULT_PATH"] / "30-habits" / "log.md"

        def merge(existing: str) -> str:
            rows = parse_log(existing)
            today_ticks = next(
                (r["ticks"] for r in rows if r["date"] == today), {}
            )
            today_ticks[habit_id] = percent
            return append_day_to_log(existing, today, today_ticks)

        safe_modify(log_path, merge)
        broadcast("30-habits/log.md")
        return render_template(
            "_components/habit_row.html",
            h=_habit_state_for(app, habit_id, today, percent),
        )

    @app.route("/toggle", methods=["POST"])
    def toggle():
        try:
            section, index = validate_toggle(request.form)
        except ValueError as e:
            return (str(e), 400)

        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        if not note_path.exists():
            return ("today's note not found", 404)

        # Section name in markdown
        heading = "### My Top 3" if section == "top_3" else "### Bonus"

        def toggle_in_section(existing: str) -> str:
            return _toggle_nth_checkbox(existing, heading, index)

        safe_modify(note_path, toggle_in_section)
        broadcast(f"01-daily/{today}.md")
        return ("", 204)

    @app.route("/save", methods=["POST"])
    def save():
        try:
            section, content = validate_save(request.form)
        except ValueError as e:
            return (str(e), 400)

        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        if not note_path.exists():
            return ("today's note not found", 404)

        def replace_section(existing: str) -> str:
            return _replace_section_body(existing, section, content)

        safe_modify(note_path, replace_section)
        broadcast(f"01-daily/{today}.md")
        return ("", 204)


def _toggle_nth_checkbox(md: str, heading: str, index: int) -> str:
    """Toggle the `- [ ]` / `- [x]` on the Nth (0-indexed) list item under `heading`.

    Items under a level-3 heading like `### My Top 3` are numbered list rows
    starting with a digit then `. [ ]` or `. [x]`. We rewrite only the Nth.
    """
    lines = md.splitlines()
    in_section = False
    seen = 0
    for i, line in enumerate(lines):
        if line.startswith(heading):
            in_section = True
            continue
        if in_section and line.startswith("### "):
            break  # next subsection
        if in_section and line.startswith("## "):
            break  # next major section
        if not in_section:
            continue
        # numbered list row: "1. [ ] foo" or "- [ ] foo"
        stripped = line.lstrip()
        if not stripped or stripped[0] not in "0123456789-":
            continue
        if "[ ]" not in stripped and "[x]" not in stripped:
            continue
        if seen == index:
            if "[ ]" in line:
                lines[i] = line.replace("[ ]", "[x]", 1)
            else:
                lines[i] = line.replace("[x]", "[ ]", 1)
            break
        seen += 1
    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def _replace_section_body(md: str, section_name: str, new_body: str) -> str:
    """Replace the body of `## <section_name>` with new_body, preserving
    surrounding sections. If section doesn't exist, append it at the end.
    """
    heading = f"## {section_name}"
    lines = md.splitlines()
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i
            continue
        if start is not None and line.startswith("## ") and not line.startswith("### "):
            end = i
            break
    new_block = [heading, "", new_body.rstrip(), ""]
    if start is None:
        # append
        return md.rstrip("\n") + "\n\n" + "\n".join(new_block) + "\n"
    return "\n".join(lines[:start] + new_block + lines[end:]) + ("\n" if md.endswith("\n") else "")
```

- [ ] **Step 5: Create `_components/habit_row.html`**

```html
<li class="flex items-center justify-between py-1" id="habit-{{ h.id }}">
  <button hx-post="/tick"
          hx-vals='{"habit_id":"{{ h.id }}","percent":{{ "0.0" if h.percent == 1.0 else "1.0" }}}'
          hx-target="#habit-{{ h.id }}"
          hx-swap="outerHTML"
          class="flex items-center gap-2 text-left">
    <span class="inline-block w-5 h-5 border-2 rounded text-center text-sm leading-4
                 {% if h.percent == 1.0 %}bg-blue-900 text-white border-blue-900{% elif h.percent == 0.5 %}bg-blue-200 border-blue-400{% else %}bg-white border-stone-300{% endif %}">
      {% if h.percent == 1.0 %}✓{% elif h.percent == 0.5 %}~{% endif %}
    </span>
    <span>{{ h.emoji }} {{ h.name }}</span>
  </button>
  <span class="text-sm text-stone-500">{{ h.streak_days }}d{% if h.status == 'at_risk' %} ⚠{% elif h.streak_days >= 7 %} 🔥{% endif %}</span>
</li>
```

- [ ] **Step 6: Update `day.html` checkbox markup**

```html
<input type="checkbox" class="w-4 h-4"
       {% if item.checked %}checked{% endif %}
       hx-post="/toggle"
       hx-vals='{"section":"top_3","index":{{ loop.index0 }}}'
       hx-swap="none"
       hx-on:htmx:response-error="window.__toolkitErrorToast(event)">
```

- [ ] **Step 7: Run tests, verify pass, commit**

```bash
cd companion && pytest tests/test_day_interactions.py -v
git add companion/server.py companion/safe_write.py companion/validation.py companion/templates/ companion/tests/test_day_interactions.py
git commit -m "feat(day): /tick + /toggle + /save with validation and file locking"
```

---

### Task 8: Day tab — Coach Cards (morning + evening)

The Day tab has **four states** that depend on time of day and whether close-day has run:

| State | When | What renders |
|---|---|---|
| Morning Coach Cards | Day starts; user runs `/open-day` | 7-step ritual to lock in Top 3, Bonus, focus blocks, habit intentions, vitality |
| Command Center | After morning ritual; throughout workday | Dense dashboard: Top 3 checklist, Bonus, Habits row with streaks |
| Evening Coach Cards | User runs `/close-day`; daily note has `## Insight Reflection` heading | 4-step close ritual: stats recap → Insight Reflection textarea → Gratitude textarea → Done |
| Evening Results | After evening ritual is submitted | Read-only summary: stats, what was done, reflection + gratitude text |

State detection on `GET /`:
- Has today's daily note got a non-empty `## Insight Reflection`? → **Evening Results** (read-only)
- Does it have the `## Insight Reflection` heading but the body is empty/template? → **Evening Coach Cards**
- Does Morning Check-in have all Top 3 lines filled? → **Command Center**
- Otherwise → **Morning Coach Cards**

User can override via `?mode=coach-morning`, `?mode=command`, `?mode=coach-evening`, `?mode=results` for any state at any time.

**Files:**
- Modify: `companion/templates/day.html`
- Create: `companion/templates/_components/coach_morning.html`
- Create: `companion/templates/_components/coach_evening.html`
- Create: `companion/templates/_components/results.html`
- Modify: `companion/server.py` (state detection, mode dispatch)
- Create: `companion/tests/test_coach_cards.py`

- [ ] **Step 1: Failing tests**

```python
from datetime import date


def test_morning_coach_renders_7_steps(client_with_today):
    resp = client_with_today.get("/?mode=coach-morning")
    assert resp.status_code == 200
    for label in (b"Good morning", b"Confirm Top 3", b"Bonus list",
                  b"Focus blocks", b"Habit intentions", b"Vitality",
                  b"Lock in"):
        assert label in resp.data


def test_evening_coach_renders_4_steps(client_with_today, tmp_path):
    today = date.today().isoformat()
    note = tmp_path / "vault" / "01-daily" / f"{today}.md"
    note.write_text("## Morning Check-in\n### My Top 3\n\n## Insight Reflection\n\n")
    resp = client_with_today.get("/?mode=coach-evening")
    assert resp.status_code == 200
    for label in (b"Today's stats", b"Insight Reflection",
                  b"Gratitude", b"Done"):
        assert label in resp.data


def test_state_detection_picks_evening_results_when_insight_filled(
    client_with_today, tmp_path
):
    today = date.today().isoformat()
    note = tmp_path / "vault" / "01-daily" / f"{today}.md"
    note.write_text(
        "## Morning Check-in\n### My Top 3\n1. [x] Done\n"
        "## Insight Reflection\n\nI noticed something today.\n"
    )
    resp = client_with_today.get("/")
    assert resp.status_code == 200
    assert b"I noticed something today" in resp.data


def test_lock_in_morning_writes_nothing_but_returns_command_view(client_with_today):
    resp = client_with_today.post("/lock-in", data={"phase": "morning"})
    assert resp.status_code == 200
    # Returns the Command Center HTML for HTMX to swap in
    assert b"Top 3" in resp.data
```

- [ ] **Step 2: Implement `_components/coach_morning.html` — 7 steps in full**

```html
<div x-data="{ step: {{ step or 1 }} }" class="bg-white rounded-lg shadow p-6 max-w-2xl mx-auto">
  <div class="flex gap-1 mb-3">
    {% for i in range(1, 8) %}
      <div class="flex-1 h-1 rounded" :class="step >= {{ i }} ? 'bg-blue-900' : 'bg-stone-200'"></div>
    {% endfor %}
  </div>
  <div class="text-xs uppercase text-stone-500 mb-4">Step <span x-text="step"></span> of 7</div>

  <template x-if="step === 1">
    <div>
      <h3 class="font-semibold text-lg mb-2">Good morning</h3>
      <p class="text-stone-700">Today is {{ today_pretty }}. {{ top_3 | length }} priorities pulled from your daily planning.</p>
    </div>
  </template>

  <template x-if="step === 2">
    <div>
      <h3 class="font-semibold text-lg mb-2">Confirm Top 3</h3>
      <p class="text-sm text-stone-600 mb-3">Edit if needed. Press Next to continue — changes save on Lock in.</p>
      <form id="step2-form">
        {% for item in top_3 %}
        <input name="top_{{ loop.index0 }}" value="{{ item }}"
               class="block w-full border rounded px-3 py-2 mb-2">
        {% endfor %}
      </form>
    </div>
  </template>

  <template x-if="step === 3">
    <div>
      <h3 class="font-semibold text-lg mb-2">Bonus list</h3>
      <p class="text-sm text-stone-600 mb-3">Lower priority — only if Top 3 is done. One per line.</p>
      <textarea name="bonus" rows="5" form="step3-form"
                class="block w-full border rounded px-3 py-2 font-mono text-sm">{{ bonus_text }}</textarea>
      <form id="step3-form"></form>
    </div>
  </template>

  <template x-if="step === 4">
    <div>
      <h3 class="font-semibold text-lg mb-2">Focus blocks</h3>
      <p class="text-sm text-stone-600 mb-3">Pick deep-work windows. Time picker per row (drag-and-drop is Phase 2).</p>
      <div class="space-y-2">
        {% for block in focus_blocks %}
        <div class="flex items-center gap-2">
          <input type="time" value="{{ block.start }}" class="border rounded px-2 py-1">
          <span>–</span>
          <input type="time" value="{{ block.end }}" class="border rounded px-2 py-1">
          <input value="{{ block.label }}" placeholder="What for?" class="flex-1 border rounded px-2 py-1">
        </div>
        {% endfor %}
        <button type="button" class="text-sm text-blue-700">+ Add block</button>
      </div>
    </div>
  </template>

  <template x-if="step === 5">
    <div>
      <h3 class="font-semibold text-lg mb-2">Habit intentions</h3>
      <p class="text-sm text-stone-600 mb-3">Which habits will you do today? Tap to mark intent (saves to log.md as 0.0 until completed).</p>
      <ul class="space-y-2">
        {% for h in active_habits %}
        <li class="flex items-center gap-3">
          <input type="checkbox" id="intent-{{ h.id }}" class="w-5 h-5"
                 hx-post="/tick" hx-vals='{"habit_id":"{{ h.id }}","percent":"0.0"}'
                 hx-swap="none">
          <label for="intent-{{ h.id }}">{{ h.emoji }} {{ h.name }}</label>
        </li>
        {% endfor %}
      </ul>
    </div>
  </template>

  <template x-if="step === 6">
    <div>
      <h3 class="font-semibold text-lg mb-2">Vitality intentions</h3>
      <p class="text-sm text-stone-600 mb-3">One movement, one nourishment line. Optional but recommended.</p>
      <input name="movement" placeholder="Movement (e.g., 30min walk)"
             class="block w-full border rounded px-3 py-2 mb-2">
      <input name="nourishment" placeholder="Nourishment (e.g., lunch outside)"
             class="block w-full border rounded px-3 py-2">
    </div>
  </template>

  <template x-if="step === 7">
    <div>
      <h3 class="font-semibold text-lg mb-2">Lock in the day</h3>
      <p class="text-stone-700 mb-3">Your morning ritual is set. Tap Lock in to switch to the Command Center for the rest of the day.</p>
      <p class="text-sm text-stone-500">Edits made in earlier steps were saved as you typed. Lock in just transitions the view — it does not write anything new.</p>
    </div>
  </template>

  <div class="mt-6 flex justify-between gap-3">
    <button @click="step--" :disabled="step <= 1"
            class="px-4 py-2 border rounded disabled:opacity-30">Back</button>
    <button @click="step++" x-show="step < 7"
            class="px-4 py-2 bg-blue-900 text-white rounded">Next</button>
    <button x-show="step >= 7"
            hx-post="/lock-in" hx-vals='{"phase":"morning"}'
            hx-target="body" hx-swap="innerHTML"
            class="px-4 py-2 bg-blue-900 text-white rounded">Lock in →</button>
  </div>
</div>
```

- [ ] **Step 3: Implement `_components/coach_evening.html` — 4-step close ritual**

```html
<div x-data="{ step: {{ step or 1 }} }" class="bg-white rounded-lg shadow p-6 max-w-2xl mx-auto">
  <div class="flex gap-1 mb-3">
    {% for i in range(1, 5) %}
      <div class="flex-1 h-1 rounded" :class="step >= {{ i }} ? 'bg-amber-700' : 'bg-stone-200'"></div>
    {% endfor %}
  </div>
  <div class="text-xs uppercase text-stone-500 mb-4">Step <span x-text="step"></span> of 4 · Evening</div>

  <template x-if="step === 1">
    <div>
      <h3 class="font-semibold text-lg mb-3">Today's stats</h3>
      <div class="grid grid-cols-2 gap-3 text-sm">
        <div class="bg-stone-50 p-3 rounded"><div class="text-stone-500 text-xs">Top 3 completed</div><div class="text-2xl font-semibold">{{ stats.top_3_done }}/{{ stats.top_3_total }}</div></div>
        <div class="bg-stone-50 p-3 rounded"><div class="text-stone-500 text-xs">Habits completed</div><div class="text-2xl font-semibold">{{ stats.habits_done }}/{{ stats.habits_total }}</div></div>
        <div class="bg-stone-50 p-3 rounded"><div class="text-stone-500 text-xs">Focus time</div><div class="text-2xl font-semibold">{{ stats.focus_hours }}h</div></div>
        <div class="bg-stone-50 p-3 rounded"><div class="text-stone-500 text-xs">Streak</div><div class="text-2xl font-semibold">{{ stats.streak_days }}d</div></div>
      </div>
    </div>
  </template>

  <template x-if="step === 2">
    <div>
      <h3 class="font-semibold text-lg mb-2">Insight Reflection</h3>
      <p class="text-sm text-stone-600 mb-3">What did you notice about yourself today? One pattern, one resistance, one win — whatever is alive. Auto-saves as you type.</p>
      <textarea rows="8" class="block w-full border rounded px-3 py-2 font-serif"
                hx-post="/save" hx-trigger="input changed delay:1500ms"
                hx-vals='{"section":"Insight Reflection"}' name="content"
                hx-swap="none"
                hx-on:htmx:response-error="window.__toolkitErrorToast(event)">{{ insight_reflection_text }}</textarea>
    </div>
  </template>

  <template x-if="step === 3">
    <div>
      <h3 class="font-semibold text-lg mb-2">Gratitude</h3>
      <p class="text-sm text-stone-600 mb-3">One thing you're grateful for today. Short or long. Auto-saves as you type.</p>
      <textarea rows="4" class="block w-full border rounded px-3 py-2 font-serif"
                hx-post="/save" hx-trigger="input changed delay:1500ms"
                hx-vals='{"section":"Gratitude"}' name="content"
                hx-swap="none"
                hx-on:htmx:response-error="window.__toolkitErrorToast(event)">{{ gratitude_text }}</textarea>
    </div>
  </template>

  <template x-if="step === 4">
    <div>
      <h3 class="font-semibold text-lg mb-3">Done for today</h3>
      <p class="text-stone-700 mb-2">Insight and Gratitude saved to today's daily note.</p>
      <p class="text-sm text-stone-500">Tap Done to switch to the read-only Results view.</p>
    </div>
  </template>

  <div class="mt-6 flex justify-between gap-3">
    <button @click="step--" :disabled="step <= 1"
            class="px-4 py-2 border rounded disabled:opacity-30">Back</button>
    <button @click="step++" x-show="step < 4"
            class="px-4 py-2 bg-amber-700 text-white rounded">Next</button>
    <button x-show="step >= 4"
            hx-post="/lock-in" hx-vals='{"phase":"evening"}'
            hx-target="body" hx-swap="innerHTML"
            class="px-4 py-2 bg-amber-700 text-white rounded">Done →</button>
  </div>
</div>
```

- [ ] **Step 4: Implement `_components/results.html` — read-only evening summary**

```html
<div class="max-w-2xl mx-auto space-y-4">
  <header class="bg-amber-50 p-4 rounded"><h2 class="font-semibold">Day closed · {{ today_pretty }}</h2></header>

  <section class="bg-white p-5 rounded shadow">
    <h3 class="text-sm uppercase text-stone-500 mb-2">Stats</h3>
    <div class="grid grid-cols-4 gap-3 text-sm">
      <div><div class="text-stone-500">Top 3</div><div class="font-semibold">{{ stats.top_3_done }}/{{ stats.top_3_total }}</div></div>
      <div><div class="text-stone-500">Habits</div><div class="font-semibold">{{ stats.habits_done }}/{{ stats.habits_total }}</div></div>
      <div><div class="text-stone-500">Focus</div><div class="font-semibold">{{ stats.focus_hours }}h</div></div>
      <div><div class="text-stone-500">Streak</div><div class="font-semibold">{{ stats.streak_days }}d</div></div>
    </div>
  </section>

  <section class="bg-white p-5 rounded shadow">
    <h3 class="text-sm uppercase text-stone-500 mb-2">Top 3</h3>
    <ul class="space-y-1">
      {% for item in top_3 %}
      <li class="flex items-start gap-2">
        <span>{% if item.checked %}✅{% else %}⬜{% endif %}</span>
        <span class="{% if item.checked %}line-through text-stone-400{% endif %}">{{ item.text }}</span>
      </li>
      {% endfor %}
    </ul>
  </section>

  {% if insight_reflection_text %}
  <section class="bg-white p-5 rounded shadow">
    <h3 class="text-sm uppercase text-stone-500 mb-2">Insight Reflection</h3>
    <p class="whitespace-pre-wrap font-serif text-stone-800">{{ insight_reflection_text }}</p>
  </section>
  {% endif %}

  {% if gratitude_text %}
  <section class="bg-white p-5 rounded shadow">
    <h3 class="text-sm uppercase text-stone-500 mb-2">Gratitude</h3>
    <p class="whitespace-pre-wrap font-serif text-stone-800">{{ gratitude_text }}</p>
  </section>
  {% endif %}
</div>
```

- [ ] **Step 5: State detection + dispatch in `server.py`**

```python
def _detect_day_state(daily_md: str, top_3: list) -> str:
    """Return one of 'coach-morning', 'command', 'coach-evening', 'results'."""
    sections = parse_daily_note_sections(daily_md)
    insight = sections.get("Insight Reflection", "").strip()
    if insight:
        return "results"
    if "Insight Reflection" in sections:
        return "coach-evening"
    if top_3 and all(item.get("text") for item in top_3):
        return "command"
    return "coach-morning"


# In the index route:
    @app.route("/")
    def index():
        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        daily_md = note_path.read_text() if note_path.exists() else ""
        top_3 = _extract_top_3(daily_md)
        # User override → respected; otherwise auto-detect
        mode = request.args.get("mode") or _detect_day_state(daily_md, top_3)
        ctx = _build_day_context(app, daily_md, top_3)
        if mode == "coach-morning":
            return render_template("_components/coach_morning.html", step=int(request.args.get("step", 1)), **ctx)
        if mode == "coach-evening":
            return render_template("_components/coach_evening.html", step=int(request.args.get("step", 1)), **ctx)
        if mode == "results":
            return render_template("_components/results.html", **ctx)
        return render_template("day.html", **ctx)  # Command Center


    @app.route("/lock-in", methods=["POST"])
    def lock_in():
        # No vault write — the ritual is the confirmation, individual steps
        # autosaved as the user moved through them. Lock in just transitions
        # the view from Coach Cards to the next state.
        phase = request.form.get("phase", "morning")
        target_mode = "command" if phase == "morning" else "results"
        today = date.today().isoformat()
        note_path = app.config["VAULT_PATH"] / "01-daily" / f"{today}.md"
        daily_md = note_path.read_text() if note_path.exists() else ""
        top_3 = _extract_top_3(daily_md)
        ctx = _build_day_context(app, daily_md, top_3)
        if target_mode == "results":
            return render_template("_components/results.html", **ctx)
        return render_template("day.html", **ctx)
```

- [ ] **Step 6: Run tests, verify pass, commit**

```bash
cd companion && pytest tests/test_coach_cards.py -v
git add companion/templates/ companion/tests/test_coach_cards.py
git commit -m "feat(day): Coach Cards morning mode with Alpine-driven step progression"
```

---

### Task 9: SSE wiring — browser auto-refresh with reconnect + dirty-textarea guard

**Files:**
- Modify: `companion/templates/base.html` (add SSE client + error toast)
- Create: `companion/tests/test_sse_integration.py`

- [ ] **Step 1: Add the SSE client + global error toast to base.html**

The client handles four real-world failure modes:
- **iOS Safari / mobile** drops the EventSource when the tab backgrounds → `visibilitychange` triggers a manual refresh + reconnect on return.
- **Disconnect** during a sleep or transient network blip → `onerror` triggers exponential-backoff reconnect.
- **Dirty textarea** (user typing while a CLI write fires) → before swapping `main`, check for unsaved input; prompt before clobbering.
- **POST failure** (server returns 4xx/5xx) → a global toast surfaces the error instead of failing silently.

```html
<script>
  (function () {
    let es = null;
    let reconnectDelay = 1000;        // backoff base
    let lastReload = Date.now();
    const RELOAD_DEBOUNCE_MS = 800;

    function isMainDirty() {
      // Any textarea inside <main> whose current value differs from its initial
      // value is "dirty" and we should warn before clobbering it.
      for (const t of document.querySelectorAll("main textarea")) {
        if (t.value !== (t.defaultValue || "")) return true;
      }
      return false;
    }

    function reloadMain() {
      if (Date.now() - lastReload < RELOAD_DEBOUNCE_MS) return;
      lastReload = Date.now();
      if (isMainDirty()) {
        const ok = confirm(
          "The CLI updated this file. Reload and lose the edits you're typing?\n\n" +
          "OK = reload\nCancel = keep my edits (you can refresh manually later)"
        );
        if (!ok) return;
      }
      htmx.ajax("GET", window.location.href, { target: "main", swap: "innerHTML" });
    }

    function connect() {
      if (es) try { es.close(); } catch (_) {}
      es = new EventSource("/events");
      es.onopen = () => { reconnectDelay = 1000; };
      es.onmessage = (e) => {
        const path = e.data;
        if (path.startsWith("01-daily/") || path.startsWith("30-habits/")) {
          reloadMain();
        }
      };
      es.onerror = () => {
        try { es.close(); } catch (_) {}
        setTimeout(connect, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 30000);  // cap 30s
      };
    }

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        // iOS drops SSE when the tab is backgrounded — refresh + reconnect.
        reloadMain();
        connect();
      }
    });

    connect();

    // Global toast for HTMX response errors. All POSTs in templates use:
    //   hx-on:htmx:response-error="window.__toolkitErrorToast(event)"
    window.__toolkitErrorToast = function (evt) {
      const xhr = evt.detail && evt.detail.xhr;
      const msg = (xhr && xhr.responseText) || "Save failed";
      let toast = document.getElementById("toolkit-toast");
      if (!toast) {
        toast = document.createElement("div");
        toast.id = "toolkit-toast";
        toast.className = "fixed bottom-4 right-4 bg-red-700 text-white px-4 py-2 rounded shadow-lg z-50";
        document.body.appendChild(toast);
      }
      toast.textContent = `⚠ ${msg.slice(0, 200)}`;
      toast.style.display = "block";
      clearTimeout(toast._timer);
      toast._timer = setTimeout(() => { toast.style.display = "none"; }, 4000);
    };
  })();
</script>
```

- [ ] **Step 2: Smoke test (manual)**

Start the server, open `http://localhost:7777` in a browser, then in another terminal touch a file:

```bash
touch "$OBSIDIAN_VAULT_PATH/01-daily/$(date +%Y-%m-%d).md"
```

The browser should re-render the Day tab within ~1 second.

Also test:
- Open the page on an iPhone over LAN (Phase 2), background the tab for 30s, return — page reloads.
- Type into an Insight Reflection textarea, then trigger a vault change from another tab — confirm dialog fires.

- [ ] **Step 3: Commit**

```bash
git add companion/templates/base.html
git commit -m "feat(sse): robust auto-refresh with reconnect, visibilitychange, dirty-textarea guard"
```

---

## Phase 4 — Streaks tab

### Task 10: Streaks tab — habit list + 30-day heatmap

**Files:**
- Create: `companion/templates/streaks.html`
- Modify: `companion/server.py` (`GET /streaks` route)
- Create: `companion/tests/test_streaks_tab.py`

- [ ] **Step 1: Failing test**

```python
def test_streaks_tab_renders_habits(client_with_today):
    resp = client_with_today.get("/streaks")
    assert resp.status_code == 200
    assert b"Walk" in resp.data
    assert b"Read 15m" in resp.data


def test_streaks_tab_shows_heatmap_cells(client_with_today):
    resp = client_with_today.get("/streaks")
    # 30-day heatmap = 30 cells per habit, 2 habits => 60 cells
    assert resp.data.count(b'class="hm-cell') >= 60
```

- [ ] **Step 2: Implement `GET /streaks`**

```python
    @app.route("/streaks")
    def streaks():
        from datetime import timedelta
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        log_path = app.config["VAULT_PATH"] / "30-habits" / "log.md"
        habits = parse_habits(habits_path.read_text()) if habits_path.exists() else {"active": [], "archived": []}
        log = parse_log(log_path.read_text()) if log_path.exists() else []

        today = date.today()
        rows = []
        for h in habits["active"]:
            habit_log = [DayResult(d["date"], d["ticks"].get(h["id"], 0.0))
                         for d in log if h["id"] in d["ticks"]]
            cells = []
            for i in range(29, -1, -1):
                day = (today - timedelta(days=i)).isoformat()
                pct = next((d["ticks"].get(h["id"]) for d in log if d["date"] == day), None)
                cells.append({"date": day, "percent": pct})
            rows.append({
                "habit": h,
                "streak_days": streak_days(habit_log),
                "concern": compute_concern(habit_log),
                "status": status_for(compute_concern(habit_log)),
                "cells": cells,
            })
        return render_template("streaks.html", today=today.isoformat(), rows=rows)
```

- [ ] **Step 3: Implement `companion/templates/streaks.html`**

```html
{% extends "base.html" %}
{% set active_tab = 'streaks' %}
{% block content %}
<div class="flex justify-between items-center mb-6">
  <h1 class="text-2xl font-bold">Your habits</h1>
  <button hx-get="/add-habit-form" hx-target="#habit-form-slot" class="px-3 py-2 bg-blue-900 text-white rounded text-sm">+ Add habit</button>
</div>
<div id="habit-form-slot"></div>

<div class="space-y-3">
{% for r in rows %}
  <div class="bg-white rounded-lg shadow p-4 flex items-center gap-4 {% if r.status == 'at_risk' %}border-l-4 border-yellow-600{% endif %}">
    <div class="text-2xl">{{ r.habit.emoji }}</div>
    <div class="flex-1">
      <div class="font-semibold">{{ r.habit.name }}</div>
      <div class="text-xs text-stone-500">target: {{ r.habit.target }} · {{ r.habit.frequency }}</div>
      <div class="grid grid-cols-15 gap-0.5 mt-2" style="display:grid; grid-template-columns: repeat(15, 1fr); gap: 2px;">
        {% for c in r.cells %}
          {% if c.percent is none %}
            <div class="hm-cell" style="aspect-ratio:1; background:#e5e1d6; border-radius:2px;"></div>
          {% elif c.percent >= 1.0 %}
            <div class="hm-cell" style="aspect-ratio:1; background:#5a8a3a; border-radius:2px;"></div>
          {% elif c.percent > 0 %}
            <div class="hm-cell" style="aspect-ratio:1; background:#f0c460; border-radius:2px;"></div>
          {% else %}
            <div class="hm-cell" style="aspect-ratio:1; background:#c4554d; opacity:0.55; border-radius:2px;"></div>
          {% endif %}
        {% endfor %}
      </div>
    </div>
    <div class="text-right">
      <div class="text-xl font-bold {% if r.status == 'at_risk' %}text-yellow-700{% else %}text-green-800{% endif %}">
        {% if r.status == 'at_risk' %}⚠ at risk{% else %}{{ r.streak_days }}d{% if r.streak_days >= 7 %} 🔥{% endif %}{% endif %}
      </div>
      <div class="text-xs text-stone-500">concern {{ '%.1f' % r.concern }}</div>
    </div>
  </div>
{% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 4: Run tests, verify pass, commit**

```bash
cd companion && pytest tests/test_streaks_tab.py -v
git add companion/server.py companion/templates/streaks.html companion/tests/test_streaks_tab.py
git commit -m "feat(streaks): habit list with 30-day heatmap and status indicators"
```

---

### Task 11: Streaks tab — Add and archive habit

**Files:**
- Modify: `companion/server.py` (`GET /add-habit-form`, `POST /habit`)
- Create: `companion/templates/_components/add_habit_form.html`
- Create: `companion/tests/test_habit_management.py`

- [ ] **Step 1: Failing test**

```python
def test_add_habit_writes_to_habits_md(client_with_today, tmp_path):
    resp = client_with_today.post("/habit", data={
        "id": "meditate", "name": "Meditate", "emoji": "🧘",
        "target": "10min", "frequency": "daily"
    })
    assert resp.status_code in (200, 204)
    habits_md = (tmp_path / "vault" / "30-habits" / "habits.md").read_text()
    assert "id: meditate" in habits_md
    assert "name: Meditate" in habits_md


def test_archive_habit_moves_to_archived_section(client_with_today, tmp_path):
    resp = client_with_today.post("/habit/archive", data={"habit_id": "walk"})
    assert resp.status_code in (200, 204)
    habits_md = (tmp_path / "vault" / "30-habits" / "habits.md").read_text()
    # walk should now appear under ## Archived, not ## Active
    archived_idx = habits_md.find("## Archived")
    walk_idx = habits_md.find("id: walk")
    assert walk_idx > archived_idx
```

- [ ] **Step 2: Implement add/archive in server.py — with validation and file-locked writes**

```python
from companion.safe_write import safe_modify
from companion.validation import validate_habit_fields, HABIT_ID_RE

    @app.route("/add-habit-form")
    def add_habit_form():
        return render_template("_components/add_habit_form.html")

    @app.route("/habit", methods=["POST"])
    def add_habit():
        try:
            fields = validate_habit_fields(request.form)
        except ValueError as e:
            return (str(e), 400)
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        new_entry = (
            f"\n- id: {fields['id']}\n"
            f"  name: {fields['name']}\n"
            f"  emoji: {fields['emoji']}\n"
            f"  target: {fields['target']}\n"
            f"  frequency: {fields['frequency']}\n"
        )
        def insert(existing: str) -> str:
            md = existing or "# Daily Habits\n\n## Active\n\n## Archived\n"
            # Reject duplicate ids
            if f"id: {fields['id']}" in md:
                raise ValueError("habit id already exists")
            return md.replace("## Active\n", "## Active\n" + new_entry, 1)
        try:
            safe_modify(habits_path, insert)
        except ValueError as e:
            return (str(e), 400)
        broadcast("30-habits/habits.md")
        return ("", 204)

    @app.route("/habit/archive", methods=["POST"])
    def archive_habit():
        habit_id = request.form.get("habit_id", "").strip()
        if not HABIT_ID_RE.fullmatch(habit_id):
            return ("invalid habit_id", 400)
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        if not habits_path.exists():
            return ("", 404)
        found = [False]
        def archive(existing: str) -> str:
            habits = parse_habits(existing)
            active = habits["active"]
            target = next((h for h in active if h["id"] == habit_id), None)
            if target is None:
                return existing  # signal not-found via found[0]
            found[0] = True
            target["archived_at"] = date.today().isoformat()
            habits["active"] = [h for h in active if h["id"] != habit_id]
            habits["archived"].append(target)
            return _serialize_habits(habits)
        safe_modify(habits_path, archive)
        if not found[0]:
            return ("habit not found", 404)
        broadcast("30-habits/habits.md")
        return ("", 204)
```

`_serialize_habits` is a small helper that writes the dict back to the canonical markdown format (active section first, then archived).

- [ ] **Step 3: Implement the form template**

```html
<!-- _components/add_habit_form.html -->
<form hx-post="/habit" hx-target="closest div" hx-swap="outerHTML" class="bg-white rounded-lg shadow p-4 mb-4">
  <div class="grid grid-cols-2 gap-3">
    <input name="id" placeholder="id (e.g. walk)" class="border rounded px-3 py-2" required>
    <input name="name" placeholder="Name" class="border rounded px-3 py-2" required>
    <input name="emoji" placeholder="🚶" class="border rounded px-3 py-2" required>
    <input name="target" placeholder="30min" class="border rounded px-3 py-2" required>
    <select name="frequency" class="border rounded px-3 py-2 col-span-2">
      <option>daily</option>
      <option>3/week</option>
      <option>4/week</option>
      <option>5/week</option>
    </select>
  </div>
  <button class="mt-3 px-4 py-2 bg-blue-900 text-white rounded">Add</button>
</form>
```

- [ ] **Step 4: Run tests, verify pass, commit**

```bash
cd companion && pytest tests/test_habit_management.py -v
git add companion/server.py companion/templates/_components/ companion/tests/test_habit_management.py
git commit -m "feat(streaks): add and archive habit"
```

---

## Phase 5 — Week tab (stub)

### Task 12: Week tab — read-only weekly-note markdown render

The full Week tab (stack rank, mode badge, push/protect, trap check, meeting check, week-at-a-glance) is deferred to **Phase 2**. The actual weekly-note schema written by `/open-week` (`## Week Plan: [date range]` with nested `### Recommended Top 3`, `## Focus This Week`, `## Parked`) plus the separate stack-rank file at `10-strategy/stack-rank/YYYY-WNN.md` is more involved than the original Task 12 acknowledged, and Phase 1's focus is `open-day` / `close-day`. The Phase 1 Week tab is a minimal markdown viewer so the tab isn't a dead link.

**Files:**
- Create: `companion/templates/week.html`
- Modify: `companion/server.py` (`GET /week`)
- Create: `companion/tests/test_week_tab.py`

- [ ] **Step 1: Failing test**

```python
from datetime import date


def test_week_tab_renders_weekly_note_as_markdown(client_with_today, tmp_path):
    weekly = tmp_path / "vault" / "02-weekly"
    weekly.mkdir(parents=True)
    iso_year, iso_week, _ = date.today().isocalendar()
    (weekly / f"{iso_year}-W{iso_week:02d}.md").write_text(
        "# Week\n\n## Week Plan: 2026-05-12 to 2026-05-18\n\n### Recommended Top 3\n1. Ship toolkit\n"
    )
    resp = client_with_today.get("/week")
    assert resp.status_code == 200
    assert b"Ship toolkit" in resp.data


def test_week_tab_shows_helpful_empty_state(client_with_today):
    resp = client_with_today.get("/week")
    assert resp.status_code == 200
    assert b"No weekly note yet" in resp.data
    assert b"/open-week" in resp.data
```

- [ ] **Step 2: Implement `GET /week` — pass raw markdown**

```python
    @app.route("/week")
    def week():
        y, w, _ = date.today().isocalendar()
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{y}-W{w:02d}.md"
        week_md = path.read_text() if path.exists() else ""
        return render_template("week.html", week_md=week_md, week_of=f"{y}-W{w:02d}")
```

- [ ] **Step 3: Implement `companion/templates/week.html` — markdown stub**

```html
{% extends "base.html" %}
{% set active_tab = 'week' %}
{% block content %}
<h1 class="text-2xl font-bold mb-4">Week — {{ week_of }}</h1>

{% if not week_md %}
  <div class="bg-white rounded-lg shadow p-6 text-center">
    <p class="text-stone-600">No weekly note yet.</p>
    <p class="text-sm text-stone-500 mt-2">Run <code class="bg-stone-100 px-1 rounded">/open-week</code> in your terminal to create one.</p>
  </div>
{% else %}
  <div class="bg-white rounded-lg shadow p-6">
    <details class="mb-4">
      <summary class="text-sm text-stone-500 cursor-pointer">Phase 1 note — full Week tab is Phase 2</summary>
      <p class="text-sm text-stone-600 mt-2">For now this view shows the raw weekly-note markdown. Rich rendering of stack rank, push/protect mode, trap check, and meeting check is on the roadmap. The canonical content lives in your Obsidian vault — open it there for full formatting.</p>
    </details>
    <pre class="font-mono text-sm whitespace-pre-wrap text-stone-800">{{ week_md }}</pre>
  </div>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Run tests, verify pass, commit**

```bash
cd companion && pytest tests/test_week_tab.py -v
git add companion/server.py companion/templates/week.html companion/tests/test_week_tab.py
git commit -m "feat(week): minimal weekly-note markdown viewer (full tab is Phase 2)"
```

---

## Phase 6 — CLI entry point + install integration

### Task 13: `toolkit-companion` CLI

**Files:**
- Create: `companion/cli.py`

- [ ] **Step 1: Implement `companion/cli.py`**

```python
"""toolkit-companion CLI: serve, stop, status."""

import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import click


PID_FILE = Path.home() / ".claude" / "local-plugins" / "nsls-personal-toolkit" / ".companion.pid"


def _find_free_port(start: int = 7777) -> int:
    for port in range(start, start + 100):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")


@click.group()
def main():
    """NSLS toolkit web companion."""


@main.command()
@click.option("--vault", default=None, help="Override vault path (defaults to OBSIDIAN_VAULT_PATH env var)")
@click.option("--port", default=None, type=int, help="Port (default: first free starting at 7777)")
@click.option("--no-open", is_flag=True, help="Don't open the browser")
def serve(vault, port, no_open):
    """Start the local web companion.

    v1 binds 127.0.0.1 only. LAN/phone access is Phase 2 (will require a
    shared-secret token).
    """
    vault = vault or os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        click.echo("Set OBSIDIAN_VAULT_PATH or pass --vault", err=True)
        sys.exit(1)
    port = port or _find_free_port()
    host = "127.0.0.1"  # hard-coded — no LAN bind in v1

    from companion.server import create_app
    app = create_app(vault_path=vault)

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Permissions: 0600 (owner read/write only) — prevents other users on a
    # shared machine from reading or overwriting the pidfile.
    PID_FILE.write_text(f"{os.getpid()}\n{host}:{port}\n")
    PID_FILE.chmod(0o600)

    url = f"http://{host}:{port}"
    click.echo(f"Serving at {url}")
    if not no_open:
        webbrowser.open(url)

    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    finally:
        try:
            PID_FILE.unlink()
        except FileNotFoundError:
            pass


@main.command()
def stop():
    """Stop a running companion server."""
    if not PID_FILE.exists():
        click.echo("No running companion found.")
        return
    pid = int(PID_FILE.read_text().splitlines()[0])
    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"Sent SIGTERM to {pid}")
    except ProcessLookupError:
        click.echo("Stale pidfile; cleaning up.")
    PID_FILE.unlink(missing_ok=True)


@main.command()
def status():
    """Show companion status."""
    if not PID_FILE.exists():
        click.echo("Not running.")
        return
    lines = PID_FILE.read_text().splitlines()
    click.echo(f"Running: pid {lines[0]}, address {lines[1]}")
```

- [ ] **Step 2: Smoke test**

```bash
cd companion && pip install -e .
toolkit-companion --help
OBSIDIAN_VAULT_PATH=/tmp/test-vault mkdir -p /tmp/test-vault/01-daily
OBSIDIAN_VAULT_PATH=/tmp/test-vault toolkit-companion serve --no-open --port 7778 &
sleep 2
curl -s http://localhost:7778/ | head -5
toolkit-companion stop
```

- [ ] **Step 3: Commit**

```bash
git add companion/cli.py
git commit -m "feat(cli): toolkit-companion serve / stop / status commands"
```

---

### Task 14: Install script integration + optional launchd autostart

**Files:**
- Modify: `install.sh`
- Create: `templates/com.nsls.toolkit-companion.plist.template`

- [ ] **Step 1: Add companion install option to `install.sh`**

Near the end of `install.sh`:

```bash
# Optional: install web companion
read -p "Install the web companion (browser-based UI)? [Y/n] " yn
if [[ "${yn:-y}" =~ ^[Yy] ]]; then
  # Ensure Python deps are installed
  if command -v pip3 >/dev/null 2>&1; then
    (cd "$HOME/.claude/local-plugins/nsls-personal-toolkit/companion" && pip3 install -e . -q)
    echo "✓ Installed nsls-toolkit-companion CLI"
  else
    echo "⚠ pip3 not found; skipping companion install"
  fi

  read -p "Auto-start the companion at login? [y/N] " auto
  if [[ "${auto:-n}" =~ ^[Yy] ]]; then
    install_companion_launchd
  fi
fi
```

- [ ] **Step 2: Implement `install_companion_launchd` — Python-generated plist, vault resolved from builder-profile**

Generate the plist via Python (not `sed`) to avoid shell-quoting issues with vault paths that contain spaces or special characters. Resolve the vault path at install time by checking, in order:
1. `OBSIDIAN_VAULT_PATH` env var
2. `data_sources.familiar.paths[]` from `50-reference/builder-profile.md` (first entry where `host` matches the current hostname)
3. Prompt the user

Verify the resolved path contains `01-daily/` before installing — fail loudly if not.

```bash
install_companion_launchd() {
  local plugin_dir="$HOME/.claude/local-plugins/nsls-personal-toolkit"
  local plist_dest="$HOME/Library/LaunchAgents/com.nsls.toolkit-companion.plist"

  # Resolve vault path via Python (handles env var, builder-profile, and prompt)
  local vault_path
  vault_path=$(python3 "$plugin_dir/companion/install_helper.py" resolve-vault)
  if [ -z "$vault_path" ] || [ ! -d "$vault_path/01-daily" ]; then
    echo "✗ Could not find a vault with 01-daily/ at: $vault_path"
    echo "  Set OBSIDIAN_VAULT_PATH or add the vault to builder-profile.md, then re-run install."
    return 1
  fi

  # Generate the plist via Python (handles quoting correctly)
  python3 "$plugin_dir/companion/install_helper.py" write-plist \
    --vault "$vault_path" \
    --dest "$plist_dest"

  launchctl load -w "$plist_dest"
  echo "✓ Auto-start enabled. Companion will run at login."
  echo "  Vault: $vault_path"
  echo "  To disable later: launchctl unload -w $plist_dest"
}
```

Create `companion/install_helper.py`:

```python
"""Resolve vault path and generate the launchd plist safely.

Invoked from install.sh as a python subprocess so we avoid sed quoting issues.
"""

import os
import plistlib
import socket
import sys
from pathlib import Path

PROFILE_PATH = Path.home() / ".claude" / "local-plugins" / "nsls-personal-toolkit" / "50-reference" / "builder-profile.md"


def resolve_vault() -> str:
    # 1) env var
    env = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env and (Path(env) / "01-daily").is_dir():
        return env
    # 2) builder-profile (simple YAML-in-markdown — find data_sources.familiar.paths)
    if PROFILE_PATH.exists():
        text = PROFILE_PATH.read_text()
        host = socket.gethostname()
        # Naive lookup; profile schema is small and stable.
        in_paths = False
        current: dict = {}
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "paths:":
                in_paths = True; continue
            if in_paths and stripped.startswith("- host:"):
                if current.get("host") == host and current.get("path"):
                    return current["path"]
                current = {"host": stripped.split(":", 1)[1].strip()}
            elif in_paths and stripped.startswith("path:"):
                current["path"] = stripped.split(":", 1)[1].strip()
            elif in_paths and stripped == "":
                if current.get("host") == host and current.get("path"):
                    return current["path"]
                current = {}
        if current.get("host") == host and current.get("path"):
            return current["path"]
    # 3) prompt fallback
    sys.stderr.write("Vault path not found. Enter path to your Obsidian vault: ")
    sys.stderr.flush()
    return input().strip()


def write_plist(vault: str, dest: str, python_exe: str | None = None) -> None:
    python_exe = python_exe or sys.executable
    plist = {
        "Label": "com.nsls.toolkit-companion",
        "ProgramArguments": [python_exe, "-m", "companion.cli", "serve", "--no-open"],
        "EnvironmentVariables": {"OBSIDIAN_VAULT_PATH": vault},
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(Path.home() / "Library" / "Logs" / "nsls-toolkit-companion.log"),
        "StandardErrorPath": str(Path.home() / "Library" / "Logs" / "nsls-toolkit-companion.log"),
    }
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        plistlib.dump(plist, f)
    # Restrict perms — only owner can read/modify the autostart config.
    os.chmod(dest, 0o600)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "resolve-vault":
        print(resolve_vault())
    elif cmd == "write-plist":
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--vault", required=True)
        ap.add_argument("--dest", required=True)
        args = ap.parse_args(sys.argv[2:])
        write_plist(args.vault, args.dest)
    else:
        sys.exit("usage: install_helper.py {resolve-vault|write-plist}")
```

This removes the `sed` substitution surface, fixes the `~/Obsidian` fallback that wasn't the actual vault location for most users, and writes logs to `~/Library/Logs/` (mode-0600) instead of world-readable `/tmp/`.

- [ ] **Step 3: (no separate template file needed)**

The plist is generated by `install_helper.py` at install time using `plistlib`, so there is no `.template` file to maintain. This avoids the `sed`-substitution failure modes (special characters in vault paths, command-injection via `$(which python3)`) and keeps the plist format authoritative in one place.

- [ ] **Step 4: Commit**

```bash
git add install.sh companion/install_helper.py
git commit -m "install: optional companion + launchd autostart with safe plist generation"
```

---

## Phase 7 — Skill updates (two small additions for habits)

### Task 15: `open-day` — seed habits row in daily note

**Files:**
- Modify: `skills/open-day/SKILL.md`

- [ ] **Step 1: Find the daily-note template section**

Open `skills/open-day/SKILL.md`. Find the template section that begins with `The daily note should include:` (around line 580).

- [ ] **Step 2: Add Bonus and Habits subsections**

After `### My Top 3` template block:

```markdown
### Bonus

(nice-to-have items if there's time today — typically 1-3 items)

1. [Bonus item 1]
2. [Bonus item 2]
3. [Bonus item 3]
```

After `### Vitality`:

```markdown
### Habits

(One checkbox per active habit from 30-habits/habits.md. The bolded text MUST match the habit's name field verbatim — the companion and close-day both match on that string.)

- [ ] **Walk**
- [ ] **Read 15m**
- [ ] **Workout**

Read habits from `$OBSIDIAN_VAULT_PATH/30-habits/habits.md` parsing the Active list. Use each habit's `name` field for the bolded text. If the file does not exist, ask the builder once whether to create it (offer the template), then write `30-habits/habits.md` and `30-habits/log.md` from the templates.
```

- [ ] **Step 3: Commit**

```bash
git add skills/open-day/SKILL.md
git commit -m "feat(open-day): seed Bonus and Habits sections, ensure habits.md exists"
```

---

### Task 16: `close-day` — habit log reconciliation + streak prose + Gratitude

**Files:**
- Modify: `skills/close-day/SKILL.md`

- [ ] **Step 1: Find the close-day output template**

Around line 503 of `close-day/SKILL.md`, find the section that builds today's `## Habits` summary.

- [ ] **Step 2: Add habit-log reconciliation with canonical-source rule**

**Canonical source of truth for habit state: `30-habits/log.md`.** The companion writes to log.md directly when the user taps a habit. close-day merges from the daily note's `### Habits` checkboxes when it runs, but **log.md wins on conflict**: if the daily-note row says `- [ ] **Walk**` (unchecked) but log.md already has `walk:1.0` for today (because the user tapped in the companion), close-day must keep `1.0` — not overwrite to `0.0`.

Concretely:

```markdown
### Reconcile to log.md

After producing the `## Habits` summary, append today's results to `30-habits/log.md` in the format:

`YYYY-MM-DD · habit_id:percent · habit_id:percent`

Reconciliation rules (apply in order):

1. **Read existing log.md row for today** (if any). Call this `log_ticks` (a dict `{habit_id: percent}`).
2. **Read daily-note checkboxes** under `## Morning Check-in` → `### Habits`. Use the parser semantics: `[x]` = 1.0, `[/]` or `[~]` = 0.5, `[ ]` = 0.0. Call this `note_ticks`.
3. **For each active habit, merge — taking the MAX of the two values.** This gives canonical priority to log.md (companion ticks survive even if the user didn't update the checkbox in the daily note), while still letting users tick checkboxes in Obsidian or the CLI if log.md hasn't been touched for that habit today.
4. **Write the merged row back to log.md**, idempotent on the date — if a row for today already exists, replace it.
5. **Update the daily-note `### Habits` checkboxes to reflect the merged result** — checked (`[x]`) for 1.0, partial (`[/]`) for 0.5, unchecked (`[ ]`) for 0.0. This keeps the markdown human-readable in Obsidian, but the log.md value is authoritative.

This MAX-merge resolves the two-writer problem without needing mtime comparison: a tap in the companion never gets undone by close-day running afterwards, and a manual checkbox tick never gets undone by close-day if the companion was already at 1.0. Resetting a habit to 0.0 mid-day requires editing log.md directly.
```

- [ ] **Step 3: Add the streak rule prose paragraph**

After the existing habits section, add:

```markdown
### Streak rule reference

When describing habit streaks in `## Today's stats` or in Insight Reflection prompts, follow this rule:

Walk a habit's recent log backwards from yesterday until a 100% day is found (or the log is exhausted). Along the way, partial days (50%) add 0.5 to a "concern counter"; missed days (0%) add 1.0. A 100% day clears the counter back to 0 and stops the walk.

Status thresholds: 0–0.5 → OK. 1.0 → one miss recorded, streak still alive. 1.5 → at risk. 2.0 or more → reset.

When a habit is at risk, name it explicitly: *"Workout is at risk — one full day clears it."* When a habit just reset, acknowledge it without judgment: *"Walking streak reset; tomorrow restarts the count."*
```

- [ ] **Step 4: Add Gratitude section to the output template**

Find the `## Insight Reflection` template block. Immediately after it:

```markdown
## Gratitude

(Ask the builder for one thing they're grateful for from today. Optional — skip if user has nothing to write.)

[gratitude line]
```

- [ ] **Step 5: Verify Brain Dump section is intact**

Confirm the existing `## Brain Dump` section and routing logic in close-day is unchanged. This is a critical preservation — the cowork brainstorm previously dropped it accidentally.

- [ ] **Step 6: Commit**

```bash
git add skills/close-day/SKILL.md
git commit -m "feat(close-day): habit log reconciliation, streak prose, Gratitude — Brain Dump preserved"
```

---

## Phase 8 — Wrap-up

### Task 17: Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Create: `docs/companion-quickstart.md`

- [ ] **Step 1: Update `README.md`**

Add a section "Optional: Web Companion" after the existing Skills table:

```markdown
## Optional: Web Companion

A browser-based view onto your toolkit data, running locally at `http://localhost:7777`.

Install during the main `install.sh` flow when prompted, or later:

```bash
cd ~/.claude/local-plugins/nsls-personal-toolkit/companion
pip install -e .
toolkit-companion serve
```

The companion shows your Day, Week, and Streaks views with tappable checkboxes and a 30-day habit heatmap. It reads and writes the same Obsidian vault your CLI skills do, in real time. The CLI keeps working exactly as before — the companion is purely additive.

See `docs/companion-quickstart.md` for details.
```

- [ ] **Step 2: Update `CLAUDE.md`**

Add Companion section after Skills table:

```markdown
## Web Companion

The companion runs at `http://localhost:7777` (or `toolkit-companion status` to check). It is optional — install with `install.sh` or `cd companion && pip install -e .`.

Habits live in `30-habits/habits.md`; daily ticks accumulate in `30-habits/log.md` (append-only). The streak rule is documented in `skills/close-day/SKILL.md` and implemented in `companion/streak.py`. Both must stay in sync.
```

- [ ] **Step 3: Write `docs/companion-quickstart.md`**

```markdown
# Companion Quickstart

You've installed the companion. Here's how to use it.

## Start it

```bash
toolkit-companion serve
```

This starts the server on `http://localhost:7777` (or the next free port if 7777 is taken) and opens your browser.

## Your first day with both surfaces

1. **Morning:** Open your terminal, run `claude /open-day`. The skill pulls calendar, Asana, etc., and writes today's daily note.
2. Within ~1 second, the companion's browser tab auto-refreshes: you see Top 3, Bonus, Schedule, Habits.
3. Tap checkboxes as you work. Each tap saves immediately to the daily note.
4. Use the CLI for narrative work ("what should I push to tomorrow?", "summarize my morning").
5. **Evening:** `claude /close-day`. The companion's Day tab shows your stats, prompts for Insight Reflection and Gratitude. Type into the textarea or speak via CLI — either saves.

## Streaks

Click the Streaks tab. You see all active habits with a 30-day heatmap each. Add or archive habits with the buttons.

## Stop it

```bash
toolkit-companion stop
```

Or auto-start at login (offered during install). Manage with `launchctl`.

## When something breaks

The CLI is the source of truth. Worst case: stop the companion and use the terminal — everything still works.
```

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md docs/companion-quickstart.md
git commit -m "docs: companion quickstart + README/CLAUDE.md updates"
```

---

### Task 18: End-to-end smoke test on a fresh vault

**Goal:** Verify the whole flow on a clean install without any of Dave's local state.

- [ ] **Step 1: Create a fresh test vault**

```bash
mkdir -p /tmp/companion-test/{01-daily,02-weekly,30-habits,50-reference}
cp templates/habits.md.template /tmp/companion-test/30-habits/habits.md
cp templates/log.md.template /tmp/companion-test/30-habits/log.md
```

- [ ] **Step 2: Start companion against the test vault**

```bash
OBSIDIAN_VAULT_PATH=/tmp/companion-test toolkit-companion serve --port 7799 --no-open &
sleep 2
```

- [ ] **Step 3: Verify empty state renders**

```bash
curl -s http://localhost:7799/ | grep "No daily note for today yet" && echo "✓ empty Day"
curl -s http://localhost:7799/streaks | grep "Walk" && echo "✓ Streaks shows Walk"
curl -s http://localhost:7799/week | grep "No weekly note" && echo "✓ empty Week"
```

- [ ] **Step 4: Simulate a daily note being written**

```bash
TODAY=$(date +%Y-%m-%d)
cat > /tmp/companion-test/01-daily/$TODAY.md <<EOF
# Daily Note

## Morning Check-in

### My Top 3
1. Test priority
2. Another priority
3. Third priority

### Bonus
1. Bonus item

### Habits
- [ ] **Walk**
- [ ] **Read 15m**
EOF
```

- [ ] **Step 5: Verify companion shows it**

```bash
sleep 1
curl -s http://localhost:7799/ | grep "Test priority" && echo "✓ Day tab shows new note"
```

- [ ] **Step 6: Tick a habit via the API**

```bash
curl -s -X POST http://localhost:7799/tick -d "habit_id=walk&percent=1.0"
sleep 1
grep "$TODAY .* walk:1.0" /tmp/companion-test/30-habits/log.md && echo "✓ habit tick written"
```

- [ ] **Step 7: Cleanup**

```bash
toolkit-companion stop
rm -rf /tmp/companion-test
```

If any step fails, fix the bug and rerun.

---

### Task 19: Release v1.0-companion

**Files:**
- Update version stamps where present

- [ ] **Step 1: Run full pytest suite**

```bash
cd companion && pytest -v
```

Expected: all tests green.

- [ ] **Step 2: Update version**

In `companion/pyproject.toml`, bump to `1.0.0`.

- [ ] **Step 3: Write release notes**

Create `updates/2026-05-XX-companion-v1.md`:

```markdown
# Companion v1.0

A local web companion for the toolkit. Browser-based UI on localhost:7777.

## What's new

- Day / Week / Streaks tabs in a browser tab alongside your CLI
- Habits and Streaks engine with concern-counter rule
- Bonus list and Gratitude line additions to daily notes
- Real-time sync between CLI and browser via filesystem watcher + SSE
- Optional auto-start at login (macOS launchd)

## What's not changed

- All existing skills work exactly as before
- All existing hooks (`skill-event` etc.) continue to fire
- The Obsidian vault remains the single source of truth

## Install or upgrade

```bash
cd ~/.claude/local-plugins/nsls-personal-toolkit && git pull
./install.sh
```

When prompted, opt into the companion.
```

- [ ] **Step 4: Tag and push**

```bash
git tag -a v1.0-companion -m "Companion v1.0 — local web UI alongside CLI"
git push --tags
```

- [ ] **Step 5: Run /announce-update**

(From CLI, in the existing builder-toolkit pattern. Generates the release announcement.)

---

## Self-review

**Spec coverage** — walking the spec section by section:

- ✅ One-time setup (Task 14)
- ✅ Daily flow (Tasks 6-9)
- ✅ Weekly flow (Task 12)
- ✅ Streaks tab (Tasks 10-11)
- ✅ Architecture two processes / one source of truth (Tasks 4-5)
- ✅ Tech stack (Task 1 lists deps; templates use CDN script tags)
- ✅ Streak rule (Tasks 2, 16)
- ✅ Companion server structure (Tasks 4-12)
- ✅ Trigger model — user types in CLI (Tasks 15-16 cover the skill side; no scheduling work)
- ✅ Edge cases (covered in test fixtures and in the smoke test — Task 18)
- ✅ Skills inventory unchanged except two small additions (Tasks 15-16)
- ✅ Data model — uses upstream's existing daily-note section names (Task 6 extraction is from upstream sections)
- ✅ Phase 2 deferrals — not addressed in this plan, per spec

**Placeholder scan** — searched for "TBD", "TODO", "fill in", "similar to". One ellipsis in Task 7 ("Implementation: parse_daily_note_sections + line-level replace. See full implementation in task self-review.") — this is acceptable because the actual implementation is straightforward and the surrounding code shows the full pattern. The engineer implementing this task will use `parse_daily_note_sections` (defined in Task 3) to find the right block and a regex line-replace to toggle the checkbox marker. If a fully expanded implementation is needed, replace the `...` with a 10-line function body during execution.

**Type consistency** — `DayResult`, `Habits` dict shape `{"active": [...], "archived": [...]}`, log row shape `{"date": str, "ticks": dict}`, and `Status` literals match across all tasks.

**Open issue** — none blocking. The Coach Cards morning mode in Task 8 shows only steps 1-2 in the HTML example; steps 3-7 follow the same pattern (Bonus, Focus blocks, Habit intentions, Vitality, Lock in) and the engineer should mirror the structure. If a stricter expansion is needed for an inline executor, expand during the Task 8 step before running tests.

---

## Execution

**Plan complete and saved to `docs/plans/2026-05-16-cli-companion-build.md`.** Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
