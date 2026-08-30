"""Deterministic portfolio-quadrant logic for the NSLS toolkit.

Mirrors the prose in skills/close-week/references/portfolio-attribution.md.
The judgment half (inferring offense/defense from Work Log prose, mapping a
Fathom topic to a quadrant) lives only in that prose; the arithmetic and the
cascade live only here. Keep both in sync — same contract as streak.py.
"""

import json
import math
import re
import sys
from dataclasses import dataclass, field

QUADRANTS: tuple[str, ...] = (
    "growth-driver",
    "operating-efficiency",
    "hygiene",
    "reliability",
)
CROSS_CUTTING = "cross-cutting"
_VALID = set(QUADRANTS) | {CROSS_CUTTING}

# The token close-day renders for a project whose frontmatter carries no
# portfolio-category. It is the ONLY out-of-vocabulary quadrant word that
# means "deliberately unbucketed"; every other one is drift.
UNCATEGORIZED = "uncategorized"


def _known_quadrant(value) -> bool:
    """True only for one of the five vocabulary strings. Type-checked, not
    just membership-checked: `value in _VALID` raises TypeError on an
    unhashable value (a list arriving from a JSON payload), and this module
    reports malformed input rather than raising on it."""
    return isinstance(value, str) and value in _VALID


def _finite_number(value) -> bool:
    """True only for a real, finite number.

    Two traps this closes, both of which reached arithmetic before:
      * a JSON string ("2") or null passes no type check at all and blows up
        at the first comparison, aborting the WHOLE week over one row;
      * NaN and Infinity pass every `< 0` / range check cleanly and then
        poison total_hours, the quadrant totals and every percentage.
    bool is excluded on purpose — Python's bool IS an int, so `True` would
    otherwise be accepted as one hour of work."""
    return (isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value))


def _json_safe(value):
    """A rejected row is printed as JSON at the confirm gate, so a value
    json.dumps cannot render honestly comes back as its repr instead. NaN
    and Infinity are not JSON (json.dumps emits bare `NaN`, which a strict
    reader rejects) and an arbitrary object is not serialisable at all.
    Anything JSON already represents passes through untouched, so a
    well-formed row is echoed back exactly as it was handed in."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return repr(value)


@dataclass(frozen=True)
class RoleRule:
    match: str      # lowercased substring matched against attendee name/email
    quadrant: str
    comment: str = ""


def parse_role_map(text: str) -> list[RoleRule]:
    """Parse ~/.claude/portfolio-role-map.txt. Unknown quadrants are dropped,
    never guessed — a typo must lose its rule loudly, not silently mis-file
    a whole category of meetings."""
    rules: list[RoleRule] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        body, _, comment = line.partition("#")
        arrow = "→" if "→" in body else ("->" if "->" in body else None)
        if arrow is None:
            continue
        left, _, right = body.partition(arrow)
        quadrant = right.strip().lower()
        match = left.strip().lower()
        if not match or quadrant not in _VALID:
            continue
        rules.append(RoleRule(match=match, quadrant=quadrant,
                              comment=comment.strip()))
    return rules


def project_quadrant(frontmatter: dict[str, str]) -> str | None:
    """The project's DEFAULT quadrant. Returns None when absent or outside the
    vocabulary, so the caller surfaces it rather than inventing a bucket.
    Note: 'founder-transition' appears in the vault as a legacy value and is
    deliberately not accepted — such projects map to cross-cutting by hand."""
    value = (frontmatter.get("portfolio-category") or "").strip().lower()
    return value if value in _VALID else None


def is_driver(frontmatter: dict[str, str]) -> bool:
    return (frontmatter.get("portfolio-role") or "").strip().lower() == "driver"


@dataclass(frozen=True)
class Resolution:
    quadrant: str | None
    resolved_by: str                                   # role|topic|project|unresolved
    splits: tuple[tuple[str, float], ...] = ()
    note: str = ""


def resolve_meeting(
    attendees: list[str],
    topics: list[tuple[str, float]],
    project_quadrant: str | None,
    role_map: list[RoleRule],
) -> Resolution:
    """First rule that resolves wins: role -> topic -> project -> unresolved."""
    for person in attendees:
        needle = person.lower()
        local = needle.split("@")[0].replace(".", " ")
        for rule in role_map:
            if rule.match in needle or rule.match in local:
                return Resolution(rule.quadrant, "role")

    valid_topics = [(q, s) for q, s in topics if q in _VALID and s > 0]
    if valid_topics:
        total = sum(s for _, s in valid_topics)
        note = ""
        if abs(total - 1.0) > 1e-6:
            valid_topics = [(q, s / total) for q, s in valid_topics]
            note = "shares normalised"
        if len(valid_topics) == 1:
            return Resolution(valid_topics[0][0], "topic", note=note)
        return Resolution(None, "topic", tuple(valid_topics), note)

    if project_quadrant in _VALID:
        return Resolution(project_quadrant, "project")

    return Resolution(None, "unresolved")


@dataclass(frozen=True)
class ProjectWeek:
    project: str
    quadrant: str | None     # None when the project's frontmatter carries no
                             # portfolio-category -- renders/parses as
                             # "uncategorized", never guessed into a bucket.
    offense_pct: int         # 0-100; defense is the remainder
    hours: float


# Matches a close-day '## Projects Touched' line:
#   - [[20-projects/<slug>|<slug>]] — <summary> · <X.X>h · <quadrant> · <NN>% offense
# The summary is captured greedily up to the LAST occurrence of the trailing
# " · <hours>h · <quadrant> · <NN>% offense" tail, so a summary that itself
# contains a '·' character does not break the parse -- regex backtracking
# finds the rightmost match of the fixed-shape tail rather than the first.
_PROJECT_LINE_RE = re.compile(
    r"^-\s*\[\[20-projects/(?P<slug>[^|\]]+)\|[^\]]*\]\]\s*—\s*"
    r"(?P<summary>.*)\s*·\s*(?P<hours>\d+(?:\.\d+)?)h\s*·\s*"
    r"(?P<quadrant>[a-z][a-z-]*)\s*·\s*(?P<offense>\d{1,3})%\s*offense\s*$"
)


def _section_lines(md: str, heading: str) -> list[str]:
    """Lines under '## <heading>' up to the next '## ' heading or EOF."""
    lines = md.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            start = i + 1
            break
    if start is None:
        return []
    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        section.append(line)
    return section


@dataclass(frozen=True)
class DayParse:
    """What one daily note's '## Projects Touched' section yielded."""
    projects: list[ProjectWeek]
    skipped: list[str]      # raw non-blank lines that did not match the format

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


def parse_daily_note(md: str) -> DayParse:
    """Parse a daily note's '## Projects Touched' section into one
    ProjectWeek per well-formed line, AND the raw text of every non-blank
    line that did not parse. This is the format contract between close-day
    (producer, this module's caller via the skill) and close-week
    (consumer, Task 8) -- verifying it here is the point of this function.

    A line rendered '· uncategorized ·' comes back with quadrant=None --
    losing that row silently is the failure mode this whole feature exists
    to prevent. That literal token is the ONLY out-of-vocabulary quadrant
    that maps to None: any other word in that slot (e.g. the legacy
    'founder-transition' still present in the vault) is reported as a
    skipped line, because quietly turning it into None routes its hours to
    unresolved with skipped_count reading 0 -- no signal at all.
    A line that predates this format (legacy notes with no
    hours/quadrant/offense suffix, or any other line that doesn't match)
    is skipped, never raised on -- old daily notes must still parse. But a
    skipped line is REPORTED, not swallowed: an unparsed line is a day's
    hours vanishing from the week total with no signal, which is the exact
    silent failure this module exists to surface. The caller (close-week
    Step 2a) must show the skipped count at its confirm gate.

    A note with no '## Projects Touched' section returns an empty parse.
    """
    project_weeks: list[ProjectWeek] = []
    skipped: list[str] = []
    for line in _section_lines(md, "Projects Touched"):
        stripped = line.strip()
        if not stripped:
            continue
        match = _PROJECT_LINE_RE.match(stripped)
        if not match:
            # Only a line that was TRYING to be a project row counts as a
            # lost row. The section also carries explanatory prose (see the
            # close-day template), and reporting that as "skipped" would
            # cry wolf until nobody reads the count.
            if stripped.startswith("-") or "20-projects/" in stripped:
                skipped.append(stripped)
            continue
        offense_pct = int(match.group("offense"))
        if not 0 <= offense_pct <= 100:
            # The regex accepts \d{1,3}, so '150% offense' has the SHAPE of a
            # row but cannot be a percentage. Report it as a skipped line so
            # it surfaces at the confirm gate, rather than parsing
            # "successfully" and reaching aggregate(), where it would compute
            # negative defense hours out of a number nobody ever read.
            skipped.append(stripped)
            continue
        quadrant_raw = match.group("quadrant")
        if quadrant_raw in _VALID:
            quadrant = quadrant_raw
        elif quadrant_raw == UNCATEGORIZED:
            # The documented "no portfolio-category" row. quadrant=None is
            # its real value, not a fallback.
            quadrant = None
        else:
            # Any OTHER word in the quadrant slot is drift, not a deliberate
            # blank. Mapping it to None too is how 'founder-transition' — a
            # real legacy value still sitting in the vault — would route its
            # hours to unresolved with skipped_count reading 0, i.e. with no
            # signal at all. Report it so the confirm gate can show it.
            skipped.append(stripped)
            continue
        hours = float(match.group("hours"))
        if not math.isfinite(hours):
            # The regex accepts unbounded digits, so a 400-digit hours field
            # float()s to inf and would poison total_hours and every
            # percentage downstream. Same treatment as an out-of-range
            # percentage: report the line, never pass the value on.
            skipped.append(stripped)
            continue
        project_weeks.append(ProjectWeek(
            project=match.group("slug"),
            quadrant=quadrant,
            offense_pct=offense_pct,
            hours=hours,
        ))
    return DayParse(project_weeks, skipped)


def parse_projects_touched(md: str) -> list[ProjectWeek]:
    """The parsed rows only. Prefer parse_daily_note() -- it also returns
    the lines that did NOT parse, which is the half a caller must not drop.
    """
    return parse_daily_note(md).projects


@dataclass(frozen=True)
class MeetingRow:
    label: str
    resolution: Resolution
    hours: float


def _empty_by_quadrant() -> dict[str, float]:
    return {q: 0.0 for q in (*QUADRANTS, CROSS_CUTTING)}


def _empty_by_quadrant_mode() -> dict[str, dict[str, float]]:
    return {q: {"offense": 0.0, "defense": 0.0}
            for q in (*QUADRANTS, CROSS_CUTTING)}


@dataclass(frozen=True)
class RejectedRow:
    """Something the module refused to trust, kept with the reason it failed.

    Silent correction is the exact failure this feature exists to catch, so a
    malformed row is never quietly fixed up: its hours are routed to
    unresolved (or, when the hours themselves are the malformed part, left
    out of the week entirely) AND the raw row comes back here so the caller
    can show it. A rejected row the caller never renders is the same silent
    failure one layer up -- close-week Step 2a must print these at its
    confirm gate.

    TWO SOURCES, ONE LIST. aggregate() rejects on VALUES and is the only
    place value rules live. summarize() rejects on the JSON payload's SHAPE
    -- a row missing a required key, a container that isn't a list, a
    week-level number that isn't one -- because aggregate() takes dataclasses
    and structurally never sees the payload's dicts. That is a different
    rule, not a second copy of the same rule: no value check may be written
    in summarize(), which is how these two came apart once already."""
    kind: str        # "project" | "meeting" | "payload"
    row: dict        # the raw row's values, JSON-safe, exactly as handed in
    reason: str      # one line, naming the field and the value that failed


@dataclass(frozen=True)
class WeekTotals:
    by_quadrant: dict[str, float]
    by_mode: dict[str, float]
    unresolved_hours: float
    total_hours: float
    # Mode split WITHIN each quadrant, project rows only -- the same
    # invariant as by_mode, one level down. A quadrant whose hours are all
    # meeting hours has 0.0/0.0 here, which means "no mode recorded", NOT
    # "recorded zero offense": meetings carry a quadrant and deliberately
    # no mode. Renderers must print an em dash for such a quadrant rather
    # than 0% / 0%. Defaulted so a caller building a WeekTotals by hand
    # (history entries) does not have to supply it.
    by_quadrant_mode: dict[str, dict[str, float]] = field(
        default_factory=_empty_by_quadrant_mode)
    # Rows aggregate() would not trust, with the reason each failed. Empty on
    # a clean week. Defaulted for the same reason as by_quadrant_mode: a
    # caller building a WeekTotals by hand (history entries) has no rows.
    rejected: tuple[RejectedRow, ...] = ()


def _project_row_dict(pw: ProjectWeek) -> dict:
    return {"project": _json_safe(pw.project),
            "quadrant": _json_safe(pw.quadrant),
            "offense_pct": _json_safe(pw.offense_pct),
            "hours": _json_safe(pw.hours)}


def _meeting_row_dict(row: MeetingRow) -> dict:
    res = row.resolution
    return {"label": _json_safe(row.label),
            "quadrant": _json_safe(res.quadrant),
            "resolved_by": _json_safe(res.resolved_by),
            "hours": _json_safe(row.hours),
            "splits": [[_json_safe(q), _json_safe(s)] for q, s in res.splits]}


def aggregate(project_weeks: list[ProjectWeek],
              meeting_rows: list[MeetingRow]) -> WeekTotals:
    """Mode comes only from project work. A meeting has a quadrant but no
    offense/defense reading — inferring one from a transcript would be a
    judgment this module deliberately does not make.

    THIS FUNCTION IS THE VALIDATION BOUNDARY. Every caller funnels through
    it — direct callers, summarize()'s JSON payload, and the CLI — so the
    checks live here and nowhere else. Validating per entry point is what
    already failed once: an out-of-vocabulary split quadrant was guarded in
    summarize() only and stayed live in aggregate(), where it raised
    KeyError. What is checked:

      * every numeric field is a real, FINITE number, checked BEFORE any
        comparison or arithmetic touches it — hours and offense_pct on
        project rows, hours on meeting rows, and every split share. A JSON
        payload can hand us "2", null or a list; NaN and Infinity survive
        every range check and then poison total_hours and every percentage
      * quadrant (and every split quadrant) is in the five-value vocabulary
      * 0 <= offense_pct <= 100
      * hours >= 0, on project rows and meeting rows alike
      * every split share >= 0

    A row that fails is REPORTED, never silently corrected: its hours go to
    unresolved and the raw row comes back in WeekTotals.rejected with the
    reason. The one exception is unusable hours — negative, or not a finite
    number — which cannot be routed anywhere without pushing
    unresolved_hours below zero or making the week's total meaningless; such
    a row is left out of total_hours entirely and reported. Either way
    sum(by_quadrant) + unresolved_hours == total_hours still holds, and
    unresolved_hours is never negative. Nothing here raises: one malformed
    row must cost its own row, not the whole week summary.

    A quadrant of None is NOT a rejection: it is the documented
    'uncategorized' project row and the documented unresolved meeting, both
    of which route to unresolved by design.
    """
    by_quadrant = _empty_by_quadrant()
    by_quadrant_mode = _empty_by_quadrant_mode()
    by_mode = {"offense": 0.0, "defense": 0.0}
    unresolved = 0.0
    total = 0.0
    rejected: list[RejectedRow] = []

    for pw in project_weeks:
        # TYPE BEFORE VALUE. `pw.hours < 0` on the string "2" or on None
        # raises TypeError, and one such row from the JSON payload used to
        # abort the entire week summary — the CLI printed nothing and the
        # confirm gate never saw the row that caused it.
        if not _finite_number(pw.hours):
            rejected.append(RejectedRow(
                "project", _project_row_dict(pw),
                f"hours {pw.hours!r} is not a finite number — row excluded "
                "from the week"))
            continue
        if pw.hours < 0:
            # Not routable: adding negative hours to unresolved would render
            # a negative unresolved figure. Drop it from the week and say so.
            rejected.append(RejectedRow(
                "project", _project_row_dict(pw),
                f"hours is negative ({pw.hours}) — row excluded from the week"))
            continue
        total += pw.hours
        if not _finite_number(pw.offense_pct):
            rejected.append(RejectedRow(
                "project", _project_row_dict(pw),
                f"offense_pct {pw.offense_pct!r} is not a finite number — "
                "hours routed to unresolved, no mode recorded"))
            unresolved += pw.hours
            continue
        if not 0 <= pw.offense_pct <= 100:
            rejected.append(RejectedRow(
                "project", _project_row_dict(pw),
                f"offense_pct {pw.offense_pct} is outside 0-100 — hours "
                "routed to unresolved, no mode recorded"))
            unresolved += pw.hours
            continue
        offense_hours = pw.hours * pw.offense_pct / 100.0
        defense_hours = pw.hours * (100 - pw.offense_pct) / 100.0
        if _known_quadrant(pw.quadrant):
            by_quadrant[pw.quadrant] += pw.hours
            by_quadrant_mode[pw.quadrant]["offense"] += offense_hours
            by_quadrant_mode[pw.quadrant]["defense"] += defense_hours
        else:
            if pw.quadrant is not None:
                rejected.append(RejectedRow(
                    "project", _project_row_dict(pw),
                    f"quadrant {pw.quadrant!r} is outside the vocabulary — "
                    "hours routed to unresolved"))
            unresolved += pw.hours
        by_mode["offense"] += offense_hours
        by_mode["defense"] += defense_hours

    for row in meeting_rows:
        res = row.resolution
        if not _finite_number(row.hours):
            rejected.append(RejectedRow(
                "meeting", _meeting_row_dict(row),
                f"hours {row.hours!r} is not a finite number — row excluded "
                "from the week"))
            continue
        if row.hours < 0:
            rejected.append(RejectedRow(
                "meeting", _meeting_row_dict(row),
                f"hours is negative ({row.hours}) — row excluded from the week"))
            continue
        total += row.hours
        if res.splits:
            # Again type before value: `s < 0` on a string or None raises,
            # and a NaN share sails through `s < 0` to make every quadrant
            # total NaN. Both cost the whole row, exactly like a negative
            # share, because a share nobody can read cannot be apportioned.
            unusable = [s for _, s in res.splits if not _finite_number(s)]
            if unusable:
                rejected.append(RejectedRow(
                    "meeting", _meeting_row_dict(row),
                    f"split share {unusable[0]!r} is not a finite number — "
                    "whole row routed to unresolved"))
                unresolved += row.hours
                continue
            negative = [s for _, s in res.splits if s < 0]
            if negative:
                # A negative share subtracts hours from a quadrant that was
                # never worked. The reconciliation invariant would still hold
                # arithmetically while every rendered number was nonsense, so
                # the whole row goes to unresolved rather than part of it.
                rejected.append(RejectedRow(
                    "meeting", _meeting_row_dict(row),
                    f"split share is negative ({negative[0]}) — whole row "
                    "routed to unresolved"))
                unresolved += row.hours
                continue
            # NORMALISE FIRST, DROP SECOND. Splits normally sum to 1.0
            # (resolve_meeting() guarantees it, normalising anything that
            # doesn't). A caller reaching aggregate() directly, or through
            # summarize()'s JSON payload, can hand us splits that don't.
            #
            # OVER 1.0 -> normalise, exactly as resolve_meeting() does.
            # Without this the remainder goes negative, unresolved_hours
            # renders as "-0.6h" and the quadrant percentages sum past
            # 100%: the invariant survives but the human reads nonsense.
            #
            # The scale is computed over ALL the shares, including the ones
            # whose quadrant is about to be dropped. Filtering first and
            # normalising the survivors scales them UP to fill the invalid
            # share's place, so 0.7/0.6/0.1 on a 2h meeting put all 2h into
            # valid quadrants with unresolved_hours at 0.0 — while the
            # rejection below said those hours had gone to unresolved. The
            # reason string has to be true, so the invalid share's hours
            # genuinely land in unresolved.
            total_share = sum(share for _, share in res.splits)
            scale = 1.0 / total_share if total_share > 1.0 + 1e-9 else 1.0
            splits = tuple((q, s * scale) for q, s in res.splits
                           if _known_quadrant(q))
            dropped = [q for q, _ in res.splits if not _known_quadrant(q)]
            if dropped:
                rejected.append(RejectedRow(
                    "meeting", _meeting_row_dict(row),
                    "split quadrant(s) outside the vocabulary: "
                    + ", ".join(repr(q) for q in dropped)
                    + " — that share routed to unresolved"))
            apportioned = sum(share for _, share in splits)
            for quadrant, share in splits:
                by_quadrant[quadrant] += row.hours * share
            # UNDER 1.0 -> the missing share is unresolved, never silently
            # dropped. This is the deliberate path for a split that named an
            # out-of-vocabulary quadrant (dropped just above) and for one a
            # caller simply under-apportioned. max() is belt-and-braces:
            # after normalisation the remainder cannot be negative, so
            # unresolved_hours never is either, and the invariant
            # sum(by_quadrant) + unresolved == total always holds.
            remainder = max(0.0, 1.0 - apportioned)
            if remainder:
                unresolved += row.hours * remainder
        elif _known_quadrant(res.quadrant):
            by_quadrant[res.quadrant] += row.hours
        else:
            if res.quadrant is not None:
                rejected.append(RejectedRow(
                    "meeting", _meeting_row_dict(row),
                    f"quadrant {res.quadrant!r} is outside the vocabulary — "
                    "hours routed to unresolved"))
            unresolved += row.hours

    return WeekTotals(by_quadrant, by_mode, unresolved, total,
                      by_quadrant_mode, tuple(rejected))


RELIABILITY_ZERO_WEEKS = 2
OPERATING_EFFICIENCY_CEILING = 0.40


def evaluate_flags(current: WeekTotals, history: list[WeekTotals],
                   driver_hours: float, held_hours: float) -> list[str]:
    """Each flag names the decision it forces. A flag with no decision
    attached does not belong here."""
    flags: list[str] = []

    recent = [current, *history][:RELIABILITY_ZERO_WEEKS]
    if (len(recent) == RELIABILITY_ZERO_WEEKS
            and all(w.by_quadrant.get("reliability", 0.0) == 0.0 for w in recent)):
        flags.append(
            f"Reliability starving — 0h for {RELIABILITY_ZERO_WEEKS} consecutive "
            "weeks. Fund it, or say out loud you are not."
        )

    if current.total_hours > 0:
        share = current.by_quadrant.get("operating-efficiency", 0.0) / current.total_hours
        if share > OPERATING_EFFICIENCY_CEILING:
            flags.append(
                f"operating-efficiency at {share:.0%} — the machine is eating "
                "the output it exists to produce."
            )

    if history and (history[0].by_mode["offense"] + history[0].by_mode["defense"] > 0):
        # Only compare against a prior week that actually recorded mode
        # hours. A prior week with no recorded mode data reads as
        # "unknown", never as "zero defense" — absent history must never
        # manufacture this flag.
        def defense_share(w: WeekTotals) -> float:
            spent = w.by_mode["offense"] + w.by_mode["defense"]
            return w.by_mode["defense"] / spent if spent else 0.0
        if defense_share(current) > defense_share(history[0]):
            flags.append(
                f"Defense share rose to {defense_share(current):.0%} — your best "
                "assets are decaying under you."
            )

    if held_hours > driver_hours:
        flags.append(
            f"held projects out-earned drivers ({held_hours:.1f}h vs "
            f"{driver_hours:.1f}h) — the ranking is not what you are doing."
        )

    return flags


def _totals_from_history_entry(entry: dict) -> WeekTotals:
    """A history entry carries `by_quadrant` and, optionally, `by_mode`.
    When `by_mode` is omitted (or empty), historical mode hours read as
    zero here — but evaluate_flags is what actually protects against
    that being misread as "recorded zero defense spend": it only runs the
    rising-defense-share comparison when a prior week's by_mode hours sum
    to something greater than zero. Absent history must never manufacture
    a flag.

    An entry that is not a dict, or whose numbers are not finite numbers,
    reads as an EMPTY week — the same state as an omitted `by_mode`, which
    evaluate_flags already treats as "no data" and never as "recorded
    zero". That is the safe direction: a malformed prior week can only
    suppress a trend flag, never manufacture one. It is not routed to
    `rejected`, which describes THIS week's rows; the caller is told at the
    confirm gate that history was suppressed (close-week Step 2a #5)."""
    if not isinstance(entry, dict):
        entry = {}
    by_quadrant = _empty_by_quadrant()
    raw_quadrant = entry.get("by_quadrant")
    if isinstance(raw_quadrant, dict):
        by_quadrant.update({k: v for k, v in raw_quadrant.items()
                            if _known_quadrant(k) and _finite_number(v)})
    raw_mode = entry.get("by_mode")
    if not isinstance(raw_mode, dict):
        raw_mode = {}
    by_mode = {
        mode: (raw_mode.get(mode) if _finite_number(raw_mode.get(mode)) else 0.0)
        for mode in ("offense", "defense")
    }
    return WeekTotals(by_quadrant, by_mode, 0.0, sum(by_quadrant.values()))


# Keys a payload row cannot be read without. `quadrant` is required on a
# project row (null is a legal VALUE for it -- the documented uncategorized
# row -- but an absent key means nobody said) and optional on a meeting row,
# where a split or unresolved meeting legitimately carries no quadrant at all.
_REQUIRED_PROJECT_KEYS = ("project", "quadrant", "offense_pct", "hours")
_REQUIRED_MEETING_KEYS = ("label", "resolved_by", "hours")


def _payload_row_dict(row) -> dict:
    """Echo a raw payload row back JSON-safely, for a shape rejection. The
    row may not be a dict at all, which is itself the failure."""
    if isinstance(row, dict):
        return {str(k): _json_safe(v) for k, v in row.items()}
    return {"row": _json_safe(row)}


def _missing_keys(row, required: tuple[str, ...]) -> list[str]:
    if not isinstance(row, dict):
        return list(required)
    return [key for key in required if key not in row]


def _split_pairs(raw):
    """Return (pairs, reason). `splits` is a list of [quadrant, share] pairs;
    anything else is a shape failure, reported rather than unpacked. Zipping
    a malformed entry raises ValueError, which would abort the week."""
    if raw is None:
        return (), None
    if not isinstance(raw, (list, tuple)):
        return (), f"'splits' is {type(raw).__name__}, not a list"
    pairs = []
    for entry in raw:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            return (), ("'splits' entry is not a [quadrant, share] pair: "
                        f"{_json_safe(entry)!r}")
        pairs.append((entry[0], entry[1]))
    return tuple(pairs), None


def _payload_rows(payload: dict, key: str, rejects: list) -> list:
    """The rows under `key`, or none plus a reported reason. A non-list
    container silently read as empty is a whole week of work vanishing."""
    rows = payload.get(key)
    if rows is None:
        return []
    if isinstance(rows, (list, tuple)):
        return list(rows)
    rejects.append(RejectedRow(
        "payload", {key: _json_safe(rows)},
        f"payload key {key!r} is {type(rows).__name__}, not a list — no rows "
        "were read from it"))
    return []


def _week_number(payload: dict, key: str, rejects: list) -> float:
    """driver_hours / held_hours. A bad value reads as 0.0 AND is reported.

    These feed only the held-vs-driver flag, so killing the whole week
    summary over one of them would be disproportionate to what they do —
    but reading 0.0 silently is worse than useless: held > driver is how
    that flag fires, so a bad driver_hours could manufacture it. Reported
    at 0.0, the flag can still fire wrongly, which is exactly why the
    reason has to reach the confirm gate beside it."""
    value = payload.get(key, 0.0)
    if _finite_number(value):
        return float(value)
    rejects.append(RejectedRow(
        "payload", {key: _json_safe(value)},
        f"{key} {value!r} is not a finite number — read as 0.0; any "
        "held-vs-driver flag below is computed without it"))
    return 0.0


def summarize(payload: dict) -> dict:
    """The one entry point a caller (skill prose, CLI) should use: turn a
    JSON-shaped week description into the numbers a person reads. Everything
    upstream of this (attributing a meeting, reading frontmatter) is the
    caller's job; this function only aggregates and flags.

    It owns exactly one rule of its own: the payload's SHAPE. A row missing
    a required key, a `splits` that isn't a list of pairs, a container that
    isn't a list, a week-level number that isn't one — all are reported as
    `rejected` entries here, because aggregate() takes dataclasses and can
    never see the payload's dicts. VALUES are still aggregate()'s alone; a
    value check written here is how the two halves came apart once already
    (a bad split quadrant was filtered out in this function and still raised
    KeyError inside aggregate() for every direct caller).

    Nothing raises out of this function. One malformed row costs its own
    row; it must never cost the week summary, which is the only thing
    standing between the builder and a silently missing Friday."""
    shape_rejects: list[RejectedRow] = []

    if not isinstance(payload, dict):
        return _summary(aggregate([], []), [], [RejectedRow(
            "payload", {"payload": _json_safe(payload)},
            f"payload is {type(payload).__name__}, not an object — nothing "
            "could be read from it")])

    project_weeks = []
    for pw in _payload_rows(payload, "project_weeks", shape_rejects):
        missing = _missing_keys(pw, _REQUIRED_PROJECT_KEYS)
        if missing:
            shape_rejects.append(RejectedRow(
                "project", _payload_row_dict(pw),
                "payload row is missing required key(s): "
                + ", ".join(repr(k) for k in missing)
                + " — row excluded from the week"))
            continue
        project_weeks.append(ProjectWeek(
            project=pw["project"],
            quadrant=pw["quadrant"],
            offense_pct=pw["offense_pct"],
            hours=pw["hours"],
        ))

    meeting_rows = []
    for mr in _payload_rows(payload, "meeting_rows", shape_rejects):
        missing = _missing_keys(mr, _REQUIRED_MEETING_KEYS)
        if missing:
            shape_rejects.append(RejectedRow(
                "meeting", _payload_row_dict(mr),
                "payload row is missing required key(s): "
                + ", ".join(repr(k) for k in missing)
                + " — row excluded from the week"))
            continue
        splits, bad_splits = _split_pairs(mr.get("splits"))
        if bad_splits:
            shape_rejects.append(RejectedRow(
                "meeting", _payload_row_dict(mr),
                bad_splits + " — row excluded from the week"))
            continue
        # Values pass through EXACTLY as given from here: aggregate() is the
        # one boundary that checks quadrants, shares, hours and offense_pct.
        resolution = Resolution(
            quadrant=mr.get("quadrant"),
            resolved_by=mr["resolved_by"],
            splits=splits,
        )
        meeting_rows.append(MeetingRow(mr["label"], resolution, mr["hours"]))

    history = [
        _totals_from_history_entry(entry)
        for entry in _payload_rows(payload, "history", shape_rejects)
    ]

    current = aggregate(project_weeks, meeting_rows)
    flags = evaluate_flags(
        current, history,
        driver_hours=_week_number(payload, "driver_hours", shape_rejects),
        held_hours=_week_number(payload, "held_hours", shape_rejects),
    )
    return _summary(current, flags, shape_rejects)


def _summary(current: WeekTotals, flags: list[str],
             shape_rejects: list[RejectedRow]) -> dict:
    """Render one aggregated week as the JSON a person reads. Shape
    rejections from summarize() join aggregate()'s value rejections in ONE
    `rejected` list -- the caller has exactly one place to look, and every
    entry means the same thing: a row the module would not guess at."""

    total = current.total_hours
    percentages = {
        quadrant: (hours / total if total else 0.0)
        for quadrant, hours in current.by_quadrant.items()
    }

    # Every percentage the renderer needs is returned here, so no caller
    # has to divide anything by hand -- including Unresolved%. A share is
    # 0.0 when its denominator is 0.0; the renderer distinguishes "no mode
    # recorded" from "recorded zero" by reading by_quadrant_mode's HOURS,
    # not this table (a quadrant whose hours are all meeting hours has no
    # mode at all, and must render an em dash rather than 0% / 0%).
    mode_spent = current.by_mode["offense"] + current.by_mode["defense"]
    mode_percentages = {
        mode: (hours / mode_spent if mode_spent else 0.0)
        for mode, hours in current.by_mode.items()
    }
    quadrant_mode_percentages = {}
    for quadrant, modes in current.by_quadrant_mode.items():
        spent = modes["offense"] + modes["defense"]
        quadrant_mode_percentages[quadrant] = {
            mode: (hours / spent if spent else 0.0)
            for mode, hours in modes.items()
        }

    return {
        "by_quadrant": current.by_quadrant,
        "by_mode": current.by_mode,
        "by_quadrant_mode": current.by_quadrant_mode,
        "unresolved_hours": current.unresolved_hours,
        "total_hours": current.total_hours,
        "percentages": percentages,
        "mode_percentages": mode_percentages,
        "quadrant_mode_percentages": quadrant_mode_percentages,
        "unresolved_pct": (current.unresolved_hours / total if total else 0.0),
        # Every row aggregate() refused to trust, with the reason. Empty on a
        # clean week. The caller must SHOW these -- a rejected row that never
        # reaches the confirm gate is the silent correction this whole
        # feature exists to prevent.
        "rejected": [
            {"kind": r.kind, "row": r.row, "reason": r.reason}
            for r in (*shape_rejects, *current.rejected)
        ],
        "flags": flags,
    }


# Run this with the COMPANION'S interpreter, never a bare `python3`: the
# module needs >=3.10, a stock Mac's /usr/bin/python3 is 3.9, and a supported
# Windows install has no `python3` on PATH at all (the launcher is `py`, and
# the toolkit may be running from its own private runtime). $PY below is the
# venv interpreter beside the binary ensure-companion.sh resolves — see
# skills/close-week/references/portfolio-attribution.md §7 for the two lines
# that produce it.
USAGE = (
    'usage (run with the companion interpreter, not a bare python3):\n'
    '  "$PY" -m companion.portfolio                < payload.json\n'
    '  "$PY" -m companion.portfolio --parse-daily  < daily-note.md\n'
)


def main(argv: list[str] | None = None) -> int:
    """Two modes, both stdin -> stdout JSON.

    Default: read a week payload and print summarize()'s result.

    --parse-daily: read ONE daily note's markdown and print its
    '## Projects Touched' rows plus every line that did not parse. This
    mode exists so close-week never hand-rolls a regex for the close-day
    format contract, and so a drifted line is reported at the confirm gate
    rather than quietly shrinking the week's hours.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--parse-daily"]:
        parsed = parse_daily_note(sys.stdin.read())
        print(json.dumps({
            "project_weeks": [
                {"project": pw.project, "quadrant": pw.quadrant,
                 "offense_pct": pw.offense_pct, "hours": pw.hours}
                for pw in parsed.projects
            ],
            "skipped_lines": parsed.skipped,
            "skipped_count": parsed.skipped_count,
        }, indent=2))
        return 0
    if args:
        sys.stderr.write(USAGE)
        return 2
    payload = json.load(sys.stdin)
    print(json.dumps(summarize(payload), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
