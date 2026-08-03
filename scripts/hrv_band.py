#!/usr/bin/env python3
"""Compute an HRV baseline band from daily-note frontmatter.

Why this exists
---------------
Apple Watch reports HRV as SDNN sampled *opportunistically* — irregular
background spot checks plus every Breathe session and ECG. There is no fixed
physiological window, so a single day's aggregate blends deep-sleep samples
with sitting-at-desk and post-coffee samples. Individual days are noise.

The morning spot-reading is noisier still, and biased high: across 2026-07-17
to 2026-07-29 every divergence between the value written in the morning and
the settled daily aggregate ran optimistic (106 vs 63, 70 vs 49, 66 vs 44).
So: never make a go/no-go call on one day, and never on a spot value.

What a band buys you
--------------------
Compare today against the builder's OWN trailing mean +/- 1 SD. Population
norms are meaningless for HRV (it varies hugely with age, genetics, and
whether the device reports SDNN or RMSSD).

Decision rule, per the VO2 goal file:
  - one day below band  -> noise, especially the day after a hard session
  - two consecutive days below band -> back off intensity
  - the trend of the baseline matters more than any single day

Reads `hrv_ms` from `$OBSIDIAN_VAULT_PATH/01-daily/YYYY-MM-DD.md` frontmatter.
Missing notes and `null` values are skipped, not treated as zero.

Usage
-----
    python3 hrv_band.py [--date YYYY-MM-DD] [--window 14] [--json]

Default output is one line suitable for dropping into a morning note.
`--json` emits the full structure for a skill to format itself.
"""

import argparse
import datetime
import json
import os
import pathlib
import re
import statistics
import sys

FM_RE = re.compile(r"^hrv_ms:\s*(\S+)\s*$", re.M)


def read_hrv(vault: pathlib.Path, day: datetime.date):
    """Return the settled hrv_ms for `day`, or None if absent/null/unparseable."""
    note = vault / "01-daily" / f"{day.isoformat()}.md"
    if not note.exists():
        return None
    # Only look at frontmatter — the body may quote a spot-reading in prose.
    text = note.read_text(errors="ignore")
    head = text.split("---", 2)
    fm = head[1] if text.startswith("---") and len(head) >= 3 else text[:1500]
    m = FM_RE.search(fm)
    if not m:
        return None
    raw = m.group(1).strip().strip('"').strip("'")
    if raw.lower() in ("null", "none", "~", ""):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def build(vault: pathlib.Path, target: datetime.date, window: int):
    """Collect the trailing `window` days BEFORE target, plus target itself."""
    history = []  # [(date, value)] oldest first, excludes target
    for i in range(window, 0, -1):
        d = target - datetime.timedelta(days=i)
        v = read_hrv(vault, d)
        if v is not None:
            history.append((d, v))
    today = read_hrv(vault, target)
    return history, today


def classify(value, low, high):
    if value is None or low is None:
        return "unknown"
    if value < low:
        return "below"
    if value > high:
        return "above"
    return "in_band"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="target date (default: today)")
    ap.add_argument("--window", type=int, default=14,
                    help="trailing days for the baseline (default 14)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--vault", default=os.environ.get("OBSIDIAN_VAULT_PATH", ""))
    args = ap.parse_args()

    if not args.vault:
        print("hrv_band: OBSIDIAN_VAULT_PATH not set", file=sys.stderr)
        return 2
    vault = pathlib.Path(args.vault).expanduser()

    target = (datetime.date.fromisoformat(args.date) if args.date
              else datetime.date.today())

    history, today = build(vault, target, args.window)
    values = [v for _, v in history]

    out = {
        "date": target.isoformat(),
        "window_days": args.window,
        "n": len(values),
        "today": today,
        "mean": None, "sd": None, "band_low": None, "band_high": None,
        "z": None, "status": "unknown",
        "consecutive_below": 0,
        "back_off": False,
        "trend_delta": None,
        "trend_reliable": False,
        "line": "",
        "series": [{"date": d.isoformat(), "hrv": v} for d, v in history],
    }

    # Need a real sample before a band means anything.
    if len(values) >= 5:
        mean = statistics.fmean(values)
        sd = statistics.stdev(values) if len(values) > 1 else 0.0
        low, high = mean - sd, mean + sd
        out.update(mean=round(mean, 1), sd=round(sd, 1),
                   band_low=round(low, 1), band_high=round(high, 1))
        out["status"] = classify(today, low, high)
        if today is not None and sd > 0:
            out["z"] = round((today - mean) / sd, 2)

        # Consecutive days below band, walking back from target. Every day is
        # scored against the SAME (target's) band — recomputing per-day would
        # let a slide redefine "normal" and mask the drift we care about.
        #
        # A day counts as below only at z <= -1.0, not merely a hair under
        # band_low. Without the margin this fires on rounding: 2026-07-28 read
        # 49 against a band_low of 49.4 and would have told Kevin to skip the
        # Wednesday 4x4 that produced his best VO2 gain of the quarter.
        # Walk actual CALENDAR days backwards and stop at the first day with no
        # reading. `history` has already dropped gaps, so iterating it would weld
        # non-adjacent low days together: one low day, a missed note, another low
        # day reads as "2 consecutive" and fires back_off on a two-day streak that
        # never happened. Kevin misses notes when travelling, so this is routine,
        # not hypothetical.
        run = 0
        if sd > 0:
            by_date = {d: v for d, v in history}
            by_date[target] = today
            day = target
            while True:
                v = by_date.get(day)
                if v is None or (v - mean) / sd > -1.0:
                    break
                run += 1
                day -= datetime.timedelta(days=1)
        out["consecutive_below"] = run
        out["back_off"] = run >= 2

        # Baseline drift: this window's mean vs the window before it.
        #
        # Only trustworthy when both windows hold settled aggregates. Morning
        # spot-readings run high (see module docstring), so a window polluted
        # with them makes the baseline look like it collapsed when all that
        # happened was the data got corrected. Gate on coverage AND on the
        # absence of obvious spot-reading outliers.
        prior_hist, _ = build(vault, target - datetime.timedelta(days=args.window),
                              args.window)
        prior = [v for _, v in prior_hist]
        if len(prior) >= 5:
            out["trend_delta"] = round(mean - statistics.fmean(prior), 1)
            prior_mean = statistics.fmean(prior)
            prior_sd = statistics.stdev(prior) if len(prior) > 1 else 0.0
            has_outlier = any(v > prior_mean + 3 * prior_sd for v in prior) if prior_sd else False
            out["trend_reliable"] = (
                len(prior) >= args.window - 1
                and len(values) >= args.window - 1
                and not has_outlier
            )

    # Human line for the morning note.
    if out["today"] is None:
        out["line"] = "HRV: no reading yet for this date."
    elif out["mean"] is None:
        out["line"] = (f"HRV {out['today']:.0f} — baseline needs "
                       f"{5 - out['n']} more day(s) of data.")
    else:
        label = {"below": "BELOW band", "above": "above band",
                 "in_band": "in band"}[out["status"]]
        line = (f"HRV **{out['today']:.0f}** — {label} "
                f"({out['band_low']:.0f}–{out['band_high']:.0f}, "
                f"{args.window}d baseline {out['mean']:.0f} ± {out['sd']:.0f})")
        if out["z"] is not None:
            line += f", z={out['z']:+.1f}"
        line += "."
        if out["trend_delta"] is not None and out["trend_reliable"]:
            arrow = "↑" if out["trend_delta"] > 0 else "↓"
            line += (f" Baseline {arrow} {abs(out['trend_delta']):.0f} "
                     f"vs prior {args.window}d.")
        if out["back_off"]:
            line += (f" ⚠️ **{out['consecutive_below']} consecutive days at z≤−1.0 "
                     f"— treat easy days as genuinely easy and hold volume flat.** "
                     f"(Does not override the Wednesday 4×4 — that session is "
                     f"~90% of the VO2 signal.)")
        elif out["status"] == "below":
            line += " One day below band = noise, especially after a hard session."
        out["line"] = line

    print(json.dumps(out, indent=1) if args.json else out["line"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
