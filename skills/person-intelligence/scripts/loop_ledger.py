#!/usr/bin/env python3.12
"""
loop_ledger.py — the cross-week loop-closure ledger (Phase 4).

A "loop" is a person's recurring-friction episode (Signal friction_streak ≥2 weeks),
keyed by slug + started_week so it survives week-to-week wording changes. Lifecycle:

    open ──(streak ends)──► resolved ──(you told the person)──► closed

The point is the gap between *resolved* and *closed*: a resolved-but-unclosed loop
means the friction stopped but you never told the person it was heard. Those roll
forward every week until you close them — that's the manager's highest-trust habit.

Durable store: $OBSIDIAN_VAULT_PATH/03-meta/loop-closure-ledger.json (persists +
iCloud-syncs; themes are sensitivity-screened before they're written).

Modes:
  --update            Reconcile against the latest team summary (default).
  --close "<name|slug>" [--note "..."]   Mark a person's resolved loop closed.
  --list              Print the ledger (open + resolved-unclosed + closed).
  --for "<names>"     Filter open/resolved-unclosed loops to these people (open-day).

Honors SIGNAL_INGEST. Output: JSON. Status → stderr.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from fetch_signal import is_sensitive  # noqa: E402

RECURRING_THRESHOLD = 2   # friction_streak_weeks that makes friction a tracked "loop"
LONG_OPEN_WEEKS = 3       # open this many weeks → P1 candidate


def ledger_path() -> Path:
    vault = Path(os.environ["OBSIDIAN_VAULT_PATH"])
    return vault / "03-meta" / "loop-closure-ledger.json"


def log(m: str) -> None:
    print(f"[loops] {m}", file=sys.stderr)


def load() -> dict:
    p = ledger_path()
    if p.exists():
        return json.loads(p.read_text())
    return {"version": 1, "updated_at": None, "loops": []}


def save(led: dict) -> None:
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(led, indent=2))


def open_loop_for(led: dict, slug: str) -> dict | None:
    return next((l for l in led["loops"] if l["slug"] == slug and l["status"] == "open"), None)


def slugify(name: str) -> str:
    return name.lower().replace("'", "").replace(".", "").replace(" ", "-")


def fetch_summary() -> dict | None:
    out = subprocess.run(
        ["python3.12", str(SCRIPT_DIR / "fetch_signal.py"), "--team-summary"],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0 or not out.stdout.strip():
        log(f"team-summary fetch failed: {out.stderr.strip()[:120]}")
        return None
    return json.loads(out.stdout)


def update(led: dict) -> dict:
    s = fetch_summary()
    if not s:
        return {"enabled": True, "available": False}
    week = s.get("week_of")

    # Recurring friction now: person slug -> {streak, themes (screened)}
    recurring: dict[str, dict] = {}
    for f in s.get("friction_signals") or []:
        streak = f.get("streak_weeks", 0)
        if streak < RECURRING_THRESHOLD:
            continue
        q = f.get("quote", "")
        if is_sensitive(q):
            continue
        slug = (f.get("person") or {}).get("slug")
        name = (f.get("person") or {}).get("name")
        if not slug:
            continue
        rec = recurring.setdefault(slug, {"name": name, "streak": streak, "themes": []})
        rec["streak"] = max(rec["streak"], streak)
        if q and q not in rec["themes"]:
            rec["themes"].append(q)

    # 1. Upsert open loops for everyone with recurring friction now.
    for slug, rec in recurring.items():
        loop = open_loop_for(led, slug)
        if loop is None:
            loop = {
                "id": f"{slug}:{week}", "slug": slug, "person": rec["name"],
                "started_week": week, "last_week": week, "status": "open",
                "streak_weeks": rec["streak"], "themes": list(rec["themes"]),
                "resolved_week": None, "closed_date": None, "closed_note": None,
                "surfaced_count": 0,
            }
            led["loops"].append(loop)
            log(f"opened loop {loop['id']} ({rec['name']})")
        else:
            loop["last_week"] = week
            loop["streak_weeks"] = rec["streak"]
            for t in rec["themes"]:
                if t not in loop["themes"]:
                    loop["themes"].append(t)

    # 2. Resolve open loops whose person no longer has recurring friction.
    just_broken = {(x.get("person") or {}).get("slug")
                   for x in ((s.get("analytics") or {}).get("deltas") or {}).get("just_broken_streaks") or []}
    for loop in led["loops"]:
        if loop["status"] == "open" and loop["slug"] not in recurring:
            loop["status"] = "resolved"
            loop["resolved_week"] = week
            log(f"resolved loop {loop['id']} ({loop['person']})")

    # 3. Backfill: just_broken persons with no tracked loop → create a resolved loop
    #    so the closure still surfaces once.
    tracked = {l["slug"] for l in led["loops"]}
    name_by_slug = {(x.get("person") or {}).get("slug"): (x.get("person") or {}).get("name")
                    for x in ((s.get("analytics") or {}).get("deltas") or {}).get("just_broken_streaks") or []}
    for slug in just_broken:
        if slug and slug not in tracked:
            led["loops"].append({
                "id": f"{slug}:{week}", "slug": slug, "person": name_by_slug.get(slug, slug),
                "started_week": week, "last_week": week, "status": "resolved",
                "streak_weeks": 0, "themes": ["(prior recurring friction — streak broke)"],
                "resolved_week": week, "closed_date": None, "closed_note": None,
                "surfaced_count": 0,
            })
            log(f"backfilled resolved loop for {slug}")

    led["updated_at"] = dt.datetime.now(dt.UTC).isoformat()
    save(led)
    return summarize(led, week)


def weeks_open(loop: dict, ref_week: str | None) -> int:
    try:
        a = dt.date.fromisoformat(loop["started_week"])
        b = dt.date.fromisoformat(ref_week) if ref_week else dt.date.today()
        return max(1, round((b - a).days / 7) + 1)
    except Exception:
        return 1


def summarize(led: dict, ref_week: str | None = None) -> dict:
    resolved_unclosed = [l for l in led["loops"] if l["status"] == "resolved" and not l["closed_date"]]
    open_loops = [l for l in led["loops"] if l["status"] == "open"]
    long_open = [l for l in open_loops if weeks_open(l, ref_week) >= LONG_OPEN_WEEKS]
    return {
        "enabled": True, "available": True,
        "close_the_loop": [  # resolved but you haven't told them
            {"person": l["person"], "slug": l["slug"], "themes": l["themes"][:2],
             "resolved_week": l["resolved_week"], "id": l["id"]}
            for l in resolved_unclosed
        ],
        "open": [{"person": l["person"], "slug": l["slug"], "themes": l["themes"][:2],
                  "weeks_open": weeks_open(l, ref_week), "id": l["id"]} for l in open_loops],
        "p1_candidates": [  # open ≥3 weeks = unresolved recurring friction = trust risk
            {"person": l["person"], "themes": l["themes"][:2], "weeks_open": weeks_open(l, ref_week), "id": l["id"]}
            for l in long_open
        ],
    }


def close(led: dict, who: str, note: str | None) -> dict:
    who_l = who.lower()
    matched = [l for l in led["loops"]
               if l["status"] == "resolved" and not l["closed_date"]
               and (l["slug"] == who_l or l["person"].lower() == who_l or l["id"] == who)]
    if not matched:
        # allow closing an open loop directly too (you resolved + told them in one go)
        matched = [l for l in led["loops"]
                   if not l["closed_date"] and (l["slug"] == who_l or l["person"].lower() == who_l or l["id"] == who)]
    if not matched:
        log(f"no open/resolved loop found for '{who}'")
        return {"closed": 0}
    today = dt.date.today().isoformat()
    for l in matched:
        l["status"] = "closed"
        l["closed_date"] = today
        l["closed_note"] = note
        log(f"closed loop {l['id']} ({l['person']})")
    save(led)
    return {"closed": len(matched), "loops": [l["id"] for l in matched]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--close")
    ap.add_argument("--note")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--for", dest="people")
    args = ap.parse_args()

    if os.environ.get("SIGNAL_INGEST") != "1":
        print(json.dumps({"enabled": False, "reason": "SIGNAL_INGEST != 1"}))
        return

    led = load()

    if args.close:
        print(json.dumps(close(led, args.close, args.note), indent=2))
        return
    if args.list:
        print(json.dumps(led, indent=2))
        return
    if args.people:
        names = {p.strip().lower() for p in args.people.split(",") if p.strip()}
        summ = summarize(led)
        summ["close_the_loop"] = [c for c in summ["close_the_loop"]
                                  if c["person"].lower() in names or c["slug"] in names]
        summ["open"] = [c for c in summ["open"] if c["person"].lower() in names or c["slug"] in names]
        print(json.dumps(summ, indent=2))
        return
    # default: --update
    print(json.dumps(update(led), indent=2))


if __name__ == "__main__":
    main()
