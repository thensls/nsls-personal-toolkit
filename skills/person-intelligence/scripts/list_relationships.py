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
      "operating_user": {"name": "Marcus Vance", "email": "...", ...},
      "relationships": [
        {
          "name": "Adam Ferris",
          "email": "aferris@nsls.org",
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
    n.strip() for n in os.environ.get("SIGNAL_EXCLUDE", "Dana Ashford").split(",") if n.strip()
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


def build_untracked_set(vault_path):
    """Names the vault has explicitly marked `tracked: false` (archived/out-of-scope).

    The roster is built from org-chart.json, which is a Rippling mirror and the arbiter of
    *current-staff* status. It is NOT the arbiter of *tracked-relationship* status: it carries
    departed contractors and people who were never a managed relationship, and it grew a batch
    of `title: Contractor` rows in Aug 2026 that re-added four people the vault had already
    resolved. Archiving a profile has to actually remove someone from the sweep, or the archive
    is decoration.

    Reads `30-people/**` (including `_archive/`) so the private vault stays the control surface
    and no person's name is ever hardcoded into this repo.
    """
    import re as _re

    untracked = set()
    if not vault_path or str(vault_path) == ".":
        return untracked
    people_dir = vault_path / "30-people"
    if not people_dir.is_dir():
        return untracked
    for path in sorted(people_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # Only the leading YAML frontmatter block counts. Scanning a fixed-size prefix was
        # wrong in both directions: prose in the BODY saying `tracked: false` silently
        # dropped an active relationship, and frontmatter longer than the cutoff was
        # truncated so a genuinely archived person stayed in the roster.
        fm = _frontmatter(text)
        if fm is None:
            continue
        if not _re.search(r"^tracked:[ \t]*false[ \t]*$", fm, _re.MULTILINE | _re.IGNORECASE):
            continue
        untracked.add(path.stem.lower())
        for m in _re.finditer(r"^email(?:_alt)?:[ \t]*(\S+)[ \t]*$", fm, _re.MULTILINE):
            untracked.add(m.group(1).strip().strip('"').strip("'").lower())
    return untracked


def _frontmatter(text):
    """Return the leading YAML frontmatter body, or None when the file has none."""
    import re as _re

    m = _re.match(r"\A\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", text, _re.DOTALL)
    return m.group(1) if m else None


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
    # Rippling stores formal names ("Jana Kessler", "Jordyn Sutter") for people who go
    # by something else. Without this, the org-chart name and the preferred name are added as
    # TWO relationships — dedup is by email, and the key-relationship entry usually has no
    # email to match on — which double-lists the person and leaves a phantom "never
    # assessed" row in the health dashboard.
    redirect_map = build_redirect_map(Path(os.environ.get("OBSIDIAN_VAULT_PATH", "")).expanduser())
    _vault = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "")).expanduser()
    untracked = build_untracked_set(_vault)
    # Names that some redirect points AT — i.e. canonical identities the vault has declared.
    # Any org-chart record resolving to one of these IS that person, whichever order the
    # records happen to arrive in. Precomputed once; add() runs in a loop.
    redirect_targets = {v.lower() for v in redirect_map.values()}

    def add(emp, reason):
        raw_name = emp.get("name", "")
        name = preferred_name(raw_name, redirect_map)
        # True only when the vault's redirect map actually canonicalized this record onto
        # another identity. Two unrelated people who merely share an ordinary name are NOT
        # the same human, and merging them would silently drop the second from the sweep.
        via_redirect = name != raw_name
        emp_email = emp.get("email", "")
        # Deduplicate by email when known, by name otherwise.
        key_email = emp_email.lower() if emp_email else None
        key_name = name.lower()
        # Explicitly untracked (archived / out-of-scope) — the vault overrides the org chart.
        if key_name in untracked or (key_email and key_email in untracked):
            warnings.append(
                f"Skipped '{name}' ({reason}): marked `tracked: false` in the vault. "
                "org-chart.json still lists them; the archive is the arbiter here."
            )
            return
        if key_email and key_email in seen_emails:
            return
        # Dedup by resolved name when any of these proves the records are one human:
        #   * this record was itself canonicalized by a vault redirect, or
        #   * there is no email to key on, or
        #   * the resolved name is a redirect TARGET — a canonical identity the vault has
        #     declared, so anything landing on it is that person.
        # One person can hold two org-chart emails (an agency address plus a work one), and
        # email-only dedup let both through and double-listed them under one name.
        #
        # The redirect-target check is what makes this ORDER-INDEPENDENT. With only the
        # via_redirect test, "redirected record first, canonical record second" left both
        # tracked (the second has an email and no redirect of its own), while the reverse
        # order merged correctly — so the roster size depended on org-chart ordering.
        #
        # But do NOT merge on a bare name collision between two records that each carry a
        # DIFFERENT known email, where neither was linked by a redirect and the name is not a
        # declared canonical identity — those are two people who happen to share a name, and
        # merging drops the second one silently.
        if key_name in seen_names and (
            via_redirect or not key_email or key_name in redirect_targets
        ):
            warnings.append(
                f"Merged a second org-chart record onto '{name}' ({reason}): "
                f"email {emp_email or '<none>'} resolves to an already-tracked person"
                f"{' via a vault redirect' if via_redirect else ''}."
            )
            return
        if key_name in seen_names:
            warnings.append(
                f"NAME COLLISION: '{name}' ({reason}, {emp_email}) shares a name with an "
                "already-tracked person but has a different email and no vault redirect "
                "linking them. Tracking both. If they ARE the same person, add a "
                "`type: person-redirect` stub; if not, no action needed."
            )
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
            # Same untracked gate `add()` applies. Without this, archiving someone who is
            # in KEY_RELATIONSHIPS but absent from the org chart (a departed contractor,
            # a former coach) left them in the sweep forever — the exact class of bug the
            # gate exists to close, reintroduced through the one branch that skips add().
            if name.lower() in untracked:
                warnings.append(
                    f"Skipped '{name}' (key_relationship_external): marked `tracked: false` "
                    "in the vault. Remove them from KEY_RELATIONSHIPS to stop the lookup too."
                )
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
        "untracked_excluded_count": len(
            [w for w in warnings if "marked `tracked: false`" in w]
        ),
        "records_merged_count": len(
            [w for w in warnings if "Merged a second org-chart record" in w]
        ),
        "org_chart_age_days": resolve_user.org_chart_age_days(path),
    }

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
