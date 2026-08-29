"""Acceptance test: reproduce a week whose answer is already known.

Hand-built close for 2026-08-22..28 recorded 52.6h total, ~23.75h of meetings
across 26, a parked build lane at ~4h, and a 30-day silent-outage fix. If the
pipeline cannot reproduce this week, it is not ready for one we do not know.

Project slugs below are ANONYMISED (project-a .. project-g) because this repo
is public and the standing rule is that real internal project names never
appear in it. The real slug<->project-a..g mapping lives in the user's own
weekly note (02-weekly/2026-W35.md), outside this repo -- not here. Every
quadrant, mode (offense_pct) and hours value is kept exactly as hand-built;
only the names were swapped, since the numbers are what reproduce the week
and the names are not. The same anonymisation is applied to the meeting
labels below (generic role/ceremony names, no real project or person names).

Why 22.0h (this file's project total) is not 52.6h (the week's hand-built
total): W35_PROJECTS holds PROJECT rows only -- the '## Projects Touched'
tally from daily notes. The week's full 52.6h also includes ~23.75h of
meetings across 26 (added below as W35_MEETINGS) plus desk time that was
never attributed to any single project. 22.0 + 23.75 = 45.75, still short of
52.6 -- the remaining ~6.85h is unattributed desk time this module has no
row type for and does not claim to reproduce. That gap is expected, not a
failed reproduction; the module-level assertions below hold the two totals
apart on purpose rather than reconciling them into one number.

One correction to the spec's stated acceptance criterion, recorded here
because it is a finding rather than a defect: the ④-starvation flag is true
of W35's PROJECT rows (no project carried a reliability category) but NOT of
the full week, which puts 1.25h of meeting time into reliability. The full
week instead trips the operating-efficiency ceiling at 52%. Both are
asserted below, as they are, rather than the fixture being bent until the
originally-expected flag appears.
"""
import pytest
from companion.portfolio import (
    ProjectWeek, MeetingRow, Resolution, WeekTotals, aggregate, evaluate_flags,
)

# Hours from the hand-built W35 close. Quadrants per project frontmatter;
# mode per the Work Log bullets recorded in each daily note.
W35_PROJECTS = [
    ProjectWeek("project-a", "operating-efficiency", 100, 4.0),  # parked build lane
    ProjectWeek("project-b", "operating-efficiency", 100, 5.5),
    ProjectWeek("project-c", "cross-cutting",        100, 6.5),
    ProjectWeek("project-d", "operating-efficiency",  50, 2.0),
    ProjectWeek("project-e", "operating-efficiency", 100, 1.5),
    ProjectWeek("project-f", "operating-efficiency",   0, 1.0),  # silent outage fix
    ProjectWeek("project-g", "operating-efficiency", 100, 1.5),
]

# 23.75h across 26 meetings, distributed by day as hand-built:
#   Sat 0h/0, Sun 0h/0, Mon 4.1h/5, Tue 4.3h/5, Wed 6.6h/6, Thu 3.25h/4, Fri 5.5h/6
# Resolutions are constructed directly (as the pipeline would after running
# resolve_meeting) rather than derived here, exercising a mix: role, a topic
# split across two quadrants, project, and unresolved -- so the
# sum(by_quadrant) + unresolved == total invariant runs on realistic data,
# not just the single-row example below it.
W35_MEETINGS = [
    # Mon -- 5 meetings, 4.1h
    MeetingRow("Project Sync",       Resolution("operating-efficiency", "project"), 1.0),
    MeetingRow("Working Session",    Resolution("growth-driver", "topic"),          0.75),
    MeetingRow("Manager 1:1",        Resolution("hygiene", "role"),                 0.75),
    MeetingRow("Standup",            Resolution("operating-efficiency", "project"), 0.6),
    MeetingRow("Impromptu Call",     Resolution(None, "unresolved"),                1.0),
    # Tue -- 5 meetings, 4.3h
    MeetingRow("Leadership Sync",    Resolution("cross-cutting", "topic"),          1.0),
    MeetingRow("Ops Review",         Resolution("operating-efficiency", "project"), 1.0),
    MeetingRow("Cross-Team Planning", Resolution(
        None, "topic",
        splits=(("growth-driver", 0.6), ("operating-efficiency", 0.4)),
    ), 0.75),
    MeetingRow("Incident Review",    Resolution("reliability", "role"),             0.75),
    MeetingRow("Compliance Check-in", Resolution("hygiene", "project"),             0.8),
    # Wed -- 6 meetings, 6.6h
    MeetingRow("Sprint Planning",    Resolution("operating-efficiency", "project"), 1.5),
    MeetingRow("Strategy Session",   Resolution("growth-driver", "topic"),          1.5),
    MeetingRow("Coaching 1:1",       Resolution("hygiene", "role"),                 1.0),
    MeetingRow("Exec Sync",          Resolution("cross-cutting", "project"),        1.0),
    MeetingRow("Process Review",     Resolution("operating-efficiency", "topic"),   0.75),
    MeetingRow("Ad-hoc Huddle",      Resolution(None, "unresolved"),                0.85),
    # Thu -- 4 meetings, 3.25h
    MeetingRow("Team Standup",       Resolution("operating-efficiency", "project"), 1.0),
    MeetingRow("Growth Review",      Resolution("growth-driver", "topic"),          1.0),
    MeetingRow("HR Check-in",        Resolution("hygiene", "role"),                 0.75),
    MeetingRow("Reliability Triage", Resolution("reliability", "project"),          0.5),
    # Fri -- 6 meetings, 5.5h
    MeetingRow("Roadmap Review",     Resolution("operating-efficiency", "topic"),   1.5),
    MeetingRow("Growth Planning",    Resolution("growth-driver", "project"),        1.0),
    MeetingRow("Board Prep",         Resolution("cross-cutting", "role"),           1.0),
    MeetingRow("Governance Review",  Resolution("hygiene", "topic"),                0.75),
    MeetingRow("Weekly Sync",        Resolution("operating-efficiency", "project"), 0.75),
    MeetingRow("Unplanned Zoom",     Resolution(None, "unresolved"),                0.5),
]

assert len(W35_MEETINGS) == 26
assert sum(m.hours for m in W35_MEETINGS) == pytest.approx(23.75)


def test_w35_total_project_hours_match_the_hand_built_close():
    totals = aggregate(W35_PROJECTS, [])
    assert totals.total_hours == pytest.approx(22.0)


def test_w35_parked_build_lane_lands_in_operating_efficiency():
    totals = aggregate(W35_PROJECTS, [])
    assert totals.by_quadrant["operating-efficiency"] >= 4.0


def test_w35_silent_outage_fix_lands_in_its_quadrants_defense_column():
    """The 30-day silent-outage fix was pure defense (offense_pct 0). Assert
    that THROUGH aggregate() -- reading offense_pct back off the fixture
    would only test the fixture."""
    totals = aggregate(W35_PROJECTS, [])
    modes = totals.by_quadrant_mode["operating-efficiency"]
    # 4.0 + 5.5 + 1.5 + 1.5 fully offense, 2.0 at 50/50, 1.0 fully defense.
    assert modes["offense"] == pytest.approx(13.5)
    assert modes["defense"] == pytest.approx(2.0)


# The ④-starvation flag needs TWO consecutive zero-reliability weeks. This
# repo has no hand-built W34 to reproduce, so the prior week below is an
# explicitly synthetic minimum -- no reliability hours, no recorded mode --
# built only to exercise that two-week condition. It is NOT a reproduction
# of W34. Using the W35 fixture as its own prior week (what this file did
# originally) makes the check self-referential and proves nothing.
SYNTHETIC_PRIOR_WEEK_NO_RELIABILITY = WeekTotals(
    by_quadrant={"growth-driver": 0.0, "operating-efficiency": 10.0,
                 "hygiene": 0.0, "reliability": 0.0, "cross-cutting": 0.0},
    by_mode={"offense": 0.0, "defense": 0.0},
    unresolved_hours=0.0,
    total_hours=10.0,
)


def test_w35_project_rows_alone_record_no_reliability_time():
    """The project half of the week: no project carried a reliability
    category, which is the finding the spec's acceptance criterion names."""
    totals = aggregate(W35_PROJECTS, [])
    assert totals.by_quadrant["reliability"] == 0.0


def test_w35_reliability_starvation_fires_on_a_genuinely_zero_week():
    """Given a week that records zero reliability hours and a prior week
    that also did, the flag fires. Asserted on the project rows, which is
    the only part of W35 that reads zero -- see the next test for what the
    FULL week does."""
    totals = aggregate(W35_PROJECTS, [])
    flags = evaluate_flags(totals, [SYNTHETIC_PRIOR_WEEK_NO_RELIABILITY],
                           driver_hours=11.0, held_hours=11.0)
    assert any("reliability starving" in f.lower() for f in flags)


def test_w35_full_week_does_not_starve_reliability_and_flags_the_machine():
    """The truth about the whole week, meetings included: reliability is NOT
    at zero -- two meetings (Incident Review 0.75h, Reliability Triage 0.5h)
    put 1.25h into it -- so the ④ flag correctly does NOT fire. What fires
    instead is the operating-efficiency ceiling at 52%.

    This is asserted rather than engineered away. The earlier version of
    this file asserted the ④ flag against the projects-only aggregate while
    the meeting fixture in the same file contradicted it; the honest fix is
    to state what the full week actually shows, not to move meeting hours
    out of reliability until the desired flag appears."""
    totals = aggregate(W35_PROJECTS, W35_MEETINGS)
    assert totals.by_quadrant["reliability"] == pytest.approx(1.25)

    flags = evaluate_flags(totals, [SYNTHETIC_PRIOR_WEEK_NO_RELIABILITY],
                           driver_hours=11.0, held_hours=11.0)
    assert not any("reliability starving" in f.lower() for f in flags)
    # 23.9h of 45.75h is operating-efficiency -- over the 40% ceiling.
    assert any("operating-efficiency at 52%" in f for f in flags)


def test_w35_meetings_carry_a_quadrant_but_never_a_mode():
    """Reliability's 1.25h is entirely meeting time, so it records no mode
    at all. The renderer must print an em dash for that quadrant, never
    0% / 0% -- 'unknown' and 'recorded zero' are different findings."""
    totals = aggregate(W35_PROJECTS, W35_MEETINGS)
    assert totals.by_quadrant_mode["reliability"] == {
        "offense": 0.0, "defense": 0.0}
    assert totals.by_quadrant["reliability"] > 0.0


def test_w35_meetings_reconcile_the_by_quadrant_plus_unresolved_invariant():
    totals = aggregate([], W35_MEETINGS)
    assert (sum(totals.by_quadrant.values()) + totals.unresolved_hours
            == pytest.approx(totals.total_hours))


def test_w35_project_and_meeting_hours_combined_reconcile_the_invariant():
    totals = aggregate(W35_PROJECTS, W35_MEETINGS)
    assert (sum(totals.by_quadrant.values()) + totals.unresolved_hours
            == pytest.approx(totals.total_hours))
    # 22.0h projects + 23.75h meetings -- still short of the hand-built
    # 52.6h week total (see module docstring): the remainder is
    # unattributed desk time this module has no row type for.
    assert totals.total_hours == pytest.approx(45.75)
