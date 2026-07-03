#!/usr/bin/env python3.12
"""
surface_management_for_week.py — the /open-week Management cadence lane (Phase 3).

One call to the weekly team summary becomes the manager's weekly operating rhythm:
  - celebrate_candidates — wins to recognize (1 per person)
  - develop_candidates   — pending coaching-goal actions across reports
  - unblock_candidates   — friction signals sorted by streak (recurring = priority)
  - cadence_alerts       — who didn't submit Quick Notes this week (chronic vs lapsed)
  - loop_closure         — streaks that just broke (resolved? → tell the person) and
                           emerging risk (novel lows, streaks just started)

The skill then asks the manager to set exactly THREE weekly intentions — one
celebrate, one develop, one unblock — on three DIFFERENT reports.

Sensitivity: friction quotes pass the same mechanical filter as the daily lane;
anything health/family/comp is dropped (team-summary quotes are already clarified,
this is defense in depth).

Usage: surface_management_for_week.py [--manager SLUG] [--week YYYY-MM-DD]
Honors SIGNAL_INGEST. Output: JSON. Status → stderr.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from fetch_signal import is_sensitive  # noqa: E402

CACHE = Path.home() / ".cache" / "person-intelligence" / "coaching_actions.json"


def log(m: str) -> None:
    print(f"[mgmt-week] {m}", file=sys.stderr)


def fetch_summary(manager: str | None, week: str | None) -> dict | None:
    cmd = ["python3.12", str(SCRIPT_DIR / "fetch_signal.py"), "--team-summary"]
    if manager:
        cmd += ["--manager", manager]
    if week:
        cmd += ["--week", week]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if out.returncode != 0 or not out.stdout.strip():
        log(f"team-summary fetch failed: {out.stderr.strip()[:120]}")
        return None
    return json.loads(out.stdout)


def develop_candidates() -> list[dict]:
    try:
        coaching = json.loads(CACHE.read_text())
    except Exception:
        return []
    out = []
    for name, rec in coaching.items():
        if rec.get("relationship_type") != "direct_report":
            continue
        for a in rec.get("actions") or []:
            if a.get("status") in (None, "pending") and a.get("source") == "coaching_goal":
                out.append({"person": name, "text": a.get("text"),
                            "goal_title": a.get("goal_title"), "dimension": a.get("dimension")})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manager")
    ap.add_argument("--week")
    args = ap.parse_args()

    if os.environ.get("SIGNAL_INGEST") != "1":
        print(json.dumps({"enabled": False, "reason": "SIGNAL_INGEST != 1"}))
        return

    s = fetch_summary(args.manager, args.week)
    if not s:
        print(json.dumps({"enabled": True, "available": False}))
        return

    # Celebrate: one standout win per person
    seen, celebrate = set(), []
    for w in s.get("wins") or []:
        p = (w.get("person") or {}).get("name")
        if p and p not in seen:
            seen.add(p)
            celebrate.append({"person": p, "win": w.get("body")})

    # Unblock: friction sorted by streak desc, sensitivity-screened
    unblock, dropped = [], 0
    for f in s.get("friction_signals") or []:
        q = f.get("quote", "")
        if is_sensitive(q):
            dropped += 1
            continue
        unblock.append({"person": (f.get("person") or {}).get("name"),
                        "quote": q, "streak": f.get("streak_weeks", 0)})
    unblock.sort(key=lambda x: x["streak"], reverse=True)

    # Cadence: who didn't submit
    cadence = []
    for p in s.get("not_submitted_this_week") or []:
        lifetime = p.get("lifetime_submissions", 0)
        cadence.append({"person": p.get("preferred_name") or p.get("name"),
                        "kind": "chronic (rarely submits)" if lifetime <= 2 else "lapsed this week",
                        "lifetime": lifetime})

    # Loop-closure + emerging risk from analytics deltas
    d = (s.get("analytics") or {}).get("deltas") or {}
    loop = {
        "resolved_check": [{"person": (x.get("person") or {}).get("name")}
                           for x in d.get("just_broken_streaks") or []],
        "emerging": (
            [{"person": (x.get("person") or {}).get("name"), "why": "novel low"} for x in d.get("novel_lows") or []]
            + [{"person": (x.get("person") or {}).get("name"), "why": f"friction streak {x.get('friction_streak_weeks')} wks (just started)"}
               for x in d.get("just_started_streaks") or []]
        ),
    }

    print(json.dumps({
        "enabled": True, "available": True,
        "week_label": s.get("week_label"), "team_size": s.get("team_size"),
        "submitted": len(s.get("submitted_this_week") or []),
        "wins_count": s.get("wins_count"),
        "celebrate_candidates": celebrate,
        "develop_candidates": develop_candidates(),
        "unblock_candidates": unblock,
        "cadence_alerts": cadence,
        "loop_closure": loop,
        "sensitive_dropped": dropped,
    }, indent=2))


if __name__ == "__main__":
    main()
