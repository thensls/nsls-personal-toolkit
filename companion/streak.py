"""Canonical streak rule for the NSLS toolkit.

Mirrors the prose description in skills/close-day/SKILL.md. The rule lives
in exactly two places: this module (for the web companion) and the prose
paragraph in close-day's prompt (for narrative description).
"""

from dataclasses import dataclass
from datetime import date as _date, timedelta
from typing import Literal


Status = Literal["ok", "one_miss", "at_risk", "reset"]


@dataclass(frozen=True)
class DayResult:
    date: str  # ISO YYYY-MM-DD
    percent: float  # 0.0, 0.5, or 1.0 (anything in (0,1) treated as partial)


def _fill_gap_misses(log: list[DayResult], today: str | None) -> list[DayResult]:
    """Expand calendar gaps into explicit 0.0-miss days.

    log.md only has rows for days something was ticked — a day with no row
    is a real miss, but walking only logged rows made three ticks spread
    over a month read as a 3-day streak. Fills every unlogged day between
    entries, and (when ``today`` is given) between the last entry and
    YESTERDAY — today isn't over, so an unticked today is never a miss.
    Malformed dates fall back to the raw log unchanged.
    """
    if not log:
        return log
    try:
        entries = sorted(log, key=lambda d: _date.fromisoformat(d.date))
        filled: list[DayResult] = []
        prev: _date | None = None
        for day in entries:
            cur = _date.fromisoformat(day.date)
            if prev is not None:
                step = prev + timedelta(days=1)
                while step < cur:
                    filled.append(DayResult(step.isoformat(), 0.0))
                    step += timedelta(days=1)
            filled.append(day)
            prev = cur
        if today is not None:
            end = _date.fromisoformat(today)  # fill up to, not including, today
            step = prev + timedelta(days=1)
            while step < end:
                filled.append(DayResult(step.isoformat(), 0.0))
                step += timedelta(days=1)
        return filled
    except ValueError:
        return log


def compute_concern(log: list[DayResult], today: str | None = None) -> float:
    """Walk the log from most recent backwards. Sum partial/miss
    contributions until a 100% day closes the chain.

    - 100% (>= 1.0): resets concern to 0, walk stops.
    - partial (0 < p < 1.0): + 0.5 concern.
    - miss (= 0.0, logged or an unlogged calendar day): + 1.0 concern.

    Pass ``today`` so unlogged days since the last entry count as misses
    (excluding today itself — the day isn't over).
    """
    concern = 0.0
    for day in reversed(_fill_gap_misses(log, today)):
        if day.percent >= 1.0:
            break
        if day.percent > 0:
            concern += 0.5
        else:
            concern += 1.0
    return concern


def status_for(concern: float) -> Status:
    if concern >= 2.0:
        return "reset"
    if concern >= 1.5:
        return "at_risk"
    if concern >= 1.0:
        return "one_miss"
    return "ok"


def streak_days(log: list[DayResult], today: str | None = None) -> int:
    """Count the ACTIVE days (full or partial ticks) in the unbroken chain,
    walking from the most recent day backwards. The chain breaks when the
    cumulative concern reaches 2.0 — same tolerance as compute_concern.

    Unlogged calendar days count as misses (pass ``today``), and miss days
    never add to the count — a badge of "3d" must mean three days of doing
    the habit, not three log rows spread over a month.
    """
    concern = 0.0
    days = 0
    for day in reversed(_fill_gap_misses(log, today)):
        if day.percent >= 1.0:
            concern = 0.0
        elif day.percent > 0:
            concern += 0.5
        else:
            concern += 1.0
        if concern >= 2.0:
            break
        if day.percent > 0:
            days += 1
    return days
