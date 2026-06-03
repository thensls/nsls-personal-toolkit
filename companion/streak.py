"""Canonical streak rule for the NSLS toolkit.

Mirrors the prose description in skills/close-day/SKILL.md. The rule lives
in exactly two places: this module (for the web companion) and the prose
paragraph in close-day's prompt (for narrative description).
"""

from dataclasses import dataclass
from typing import Literal


Status = Literal["ok", "one_miss", "at_risk", "reset"]


@dataclass(frozen=True)
class DayResult:
    date: str  # ISO YYYY-MM-DD
    percent: float  # 0.0, 0.5, or 1.0 (anything in (0,1) treated as partial)


def compute_concern(log: list[DayResult]) -> float:
    """Walk the log from most recent backwards. Sum partial/miss
    contributions until a 100% day closes the chain.

    - 100% (>= 1.0): resets concern to 0, walk stops.
    - partial (0 < p < 1.0): + 0.5 concern.
    - miss (= 0.0): + 1.0 concern.
    """
    concern = 0.0
    for day in reversed(log):
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


def streak_days(log: list[DayResult]) -> int:
    """Count consecutive days from today backwards that haven't reset.
    A day triggers reset when the concern up to and including that day
    is >= 2.0.

    Single-pass O(n): walks backward tracking cumulative concern the
    same way compute_concern does, but counts streak days inline
    instead of re-scanning the entire prefix each iteration.
    """
    concern = 0.0
    days = 0
    for day in reversed(log):
        if day.percent >= 1.0:
            concern = 0.0
        elif day.percent > 0:
            concern += 0.5
        else:
            concern += 1.0
        if concern >= 2.0:
            break
        days += 1
    return days
