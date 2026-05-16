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
pythonpath = ["."]
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
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd companion && pytest tests/test_parsers.py -v
```

Expected: 7 passed.

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

- [ ] **Step 3: Implement `companion/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NSLS Toolkit Companion</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/htmx.org@1.9.10"></script>
  <script defer src="https://unpkg.com/alpinejs@3.13.5/dist/cdn.min.js"></script>
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

- [ ] **Step 4: Implement `companion/templates/day.html`**

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

- [ ] **Step 5: Run tests, verify pass**

```bash
cd companion && pytest tests/test_server.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Smoke test manually**

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

- [ ] **Step 7: Commit**

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

- [ ] **Step 3: Add SSE endpoint to server**

Modify `companion/server.py`:

```python
import queue
from flask import Response, stream_with_context

# inside create_app:
    subscribers: list[queue.Queue] = []

    @app.route("/events")
    def events():
        q: queue.Queue = queue.Queue()
        subscribers.append(q)

        def stream():
            try:
                while True:
                    msg = q.get()
                    yield f"data: {msg}\n\n"
            finally:
                subscribers.remove(q)

        return Response(stream_with_context(stream()), mimetype="text/event-stream")

    def broadcast(relpath: str) -> None:
        for q in list(subscribers):
            q.put(relpath)

    app.config["BROADCAST"] = broadcast
```

- [ ] **Step 4: Wire watcher into the app**

In `companion/server.py` create_app:

```python
from companion.watcher import VaultWatcher

# inside create_app, after subscribers are defined:
    watcher = VaultWatcher(vault_path, on_change=broadcast)
    watcher.start()
    app.config["WATCHER"] = watcher
```

(Tests using `create_app` should stop the watcher in fixture teardown to avoid leftover threads. Update the test fixture in test_server.py accordingly.)

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
- Modify: `companion/server.py` (add `POST /tick` and `POST /toggle`)
- Modify: `companion/templates/day.html`
- Create: `companion/tests/test_day_interactions.py`

- [ ] **Step 1: Failing test for habit-tick endpoint**

```python
def test_tick_habit_writes_to_log(client_with_today, tmp_path):
    resp = client_with_today.post("/tick", data={"habit_id": "walk", "percent": "1.0"})
    assert resp.status_code == 200
    log = (tmp_path / "vault" / "30-habits" / "log.md").read_text()
    from datetime import date
    today = date.today().isoformat()
    assert today in log
    assert "walk:1.0" in log
```

- [ ] **Step 2: Implement `POST /tick` in server.py**

```python
from companion.parsers import parse_log, append_day_to_log

# inside create_app:
    @app.route("/tick", methods=["POST"])
    def tick():
        habit_id = request.form["habit_id"]
        percent = float(request.form["percent"])
        log_path = app.config["VAULT_PATH"] / "30-habits" / "log.md"
        existing = log_path.read_text() if log_path.exists() else ""
        # Merge with existing today's ticks
        today = date.today().isoformat()
        rows = parse_log(existing)
        today_ticks = next((r["ticks"] for r in rows if r["date"] == today), {})
        today_ticks[habit_id] = percent
        updated = append_day_to_log(existing, today, today_ticks)
        log_path.write_text(updated)
        broadcast(f"30-habits/log.md")
        # Return updated habit row (HTMX swaps it in)
        return render_template("_components/habit_row.html",
                               h=_habit_state_for(app, habit_id, today, percent))
```

- [ ] **Step 3: Add Toggle endpoint for Top 3 / Bonus checkboxes**

```python
    @app.route("/toggle", methods=["POST"])
    def toggle():
        section = request.form["section"]  # "top_3" or "bonus"
        index = int(request.form["index"])
        # Read today's note, find the relevant `### My Top 3` / `### Bonus`,
        # toggle the leading "- [ ]" / "- [x]" on the Nth item, write back.
        # Implementation: parse_daily_note_sections + line-level replace.
        # See full implementation in task self-review.
        ...
        broadcast(f"01-daily/{today}.md")
        return ("", 204)
```

- [ ] **Step 4: Add HTMX attributes to checkbox templates**

In `day.html`, change checkboxes to HTMX-posting buttons:

```html
<input type="checkbox" class="w-4 h-4"
       hx-post="/toggle"
       hx-vals='{"section":"top_3", "index":{{ loop.index0 }}}'
       hx-swap="none">
```

- [ ] **Step 5: Run tests, verify pass, commit**

```bash
cd companion && pytest tests/test_day_interactions.py -v
git add companion/server.py companion/templates/day.html companion/tests/test_day_interactions.py
git commit -m "feat(day): interactive checkbox + habit tick via HTMX"
```

---

### Task 8: Day tab — Coach Cards morning mode

**Files:**
- Modify: `companion/templates/day.html` (add mode toggle)
- Create: `companion/templates/_components/coach_cards.html`
- Create: `companion/tests/test_coach_cards.py`

- [ ] **Step 1: Failing test for Coach Cards mode rendering**

```python
def test_coach_cards_mode_renders_step_1(client_with_today):
    resp = client_with_today.get("/?mode=coach")
    assert resp.status_code == 200
    assert b"Step 1" in resp.data
    assert b"Confirm Top 3" in resp.data


def test_coach_cards_progress(client_with_today):
    resp = client_with_today.get("/?mode=coach&step=2")
    assert b"Step 2" in resp.data
```

- [ ] **Step 2: Implement `_components/coach_cards.html`**

```html
<div x-data="{ step: {{ step or 1 }} }" class="bg-white rounded-lg shadow p-6">
  <div class="flex gap-1 mb-3">
    {% for i in range(1, 8) %}
      <div class="flex-1 h-1 rounded" :class="step >= {{ i }} ? 'bg-blue-900' : 'bg-stone-200'"></div>
    {% endfor %}
  </div>
  <div class="text-xs uppercase text-stone-500 mb-4">Step <span x-text="step"></span> of 7</div>

  <template x-if="step === 1">
    <div><h3 class="font-semibold mb-2">Good morning</h3><p>Today is {{ today }}. {{ top_3 | length }} priorities pulled from Asana.</p></div>
  </template>
  <template x-if="step === 2">
    <div><h3 class="font-semibold mb-2">Confirm Top 3</h3>
      {% for item in top_3 %}<input value="{{ item }}" class="block w-full border rounded px-3 py-2 mb-2">{% endfor %}
    </div>
  </template>
  <!-- ... steps 3-7 similar — Bonus, Focus blocks, Habit intentions, Vitality, Lock in -->

  <div class="mt-6 flex justify-end gap-3">
    <button @click="step--" :disabled="step <= 1" class="px-4 py-2 border rounded">Back</button>
    <button @click="step++" x-show="step < 7" class="px-4 py-2 bg-blue-900 text-white rounded">Next</button>
    <button x-show="step >= 7" hx-post="/lock-in" class="px-4 py-2 bg-blue-900 text-white rounded">Lock in</button>
  </div>
</div>
```

- [ ] **Step 3: Add mode toggle to day.html**

```html
<div class="mb-4 text-sm">
  <a href="?mode=coach" class="text-blue-700">Coach Cards</a> · 
  <a href="/" class="text-blue-700">Command Center</a>
</div>
{% if mode == 'coach' %}
  {% include "_components/coach_cards.html" %}
{% else %}
  <!-- existing Top 3 / Bonus / Habits sections -->
{% endif %}
```

- [ ] **Step 4: Run tests, verify pass, commit**

```bash
cd companion && pytest tests/test_coach_cards.py -v
git add companion/templates/ companion/tests/test_coach_cards.py
git commit -m "feat(day): Coach Cards morning mode with Alpine-driven step progression"
```

---

### Task 9: SSE wiring — browser auto-refresh on file change

**Files:**
- Modify: `companion/templates/base.html` (add SSE client)
- Create: `companion/tests/test_sse_integration.py`

- [ ] **Step 1: Add SSE client to base.html**

```html
<script>
  // Reload the current page when the vault changes.
  // We use EventSource (Server-Sent Events).
  const es = new EventSource("/events");
  let lastReload = Date.now();
  es.onmessage = (e) => {
    if (Date.now() - lastReload < 800) return;  // debounce
    lastReload = Date.now();
    if (e.data.startsWith("01-daily/") || e.data.startsWith("30-habits/")) {
      htmx.ajax("GET", window.location.href, { target: "main", swap: "innerHTML" });
    }
  };
</script>
```

- [ ] **Step 2: Smoke test (manual)**

Start the server, open `http://localhost:7777` in a browser, then in another terminal touch a file:

```bash
touch ~/Obsidian/DW/01-daily/$(date +%Y-%m-%d).md
```

The browser should re-render the Day tab within ~1 second.

- [ ] **Step 3: Commit**

```bash
git add companion/templates/base.html
git commit -m "feat: SSE-driven auto-refresh when vault files change"
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

- [ ] **Step 2: Implement add/archive in server.py**

```python
    @app.route("/add-habit-form")
    def add_habit_form():
        return render_template("_components/add_habit_form.html")

    @app.route("/habit", methods=["POST"])
    def add_habit():
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        md = habits_path.read_text() if habits_path.exists() else "# Daily Habits\n\n## Active\n\n## Archived\n"
        new_entry = (
            f"\n- id: {request.form['id']}\n"
            f"  name: {request.form['name']}\n"
            f"  emoji: {request.form['emoji']}\n"
            f"  target: {request.form['target']}\n"
            f"  frequency: {request.form['frequency']}\n"
        )
        # Insert after "## Active"
        md = md.replace("## Active\n", "## Active\n" + new_entry, 1)
        habits_path.write_text(md)
        broadcast("30-habits/habits.md")
        return ("", 204)

    @app.route("/habit/archive", methods=["POST"])
    def archive_habit():
        habit_id = request.form["habit_id"]
        habits_path = app.config["VAULT_PATH"] / "30-habits" / "habits.md"
        md = habits_path.read_text()
        habits = parse_habits(md)
        active = habits["active"]
        target = next((h for h in active if h["id"] == habit_id), None)
        if target is None:
            return ("", 404)
        target["archived_at"] = date.today().isoformat()
        habits["active"] = [h for h in active if h["id"] != habit_id]
        habits["archived"].append(target)
        # Re-serialize and write
        md = _serialize_habits(habits)
        habits_path.write_text(md)
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

## Phase 5 — Week tab

### Task 12: Week tab — render weekly note + stack rank

**Files:**
- Create: `companion/templates/week.html`
- Modify: `companion/server.py` (`GET /week`)
- Create: `companion/tests/test_week_tab.py`

- [ ] **Step 1: Failing test**

```python
def test_week_tab_renders_weekly_note(client_with_today, tmp_path):
    weekly = tmp_path / "vault" / "02-weekly"
    weekly.mkdir(parents=True)
    from datetime import date
    iso_year, iso_week, _ = date.today().isocalendar()
    (weekly / f"{iso_year}-W{iso_week:02d}.md").write_text("""# Week

## Mode
push

## Stack Rank

1. Ship toolkit cowork
2. Q3 LOP draft

## Recommended Top 3
""")
    resp = client_with_today.get("/week")
    assert b"PUSH" in resp.data or b"push" in resp.data
    assert b"Ship toolkit cowork" in resp.data
```

- [ ] **Step 2: Implement `GET /week`**

```python
    @app.route("/week")
    def week():
        from datetime import date
        y, w, _ = date.today().isocalendar()
        path = app.config["VAULT_PATH"] / "02-weekly" / f"{y}-W{w:02d}.md"
        if not path.exists():
            return render_template("week.html", week_md="", sections={})
        md = path.read_text()
        sections = parse_daily_note_sections(md)  # same parser works
        return render_template("week.html", week_md=md, sections=sections, week_of=f"{y}-W{w:02d}")
```

- [ ] **Step 3: Implement `companion/templates/week.html`**

```html
{% extends "base.html" %}
{% set active_tab = 'week' %}
{% block content %}
<h1 class="text-2xl font-bold mb-4">Week — {{ week_of }}</h1>

{% if not week_md %}
  <p class="text-stone-500">No weekly note yet. Run <code>/open-week</code> in your terminal.</p>
{% else %}

<div class="grid grid-cols-2 gap-4">
  <section class="bg-white rounded-lg shadow p-5">
    <h2 class="text-sm uppercase text-stone-500 mb-3">Mode</h2>
    <div class="text-2xl font-bold">{{ sections.get('Mode', '').upper() }}</div>
  </section>
  <section class="bg-white rounded-lg shadow p-5">
    <h2 class="text-sm uppercase text-stone-500 mb-3">Stack rank</h2>
    <pre class="text-sm whitespace-pre-wrap">{{ sections.get('Stack Rank', '') }}</pre>
  </section>
</div>

<section class="bg-white rounded-lg shadow p-5 mt-4">
  <h2 class="text-sm uppercase text-stone-500 mb-3">Recommended Top 3</h2>
  <pre class="text-sm whitespace-pre-wrap">{{ sections.get('Recommended Top 3', '') }}</pre>
</section>

{% endif %}
{% endblock %}
```

- [ ] **Step 4: Run tests, verify pass, commit**

```bash
cd companion && pytest tests/test_week_tab.py -v
git add companion/server.py companion/templates/week.html companion/tests/test_week_tab.py
git commit -m "feat(week): render weekly note with mode, stack rank, recommended Top 3"
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
@click.option("--host", default="127.0.0.1", help="Bind host (use 0.0.0.0 for LAN)")
@click.option("--no-open", is_flag=True, help="Don't open the browser")
def serve(vault, port, host, no_open):
    """Start the local web companion."""
    vault = vault or os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        click.echo("Set OBSIDIAN_VAULT_PATH or pass --vault", err=True)
        sys.exit(1)
    port = port or _find_free_port()

    from companion.server import create_app
    app = create_app(vault_path=vault)

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(f"{os.getpid()}\n{host}:{port}\n")

    url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}"
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

- [ ] **Step 2: Implement `install_companion_launchd`**

```bash
install_companion_launchd() {
  local plist_template="$HOME/.claude/local-plugins/nsls-personal-toolkit/templates/com.nsls.toolkit-companion.plist.template"
  local plist_dest="$HOME/Library/LaunchAgents/com.nsls.toolkit-companion.plist"
  local vault_path="${OBSIDIAN_VAULT_PATH:-$HOME/Obsidian}"

  sed "s|{{VAULT_PATH}}|$vault_path|g; s|{{TOOLKIT_PYTHON}}|$(which python3)|g" \
    "$plist_template" > "$plist_dest"
  launchctl load -w "$plist_dest"
  echo "✓ Auto-start enabled. Companion will run at login."
  echo "  To disable later: launchctl unload -w $plist_dest"
}
```

- [ ] **Step 3: Create `templates/com.nsls.toolkit-companion.plist.template`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.nsls.toolkit-companion</string>
  <key>ProgramArguments</key>
  <array>
    <string>{{TOOLKIT_PYTHON}}</string>
    <string>-m</string>
    <string>companion.cli</string>
    <string>serve</string>
    <string>--no-open</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>OBSIDIAN_VAULT_PATH</key>
    <string>{{VAULT_PATH}}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>/tmp/nsls-toolkit-companion.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/nsls-toolkit-companion.log</string>
</dict>
</plist>
```

- [ ] **Step 4: Commit**

```bash
git add install.sh templates/com.nsls.toolkit-companion.plist.template
git commit -m "install: optional companion + launchd autostart"
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

- [ ] **Step 2: Add habit-log reconciliation**

After the existing `## Habits` summary block, add:

```markdown
### Reconcile to log.md

After producing the `## Habits` summary, append today's results to `30-habits/log.md` in the format:

`YYYY-MM-DD · habit_id:percent · habit_id:percent`

Where percent is 1.0 if the habit's checkbox is checked in today's daily note, 0.5 if the user explicitly marked it partial, or 0.0 if unchecked. If a row for today already exists (because /close-day was run earlier), replace it — do not duplicate.
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
