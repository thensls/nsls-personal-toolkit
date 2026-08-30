#!/usr/bin/env python3
"""surface_actions_for_day.py — pick coaching actions for /open-day.

Called by /open-day with the names of people scheduled today (from the
calendar). Returns up to 3 actions to surface in the morning check-in,
prioritized by:
  1. Health-score-low (lower scores = higher priority)
  2. Action freshness (newer first)
  3. Direct meeting context (if a person has a meeting today, their
     actions outrank actions from people not scheduled today)

Also handles the decay + dismiss model:
  - Each surface increments times_surfaced and updates last_surfaced
  - times_surfaced >= 3 without status change → auto-stale (drops from rotation)
  - Snoozed actions skip until snooze_until passes
  - Status updates are persisted back to coaching_actions.json

Usage:
    python3.12 surface_actions_for_day.py --people "Adam Ferris,Warren Aldrich,Lauren Vance"
    python3.12 surface_actions_for_day.py --people-stdin   # read newline-separated names
    python3.12 surface_actions_for_day.py --weekly         # cap 5, broader scope

Output: JSON array of actions to surface, ready for /open-day to format.
Each action: {person, relationship_type, text, dimension, priority}
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "person-intelligence"
DEFAULT_ROLE_CACHE_DIR = Path.home() / ".cache" / "role-coach"
HARD_CAP_DAILY = 3
HARD_CAP_WEEKLY = 5
DECAY_THRESHOLD = 3  # times_surfaced before auto-stale (actions AND role cues)


def utc_today_iso():
    return date.today().isoformat()


def is_snoozed(action, today_iso):
    snooze = action.get("snooze_until")
    if not snooze:
        return False
    try:
        return snooze >= today_iso
    except (ValueError, TypeError):
        return False


def candidate_actions(cache_data, today_people, today_iso):
    """Build the candidate pool: pending actions, scheduled-people prioritized."""
    candidates = []
    today_lower = {p.lower() for p in today_people}

    for person, info in cache_data.items():
        for action in info.get("actions", []):
            if action.get("status") != "pending":
                continue
            if is_snoozed(action, today_iso):
                continue
            # Auto-stale check
            if action.get("times_surfaced", 0) >= DECAY_THRESHOLD:
                action["status"] = "stale"
                continue

            is_scheduled = person.lower() in today_lower
            candidates.append({
                "person": person,
                "relationship_type": action.get("relationship_type") or info.get("relationship_type"),
                "text": action["text"],
                "dimension": action.get("dimension"),
                "priority": action.get("priority", 50),
                "times_surfaced": action.get("times_surfaced", 0),
                "is_scheduled_today": is_scheduled,
                "goal_title": action.get("goal_title"),
                "_action_ref": action,
            })
    return candidates


def select_and_surface(candidates, cap, today_iso):
    """Distribute selections across people first, then stack if cap allows.

    Algorithm: round-robin by person. Sort candidates per-person by priority +
    freshness. First pass picks one action per scheduled person. If cap is
    still unfilled, do additional rounds. Within each round, scheduled-today
    people outrank unscheduled.
    """
    # Group by person
    by_person = {}
    for c in candidates:
        by_person.setdefault(c["person"], []).append(c)

    # Within each person, sort by priority desc, then times_surfaced asc.
    for actions in by_person.values():
        actions.sort(key=lambda c: (-c["priority"], c["times_surfaced"]))

    # Order people: scheduled-today first (sorted by best action's priority desc),
    # then unscheduled (also by best action's priority desc).
    def best_priority(person):
        return -by_person[person][0]["priority"] if by_person[person] else 0

    scheduled_people = sorted(
        [p for p in by_person if by_person[p][0]["is_scheduled_today"]],
        key=best_priority,
    )
    unscheduled_people = sorted(
        [p for p in by_person if not by_person[p][0]["is_scheduled_today"]],
        key=best_priority,
    )
    person_order = scheduled_people + unscheduled_people

    # Round-robin
    selected = []
    round_idx = 0
    while len(selected) < cap:
        added_this_round = False
        for person in person_order:
            if len(selected) >= cap:
                break
            if round_idx < len(by_person[person]):
                selected.append(by_person[person][round_idx])
                added_this_round = True
        if not added_this_round:
            break
        round_idx += 1

    for s in selected:
        ref = s["_action_ref"]
        ref["times_surfaced"] = ref.get("times_surfaced", 0) + 1
        ref["last_surfaced"] = today_iso

    return selected


def write_cache(cache_data, cache_path):
    cache_path.write_text(json.dumps(cache_data, indent=2))


def select_role_cue(role_cache_dir, today_iso):
    """Pick at most ONE pending role-coach cue from <role-cache>/cues.json.

    Arbitration rule (role-coach plan, Phase 2): role-coach gets at most one
    slot inside the existing hard caps; person-intelligence fills the rest.
    Decay mirrors the action model: times_surfaced >= DECAY_THRESHOLD -> stale.
    Mutates and persists cues.json (surfaced count, stale marks).
    """
    cues_path = role_cache_dir / "cues.json"
    if not cues_path.exists():
        return None
    try:
        data = json.loads(cues_path.read_text())
    except json.JSONDecodeError:
        return None

    cues = data.get("cues", [])
    dirty = False
    candidates = []
    for c in cues:
        if c.get("status") != "pending":
            continue
        if c.get("times_surfaced", 0) >= DECAY_THRESHOLD:
            c["status"] = "stale"
            dirty = True
            continue
        expires = c.get("expires")
        if expires and expires < today_iso:
            continue
        candidates.append(c)

    selected = None
    if candidates:
        # Newest first; ties broken by least-surfaced
        candidates.sort(key=lambda c: (c.get("created", ""), -c.get("times_surfaced", 0)), reverse=True)
        selected = candidates[0]
        selected["times_surfaced"] = selected.get("times_surfaced", 0) + 1
        selected["last_surfaced"] = today_iso
        dirty = True

    if dirty:
        cues_path.write_text(json.dumps(data, indent=2))

    if selected is None:
        return None
    return {
        "id": selected.get("id"),
        "pattern_id": selected.get("pattern_id"),
        "text": selected.get("text"),
        "lens": selected.get("lens"),
        "created": selected.get("created"),
    }


def read_sweep_status(cache_dir):
    """Return last sweep status for failure alerting."""
    status_path = cache_dir / "last-sweep-status.json"
    if not status_path.exists():
        return None
    try:
        return json.loads(status_path.read_text())
    except json.JSONDecodeError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--people",
        default="",
        help="Comma-separated names of people scheduled today",
    )
    parser.add_argument(
        "--people-stdin",
        action="store_true",
        help="Read newline-separated names from stdin",
    )
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Use weekly cap (5) instead of daily (3)",
    )
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--role-cache-dir", type=Path, default=DEFAULT_ROLE_CACHE_DIR)
    args = parser.parse_args()

    today_iso = utc_today_iso()
    cap = HARD_CAP_WEEKLY if args.weekly else HARD_CAP_DAILY

    # Role-coach pool: at most one cue, consuming one slot of the cap.
    role_cue = select_role_cue(args.role_cache_dir, today_iso)
    actions_cap = cap - 1 if role_cue else cap

    cache_path = args.cache_dir / "coaching_actions.json"
    if not cache_path.exists():
        # No coaching actions yet — role cue (if any) still surfaces.
        result = {
            "surfaced_actions": [],
            "role_cue": role_cue,
            "sweep_status": read_sweep_status(args.cache_dir),
            "hint": "no_cache",
        }
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    cache_data = json.loads(cache_path.read_text())

    if args.people_stdin:
        people = [line.strip() for line in sys.stdin if line.strip()]
    else:
        people = [p.strip() for p in args.people.split(",") if p.strip()]

    candidates = candidate_actions(cache_data, people, today_iso)
    selected = select_and_surface(candidates, actions_cap, today_iso)
    write_cache(cache_data, cache_path)

    result = {
        "surfaced_actions": [
            {
                "person": s["person"],
                "relationship_type": s["relationship_type"],
                "text": s["text"],
                "dimension": s["dimension"],
                "is_scheduled_today": s["is_scheduled_today"],
                "goal_title": s.get("goal_title"),
            }
            for s in selected
        ],
        "role_cue": role_cue,
        "candidates_total": len(candidates),
        "cap": cap,
        "today_people": people,
        "sweep_status": read_sweep_status(args.cache_dir),
    }
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
