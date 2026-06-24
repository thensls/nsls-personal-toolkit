"""Markdown parsers for habits.md, log.md, and daily-note sections.

These read upstream-conforming markdown and return Python dicts. They also
serialize back: append_day_to_log writes one row of ticks, idempotent on
the date (replaces if already present).
"""

import hashlib
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


def parse_frontmatter(md: str) -> dict[str, str]:
    """Extract YAML frontmatter from a daily note.

    Returns a flat dict of key-value pairs. Values are always strings.
    If no frontmatter block is present, returns {}.

    Daily-note analogue of week_parsers.parse_weekly_frontmatter — behavior
    must stay identical so the CLI/web companion and the cowork artifact never
    disagree on the `status:` contract.
    """
    if not md.startswith("---"):
        return {}
    end = md.find("\n---", 3)
    if end == -1:
        return {}
    block = md[3:end].strip()
    result: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            result[key] = value
    return result


def set_frontmatter(md: str, key: str, value: str) -> str:
    """Set a single frontmatter key. Creates the frontmatter block if missing.

    Daily-note analogue of week_parsers.set_weekly_frontmatter.
    """
    if not md.startswith("---"):
        # No frontmatter — prepend one.
        return f"---\n{key}: {value}\n---\n\n{md}"
    end = md.find("\n---", 3)
    if end == -1:
        return f"---\n{key}: {value}\n---\n\n{md}"
    block = md[3:end]
    after = md[end + 4:]  # skip \n---
    # Check if key already exists in block
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*:\s*)(.*)$", re.MULTILINE)
    m = pattern.search(block)
    if m:
        block = block[:m.start()] + f"{key}: {value}" + block[m.end():]
    else:
        block = block.rstrip("\n") + f"\n{key}: {value}\n"
    return f"---{block}\n---{after}"


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


# ===========================================================================
# SAVE_DAY handler — the canonical save channel (build plan §3.2/§3.3)
# ===========================================================================
#
# The cowork artifact hands edited day-state back to Claude via
# `sendPrompt("SAVE_DAY " + JSON.stringify(envelope))` — a visible chat message.
# Claude parses it and writes the vault in one turn. Cowork has NO Python
# runtime: on that surface this module is the *executable spec* the open-day /
# close-day SKILL.md prose describes; Claude follows the prose. The CLI/web
# companion can import and call apply_save_day directly. One source of truth —
# same pattern as streak.py being canonical for streak.js.
#
# Contract: docs/specs/2026-06-21-cowork-dashboard-2.1-design.md "Save protocol".

SAVE_DAY_SCHEMA_VERSION = 1

# Progress markers round-trip as an invisible trailing HTML comment, identical
# to the CLI/web companion (companion/server.py _PROGRESS_RE / _set_nth_progress).
_SAVE_PROGRESS_RE = re.compile(r"\s*<!--\s*p:(\d{1,3})\s*-->\s*$")

# Energy is captured twice and the two must never be conflated: morning lives
# in `## Morning Check-in`, evening in `## End of Day` (matches server.py
# _ENERGY_SECTIONS).
_SAVE_ENERGY_SECTIONS = {"morning": "Morning Check-in", "evening": "End of Day"}


def compute_note_hash(md: str) -> str:
    """16-hex-char sha256 prefix of a note's bytes — the conflict-detection key.

    The artifact is seeded with this hash (`baseHash`); on save we recompute it
    from the LATEST note on disk. Equal -> clean patch; different -> the note
    changed underneath us (CLI, close-day, manual edit) and we patch-with-drift.

    Must match the artifact's hashing. The artifact hashes the same UTF-8 text;
    a parity test (companion/tests/test_save_day_parity.py) shells the JS hasher
    through node and asserts it equals this for the canonical fixtures.
    """
    return hashlib.sha256(md.encode("utf-8")).hexdigest()[:16]


def _strip_save_progress(text: str) -> str:
    """Drop a trailing ``<!--p:NN-->`` marker from item text."""
    m = _SAVE_PROGRESS_RE.search(text)
    return text[: m.start()].rstrip() if m else text


def _render_numbered_item(n: int, item: dict) -> str:
    """One ``N. [ ] text <!--p:NN-->`` row from an envelope item.

    - done disposition (or progress >= 100) -> ``[x]`` and no marker.
    - 25/50/75 -> ``[ ]`` + ``<!--p:NN-->`` (invisible in rendered Obsidian).
    - 0 -> ``[ ]`` only.
    Empty positional slots render as ``N. [ ]`` (NEVER compacted away).
    Deleted is a reversible MARK: the row is kept (cowork gates rm) and the text
    preserved; deletion is tracked in the ``### Deleted`` subsection, not by
    dropping the line. An item can be deleted AND carry a %.
    """
    text = _strip_save_progress((item.get("text") or "").strip())
    progress = int(item.get("progress") or 0)
    disposition = item.get("disposition") or "active"
    done = disposition == "done" or progress >= 100
    if done:
        box, marker = "[x]", ""
    else:
        box = "[ ]"
        marker = f" <!--p:{progress}-->" if 0 < progress < 100 else ""
    body = f"{text}{marker}".rstrip()
    return f"{n}. {box} {body}".rstrip()


def _render_numbered_block(items: list[dict]) -> list[str]:
    """Render a positional list of items as numbered markdown rows."""
    return [_render_numbered_item(i + 1, it) for i, it in enumerate(items)]


def _splice_subsection(md: str, parent: str, heading: str, body_lines: list[str]) -> str:
    """Replace the body of a ``### <heading>`` subsection that lives under the
    level-2 ``## <parent>`` section. Creates the subsection at the end of the
    parent if absent. Every other line of the note is preserved verbatim.

    `heading` is the bare title (e.g. "My Top 3"). `body_lines` are the rendered
    rows (no heading line).
    """
    full = f"### {heading}"
    parent_h = f"## {parent}"
    lines = md.splitlines()

    parent_start = None
    parent_end = len(lines)
    for i, line in enumerate(lines):
        if parent_start is None:
            if line.strip() == parent_h:
                parent_start = i
            continue
        if line.startswith("## ") and not line.startswith("### "):
            parent_end = i
            break
    if parent_start is None:
        # Parent section missing — append parent + subsection at the end.
        block = [parent_h, "", full, *body_lines, ""]
        return md.rstrip("\n") + "\n\n" + "\n".join(block) + "\n"

    # Find the subsection within [parent_start, parent_end).
    sub_start = None
    sub_end = parent_end
    for i in range(parent_start + 1, parent_end):
        if lines[i].strip() == full:
            sub_start = i
        elif sub_start is not None and (lines[i].startswith("### ") or lines[i].startswith("## ")):
            sub_end = i
            break

    if sub_start is None:
        # Subsection missing — insert it at the end of the parent (before the
        # next level-2 heading), keeping a blank line separator.
        insert_at = parent_end
        # trim trailing blanks inside the parent so we don't pile up blank lines
        while insert_at - 1 > parent_start and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        new = ["", full, *body_lines]
        lines[insert_at:insert_at] = new
        return "\n".join(lines) + ("\n" if md.endswith("\n") else "")

    new_block = [full, *body_lines]
    spliced = lines[:sub_start] + new_block + lines[sub_end:]
    return "\n".join(spliced) + ("\n" if md.endswith("\n") else "")


def _splice_section_body(md: str, section: str, body_lines: list[str]) -> str:
    """Replace the body of a level-2 ``## <section>`` with body_lines, preserving
    surrounding sections. Append the section at the end if it's absent."""
    heading = f"## {section}"
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
    new_block = [heading, "", *body_lines, ""]
    if start is None:
        return md.rstrip("\n") + "\n\n" + "\n".join(new_block) + "\n"
    spliced = lines[:start] + new_block + lines[end:]
    return "\n".join(spliced) + ("\n" if md.endswith("\n") else "")


def _clear_section(md: str, section: str) -> str:
    """Remove a level-2 ``## <section>`` and its body entirely. No-op if absent.

    Used when a SAVE_DAY field is explicitly cleared (sent as "") — we delete
    the whole section rather than leave an empty heading behind."""
    heading = f"## {section}"
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
    if start is None:
        return md
    # Eat a single trailing blank-line separator the section left behind.
    while end < len(lines) and lines[end].strip() == "":
        end += 1
        break
    del lines[start:end]
    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def _set_energy_in_section(md: str, section: str, level: str) -> str:
    """Set ``- Energy: <level>`` inside ``## <section>`` without disturbing the
    rest of the section. Replaces an existing (empty or filled) Energy bullet;
    inserts one right after the heading if none exists. Mirrors server.py."""
    heading = f"## {section}"
    energy_line = f"- Energy: {level}"
    energy_re = re.compile(r"^\s*-\s*Energy:", re.IGNORECASE)
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
    if start is None:
        return md.rstrip("\n") + f"\n\n{heading}\n{energy_line}\n"
    for i in range(start + 1, end):
        if energy_re.match(lines[i]):
            lines[i] = energy_line
            return "\n".join(lines) + ("\n" if md.endswith("\n") else "")
    lines.insert(start + 1, energy_line)
    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def _render_habit_lines(habits: list[dict], active_habits: list[dict] | None) -> list[str]:
    """Render ``### Habits`` checkbox rows from per-habit percents.

    1.0 -> ``[x]``, 0.5 -> ``[/]``, else ``[ ]``. The bold label MUST be the
    habit's `name` (matched verbatim by close-day + the CLI companion), so we
    map id->name from active_habits. Unknown ids (no name) are skipped.
    """
    id_to_name = {h["id"]: h["name"] for h in (active_habits or [])}
    rows: list[str] = []
    for h in habits:
        name = id_to_name.get(h.get("id"))
        if not name:
            continue
        pct = float(h.get("percent") or 0.0)
        box = "[x]" if pct >= 1.0 else ("[/]" if pct >= 0.5 else "[ ]")
        rows.append(f"- {box} **{name}**")
    return rows


def _sync_deleted_subsection(md: str, top3: list[dict], bonus: list[dict],
                             unplanned: list[dict]) -> str:
    """Keep the ``### Deleted`` subsection in sync with deleted-disposition items.

    Delete is a reversible mark: the item's row stays in its list, and its text
    is ALSO listed under ``### Deleted`` so close-day knows to skip carrying it.
    Toggling an item back to active removes it from ``### Deleted``. We rebuild
    the subsection from the current dispositions each save (idempotent)."""
    deleted_texts: list[str] = []
    for it in list(top3) + list(bonus) + list(unplanned):
        if (it.get("disposition") == "deleted") and (it.get("text") or "").strip():
            deleted_texts.append(_strip_save_progress(it["text"].strip()))
    body = [f"- {t}" for t in deleted_texts]
    if not body:
        # Nothing deleted -> ensure the subsection is gone (don't leave an empty one).
        return _remove_subsection(md, "Morning Check-in", "Deleted")
    return _splice_subsection(md, "Morning Check-in", "Deleted", body)


def _remove_subsection(md: str, parent: str, heading: str) -> str:
    """Remove a ``### <heading>`` subsection (and its body) from ``## <parent>``.
    No-op if absent."""
    full = f"### {heading}"
    parent_h = f"## {parent}"
    lines = md.splitlines()
    parent_start = None
    parent_end = len(lines)
    for i, line in enumerate(lines):
        if parent_start is None:
            if line.strip() == parent_h:
                parent_start = i
            continue
        if line.startswith("## ") and not line.startswith("### "):
            parent_end = i
            break
    if parent_start is None:
        return md
    sub_start = None
    sub_end = parent_end
    for i in range(parent_start + 1, parent_end):
        if lines[i].strip() == full:
            sub_start = i
        elif sub_start is not None and (lines[i].startswith("### ") or lines[i].startswith("## ")):
            sub_end = i
            break
    if sub_start is None:
        return md
    del lines[sub_start:sub_end]
    # Collapse a doubled blank-line separator left where the subsection was.
    if 0 < sub_start < len(lines) and lines[sub_start - 1].strip() == "" \
            and lines[sub_start].strip() == "":
        del lines[sub_start]
    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def _validate_envelope(envelope) -> str | None:
    """Return a human error string if the envelope is malformed, else None."""
    if not isinstance(envelope, dict):
        return "Save payload was not a JSON object — nothing written."
    if envelope.get("type") != "SAVE_DAY":
        return f"Unexpected payload type {envelope.get('type')!r} — expected SAVE_DAY. Nothing written."
    if envelope.get("schemaVersion") != SAVE_DAY_SCHEMA_VERSION:
        return (f"SAVE_DAY schemaVersion {envelope.get('schemaVersion')!r} is not supported "
                f"(this build expects {SAVE_DAY_SCHEMA_VERSION}). Nothing written — your edits are safe in the dashboard.")
    if "saveId" not in envelope or not envelope.get("saveId"):
        return "SAVE_DAY payload is missing a saveId — nothing written."
    if not isinstance(envelope.get("changes"), dict):
        return "SAVE_DAY payload is missing its `changes` object — nothing written."
    return None


def apply_save_day(latest_note_md: str, envelope, applied_save_ids,
                   active_habits: list[dict] | None = None) -> dict:
    """Apply a SAVE_DAY envelope to the LATEST daily note. Pure function.

    Args:
      latest_note_md: the note as just re-read from disk (NOT the artifact's
        stale snapshot). Hashing this is the conflict check.
      envelope: the parsed SAVE_DAY dict (or a non-dict, which is refused).
      applied_save_ids: the set of saveIds already applied this session
        (idempotency). Caller adds the returned save_id after a write.
      active_habits: [{"id","name"}, ...] so habit ids map to bold labels.

    Returns a dict:
      action: "refuse" | "noop" | "patched" | "patched-with-drift"
      note_md: the new whole-file content (== input on refuse/noop)
      save_id: the envelope's saveId (or None)
      message: a one-line human explanation (always set)

    The patch rewrites ONLY the sections the artifact owns (Top 3, Bonus,
    Unplanned, Habits, both energies, Gratitude, Daily Insight, Insight
    Reflection, status frontmatter). Every other section — Calendar, Work Log,
    AI Suggested, Projects, Time Allocation — is preserved verbatim. Whole-file
    replace, never delete.
    """
    # --- Step 1: validate ---
    err = _validate_envelope(envelope)
    if err is not None:
        return {"action": "refuse", "note_md": latest_note_md,
                "save_id": (envelope.get("saveId") if isinstance(envelope, dict) else None),
                "message": err}

    save_id = envelope["saveId"]
    changes = envelope["changes"]

    # --- Step 2: idempotency ---
    if save_id in set(applied_save_ids):
        return {"action": "noop", "note_md": latest_note_md, "save_id": save_id,
                "message": f"Save {save_id} was already applied — no change."}

    # --- Step 3: conflict / drift ---
    latest_hash = compute_note_hash(latest_note_md)
    drifted = latest_hash != envelope.get("baseHash")

    # --- Steps 4-6: field-level patch onto the LATEST note (never the snapshot) ---
    md = latest_note_md

    top3 = changes.get("top3")
    if top3 is not None:
        md = _splice_subsection(md, "Morning Check-in", "My Top 3",
                                _render_numbered_block(top3))

    bonus = changes.get("bonus")
    if bonus is not None:
        md = _splice_subsection(md, "Morning Check-in", "Bonus",
                                _render_numbered_block(bonus))

    unplanned = changes.get("unplanned")
    if unplanned:  # only author ### Unplanned when there is something to show
        md = _splice_subsection(md, "Morning Check-in", "Unplanned",
                                _render_numbered_block(unplanned))

    # Deleted mark sync (depends on whichever lists were sent).
    md = _sync_deleted_subsection(md, top3 or [], bonus or [], unplanned or [])

    # Habits: only rewrite ### Habits when we have a name map AND it yields rows.
    # Without active_habits we cannot map ids -> bold labels, so we PRESERVE the
    # existing section rather than splice an empty one (which would wipe the
    # checkboxes on an unrelated energy/gratitude save). Codex review [P2].
    habits = changes.get("habits")
    if habits and active_habits:
        rows = _render_habit_lines(habits, active_habits)
        if rows:
            md = _splice_subsection(md, "Morning Check-in", "Habits", rows)

    energy = changes.get("energy") or {}
    for which, section in _SAVE_ENERGY_SECTIONS.items():
        if which in energy and energy[which]:
            md = _set_energy_in_section(md, section, str(energy[which]).lower())

    # Free-text reflection fields are patched on KEY PRESENCE, not truthiness, so
    # an explicit clear (the user emptied the field -> "") deletes the section
    # instead of leaving stale text. A field absent from `changes` is left as-is.
    # Codex review [P2].
    for key, section in (("gratitude", "Gratitude"),
                         ("insightReflection", "Insight Reflection"),
                         ("dailyInsight", "Daily Insight")):
        if key not in changes:
            continue
        value = (changes.get(key) or "").rstrip()
        if value:
            md = _splice_section_body(md, section, [value])
        else:
            md = _clear_section(md, section)

    transition = changes.get("statusTransition")
    if transition in ("active", "closed", "planning"):
        md = set_frontmatter(md, "status", transition)

    action = "patched-with-drift" if drifted else "patched"
    msg = (f"Patched {envelope.get('notePath', 'the daily note')}"
           + (" (note had changed since it was opened — your fields were merged onto the latest)."
              if drifted else "."))
    return {"action": action, "note_md": md, "save_id": save_id, "message": msg}
