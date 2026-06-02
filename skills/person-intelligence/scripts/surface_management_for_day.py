#!/usr/bin/env python3.12
"""
surface_management_for_day.py — the /open-day Management lane (Phase 2).

For the DIRECT REPORTS who are on today's calendar, surface the three jobs a
great manager does each touchpoint:
  🎉 Celebrate — a recent Signal win, named, so it gets said out loud
  🌱 Develop   — the pending coaching action tied to their goal
  🔧 Unblock   — a recurring Signal friction theme (with streak)

Plus per-person flags:
  - cadence: no Quick Notes in ≥2 weeks (the open-day threshold), or inactive
  - sentiment: novel low / recent reversal / friction streak ≥3
And a `top3_candidates` list: reports whose signal is urgent enough (streak ≥3 or
novel low) to claim a Top-3 Management slot today.

Scope: today's direct-report attendees only. The full-team friction scan is
open-week's job (signal_team_summary), not a daily 10-call sweep.

Usage:
    echo "Chelsea Byers\\nTrina Limpert" | surface_management_for_day.py --people-stdin
    surface_management_for_day.py --people "Chelsea Byers,Trina Limpert"

Reads SIGNAL via fetch_signal.py --fetch (token-direct). Honors SIGNAL_INGEST.
Output: JSON. Status → stderr.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE = Path.home() / ".cache" / "person-intelligence" / "coaching_actions.json"
CADENCE_GAP_DAYS = 14  # open-day threshold N=2 weeks


def log(m: str) -> None:
    print(f"[mgmt] {m}", file=sys.stderr)


def report_index() -> list[dict]:
    """Direct reports with aliases + signal slug. Resolves person-redirect stubs
    so a calendar attendee using a preferred name (Red Akasha) maps to the
    Rippling-name slug Signal knows (jana-amsellem)."""
    out = subprocess.check_output(
        ["python3.12", str(SCRIPT_DIR / "fetch_signal.py"), "--list-reports"],
        text=True, stderr=subprocess.DEVNULL,
    )
    reports = json.loads(out)  # [{name, slug}]
    vault = Path(os.environ.get("OBSIDIAN_VAULT_PATH", ""))
    people_dir = vault / "30-people"
    idx = []
    for r in reports:
        aliases = {r["name"]}
        # If the org-chart name is a redirect stub, add the preferred name as an alias.
        stub = people_dir / f"{r['name']}.md"
        if stub.exists():
            head = stub.read_text(encoding="utf-8")[:600]
            if "type: person-redirect" in head:
                m = re.search(r'preferred_name:\s*(.+)', head)
                if m:
                    aliases.add(m.group(1).strip())
                cm = re.search(r'canonical_profile:\s*"?\[\[([^\]]+)\]\]"?', head)
                if cm:
                    aliases.add(cm.group(1).strip())
        idx.append({"slug": r["slug"], "aliases": {a.lower() for a in aliases}, "display": r["name"]})
    return idx


def fetch_norm(slug: str, weeks: int = 4) -> dict | None:
    try:
        out = subprocess.run(
            ["python3.12", str(SCRIPT_DIR / "fetch_signal.py"), "--fetch", "--slug", slug, "--weeks", str(weeks)],
            capture_output=True, text=True, timeout=60,
        )
        if out.returncode != 0 or not out.stdout.strip():
            log(f"{slug}: fetch failed: {out.stderr.strip()[:100]}")
            return None
        return json.loads(out.stdout)
    except Exception as e:
        log(f"{slug}: {e}")
        return None


def load_coaching() -> dict:
    try:
        return json.loads(CACHE.read_text())
    except Exception:
        return {}


def develop_action(coaching: dict, aliases: set[str]) -> dict | None:
    for name, rec in coaching.items():
        if name.lower() in aliases:
            acts = [a for a in (rec.get("actions") or []) if a.get("status") in (None, "pending")]
            if not acts:
                continue
            acts.sort(key=lambda a: (a.get("source") != "coaching_goal", a.get("priority", 999)))
            a = acts[0]
            return {"text": a.get("text"), "goal_title": a.get("goal_title"), "dimension": a.get("dimension")}
    return None


def cadence_flag(norm: dict, today: dt.date) -> str | None:
    s = norm.get("sentiment") or {}
    if s.get("quick_notes_active") is False:
        return "not submitting Quick Notes"
    weeks = norm.get("submitted_weeks") or []
    if not weeks:
        return "no Quick Notes in window"
    try:
        last = dt.date.fromisoformat(weeks[0])
        if (today - last).days >= CADENCE_GAP_DAYS:
            return f"no Quick Notes since {weeks[0]} (≥2 wks)"
    except Exception:
        pass
    return None


def sentiment_flag(norm: dict) -> str | None:
    s = norm.get("sentiment") or {}
    if s.get("is_novel_low"):
        return "novel low"
    if (s.get("friction_streak_weeks") or 0) >= 3:
        return f"friction streak {s['friction_streak_weeks']} wks"
    if s.get("has_recent_reversal"):
        return "recent sentiment reversal"
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--people")
    ap.add_argument("--people-stdin", action="store_true")
    ap.add_argument("--weeks", type=int, default=4)
    args = ap.parse_args()

    if os.environ.get("SIGNAL_INGEST") != "1":
        print(json.dumps({"enabled": False, "reason": "SIGNAL_INGEST != 1"}))
        return

    if args.people_stdin:
        people = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
    elif args.people:
        people = [p.strip() for p in args.people.split(",") if p.strip()]
    else:
        people = []
    people_lc = {p.lower() for p in people}

    idx = report_index()
    today_reports = [r for r in idx if r["aliases"] & people_lc]
    log(f"{len(today_reports)} direct report(s) on today's calendar: "
        f"{', '.join(r['display'] for r in today_reports) or 'none'}")

    coaching = load_coaching()
    today = dt.date.today()
    buckets, top3 = [], []

    for r in today_reports:
        norm = fetch_norm(r["slug"], args.weeks)
        if not norm:
            continue
        wins = norm.get("wins") or []
        fr = norm.get("friction") or []
        streak = (norm.get("sentiment") or {}).get("friction_streak_weeks") or 0
        entry = {
            "person": r["display"],
            "celebrate": wins[0]["text"] if wins else None,
            "develop": develop_action(coaching, r["aliases"]),
            "unblock": ({"text": fr[0]["text"], "streak": streak} if fr else None),
            "cadence_flag": cadence_flag(norm, today),
            "sentiment_flag": sentiment_flag(norm),
        }
        buckets.append(entry)
        if streak >= 3 or (norm.get("sentiment") or {}).get("is_novel_low"):
            top3.append({"person": r["display"],
                         "why": entry["sentiment_flag"] or f"friction streak {streak} wks",
                         "friction": entry["unblock"]["text"] if entry["unblock"] else None})

    print(json.dumps({"enabled": True, "buckets": buckets, "top3_candidates": top3,
                      "today_people": people}, indent=2))


if __name__ == "__main__":
    main()
