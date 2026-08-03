#!/usr/bin/env python3
"""sweep_due.py — decide whether the biweekly sweep should run right now.

The scheduler (launchd on Mac, Task Scheduler on Windows) fires WEEKLY. This
script is what makes the cadence biweekly, because standard cron cannot express
"every other Sunday" — in the day-of-week field `0/2` expands to Sun/Tue/Thu/Sat,
not alternating Sundays. Rather than fight cron, we fire weekly and gate here on
the age of the last *finalized* sweep.

Reads ~/.cache/person-intelligence/last-sweep-status.json and exits with a code
the wrapper scripts branch on. Prints a one-line human reason to stdout every
time — a scheduled run must never be silent about why it did nothing.

Exit codes:
    0   DUE           — no recent sweep; run the full pipeline
    10  FRESH         — a finalized sweep is newer than the interval; do nothing
    11  NEEDS_FINALIZE— a recent sweep ran but was never finalized; run
                        `biweekly_sweep.py --finalize` only, do NOT re-sweep
    2   ERROR         — status file unreadable/malformed; treat as a real failure

Usage:
    python3.12 sweep_due.py [--interval-days 12] [--cache-dir PATH] [--today YYYY-MM-DD]
"""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "person-intelligence"
DEFAULT_INTERVAL_DAYS = 12

DUE = 0
ERROR = 2
FRESH = 10
NEEDS_FINALIZE = 11


def parse_status_date(status):
    """Return the date the last sweep covers, or None.

    Prefer `sweep_date` (the cycle the work belongs to). Fall back to
    `timestamp`, which on an unfinalized file is plan-time, not completion —
    still the best age signal available.
    """
    raw = status.get("sweep_date")
    if raw:
        return date.fromisoformat(str(raw)[:10])
    raw = status.get("timestamp")
    if raw:
        # Tolerate both "...+00:00" and a bare "Z" suffix.
        cleaned = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned).date()
    return None


def decide(status_path, interval_days, today):
    if not status_path.exists():
        return DUE, f"DUE: no status file at {status_path} — first sweep."

    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return ERROR, f"ERROR: cannot read {status_path}: {exc}"

    try:
        last = parse_status_date(status)
    except ValueError as exc:
        return ERROR, f"ERROR: unparseable date in {status_path}: {exc}"

    if last is None:
        return DUE, f"DUE: {status_path} has no sweep_date or timestamp."

    age = (today - last).days
    finalized = bool(status.get("finalized")) and bool(status.get("complete"))

    if age >= interval_days:
        state = "finalized" if finalized else "UNFINALIZED"
        return DUE, f"DUE: last sweep {last} is {age}d old ({state}), interval {interval_days}d."

    if not finalized:
        return (
            NEEDS_FINALIZE,
            f"NEEDS_FINALIZE: sweep {last} is only {age}d old but finalized="
            f"{status.get('finalized')} complete={status.get('complete')} — "
            "finalizing instead of re-sweeping.",
        )

    processed = status.get("relationships_processed", "?")
    return (
        FRESH,
        f"FRESH: finalized sweep {last} is {age}d old ({processed} relationships), "
        f"interval {interval_days}d — skipping.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval-days", type=int, default=DEFAULT_INTERVAL_DAYS)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--today", help="Override today's date (YYYY-MM-DD), for testing.")
    args = parser.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()
    code, reason = decide(
        args.cache_dir / "last-sweep-status.json", args.interval_days, today
    )
    print(reason)
    return code


if __name__ == "__main__":
    sys.exit(main())
