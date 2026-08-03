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

SIGNAL_EXCLUDE = {
    n.strip() for n in os.environ.get("SIGNAL_EXCLUDE", "Cory Capoccia").split(",") if n.strip()
}


def build_redirect_map(vault_path):
    """Map each `type: person-redirect` stub's name -> the canonical (preferred) name.

    Mirrors sync_obsidian_frontmatter.build_redirect_map and
    biweekly_sweep.resolve_canonical_name. Any place that turns an org-chart name into a
    vault identity has to go through this, or the Rippling spelling wins.
    """
    import re

    mapping = {}
    people_dir = vault_path / "30-people" if vault_path and str(vault_path) != "." else None
    if not people_dir or not people_dir.is_dir():
        return mapping
    for path in sorted(people_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not re.search(r"^type:\s*person-redirect\s*$", text, re.MULTILINE):
            continue
        canonical = None
        for pat in (
            r"^preferred_name:[ \t]*(\S[^\n]*)$",
            r'^canonical_profile:[ \t]*"?\[\[([^\]]+)\]\]"?',
            r'^canonical:[ \t]*"?\[\[([^\]]+)\]\]"?',
        ):
            m = re.search(pat, text, re.MULTILINE)
            if m:
                canonical = m.group(1).strip().strip('"').strip("'")
                break
        if not canonical or canonical == path.stem:
            continue
        mapping[path.stem] = canonical
        m = re.search(r"^rippling_name:[ \t]*(\S[^\n]*)$", text, re.MULTILINE)
        if m:
            rn = m.group(1).strip().strip('"').strip("'")
            if rn and rn != canonical:
                mapping[rn] = canonical
    return mapping


def preferred_name(name, redirect_map):
    seen = set()
    while name in redirect_map and name not in seen:
        seen.add(name)
        name = redirect_map[name]
    return name


def is_signal_eligible(name, email, tracking_reason):
    """True when a tracked person plausibly has NSLS Signal Quick Notes.

    Signal is coaching/context only; this only decides whether to ATTEMPT a
    fetch. A no-match still degrades to empty in fetch_signal.py.
    """
    email = (email or "").strip().lower()
    if not email.endswith("@nsls.org"):
        return False
    if tracking_reason == "key_relationship_external":
        return False
    if name in SIGNAL_EXCLUDE:
        return False
    return True


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

    # Preferred-name map, built from the vault's `type: person-redirect` stubs.
    # Rippling stores formal names ("Jana Amsellem", "Jordyn Tannenbaum") for people who go
    # by something else. Without this, the org-chart name and the preferred name are added as
    # TWO relationships — dedup is by email, and the key-relationship entry usually has no
    # email to match on — which double-lists the person and leaves a phantom "never
    # assessed" row in the health dashboard.
    redirect_map = build_redirect_map(Path(os.environ.get("OBSIDIAN_VAULT_PATH", "")).expanduser())

    def add(emp, reason):
        name = preferred_name(emp.get("name", ""), redirect_map)
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
    for raw_name in key_names:
        # Resolve to the preferred name FIRST. A key relationship named by its Rippling
        # spelling (or already picked up as a report/peer under the preferred name) must not
        # be added a second time.
        name = preferred_name(raw_name, redirect_map)
        emp = find_by_name(employees, raw_name) or find_by_name(employees, name)
        if emp:
            add(emp, "key_relationship")
        else:
            # Not in org chart — likely a contractor, coach, board member, family.
            # Add a minimal record; the sweep works from Fathom + manual notes.
            # Route through the same dedup gate `add()` uses, or an org-chart entry
            # already added under the preferred name gets duplicated here.
            if name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
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

    # Tag all relationships with signal_eligible before output.
    for rel in relationships:
        rel["signal_eligible"] = is_signal_eligible(
            rel.get("name", ""), rel.get("email", ""), rel.get("tracking_reason", "")
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
