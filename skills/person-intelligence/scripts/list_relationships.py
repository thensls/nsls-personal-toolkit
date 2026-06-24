#!/usr/bin/env python3
"""list_relationships.py — compose the set of relationships to track biweekly.

The biweekly sweep needs to know which people to fetch data for. This script
composes that set from three sources:

  1. The operating user's direct reports (from org-chart.json `manages` field)
  2. People who share the user's manager (peer ring), if INCLUDE_MANAGEMENT_PEERS=1
  3. Names listed in KEY_RELATIONSHIPS env var (contractors, family, externals)

For each tracked person, the script returns name, email, slack ID (when known),
and the tracking_reason so downstream code can apply the right coaching frame.

No Airtable API key is required. Set AIRTABLE_API_KEY=invalid if you want to
verify that.

Usage:
    python3.12 list_relationships.py
    OPERATING_USER_EMAIL=someone@nsls.org python3.12 list_relationships.py

Output:
    {
      "operating_user": {"name": "Kevin Prentiss", "email": "...", ...},
      "relationships": [
        {
          "name": "Adam Stone",
          "email": "astone@nsls.org",
          "slack": "U...",
          "tracking_reason": "direct_report"
        },
        ...
      ],
      "warnings": [...]
    }
"""

import json
import os
import sys
from pathlib import Path

# Import resolve_user from the same directory.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import load_dotenv_local  # noqa: E402,F401  — load .env into os.environ for cron/non-interactive runs
import resolve_user  # noqa: E402


def parse_key_relationships(raw):
    """Parse KEY_RELATIONSHIPS env var. Accepts comma or newline separators."""
    if not raw:
        return []
    names = []
    for chunk in raw.replace("\n", ",").split(","):
        name = chunk.strip()
        if name:
            names.append(name)
    return names


def find_by_name(employees, name):
    """Case-insensitive name match in the org chart."""
    for emp in employees:
        if emp.get("name", "").lower() == name.lower():
            return emp
    return None


def find_peers(employees, user_manager):
    """Return employees who share the user's manager (excluding the user)."""
    if not user_manager:
        return []
    peers = []
    for emp in employees:
        if emp.get("manager", "") == user_manager:
            peers.append(emp)
    return peers


def main():
    path = resolve_user.find_org_chart()
    if path is None:
        print(
            "ERROR: org-chart.json not found. See resolve_user.py for paths checked.",
            file=sys.stderr,
        )
        sys.exit(2)

    employees = resolve_user.load_org_chart(path)
    email = resolve_user.get_user_email()
    if not email:
        print(
            "ERROR: neither OPERATING_USER_EMAIL nor BUILDER_EMAIL is set.",
            file=sys.stderr,
        )
        sys.exit(1)

    user = resolve_user.resolve(email, employees)
    warnings = []

    operating_user_block = {
        "email": email,
        "found_in_org_chart": user is not None,
    }
    if user:
        operating_user_block.update(
            {
                "name": user.get("name", ""),
                "slack": user.get("slack", ""),
                "manager": user.get("manager", ""),
            }
        )
    else:
        warnings.append(
            f"{email} not in org-chart.json — using KEY_RELATIONSHIPS only"
        )

    relationships = []
    seen_emails = set()
    seen_names = set()

    def add(emp, reason):
        name = emp.get("name", "")
        emp_email = emp.get("email", "")
        # Deduplicate by email when known, by name otherwise.
        key_email = emp_email.lower() if emp_email else None
        key_name = name.lower()
        if key_email and key_email in seen_emails:
            return
        if not key_email and key_name in seen_names:
            return
        if key_email:
            seen_emails.add(key_email)
        seen_names.add(key_name)
        relationships.append(
            {
                "name": name,
                "email": emp_email,
                "slack": emp.get("slack", ""),
                "title": emp.get("title", ""),
                "department": emp.get("department", ""),
                "tracking_reason": reason,
            }
        )

    # 1. Direct reports.
    if user:
        for report_name in user.get("manages", []) or []:
            emp = find_by_name(employees, report_name)
            if emp:
                add(emp, "direct_report")
            else:
                warnings.append(
                    f"Direct report '{report_name}' (from manages[]) "
                    "not found as a separate record in org-chart.json"
                )

    # 2. Peers via shared manager.
    include_peers = os.environ.get("INCLUDE_MANAGEMENT_PEERS", "").strip() in {
        "1",
        "true",
        "yes",
    }
    if include_peers and user:
        for peer in find_peers(employees, user.get("manager", "")):
            if peer.get("email", "").lower() == email.lower():
                continue  # skip self
            add(peer, "management_peer")

    # 3. KEY_RELATIONSHIPS.
    key_names = parse_key_relationships(os.environ.get("KEY_RELATIONSHIPS", ""))
    for name in key_names:
        emp = find_by_name(employees, name)
        if emp:
            add(emp, "key_relationship")
        else:
            # Not in org chart — likely a contractor, family, external.
            # Add a minimal record; the sweep will work from Fathom + manual notes.
            relationships.append(
                {
                    "name": name,
                    "email": "",
                    "slack": "",
                    "title": "",
                    "department": "",
                    "tracking_reason": "key_relationship_external",
                }
            )

    output = {
        "operating_user": operating_user_block,
        "relationships": relationships,
        "relationship_count": len(relationships),
        "warnings": warnings,
        "org_chart_age_days": resolve_user.org_chart_age_days(path),
    }

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
