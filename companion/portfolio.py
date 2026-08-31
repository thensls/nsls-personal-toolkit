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


# The largest magnitude a float can hold. An int beyond it has no float at
# all, which is why the check below is a comparison and not a conversion.
_MAX_FLOAT = sys.float_info.max


def _finite_number(value) -> bool:
    """True only for a real, finite number.

    Three traps this closes, all of which reached arithmetic before:
      * a JSON string ("2") or null passes no type check at all and blows up
        at the first comparison, aborting the WHOLE week over one row;
      * NaN and Infinity pass every `< 0` / range check cleanly and then
        poison total_hours, the quadrant totals and every percentage;
      * a huge JSON INTEGER made this guard raise the very exception it
        exists to prevent. Python ints are arbitrary-precision and
        `math.isfinite()` converts its argument to float FIRST, so
        `math.isfinite(10**400)` raises OverflowError rather than returning
        False — and json.load happily materialises an unbounded integer
        literal. One drifted number in a payload therefore killed the whole
        week: the CLI exited 1 with empty stdout and the confirm gate never
        saw the row that caused it. An int is range-checked by COMPARISON
        instead (Python compares int to float exactly, without converting
        the int), so it is REJECTED, never fatal. Every later
        `math.isfinite()` / `float()` in this module runs on a value this
        function has already passed, so none of them can overflow either —
        except sums, which are checked through this function too.
    bool is excluded on purpose — Python's bool IS an int, so `True` would
    otherwise be accepted as one hour of work."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if isinstance(value, int):
        return -_MAX_FLOAT <= value <= _MAX_FLOAT
    return math.isfinite(value)


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


# The only four values `resolved_by` may hold. It names WHICH rule in the
# cascade fired; a fifth value is not a new kind of resolution, it is a caller
# inventing one — and the field is echoed into `rejected` rows that a human
# reads, so an invented value has to be refused, not passed along.
RESOLVED_BY: tuple[str, ...] = ("role", "topic", "project", "unresolved")


def _is_pair(entry) -> bool:
    """One `splits` entry has exactly two slots.

    THE SHAPE RULE LIVES HERE AND NOWHERE ELSE. `for q, s in splits` raises
    ValueError on a 1-tuple and TypeError on a non-sequence, and both used to
    abort the whole week from inside aggregate(). Two places need this
    judgment — the payload gate, which reports the bad entry, and the
    Resolution constructor, which refuses to build the object — and letting
    each carry its own reading of "is a pair" is how two halves of one rule
    come apart."""
    return isinstance(entry, (list, tuple)) and len(entry) == 2


def _normalised_splits(raw):
    """`raw` as a tuple of exactly-two-element tuples, or None when it is not
    a sequence of pairs at all.

    SHAPE ONLY. The quadrant strings and the share numbers are VALUES, and
    every value rule in this module lives in aggregate() — see its docstring.
    This function decides one thing: whether `for q, s in splits` can run."""
    if not isinstance(raw, (list, tuple)):
        return None
    pairs = []
    for entry in raw:
        if not _is_pair(entry):
            return None
        pairs.append((entry[0], entry[1]))
    return tuple(pairs)


@dataclass(frozen=True)
class Resolution:
    """A meeting's attribution — VALIDATED WHERE IT IS CONSTRUCTED.

    A malformed Resolution is impossible to create, so no present or future
    consumer has to defend against one. That is deliberately structural
    rather than a guard at the point of use: `Resolution(None, "topic",
    ("bad",))` was accepted here and raised ValueError three frames away, at
    aggregate()'s `for q, s in splits`, killing the whole week summary. Three
    review rounds have each found a NEW shape of the same class (a 1-tuple, a
    non-sequence entry, a non-list container), which is the signature of a
    per-shape guard: the fix belongs at the boundary where the object comes
    into existence, not at each of the places that later reads it.

    WHY IT RAISES RATHER THAN COERCING. Coercion was the alternative — drop a
    malformed `splits` and let the row fall through as unresolved. It is
    rejected because a constructor has no channel to report through: there is
    no `rejects` list here, so coercion would silently reroute a caller's
    split meeting, and silent correction is the exact failure this whole
    feature exists to catch. Nor does raising cost the week, because no DATA
    can reach it: summarize()'s `_split_pairs()` gate reports a malformed
    payload `splits` as a `rejected` row BEFORE any Resolution is built, and
    the same is true of `resolved_by`. What is left is an in-process
    programming error, where loud and immediate is the right answer — and
    even that cannot reach a user as a traceback, because summarize() and
    main() both floor every unhandled exception into a JSON `payload`
    rejection.

    `splits` is normalised to a tuple of 2-tuples, so after construction
    `for q, s in splits` is guaranteed to work for every consumer.
    """
    quadrant: str | None
    resolved_by: str                                   # role|topic|project|unresolved
    splits: tuple[tuple[str, float], ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        # `not in` on a tuple compares with ==, never hashes, so an unhashable
        # resolved_by (a list from a JSON payload) is refused, not raised on.
        if self.resolved_by not in RESOLVED_BY:
            raise ValueError(
                f"resolved_by {self.resolved_by!r} is not one of "
                + ", ".join(repr(v) for v in RESOLVED_BY))
        normalised = _normalised_splits(self.splits)
        if normalised is None:
            raise ValueError(
                f"splits {self.splits!r} is not a sequence of "
                "[quadrant, share] pairs")
        # frozen=True blocks plain assignment; this is the documented way to
        # finish initialising a frozen dataclass.
        object.__setattr__(self, "splits", normalised)


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

    # TYPE BEFORE VALUE here too: `q in _VALID` raises TypeError on an
    # unhashable quadrant and `s > 0` raises on a string or None, so a topic
    # list assembled upstream from Fathom data could abort the cascade before
    # it ever reached the boundary that reports such things.
    valid_topics = [(q, s) for q, s in topics
                    if _known_quadrant(q) and _finite_number(s) and s > 0]
    topic_note = ""
    if valid_topics:
        total = sum(s for _, s in valid_topics)
        if not _finite_number(total):
            # Every accepted share is finite and the SUM is not — two 1e308
            # shares do it. Dividing by inf turns EVERY share into 0.0 while
            # the meeting stays marked topic-resolved, so aggregate() assigns
            # none of its hours to any quadrant and silently routes the whole
            # meeting to unresolved under a "shares normalised" story that
            # never happened. Refuse to resolve by topic instead and fall
            # through to the rest of the cascade (project, then unresolved),
            # carrying a note that says which rule declined and why.
            valid_topics = []
            topic_note = ("topic shares sum outside the finite range — topic "
                          "resolution declined")
        else:
            note = ""
            # NORMALISE DOWN ONLY, matching aggregate(). Scaling an UNDER-1.0
            # total up to 1.0 invents attribution: a meeting whose topics
            # covered 0.6 of it is 60% about those quadrants, and the missing
            # 0.4 is hours nobody assigned — it belongs in unresolved, not
            # handed to whichever quadrant happened to be named. The two sites
            # normalising in opposite directions is what let this through.
            if total > 1.0 + 1e-6:
                # total >= every share (all are positive), so s / total is in
                # (0, 1] and cannot overflow.
                valid_topics = [(q, s / total) for q, s in valid_topics]
                note = "shares normalised"
                total = 1.0
            # The single-topic shortcut returns a quadrant-only Resolution, and
            # aggregate() books the WHOLE meeting to that quadrant — correct
            # only when the topic actually accounted for all of it. Below 1.0,
            # keep the share as a split so the remainder reaches unresolved.
            if len(valid_topics) == 1 and total >= 1.0 - 1e-6:
                return Resolution(valid_topics[0][0], "topic", note=note)
            return Resolution(None, "topic", tuple(valid_topics), note)

    if _known_quadrant(project_quadrant):
        return Resolution(project_quadrant, "project", note=topic_note)

    return Resolution(None, "unresolved", note=topic_note)


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
    """One meeting's hours and its attribution.

    `resolution` is CHECKED AT CONSTRUCTION, for the same reason
    Resolution's `splits` is: aggregate() reads `row.resolution.splits` and
    `.quadrant` unconditionally, so a row built with `None` (or a dict from a
    caller who thought this took raw payload) raised AttributeError three
    frames away and cost the whole week. `hours` is deliberately NOT checked
    here — it is a VALUE, and every value rule in this module lives in
    aggregate() so that direct callers and the payload path cannot diverge.
    """
    label: str
    resolution: Resolution
    hours: float

    def __post_init__(self) -> None:
        if not isinstance(self.resolution, Resolution):
            raise TypeError(
                "resolution must be a Resolution, not "
                f"{type(self.resolution).__name__}")


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
    # Hours from PROJECT rows only -- every project row whose hours were
    # usable, including one whose offense_pct was rejected and therefore
    # recorded no mode. This is the honest denominator for the week's
    # offense/defense share: by_mode covers only the project rows that had a
    # readable mode, so dividing by (offense + defense) would report a share
    # of a smaller base than "share of the week's project hours" claims.
    # Defaulted for the same reason as the two fields above.
    project_hours: float = 0.0

    def __post_init__(self) -> None:
        """The three mapping fields must BE mappings, checked here.

        Every consumer reads them unconditionally — `evaluate_flags` calls
        `w.by_quadrant.get(...)`, `_summary` calls `.items()` on all three —
        so a hand-built WeekTotals carrying a string raised AttributeError
        deep inside a flag rather than at the point of the mistake. Direct
        callers DO build these by hand (history entries, tests), which is
        exactly the caller a prose-only rule never reaches.

        `by_mode` must name both modes, because modes are exactly
        offense/defense and `_summary` indexes both directly.

        `by_quadrant_mode`'s inner dicts are checked for dict-ness and NOT for
        completeness, deliberately: `{"growth-driver": {"offense": 5.0}}` is a
        half-measured quadrant, which this module supports and reports as
        UNMEASURED rather than treating as zero defense. Refusing to build it
        would turn a case the design handles into a crash.

        These are SHAPES, not values. The numbers inside are still
        aggregate()'s and _history_entry_problem()'s business.
        """
        for name in ("by_quadrant", "by_mode", "by_quadrant_mode"):
            value = getattr(self, name)
            if not isinstance(value, dict):
                raise TypeError(
                    f"{name} must be a dict, not {type(value).__name__}")
        missing = [mode for mode in _MODES if mode not in self.by_mode]
        if missing:
            raise ValueError(
                "by_mode is missing " + ", ".join(repr(m) for m in missing))
        for quadrant, modes in self.by_quadrant_mode.items():
            if not isinstance(modes, dict):
                raise TypeError(
                    f"by_quadrant_mode[{quadrant!r}] must be a dict, not "
                    f"{type(modes).__name__}")


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
      * the RESULT of the arithmetic stays finite too. Finite inputs are not
        enough: 1e308 hours at 50% offense overflowed a plain
        `hours * offense_pct` to Infinity, and a few 1e308-hour rows overflow
        the running total the same way. Every number this module prints has
        to survive json.dumps(allow_nan=False), so the products are ordered
        so they cannot overflow (`hours * (pct / 100)`, a factor in [0, 1])
        and the running total is checked BEFORE a row is added to it. Every
        other accumulator is bounded by that total -- sum(by_quadrant) +
        unresolved == total, and by_mode/by_quadrant_mode sum to AT MOST the
        project hours inside it -- so guarding the total guards all of them.
        (At most, not exactly: a project row whose offense_pct was rejected
        contributes its hours to total_hours and project_hours and no mode
        hours at all. That gap is deliberate and is what `project_hours`
        exists to make visible; see _summary().)

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
    project_hours = 0.0
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
        if not _finite_number(total + pw.hours):
            # Finite hours, non-finite SUM. Adding this row would make
            # total_hours (and every percentage divided by it) Infinity,
            # which json.dumps(allow_nan=False) cannot render at all — the
            # whole week summary would fail to print over one row. Same
            # treatment as unusable hours: out of the week, and reported.
            rejected.append(RejectedRow(
                "project", _project_row_dict(pw),
                f"hours {pw.hours!r} overflows the week's running total "
                "(no longer a finite number) — row excluded from the week"))
            continue
        total += pw.hours
        project_hours += pw.hours
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
        # SCALE FIRST, MULTIPLY SECOND. `pw.hours * pw.offense_pct` is
        # evaluated before the division, so 1e308 hours at 50% overflowed to
        # Infinity and only then got divided by 100 — Infinity again. Both
        # factors below are in [0, 1], so the product can never exceed
        # pw.hours, which the guard above already proved finite.
        offense_hours = pw.hours * (pw.offense_pct / 100.0)
        defense_hours = pw.hours * ((100 - pw.offense_pct) / 100.0)
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
        if not _finite_number(total + row.hours):
            # Same overflow rule as the project loop above, and it fires on
            # meeting hours too: a finite meeting row added to a finite
            # running total can still leave the finite range.
            rejected.append(RejectedRow(
                "meeting", _meeting_row_dict(row),
                f"hours {row.hours!r} overflows the week's running total "
                "(no longer a finite number) — row excluded from the week"))
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
            if not _finite_number(total_share):
                # Every share is finite and non-negative and the SUM still
                # overflowed. 1.0/inf is 0.0, which would scale every share
                # to zero and route the row to unresolved with a "shares
                # normalised" story that never happened — a silent
                # correction. Say what actually failed instead.
                rejected.append(RejectedRow(
                    "meeting", _meeting_row_dict(row),
                    "split shares sum to a value outside the finite range — "
                    "whole row routed to unresolved"))
                unresolved += row.hours
                continue
            # NO TOLERANCE ON THE NORMALISATION THRESHOLD. This read
            # `> 1.0 + 1e-9`, so a total_share of 1.0000000005 was judged
            # "close enough to 1.0" and passed through unscaled — and
            # `row.hours * share` with row.hours at sys.float_info.max then
            # stored Infinity in by_quadrant, breaking the finite-output
            # invariant that 40,000 hostile fuzz iterations had survived
            # (the corpus never combined float-max hours with a share a hair
            # over 1.0). A tolerance that exists to avoid a pointless rescale
            # is not worth a hole in the invariant: normalise whenever the
            # shares sum to more than 1.0, full stop.
            scale = 1.0 / total_share if total_share > 1.0 else 1.0
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
            # RESULT-CHECKED, NOT JUST INPUT-CHECKED — the same rule the
            # running total already follows. Removing the tolerance above
            # closes the specific case, but normalisation is float division:
            # s * (1.0 / total_share) can still land a few ulps above 1.0,
            # and float-max hours has no headroom for even one ulp. So the
            # contributions are computed into a scratch dict and committed
            # only if every resulting bucket is still finite; otherwise the
            # whole row goes to unresolved and says so, exactly like a share
            # nobody can read. This is what keeps `every value finite` a
            # property of the OUTPUT rather than an inference from the input.
            contributions: dict[str, float] = {}
            for quadrant, share in splits:
                contributions[quadrant] = (contributions.get(quadrant, 0.0)
                                           + row.hours * share)
            if not all(_finite_number(by_quadrant[q] + c)
                       for q, c in contributions.items()):
                rejected.append(RejectedRow(
                    "meeting", _meeting_row_dict(row),
                    "split shares apportion these hours outside the finite "
                    "range — whole row routed to unresolved"))
                unresolved += row.hours
                continue
            for quadrant, contribution in contributions.items():
                by_quadrant[quadrant] += contribution
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
                      by_quadrant_mode, tuple(rejected), project_hours)


RELIABILITY_ZERO_WEEKS = 2
OPERATING_EFFICIENCY_CEILING = 0.40
# Spec §3.6 scopes the assets-decaying flag to quadrant ① and nowhere else.
DECAY_QUADRANT = "growth-driver"


def _quadrant_defense_share(week: WeekTotals, quadrant: str) -> float | None:
    """That quadrant's defense share of its OWN recorded mode hours, or None
    when it recorded none.

    None means "nobody measured", never "zero defense". Returning 0.0 for an
    unmeasured quadrant is the firing condition of the flag below against any
    week with defense in it — the fourth-instance bug one level down.

    The denominator is deliberately the quadrant's own offense + defense
    hours, which is exactly what the per-quadrant Offense / Defense column
    renders from (`quadrant_mode_percentages`). The week line's denominator is
    `project_hours` and it answers a different question; two numbers in one
    report must not both be called "the defense share"."""
    modes = week.by_quadrant_mode.get(quadrant)
    if not isinstance(modes, dict):
        return None
    # NO 0.0 DEFAULT on either read. An absent 'defense' key defaulted to 0.0
    # is a 0% defense share, which is this flag's firing condition against any
    # week with defense in it -- the same unknown-as-zero shape one level down.
    offense = modes.get("offense")
    defense = modes.get("defense")
    if not _finite_number(offense) or not _finite_number(defense):
        return None
    spent = offense + defense
    if spent <= 0:
        return None
    return defense / spent


def evaluate_flags(current: WeekTotals, history: list[WeekTotals],
                   driver_hours: float | None, held_hours: float | None,
                   rejects: list | None = None,
                   current_measured: bool = True) -> list[str]:
    """Each flag names the decision it forces. A flag with no decision
    attached does not belong here.

    ABSENT INPUT SUPPRESSES A FLAG AND SAYS SO; it never manufactures one.
    `driver_hours` / `held_hours` are `None` when the payload did not carry a
    readable number for them, and `current_measured` is False when the payload
    carried no row containers at all — an unmeasured week, whose 0h of
    reliability is not the same fact as a measured week that funded none. A
    suppressed flag is appended to `rejects` (as a `payload` row the caller
    already renders) rather than passing silently — "no flags fired" and "that
    flag could not run" mean opposite things and must not print
    identically."""
    flags: list[str] = []

    def suppress(row: dict, reason: str) -> None:
        if rejects is not None:
            rejects.append(RejectedRow("payload", row, reason))

    recent = [current, *history][:RELIABILITY_ZERO_WEEKS]
    # `.get("reliability")` with NO 0.0 default: a week whose by_quadrant does
    # not name reliability at all did not measure it, and 0h of reliability IS
    # this flag's firing condition. aggregate() and a validated history entry
    # both always name all five, so this only bites a hand-built WeekTotals --
    # which is exactly the caller a prose-only rule would not reach.
    reliability = [w.by_quadrant.get("reliability") for w in recent]
    if not current_measured:
        # Say WHICH of the two ways it was unmeasured. The reason a person
        # reads has to match what actually happened: this fired for a week
        # where meeting_rows read fine and only project_weeks was broken, and
        # a blanket "neither was readable" would have been simply false. A
        # reason that misdescribes its own cause is the same defect as a
        # silent one, one step later.
        suppress({"project_weeks": None, "meeting_rows": None},
                 "this week's hours could not be trusted as measured — either "
                 "no row container was readable at all, or one was supplied "
                 "and broken while the other read fine. Both `project_weeks` "
                 "and `meeting_rows` feed reliability hours, so a 0h total is "
                 "only believable when neither was unreadable. An unmeasured "
                 "week is not a week with 0h in it, so the "
                 "reliability-starvation flag did not run this week — see the "
                 "per-key rejections above for which container failed")
    elif any(not _finite_number(h) for h in reliability):
        suppress({"by_quadrant": "reliability"},
                 "a week in the comparison recorded no reliability hours at "
                 "all (the key is absent, not zero) — the "
                 "reliability-starvation flag did not run this week")
    elif (len(recent) == RELIABILITY_ZERO_WEEKS
            and all(hours == 0.0 for hours in reliability)):
        flags.append(
            f"Reliability starving — 0h for {RELIABILITY_ZERO_WEEKS} consecutive "
            "weeks. Fund it, or say out loud you are not."
        )

    if current.total_hours > 0:
        # The 0.0 default here is safe in the one direction that matters: an
        # absent operating-efficiency key reads as 0h, which SUPPRESSES this
        # flag (it needs a share above the ceiling to fire). Absent can never
        # manufacture it, so it is left as a floor rather than a guard.
        share = current.by_quadrant.get("operating-efficiency", 0.0) / current.total_hours
        if share > OPERATING_EFFICIENCY_CEILING:
            flags.append(
                f"operating-efficiency at {share:.0%} — the machine is eating "
                "the output it exists to produce."
            )

    # SCOPED TO ①, per spec §3.6 ("defense share on ① rising week over week").
    # It used to compare the WEEK-WIDE defense share while its message named
    # growth drivers, so a week where ① defense FELL and hygiene defense rose
    # fired it and named the wrong assets.
    if history:
        prior_share = _quadrant_defense_share(history[0], DECAY_QUADRANT)
        current_share = _quadrant_defense_share(current, DECAY_QUADRANT)
        if prior_share is None:
            suppress(
                {"history[0].by_quadrant_mode": DECAY_QUADRANT},
                f"last week recorded no {DECAY_QUADRANT} offense/defense hours "
                "(the prior week's `by_quadrant_mode` is absent or all zero) — "
                "the assets-decaying flag did not run this week")
        elif current_share is None:
            suppress(
                {"by_quadrant_mode": DECAY_QUADRANT},
                f"this week recorded no {DECAY_QUADRANT} offense/defense hours "
                "— the assets-decaying flag did not run this week")
        elif current_share > prior_share:
            flags.append(
                f"Defense share on {DECAY_QUADRANT} rose to "
                f"{current_share:.0%} of its recorded mode hours (last week "
                f"{prior_share:.0%}) — your best assets are decaying under you."
            )

    absent = [name for name, value in (("driver_hours", driver_hours),
                                       ("held_hours", held_hours))
              if value is None]
    if absent:
        suppress(
            {key: None for key in absent},
            " and ".join(absent) + (" is" if len(absent) == 1 else " are")
            + " absent from the payload — the held-vs-driver flag did not run "
              "this week (an unmeasured number is not 0.0)")
    elif held_hours > driver_hours:
        flags.append(
            f"held projects out-earned drivers ({held_hours:.1f}h vs "
            f"{driver_hours:.1f}h) — the ranking is not what you are doing."
        )

    return flags


# The three states a payload row container can be in, and they are THREE, not
# two. "Absent" and "invalid" both yield no rows, and NEITHER of them means
# the builder measured a week. Collapsing them into "the key was there" is
# what made `project_weeks: "bad"` and `project_weeks: null` read as MEASURED
# zero-hour weeks, which fired the two-week reliability-starvation flag off a
# payload from which no row was ever read. Key presence is not evidence of
# measurement; a readable container is. Defined up here because
# _history_from_payload() takes one as a default argument, and a default is
# evaluated at definition time.
_ROWS_ABSENT = "absent"      # the key was not in the payload at all
_ROWS_INVALID = "invalid"    # the key was there and was not a list of rows
_ROWS_READ = "read"          # a real list — possibly an empty one, which is a
                             # genuine measured zero and must still count


# Everything a prior week must carry before evaluate_flags may compare
# against it. Both top-level keys are required, `by_quadrant` must name all
# five quadrants and `by_mode` both modes — because a MISSING number here is
# not a week with a zero in it, it is a week nobody measured, and the two
# trend flags both fire on zeros.
_REQUIRED_HISTORY_KEYS = ("by_quadrant", "by_mode")
_MODES = ("offense", "defense")


def _history_entry_problem(entry) -> str | None:
    """Why this prior week cannot be trusted, or None when it can.

    THE GUARD LIVES HERE, IN THE MODULE, NOT IN THE CALLING SKILL'S PROSE.
    "Unknown treated as zero" has now been the bug three times in this one
    feature — in the CLI contract, in _totals_from_history_entry(), and in
    the rekeying step close-week performs before it gets here — and a rule
    written only in prose is a rule the fourth caller does not have. The
    reason it keeps coming back is that zero is not a neutral value for
    either trend flag:

      * a prior week read as all-zero hours has 0h of reliability, which IS
        the reliability-starvation flag's firing condition. An absent week
        thereby manufactures "0h for 2 consecutive weeks";
      * a prior week of {"offense": 10, "defense": null} has a non-zero mode
        total and a 0% defense share, which IS the rising-defense-share
        flag's firing condition against any current week with defense in it.

    So a prior week is either complete and finite, or it is not history.
    Nothing here is silently corrected and nothing raises: the reason comes
    back as a string for the caller to report."""
    if not isinstance(entry, dict):
        return f"entry is {type(entry).__name__}, not an object"
    missing = [k for k in _REQUIRED_HISTORY_KEYS if k not in entry]
    if missing:
        return ("entry is missing required key(s): "
                + ", ".join(repr(k) for k in missing))

    raw_quadrant = entry["by_quadrant"]
    if not isinstance(raw_quadrant, dict):
        return f"'by_quadrant' is {type(raw_quadrant).__name__}, not an object"
    absent = [q for q in (*QUADRANTS, CROSS_CUTTING) if q not in raw_quadrant]
    if absent:
        return ("'by_quadrant' is missing quadrant(s): "
                + ", ".join(repr(q) for q in absent))
    for key, value in raw_quadrant.items():
        if not _known_quadrant(key):
            return f"'by_quadrant' key {_json_safe(key)!r} is not a quadrant"
        if not _finite_number(value) or value < 0:
            return (f"'by_quadrant[{key}]' is {_json_safe(value)!r}, not a "
                    "non-negative finite number")
    if not _finite_number(sum(raw_quadrant.values())):
        return "'by_quadrant' hours sum to a value outside the finite range"

    raw_mode = entry["by_mode"]
    if not isinstance(raw_mode, dict):
        return f"'by_mode' is {type(raw_mode).__name__}, not an object"
    for mode in _MODES:
        if mode not in raw_mode:
            return f"'by_mode' is missing {mode!r}"
        if not _finite_number(raw_mode[mode]) or raw_mode[mode] < 0:
            return (f"'by_mode[{mode}]' is {_json_safe(raw_mode[mode])!r}, "
                    "not a non-negative finite number")
    if not _finite_number(raw_mode["offense"] + raw_mode["defense"]):
        return "'by_mode' hours sum to a value outside the finite range"

    # `by_quadrant_mode` is OPTIONAL, because prior notes written before the
    # assets-decaying flag was scoped to ① do not carry it. Absent, it costs
    # only that one flag, which evaluate_flags then suppresses and reports —
    # it must not invalidate the whole entry and take the reliability
    # -starvation flag down with it. PRESENT, it is held to the same standard
    # as everything else here: a half-readable quadrant is a quadrant nobody
    # measured, and reading its missing half as 0.0 is the same manufactured
    # flag one level down.
    if "by_quadrant_mode" in entry:
        raw_quadrant_mode = entry["by_quadrant_mode"]
        if not isinstance(raw_quadrant_mode, dict):
            return ("'by_quadrant_mode' is "
                    f"{type(raw_quadrant_mode).__name__}, not an object")
        for key, modes in raw_quadrant_mode.items():
            if not _known_quadrant(key):
                return ("'by_quadrant_mode' key "
                        f"{_json_safe(key)!r} is not a quadrant")
            if not isinstance(modes, dict):
                return (f"'by_quadrant_mode[{key}]' is "
                        f"{type(modes).__name__}, not an object")
            for mode in _MODES:
                if mode not in modes:
                    return f"'by_quadrant_mode[{key}]' is missing {mode!r}"
                if not _finite_number(modes[mode]) or modes[mode] < 0:
                    return (f"'by_quadrant_mode[{key}][{mode}]' is "
                            f"{_json_safe(modes[mode])!r}, not a non-negative "
                            "finite number")
            if not _finite_number(modes["offense"] + modes["defense"]):
                return (f"'by_quadrant_mode[{key}]' hours sum to a value "
                        "outside the finite range")
    return None


_NO_HISTORY_CONSEQUENCE = (
    "the reliability-starvation and assets-decaying flags did not run this "
    "week")


def _history_from_payload(entries: list, rejects: list,
                          state: str = _ROWS_READ) -> list[WeekTotals]:
    """Validated prior weeks — or none of them.

    ONE BAD ENTRY SUPPRESSES THE WHOLE HISTORY. evaluate_flags reads this
    list positionally: history[0] IS "last week". Dropping a malformed
    entry 0 while keeping entry 1 promotes a two-weeks-ago week into last
    week's slot and compares this week against it — manufacturing a trend
    out of a different week, which is the same failure as reading an absent
    week as zero. Suppressing everything is the only reading that cannot
    invent a trend.

    EVERY suppression is REPORTED, as a `payload` rejection the caller
    already has to render — the malformed case AND the absent/empty one.
    Without it, "no flags fired" and "the trend flags could not run" print
    identically, and those two mean opposite things. The absent case is the
    COMMON one, not the edge: the first week on the pipeline, a gap week
    (which close-week Step 2a #5 signals by passing `[]`), an extended
    close, a week whose prior Step 2a was rejected, or any note predating
    this pipeline. Reporting only the malformed case left the artifact —
    the weekly note — reading identically in both, which is the exact
    failure this guard was written to end."""
    if not entries:
        # Three states, three truthful sentences. `history: "bad"` is neither
        # absent nor empty, and saying "no `history` key in the payload" about
        # a key that WAS there is the kind of untrue reason a reader acts on.
        what = {
            _ROWS_ABSENT: ("no `history` key in the payload", None),
            _ROWS_INVALID: ("`history` was not a list of prior weeks", "invalid"),
        }.get(state, ("`history` is empty", []))
        rejects.append(RejectedRow(
            "payload", {"history": what[1]},
            what[0] + " — there is no prior week to compare against, so "
            + _NO_HISTORY_CONSEQUENCE))
        return []
    problems = []
    for index, entry in enumerate(entries):
        problem = _history_entry_problem(entry)
        if problem:
            problems.append(f"entry {index}: {problem}")
    if problems:
        rejects.append(RejectedRow(
            "payload",
            {"history": [_payload_row_dict(e) for e in entries]},
            "history " + "; ".join(problems)
            + " — history suppressed (read as []); "
            + _NO_HISTORY_CONSEQUENCE))
        return []
    return [_totals_from_history_entry(entry) for entry in entries]


def _totals_from_history_entry(entry: dict) -> WeekTotals:
    """Turn ONE ALREADY-VALIDATED history entry into a WeekTotals.

    Call it through _history_from_payload(), never directly on raw payload
    data: this function reads numbers, it does not judge them, and an entry
    that reaches it unvalidated reads as zeros — which is precisely how a
    missing prior week used to manufacture a reliability-starvation or
    rising-defense-share flag. _history_entry_problem() is where that
    judgment lives.

    The defensive reads below stay because they are cheap and because a
    direct caller (a test, a future entry point) is still not allowed to
    crash the week — but they are a floor, not the guard."""
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
        for mode in _MODES
    }
    # NOT _empty_by_quadrant_mode(). A history entry that carried no
    # by_quadrant_mode must come back with NOTHING here, not with five
    # quadrants of 0.0/0.0 — zero mode hours reads as "0% defense last
    # week", which is the assets-decaying flag's firing condition against any
    # current week with defense in it. Absent has to stay absent all the way
    # to _quadrant_defense_share(), which returns None for it and suppresses
    # the flag. Only quadrants the entry actually named appear here.
    by_quadrant_mode: dict[str, dict[str, float]] = {}
    raw_quadrant_mode = entry.get("by_quadrant_mode")
    if isinstance(raw_quadrant_mode, dict):
        for key, modes in raw_quadrant_mode.items():
            if not _known_quadrant(key) or not isinstance(modes, dict):
                continue
            if all(_finite_number(modes.get(m)) for m in _MODES):
                by_quadrant_mode[key] = {m: float(modes[m]) for m in _MODES}
    # A history entry carries no project_hours of its own. The mode hours it
    # DOES carry are project hours by construction (only project rows record
    # a mode), so this is the one project-hours figure the entry attests —
    # and setting it keeps WeekTotals' documented relationship between
    # by_mode and project_hours true for a history week instead of leaving a
    # 0.0 that a future consumer would read as "no project work".
    return WeekTotals(by_quadrant, by_mode, 0.0, sum(by_quadrant.values()),
                      by_quadrant_mode, (),
                      by_mode["offense"] + by_mode["defense"])


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
    anything else is a shape failure, REPORTED rather than unpacked, because
    `for q, s in splits` raises on it.

    This is the payload-side half of the shape rule and it exists to produce a
    precise reason naming the offending entry. The enforcing half is
    Resolution.__post_init__, which refuses to build the object at all. Both
    read the shape through _is_pair() so the two cannot drift apart — the
    failure mode this module has already suffered twice."""
    if raw is None:
        return (), None
    if not isinstance(raw, (list, tuple)):
        return (), f"'splits' is {type(raw).__name__}, not a list"
    pairs = []
    for entry in raw:
        if not _is_pair(entry):
            return (), ("'splits' entry is not a [quadrant, share] pair: "
                        f"{_json_safe(entry)!r}")
        pairs.append((entry[0], entry[1]))
    return tuple(pairs), None


def _payload_rows(payload: dict, key: str,
                  rejects: list) -> tuple[list, str]:
    """(rows, state) — the rows under `key`, plus which of the three states
    above the container was in.

    A non-list container silently read as empty is a whole week of work
    vanishing, so an invalid one is REPORTED. It is also reported as
    unreadable to the caller through `state`, because a container nobody
    could read did not measure anything: see _ROWS_INVALID above."""
    if key not in payload:
        return [], _ROWS_ABSENT
    rows = payload[key]
    if isinstance(rows, (list, tuple)):
        return list(rows), _ROWS_READ
    rejects.append(RejectedRow(
        "payload", {key: _json_safe(rows)},
        f"payload key {key!r} is {type(rows).__name__}, not a list — no rows "
        "were read from it"))
    return [], _ROWS_INVALID


def _week_number(payload: dict, key: str, rejects: list) -> float | None:
    """driver_hours / held_hours, or None when the payload did not give one.

    ABSENT IS NOT 0.0. `payload.get(key, 0.0)` could not tell "nobody
    measured driver hours" from "driver hours were measured and are zero",
    and 0.0 is not a neutral value here: `held_hours > driver_hours` is how
    the held-vs-driver flag fires, so an absent driver_hours manufactured
    "held projects out-earned drivers (5.0h vs 0.0h)" — a decision-forcing
    claim about the builder's own prioritisation, invented from a field
    nobody supplied, entirely silently. That was the FOURTH appearance of
    "unknown treated as zero" in this feature.

    Both failures now read the same way and neither is fatal: absent, or
    present-but-unreadable, comes back as None, and evaluate_flags suppresses
    the flag and says so. A present-but-unreadable value is reported HERE as
    well, because "the value you sent is not a number" and "the flag did not
    run" are two different things a reader needs.

    NEGATIVE IS UNREADABLE, NOT SMALL. Hours worked cannot be negative, and
    accepting one did not merely pass a bad number through — it INVERTED the
    flag's meaning. `driver_hours: -1` beside `held_hours: 0` satisfies
    `held > driver` and printed "held projects out-earned drivers (0.0h vs
    -1.0h)": a decision-forcing claim about the builder's own prioritisation,
    fired by arithmetic on a number that could not be hours, with the
    malformed input never reported at all. Same rule as every other hours
    field in this module (project rows, meeting rows): non-negative or
    unusable."""
    if key not in payload:
        return None
    value = payload[key]
    if _finite_number(value) and value >= 0:
        return float(value)
    rejects.append(RejectedRow(
        "payload", {key: _json_safe(value)},
        f"{key} {value!r} is not a non-negative finite number — read as "
        "absent, never as 0.0"))
    return None


def _crash_rejection(exc: BaseException) -> RejectedRow:
    """The last-resort rejection: an exception nobody anticipated, rendered as
    a `payload` row a human can read and a machine can parse.

    LOUD AND SPECIFIC, NEVER SWALLOWED. It names the exception type and
    message, and it is prefixed INTERNAL so it cannot be mistaken for a data
    problem the builder caused — a floor that quietly emitted an empty week
    would be worse than the crash it replaced, because an empty week looks
    exactly like a light week."""
    return RejectedRow(
        "payload",
        {"exception": type(exc).__name__, "message": _json_safe(str(exc))},
        f"INTERNAL: unhandled {type(exc).__name__}: {exc} — the week summary "
        "could not be computed from this input and NO rows were read from it. "
        "Every number in this result is zero because nothing was aggregated, "
        "not because nothing was worked. Either the input is not the shape "
        "this module documents, or this is a bug in companion/portfolio.py; "
        "report it with the input that produced it.")


def summarize(payload: dict) -> dict:
    """The one entry point a caller (skill prose, CLI) should use: turn a
    JSON-shaped week description into the numbers a person reads. Everything
    upstream of this (attributing a meeting, reading frontmatter) is the
    caller's job; this function only aggregates and flags.

    NOTHING RAISES OUT OF HERE, FOR ANY INPUT WHATSOEVER — and that is now a
    FLOOR, not a claim assembled out of per-field guards. Three review rounds
    each found a different escape from the same class: a 1-tuple in `splits`
    (ValueError), a huge JSON integer (OverflowError), a string where a number
    belonged (TypeError). Each one exited the CLI with status 1 and an EMPTY
    stdout, so the caller saw nothing at all — no numbers, no rejection, no
    reason, on the one day of the week this module exists to serve. The
    specific guards below all stay; this wrapper is what makes the guarantee
    hold for the shape nobody has thought of yet, by turning any unhandled
    exception into a valid JSON result carrying a `payload` rejection that
    names it.

    Belt-and-braces means BOTH, in this order: the specific validation is
    what produces a precise, per-row reason a builder can act on, and the
    floor is what stops the absence of one from costing the whole week. A
    rejection from the floor is deliberately loud (see _crash_rejection) so
    it can never read as a clean week."""
    try:
        return _summarize(payload)
    except Exception as exc:                     # noqa: BLE001 — the floor
        # The fallback path touches NO payload data: aggregate([], []) over two
        # empty lists and _summary() over its all-zero result are pure
        # arithmetic on dicts this module built itself, with no division by a
        # zero denominator (every share is guarded by `if total else 0.0`).
        # That is why it is safe to call unguarded here — there is no input
        # left for it to trip over.
        return _summary(aggregate([], []), [], [_crash_rejection(exc)])


def _summarize(payload: dict) -> dict:
    """summarize()'s body, with the specific validation. Call summarize().

    It owns exactly one rule of its own: the payload's SHAPE. A row missing
    a required key, a `splits` that isn't a list of pairs, a `resolved_by`
    outside the four-value vocabulary, a container that isn't a list, a
    week-level number that isn't one — all are reported as `rejected` entries
    here, because aggregate() takes dataclasses and can never see the
    payload's dicts. VALUES are still aggregate()'s alone; a value check
    written here is how the two halves came apart once already (a bad split
    quadrant was filtered out in this function and still raised KeyError
    inside aggregate() for every direct caller).

    One malformed row costs its own row; it must never cost the week summary,
    which is the only thing standing between the builder and a silently
    missing Friday."""
    shape_rejects: list[RejectedRow] = []

    if not isinstance(payload, dict):
        return _summary(aggregate([], []), [], [RejectedRow(
            "payload", {"payload": _json_safe(payload)},
            f"payload is {type(payload).__name__}, not an object — nothing "
            "could be read from it")])

    project_rows, project_state = _payload_rows(
        payload, "project_weeks", shape_rejects)
    meeting_payload_rows, meeting_state = _payload_rows(
        payload, "meeting_rows", shape_rejects)

    project_weeks = []
    for pw in project_rows:
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
    for mr in meeting_payload_rows:
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
        # `resolved_by` names which cascade rule fired, and it is a CLOSED
        # four-value vocabulary. Reported here, at the payload boundary, for
        # the same reason `splits` is: Resolution refuses to be built with an
        # invented one, so without this gate a drifted value would reach the
        # floor and cost the whole week instead of its own row.
        if mr["resolved_by"] not in RESOLVED_BY:
            shape_rejects.append(RejectedRow(
                "meeting", _payload_row_dict(mr),
                f"resolved_by {mr['resolved_by']!r} is not one of "
                + ", ".join(repr(v) for v in RESOLVED_BY)
                + " — row excluded from the week"))
            continue
        # Values pass through EXACTLY as given from here: aggregate() is the
        # one boundary that checks quadrants, shares, hours and offense_pct.
        resolution = Resolution(
            quadrant=mr.get("quadrant"),
            resolved_by=mr["resolved_by"],
            splits=splits,
        )
        meeting_rows.append(MeetingRow(mr["label"], resolution, mr["hours"]))

    history_rows, history_state = _payload_rows(
        payload, "history", shape_rejects)
    history = _history_from_payload(history_rows, shape_rejects, history_state)

    current = aggregate(project_weeks, meeting_rows)
    flags = evaluate_flags(
        current, history,
        driver_hours=_week_number(payload, "driver_hours", shape_rejects),
        held_hours=_week_number(payload, "held_hours", shape_rejects),
        # Every flag that could NOT be evaluated is reported through here,
        # into the same `rejected` list the caller already renders.
        rejects=shape_rejects,
        # MEASURED MEANS A CONTAINER WAS READ, NOT THAT A KEY WAS THERE.
        # A payload carrying NEITHER readable row container did not measure a
        # week; it is not a week that measured zero. `project_weeks: []` IS a
        # measured empty week (a genuine holiday) and still counts — the same
        # absent-vs-empty distinction `history` already makes.
        #
        # This read `"project_weeks" in payload`, i.e. key presence, while
        # _payload_rows() next door REJECTED an invalid container — so
        # `project_weeks: "bad"` or `project_weeks: null` counted as a
        # measured zero-hour week and, beside one prior zero-reliability week,
        # fired "reliability starving — 0h for 2 consecutive weeks" out of a
        # payload from which not one row was ever read. Key presence is not
        # evidence of measurement.
        # AND "at least one container was read" was still too weak. With
        # `project_weeks: "bad"` beside `meeting_rows: []`, one container read
        # fine (there were genuinely no meetings) so the week counted as
        # measured — and a 0h reliability total got trusted even though the
        # project rows, which also contribute reliability hours, were supplied
        # and broken. A zero is only trustworthy when nothing that feeds it was
        # unreadable, so a container that was PRESENT AND INVALID poisons the
        # measurement even when its sibling is fine. Absent is different: the
        # caller supplied what it had.
        current_measured=(
            _ROWS_INVALID not in (project_state, meeting_state)
            and _ROWS_READ in (project_state, meeting_state)
        ),
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
    # THE DENOMINATOR IS ALL PROJECT HOURS, not the project hours that
    # happened to record a mode. `by_mode["offense"] + by_mode["defense"]`
    # omits every project row whose offense_pct was rejected -- that row's
    # hours are in total_hours and in project_hours, but it contributed no
    # mode hours at all. Dividing by the mode hours made offense and defense
    # sum to 100% of a base nobody was told had shrunk, which is the opposite
    # of what "share of the week's project hours" says. Divided by
    # project_hours the two shares sum to LESS than 100% exactly when some
    # project hours have no mode recorded -- the truthful reading, and the
    # missing slice is visible rather than absorbed.
    mode_percentages = {
        mode: (hours / current.project_hours if current.project_hours else 0.0)
        for mode, hours in current.by_mode.items()
    }
    # The slice mode_percentages does NOT cover: project hours that recorded
    # no offense/defense at all. Returned rather than left as a subtraction
    # for the renderer to perform, because "offense 45% / defense 30%" is a
    # pair a reader will try to reconcile to 100% and the missing 25% is the
    # only thing that explains it. max() is float slop only.
    unmoded_hours = max(0.0, current.project_hours
                        - (current.by_mode["offense"] + current.by_mode["defense"]))
    # READ THE MODES THE SAME WAY _quadrant_defense_share() DOES. This
    # indexed modes["offense"] / ["defense"] directly while its sibling reader
    # two hundred lines up guarded both with .get() and a finiteness check --
    # so a half-written by_quadrant_mode ({"growth-driver": {"offense": 5.0}}),
    # a shape the module deliberately SUPPORTS as "half measured", was
    # unmeasured over there and a KeyError over here. Two readings of one
    # field is how the halves of this module have come apart before; an
    # unreadable half reads as no mode at all, which the renderer already
    # prints as an em dash.
    quadrant_mode_percentages = {}
    for quadrant, modes in current.by_quadrant_mode.items():
        hours_by_mode = {
            mode: (modes.get(mode) if _finite_number(modes.get(mode)) else 0.0)
            for mode in _MODES
        }
        spent = hours_by_mode["offense"] + hours_by_mode["defense"]
        quadrant_mode_percentages[quadrant] = {
            mode: (hours / spent if spent else 0.0)
            for mode, hours in hours_by_mode.items()
        }

    return {
        "by_quadrant": current.by_quadrant,
        "by_mode": current.by_mode,
        "by_quadrant_mode": current.by_quadrant_mode,
        "unresolved_hours": current.unresolved_hours,
        "total_hours": current.total_hours,
        # The denominator behind mode_percentages, returned so the renderer
        # can say what the offense/defense shares are a share OF -- and so a
        # pair that sums to less than 100% is explainable rather than a bug.
        "project_hours": current.project_hours,
        "percentages": percentages,
        "mode_percentages": mode_percentages,
        # Project hours with no mode recorded, and their share of
        # project_hours -- exactly what mode_percentages' two shares are
        # missing when they sum to less than 100%.
        "unmoded_hours": unmoded_hours,
        "unmoded_pct": (unmoded_hours / current.project_hours
                        if current.project_hours else 0.0),
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
# the toolkit may be running from its own private runtime). $PY below is what
# `"$TC" python-path` printed — the companion binary naming its OWN
# interpreter. It is not the file beside $TC: ensure-companion.sh can resolve
# $TC from PATH, whose directory need not hold a Python at all. See
# skills/close-week/references/portfolio-attribution.md §7.
USAGE = (
    'usage (run with the companion interpreter, not a bare python3):\n'
    '  "$PY" -m companion.portfolio                < payload.json\n'
    '  "$PY" -m companion.portfolio --parse-daily  < daily-note.md\n'
)


def _parse_daily_result(md: str) -> dict:
    parsed = parse_daily_note(md)
    return {
        "project_weeks": [
            {"project": pw.project, "quadrant": pw.quadrant,
             "offense_pct": pw.offense_pct, "hours": pw.hours}
            for pw in parsed.projects
        ],
        "skipped_lines": parsed.skipped,
        "skipped_count": parsed.skipped_count,
    }


def main(argv: list[str] | None = None) -> int:
    """Two modes, both stdin -> stdout JSON.

    Default: read a week payload and print summarize()'s result.

    --parse-daily: read ONE daily note's markdown and print its
    '## Projects Touched' rows plus every line that did not parse. This
    mode exists so close-week never hand-rolls a regex for the close-day
    format contract, and so a drifted line is reported at the confirm gate
    rather than quietly shrinking the week's hours.

    NEVER A TRACEBACK, NEVER AN EMPTY STDOUT, NEVER A NON-ZERO EXIT FOR A
    DATA PROBLEM. summarize() has its own floor, but main() adds work
    OUTSIDE it that could still fail the same way — `json.load(sys.stdin)`
    on malformed JSON, `sys.stdin.read()` on undecodable bytes, json.dumps
    on the result — and every one of those used to exit 1 with nothing on
    stdout, which the caller cannot tell from a week with no work in it. So
    both modes are floored here too, and both print parseable JSON carrying
    a rejection that names the exception.

    The ONE non-zero exit that remains is a usage error (unknown argv),
    which is a caller bug, not a data problem, and produces no JSON at all
    by design."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--parse-daily"]:
        try:
            result = _parse_daily_result(sys.stdin.read())
        except Exception as exc:                 # noqa: BLE001 — the floor
            rejection = _crash_rejection(exc)
            # This mode's result shape has no `rejected` list, so the failure
            # is routed into `skipped_lines` / `skipped_count` — which the
            # skill is ALREADY required to report at its confirm gate, per
            # day, even when the count is 0. A new key nobody was told to read
            # would be a silent failure wearing a report's clothes. `error`
            # carries the machine-readable form beside it.
            result = {"project_weeks": [], "skipped_lines": [rejection.reason],
                      "skipped_count": 1, "error": rejection.row}
        print(json.dumps(result, indent=2))
        return 0
    if args:
        sys.stderr.write(USAGE)
        return 2
    try:
        result = summarize(json.load(sys.stdin))
        rendered = json.dumps(result, indent=2)
    except Exception as exc:                     # noqa: BLE001 — the floor
        rendered = json.dumps(
            _summary(aggregate([], []), [], [_crash_rejection(exc)]), indent=2)
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
