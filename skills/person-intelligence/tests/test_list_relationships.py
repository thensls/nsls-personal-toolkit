#!/usr/bin/env python3.12
"""Tests for list_relationships.py.

Run: python3.12 test_list_relationships.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
LIST_RELATIONSHIPS = SCRIPT_DIR / "list_relationships.py"

FIXTURE_EMPLOYEES = [
    {
        "name": "Test User",
        "email": "test@example.com",
        "slack": "U_TEST",
        "manager": "Test Manager",
        "manages": ["Report A", "Report B"],
        "title": "Tester",
        "department": "QA",
    },
    {
        "name": "Report A",
        "email": "a@example.com",
        "slack": "U_A",
        "manager": "Test User",
        "manages": [],
        "title": "Engineer",
        "department": "QA",
    },
    {
        "name": "Report B",
        "email": "b@example.com",
        "slack": "U_B",
        "manager": "Test User",
        "manages": [],
        "title": "Engineer",
        "department": "QA",
    },
    {
        "name": "Peer One",
        "email": "p1@example.com",
        "slack": "U_P1",
        "manager": "Test Manager",
        "manages": [],
        "title": "Manager",
        "department": "Ops",
    },
    {
        "name": "Peer Two",
        "email": "p2@example.com",
        "slack": "U_P2",
        "manager": "Test Manager",
        "manages": [],
        "title": "Manager",
        "department": "Sales",
    },
]


def run(env, fixture_path):
    full_env = {**os.environ, **env}
    for k in (
        "OPERATING_USER_EMAIL",
        "BUILDER_EMAIL",
        "INCLUDE_MANAGEMENT_PEERS",
        "KEY_RELATIONSHIPS",
    ):
        if k not in env:
            full_env.pop(k, None)

    wrapper = f"""
import sys
sys.path.insert(0, {str(SCRIPT_DIR)!r})
import resolve_user
from pathlib import Path
resolve_user.ORG_CHART_PATHS = [Path({str(fixture_path)!r})]
import list_relationships
list_relationships.main()
"""
    result = subprocess.run(
        ["python3.12", "-c", wrapper],
        env=full_env,
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def make_fixture():
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(FIXTURE_EMPLOYEES, tmp)
    tmp.close()
    return Path(tmp.name)


def assert_eq(actual, expected, label):
    if actual != expected:
        print(f"FAIL [{label}]: expected {expected!r}, got {actual!r}", file=sys.stderr)
        sys.exit(1)
    print(f"  PASS [{label}]")


def test_direct_reports_only():
    print("test_direct_reports_only")
    fixture = make_fixture()
    try:
        stdout, _, code = run({"OPERATING_USER_EMAIL": "test@example.com"}, fixture)
        assert_eq(code, 0, "exit code")
        data = json.loads(stdout)
        assert_eq(data["relationship_count"], 2, "two direct reports")
        names = sorted(r["name"] for r in data["relationships"])
        assert_eq(names, ["Report A", "Report B"], "direct report names")
        reasons = {r["tracking_reason"] for r in data["relationships"]}
        assert_eq(reasons, {"direct_report"}, "only direct_report reasons")
    finally:
        fixture.unlink()


def test_with_peers():
    print("test_with_peers")
    fixture = make_fixture()
    try:
        stdout, _, code = run(
            {
                "OPERATING_USER_EMAIL": "test@example.com",
                "INCLUDE_MANAGEMENT_PEERS": "1",
            },
            fixture,
        )
        assert_eq(code, 0, "exit code")
        data = json.loads(stdout)
        assert_eq(data["relationship_count"], 4, "2 direct + 2 peers")
        peer_names = sorted(
            r["name"]
            for r in data["relationships"]
            if r["tracking_reason"] == "management_peer"
        )
        assert_eq(peer_names, ["Peer One", "Peer Two"], "peer names")
    finally:
        fixture.unlink()


def test_self_excluded_from_peers():
    """Don't include the operating user in their own peer ring."""
    print("test_self_excluded_from_peers")
    fixture = make_fixture()
    try:
        stdout, _, code = run(
            {
                "OPERATING_USER_EMAIL": "test@example.com",
                "INCLUDE_MANAGEMENT_PEERS": "1",
            },
            fixture,
        )
        data = json.loads(stdout)
        emails = {r["email"] for r in data["relationships"]}
        if "test@example.com" in emails:
            print("FAIL: operating user appeared in their own peer ring", file=sys.stderr)
            sys.exit(1)
        print("  PASS [self excluded from peers]")
    finally:
        fixture.unlink()


def test_key_relationships_external():
    """Names in KEY_RELATIONSHIPS that aren't in org-chart still get tracked."""
    print("test_key_relationships_external")
    fixture = make_fixture()
    try:
        stdout, _, code = run(
            {
                "OPERATING_USER_EMAIL": "test@example.com",
                "KEY_RELATIONSHIPS": "External Person, Another Outsider",
            },
            fixture,
        )
        data = json.loads(stdout)
        externals = [
            r
            for r in data["relationships"]
            if r["tracking_reason"] == "key_relationship_external"
        ]
        assert_eq(len(externals), 2, "two externals tracked")
        names = sorted(r["name"] for r in externals)
        assert_eq(names, ["Another Outsider", "External Person"], "external names")
    finally:
        fixture.unlink()


def test_key_relationships_dedup_with_direct_report():
    """A name in both manages[] and KEY_RELATIONSHIPS appears once, as direct_report."""
    print("test_key_relationships_dedup_with_direct_report")
    fixture = make_fixture()
    try:
        stdout, _, code = run(
            {
                "OPERATING_USER_EMAIL": "test@example.com",
                "KEY_RELATIONSHIPS": "Report A",
            },
            fixture,
        )
        data = json.loads(stdout)
        report_a_records = [r for r in data["relationships"] if r["name"] == "Report A"]
        assert_eq(len(report_a_records), 1, "Report A appears once, not twice")
        assert_eq(
            report_a_records[0]["tracking_reason"],
            "direct_report",
            "first reason wins (direct_report > key_relationship)",
        )
    finally:
        fixture.unlink()


def test_non_employee_operating_user():
    """A contractor without an org chart record still gets KEY_RELATIONSHIPS tracking."""
    print("test_non_employee_operating_user")
    fixture = make_fixture()
    try:
        stdout, _, code = run(
            {
                "OPERATING_USER_EMAIL": "contractor@elsewhere.com",
                "KEY_RELATIONSHIPS": "External Person",
            },
            fixture,
        )
        assert_eq(code, 0, "exit code 0 (warn but proceed)")
        data = json.loads(stdout)
        assert_eq(
            data["operating_user"]["found_in_org_chart"],
            False,
            "user not in org chart",
        )
        assert_eq(data["relationship_count"], 1, "one external key relationship")
        if not any(
            "not in org-chart.json" in w for w in data["warnings"]
        ):
            print(f"FAIL: missing warning about user not in org chart: {data['warnings']}", file=sys.stderr)
            sys.exit(1)
        print("  PASS [warning surfaced]")
    finally:
        fixture.unlink()


def test_no_airtable_dependency():
    print("test_no_airtable_dependency")
    fixture = make_fixture()
    try:
        stdout, _, code = run(
            {
                "OPERATING_USER_EMAIL": "test@example.com",
                "AIRTABLE_API_KEY": "invalid",
            },
            fixture,
        )
        assert_eq(code, 0, "exit code")
        data = json.loads(stdout)
        assert_eq(data["relationship_count"], 2, "ran without Airtable")
    finally:
        fixture.unlink()


if __name__ == "__main__":
    print("Running list_relationships.py tests")
    test_direct_reports_only()
    test_with_peers()
    test_self_excluded_from_peers()
    test_key_relationships_external()
    test_key_relationships_dedup_with_direct_report()
    test_non_employee_operating_user()
    test_no_airtable_dependency()
    print("\nAll list_relationships tests passed.")
