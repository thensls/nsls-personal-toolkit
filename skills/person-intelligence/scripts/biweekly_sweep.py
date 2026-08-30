#!/usr/bin/env python3
"""biweekly_sweep.py — orchestrator for the recurring person-intelligence sweep.

This script does the deterministic plumbing of a biweekly run:

  1. Resolve the operating user from org-chart.json.
  2. Compose the tracked relationship set (direct reports + peers + key relations).
  3. For each relationship, determine what new Fathom meetings exist since
     last-synthesized (and a flag for Slack/Gmail availability — actual MCP
     calls happen in the orchestrating Claude session).
  4. Write a manifest JSON to ~/.cache/person-intelligence/ that the Claude
     orchestrator consumes to run the per-person synthesis.
  5. Write last-sweep-status.json on completion (or on partial failure) so
     /open-day can surface a one-line status.

The script is idempotent: re-running on the same day reads the existing
manifest and reports what's already complete so mid-stream interruptions
can resume.

Usage:
    python3.12 biweekly_sweep.py [--resume] [--cache-dir PATH]

Env:
    OPERATING_USER_EMAIL — required (or BUILDER_EMAIL fallback)
    OBSIDIAN_VAULT_PATH — required to read each profile's last-synthesized date
    FATHOM_API_KEY — required to query Fathom for new meetings
    KEY_RELATIONSHIPS, INCLUDE_MANAGEMENT_PEERS — optional, see resolve_user.py
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import load_dotenv_local  # noqa: E402,F401  — load .env into os.environ for cron/non-interactive runs
import resolve_user  # noqa: E402
import list_relationships  # noqa: E402

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "person-intelligence"


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def resolve_canonical_name(vault_path, person_name):
    """If a person's profile is a redirect stub, return the canonical name it points to.

    Rippling stores a formal name (e.g. "Jana Kessler") for someone who goes by a
    preferred name (e.g. "Robin Alder"). The formal-name file is a
    `type: person-redirect` stub pointing at the canonical profile. Following it
    keeps the manifest from double-listing the person and from false-flagging the
    stub as "never synthesized." Returns the original name when there's no redirect.
    """
    candidate = vault_path / "30-people" / f"{person_name}.md"
    try:
        text = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return person_name
    if not re.search(r"^type:\s*person-redirect\s*$", text, re.MULTILINE):
        return person_name
    m = re.search(r"^preferred_name:[ \t]*(\S[^\n]*)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    m = re.search(r'^canonical_profile:[ \t]*"?\[\[([^\]]+)\]\]"?', text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return person_name


def read_last_synthesized(vault_path, person_name):
    """Read the last-synthesized date from a person's Obsidian profile frontmatter.

    Returns ISO date string (YYYY-MM-DD) or None if not found / no profile.
    Follows redirect stubs to the canonical profile first.
    """
    person_name = resolve_canonical_name(vault_path, person_name)
    candidate = vault_path / "30-people" / f"{person_name}.md"
    if not candidate.exists():
        return None
    try:
        text = candidate.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    # Constrain whitespace to spaces/tabs only (not newlines) so an empty value
    # doesn't silently capture the next YAML key.
    m = re.search(r"^last-synthesized:[ \t]*(\S[^\n]*)$", text, re.MULTILINE)
    if m:
        value = m.group(1).strip()
        return value or None
    return None


def list_fathom_meetings_since(email, since_date):
    """Call fetch_fathom_1on1s.py --list to count new meetings since a date.

    Returns dict: {"count": N, "meetings": [...], "error": str | None}.
    A None since_date means "all meetings" (first sync for this person).
    """
    if not email:
        return {"count": 0, "meetings": [], "error": "no email", "skipped": True}

    cmd = [
        "python3.12",
        str(SCRIPT_DIR / "fetch_fathom_1on1s.py"),
        "--email",
        email,
        "--list",
        "--json",  # emit JSON lines to stdout (we parse result.stdout below)
    ]
    if since_date:
        cmd.extend(["--after", since_date])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            # Only the first call populates the shared light cache (one windowed
            # fetch); every later person filters that cache in <1s. Generous ceiling
            # so the cache-populating call can finish even on a slow API day.
            timeout=240,
        )
    except subprocess.TimeoutExpired:
        return {"count": 0, "meetings": [], "error": "fathom fetch timed out"}

    if result.returncode != 0:
        return {
            "count": 0,
            "meetings": [],
            "error": f"fathom fetch exited {result.returncode}: {result.stderr.strip()[:200]}",
        }

    meetings = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
            meetings.append({
                "id": m.get("id") or m.get("meeting_id"),
                "date": m.get("scheduled_start_time") or m.get("created_at") or m.get("date"),
                "title": m.get("title", ""),
            })
        except json.JSONDecodeError:
            continue

    return {"count": len(meetings), "meetings": meetings, "error": None}


def plan_signal(rel, signal_available):
    """Set signal_ingest_planned + signal_slug on a relationship dict. Pure/testable.

    Computes signal_eligible if the caller didn't already tag it (the biweekly
    sweep builds relationship dicts inline and does not run list_relationships.main()).
    """
    eligible = rel.get("signal_eligible")
    if eligible is None:
        eligible = list_relationships.is_signal_eligible(
            rel.get("name", ""), rel.get("email", ""), rel.get("tracking_reason", "")
        )
        rel["signal_eligible"] = eligible
    rel["signal_ingest_planned"] = bool(signal_available) and bool(eligible)
    if rel["signal_ingest_planned"]:
        rel["signal_slug"] = (
            rel["name"].lower().replace("'", "").replace(".", "").replace(" ", "-")
        )
    return rel


def build_manifest(vault_path, cache_dir):
    """Build the manifest of what the sweep needs to process."""
    # 1. Identity + relationship set
    chart_path = resolve_user.find_org_chart()
    if chart_path is None:
        return None, "org-chart.json not found"

    employees = resolve_user.load_org_chart(chart_path)
    email = resolve_user.get_user_email()
    if not email:
        return None, "OPERATING_USER_EMAIL not set"

    user_record = resolve_user.resolve(email, employees)

    # 2. Compose relationship list via list_relationships.py logic
    #    (re-implementing inline to avoid subprocess overhead)
    rel_set = []
    seen_emails = set()
    seen_names = set()

    def add(emp, reason):
        name = resolve_canonical_name(vault_path, emp.get("name", ""))
        emp_email = emp.get("email", "")
        key_email = emp_email.lower() if emp_email else None
        key_name = name.lower()
        if key_email and key_email in seen_emails:
            return
        if not key_email and key_name in seen_names:
            return
        if key_email:
            seen_emails.add(key_email)
        seen_names.add(key_name)
        rel_set.append({
            "name": name,
            "email": emp_email,
            "slack": emp.get("slack", ""),
            "title": emp.get("title", ""),
            "department": emp.get("department", ""),
            "tracking_reason": reason,
            "relationship_type": (
                "direct_report" if reason == "direct_report"
                else "peer" if reason == "management_peer"
                else "key_relationship"
            ),
        })

    if user_record:
        for report_name in user_record.get("manages", []) or []:
            emp = list_relationships.find_by_name(employees, report_name)
            if emp:
                add(emp, "direct_report")

        if os.environ.get("INCLUDE_MANAGEMENT_PEERS", "").strip() in {"1", "true", "yes"}:
            for peer in list_relationships.find_peers(employees, user_record.get("manager", "")):
                if peer.get("email", "").lower() != email.lower():
                    add(peer, "management_peer")

    # The user's own manager — upward relationship
    if user_record and user_record.get("manager"):
        mgr_name = user_record["manager"]
        mgr_emp = list_relationships.find_by_name(employees, mgr_name)
        if mgr_emp:
            # Override relationship_type to "manager"
            mgr_email = mgr_emp.get("email", "")
            if mgr_email.lower() not in seen_emails:
                rel_set.append({
                    "name": mgr_emp.get("name", ""),
                    "email": mgr_email,
                    "slack": mgr_emp.get("slack", ""),
                    "title": mgr_emp.get("title", ""),
                    "department": mgr_emp.get("department", ""),
                    "tracking_reason": "manager",
                    "relationship_type": "manager",
                })
                seen_emails.add(mgr_email.lower())

    # Key relationships from env
    for name in list_relationships.parse_key_relationships(
        os.environ.get("KEY_RELATIONSHIPS", "")
    ):
        emp = list_relationships.find_by_name(employees, name)
        if emp:
            add(emp, "key_relationship")
        else:
            canonical = resolve_canonical_name(vault_path, name)
            if canonical.lower() in seen_names:
                continue
            seen_names.add(canonical.lower())
            rel_set.append({
                "name": canonical,
                "email": "",
                "slack": "",
                "title": "",
                "department": "",
                "tracking_reason": "key_relationship_external",
                "relationship_type": "key_relationship",
            })

    # 3. For each relationship, check Fathom for new meetings since last-synthesized
    print(f"Checking Fathom for {len(rel_set)} relationships...", file=sys.stderr)

    fathom_available = bool(os.environ.get("FATHOM_API_KEY"))
    slack_available = not os.environ.get("SKIP_SLACK_INGEST")
    gmail_available = not os.environ.get("SKIP_GMAIL_INGEST")
    # Signal: gated by eligibility (see list_relationships.is_signal_eligible), not
    # relationship type, and only when opted in. plan_signal() computes eligibility
    # on this inline sweep path since list_relationships.main() never runs here.
    # The orchestrator runs `fetch_signal.py --fetch --slug <signal_slug>` for each
    # rel where signal_ingest_planned is true and folds the result into the
    # synthesize payload.
    signal_available = os.environ.get("SIGNAL_INGEST") == "1"

    for i, rel in enumerate(rel_set, 1):
        last_synth = read_last_synthesized(vault_path, rel["name"])
        rel["last_synthesized"] = last_synth
        rel["has_obsidian_file"] = last_synth is not None or (vault_path / "30-people" / f"{rel['name']}.md").exists()

        print(f"  [{i}/{len(rel_set)}] {rel['name']} (since {last_synth or 'never'})...", file=sys.stderr)

        if fathom_available and rel["email"]:
            fathom_result = list_fathom_meetings_since(rel["email"], last_synth)
            rel["fathom"] = fathom_result
        else:
            rel["fathom"] = {
                "count": 0,
                "meetings": [],
                "error": "no FATHOM_API_KEY" if not fathom_available else "no email",
                "skipped": True,
            }

        rel["slack_ingest_planned"] = slack_available and bool(rel.get("slack"))
        rel["gmail_ingest_planned"] = gmail_available and bool(rel.get("email"))
        plan_signal(rel, signal_available)

    # 4. Assemble manifest
    manifest = {
        "manifest_version": 1,
        "generated_at": utc_now_iso(),
        "operating_user": {
            "email": email,
            "name": user_record.get("name") if user_record else None,
            "manager": user_record.get("manager") if user_record else None,
            "found_in_org_chart": user_record is not None,
        },
        "ingest_sources_available": {
            "fathom": fathom_available,
            "slack": slack_available,
            "gmail": gmail_available,
            "signal": signal_available,
        },
        "relationship_count": len(rel_set),
        "relationships": rel_set,
        "completed_relationships": [],  # populated as each is processed
    }

    return manifest, None


def write_manifest(manifest, cache_dir, sweep_date):
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"biweekly-sweep-{sweep_date}.manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    return path


def write_status(cache_dir, status):
    """Write last-sweep-status.json for /open-day to consume."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "last-sweep-status.json"
    path.write_text(json.dumps(status, indent=2))


def count_synthesized_today(vault_path, sweep_date):
    """Count profiles whose health_last_assessed equals sweep_date.

    This is the ground truth for 'did the sweep actually do work'. The manifest's
    completed_relationships list is written at PLAN time and is always empty, so
    it can never answer the question.
    """
    people_dir = vault_path / "30-people"
    names = []
    if not people_dir.is_dir():
        return names
    for f in sorted(people_dir.glob("*.md")):
        try:
            text = f.read_text()
        except Exception:
            continue
        for line in text.splitlines()[:40]:
            if line.startswith("health_last_assessed:"):
                if line.split(":", 1)[1].strip().strip('"\'') == sweep_date:
                    names.append(f.stem)
                break
    return names


def finalize(vault_path, cache_dir, sweep_date):
    """Recompute last-sweep-status.json from what is actually on disk.

    Run this as the LAST step of a sweep. Without it the status file keeps the
    baseline written at manifest-build time, which always reports
    relationships_processed: 0 and a timestamp from before any work happened.
    """
    # A missing or unreadable manifest is a real degradation, not a zero.
    # Defaulting `expected` to 0 would make `len(synthesized) >= expected`
    # vacuously true, certifying a damaged sweep as complete.
    manifest_path = cache_dir / f"biweekly-sweep-{sweep_date}.manifest.json"
    manifest = {}
    manifest_error = None
    if not manifest_path.exists():
        manifest_error = f"manifest not found: {manifest_path}"
    else:
        try:
            loaded = json.loads(manifest_path.read_text())
        except Exception as exc:
            manifest_error = f"manifest unreadable: {exc}"
        else:
            # Valid JSON is not necessarily an object. A bare array or string would
            # make manifest.get() raise, aborting finalize before write_status and
            # leaving the status file stale — the exact outcome this path exists to
            # prevent. Nothing below may raise; finalize must always write.
            if isinstance(loaded, dict):
                manifest = loaded
            else:
                manifest_error = (
                    f"manifest is {type(loaded).__name__}, expected object: {manifest_path}"
                )

    synthesized = count_synthesized_today(vault_path, sweep_date)
    expected = manifest.get("relationship_count", 0)
    # bool is an int subclass, so True would otherwise sail through as 1; a
    # negative count would make the "short count" check vacuously false and let
    # a nonsense manifest certify the sweep complete.
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
        manifest_error = (manifest_error or "") + (
            f" relationship_count is {expected!r}, expected a non-negative int;"
        ).strip()
        expected = 0
    pulse = vault_path / "30-people" / "_pulse" / f"{sweep_date}-team-pulse.md"

    problems = []
    if manifest_error:
        problems.append(manifest_error)
    if not synthesized:
        problems.append("finalize found 0 profiles stamped for this sweep_date")
    elif len(synthesized) < expected:
        problems.append(f"only {len(synthesized)} of {expected} relationships synthesized")
    if not pulse.exists():
        problems.append(f"team-pulse digest missing: {pulse.name}")

    # `complete` gates the scheduler's freshness check, so it has to mean
    # "nothing left to retry". A sweep that skipped the digest is not complete —
    # marking it so suppresses the next run and the digest is never produced.
    status = {
        "timestamp": utc_now_iso(),
        "sweep_date": sweep_date,
        "exit_code": 0 if not problems else 1,
        "error": None if not problems else "; ".join(problems),
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "relationships_processed": len(synthesized),
        "relationship_count": expected,
        "profiles_synthesized": synthesized,
        "team_pulse_written": pulse.exists(),
        "complete": not problems,
        "finalized": True,
    }
    write_status(cache_dir, status)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="If today's manifest exists, read it and report status rather than re-fetching",
    )
    parser.add_argument(
        "--finalize",
        action="store_true",
        help=(
            "Run as the LAST step of a sweep: recompute last-sweep-status.json from "
            "profiles actually stamped with health_last_assessed == sweep date. Without "
            "this, the status file keeps the plan-time baseline (relationships_processed: 0)."
        ),
    )
    parser.add_argument(
        "--sweep-date",
        default=None,
        help="Sweep date for --finalize (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"Cache directory (default: {DEFAULT_CACHE_DIR})",
    )
    args = parser.parse_args()

    vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        print("ERROR: OBSIDIAN_VAULT_PATH not set", file=sys.stderr)
        sys.exit(1)
    vault_path = Path(vault).expanduser()

    today = date.today().isoformat()

    if args.finalize:
        status = finalize(vault_path, args.cache_dir, args.sweep_date or today)
        json.dump(status, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(0 if status["exit_code"] == 0 else 1)

    manifest_path = args.cache_dir / f"biweekly-sweep-{today}.manifest.json"

    if args.resume and manifest_path.exists():
        print(f"Resuming from {manifest_path}", file=sys.stderr)
        manifest = json.loads(manifest_path.read_text())
        completed = len(manifest.get("completed_relationships", []))
        total = manifest.get("relationship_count", 0)
        print(f"Status: {completed}/{total} complete", file=sys.stderr)
    else:
        manifest, err = build_manifest(vault_path, args.cache_dir)
        if err:
            write_status(args.cache_dir, {
                "timestamp": utc_now_iso(),
                "exit_code": 1,
                "error": err,
                "relationships_processed": 0,
            })
            print(f"ERROR: {err}", file=sys.stderr)
            sys.exit(1)

        manifest_path = write_manifest(manifest, args.cache_dir, today)
        print(f"Manifest written to {manifest_path}", file=sys.stderr)

    # Write a baseline status — the orchestrator will update it as work completes
    write_status(args.cache_dir, {
        "timestamp": utc_now_iso(),
        "exit_code": 0,
        "error": None,
        "manifest_path": str(manifest_path),
        "relationships_processed": len(manifest.get("completed_relationships", [])),
        "relationship_count": manifest.get("relationship_count", 0),
    })

    # Print the manifest to stdout for the orchestrating Claude session
    json.dump(manifest, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
