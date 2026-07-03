#!/usr/bin/env python3
"""backfill_emoji_chart.py — write biweekly emoji rows for missed periods.

When the person-intelligence sweep hasn't been running, profiles develop
gaps in their `## Relationship Health` table. This script fills those gaps
with **visibly-distinct** backfilled rows so the chart has cadence integrity
without claiming assessments that didn't happen.

Backfilled rows use:
  - Date column suffix: ` ⚪` (e.g., `2026-04-05 ⚪`)
  - State column: `⚪ {score}` (un-assessed rollup)
  - Per-dimension cells: outlined emoji (`🟩` for `💚`, `🟨` for `🟢`/`🟡`, `🟧` for `🔴`)
  - Note column: `Backfilled`

The last existing row (before backfill) gets `Assessed` written into its
Note column lazily. Older rows are left untouched (we don't retro-label
history we didn't track).

Frontmatter `last-synthesized` is NOT advanced.

Usage:
    python3.12 backfill_emoji_chart.py [--dry-run] [--only NAME]

Env:
    OBSIDIAN_VAULT_PATH — required
    OPERATING_USER_EMAIL — required to compute the tracked relationship set
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import resolve_user  # noqa: E402
import list_relationships  # noqa: E402


# Round emoji for backfilled rows — every emoji becomes ⚪ to signal
# "no assessment, carried forward". The numeric score is preserved so the
# value is still visible. Matches the round visual style of 💚🟢🟡🔴.
UNASSESSED_DOT = "⚪"
UNASSESSED_ROLLUP = "⚪"
DATE_SUFFIX = " ⚪"
FILLED_EMOJIS = ("💚", "🟢", "🟡", "🔴")


def biweekly_dates_between(start_iso, today):
    """Return list of YYYY-MM-DD dates that fall every 14 days strictly
    after start_iso and strictly before today."""
    try:
        start = datetime.fromisoformat(start_iso).date()
    except (ValueError, TypeError):
        return []
    dates = []
    cursor = start + timedelta(days=14)
    while cursor < today:
        dates.append(cursor.isoformat())
        cursor += timedelta(days=14)
    return dates


def parse_health_table(profile_text):
    """Locate the `## Relationship Health` table and parse its rows.

    Returns dict:
      {
        "start": int (offset of `## Relationship Health` line),
        "table_start": int (offset of the `|` of the header row),
        "table_end": int (offset just after the last row's newline),
        "header_cells": [str, ...],
        "rows": [{"cells": [str, ...], "raw": str, "date": str|None}, ...],
        "has_note_column": bool,
        "after_table": str (text from table_end to start of next ## or end of file),
      }
    Returns None if no Relationship Health section found.
    """
    m = re.search(r"^## Relationship Health\s*$", profile_text, re.MULTILINE)
    if not m:
        return None
    section_start = m.start()
    section_body = profile_text[m.end():]

    # End at next `## ` heading or end of file
    next_heading = re.search(r"^## ", section_body, re.MULTILINE)
    section_end = m.end() + (next_heading.start() if next_heading else len(section_body))

    section_text = profile_text[m.end():section_end]

    # Find the first table line — a line starting with `|`
    table_match = re.search(r"^\|.+\|\s*$", section_text, re.MULTILINE)
    if not table_match:
        return None
    table_local_start = table_match.start()
    table_start = m.end() + table_local_start

    # Collect consecutive `|...|` lines
    lines = []
    pos = table_local_start
    for raw_line in section_text[table_local_start:].split("\n"):
        if raw_line.strip().startswith("|") and raw_line.strip().endswith("|"):
            lines.append(raw_line)
            pos += len(raw_line) + 1
        elif raw_line.strip() == "":
            # blank line ends the table
            break
        else:
            break

    if len(lines) < 2:
        return None  # need at least header + separator

    table_end = m.end() + table_local_start + sum(len(l) + 1 for l in lines)

    # Parse header
    header_cells = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    # lines[1] is the separator (|---|---|...)
    rows = []
    for raw in lines[2:]:
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        date_str = None
        if cells:
            # Date is the first cell; may have a trailing emoji marker
            date_part = re.match(r"^(\d{4}-\d{2}-\d{2})", cells[0])
            if date_part:
                date_str = date_part.group(1)
        rows.append({"cells": cells, "raw": raw, "date": date_str})

    # Accept "Note" or "Notes" (some profiles use the plural form already).
    has_note_column = any(
        h.strip().lower() in ("note", "notes") for h in header_cells
    )

    return {
        "start": section_start,
        "table_start": table_start,
        "table_end": table_end,
        "header_cells": header_cells,
        "rows": rows,
        "has_note_column": has_note_column,
    }


def outline_emoji_cell(cell):
    """Return the unassessed version of a cell: replace any filled emoji with ⚪.
    Preserves the score number.
    """
    if not cell:
        return cell
    new_cell = cell
    for filled in FILLED_EMOJIS:
        new_cell = new_cell.replace(filled, UNASSESSED_DOT)
    return new_cell


def build_backfill_row(date_iso, template_cells, has_note_column):
    """Build a new backfilled row using template_cells (the most recent assessed row).

    template_cells: list of cells from the last assessed row (excluding any Note column).
    """
    # Cells = [Date, State, Align, Trust, Collab, Tension, Engage, Influence, (Note)]
    cells = list(template_cells)

    # Date column with ⚪ suffix
    cells[0] = f"{date_iso}{DATE_SUFFIX}"

    # State column — replace filled emoji with ⚪ but keep the numeric score
    state_score = re.search(r"\d+\.\d+|\d+", cells[1]) if len(cells) > 1 else None
    score_text = state_score.group(0) if state_score else ""
    cells[1] = f"{UNASSESSED_ROLLUP} {score_text}".rstrip()

    # Per-dimension cells — outline the emoji
    for i in range(2, min(8, len(cells))):
        cells[i] = outline_emoji_cell(cells[i])

    # Note column
    if has_note_column:
        if len(cells) <= 8:
            cells.append("Backfilled")
        else:
            cells[8] = "Backfilled"

    return "| " + " | ".join(cells) + " |"


def upgrade_with_note_column(parsed):
    """Migrate a table that lacks a Note column. Returns updated header + rows.

    Strategy: add `Note` header. If an existing row already has overflow cells
    (more cells than columns), treat that overflow as an implicit note value
    and migrate it into the new column. The most-recent row gets `Assessed`
    if it doesn't already have a note. Older rows without notes get empty.
    """
    new_header = parsed["header_cells"] + ["Note"]
    header_width = len(parsed["header_cells"])
    new_rows = []
    for i, row in enumerate(parsed["rows"]):
        new_cells = list(row["cells"])
        if len(new_cells) > header_width:
            # Existing overflow cells become the note value.
            note_value = " ".join(new_cells[header_width:]).strip()
            new_cells = new_cells[:header_width]
        else:
            note_value = ""
            while len(new_cells) < header_width:
                new_cells.append("")
        # Most-recent row gets "Assessed" if no note already.
        if i == 0 and not note_value:
            note_value = "Assessed"
        new_cells.append(note_value)
        new_rows.append({**row, "cells": new_cells})
    return new_header, new_rows


def render_table(header_cells, rows):
    """Render a markdown table from cells and rows."""
    width = len(header_cells)
    header_line = "| " + " | ".join(header_cells) + " |"
    sep_line = "|" + "|".join(["---"] * width) + "|"
    row_lines = []
    for row in rows:
        cells = row["cells"]
        # Pad
        while len(cells) < width:
            cells.append("")
        row_lines.append("| " + " | ".join(cells) + " |")
    return "\n".join([header_line, sep_line] + row_lines)


def write_journal_entry(profile_text, table_end, today_iso):
    """Append a `### YYYY-MM-DD — Cadence resumption` journal entry just after the table.

    Returns new profile text.
    """
    entry = (
        f"\n\n### {today_iso} — Cadence resumption\n\n"
        f"Backfilled rows use ⚪ in place of the filled health emoji "
        f"(💚/🟢/🟡/🔴) to indicate no human assessment. The score number "
        f"is carried forward from the last assessed row. The cadence clock "
        f"resumes now; the next sweep's assessment lands as a real row.\n"
    )
    return profile_text[:table_end] + entry + profile_text[table_end:]


def backfill_profile(path, today, dry_run):
    """Apply backfill to a single profile file. Returns dict summary or None if no changes."""
    text = path.read_text(encoding="utf-8")
    parsed = parse_health_table(text)
    if parsed is None:
        return {"path": str(path), "status": "no_health_table"}

    if not parsed["rows"]:
        return {"path": str(path), "status": "empty_table"}

    last_row = parsed["rows"][0]
    last_date = last_row.get("date")
    if not last_date:
        return {"path": str(path), "status": "last_row_has_no_date"}

    backfill_dates = biweekly_dates_between(last_date, today)
    if not backfill_dates:
        return {"path": str(path), "status": "current"}

    # Build the new rows
    has_note = parsed["has_note_column"]
    template_cells = list(last_row["cells"])

    if not has_note:
        # Migrate: add Note column. Mark last row as Assessed.
        new_header, new_rows = upgrade_with_note_column(parsed)
        # template_cells doesn't include note yet; for backfill we'll add it.
    else:
        new_header = list(parsed["header_cells"])
        new_rows = [dict(r) for r in parsed["rows"]]

    # Insert backfill rows at the TOP of the data rows. Iterate ascending
    # (oldest first) so later inserts push earlier ones down — final order
    # is descending (most recent first) at the top of the table.
    for d in sorted(backfill_dates):
        new_row_text = build_backfill_row(d, template_cells, has_note_column=True)
        new_cells = [c.strip() for c in new_row_text.strip().strip("|").split("|")]
        new_rows.insert(0, {"cells": new_cells, "raw": new_row_text, "date": d})

    new_table = render_table(new_header, new_rows)
    new_text = (
        text[:parsed["table_start"]]
        + new_table
        + "\n"
        + text[parsed["table_end"]:]
    )

    # Compute new table_end for journal insertion
    new_table_end = parsed["table_start"] + len(new_table) + 1

    # Append journal entry (only if we backfilled anything)
    today_iso = today.isoformat()
    new_text = write_journal_entry(new_text, new_table_end, today_iso)

    if not dry_run:
        path.write_text(new_text, encoding="utf-8")

    return {
        "path": str(path),
        "status": "backfilled",
        "last_assessed_date": last_date,
        "backfill_dates": backfill_dates,
        "note_column_added": not has_note,
    }


def compose_tracked_relationships():
    """Compute the tracked relationship set using list_relationships logic.

    Returns list of names.
    """
    chart_path = resolve_user.find_org_chart()
    if chart_path is None:
        return []
    employees = resolve_user.load_org_chart(chart_path)
    email = resolve_user.get_user_email()
    if not email:
        return []
    user = resolve_user.resolve(email, employees)

    names = set()
    if user:
        for r in user.get("manages", []) or []:
            names.add(r)
        if user.get("manager"):
            names.add(user["manager"])
        if os.environ.get("INCLUDE_MANAGEMENT_PEERS", "").strip() in {"1", "true", "yes"}:
            for peer in list_relationships.find_peers(employees, user.get("manager", "")):
                if peer.get("email", "").lower() != email.lower():
                    names.add(peer.get("name", ""))

    for name in list_relationships.parse_key_relationships(os.environ.get("KEY_RELATIONSHIPS", "")):
        names.add(name)

    return sorted(n for n in names if n)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show diffs, don't write")
    parser.add_argument("--only", help="Only process this person's profile (by name)")
    args = parser.parse_args()

    vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        print("ERROR: OBSIDIAN_VAULT_PATH not set", file=sys.stderr)
        sys.exit(1)
    vault_path = Path(vault).expanduser()

    today = date.today()

    if args.only:
        names = [args.only]
    else:
        names = compose_tracked_relationships()
        if not names:
            print("ERROR: no tracked relationships (check OPERATING_USER_EMAIL)", file=sys.stderr)
            sys.exit(1)

    print(f"Backfilling {len(names)} profile(s) ({'DRY RUN' if args.dry_run else 'LIVE'})", file=sys.stderr)

    summaries = []
    for name in names:
        path = vault_path / "30-people" / f"{name}.md"
        if not path.exists():
            summaries.append({"path": str(path), "status": "no_obsidian_file", "name": name})
            continue
        result = backfill_profile(path, today, args.dry_run)
        result["name"] = name
        summaries.append(result)

    # Summary
    print(f"\nResults:")
    by_status = {}
    for s in summaries:
        by_status.setdefault(s["status"], []).append(s)

    for status, items in sorted(by_status.items()):
        print(f"\n  {status} ({len(items)}):")
        for s in items:
            line = f"    - {s.get('name', '?')}"
            if status == "backfilled":
                dates = s.get("backfill_dates", [])
                line += f": +{len(dates)} rows ({', '.join(dates[:3])}{'...' if len(dates) > 3 else ''})"
                if s.get("note_column_added"):
                    line += " [Note column added]"
            print(line)


if __name__ == "__main__":
    main()
