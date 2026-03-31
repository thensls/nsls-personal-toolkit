#!/usr/bin/env python3
"""
fetch_airtable_people_ops.py -- pull employee + LOP goal data from People Ops Airtable.

Usage:
  python3.12 fetch_airtable_people_ops.py "Adam Stone"

Output: JSON to stdout with employee record and LOP goals.
Status messages go to stderr.

Requires: AIRTABLE_API_KEY env var.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

BASE_ID = "appnXPTu01esWWbrK"
BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}"

EMPLOYEES_TABLE = "tblpa8L4JPnqByINh"
LOP_GOALS_TABLE = "tblWWupDuX8AiYiId"

# Field IDs for Employees
EMPLOYEE_FIELDS = {
    "fldkA557zfIC2p8y2": "name",
    "fld3CmPWkul8GodI2": "email",
    "fld3lm4bSBxV2tYVX": "slack_user_id",
    "fldIFpAjpTJpV965h": "department",
    "fldxE7Jk26p4slmo8": "team",
    "fldVaevdMZwPc2NVu": "role_title",
    "fldahdsbn22p7WeM2": "level",
    "fldpkBn8dAvZvyTyO": "start_date",
    "fld8Wg5gwCEw6nCfw": "status",
}

# Field IDs for LOP Goals
LOP_GOAL_FIELDS = {
    "fldAdSTJLl35VfylP": "name",
    "flddRhzpx0wi212M7": "description",
    "fld7Ju6qIxq1M1yfa": "cascade_level",
    "fldhZOyxmcwr827GS": "department",
    "fldMhfBGbXeZsqqAo": "status",
    "fld7N04Iih14g2D6z": "fiscal_year",
}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def get_api_key() -> str:
    key = os.environ.get("AIRTABLE_API_KEY", "")
    if not key:
        log("ERROR: AIRTABLE_API_KEY not set")
        sys.exit(1)
    return key


def airtable_get(table_id: str, params: dict, api_key: str) -> list[dict]:
    """Fetch all pages from an Airtable table, returning raw records."""
    all_records: list[dict] = []
    offset = None

    while True:
        p = dict(params)
        if offset:
            p["offset"] = offset

        url = f"{BASE_URL}/{table_id}?{urllib.parse.urlencode(p, doseq=True)}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {api_key}",
        })

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            log(f"ERROR: Airtable API {e.code}: {body}")
            sys.exit(1)

        all_records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        time.sleep(0.25)

    return all_records


def fetch_employee(person_name: str, api_key: str) -> dict | None:
    """Fetch a single employee by name. Returns mapped dict or None."""
    log(f"Fetching employee: {person_name}")

    params = {
        "filterByFormula": f"{{employee_name}}='{person_name}'",
        "fields[]": list(EMPLOYEE_FIELDS.keys()),
        "returnFieldsByFieldId": "true",
    }

    records = airtable_get(EMPLOYEES_TABLE, params, api_key)

    if not records:
        return None

    if len(records) > 1:
        log(f"WARNING: {len(records)} employees match '{person_name}', using first")

    raw = records[0].get("fields", {})
    employee = {}
    for fid, key in EMPLOYEE_FIELDS.items():
        val = raw.get(fid)
        # Flatten single-select values (already strings) and skip linked records
        if isinstance(val, list):
            val = val[0] if val else None
        employee[key] = val

    return employee


def fetch_lop_goals(person_name: str, api_key: str) -> list[dict]:
    """Fetch LOP goals owned by a person. ARRAYJOIN on owner returns display names."""
    log(f"Fetching LOP goals for: {person_name}")

    time.sleep(0.25)

    params = {
        "filterByFormula": f"FIND('{person_name}', ARRAYJOIN({{owner}}, ','))",
        "fields[]": list(LOP_GOAL_FIELDS.keys()),
        "returnFieldsByFieldId": "true",
    }

    records = airtable_get(LOP_GOALS_TABLE, params, api_key)

    goals = []
    for rec in records:
        raw = rec.get("fields", {})
        goal = {}
        for fid, key in LOP_GOAL_FIELDS.items():
            val = raw.get(fid)
            if isinstance(val, list):
                val = val[0] if val else None
            goal[key] = val
        goals.append(goal)

    return goals


def main() -> None:
    if len(sys.argv) < 2:
        log("Usage: fetch_airtable_people_ops.py <person_name>")
        sys.exit(1)

    person_name = sys.argv[1]
    api_key = get_api_key()

    employee = fetch_employee(person_name, api_key)
    if employee is None:
        log(f"WARNING: No employee found for '{person_name}'")

    lop_goals = fetch_lop_goals(person_name, api_key)
    log(f"Found {len(lop_goals)} LOP goal(s)")

    result = {
        "employee": employee,
        "lop_goals": lop_goals,
    }

    json.dump(result, sys.stdout, indent=2, default=str)
    print()  # trailing newline


if __name__ == "__main__":
    main()
