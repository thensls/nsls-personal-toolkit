#!/usr/bin/env python3
"""run_real_sweep.py — replace backfilled/stub rows with real per-period assessments.

For each tracked profile:
  1. Parse the `## Relationship Health` table
  2. Identify rows marked `Backfilled` or `Stub`
  3. For each, call assess_biweekly_period.py with the period start date
  4. Replace the row with the real assessed row (or a "no data" marker if
     no meetings happened in that window)

Email comes from the profile's frontmatter. Profiles without an email are
skipped with a warning.

Usage:
    python3.12 run_real_sweep.py [--only NAME] [--dry-run]
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import resolve_user  # noqa: E402
import list_relationships  # noqa: E402


def parse_frontmatter_email(text):
    """Return the email from profile frontmatter, or None."""
    m = re.search(r"^email:\s*(\S+)", text, re.MULTILINE)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    return None


def parse_table(text):
    """Locate the Relationship Health table. Return dict with header/rows/offsets."""
    m = re.search(r"^## Relationship Health\s*$", text, re.MULTILINE)
    if not m:
        return None
    section_start = m.end()
    next_h = re.search(r"^## ", text[section_start:], re.MULTILINE)
    section_end = section_start + (next_h.start() if next_h else len(text) - section_start)

    section_text = text[section_start:section_end]
    table_match = re.search(r"^\|.+\|\s*$", section_text, re.MULTILINE)
    if not table_match:
        return None
    table_local_start = table_match.start()
    lines = []
    line_pos = table_local_start
    for raw in section_text[table_local_start:].split("\n"):
        if raw.strip().startswith("|") and raw.strip().endswith("|"):
            lines.append(raw)
            line_pos += len(raw) + 1
        elif raw.strip() == "":
            break
        else:
            break

    if len(lines) < 2:
        return None

    header = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    rows = []
    for raw in lines[2:]:
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", cells[0] if cells else "")
        rows.append({
            "raw": raw,
            "cells": cells,
            "date": date_match.group(1) if date_match else None,
        })

    return {
        "table_start": section_start + table_local_start,
        "table_end": section_start + table_local_start + sum(len(l) + 1 for l in lines),
        "header": header,
        "rows": rows,
        "separator_line": lines[1] if len(lines) > 1 else "|---|",
    }


def find_note_column_index(header):
    """Index of Note or Notes column, or -1."""
    for i, h in enumerate(header):
        if h.strip().lower() in ("note", "notes"):
            return i
    return -1


def row_note(cells, note_idx):
    """Return the Note value of a row."""
    if note_idx < 0 or note_idx >= len(cells):
        return ""
    return cells[note_idx].strip()


def is_backfill_or_stub(cells, note_idx):
    note = row_note(cells, note_idx)
    return note in ("Backfilled", "Stub")


def build_assessment_row(assessment, header, note_idx):
    """Build a markdown row from an assessment dict matching the header structure.

    Standard format expected: [Date, State|Overall, 6 dimensions, Note]
    """
    cells = []
    width = len(header)
    if width < 8:
        # Unknown shape — fall back
        return None

    # Date — use period_start
    cells.append(assessment["period_start"])

    # State/Overall — index 1
    state = assessment["state"]
    cells.append(f"{state['emoji']} {state['score']}")

    # Dimensions — try to map by header name; fall back to fixed order
    dim_keys_by_header = {
        "align": "alignment",
        "alignment": "alignment",
        "trust": "trust",
        "collab": "collaboration",
        "collaboration": "collaboration",
        "tension": "tension",
        "engage": "engagement",
        "engagement": "engagement",
        "influence": "influence",
        "influence balance": "influence",
    }
    for i in range(2, width - 1):
        header_name = header[i].strip().lower()
        dim_key = dim_keys_by_header.get(header_name)
        if dim_key and dim_key in assessment:
            dim = assessment[dim_key]
            cells.append(f"{dim['emoji']} {dim['score']}")
        else:
            cells.append("")

    # Note — last column
    note_text = assessment.get("row_note", "").strip() or "Assessed"
    cells.append(note_text)

    return "| " + " | ".join(cells) + " |"


def build_no_data_row(period_start, header):
    """Build a row marking 'No 1:1 this period' for windows with zero meetings."""
    cells = [period_start]
    width = len(header)
    for _ in range(1, width - 1):
        cells.append("—")
    cells.append("No 1:1 this period")
    return "| " + " | ".join(cells) + " |"


def assess_period(person_name, email, period_start):
    """Call assess_biweekly_period.py for one window."""
    payload = json.dumps({
        "person_name": person_name,
        "email": email,
        "period_start": period_start,
    })
    result = subprocess.run(
        ["python3.12", str(SCRIPT_DIR / "assess_biweekly_period.py")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=600,
    )
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {
            "status": "error",
            "error": f"could not parse output: {result.stdout[:300]}; stderr: {result.stderr[:300]}",
        }


def process_profile(name, vault_path, dry_run):
    """Process one profile. Returns summary dict."""
    path = vault_path / "30-people" / f"{name}.md"
    if not path.exists():
        return {"name": name, "status": "no_profile"}

    text = path.read_text(encoding="utf-8")
    email = parse_frontmatter_email(text)
    if not email:
        return {"name": name, "status": "no_email_in_frontmatter"}

    parsed = parse_table(text)
    if parsed is None:
        return {"name": name, "status": "no_health_table"}

    note_idx = find_note_column_index(parsed["header"])
    if note_idx < 0:
        return {"name": name, "status": "no_note_column"}

    # Find rows to replace
    targets = []
    for i, row in enumerate(parsed["rows"]):
        if not row["cells"]:
            continue
        if is_backfill_or_stub(row["cells"], note_idx):
            if row["date"]:
                targets.append((i, row["date"]))

    if not targets:
        return {"name": name, "status": "no_rows_to_replace"}

    # Order ascending date for stable processing
    targets.sort(key=lambda t: t[1])

    print(f"  {name}: {len(targets)} period(s) to assess", file=sys.stderr)

    assessment_results = []
    new_rows_by_index = {}
    for i, period_start in targets:
        if dry_run:
            assessment_results.append({"period_start": period_start, "status": "dry_run"})
            continue
        result = assess_period(name, email, period_start)
        result["_row_index"] = i
        assessment_results.append(result)
        if result.get("status") == "error":
            print(f"    ERROR for {name} {period_start}: {result.get('error', '?')[:400]}", file=sys.stderr)

        if result.get("status") == "assessed":
            new_rows_by_index[i] = build_assessment_row(result, parsed["header"], note_idx)
        elif result.get("status") == "no_data":
            new_rows_by_index[i] = build_no_data_row(period_start, parsed["header"])
        # On error: leave the row as-is (keep current Backfilled/Stub)

    if dry_run or not new_rows_by_index:
        return {
            "name": name,
            "status": "dry_run" if dry_run else "no_changes",
            "targets": len(targets),
            "results": assessment_results,
        }

    # Splice new rows into the file
    new_rows = []
    for i, row in enumerate(parsed["rows"]):
        if i in new_rows_by_index:
            new_rows.append(new_rows_by_index[i])
        else:
            new_rows.append(row["raw"])

    new_table = (
        "| " + " | ".join(parsed["header"]) + " |\n"
        + parsed["separator_line"] + "\n"
        + "\n".join(new_rows) + "\n"
    )
    new_text = text[:parsed["table_start"]] + new_table + text[parsed["table_end"]:]
    path.write_text(new_text, encoding="utf-8")

    return {
        "name": name,
        "status": "updated",
        "targets": len(targets),
        "results": assessment_results,
        "rows_replaced": len(new_rows_by_index),
    }


def compose_default_targets():
    """Return the 16 profile names we want to sweep (mirrors current tracked set)."""
    chart_path = resolve_user.find_org_chart()
    if chart_path is None:
        return []
    employees = resolve_user.load_org_chart(chart_path)
    email = resolve_user.get_user_email()
    user = resolve_user.resolve(email, employees) if email else None

    names = []
    if user:
        for r in user.get("manages", []) or []:
            names.append(r)
        if user.get("manager"):
            names.append(user["manager"])
        if os.environ.get("INCLUDE_MANAGEMENT_PEERS", "").strip() in {"1", "true", "yes"}:
            for peer in list_relationships.find_peers(employees, user.get("manager", "")):
                if peer.get("email", "").lower() != (email or "").lower():
                    names.append(peer.get("name", ""))

    for n in list_relationships.parse_key_relationships(os.environ.get("KEY_RELATIONSHIPS", "")):
        if n and n not in names:
            names.append(n)
    return [n for n in names if n]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="Only process this person")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        print("ERROR: OBSIDIAN_VAULT_PATH not set", file=sys.stderr)
        sys.exit(1)
    vault_path = Path(vault).expanduser()

    if args.only:
        names = [args.only]
    else:
        names = compose_default_targets()

    print(f"Processing {len(names)} profile(s) ({'DRY RUN' if args.dry_run else 'LIVE'})", file=sys.stderr)

    summaries = []
    for name in names:
        result = process_profile(name, vault_path, args.dry_run)
        summaries.append(result)

    print("\nResults:")
    by_status = {}
    for s in summaries:
        by_status.setdefault(s["status"], []).append(s)
    for status, items in sorted(by_status.items()):
        print(f"\n  {status} ({len(items)}):")
        for s in items:
            line = f"    - {s['name']}"
            if "results" in s and isinstance(s["results"], list):
                period_statuses = [r.get("status", "?") for r in s["results"]]
                from collections import Counter
                c = Counter(period_statuses)
                line += f" — {dict(c)}"
            print(line)


if __name__ == "__main__":
    main()
