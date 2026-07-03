#!/usr/bin/env python3
"""sync_obsidian_frontmatter.py — keep Obsidian people profiles' frontmatter
in sync with the builder toolkit's org-chart.json.

Reads `org-chart.json`. For each employee, finds the matching `30-people/*.md`
file in the Obsidian vault. Updates only an allowlist of frontmatter fields.
**Never touches the body** of any file, and never touches frontmatter fields
outside the allowlist (so Kevin's curated tags, health scores, role descriptions,
and human-authored sections all stay put).

Usage:
    python3.12 sync_obsidian_frontmatter.py --dry-run
    python3.12 sync_obsidian_frontmatter.py

Env:
    OBSIDIAN_VAULT_PATH — required; the vault root (e.g., the KP folder)
    OPERATING_USER_EMAIL — optional; resolves which org-chart to use (not yet used)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import resolve_user  # noqa: E402


# Fields the sync controls. Anything outside this list is left untouched.
SYNC_FIELDS = ("email", "slack", "department", "title", "manager")


FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


def parse_frontmatter(text):
    """Return (frontmatter_lines: list[str], body: str). Empty list if no frontmatter."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return [], text
    fm_block = m.group(1)
    body = m.group(2)
    # Preserve the raw lines (not parsed YAML) so we can do precise line-level edits
    # that preserve formatting of fields we don't touch.
    return fm_block.split("\n"), body


def read_field(fm_lines, key):
    """Find the value of a top-level scalar field in the frontmatter lines.

    Returns (value, line_index) or (None, -1) if not found.
    Handles only top-level scalar fields like `email: foo@bar.com`. Nested
    structures (lists, multiline) are left to the caller to detect via line_index.
    """
    pattern = re.compile(rf"^{re.escape(key)}\s*:\s*(.*)$")
    for i, line in enumerate(fm_lines):
        m = pattern.match(line)
        if m:
            return m.group(1).strip(), i
    return None, -1


def update_field(fm_lines, key, new_value):
    """Update or insert a top-level scalar field. Returns updated list.

    new_value should be the full YAML value (already quoted if needed).
    """
    pattern = re.compile(rf"^{re.escape(key)}\s*:\s*(.*)$")
    for i, line in enumerate(fm_lines):
        if pattern.match(line):
            fm_lines[i] = f"{key}: {new_value}"
            return fm_lines
    # Not present — append at the end of the frontmatter block.
    fm_lines.append(f"{key}: {new_value}")
    return fm_lines


def serialize(fm_lines, body):
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + body


def yaml_quote(value):
    """Quote a scalar value for YAML output if needed."""
    if value is None or value == "":
        return ""
    s = str(value)
    # Quote if contains special chars or starts with a YAML-significant token.
    if any(ch in s for ch in [":", "#", "'", '"', "[", "]", "{", "}", "\n", ","]):
        # Use double quotes, escape any double quotes already in the value.
        return '"' + s.replace('"', '\\"') + '"'
    # Quote if leading/trailing whitespace or looks like a YAML keyword
    if s.strip() != s or s.lower() in ("yes", "no", "true", "false", "null", "~"):
        return '"' + s + '"'
    return s


def compute_proposed_fields(emp):
    """Return a dict {field: yaml_value} of fields the sync wants to set for this employee."""
    proposed = {}
    if emp.get("email"):
        proposed["email"] = yaml_quote(emp["email"])
    if emp.get("slack"):
        proposed["slack"] = yaml_quote(emp["slack"])
    if emp.get("department"):
        proposed["department"] = yaml_quote(emp["department"])
    if emp.get("title"):
        proposed["title"] = yaml_quote(emp["title"])
    if emp.get("manager"):
        proposed["manager"] = yaml_quote(emp["manager"])
    return proposed


def find_obsidian_file(emp, people_dir, email_index):
    """Locate the 30-people/*.md file for this employee.

    Strategy:
      1. Match by email (frontmatter email == emp.email)
      2. Match by exact filename `[Name].md`
    """
    email = (emp.get("email") or "").lower()
    if email and email in email_index:
        return email_index[email]
    name = emp.get("name", "")
    if name:
        candidate = people_dir / f"{name}.md"
        if candidate.exists():
            return candidate
    return None


def build_email_index(people_dir):
    """Pre-scan all person files for their frontmatter email field."""
    index = {}
    for path in sorted(people_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        fm_lines, _ = parse_frontmatter(text)
        if not fm_lines:
            continue
        email, _ = read_field(fm_lines, "email")
        if email:
            # Strip quotes if YAML-quoted.
            email = email.strip().strip('"').strip("'").lower()
            if email:
                index[email] = path
    return index


def diff_employee(emp, path):
    """Return list of (field, old, new) tuples for this employee's file."""
    text = path.read_text(encoding="utf-8")
    fm_lines, _ = parse_frontmatter(text)
    if not fm_lines:
        return []
    proposed = compute_proposed_fields(emp)
    changes = []
    for field in SYNC_FIELDS:
        if field not in proposed:
            continue
        old_value, _ = read_field(fm_lines, field)
        new_value = proposed[field]
        # Normalize old for comparison: strip surrounding quotes
        old_normalized = (old_value or "").strip().strip('"').strip("'")
        new_normalized = new_value.strip().strip('"').strip("'")
        if old_normalized != new_normalized:
            changes.append((field, old_value, new_value))
    return changes


def apply_changes(path, changes):
    """Apply a list of (field, _, new_value) changes to the file. Returns True if written."""
    text = path.read_text(encoding="utf-8")
    fm_lines, body = parse_frontmatter(text)
    if not fm_lines:
        return False
    for field, _, new_value in changes:
        fm_lines = update_field(fm_lines, field, new_value)
    new_text = serialize(fm_lines, body)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print proposed changes without writing files",
    )
    parser.add_argument(
        "--vault",
        default=os.environ.get("OBSIDIAN_VAULT_PATH", ""),
        help="Obsidian vault path (default: $OBSIDIAN_VAULT_PATH)",
    )
    args = parser.parse_args()

    if not args.vault:
        print("ERROR: OBSIDIAN_VAULT_PATH not set and --vault not provided.", file=sys.stderr)
        sys.exit(1)

    vault = Path(args.vault).expanduser()
    people_dir = vault / "30-people"
    if not people_dir.is_dir():
        print(f"ERROR: {people_dir} does not exist.", file=sys.stderr)
        sys.exit(2)

    chart_path = resolve_user.find_org_chart()
    if chart_path is None:
        print(
            "ERROR: org-chart.json not found. See resolve_user.py for paths checked.",
            file=sys.stderr,
        )
        sys.exit(3)

    employees = resolve_user.load_org_chart(chart_path)
    email_index = build_email_index(people_dir)

    summary = {
        "files_changed": 0,
        "files_unchanged": 0,
        "employees_without_obsidian_file": [],
        "changes_by_file": {},
    }

    for emp in employees:
        path = find_obsidian_file(emp, people_dir, email_index)
        if path is None:
            summary["employees_without_obsidian_file"].append(emp.get("name", "?"))
            continue
        changes = diff_employee(emp, path)
        if not changes:
            summary["files_unchanged"] += 1
            continue
        summary["files_changed"] += 1
        summary["changes_by_file"][str(path.relative_to(vault))] = [
            {"field": field, "old": old, "new": new}
            for field, old, new in changes
        ]
        if not args.dry_run:
            apply_changes(path, changes)

    # Output summary.
    print(f"Employees in org chart: {len(employees)}")
    print(f"Files in 30-people/: {len(list(people_dir.glob('*.md')))}")
    print(f"Files updated: {summary['files_changed']}")
    print(f"Files unchanged: {summary['files_unchanged']}")
    print(f"Employees without Obsidian file: {len(summary['employees_without_obsidian_file'])}")
    if args.dry_run:
        print("\n--- DRY RUN: proposed changes ---")
    else:
        print("\n--- Applied changes ---")
    for rel_path, changes in summary["changes_by_file"].items():
        print(f"\n{rel_path}:")
        for c in changes:
            old_display = c["old"] if c["old"] else "(unset)"
            print(f"  {c['field']}: {old_display} -> {c['new']}")
    if summary["employees_without_obsidian_file"]:
        print(f"\nNo Obsidian file for ({len(summary['employees_without_obsidian_file'])}):")
        for name in summary["employees_without_obsidian_file"][:20]:
            print(f"  - {name}")
        if len(summary["employees_without_obsidian_file"]) > 20:
            print(f"  ... and {len(summary['employees_without_obsidian_file']) - 20} more")


if __name__ == "__main__":
    main()
