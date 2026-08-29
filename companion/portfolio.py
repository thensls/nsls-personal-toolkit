"""Deterministic portfolio-quadrant logic for the NSLS toolkit.

Mirrors the prose in skills/close-week/references/portfolio-attribution.md.
The judgment half (inferring offense/defense from Work Log prose, mapping a
Fathom topic to a quadrant) lives only in that prose; the arithmetic and the
cascade live only here. Keep both in sync — same contract as streak.py.
"""

import json
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
    to prevent. A line that predates this format (legacy notes with no
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
        quadrant_raw = match.group("quadrant")
        quadrant = quadrant_raw if quadrant_raw in _VALID else None
        project_weeks.append(ProjectWeek(
            project=match.group("slug"),
            quadrant=quadrant,
            offense_pct=int(match.group("offense")),
            hours=float(match.group("hours")),
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


def aggregate(project_weeks: list[ProjectWeek],
              meeting_rows: list[MeetingRow]) -> WeekTotals:
    """Mode comes only from project work. A meeting has a quadrant but no
    offense/defense reading — inferring one from a transcript would be a
    judgment this module deliberately does not make."""
    by_quadrant = _empty_by_quadrant()
    by_quadrant_mode = _empty_by_quadrant_mode()
    by_mode = {"offense": 0.0, "defense": 0.0}
    unresolved = 0.0
    total = 0.0

    for pw in project_weeks:
        total += pw.hours
        offense_hours = pw.hours * pw.offense_pct / 100.0
        defense_hours = pw.hours * (100 - pw.offense_pct) / 100.0
        if pw.quadrant in by_quadrant:
            by_quadrant[pw.quadrant] += pw.hours
            by_quadrant_mode[pw.quadrant]["offense"] += offense_hours
            by_quadrant_mode[pw.quadrant]["defense"] += defense_hours
        else:
            unresolved += pw.hours
        by_mode["offense"] += offense_hours
        by_mode["defense"] += defense_hours

    for row in meeting_rows:
        total += row.hours
        res = row.resolution
        if res.splits:
            splits = res.splits
            apportioned = sum(share for _, share in splits)
            # Splits normally sum to 1.0 (resolve_meeting() guarantees it,
            # normalising anything that doesn't). A caller reaching
            # aggregate() directly, or through summarize()'s JSON payload,
            # can hand us splits that don't.
            #
            # OVER 1.0 -> normalise, exactly as resolve_meeting() does.
            # Without this the remainder goes negative, unresolved_hours
            # renders as "-0.6h" and the quadrant percentages sum past
            # 100%: the invariant survives but the human reads nonsense.
            if apportioned > 1.0 + 1e-9:
                splits = tuple((q, s / apportioned) for q, s in splits)
                apportioned = 1.0
            for quadrant, share in splits:
                by_quadrant[quadrant] += row.hours * share
            # UNDER 1.0 -> the missing share is unresolved, never silently
            # dropped. This is the deliberate path for a caller that
            # dropped an out-of-vocabulary quadrant from an otherwise-valid
            # split (see summarize()). max() is belt-and-braces: after
            # normalisation the remainder cannot be negative, so
            # unresolved_hours never is either, and the invariant
            # sum(by_quadrant) + unresolved == total always holds.
            remainder = max(0.0, 1.0 - apportioned)
            if remainder:
                unresolved += row.hours * remainder
        elif res.quadrant in by_quadrant:
            by_quadrant[res.quadrant] += row.hours
        else:
            unresolved += row.hours

    return WeekTotals(by_quadrant, by_mode, unresolved, total,
                      by_quadrant_mode)


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
    a flag."""
    by_quadrant = _empty_by_quadrant()
    by_quadrant.update(entry.get("by_quadrant") or {})
    raw_mode = entry.get("by_mode") or {}
    by_mode = {
        "offense": raw_mode.get("offense", 0.0),
        "defense": raw_mode.get("defense", 0.0),
    }
    return WeekTotals(by_quadrant, by_mode, 0.0, sum(by_quadrant.values()))


def summarize(payload: dict) -> dict:
    """The one entry point a caller (skill prose, CLI) should use: turn a
    JSON-shaped week description into the numbers a person reads. Everything
    upstream of this (attributing a meeting, reading frontmatter) is the
    caller's job; this function only aggregates and flags."""
    project_weeks = [
        ProjectWeek(
            project=pw["project"],
            quadrant=pw["quadrant"],
            offense_pct=pw["offense_pct"],
            hours=pw["hours"],
        )
        for pw in payload.get("project_weeks", [])
    ]

    meeting_rows = []
    for mr in payload.get("meeting_rows", []):
        raw_splits = mr.get("splits") or ()
        splits = tuple((q, s) for q, s in raw_splits if q in _VALID)
        quadrant = mr.get("quadrant")
        resolved_by = mr["resolved_by"]
        if raw_splits and not splits:
            # Every split quadrant was outside the vocabulary (a typo or a
            # stale value from JSON input) -- degrade to unresolved the same
            # way aggregate() already degrades a bad single quadrant, rather
            # than handing aggregate() a split it cannot look up and
            # crashing. Hours still count toward the total via
            # unresolved_hours; they are never silently dropped.
            quadrant = None
            resolved_by = "unresolved"
        resolution = Resolution(
            quadrant=quadrant,
            resolved_by=resolved_by,
            splits=splits,
        )
        meeting_rows.append(MeetingRow(mr["label"], resolution, mr["hours"]))

    history = [
        _totals_from_history_entry(entry)
        for entry in payload.get("history", [])
    ]

    current = aggregate(project_weeks, meeting_rows)
    flags = evaluate_flags(
        current, history,
        driver_hours=payload.get("driver_hours", 0.0),
        held_hours=payload.get("held_hours", 0.0),
    )

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
        "flags": flags,
    }


USAGE = (
    "usage:\n"
    "  python3 -m companion.portfolio                < payload.json\n"
    "  python3 -m companion.portfolio --parse-daily  < daily-note.md\n"
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
