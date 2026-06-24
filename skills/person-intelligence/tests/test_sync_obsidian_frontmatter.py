#!/usr/bin/env python3.12
"""Tests for sync_obsidian_frontmatter.py.

The contract under test is the **non-destructive** property: the sync may only
change frontmatter fields in its allowlist. Everything else — body content,
non-allowlisted frontmatter, comment lines, blank lines — must survive byte-
identically.

Run: python3.12 test_sync_obsidian_frontmatter.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
SCRIPT = SCRIPT_DIR / "sync_obsidian_frontmatter.py"

sys.path.insert(0, str(SCRIPT_DIR))
import sync_obsidian_frontmatter as syn  # noqa: E402


GOLD_PROFILE = """---
type: person
tags: [leadership, slt, board, health-good]
role: "Founder & Interim CEO"
org: NSLS
last-synthesized: 2026-03-22
sources: [fathom-1on1s, airtable-slt, airtable-people-ops]
meetings_attended: 28
health: good
health_score: 3.33
health_last_assessed: 2026-04-13
department: Unknown
email: gtuerack@nsls.org
slack: U040YTX56DP
---

# 🟢 Gary Tuerack

Body content here. The sync MUST NOT touch any of this.

## Section heading
- bullet
- another bullet
"""


SAMPLE_EMPLOYEE = {
    "name": "Gary Tuerack",
    "email": "gtuerack@nsls.org",
    "slack": "U040YTX56DP",
    "department": "Executive",
    "title": "Founder & CEO",
    "manager": "",
    "manages": ["Kevin Prentiss"],
}


def make_vault(profile_content):
    """Create a temp vault dir with a 30-people/Gary Tuerack.md."""
    vault = Path(tempfile.mkdtemp(prefix="sync-test-"))
    (vault / "30-people").mkdir()
    (vault / "30-people" / "Gary Tuerack.md").write_text(profile_content)
    return vault


def make_org_chart_file(employees):
    """Write a temp org-chart.json. Returns path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(employees, tmp)
    tmp.close()
    return Path(tmp.name)


def assert_eq(actual, expected, label):
    if actual != expected:
        print(f"FAIL [{label}]:")
        print(f"  expected: {expected!r}")
        print(f"  actual:   {actual!r}")
        sys.exit(1)
    print(f"  PASS [{label}]")


def run_script(vault, chart_path, dry_run=True):
    env = {**os.environ, "OBSIDIAN_VAULT_PATH": str(vault), "OPERATING_USER_EMAIL": "test@example.com"}
    wrapper = f"""
import sys
sys.path.insert(0, {str(SCRIPT_DIR)!r})
import resolve_user
from pathlib import Path
resolve_user.ORG_CHART_PATHS = [Path({str(chart_path)!r})]
import sync_obsidian_frontmatter
sync_obsidian_frontmatter.main()
"""
    cmd = ["python3.12", "-c", wrapper]
    if dry_run:
        cmd = ["python3.12", "-c", wrapper.replace("sync_obsidian_frontmatter.main()", "import sys; sys.argv = ['sync_obsidian_frontmatter.py', '--dry-run']; sync_obsidian_frontmatter.main()")]
    else:
        cmd = ["python3.12", "-c", wrapper.replace("sync_obsidian_frontmatter.main()", "import sys; sys.argv = ['sync_obsidian_frontmatter.py']; sync_obsidian_frontmatter.main()")]
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


# --- Unit tests (call functions directly) ---


def test_parse_frontmatter():
    print("test_parse_frontmatter")
    fm, body = syn.parse_frontmatter(GOLD_PROFILE)
    assert_eq(len(fm) > 0, True, "frontmatter parsed")
    assert_eq(body.startswith("\n# 🟢"), True, "body starts after frontmatter")


def test_parse_frontmatter_no_frontmatter():
    print("test_parse_frontmatter_no_frontmatter")
    fm, body = syn.parse_frontmatter("just body, no frontmatter")
    assert_eq(fm, [], "no frontmatter -> empty list")
    assert_eq(body, "just body, no frontmatter", "body intact")


def test_read_field():
    print("test_read_field")
    fm, _ = syn.parse_frontmatter(GOLD_PROFILE)
    email, idx = syn.read_field(fm, "email")
    assert_eq(email, "gtuerack@nsls.org", "email read")
    assert idx >= 0
    health, _ = syn.read_field(fm, "health")
    assert_eq(health, "good", "health read")
    missing, idx = syn.read_field(fm, "nonexistent")
    assert_eq(missing, None, "missing field returns None")
    assert_eq(idx, -1, "missing field returns -1")


def test_update_field_existing():
    print("test_update_field_existing")
    fm, _ = syn.parse_frontmatter(GOLD_PROFILE)
    fm = syn.update_field(fm, "department", '"Executive"')
    department, _ = syn.read_field(fm, "department")
    assert_eq(department, '"Executive"', "department updated to Executive")


def test_update_field_new():
    print("test_update_field_new")
    fm, _ = syn.parse_frontmatter(GOLD_PROFILE)
    fm = syn.update_field(fm, "new_field", "value")
    new_val, _ = syn.read_field(fm, "new_field")
    assert_eq(new_val, "value", "new field appended")


def test_compute_proposed_fields():
    print("test_compute_proposed_fields")
    proposed = syn.compute_proposed_fields(SAMPLE_EMPLOYEE)
    assert_eq("email" in proposed, True, "email in proposed")
    assert_eq("title" in proposed, True, "title in proposed")
    assert_eq("manager" not in proposed, True, "empty manager omitted")


def test_diff_employee_finds_changes():
    print("test_diff_employee_finds_changes")
    vault = make_vault(GOLD_PROFILE)
    try:
        path = vault / "30-people" / "Gary Tuerack.md"
        changes = syn.diff_employee(SAMPLE_EMPLOYEE, path)
        # email already matches (gtuerack@nsls.org)
        # slack already matches (U040YTX56DP)
        # department: "Unknown" -> "Executive" (change)
        # title: not set -> "Founder & CEO" (change)
        # manager: empty in SAMPLE so skipped
        change_fields = sorted(c[0] for c in changes)
        assert_eq(change_fields, ["department", "title"], "expected changed fields")
    finally:
        import shutil
        shutil.rmtree(vault)


def test_apply_preserves_body_and_other_fields():
    """The key invariant: body content and non-allowlisted frontmatter survive byte-perfect."""
    print("test_apply_preserves_body_and_other_fields")
    vault = make_vault(GOLD_PROFILE)
    try:
        path = vault / "30-people" / "Gary Tuerack.md"
        original = path.read_text(encoding="utf-8")
        changes = syn.diff_employee(SAMPLE_EMPLOYEE, path)
        syn.apply_changes(path, changes)
        updated = path.read_text(encoding="utf-8")

        # Body must be byte-identical
        original_body = original.split("---\n", 2)[2]
        updated_body = updated.split("---\n", 2)[2]
        assert_eq(original_body, updated_body, "body preserved byte-identically")

        # Non-allowlisted frontmatter fields must be unchanged
        for field in ("type", "tags", "role", "org", "last-synthesized", "sources",
                      "meetings_attended", "health", "health_score", "health_last_assessed"):
            fm_orig, _ = syn.parse_frontmatter(original)
            fm_new, _ = syn.parse_frontmatter(updated)
            orig_val, _ = syn.read_field(fm_orig, field)
            new_val, _ = syn.read_field(fm_new, field)
            assert_eq(new_val, orig_val, f"field '{field}' preserved")

        # Allowlisted fields that changed must be updated
        fm_new, _ = syn.parse_frontmatter(updated)
        dept, _ = syn.read_field(fm_new, "department")
        # Strip surrounding quotes for comparison — yaml_quote may or may not quote
        dept_normalized = dept.strip().strip('"').strip("'")
        assert_eq(dept_normalized, "Executive", "department updated")
    finally:
        import shutil
        shutil.rmtree(vault)


def test_email_index_matching():
    print("test_email_index_matching")
    vault = make_vault(GOLD_PROFILE)
    try:
        people_dir = vault / "30-people"
        idx = syn.build_email_index(people_dir)
        assert_eq("gtuerack@nsls.org" in idx, True, "email indexed")
        assert_eq(idx["gtuerack@nsls.org"].name, "Gary Tuerack.md", "email -> right file")
    finally:
        import shutil
        shutil.rmtree(vault)


def test_find_obsidian_file_by_email():
    print("test_find_obsidian_file_by_email")
    vault = make_vault(GOLD_PROFILE)
    try:
        people_dir = vault / "30-people"
        idx = syn.build_email_index(people_dir)
        path = syn.find_obsidian_file(SAMPLE_EMPLOYEE, people_dir, idx)
        assert_eq(path.name, "Gary Tuerack.md", "found by email")
    finally:
        import shutil
        shutil.rmtree(vault)


def test_find_obsidian_file_by_name_fallback():
    """If email isn't indexed, fall back to exact filename match."""
    print("test_find_obsidian_file_by_name_fallback")
    # Profile without an email field
    profile_no_email = "---\ntype: person\n---\n\n# Body\n"
    vault = make_vault(profile_no_email)
    try:
        people_dir = vault / "30-people"
        idx = syn.build_email_index(people_dir)
        path = syn.find_obsidian_file(SAMPLE_EMPLOYEE, people_dir, idx)
        assert_eq(path.name, "Gary Tuerack.md", "found by name fallback")
    finally:
        import shutil
        shutil.rmtree(vault)


def test_dry_run_doesnt_write():
    """--dry-run must not modify any file."""
    print("test_dry_run_doesnt_write")
    vault = make_vault(GOLD_PROFILE)
    chart_path = make_org_chart_file([SAMPLE_EMPLOYEE])
    try:
        path = vault / "30-people" / "Gary Tuerack.md"
        before = path.read_text()
        result = run_script(vault, chart_path, dry_run=True)
        after = path.read_text()
        assert_eq(after, before, "file unchanged after dry-run")
        assert_eq("DRY RUN" in result.stdout, True, "dry-run banner shown")
    finally:
        import shutil
        shutil.rmtree(vault)
        chart_path.unlink()


def test_real_run_writes():
    print("test_real_run_writes")
    vault = make_vault(GOLD_PROFILE)
    chart_path = make_org_chart_file([SAMPLE_EMPLOYEE])
    try:
        path = vault / "30-people" / "Gary Tuerack.md"
        before = path.read_text()
        result = run_script(vault, chart_path, dry_run=False)
        after = path.read_text()
        if before == after:
            print(f"FAIL: file unchanged after real run. stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            sys.exit(1)
        print("  PASS [file written]")
    finally:
        import shutil
        shutil.rmtree(vault)
        chart_path.unlink()


if __name__ == "__main__":
    print("Running sync_obsidian_frontmatter.py tests")
    test_parse_frontmatter()
    test_parse_frontmatter_no_frontmatter()
    test_read_field()
    test_update_field_existing()
    test_update_field_new()
    test_compute_proposed_fields()
    test_diff_employee_finds_changes()
    test_apply_preserves_body_and_other_fields()
    test_email_index_matching()
    test_find_obsidian_file_by_email()
    test_find_obsidian_file_by_name_fallback()
    test_dry_run_doesnt_write()
    test_real_run_writes()
    print("\nAll sync_obsidian_frontmatter tests passed.")
