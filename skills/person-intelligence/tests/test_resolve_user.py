#!/usr/bin/env python3.12
"""Tests for resolve_user.py.

Run: python3.12 test_resolve_user.py
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
RESOLVE_USER = SCRIPT_DIR / "resolve_user.py"

# Fixture: a tiny org chart we control.
FIXTURE_EMPLOYEES = [
    {
        "name": "Test User",
        "email": "test@example.com",
        "slack": "U_TEST",
        "title": "Tester",
        "department": "QA",
        "manager": "Test Manager",
        "manages": ["Test Report A", "Test Report B"],
    },
    {
        "name": "Test Report A",
        "email": "reportA@example.com",
        "slack": "U_A",
        "manager": "Test User",
        "manages": [],
        "department": "QA",
        "title": "Engineer",
    },
]


def run_with_env(env, fixture_path=None):
    """Run resolve_user.py with a fresh env. Returns (stdout, stderr, exit_code).

    When fixture_path is provided, monkey-patches ORG_CHART_PATHS via a small wrapper.
    """
    full_env = {**os.environ, **env}
    # Strip any inherited values we want to control.
    for k in ("OPERATING_USER_EMAIL", "BUILDER_EMAIL"):
        if k not in env:
            full_env.pop(k, None)

    if fixture_path:
        # Run via a wrapper that injects the fixture path.
        wrapper = f"""
import sys
sys.path.insert(0, {str(SCRIPT_DIR)!r})
import resolve_user
from pathlib import Path
resolve_user.ORG_CHART_PATHS = [Path({str(fixture_path)!r})]
resolve_user.main()
"""
        result = subprocess.run(
            ["python3.12", "-c", wrapper],
            env=full_env,
            capture_output=True,
            text=True,
        )
    else:
        result = subprocess.run(
            ["python3.12", str(RESOLVE_USER)],
            env=full_env,
            capture_output=True,
            text=True,
        )
    return result.stdout, result.stderr, result.returncode


def make_fixture(employees, age_days=0):
    """Write the fixture employees to a temp file, optionally backdating mtime."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(employees, tmp)
    tmp.close()
    path = Path(tmp.name)
    if age_days:
        old_ts = (datetime.now() - timedelta(days=age_days)).timestamp()
        os.utime(path, (old_ts, old_ts))
    return path


def assert_eq(actual, expected, label):
    if actual != expected:
        print(f"FAIL [{label}]: expected {expected!r}, got {actual!r}", file=sys.stderr)
        sys.exit(1)
    print(f"  PASS [{label}]")


def assert_contains(haystack, needle, label):
    if needle not in haystack:
        print(f"FAIL [{label}]: expected {needle!r} in output, got:\n{haystack}", file=sys.stderr)
        sys.exit(1)
    print(f"  PASS [{label}]")


def test_user_found():
    print("test_user_found")
    fixture = make_fixture(FIXTURE_EMPLOYEES)
    try:
        stdout, stderr, code = run_with_env(
            {"OPERATING_USER_EMAIL": "test@example.com"}, fixture
        )
        assert_eq(code, 0, "exit code")
        data = json.loads(stdout)
        assert_eq(data["found"], True, "found")
        assert_eq(data["name"], "Test User", "name")
        assert_eq(data["manager"], "Test Manager", "manager")
        assert_eq(data["manages"], ["Test Report A", "Test Report B"], "manages")
    finally:
        fixture.unlink()


def test_user_not_found():
    print("test_user_not_found")
    fixture = make_fixture(FIXTURE_EMPLOYEES)
    try:
        stdout, stderr, code = run_with_env(
            {"OPERATING_USER_EMAIL": "ghost@example.com"}, fixture
        )
        assert_eq(code, 0, "exit code (no match is not an error)")
        data = json.loads(stdout)
        assert_eq(data["found"], False, "found")
        assert_eq(data["email"], "ghost@example.com", "email echoed back")
    finally:
        fixture.unlink()


def test_missing_email_env():
    print("test_missing_email_env")
    fixture = make_fixture(FIXTURE_EMPLOYEES)
    try:
        stdout, stderr, code = run_with_env({}, fixture)
        assert_eq(code, 1, "exit code for missing env")
        assert_contains(stderr, "OPERATING_USER_EMAIL", "error mentions env var")
    finally:
        fixture.unlink()


def test_builder_email_fallback():
    print("test_builder_email_fallback")
    fixture = make_fixture(FIXTURE_EMPLOYEES)
    try:
        stdout, stderr, code = run_with_env(
            {"BUILDER_EMAIL": "test@example.com"}, fixture
        )
        assert_eq(code, 0, "exit code with BUILDER_EMAIL fallback")
        data = json.loads(stdout)
        assert_eq(data["found"], True, "found via fallback")
    finally:
        fixture.unlink()


def test_stale_org_chart_warning():
    print("test_stale_org_chart_warning")
    fixture = make_fixture(FIXTURE_EMPLOYEES, age_days=30)
    try:
        stdout, stderr, code = run_with_env(
            {"OPERATING_USER_EMAIL": "test@example.com"}, fixture
        )
        assert_eq(code, 0, "exit code (warn doesn't block)")
        assert_contains(stderr, "30 days old", "warning includes age")
        assert_contains(stderr, "WARN", "warning is labeled")
        data = json.loads(stdout)
        assert_eq(data["found"], True, "data still returned despite warning")
    finally:
        fixture.unlink()


def test_no_airtable_dependency():
    """Belt-and-suspenders: the script must not touch Airtable."""
    print("test_no_airtable_dependency")
    fixture = make_fixture(FIXTURE_EMPLOYEES)
    try:
        # Invalid Airtable key, set to ensure no accidental API calls succeed.
        stdout, stderr, code = run_with_env(
            {
                "OPERATING_USER_EMAIL": "test@example.com",
                "AIRTABLE_API_KEY": "invalid",
            },
            fixture,
        )
        assert_eq(code, 0, "exit code")
        data = json.loads(stdout)
        assert_eq(data["found"], True, "resolved without Airtable")
    finally:
        fixture.unlink()


if __name__ == "__main__":
    print("Running resolve_user.py tests")
    test_user_found()
    test_user_not_found()
    test_missing_email_env()
    test_builder_email_fallback()
    test_stale_org_chart_warning()
    test_no_airtable_dependency()
    print("\nAll resolve_user tests passed.")
