#!/usr/bin/env python3
"""resolve_user.py — locate the operating user's record in the org chart.

Reads OPERATING_USER_EMAIL from env (or BUILDER_EMAIL as fallback).
Looks up that email in the builder toolkit's org-chart.json.
Writes the matched record (or null + reason) to stdout as JSON.
Warnings to stderr.

The org chart is committed to ~/nsls-skills/nsls-builder-toolkit/_shared/context/org-chart.json
and is kept fresh by the builder toolkit's auto-update mechanism. No Airtable API
key is required.

Usage:
    python3.12 resolve_user.py
    OPERATING_USER_EMAIL=someone@nsls.org python3.12 resolve_user.py

Output (success):
    {
      "found": true,
      "name": "Kevin Prentiss",
      "email": "kprentiss@nsls.org",
      "slack": "U07TS8X7T7X",
      "title": "Ignite",
      "department": "Engineering",
      "manager": "Gary Tuerack",
      "manages": ["Brandon Evans", "..."],
      "org_chart_age_days": 2
    }

Output (no match):
    {
      "found": false,
      "email": "...",
      "reason": "email not in org-chart.json",
      "org_chart_age_days": 2
    }
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_dotenv_local  # noqa: E402,F401  — load .env into os.environ for cron/non-interactive runs


# Plugin-installed path first; dev clone fallback.
ORG_CHART_PATHS = [
    Path.home() / ".claude/local-plugins/nsls-builder-toolkit/_shared/context/org-chart.json",
    Path.home() / "nsls-skills/nsls-builder-toolkit/_shared/context/org-chart.json",
]

FRESHNESS_WARN_DAYS = 7


def find_org_chart():
    for path in ORG_CHART_PATHS:
        if path.exists():
            return path
    return None


def get_user_email():
    email = os.environ.get("OPERATING_USER_EMAIL", "").strip()
    if not email:
        email = os.environ.get("BUILDER_EMAIL", "").strip()
    return email or None


def load_org_chart(path):
    return json.loads(path.read_text())


def org_chart_age_days(path):
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - mtime).days


def resolve(email, employees):
    for emp in employees:
        if emp.get("email", "").lower() == email.lower():
            return emp
    return None


def main():
    email = get_user_email()
    if not email:
        print(
            "ERROR: neither OPERATING_USER_EMAIL nor BUILDER_EMAIL is set.\n"
            "  Set one in ~/nsls-skills/nsls-personal-toolkit/.env",
            file=sys.stderr,
        )
        sys.exit(1)

    path = find_org_chart()
    if path is None:
        print(
            "ERROR: org-chart.json not found at either:\n"
            f"  - {ORG_CHART_PATHS[0]}\n"
            f"  - {ORG_CHART_PATHS[1]}\n"
            "  Install the NSLS Builder Toolkit, or run /update to refresh it.",
            file=sys.stderr,
        )
        sys.exit(2)

    age = org_chart_age_days(path)
    if age > FRESHNESS_WARN_DAYS:
        print(
            f"WARN: org-chart.json is {age} days old at {path}.\n"
            "  Consider running /update or `cd ~/nsls-skills/nsls-builder-toolkit && git pull`.",
            file=sys.stderr,
        )

    employees = load_org_chart(path)
    record = resolve(email, employees)

    if record is None:
        output = {
            "found": False,
            "email": email,
            "reason": "email not in org-chart.json",
            "org_chart_age_days": age,
        }
    else:
        output = {
            "found": True,
            "name": record.get("name", ""),
            "email": record.get("email", ""),
            "slack": record.get("slack", ""),
            "title": record.get("title", ""),
            "department": record.get("department", ""),
            "manager": record.get("manager", ""),
            "manages": record.get("manages", []) or [],
            "org_chart_age_days": age,
        }

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
