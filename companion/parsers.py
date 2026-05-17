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
