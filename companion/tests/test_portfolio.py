import json
import math
import random
import sys

import pytest
from companion.portfolio import (
    QUADRANTS, CROSS_CUTTING, RoleRule, parse_role_map,
)


# summarize() reports TWO different things in one `rejected` list, because the
# caller has exactly one place to look: rows it refused to trust, and flags it
# could not evaluate (absent history, absent driver_hours / held_hours). The
# second kind fires on almost every payload a unit test writes -- a test
# payload rarely carries a prior week -- so the row-level assertions below
# filter it out rather than counting it. `_flag_suppressions` is the other
# half, asserted directly by the tests that are about it.
def _flag_suppressions(result):
    return [r for r in result["rejected"] if "did not run" in r["reason"]]


def _row_rejections(result):
    return [r for r in result["rejected"] if "did not run" not in r["reason"]]


def test_quadrant_vocabulary_is_exactly_the_five_spec_values():
    assert QUADRANTS == (
        "growth-driver",
        "operating-efficiency",
        "hygiene",
        "reliability",
    )
    assert CROSS_CUTTING == "cross-cutting"


def test_parse_role_map_reads_a_basic_rule():
    text = "Dana Vance  → hygiene   # security / governance\n"
    rules = parse_role_map(text)
    assert rules == [RoleRule(match="dana vance", quadrant="hygiene",
                              comment="security / governance")]


def test_parse_role_map_accepts_ascii_arrow():
    rules = parse_role_map("Dana Vance -> hygiene\n")
    assert rules[0].quadrant == "hygiene"


def test_parse_role_map_skips_comments_and_blank_lines():
    text = "# a comment\n\n   \nDana Vance → hygiene\n# trailing note\n"
    assert len(parse_role_map(text)) == 1


def test_parse_role_map_drops_unknown_quadrants_rather_than_guessing():
    text = "Dana Vance → nonsense-quadrant\nRio Okafor → reliability\n"
    rules = parse_role_map(text)
    assert [r.match for r in rules] == ["rio okafor"]


def test_parse_role_map_handles_an_absent_file_as_empty():
    assert parse_role_map("") == []


from companion.portfolio import project_quadrant, is_driver


def test_project_quadrant_reads_portfolio_category():
    assert project_quadrant({"portfolio-category": "growth-driver"}) == "growth-driver"


def test_project_quadrant_returns_none_when_absent_so_caller_must_handle_it():
    assert project_quadrant({}) is None
    assert project_quadrant({"portfolio-category": ""}) is None


def test_project_quadrant_rejects_a_value_outside_the_vocabulary():
    # 'founder-transition' exists in the vault today and is NOT a quadrant.
    assert project_quadrant({"portfolio-category": "founder-transition"}) is None


def test_project_quadrant_accepts_cross_cutting():
    assert project_quadrant({"portfolio-category": "cross-cutting"}) == "cross-cutting"


def test_is_driver_reads_portfolio_role():
    assert is_driver({"portfolio-role": "driver"}) is True
    assert is_driver({"portfolio-role": "held"}) is False
    assert is_driver({}) is False


from companion.portfolio import Resolution, resolve_meeting

ROLE_MAP = [RoleRule(match="dana vance", quadrant="hygiene")]


def test_role_rule_wins_over_topic_and_project():
    r = resolve_meeting(
        attendees=["Dana Vance", "kp@example.org"],
        topics=[("growth-driver", 1.0)],
        project_quadrant="operating-efficiency",
        role_map=ROLE_MAP,
    )
    assert r.quadrant == "hygiene"
    assert r.resolved_by == "role"


def test_role_matches_on_email_local_part():
    r = resolve_meeting(["dana.vance@example.org"], [], None, ROLE_MAP)
    assert r.resolved_by == "role"


def test_topic_decides_when_no_role_matches():
    r = resolve_meeting(["Rio Okafor"], [("growth-driver", 1.0)],
                        "operating-efficiency", ROLE_MAP)
    assert r.quadrant == "growth-driver"
    assert r.resolved_by == "topic"
    assert r.splits == ()


def test_topic_splits_a_meeting_across_two_quadrants():
    r = resolve_meeting(
        ["Rio Okafor"],
        [("growth-driver", 0.6), ("operating-efficiency", 0.4)],
        None, ROLE_MAP,
    )
    assert r.resolved_by == "topic"
    assert r.quadrant is None            # no single quadrant when split
    assert r.splits == (("growth-driver", 0.6), ("operating-efficiency", 0.4))


def test_project_is_the_fallback_when_no_role_and_no_topic():
    r = resolve_meeting(["Rio Okafor"], [], "reliability", ROLE_MAP)
    assert r.quadrant == "reliability"
    assert r.resolved_by == "project"


def test_unresolved_is_reported_not_absorbed():
    r = resolve_meeting(["Rio Okafor"], [], None, ROLE_MAP)
    assert r.quadrant is None
    assert r.resolved_by == "unresolved"


def test_topic_shares_that_do_not_sum_to_one_are_normalised_and_noted():
    r = resolve_meeting(["Rio Okafor"],
                        [("growth-driver", 1.0), ("hygiene", 1.0)],
                        None, ROLE_MAP)
    assert r.splits == (("growth-driver", 0.5), ("hygiene", 0.5))
    assert "normalised" in r.note


from companion.portfolio import ProjectWeek, MeetingRow, aggregate


def test_aggregate_sums_project_hours_into_quadrants():
    totals = aggregate(
        [ProjectWeek("alpha", "growth-driver", 100, 3.0),
         ProjectWeek("beta", "reliability", 0, 1.0)],
        [],
    )
    assert totals.by_quadrant["growth-driver"] == 3.0
    assert totals.by_quadrant["reliability"] == 1.0
    assert totals.total_hours == 4.0


def test_aggregate_splits_project_hours_by_mode():
    totals = aggregate([ProjectWeek("alpha", "growth-driver", 65, 4.0)], [])
    assert totals.by_mode["offense"] == pytest.approx(2.6)
    assert totals.by_mode["defense"] == pytest.approx(1.4)


def test_aggregate_apportions_a_split_meeting_across_quadrants():
    row = MeetingRow(
        "standing",
        Resolution(None, "topic", (("growth-driver", 0.6),
                                   ("operating-efficiency", 0.4))),
        1.5,
    )
    totals = aggregate([], [row])
    assert totals.by_quadrant["growth-driver"] == pytest.approx(0.9)
    assert totals.by_quadrant["operating-efficiency"] == pytest.approx(0.6)


def test_unresolved_meeting_hours_are_reported_and_still_count_to_total():
    row = MeetingRow("adhoc", Resolution(None, "unresolved"), 1.0)
    totals = aggregate([], [row])
    assert totals.unresolved_hours == 1.0
    assert totals.total_hours == 1.0
    assert sum(totals.by_quadrant.values()) == 0.0


def test_meetings_carry_no_mode_so_mode_totals_come_only_from_projects():
    row = MeetingRow("sync", Resolution("growth-driver", "project"), 2.0)
    totals = aggregate([ProjectWeek("alpha", "growth-driver", 50, 2.0)], [row])
    assert totals.by_mode["offense"] == pytest.approx(1.0)
    assert totals.by_mode["defense"] == pytest.approx(1.0)
    assert totals.by_quadrant["growth-driver"] == pytest.approx(4.0)


from companion.portfolio import evaluate_flags, WeekTotals


def _totals(quadrants, offense=1.0, defense=1.0, total=None,
            quadrant_mode=None):
    """`quadrant_mode` is the per-quadrant offense/defense split the
    assets-decaying flag reads (spec 3.6 scopes it to growth-driver). Left
    out, the week records NO per-quadrant mode hours -- which the flag must
    read as "nobody measured" and suppress on, never as "0% defense"."""
    base = {q: 0.0 for q in ("growth-driver", "operating-efficiency",
                             "hygiene", "reliability", "cross-cutting")}
    base.update(quadrants)
    return WeekTotals(base, {"offense": offense, "defense": defense}, 0.0,
                      total if total is not None else sum(base.values()),
                      dict(quadrant_mode or {}), (), offense + defense)


def test_reliability_starvation_fires_at_two_consecutive_zero_weeks():
    prior = _totals({"growth-driver": 5.0})
    current = _totals({"growth-driver": 5.0})
    flags = evaluate_flags(current, [prior], driver_hours=5.0, held_hours=0.0)
    assert any("reliability" in f.lower() for f in flags)


def test_reliability_starvation_does_not_fire_on_a_single_zero_week():
    prior = _totals({"reliability": 1.0})
    current = _totals({"growth-driver": 5.0})
    flags = evaluate_flags(current, [prior], driver_hours=5.0, held_hours=0.0)
    assert not any("reliability" in f.lower() for f in flags)


def test_operating_efficiency_over_forty_percent_fires():
    current = _totals({"operating-efficiency": 5.0, "growth-driver": 4.0})
    flags = evaluate_flags(current, [], driver_hours=9.0, held_hours=0.0)
    assert any("operating-efficiency" in f for f in flags)


def test_rising_defense_share_fires():
    prior = _totals({"growth-driver": 10.0}, offense=9.0, defense=1.0,
                    quadrant_mode={"growth-driver": {"offense": 9.0,
                                                     "defense": 1.0}})
    current = _totals({"growth-driver": 10.0}, offense=5.0, defense=5.0,
                      quadrant_mode={"growth-driver": {"offense": 5.0,
                                                       "defense": 5.0}})
    flags = evaluate_flags(current, [prior], driver_hours=10.0, held_hours=0.0)
    assert any("defense" in f.lower() for f in flags)


def test_assets_decaying_is_scoped_to_growth_driver_not_the_whole_week():
    """Spec 3.6 scopes this flag to quadrant 1, and its message names growth
    drivers by name. Computed week-wide it fired on a week whose growth-driver
    defense FELL while hygiene's rose -- naming the wrong assets."""
    prior = _totals({"growth-driver": 10.0, "hygiene": 10.0},
                    offense=18.0, defense=2.0,
                    quadrant_mode={"growth-driver": {"offense": 8.0,
                                                     "defense": 2.0},
                                   "hygiene": {"offense": 10.0,
                                               "defense": 0.0}})
    # Week-wide defense rose 10% -> 45%; growth-driver defense FELL 20% -> 10%.
    current = _totals({"growth-driver": 10.0, "hygiene": 10.0},
                      offense=11.0, defense=9.0,
                      quadrant_mode={"growth-driver": {"offense": 9.0,
                                                       "defense": 1.0},
                                     "hygiene": {"offense": 2.0,
                                                 "defense": 8.0}})
    flags = evaluate_flags(current, [prior], driver_hours=20.0, held_hours=0.0)
    assert not any("decaying" in f for f in flags)


def test_assets_decaying_fires_when_growth_driver_defense_rises_alone():
    """The mirror image: the week-wide share FALLS while growth-driver's own
    rises. The flag is about quadrant 1, so it must still fire."""
    prior = _totals({"growth-driver": 10.0, "hygiene": 10.0},
                    offense=10.0, defense=10.0,
                    quadrant_mode={"growth-driver": {"offense": 9.0,
                                                     "defense": 1.0},
                                   "hygiene": {"offense": 1.0,
                                               "defense": 9.0}})
    current = _totals({"growth-driver": 10.0, "hygiene": 10.0},
                      offense=15.0, defense=5.0,
                      quadrant_mode={"growth-driver": {"offense": 5.0,
                                                       "defense": 5.0},
                                     "hygiene": {"offense": 10.0,
                                                 "defense": 0.0}})
    flags = evaluate_flags(current, [prior], driver_hours=20.0, held_hours=0.0)
    assert any("decaying" in f for f in flags)
    assert any("growth-driver" in f for f in flags)


def test_a_prior_week_with_no_growth_driver_mode_hours_suppresses_and_reports():
    """A prior note written before by_quadrant_mode was persisted carries no
    growth-driver mode hours. That is "nobody measured", not "0% defense" --
    reading it as zero fires the flag against any week with defense in it."""
    prior = _totals({"growth-driver": 10.0}, offense=9.0, defense=1.0)
    current = _totals({"growth-driver": 10.0}, offense=5.0, defense=5.0,
                      quadrant_mode={"growth-driver": {"offense": 5.0,
                                                       "defense": 5.0}})
    rejects = []
    flags = evaluate_flags(current, [prior], driver_hours=10.0, held_hours=0.0,
                           rejects=rejects)
    assert not any("decaying" in f for f in flags)
    assert any("did not run" in r.reason and "growth-driver" in r.reason
               for r in rejects)


def test_held_out_earning_driver_fires():
    current = _totals({"growth-driver": 6.0})
    flags = evaluate_flags(current, [], driver_hours=1.0, held_hours=5.0)
    assert any("held" in f.lower() for f in flags)


def test_a_clean_week_produces_no_flags():
    prior = _totals({"reliability": 1.0, "growth-driver": 9.0},
                    offense=8.0, defense=2.0)
    current = _totals({"reliability": 1.0, "growth-driver": 9.0},
                      offense=8.0, defense=2.0)
    assert evaluate_flags(current, [prior], driver_hours=9.0, held_hours=1.0) == []


from companion.portfolio import summarize


def test_summarize_round_trips_a_well_formed_payload_to_quadrant_totals_and_percentages():
    payload = {
        "project_weeks": [
            {"project": "alpha", "quadrant": "growth-driver",
             "offense_pct": 100, "hours": 3.0},
            {"project": "beta", "quadrant": "reliability",
             "offense_pct": 0, "hours": 1.0},
        ],
        "meeting_rows": [
            {"label": "standing", "quadrant": None, "resolved_by": "topic",
             "splits": [["growth-driver", 0.6], ["operating-efficiency", 0.4]],
             "hours": 1.0},
        ],
        "history": [
            # A history entry must name all five quadrants and both modes --
            # a missing number there is a week nobody measured, not a zero.
            {"by_quadrant": {"growth-driver": 9.0, "operating-efficiency": 0.0,
                             "hygiene": 0.0, "reliability": 1.0,
                             "cross-cutting": 0.0},
             "by_mode": {"offense": 9.0, "defense": 1.0},
             # Spec 3.6 scopes the assets-decaying flag to quadrant 1, so the
             # comparison is growth-driver's own mode split, not the week's.
             "by_quadrant_mode": {"growth-driver": {"offense": 9.0,
                                                    "defense": 0.0}}},
        ],
        "driver_hours": 4.0,
        "held_hours": 0.0,
    }
    result = summarize(payload)

    assert result["by_quadrant"]["growth-driver"] == pytest.approx(3.6)
    assert result["by_quadrant"]["reliability"] == pytest.approx(1.0)
    assert result["by_quadrant"]["operating-efficiency"] == pytest.approx(0.4)
    assert result["total_hours"] == pytest.approx(5.0)
    assert result["unresolved_hours"] == 0.0
    assert result["percentages"]["growth-driver"] == pytest.approx(3.6 / 5.0)
    assert result["percentages"]["reliability"] == pytest.approx(1.0 / 5.0)
    assert isinstance(result["flags"], list)
    # This assertion depends on the history entry's growth-driver mode split:
    # this week 'beta' is reliability and 'alpha' is 100% offense, so the only
    # growth-driver mode hours are alpha's 3.0 offense -- a 0% defense share,
    # equal to the prior week's 0%, so NOT a rise. The meeting's 0.6 share of
    # growth-driver carries no mode at all and is deliberately absent from the
    # comparison.
    assert not any("decaying" in f for f in result["flags"])
    # Nothing was suppressed either: every flag input this payload needs is
    # present, so the flag did not fire because the trend is not there.
    assert result["rejected"] == []


def test_summarize_handles_an_empty_payload_with_zero_totals_and_no_division_by_zero():
    result = summarize({})

    assert result["total_hours"] == 0.0
    assert result["unresolved_hours"] == 0.0
    assert all(v == 0.0 for v in result["by_quadrant"].values())
    assert all(v == 0.0 for v in result["percentages"].values())
    assert result["flags"] == []


def test_evaluate_flags_skips_defense_check_when_prior_week_has_no_recorded_mode_hours():
    prior = _totals({"growth-driver": 5.0}, offense=0.0, defense=0.0)
    current = _totals({"growth-driver": 5.0}, offense=3.0, defense=2.0)
    flags = evaluate_flags(current, [prior], driver_hours=5.0, held_hours=0.0)
    assert not any("defense" in f.lower() for f in flags)


def test_summarize_produces_defense_flag_when_history_by_mode_shows_a_real_rise():
    payload = {
        "project_weeks": [
            {"project": "alpha", "quadrant": "growth-driver",
             "offense_pct": 50, "hours": 10.0},
        ],
        "meeting_rows": [],
        "history": [
            {"by_quadrant": {"growth-driver": 10.0, "operating-efficiency": 0.0,
                             "hygiene": 0.0, "reliability": 0.0,
                             "cross-cutting": 0.0},
             "by_mode": {"offense": 9.0, "defense": 1.0},
             "by_quadrant_mode": {"growth-driver": {"offense": 9.0,
                                                    "defense": 1.0}}},
        ],
        "driver_hours": 10.0,
        "held_hours": 0.0,
    }
    result = summarize(payload)
    # growth-driver defense: 10% last week -> 50% this week.
    assert any("decaying" in f for f in result["flags"])
    # A complete prior week is history, so nothing was suppressed.
    assert _row_rejections(result) == []


def test_summarize_with_a_by_mode_less_history_entry_suppresses_history_and_says_so():
    """`by_mode` is not optional. Without it the prior week's mode hours read
    as 0/0, and 0% defense last week is the rising-defense flag's firing
    condition against any current week with defense in it -- absent data
    manufacturing a trend. Suppress, and report the suppression."""
    payload = {
        "project_weeks": [
            {"project": "alpha", "quadrant": "growth-driver",
             "offense_pct": 50, "hours": 10.0},
        ],
        "meeting_rows": [],
        "history": [
            {"by_quadrant": {"growth-driver": 10.0, "operating-efficiency": 0.0,
                             "hygiene": 0.0, "reliability": 0.0,
                             "cross-cutting": 0.0}},
        ],
        "driver_hours": 10.0,
        "held_hours": 0.0,
    }
    result = summarize(payload)
    assert not any("defense" in f.lower() for f in result["flags"])
    suppressions = [r for r in result["rejected"]
                    if "history suppressed" in r["reason"]]
    assert len(suppressions) == 1
    assert suppressions[0]["kind"] == "payload"
    assert "'by_mode'" in suppressions[0]["reason"]


def test_summarize_drops_an_out_of_vocabulary_split_quadrant_without_crashing():
    payload = {
        "project_weeks": [],
        "meeting_rows": [
            {"label": "standing", "quadrant": None, "resolved_by": "topic",
             "splits": [["bogus-quadrant", 1.0]], "hours": 2.0},
        ],
        "history": [],
        "driver_hours": 0.0,
        "held_hours": 0.0,
    }
    result = summarize(payload)  # must not raise KeyError

    assert result["unresolved_hours"] == 2.0
    assert result["total_hours"] == 2.0
    assert sum(result["by_quadrant"].values()) == 0.0


def test_summarize_partial_invalid_split_routes_leftover_share_to_unresolved():
    """60% of the meeting resolves to a valid quadrant; 40% named an
    out-of-vocabulary quadrant (typo/stale data). The valid share is kept
    as apportioned; the invalid share's hours go to unresolved_hours
    rather than vanishing."""
    payload = {
        "project_weeks": [],
        "meeting_rows": [
            {"label": "mixed", "quadrant": None, "resolved_by": "topic",
             "splits": [["growth-driver", 0.6], ["bogus-quadrant", 0.4]],
             "hours": 2.0},
        ],
        "history": [],
        "driver_hours": 0.0,
        "held_hours": 0.0,
    }
    result = summarize(payload)

    assert result["by_quadrant"]["growth-driver"] == pytest.approx(1.2)
    assert result["unresolved_hours"] == pytest.approx(0.8)
    assert result["total_hours"] == pytest.approx(2.0)


def test_summarize_reconciles_by_quadrant_plus_unresolved_to_total_across_a_mixed_week():
    """The reconciliation invariant that protects the number a human reads:
    sum(by_quadrant) + unresolved_hours == total_hours, across a week that
    mixes project rows, a fully valid split, a partially invalid split, a
    fully invalid split, a plain resolved meeting, and a plain unresolved
    meeting."""
    payload = {
        "project_weeks": [
            {"project": "alpha", "quadrant": "growth-driver",
             "offense_pct": 80, "hours": 5.0},
            {"project": "beta", "quadrant": "hygiene",
             "offense_pct": 20, "hours": 2.0},
        ],
        "meeting_rows": [
            {"label": "planning", "quadrant": None, "resolved_by": "topic",
             "splits": [["growth-driver", 0.6], ["operating-efficiency", 0.4]],
             "hours": 3.0},
            {"label": "mixed", "quadrant": None, "resolved_by": "topic",
             "splits": [["hygiene", 0.5], ["stale-quadrant", 0.5]],
             "hours": 4.0},
            {"label": "junk", "quadrant": None, "resolved_by": "topic",
             "splits": [["nope", 1.0]], "hours": 1.5},
            {"label": "1:1", "quadrant": "reliability", "resolved_by": "project",
             "splits": [], "hours": 1.0},
            {"label": "adhoc", "quadrant": None, "resolved_by": "unresolved",
             "splits": [], "hours": 0.5},
        ],
        "history": [],
        "driver_hours": 5.0,
        "held_hours": 0.0,
    }
    result = summarize(payload)

    expected_total = 5.0 + 2.0 + 3.0 + 4.0 + 1.5 + 1.0 + 0.5
    assert result["total_hours"] == pytest.approx(expected_total)
    assert (sum(result["by_quadrant"].values()) + result["unresolved_hours"]
            == pytest.approx(result["total_hours"]))
    # Not trivially true because everything landed in a single bucket:
    assert result["unresolved_hours"] > 0.0
    assert sum(result["by_quadrant"].values()) > 0.0


from companion.portfolio import parse_projects_touched, ProjectWeek


def test_parse_projects_touched_round_trips_a_well_formed_multi_project_section():
    md = """# 2026-08-26 — Wednesday

## Work Log
- shipped the thing

## Projects Touched
- [[20-projects/lighthouse|lighthouse]] — shipped the onboarding flow · 2.5h · growth-driver · 80% offense
- [[20-projects/backstage|backstage]] — rotated the expired token · 1.0h · reliability · 10% offense

## Carrying Over
- nothing
"""
    result = parse_projects_touched(md)
    assert result == [
        ProjectWeek(project="lighthouse", quadrant="growth-driver",
                    offense_pct=80, hours=2.5),
        ProjectWeek(project="backstage", quadrant="reliability",
                    offense_pct=10, hours=1.0),
    ]


def test_parse_projects_touched_returns_none_quadrant_for_uncategorized_not_a_guess():
    md = """## Projects Touched
- [[20-projects/side-quest|side-quest]] — poked at a prototype · 0.5h · uncategorized · 50% offense
"""
    result = parse_projects_touched(md)
    assert result == [
        ProjectWeek(project="side-quest", quadrant=None,
                    offense_pct=50, hours=0.5),
    ]


def test_parse_projects_touched_skips_a_legacy_format_line_without_raising():
    md = """## Projects Touched
- [[20-projects/lighthouse|lighthouse]] — shipped the onboarding flow · 2.5h · growth-driver · 80% offense
- [[20-projects/old-note|old-note]] — this is a pre-format legacy line with no hours or quadrant
"""
    result = parse_projects_touched(md)
    assert result == [
        ProjectWeek(project="lighthouse", quadrant="growth-driver",
                    offense_pct=80, hours=2.5),
    ]


def test_parse_projects_touched_returns_empty_list_when_section_missing():
    md = """# 2026-08-26 — Wednesday

## Work Log
- shipped the thing

## Carrying Over
- nothing
"""
    assert parse_projects_touched(md) == []


def test_parse_projects_touched_summary_may_itself_contain_the_separator_character():
    md = """## Projects Touched
- [[20-projects/lighthouse|lighthouse]] — refactored auth · rate limiting · caching · 3.0h · operating-efficiency · 60% offense
"""
    result = parse_projects_touched(md)
    assert result == [
        ProjectWeek(project="lighthouse", quadrant="operating-efficiency",
                    offense_pct=60, hours=3.0),
    ]


import json

from companion.portfolio import parse_daily_note


# --- per-quadrant mode (the "quadrant x mode" half of the feature) ------


def test_aggregate_splits_mode_within_each_quadrant_not_just_week_wide():
    rows = [
        ProjectWeek("lighthouse", "growth-driver", 70, 10.0),
        ProjectWeek("backstage", "reliability", 0, 4.0),
        ProjectWeek("side-quest", "growth-driver", 100, 2.0),
    ]
    totals = aggregate(rows, [])
    assert totals.by_quadrant_mode["growth-driver"] == {
        "offense": pytest.approx(9.0), "defense": pytest.approx(3.0)}
    assert totals.by_quadrant_mode["reliability"] == {
        "offense": pytest.approx(0.0), "defense": pytest.approx(4.0)}
    # Every quadrant is present, including the untouched ones -- an omitted
    # key is how a quadrant disappears from the rendered table.
    assert set(totals.by_quadrant_mode) == set(QUADRANTS) | {CROSS_CUTTING}


def test_per_quadrant_mode_hours_reconcile_to_that_quadrant_hours():
    rows = [
        ProjectWeek("lighthouse", "growth-driver", 70, 10.0),
        ProjectWeek("backstage", "hygiene", 25, 4.0),
    ]
    totals = aggregate(rows, [])
    for quadrant, modes in totals.by_quadrant_mode.items():
        assert (modes["offense"] + modes["defense"]
                == pytest.approx(totals.by_quadrant[quadrant]))


def test_a_quadrant_carrying_only_meeting_hours_records_no_mode_at_all():
    """Meetings carry a quadrant and deliberately no mode. Such a quadrant
    must read as 'mode unknown' (0.0h offense AND 0.0h defense against
    non-zero quadrant hours), never as 'recorded zero offense' -- which is
    why the renderer is told to check the HOURS, not the percentages."""
    rows = [MeetingRow("incident review",
                       Resolution("reliability", "role"), 2.0)]
    totals = aggregate([], rows)
    assert totals.by_quadrant["reliability"] == 2.0
    assert totals.by_quadrant_mode["reliability"] == {
        "offense": 0.0, "defense": 0.0}


def test_summarize_returns_per_quadrant_mode_hours_and_percentages():
    payload = {
        "project_weeks": [
            {"project": "lighthouse", "quadrant": "growth-driver",
             "offense_pct": 70, "hours": 10.0},
            {"project": "backstage", "quadrant": "reliability",
             "offense_pct": 0, "hours": 4.0},
        ],
        "meeting_rows": [],
    }
    result = summarize(payload)
    assert result["by_quadrant_mode"]["growth-driver"] == {
        "offense": pytest.approx(7.0), "defense": pytest.approx(3.0)}
    assert result["quadrant_mode_percentages"]["growth-driver"] == {
        "offense": pytest.approx(0.7), "defense": pytest.approx(0.3)}
    assert result["quadrant_mode_percentages"]["reliability"] == {
        "offense": pytest.approx(0.0), "defense": pytest.approx(1.0)}
    # A quadrant with no hours divides by zero into 0.0, not a crash.
    assert result["quadrant_mode_percentages"]["hygiene"] == {
        "offense": 0.0, "defense": 0.0}


def test_summarize_returns_every_percentage_the_table_needs():
    payload = {
        "project_weeks": [
            {"project": "lighthouse", "quadrant": "growth-driver",
             "offense_pct": 50, "hours": 8.0},
        ],
        "meeting_rows": [
            {"label": "ad-hoc", "quadrant": None,
             "resolved_by": "unresolved", "hours": 2.0},
        ],
    }
    result = summarize(payload)
    assert result["mode_percentages"] == {
        "offense": pytest.approx(0.5), "defense": pytest.approx(0.5)}
    assert result["unresolved_pct"] == pytest.approx(0.2)
    assert result["percentages"]["growth-driver"] == pytest.approx(0.8)


def test_summarize_on_an_empty_payload_returns_zero_shares_not_a_crash():
    result = summarize({})
    assert result["unresolved_pct"] == 0.0
    assert result["mode_percentages"] == {"offense": 0.0, "defense": 0.0}
    assert all(m == {"offense": 0.0, "defense": 0.0}
               for m in result["quadrant_mode_percentages"].values())


# --- splits that don't sum to 1.0 --------------------------------------


def test_splits_summing_over_one_are_normalised_and_never_go_negative():
    """resolve_meeting() normalises shares; aggregate() must agree, or the
    same input reaches two different answers depending on the entry point.
    Un-normalised, [0.7, 0.6] on 2.0h yields unresolved_hours -0.6 and a
    table summing to 130%."""
    payload = {
        "project_weeks": [],
        "meeting_rows": [
            {"label": "leadership standing", "quadrant": None,
             "resolved_by": "topic", "hours": 2.0,
             "splits": [["growth-driver", 0.7], ["hygiene", 0.6]]},
        ],
    }
    result = summarize(payload)
    assert result["unresolved_hours"] == pytest.approx(0.0)
    assert result["unresolved_hours"] >= 0.0
    assert result["by_quadrant"]["growth-driver"] == pytest.approx(2.0 * 0.7 / 1.3)
    assert result["by_quadrant"]["hygiene"] == pytest.approx(2.0 * 0.6 / 1.3)
    assert sum(result["percentages"].values()) == pytest.approx(1.0)
    assert (sum(result["by_quadrant"].values()) + result["unresolved_hours"]
            == pytest.approx(result["total_hours"]))


def test_splits_summing_under_one_still_route_the_leftover_to_unresolved():
    """The under-1.0 case is NOT normalised: a share that went missing (a
    dropped out-of-vocabulary quadrant) is unresolved time, and absorbing
    it into the surviving quadrants would hide it."""
    payload = {
        "project_weeks": [],
        "meeting_rows": [
            {"label": "leadership standing", "quadrant": None,
             "resolved_by": "topic", "hours": 2.0,
             "splits": [["growth-driver", 0.5], ["hygiene", 0.25]]},
        ],
    }
    result = summarize(payload)
    assert result["by_quadrant"]["growth-driver"] == pytest.approx(1.0)
    assert result["by_quadrant"]["hygiene"] == pytest.approx(0.5)
    assert result["unresolved_hours"] == pytest.approx(0.5)
    assert (sum(result["by_quadrant"].values()) + result["unresolved_hours"]
            == pytest.approx(result["total_hours"]))


def test_aggregate_normalises_an_over_one_split_for_a_direct_caller_too():
    rows = [MeetingRow("leadership standing", Resolution(
        None, "topic", splits=(("growth-driver", 1.0), ("hygiene", 1.0))), 3.0)]
    totals = aggregate([], rows)
    assert totals.unresolved_hours == pytest.approx(0.0)
    assert totals.by_quadrant["growth-driver"] == pytest.approx(1.5)
    assert (sum(totals.by_quadrant.values()) + totals.unresolved_hours
            == pytest.approx(totals.total_hours))


# --- a daily-note line that does not parse must be REPORTED -------------


def test_parse_daily_note_reports_a_line_that_did_not_parse():
    """A drifted line is a day's hours vanishing from the week with no
    signal. It is still skipped (legacy notes must parse), but the caller
    is handed the evidence so the confirm gate can say '3 of 4 parsed'."""
    md = """## Projects Touched
- [[20-projects/lighthouse|lighthouse]] — shipped it · 2.5h · growth-driver · 80% offense
- [[20-projects/backstage|backstage]] — placeholders left in · [X.X]h · [quadrant] · [NN]% offense
- [[20-projects/side-quest|side-quest]] — legacy line with no tail
"""
    parsed = parse_daily_note(md)
    assert [p.project for p in parsed.projects] == ["lighthouse"]
    assert parsed.skipped_count == 2
    assert parsed.skipped_count == len(parsed.skipped)
    assert any("[X.X]h" in line for line in parsed.skipped)
    assert any("side-quest" in line for line in parsed.skipped)


def test_parse_daily_note_does_not_report_the_sections_explanatory_prose():
    """The close-day template puts a prose paragraph under this heading.
    Counting it as a lost row would cry wolf until nobody reads the count."""
    md = """## Projects Touched
- [[20-projects/lighthouse|lighthouse]] — shipped it · 2.5h · growth-driver · 80% offense

Hours come from the same Familiar attribution that produced Time Allocation.
Quadrant is the project's `portfolio-category` frontmatter.
"""
    parsed = parse_daily_note(md)
    assert len(parsed.projects) == 1
    assert parsed.skipped == []


def test_parse_daily_note_reports_nothing_skipped_for_a_clean_section():
    md = """## Projects Touched
- [[20-projects/lighthouse|lighthouse]] — shipped it · 2.5h · growth-driver · 80% offense
- [[20-projects/backstage|backstage]] — triaged alerts · 0.5h · uncategorized · 0% offense
"""
    parsed = parse_daily_note(md)
    assert len(parsed.projects) == 2
    assert parsed.skipped_count == 0


def test_parse_projects_touched_still_returns_just_the_rows():
    md = """## Projects Touched
- [[20-projects/lighthouse|lighthouse]] — shipped it · 2.5h · growth-driver · 80% offense
- a line that does not parse
"""
    assert parse_projects_touched(md) == parse_daily_note(md).projects


# --- the CLI path the skill prose actually documents --------------------


def _run_cli(args, stdin_text):
    import subprocess
    import sys as _sys
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [_sys.executable, "-m", "companion.portfolio", *args],
        input=stdin_text, capture_output=True, text=True, cwd=repo_root,
    )


def test_cli_parse_daily_mode_is_the_path_close_week_is_told_to_use():
    """close-week's Step 2a documents `--parse-daily`; if that invocation
    does not exist, an agent following the prose hand-rolls a regex and the
    format contract this module verifies stops being verified."""
    md = """## Projects Touched
- [[20-projects/lighthouse|lighthouse]] — shipped it · 2.5h · growth-driver · 80% offense
- [[20-projects/backstage|backstage]] — drifted · [X.X]h · [quadrant] · [NN]% offense
"""
    proc = _run_cli(["--parse-daily"], md)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["project_weeks"] == [
        {"project": "lighthouse", "quadrant": "growth-driver",
         "offense_pct": 80, "hours": 2.5},
    ]
    assert out["skipped_count"] == 1
    assert "[X.X]h" in out["skipped_lines"][0]


def test_cli_default_mode_still_summarizes_a_payload():
    payload = json.dumps({
        "project_weeks": [{"project": "lighthouse", "quadrant": "hygiene",
                           "offense_pct": 0, "hours": 1.0}],
        "meeting_rows": [],
    })
    proc = _run_cli([], payload)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["by_quadrant"]["hygiene"] == 1.0
    assert out["by_quadrant_mode"]["hygiene"]["defense"] == 1.0


def test_cli_rejects_an_unknown_flag_loudly():
    proc = _run_cli(["--nonsense"], "")
    assert proc.returncode == 2
    assert "usage" in proc.stderr.lower()


# --- the aggregate() validation boundary ---------------------------------
#
# Every caller funnels through aggregate(), so these run against aggregate()
# directly wherever a direct caller is the exposure, and through summarize()
# wherever the JSON payload is. A malformed row must be REPORTED (routed to
# unresolved AND named in `rejected`), never silently corrected, and the
# reconciliation invariant must survive every one of them.


def _reconciles(totals):
    return (sum(totals.by_quadrant.values()) + totals.unresolved_hours
            == pytest.approx(totals.total_hours)
            and totals.unresolved_hours >= 0.0)


def test_a_split_quadrant_outside_the_vocabulary_does_not_raise_in_aggregate():
    """A1. This used to be a KeyError at `by_quadrant[quadrant] +=` for any
    caller that reached aggregate() without going through summarize()."""
    row = MeetingRow("standing", Resolution(None, "topic",
                                            (("bogus-quadrant", 1.0),)), 2.0)
    totals = aggregate([], [row])       # must not raise

    assert totals.unresolved_hours == pytest.approx(2.0)
    assert sum(totals.by_quadrant.values()) == 0.0
    assert _reconciles(totals)
    assert len(totals.rejected) == 1
    assert totals.rejected[0].kind == "meeting"
    assert "bogus-quadrant" in totals.rejected[0].reason
    assert totals.rejected[0].row["label"] == "standing"


def test_a_partly_invalid_split_reports_the_bad_quadrant_and_keeps_the_good_share():
    row = MeetingRow("mixed", Resolution(None, "topic",
                                         (("growth-driver", 0.6),
                                          ("stale-quadrant", 0.4))), 2.0)
    totals = aggregate([], [row])

    assert totals.by_quadrant["growth-driver"] == pytest.approx(1.2)
    assert totals.unresolved_hours == pytest.approx(0.8)
    assert _reconciles(totals)
    assert len(totals.rejected) == 1
    assert "stale-quadrant" in totals.rejected[0].reason


def test_a_negative_split_share_routes_the_whole_row_to_unresolved_and_reports_it():
    """A2. The reconciliation invariant held arithmetically before this fix
    while growth-driver rendered as negative hours -- nonsense that still
    read as a number. The whole row goes to unresolved instead, and is
    named."""
    row = MeetingRow("bad split", Resolution(None, "topic",
                                             (("growth-driver", -0.5),
                                              ("hygiene", 1.5))), 4.0)
    totals = aggregate([], [row])

    assert totals.by_quadrant["growth-driver"] == 0.0
    assert totals.by_quadrant["hygiene"] == 0.0
    assert totals.unresolved_hours == pytest.approx(4.0)
    assert totals.total_hours == pytest.approx(4.0)
    assert _reconciles(totals)
    assert len(totals.rejected) == 1
    assert "negative" in totals.rejected[0].reason


def test_parse_daily_note_skips_an_out_of_range_offense_percentage():
    r"""A3. The regex accepts \d{1,3}, so '150% offense' parsed
    'successfully' and aggregate() then computed negative defense hours.
    It is a skipped line now, so it shows at the confirm gate instead."""
    md = """## Projects Touched
- [[20-projects/lighthouse|lighthouse]] — shipped · 2.0h · growth-driver · 150% offense
- [[20-projects/backstage|backstage]] — fixed · 1.0h · reliability · 0% offense
"""
    parsed = parse_daily_note(md)

    assert [pw.project for pw in parsed.projects] == ["backstage"]
    assert parsed.skipped_count == 1
    assert "150%" in parsed.skipped[0]


def test_parse_daily_note_still_accepts_the_endpoints_zero_and_one_hundred():
    md = """## Projects Touched
- [[20-projects/alpha|alpha]] — all defense · 1.0h · reliability · 0% offense
- [[20-projects/beta|beta]] — all offense · 1.0h · growth-driver · 100% offense
"""
    parsed = parse_daily_note(md)
    assert [pw.offense_pct for pw in parsed.projects] == [0, 100]
    assert parsed.skipped_count == 0


def test_an_out_of_range_offense_pct_reaching_aggregate_is_rejected_not_computed():
    """A5. The parser is not the only way in -- the JSON payload hands
    offense_pct straight to summarize(). Defense hours must never go
    negative; the hours go to unresolved and the row is named."""
    totals = aggregate([ProjectWeek("lighthouse", "growth-driver", 150, 4.0)], [])

    assert totals.by_mode == {"offense": 0.0, "defense": 0.0}
    assert totals.by_quadrant["growth-driver"] == 0.0
    assert totals.unresolved_hours == pytest.approx(4.0)
    assert _reconciles(totals)
    assert "offense_pct 150" in totals.rejected[0].reason


def test_a_negative_offense_pct_is_rejected_too():
    totals = aggregate([ProjectWeek("lighthouse", "hygiene", -20, 2.0)], [])
    assert totals.unresolved_hours == pytest.approx(2.0)
    assert totals.by_mode == {"offense": 0.0, "defense": 0.0}
    assert _reconciles(totals)


def test_negative_project_hours_are_excluded_from_the_week_and_reported():
    """A4. Routing negative hours to unresolved would render a negative
    unresolved figure, so the row leaves the week entirely -- but loudly."""
    totals = aggregate([
        ProjectWeek("good", "hygiene", 50, 2.0),
        ProjectWeek("bad", "hygiene", 50, -3.0),
    ], [])

    assert totals.total_hours == pytest.approx(2.0)
    assert totals.by_quadrant["hygiene"] == pytest.approx(2.0)
    assert totals.unresolved_hours == 0.0
    assert _reconciles(totals)
    assert [r.row["project"] for r in totals.rejected] == ["bad"]
    assert "negative" in totals.rejected[0].reason


def test_negative_meeting_hours_are_excluded_from_the_week_and_reported():
    """A4, the meeting half -- there was no guard anywhere for either."""
    totals = aggregate([], [
        MeetingRow("real", Resolution("hygiene", "role"), 1.0),
        MeetingRow("bad", Resolution("hygiene", "role"), -1.0),
    ])

    assert totals.total_hours == pytest.approx(1.0)
    assert totals.by_quadrant["hygiene"] == pytest.approx(1.0)
    assert _reconciles(totals)
    assert [r.row["label"] for r in totals.rejected] == ["bad"]


def test_a_project_quadrant_outside_the_vocabulary_is_rejected_not_bucketed():
    totals = aggregate([ProjectWeek("lighthouse", "founder-transition", 50, 4.0)], [])

    assert totals.unresolved_hours == pytest.approx(4.0)
    assert sum(totals.by_quadrant.values()) == 0.0
    assert _reconciles(totals)
    assert "founder-transition" in totals.rejected[0].reason


def test_a_meeting_quadrant_outside_the_vocabulary_is_rejected_not_bucketed():
    totals = aggregate([], [
        MeetingRow("sync", Resolution("nonsense", "project"), 1.5)])

    assert totals.unresolved_hours == pytest.approx(1.5)
    assert _reconciles(totals)
    assert "nonsense" in totals.rejected[0].reason


def test_a_null_quadrant_is_not_a_rejection_it_is_the_documented_state():
    """`uncategorized` project rows and unresolved meetings both carry
    quadrant None by design. Reporting them as malformed would cry wolf
    until nobody reads the rejected list."""
    totals = aggregate(
        [ProjectWeek("lighthouse", None, 50, 2.0)],
        [MeetingRow("adhoc", Resolution(None, "unresolved"), 1.0)],
    )

    assert totals.rejected == ()
    assert totals.unresolved_hours == pytest.approx(3.0)
    assert _reconciles(totals)


def test_a_clean_week_rejects_nothing():
    totals = aggregate(
        [ProjectWeek("lighthouse", "growth-driver", 80, 5.0)],
        [MeetingRow("sync", Resolution("hygiene", "role"), 1.0)],
    )
    assert totals.rejected == ()
    assert _reconciles(totals)


def test_the_invariant_survives_a_week_of_every_malformed_shape_at_once():
    """The binding constraint: sum(by_quadrant) + unresolved == total, and
    unresolved is never negative, for ANY input -- including one carrying
    every rejection class simultaneously."""
    totals = aggregate(
        [
            ProjectWeek("ok-project", "growth-driver", 80, 5.0),
            ProjectWeek("neg-hours-project", "hygiene", 50, -2.0),
            ProjectWeek("bad-pct", "hygiene", 150, 3.0),
            ProjectWeek("bad-project-quadrant", "made-up", 50, 1.0),
            ProjectWeek("uncategorized", None, 50, 0.5),
        ],
        [
            MeetingRow("ok-meeting", Resolution("reliability", "role"), 1.0),
            MeetingRow("neg-hours-meeting", Resolution("hygiene", "role"), -4.0),
            MeetingRow("bad-meeting-quadrant", Resolution("typo", "project"), 2.0),
            MeetingRow("neg-share", Resolution(None, "topic",
                                               (("hygiene", -1.0),
                                                ("growth-driver", 2.0))), 1.5),
            MeetingRow("part-bad", Resolution(None, "topic",
                                              (("hygiene", 0.5),
                                               ("gone", 0.5))), 2.0),
            MeetingRow("adhoc", Resolution(None, "unresolved"), 0.5),
        ],
    )

    # Both negative-hours rows are out of the week; everything else counts.
    assert totals.total_hours == pytest.approx(
        5.0 + 3.0 + 1.0 + 0.5 + 1.0 + 2.0 + 1.5 + 2.0 + 0.5)
    assert _reconciles(totals)
    assert totals.unresolved_hours > 0.0
    assert sum(totals.by_quadrant.values()) > 0.0
    # Every malformed row is reported -- and the two legitimate None
    # quadrants are not among them.
    reported = {r.row.get("project", r.row.get("label")) for r in totals.rejected}
    assert reported == {"neg-hours-project", "bad-pct", "bad-project-quadrant",
                        "neg-hours-meeting", "bad-meeting-quadrant",
                        "neg-share", "part-bad"}


def test_summarize_exposes_rejected_rows_so_the_confirm_gate_can_show_them():
    """A5 through the JSON payload -- the shape close-week actually reads."""
    payload = {
        "project_weeks": [
            {"project": "lighthouse", "quadrant": "growth-driver",
             "offense_pct": 150, "hours": 4.0},
        ],
        "meeting_rows": [
            {"label": "standing", "quadrant": None, "resolved_by": "topic",
             "splits": [["growth-driver", -0.5], ["hygiene", 1.5]],
             "hours": 2.0},
        ],
        "history": [],
        "driver_hours": 0.0,
        "held_hours": 0.0,
    }
    result = summarize(payload)

    assert len(_row_rejections(result)) == 2
    assert {r["kind"] for r in _row_rejections(result)} == {"project", "meeting"}
    assert all(r["reason"] for r in result["rejected"])
    assert _row_rejections(result)[0]["row"]["offense_pct"] == 150
    assert result["by_mode"]["defense"] >= 0.0
    assert result["unresolved_hours"] == pytest.approx(6.0)
    assert (sum(result["by_quadrant"].values()) + result["unresolved_hours"]
            == pytest.approx(result["total_hours"]))


def test_summarize_on_a_clean_payload_returns_an_empty_rejected_list():
    result = summarize({
        "project_weeks": [{"project": "lighthouse", "quadrant": "hygiene",
                           "offense_pct": 0, "hours": 1.0}],
        "meeting_rows": [],
    })
    assert _row_rejections(result) == []


def test_cli_prints_rejected_rows_as_json():
    """The CLI is the path the skill prose runs, so `rejected` has to
    survive json.dumps -- a dataclass left in there would crash the step."""
    payload = json.dumps({
        "project_weeks": [{"project": "lighthouse", "quadrant": "made-up",
                           "offense_pct": 50, "hours": 2.0}],
        "meeting_rows": [],
    })
    proc = _run_cli([], payload)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert len(_row_rejections(out)) == 1
    assert _row_rejections(out)[0]["row"]["quadrant"] == "made-up"
    assert "made-up" in _row_rejections(out)[0]["reason"]


# --- F: the boundary validates TYPE and FINITENESS, not just range -------
#
# Before this, aggregate() compared before it checked. `pw.hours < 0` on the
# string "2" or on None raised TypeError, so ONE malformed row from the JSON
# payload aborted the entire week summary -- the CLI printed nothing and the
# confirm gate never saw the row that caused it. NaN and Infinity had the
# opposite problem: they passed `hours < 0` cleanly and poisoned total_hours,
# every quadrant total and every percentage.


def test_a_string_hours_field_is_rejected_not_raised():
    """F1 (High). The JSON payload can carry "2" where a number belongs."""
    totals = aggregate(
        [ProjectWeek("good", "hygiene", 50, 2.0),
         ProjectWeek("stringy", "hygiene", 50, "2")],   # must not raise
        [],
    )
    assert totals.total_hours == pytest.approx(2.0)
    assert len(totals.rejected) == 1
    assert totals.rejected[0].row["project"] == "stringy"
    assert "not a finite number" in totals.rejected[0].reason
    assert _reconciles(totals)


def test_a_null_hours_field_is_rejected_not_raised():
    totals = aggregate([ProjectWeek("nully", "hygiene", 50, None)], [])
    assert totals.total_hours == 0.0
    assert len(totals.rejected) == 1
    assert "not a finite number" in totals.rejected[0].reason
    assert _reconciles(totals)


def test_a_boolean_is_not_one_hour_of_work():
    """A Python bool IS an int, so a plain isinstance check would count
    True as 1.0h. It is malformed input and must be reported as such."""
    totals = aggregate([ProjectWeek("boolish", "hygiene", 50, True)], [])
    assert totals.total_hours == 0.0
    assert totals.by_quadrant["hygiene"] == 0.0
    assert len(totals.rejected) == 1
    assert _reconciles(totals)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_hours_never_reach_total_hours(bad):
    """F2. These pass `hours < 0` cleanly and make every downstream number
    non-finite -- total, quadrant totals, percentages."""
    totals = aggregate(
        [ProjectWeek("good", "hygiene", 50, 2.0),
         ProjectWeek("wild", "growth-driver", 50, bad)],
        [],
    )
    assert math.isfinite(totals.total_hours)
    assert totals.total_hours == pytest.approx(2.0)
    assert all(math.isfinite(v) for v in totals.by_quadrant.values())
    assert math.isfinite(totals.unresolved_hours)
    assert len(totals.rejected) == 1
    assert _reconciles(totals)


@pytest.mark.parametrize("bad", ["80", None, float("nan"), float("inf"), True])
def test_an_offense_pct_that_is_not_a_finite_number_is_rejected(bad):
    """The hours are still good, so they count toward the week and route to
    unresolved -- but no mode is recorded off a value nobody can read."""
    totals = aggregate([ProjectWeek("odd", "hygiene", bad, 4.0)], [])
    assert totals.total_hours == pytest.approx(4.0)
    assert totals.unresolved_hours == pytest.approx(4.0)
    assert totals.by_mode == {"offense": 0.0, "defense": 0.0}
    assert len(totals.rejected) == 1
    assert "offense_pct" in totals.rejected[0].reason
    assert _reconciles(totals)


@pytest.mark.parametrize("bad", ["1.5", None, float("nan"), float("inf")])
def test_meeting_hours_that_are_not_a_finite_number_are_rejected(bad):
    totals = aggregate(
        [], [MeetingRow("standing", Resolution("hygiene", "role"), bad)])
    assert totals.total_hours == 0.0
    assert math.isfinite(totals.total_hours)
    assert len(totals.rejected) == 1
    assert totals.rejected[0].kind == "meeting"
    assert _reconciles(totals)


@pytest.mark.parametrize("bad", ["0.5", None, float("nan"), float("inf"), True])
def test_a_split_share_that_is_not_a_finite_number_costs_the_whole_row(bad):
    """Same rule as a negative share: a share nobody can read cannot be
    apportioned, so the row goes to unresolved intact rather than in part."""
    row = MeetingRow("mixed", Resolution(None, "topic",
                                         (("growth-driver", 0.5),
                                          ("hygiene", bad))), 3.0)
    totals = aggregate([], [row])
    assert totals.unresolved_hours == pytest.approx(3.0)
    assert sum(totals.by_quadrant.values()) == 0.0
    assert all(math.isfinite(v) for v in totals.by_quadrant.values())
    assert len(totals.rejected) == 1
    assert "split share" in totals.rejected[0].reason
    assert _reconciles(totals)


def test_an_unhashable_quadrant_is_reported_rather_than_raising():
    """A JSON payload can hand us a list where a quadrant string belongs.
    `value in by_quadrant` raises TypeError on an unhashable key."""
    totals = aggregate(
        [ProjectWeek("listy", ["growth-driver"], 50, 1.0)],
        [MeetingRow("listy", Resolution(None, "topic",
                                        ((["hygiene"], 1.0),)), 2.0)],
    )
    assert totals.unresolved_hours == pytest.approx(3.0)
    assert len(totals.rejected) == 2
    assert _reconciles(totals)


def test_summarize_reports_a_malformed_row_instead_of_aborting_the_week():
    """F1 through the JSON payload -- the shape close-week actually reads.
    One bad row must cost its own row, never the whole week summary."""
    result = summarize({
        "project_weeks": [
            {"project": "good", "quadrant": "growth-driver",
             "offense_pct": 80, "hours": 4.0},
            {"project": "stringy", "quadrant": "hygiene",
             "offense_pct": 50, "hours": "2"},
            {"project": "nully", "quadrant": "hygiene",
             "offense_pct": None, "hours": None},
        ],
        "meeting_rows": [
            {"label": "nan meeting", "quadrant": "hygiene",
             "resolved_by": "role", "hours": float("nan")},
        ],
        "history": [],
    })
    assert result["total_hours"] == pytest.approx(4.0)
    assert result["by_quadrant"]["growth-driver"] == pytest.approx(4.0)
    assert all(math.isfinite(v) for v in result["percentages"].values())
    assert len(_row_rejections(result)) == 3
    assert all(r["reason"] for r in result["rejected"])
    assert (sum(result["by_quadrant"].values()) + result["unresolved_hours"]
            == pytest.approx(result["total_hours"]))


def test_a_rejected_row_carrying_nan_still_serialises_as_valid_json():
    """The confirm gate prints `rejected` as JSON. json.dumps emits a bare
    `NaN`, which is not JSON at all -- a value that cannot be rendered
    honestly comes back as its repr instead."""
    result = summarize({
        "project_weeks": [{"project": "wild", "quadrant": "hygiene",
                           "offense_pct": 50, "hours": float("inf")}],
        "meeting_rows": [],
    })
    text = json.dumps(result["rejected"], allow_nan=False)   # must not raise
    assert "inf" in text
    assert _row_rejections(result)[0]["row"]["hours"] == "inf"


def test_cli_still_returns_a_week_when_one_payload_row_is_malformed():
    """The user-visible half of F1: the CLI used to exit non-zero with a
    TypeError traceback and print nothing at all."""
    payload = json.dumps({
        "project_weeks": [
            {"project": "good", "quadrant": "hygiene",
             "offense_pct": 0, "hours": 1.0},
            {"project": "stringy", "quadrant": "hygiene",
             "offense_pct": 50, "hours": "2"},
        ],
        "meeting_rows": [],
    })
    proc = _run_cli([], payload)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["total_hours"] == pytest.approx(1.0)
    assert len(_row_rejections(out)) == 1
    assert _row_rejections(out)[0]["row"]["hours"] == "2"


def test_parse_daily_note_skips_an_hours_field_that_floats_to_infinity():
    """The value parse_daily_note() PRODUCES is guarded too: the regex
    accepts unbounded digits, so a 400-digit hours field float()s to inf."""
    md = ("## Projects Touched\n"
          "- [[20-projects/lighthouse|lighthouse]] — ok · 2.5h · hygiene · 0% offense\n"
          "- [[20-projects/huge|huge]] — drifted · " + "9" * 400
          + "h · hygiene · 0% offense\n")
    parsed = parse_daily_note(md)
    assert [p.project for p in parsed.projects] == ["lighthouse"]
    assert all(math.isfinite(p.hours) for p in parsed.projects)
    assert parsed.skipped_count == 1


# --- G: normalisation order, and a rejection reason that tells the truth --


def test_an_invalid_shares_hours_reach_unresolved_instead_of_being_absorbed():
    """G. 2h split 0.7 / 0.6 / 0.1 with the last quadrant a typo.

    Dropping the typo BEFORE normalising scaled the two survivors up to
    fill its place: all 2h landed in valid quadrants and unresolved_hours
    stayed 0.0, while the emitted RejectedRow said that share had been
    'routed to unresolved'. The reason string has to be true."""
    row = MeetingRow("leadership standing", Resolution(
        None, "topic", (("growth-driver", 0.7),
                        ("hygiene", 0.6),
                        ("typo", 0.1))), 2.0)
    totals = aggregate([], [row])

    # Shares sum to 1.4, so everything scales by 1/1.4 -- the typo's 0.1
    # share keeps its own 1/14th of the meeting and that time is unresolved.
    assert totals.by_quadrant["growth-driver"] == pytest.approx(2.0 * 0.7 / 1.4)
    assert totals.by_quadrant["hygiene"] == pytest.approx(2.0 * 0.6 / 1.4)
    assert totals.unresolved_hours == pytest.approx(2.0 * 0.1 / 1.4)
    assert totals.unresolved_hours > 0.0
    assert sum(totals.by_quadrant.values()) == pytest.approx(2.0 * 1.3 / 1.4)
    assert _reconciles(totals)

    assert len(totals.rejected) == 1
    assert "typo" in totals.rejected[0].reason
    assert "unresolved" in totals.rejected[0].reason


def test_an_all_valid_over_one_split_still_normalises_to_nothing_unresolved():
    """The other half of the same rule: when nothing is dropped, scaling
    still absorbs the whole meeting, so unresolved stays 0.0."""
    row = MeetingRow("standing", Resolution(
        None, "topic", (("growth-driver", 0.7), ("hygiene", 0.6))), 2.0)
    totals = aggregate([], [row])
    assert totals.unresolved_hours == pytest.approx(0.0)
    assert sum(totals.by_quadrant.values()) == pytest.approx(2.0)
    assert _reconciles(totals)


def test_an_under_one_split_with_an_invalid_quadrant_is_not_scaled_up():
    """Under 1.0 is never normalised, so the invalid share AND the missing
    share both stay unresolved."""
    row = MeetingRow("standing", Resolution(
        None, "topic", (("growth-driver", 0.5), ("typo", 0.25))), 4.0)
    totals = aggregate([], [row])
    assert totals.by_quadrant["growth-driver"] == pytest.approx(2.0)
    assert totals.unresolved_hours == pytest.approx(2.0)
    assert _reconciles(totals)


# --- H: an out-of-vocabulary quadrant token is REPORTED, not nulled ------


def test_parse_daily_note_reports_an_out_of_vocabulary_quadrant():
    """H. Mapping ANY unrecognised token to None left skipped_count at 0
    and routed the hours to unresolved with no signal at all.
    'founder-transition' is a real legacy value in the vault today and
    would have vanished exactly this way."""
    md = ("## Projects Touched\n"
          "- [[20-projects/lighthouse|lighthouse]] — ok · 2.5h · growth-driver · 80% offense\n"
          "- [[20-projects/legacy|legacy]] — old value · 1.0h · founder-transition · 50% offense\n")
    parsed = parse_daily_note(md)

    assert [p.project for p in parsed.projects] == ["lighthouse"]
    assert parsed.skipped_count == 1
    assert "founder-transition" in parsed.skipped[0]


def test_parse_daily_note_maps_only_the_literal_uncategorized_token_to_none():
    """The one token that legitimately means 'no portfolio-category'."""
    md = ("## Projects Touched\n"
          "- [[20-projects/blank|blank]] — no category · 1.0h · uncategorized · 50% offense\n"
          "- [[20-projects/typo|typo]] — drift · 1.0h · uncatagorized · 50% offense\n")
    parsed = parse_daily_note(md)

    assert [(p.project, p.quadrant) for p in parsed.projects] == [("blank", None)]
    assert parsed.skipped_count == 1
    assert "uncatagorized" in parsed.skipped[0]


def test_cli_parse_daily_reports_an_out_of_vocabulary_quadrant_as_skipped():
    """The path close-week runs: the count it prints at the confirm gate
    has to include this line, or the hours vanish unannounced."""
    md = ("## Projects Touched\n"
          "- [[20-projects/legacy|legacy]] — old value · 1.0h · founder-transition · 50% offense\n")
    proc = _run_cli(["--parse-daily"], md)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["project_weeks"] == []
    assert out["skipped_count"] == 1
    assert "founder-transition" in out["skipped_lines"][0]


# --- the binding invariant, re-fuzzed over the newly-rejected shapes -----


def test_the_invariant_survives_randomised_malformed_input():
    """sum(by_quadrant) + unresolved_hours == total_hours for ANY input,
    and unresolved_hours >= 0 -- now including every value the boundary
    newly rejects. Seeded, so a failure is reproducible."""
    from companion.portfolio import _VALID

    rng = random.Random(20260829)
    # 1e308 / 8e307 / 5e307 are FINITE and their arithmetic is not: 1e308
    # hours at 50% overflows the product, and two 8e307-hour rows overflow
    # the running total. Validating the inputs was never enough.
    # HUGE INTS, not just huge floats. Python ints are arbitrary-precision
    # and math.isfinite() converts to float FIRST, so math.isfinite(10**400)
    # RAISES OverflowError instead of returning False -- the finiteness guard
    # raising the very exception it exists to prevent, killing the whole week
    # over one drifted number. The previous corpus had 1e308 but no big int,
    # which is why 481 green tests missed it.
    huge_int = 10 ** 400
    # FLOAT-MAX HOURS, added to the corpus in round 4. sys.float_info.max is
    # finite, and it has NO headroom: multiplied by a share one ulp above 1.0
    # it is Infinity. The old corpus had 1e308 (which does have headroom) but
    # never float_info.max, and never paired either with a share marginally
    # over 1.0 -- which is why 40,000 hostile iterations passed while
    # by_quadrant could still be handed an inf.
    float_max = sys.float_info.max
    numbers = [0.0, 1.0, 2.5, -3.0, 0.25, 1e308, 8e307, 5e307, float_max,
               huge_int, -huge_int, 10 ** 309, 2 ** 1024, 10 ** 308,
               "2", "", None, True, False, [], {}, object(),
               float("nan"), float("inf"), float("-inf")]
    quadrants = sorted(_VALID) + [None, "founder-transition", "", 7]
    percents = [0, 50, 100, 150, -20, "80", None, True, huge_int, -huge_int,
                float("nan"), float("inf")]
    # Shares chosen to sit just either side of the normalisation threshold,
    # plus two whose SUM leaves the finite range. `1.0 + 5e-10` slipped
    # through the old `> 1.0 + 1e-9` tolerance entirely.
    edge_shares = [1.0, 1.0 + 5e-10, 1.0000000005, 1.0 + 1e-16,
                   0.9999999999, 1e308, float_max, 0.5]

    for _ in range(400):
        projects = [
            ProjectWeek(f"p{i}", rng.choice(quadrants),
                        rng.choice(percents), rng.choice(numbers))
            for i in range(rng.randint(0, 4))
        ]
        meetings = []
        for i in range(rng.randint(0, 4)):
            roll = rng.random()
            if roll < 0.4:
                splits = tuple(
                    (rng.choice(quadrants), rng.choice(numbers))
                    for _ in range(rng.randint(1, 3))
                )
                res = Resolution(None, "topic", splits)
            elif roll < 0.6:
                # The round-4 combination: a valid quadrant, a share a hair
                # over 1.0 (or two shares whose sum overflows), and hours at
                # or near float_info.max.
                splits = tuple(
                    (rng.choice(sorted(_VALID)), rng.choice(edge_shares))
                    for _ in range(rng.randint(1, 3))
                )
                res = Resolution(None, "topic", splits)
                meetings.append(MeetingRow(
                    f"m{i}", res,
                    rng.choice([float_max, 1e308, 8e307, 1.0, 0.0])))
                continue
            else:
                res = Resolution(rng.choice(quadrants),
                                 rng.choice(["role", "project", "unresolved"]))
            meetings.append(MeetingRow(f"m{i}", res, rng.choice(numbers)))

        totals = aggregate(projects, meetings)          # must never raise

        assert math.isfinite(totals.total_hours)
        assert math.isfinite(totals.unresolved_hours)
        assert math.isfinite(totals.project_hours)
        assert all(math.isfinite(v) for v in totals.by_quadrant.values())
        assert all(math.isfinite(v) for v in totals.by_mode.values())
        assert all(math.isfinite(h) for modes in totals.by_quadrant_mode.values()
                   for h in modes.values())
        assert totals.unresolved_hours >= 0.0
        assert totals.project_hours <= totals.total_hours + 1e-9
        assert (sum(totals.by_quadrant.values()) + totals.unresolved_hours
                == pytest.approx(totals.total_hours))
        # Every rejected row must survive the JSON round-trip the confirm
        # gate does, and must carry a reason.
        for r in totals.rejected:
            assert r.reason
            json.dumps(r.row, allow_nan=False)


# --- F (cont.): payload SHAPE, the half aggregate() cannot see -----------
#
# aggregate() takes dataclasses, so a payload row missing a key outright
# never reaches it -- summarize() raised KeyError building the dataclass, and
# one such row aborted the whole week summary exactly like a bad value did.
# Same class, same failure mode, so: same answer, a RejectedRow naming the
# missing key.


@pytest.mark.parametrize(
    "missing", ["project", "quadrant", "offense_pct", "hours"])
def test_a_project_row_missing_a_required_key_is_rejected_not_raised(missing):
    row = {"project": "lighthouse", "quadrant": "hygiene",
           "offense_pct": 50, "hours": 2.0}
    del row[missing]
    result = summarize({"project_weeks": [row], "meeting_rows": []})

    assert result["total_hours"] == 0.0
    assert len(_row_rejections(result)) == 1
    assert _row_rejections(result)[0]["kind"] == "project"
    assert repr(missing) in _row_rejections(result)[0]["reason"]
    assert "missing required key" in _row_rejections(result)[0]["reason"]


@pytest.mark.parametrize("missing", ["label", "resolved_by", "hours"])
def test_a_meeting_row_missing_a_required_key_is_rejected_not_raised(missing):
    row = {"label": "standing", "quadrant": "hygiene",
           "resolved_by": "role", "hours": 1.0}
    del row[missing]
    result = summarize({"project_weeks": [], "meeting_rows": [row]})

    assert result["total_hours"] == 0.0
    assert len(_row_rejections(result)) == 1
    assert _row_rejections(result)[0]["kind"] == "meeting"
    assert repr(missing) in _row_rejections(result)[0]["reason"]


def test_a_meeting_row_may_still_omit_quadrant_and_splits():
    """Regression guard on the required-key list: both are documented as
    optional, and a split or unresolved meeting carries no quadrant at all.
    Requiring them would reject rows that are perfectly well-formed."""
    result = summarize({"meeting_rows": [
        {"label": "adhoc", "resolved_by": "unresolved", "hours": 1.5},
    ]})
    assert _row_rejections(result) == []
    assert result["total_hours"] == pytest.approx(1.5)
    assert result["unresolved_hours"] == pytest.approx(1.5)


def test_a_row_missing_a_key_costs_its_own_row_and_nothing_else():
    """The whole point: the good rows still produce a week."""
    result = summarize({
        "project_weeks": [
            {"project": "good", "quadrant": "growth-driver",
             "offense_pct": 100, "hours": 4.0},
            {"quadrant": "hygiene", "offense_pct": 50, "hours": 2.0},   # no project
        ],
        "meeting_rows": [
            {"label": "standing", "quadrant": "hygiene",
             "resolved_by": "role", "hours": 1.0},
            {"label": "broken", "quadrant": "hygiene"},                 # no hours
        ],
    })
    assert result["total_hours"] == pytest.approx(5.0)
    assert result["by_quadrant"]["growth-driver"] == pytest.approx(4.0)
    assert result["by_quadrant"]["hygiene"] == pytest.approx(1.0)
    assert len(_row_rejections(result)) == 2
    assert (sum(result["by_quadrant"].values()) + result["unresolved_hours"]
            == pytest.approx(result["total_hours"]))


@pytest.mark.parametrize("bad_splits", [
    "growth-driver",                       # a string, not a list
    {"growth-driver": 1.0},                # a dict
    [["growth-driver"]],                   # a pair that isn't a pair
    [["growth-driver", 0.5, "extra"]],
    [None],
])
def test_a_malformed_splits_container_is_rejected_not_unpacked(bad_splits):
    """`for q, s in splits` raises ValueError or TypeError on every one of
    these, which aborted the week before it reached aggregate()."""
    result = summarize({"meeting_rows": [
        {"label": "standing", "quadrant": None, "resolved_by": "topic",
         "hours": 2.0, "splits": bad_splits},
    ]})
    assert result["total_hours"] == 0.0
    assert len(_row_rejections(result)) == 1
    assert "splits" in _row_rejections(result)[0]["reason"]


@pytest.mark.parametrize("key", ["project_weeks", "meeting_rows", "history"])
def test_a_non_list_rows_container_is_reported_not_read_as_empty(key):
    """`for row in <a dict>` iterates its keys and blows up downstream; a
    silent empty read is a whole week of work vanishing with no signal."""
    result = summarize({key: {"oops": 1}})
    assert result["total_hours"] == 0.0
    assert len(_row_rejections(result)) == 1
    assert _row_rejections(result)[0]["kind"] == "payload"
    assert key in _row_rejections(result)[0]["reason"]


@pytest.mark.parametrize("payload", [None, [], "week", 3])
def test_a_payload_that_is_not_an_object_returns_an_empty_week_and_says_so(payload):
    result = summarize(payload)
    assert result["total_hours"] == 0.0
    assert result["flags"] == []
    assert len(_row_rejections(result)) == 1
    assert _row_rejections(result)[0]["kind"] == "payload"


# --- F (cont.): driver_hours / held_hours ---------------------------------


@pytest.mark.parametrize("key", ["driver_hours", "held_hours"])
@pytest.mark.parametrize("bad", ["4", None, float("nan"), float("inf"), True, []])
def test_bad_driver_or_held_hours_read_as_absent_and_are_reported(key, bad):
    """`held_hours > driver_hours` raises TypeError on a string or None, and
    a NaN compares false forever. These feed only the held-vs-driver flag, so
    a bad one must not cost the week -- but it reads as ABSENT, never as 0.0:
    0.0 is itself a number that can fire that flag. Reported twice, on
    purpose: once for the unreadable value, once for the flag it suppressed."""
    payload = {
        "project_weeks": [{"project": "good", "quadrant": "hygiene",
                           "offense_pct": 0, "hours": 3.0}],
        "meeting_rows": [],
        key: bad,
    }
    result = summarize(payload)                     # must not raise

    assert result["total_hours"] == pytest.approx(3.0)
    assert len(_row_rejections(result)) == 1
    assert _row_rejections(result)[0]["kind"] == "payload"
    assert key in _row_rejections(result)[0]["reason"]
    assert "never as 0.0" in _row_rejections(result)[0]["reason"]
    assert any("held-vs-driver flag did not run" in r["reason"]
               for r in _flag_suppressions(result))
    assert not any("held projects out-earned" in f for f in result["flags"])
    json.dumps(result["rejected"], allow_nan=False)


def test_a_bad_driver_hours_still_lets_the_rest_of_the_week_summarize():
    """Disproportionate is the thing to avoid: these two numbers drive one
    flag, and losing the whole Friday over them is worse than losing it."""
    result = summarize({
        "project_weeks": [{"project": "good", "quadrant": "reliability",
                           "offense_pct": 100, "hours": 6.0}],
        "meeting_rows": [{"label": "standing", "quadrant": "hygiene",
                          "resolved_by": "role", "hours": 2.0}],
        "driver_hours": "lots",
        "held_hours": None,
    })
    assert result["total_hours"] == pytest.approx(8.0)
    assert result["by_quadrant"]["reliability"] == pytest.approx(6.0)
    assert len(_row_rejections(result)) == 2
    # held 0.0 > driver 0.0 is false, so no flag is manufactured either.
    assert not any("out-earned" in f for f in result["flags"])


def test_good_driver_and_held_hours_still_fire_the_flag():
    result = summarize({
        "project_weeks": [{"project": "good", "quadrant": "reliability",
                           "offense_pct": 100, "hours": 6.0}],
        "meeting_rows": [],
        "driver_hours": 1.0,
        "held_hours": 5.0,
    })
    assert _row_rejections(result) == []
    assert any("out-earned" in f for f in result["flags"])


@pytest.mark.parametrize("entry", [
    None, "last week", 7, [],
    {},
    {"by_quadrant": "hygiene"},
    {"by_quadrant": {"hygiene": "lots"}},
    {"by_quadrant": {"hygiene": float("nan")}},
    {"by_mode": {"offense": "8", "defense": None}},
    {"by_mode": "none"},
    # Complete-looking, and still not a week: one quadrant is simply absent,
    # and reading it as 0h reliability is how the starvation flag used to be
    # manufactured out of a note that never recorded it.
    {"by_quadrant": {"growth-driver": 4.0, "operating-efficiency": 0.0,
                     "hygiene": 0.0, "cross-cutting": 0.0},
     "by_mode": {"offense": 4.0, "defense": 0.0}},
    # Partially invalid by_mode: offense readable, defense null.
    {"by_quadrant": {"growth-driver": 4.0, "operating-efficiency": 0.0,
                     "hygiene": 0.0, "reliability": 0.0, "cross-cutting": 0.0},
     "by_mode": {"offense": 10, "defense": None}},
    # Negative hours are not a week either.
    {"by_quadrant": {"growth-driver": -4.0, "operating-efficiency": 0.0,
                     "hygiene": 0.0, "reliability": 0.0, "cross-cutting": 0.0},
     "by_mode": {"offense": 4.0, "defense": 0.0}},
])
def test_a_history_entry_of_any_shape_cannot_raise_or_manufacture_a_flag(entry):
    """A prior week that is absent, malformed, or only partly readable is NOT
    history: it is suppressed entirely and the reason is reported. Reading it
    as zeros is what manufactured both trend flags -- 0h reliability IS the
    starvation condition, and a 0% defense share IS the rising-defense
    condition. The current week here has 0h reliability and 0% offense, so
    both flags would fire off a zero-valued prior week."""
    result = summarize({
        "project_weeks": [{"project": "good", "quadrant": "growth-driver",
                           "offense_pct": 0, "hours": 4.0}],
        "meeting_rows": [],
        "history": [entry],
    })
    assert result["total_hours"] == pytest.approx(4.0)
    assert not any("Defense share rose" in f for f in result["flags"])
    assert not any("Reliability starving" in f for f in result["flags"])
    assert all(math.isfinite(v) for v in result["by_quadrant"].values())
    # Suppression is never silent.
    assert any(r["kind"] == "payload" and "history suppressed" in r["reason"]
               for r in result["rejected"])


def test_one_malformed_history_entry_suppresses_the_whole_history():
    """evaluate_flags reads the list positionally -- history[0] IS last week.
    Keeping entry 1 after dropping a bad entry 0 would promote a two-weeks-ago
    week into last week's slot and compare against the wrong week."""
    good = {"by_quadrant": {"growth-driver": 10.0, "operating-efficiency": 0.0,
                            "hygiene": 0.0, "reliability": 0.0,
                            "cross-cutting": 0.0},
            "by_mode": {"offense": 10.0, "defense": 0.0}}
    result = summarize({
        "project_weeks": [{"project": "good", "quadrant": "growth-driver",
                           "offense_pct": 0, "hours": 4.0}],
        "meeting_rows": [],
        "history": [{"by_quadrant": {}}, good],
    })
    assert not any("Defense share rose" in f for f in result["flags"])
    assert not any("Reliability starving" in f for f in result["flags"])
    suppressions = [r for r in result["rejected"]
                    if "history suppressed" in r["reason"]]
    assert len(suppressions) == 1
    assert "entry 0" in suppressions[0]["reason"]


def test_a_complete_history_pair_still_fires_reliability_starvation():
    """The suppression must not become a blanket off-switch: two consecutive
    weeks that really did record 0h of reliability still fire the flag."""
    prior = {"by_quadrant": {"growth-driver": 10.0, "operating-efficiency": 0.0,
                             "hygiene": 0.0, "reliability": 0.0,
                             "cross-cutting": 0.0},
             "by_mode": {"offense": 10.0, "defense": 0.0}}
    result = summarize({
        "project_weeks": [{"project": "good", "quadrant": "growth-driver",
                           "offense_pct": 100, "hours": 4.0}],
        "meeting_rows": [],
        "history": [prior],
    })
    assert any("Reliability starving" in f for f in result["flags"])
    assert _row_rejections(result) == []


def test_cli_still_returns_a_week_when_a_payload_row_is_missing_a_key():
    payload = json.dumps({
        "project_weeks": [
            {"project": "good", "quadrant": "hygiene",
             "offense_pct": 0, "hours": 1.0},
            {"quadrant": "hygiene", "offense_pct": 0, "hours": 9.0},
        ],
        "meeting_rows": [],
        "driver_hours": "nope",
    })
    proc = _run_cli([], payload)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["total_hours"] == pytest.approx(1.0)
    assert {r["kind"] for r in out["rejected"]} == {"project", "payload"}


def test_the_invariant_survives_randomised_malformed_payloads():
    """The same fuzz as above, one layer up: through summarize()'s JSON
    payload, with rows missing keys and bad driver/held values. Nothing may
    raise, and the reconciliation invariant must still hold."""
    rng = random.Random(20260830)
    # 1e308 and 8e307 are FINITE inputs whose products and sums are not:
    # 1e308 * 50 overflows, and two 8e307-hour rows overflow the week total.
    # 10**400 and friends are the H1 corpus: a JSON integer literal has no
    # bound, json.load materialises it as a Python int, and math.isfinite()
    # RAISES on one rather than returning False.
    # float_info.max is the round-4 addition: finite, and with no headroom for
    # even one ulp of share above 1.0. -1 / -2.5 are the round-4 negatives for
    # driver_hours / held_hours, which used to INVERT the held-vs-driver flag
    # rather than being reported.
    float_max = sys.float_info.max
    values = [0.0, 1.0, 2.5, -3.0, -1, -2.5, "2", "", None, True, [], {},
              float("nan"), float("inf"), float("-inf"), 1e308, 8e307, 50,
              float_max, 10 ** 400, -(10 ** 400), 10 ** 309, 2 ** 1024,
              10 ** 308]
    quadrants = ["growth-driver", "hygiene", "cross-cutting", None,
                 "founder-transition", "", 7]
    # `resolved_by` is a CLOSED four-value vocabulary, and nothing enforced it
    # before round 4 -- an invented value flowed straight into Resolution and
    # was echoed back out in a rejection row.
    resolved_by_values = ["role", "topic", "project", "unresolved",
                          "banana", "", None, 7, []]
    splits_shapes = [
        None, [], "growth-driver", {"hygiene": 1.0}, [["hygiene"]], [None],
        # MALFORMED PAIRS -- the round-4 H1 shape. `Resolution(None, "topic",
        # ("bad",))` was constructible and raised ValueError three frames
        # away, inside aggregate(), killing the whole week summary.
        ["bad"], [("bad",)], [["growth-driver", 0.5, "extra"]], [[]],
        [["growth-driver", 0.5], "bad"], [7],
        [["growth-driver", 0.7], ["hygiene", 0.6], ["typo", 0.1]],
        [["growth-driver", "x"]], [["hygiene", 1.0]],
        # Finite shares whose SUM overflows.
        [["growth-driver", 1e308], ["hygiene", 1e308]],
        [["growth-driver", float_max], ["hygiene", float_max]],
        # Finite-as-JSON integer shares with no float at all.
        [["growth-driver", 10 ** 400], ["hygiene", 10 ** 400]],
        [["growth-driver", 10 ** 308], ["hygiene", 10 ** 308]],
        # A SHARE A HAIR OVER 1.0 -- the round-4 H6 shape. Paired with
        # float-max hours below, this stored Infinity in by_quadrant: the old
        # `> 1.0 + 1e-9` tolerance judged it close enough to skip
        # normalisation, and float-max has no headroom.
        [["hygiene", 1.0 + 5e-10]], [["hygiene", 1.0000000005]],
        [["hygiene", 1.0 + 1e-16]],
        [["growth-driver", 0.5000000005], ["hygiene", 0.5000000005]],
    ]
    # The hours paired with those split shapes, weighted towards the values
    # that have no headroom left.
    hours_values = values + [float_max, float_max, 1e308]

    def drop_keys(row):
        keys = list(row)
        for key in keys:
            if rng.random() < 0.25:
                del row[key]
        return row

    # INVALID ROW CONTAINERS, not just invalid rows -- the round-4 H3 shape.
    # `project_weeks: "bad"` / `null` was rejected by _payload_rows() and
    # STILL counted as a measured zero-hour week, because `current_measured`
    # read key presence rather than whether a container had been read; beside
    # one prior zero-reliability week that manufactured the two-week
    # reliability-starvation flag out of a payload with no rows in it.
    containers = ["rows", "rows", "rows", "bad", None, {"oops": 1}, 7, ""]

    def rows_or_junk(rows):
        choice = rng.choice(containers)
        return rows if choice == "rows" else choice

    for _ in range(400):
        payload = {
            "project_weeks": rows_or_junk([
                drop_keys({"project": f"p{i}",
                           "quadrant": rng.choice(quadrants),
                           "offense_pct": rng.choice(values),
                           "hours": rng.choice(values)})
                for i in range(rng.randint(0, 3))
            ]),
            "meeting_rows": rows_or_junk([
                drop_keys({"label": f"m{i}",
                           "quadrant": rng.choice(quadrants),
                           "resolved_by": rng.choice(resolved_by_values),
                           "hours": rng.choice(hours_values),
                           "splits": rng.choice(splits_shapes)})
                for i in range(rng.randint(0, 3))
            ]),
            "history": rng.choice([
                # Invalid CONTAINERS as well as invalid entries: `history`
                # has three states (absent, unreadable, empty) and each one
                # gets a different truthful sentence.
                "bad", None, {"oops": 1}, 7,
                [], [{}], [None], [{"by_mode": "x"}],
                # A complete-looking prior week carrying a big int.
                [{"by_quadrant": {"growth-driver": 10 ** 400,
                                  "operating-efficiency": 0.0, "hygiene": 0.0,
                                  "reliability": 0.0, "cross-cutting": 0.0},
                  "by_mode": {"offense": 10 ** 400, "defense": 1},
                  "by_quadrant_mode": {"growth-driver": {
                      "offense": 10 ** 400, "defense": 10 ** 400}}}],
                [{"by_quadrant": {"growth-driver": 1.0,
                                  "operating-efficiency": 0.0, "hygiene": 0.0,
                                  "reliability": 0.0, "cross-cutting": 0.0},
                  "by_mode": {"offense": 1.0, "defense": 0.0},
                  "by_quadrant_mode": rng.choice([
                      None, "x", {"typo": {"offense": 1.0, "defense": 0.0}},
                      {"growth-driver": {"offense": 1.0}},
                      {"growth-driver": {"offense": 1.0, "defense": 0.0}},
                  ])}],
            ]),
            "driver_hours": rng.choice(values),
            "held_hours": rng.choice(values),
        }

        result = summarize(payload)                 # must never raise

        assert math.isfinite(result["total_hours"])
        assert math.isfinite(result["unresolved_hours"])
        assert math.isfinite(result["project_hours"])
        assert all(math.isfinite(v) for v in result["by_quadrant"].values())
        assert all(math.isfinite(v) for v in result["percentages"].values())
        assert all(math.isfinite(v) for v in result["by_mode"].values())
        assert all(math.isfinite(v) for v in result["mode_percentages"].values())
        assert math.isfinite(result["unmoded_hours"])
        assert math.isfinite(result["unmoded_pct"])
        assert result["unmoded_hours"] >= 0.0
        assert all(math.isfinite(h)
                   for modes in result["by_quadrant_mode"].values()
                   for h in modes.values())
        assert all(math.isfinite(p)
                   for modes in result["quadrant_mode_percentages"].values()
                   for p in modes.values())
        assert result["unresolved_hours"] >= 0.0
        assert (sum(result["by_quadrant"].values()) + result["unresolved_hours"]
                == pytest.approx(result["total_hours"]))
        # The whole result -- rejected rows included -- must be printable as
        # strict JSON, because the CLI prints it and the skill reads it.
        json.dumps(result, allow_nan=False)
        for r in result["rejected"]:
            assert r["reason"]
            assert r["kind"] in {"project", "meeting", "payload"}
        # THE FLOOR MUST NOT BE WHAT IS PASSING THIS TEST. summarize() now
        # converts any unhandled exception into a `payload` rejection, which
        # would make every assertion above hold trivially for a payload the
        # specific validation had failed to guard. So no fuzz iteration may
        # reach it: an INTERNAL rejection here means a real escape, and the
        # per-shape guard for it is missing.
        assert not [r for r in result["rejected"]
                    if r["reason"].startswith("INTERNAL")], result["rejected"]


# --- mode_percentages is a share of ALL project hours ---------------------
#
# by_mode covers only the project rows that recorded a readable mode. A row
# whose offense_pct we reject still contributes its hours to the week and to
# project_hours -- so dividing by (offense + defense) reported a share of a
# base that had quietly shrunk, while the contract says "share of the week's
# project hours".


def test_mode_percentages_divide_by_all_project_hours_not_just_moded_ones():
    result = summarize({
        "project_weeks": [
            {"project": "moded", "quadrant": "growth-driver",
             "offense_pct": 100, "hours": 6.0},
            # offense_pct outside 0-100: hours count, mode does not.
            {"project": "unmoded", "quadrant": "hygiene",
             "offense_pct": 150, "hours": 2.0},
        ],
        "meeting_rows": [],
    })
    assert result["project_hours"] == pytest.approx(8.0)
    assert result["by_mode"]["offense"] == pytest.approx(6.0)
    # 6/8, not 6/6. The missing 25% is project time with no mode recorded --
    # visible, rather than absorbed into the rows that survived.
    assert result["mode_percentages"]["offense"] == pytest.approx(0.75)
    assert result["mode_percentages"]["defense"] == pytest.approx(0.0)
    assert sum(result["mode_percentages"].values()) < 1.0
    assert any("offense_pct" in r["reason"] for r in result["rejected"])


def test_mode_percentages_ignore_meeting_hours_in_their_denominator():
    """'Share of the week's PROJECT hours' -- a meeting carries a quadrant
    and deliberately no mode, so its hours belong to total_hours and to
    neither side of this split."""
    result = summarize({
        "project_weeks": [
            {"project": "alpha", "quadrant": "growth-driver",
             "offense_pct": 50, "hours": 4.0},
        ],
        "meeting_rows": [
            {"label": "standing", "quadrant": "hygiene",
             "resolved_by": "role", "hours": 6.0},
        ],
    })
    assert result["total_hours"] == pytest.approx(10.0)
    assert result["project_hours"] == pytest.approx(4.0)
    assert result["mode_percentages"]["offense"] == pytest.approx(0.5)
    assert result["mode_percentages"]["defense"] == pytest.approx(0.5)


def test_mode_percentages_are_zero_not_undefined_on_a_meetings_only_week():
    result = summarize({
        "project_weeks": [],
        "meeting_rows": [
            {"label": "standing", "quadrant": "hygiene",
             "resolved_by": "role", "hours": 6.0},
        ],
    })
    assert result["project_hours"] == 0.0
    assert result["mode_percentages"] == {"offense": 0.0, "defense": 0.0}


# --- finite inputs, finite RESULTS ---------------------------------------
#
# Round two promised every result survives json.dumps(allow_nan=False). It
# validated the inputs and not the arithmetic over them, so 1e308 hours at
# 50% offense produced Infinity out of two perfectly finite numbers.


def test_huge_but_finite_hours_and_percent_do_not_overflow_the_mode_split():
    result = summarize({
        "project_weeks": [
            {"project": "huge", "quadrant": "growth-driver",
             "offense_pct": 50, "hours": 1e308},
        ],
        "meeting_rows": [],
    })
    assert _row_rejections(result) == []
    assert result["by_mode"]["offense"] == pytest.approx(5e307)
    assert result["by_mode"]["defense"] == pytest.approx(5e307)
    assert math.isfinite(result["total_hours"])
    json.dumps(result, allow_nan=False)


def test_a_project_row_that_would_overflow_the_week_total_is_rejected():
    result = summarize({
        "project_weeks": [
            {"project": "big", "quadrant": "growth-driver",
             "offense_pct": 100, "hours": 1e308},
            {"project": "bigger", "quadrant": "hygiene",
             "offense_pct": 100, "hours": 1e308},
        ],
        "meeting_rows": [],
    })
    assert math.isfinite(result["total_hours"])
    assert result["total_hours"] == pytest.approx(1e308)
    assert result["by_quadrant"]["hygiene"] == 0.0
    overflow = [r for r in result["rejected"] if "overflow" in r["reason"]]
    assert len(overflow) == 1
    assert overflow[0]["kind"] == "project"
    json.dumps(result, allow_nan=False)


def test_a_meeting_row_that_would_overflow_the_week_total_is_rejected():
    result = summarize({
        "project_weeks": [
            {"project": "big", "quadrant": "growth-driver",
             "offense_pct": 100, "hours": 1e308},
        ],
        "meeting_rows": [
            {"label": "long", "quadrant": "hygiene",
             "resolved_by": "role", "hours": 1e308},
        ],
    })
    assert math.isfinite(result["total_hours"])
    overflow = [r for r in result["rejected"] if "overflow" in r["reason"]]
    assert len(overflow) == 1
    assert overflow[0]["kind"] == "meeting"
    json.dumps(result, allow_nan=False)


def test_split_shares_that_sum_past_the_finite_range_route_the_row_to_unresolved():
    """1.0/inf is 0.0, which would scale every share to zero and tell the
    reader the shares had been 'normalised'. Say what actually failed."""
    result = summarize({
        "project_weeks": [],
        "meeting_rows": [
            {"label": "standing", "quadrant": None, "resolved_by": "topic",
             "splits": [["growth-driver", 1e308], ["hygiene", 1e308]],
             "hours": 2.0},
        ],
    })
    assert result["total_hours"] == pytest.approx(2.0)
    assert result["unresolved_hours"] == pytest.approx(2.0)
    assert all(v == 0.0 for v in result["by_quadrant"].values())
    assert len(_row_rejections(result)) == 1
    assert "finite range" in _row_rejections(result)[0]["reason"]
    json.dumps(result, allow_nan=False)


def test_a_history_entry_whose_hours_sum_past_the_finite_range_is_suppressed():
    result = summarize({
        "project_weeks": [{"project": "good", "quadrant": "growth-driver",
                           "offense_pct": 0, "hours": 4.0}],
        "meeting_rows": [],
        "history": [
            {"by_quadrant": {"growth-driver": 1e308,
                             "operating-efficiency": 1e308,
                             "hygiene": 0.0, "reliability": 0.0,
                             "cross-cutting": 0.0},
             "by_mode": {"offense": 1e308, "defense": 1e308}},
        ],
    })
    assert any("history suppressed" in r["reason"] for r in result["rejected"])
    assert not any("decaying" in f for f in result["flags"])
    json.dumps(result, allow_nan=False)


# --- H1: a large JSON integer must be REJECTED, never fatal ---------------
#
# math.isfinite() converts its argument to float first, so math.isfinite() on
# an int with more than ~308 digits raises OverflowError rather than returning
# False. JSON permits an unbounded integer literal and json.load materialises
# it as a Python int, so one drifted number in a payload used to kill the
# whole week: the CLI exited 1 with EMPTY stdout and the confirm gate never
# saw the row that caused it -- the exact failure "nothing raises out of
# summarize()" exists to prevent.

_BIG_INT = 10 ** 400


def test_the_finiteness_guard_returns_false_on_a_huge_int_instead_of_raising():
    from companion.portfolio import _finite_number
    assert _finite_number(_BIG_INT) is False
    assert _finite_number(-_BIG_INT) is False
    assert _finite_number(10 ** 308) is True          # still inside float range
    assert _finite_number(2 ** 1024) is False         # just past float max


@pytest.mark.parametrize("payload", [
    pytest.param({"project_weeks": [{"project": "p", "quadrant": "hygiene",
                                     "offense_pct": 50, "hours": _BIG_INT}]},
                 id="project-hours"),
    pytest.param({"project_weeks": [{"project": "p", "quadrant": "hygiene",
                                     "offense_pct": _BIG_INT, "hours": 2.0}]},
                 id="offense-pct"),
    pytest.param({"meeting_rows": [{"label": "m", "quadrant": "hygiene",
                                    "resolved_by": "role",
                                    "hours": _BIG_INT}]},
                 id="meeting-hours"),
    pytest.param({"meeting_rows": [{"label": "m", "quadrant": None,
                                    "resolved_by": "topic", "hours": 2.0,
                                    "splits": [["hygiene", _BIG_INT]]}]},
                 id="split-share"),
    pytest.param({"driver_hours": _BIG_INT, "held_hours": 1.0},
                 id="driver-hours"),
    pytest.param({"held_hours": _BIG_INT, "driver_hours": 1.0},
                 id="held-hours"),
    pytest.param({"history": [{"by_quadrant": {"growth-driver": _BIG_INT,
                                               "operating-efficiency": 0.0,
                                               "hygiene": 0.0,
                                               "reliability": 0.0,
                                               "cross-cutting": 0.0},
                               "by_mode": {"offense": 1.0, "defense": 0.0}}]},
                 id="history-by-quadrant"),
    pytest.param({"history": [{"by_quadrant": {"growth-driver": 1.0,
                                               "operating-efficiency": 0.0,
                                               "hygiene": 0.0,
                                               "reliability": 0.0,
                                               "cross-cutting": 0.0},
                               "by_mode": {"offense": _BIG_INT,
                                           "defense": 0.0}}]},
                 id="history-by-mode"),
    pytest.param({"history": [{"by_quadrant": {"growth-driver": 1.0,
                                               "operating-efficiency": 0.0,
                                               "hygiene": 0.0,
                                               "reliability": 0.0,
                                               "cross-cutting": 0.0},
                               "by_mode": {"offense": 1.0, "defense": 0.0},
                               "by_quadrant_mode": {"growth-driver": {
                                   "offense": _BIG_INT, "defense": 0.0}}}]},
                 id="history-by-quadrant-mode"),
])
def test_a_huge_json_integer_is_rejected_and_never_kills_the_week(payload):
    result = summarize(payload)                       # must not raise
    assert any(r["reason"] for r in result["rejected"])
    assert math.isfinite(result["total_hours"])
    assert (sum(result["by_quadrant"].values()) + result["unresolved_hours"]
            == pytest.approx(result["total_hours"]))
    json.dumps(result, allow_nan=False)


def test_a_huge_json_integer_sum_is_rejected_not_fatal():
    """Every share finite on its own, their SUM past the float range -- and as
    ints there is no float for math.isfinite() to inspect at all."""
    result = summarize({
        "meeting_rows": [{"label": "m", "quadrant": None,
                          "resolved_by": "topic", "hours": 2.0,
                          "splits": [["growth-driver", 10 ** 308],
                                     ["hygiene", 10 ** 308]]}],
    })
    assert result["unresolved_hours"] == pytest.approx(2.0)
    json.dumps(result, allow_nan=False)


def test_cli_still_prints_a_week_when_a_payload_carries_a_huge_json_integer():
    """End to end: the CLI used to exit 1 with empty stdout on this input."""
    payload = json.dumps({
        "project_weeks": [
            {"project": "good", "quadrant": "growth-driver",
             "offense_pct": 100, "hours": 4.0},
            {"project": "drifted", "quadrant": "hygiene",
             "offense_pct": 50, "hours": int("9" * 400)},
        ],
        "meeting_rows": [], "history": [],
        "driver_hours": 4.0, "held_hours": 0.0,
    })
    proc = _run_cli([], payload)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["total_hours"] == pytest.approx(4.0)
    assert any("drifted" in json.dumps(r["row"]) for r in out["rejected"])


# --- H3: an absent driver_hours must suppress the flag, never invent it ---


def test_an_absent_driver_hours_suppresses_the_held_vs_driver_flag():
    """`payload.get(key, 0.0)` could not tell "nobody measured driver hours"
    from "driver hours are zero", so an absent field manufactured a
    decision-forcing claim about the builder's own prioritisation."""
    result = summarize({
        "project_weeks": [{"project": "p", "quadrant": "hygiene",
                           "offense_pct": 0, "hours": 5.0}],
        "meeting_rows": [],
        "held_hours": 5.0,
    })
    assert not any("held projects out-earned" in f for f in result["flags"])
    assert any("driver_hours" in r["reason"] and "did not run" in r["reason"]
               for r in result["rejected"])


def test_a_present_zero_driver_hours_still_fires_the_flag():
    """Absent suppresses; MEASURED zero is a real number and still fires."""
    result = summarize({
        "project_weeks": [{"project": "p", "quadrant": "hygiene",
                           "offense_pct": 0, "hours": 5.0}],
        "meeting_rows": [],
        "driver_hours": 0.0,
        "held_hours": 5.0,
    })
    assert any("held projects out-earned" in f for f in result["flags"])
    assert not any("held-vs-driver" in r["reason"] for r in result["rejected"])


# --- M4: the table and the flag must not print two different "defense
# shares". The week line divides by project_hours; the flag divides by
# growth-driver's own mode hours, which is exactly what the per-quadrant
# Offense / Defense column renders from.


def test_the_decay_flag_agrees_with_the_growth_driver_row_it_sits_beneath():
    payload = {
        "project_weeks": [
            {"project": "alpha", "quadrant": "growth-driver",
             "offense_pct": 50, "hours": 6.0},
            # offense_pct rejected: 2h of project hours with NO mode at all.
            {"project": "beta", "quadrant": "growth-driver",
             "offense_pct": 150, "hours": 2.0},
        ],
        "meeting_rows": [],
        "history": [
            {"by_quadrant": {"growth-driver": 6.0, "operating-efficiency": 0.0,
                             "hygiene": 0.0, "reliability": 0.0,
                             "cross-cutting": 0.0},
             "by_mode": {"offense": 6.0, "defense": 0.0},
             "by_quadrant_mode": {"growth-driver": {"offense": 6.0,
                                                    "defense": 0.0}}},
        ],
        "driver_hours": 8.0, "held_hours": 0.0,
    }
    result = summarize(payload)

    # The week line: 3h defense over 8h of project hours = 37.5%, and the
    # unmoded slice that explains why the two shares do not reach 100%.
    assert result["mode_percentages"]["defense"] == pytest.approx(0.375)
    assert result["unmoded_hours"] == pytest.approx(2.0)
    assert result["unmoded_pct"] == pytest.approx(0.25)
    # The growth-driver row: 3h defense over 6h of ITS recorded mode hours.
    row = result["quadrant_mode_percentages"]["growth-driver"]["defense"]
    assert row == pytest.approx(0.5)
    # The flag quotes the row's number, not a third one, and says what it is
    # a share OF. It must never print "50%" beside a table reading 37.5%
    # with both called "the defense share".
    decay = [f for f in result["flags"] if "decaying" in f]
    assert len(decay) == 1
    assert f"{row:.0%}" in decay[0]
    assert "recorded mode hours" in decay[0]


# --- M6: an ABSENT history must announce itself, not print as "no flags" ---


@pytest.mark.parametrize("history,expected", [
    pytest.param(None, "no `history` key", id="absent"),
    pytest.param([], "`history` is empty", id="empty"),
])
def test_an_absent_or_empty_history_reports_that_the_trend_flags_did_not_run(
        history, expected):
    """The first week on the pipeline, a gap week (Step 2a #5 signals it by
    passing []), an extended close and a rejected prior Step 2a all land
    here. Reported only for a MALFORMED history, the weekly note read
    identically to "no flags fired" -- the opposite meaning."""
    payload = {
        "project_weeks": [{"project": "p", "quadrant": "growth-driver",
                           "offense_pct": 50, "hours": 4.0}],
        "meeting_rows": [], "driver_hours": 4.0, "held_hours": 0.0,
    }
    if history is not None:
        payload["history"] = history
    result = summarize(payload)

    suppressions = _flag_suppressions(result)
    assert len(suppressions) == 1
    assert expected in suppressions[0]["reason"]
    assert "reliability-starvation" in suppressions[0]["reason"]
    assert "assets-decaying" in suppressions[0]["reason"]
    assert suppressions[0]["kind"] == "payload"
    json.dumps(result, allow_nan=False)


def test_a_complete_history_reports_no_suppression_at_all():
    """The other half: a week that CAN evaluate its flags must not print a
    suppression line, or the line stops meaning anything."""
    result = summarize({
        "project_weeks": [{"project": "p", "quadrant": "growth-driver",
                           "offense_pct": 50, "hours": 4.0}],
        "meeting_rows": [],
        "history": [
            {"by_quadrant": {"growth-driver": 4.0, "operating-efficiency": 0.0,
                             "hygiene": 0.0, "reliability": 4.0,
                             "cross-cutting": 0.0},
             "by_mode": {"offense": 4.0, "defense": 4.0},
             "by_quadrant_mode": {"growth-driver": {"offense": 2.0,
                                                    "defense": 2.0}}},
        ],
        "driver_hours": 4.0, "held_hours": 0.0,
    })
    assert result["rejected"] == []


# --- the "fifth instance" sweep: every remaining unknown-as-zero -----------


def test_an_absent_project_weeks_key_does_not_manufacture_reliability_starving():
    """A payload with NO row containers did not measure a week; it is not a
    week that measured 0h of reliability. With one valid prior week at zero,
    reading it as a measured zero fired "0h for 2 consecutive weeks" out of a
    payload that described no work at all."""
    history = [{"by_quadrant": {"growth-driver": 5.0,
                                "operating-efficiency": 0.0, "hygiene": 0.0,
                                "reliability": 0.0, "cross-cutting": 0.0},
                "by_mode": {"offense": 5.0, "defense": 0.0}}]
    absent = summarize({"history": history,
                        "driver_hours": 0.0, "held_hours": 0.0})
    assert not any("Reliability starving" in f for f in absent["flags"])
    assert any("unmeasured week" in r["reason"] for r in absent["rejected"])

    # An EXPLICIT empty week is measured, and still fires -- a real holiday
    # week with a starved prior week is exactly what the flag is for.
    measured = summarize({"project_weeks": [], "meeting_rows": [],
                          "history": history,
                          "driver_hours": 0.0, "held_hours": 0.0})
    assert any("Reliability starving" in f for f in measured["flags"])


def test_a_week_that_never_names_reliability_suppresses_rather_than_starves():
    """Direct callers build WeekTotals by hand. A by_quadrant that does not
    name reliability at all did not measure it, and 0h of reliability IS this
    flag's firing condition -- the rule has to live in the module, not in
    prose the next caller has not read."""
    unnamed = WeekTotals({"growth-driver": 5.0}, {"offense": 5.0,
                                                  "defense": 0.0}, 0.0, 5.0)
    rejects = []
    flags = evaluate_flags(unnamed, [unnamed], driver_hours=5.0,
                           held_hours=0.0, rejects=rejects)
    assert not any("Reliability starving" in f for f in flags)
    assert any("the key is absent, not zero" in r.reason for r in rejects)


def test_a_half_written_quadrant_mode_is_not_a_zero_defense_share():
    """`{"offense": 5.0}` with no `defense` key defaulted to 0.0 reads as a 0%
    defense share -- and 0% last week fires the flag against any week with
    defense in it. Absent has to stay absent."""
    from companion.portfolio import _quadrant_defense_share
    half = WeekTotals({"growth-driver": 5.0}, {"offense": 5.0, "defense": 0.0},
                      0.0, 5.0, {"growth-driver": {"offense": 5.0}})
    assert _quadrant_defense_share(half, "growth-driver") is None


# =========================================================================
# ROUND 4. Three classes of finding have each now appeared in three distinct
# shapes: malformed input RAISING instead of being reported, absent/invalid
# input MANUFACTURING a flag instead of suppressing one, and float edge cases
# defeating the finite-output invariant. Per-field, per-shape guards keep
# missing the next shape, so two of these fixes are structural -- validation
# where a Resolution is CONSTRUCTED (H1), and a last-resort floor under
# summarize() and main() (H2). These tests are about the guarantee, not only
# about the shape that exposed it.
# =========================================================================

from companion.portfolio import (                             # noqa: E402
    RESOLVED_BY, _crash_rejection, resolve_meeting)


# --- H1: a malformed Resolution is IMPOSSIBLE TO CONSTRUCT ---------------
#
# `Resolution(None, "topic", ("bad",))` was accepted and then raised
# ValueError three frames away, at aggregate()'s `for q, s in splits`,
# killing the whole week summary. Guarding aggregate() would close that one
# shape; validating at construction closes the CLASS, because no present or
# future consumer can be handed a malformed one.


@pytest.mark.parametrize("bad_splits", [
    ("bad",),                              # the reported shape: a 1-tuple
    ("bad", "worse"),
    (("growth-driver",),),                 # a pair that isn't a pair
    (("growth-driver", 0.5, "extra"),),    # three slots
    ((),),                                 # zero slots
    (None,),
    (7,),
    (("hygiene", 0.5), "bad"),             # one good entry, one not
    "growth-driver",                       # not a sequence of entries at all
    {"hygiene": 1.0},
    7,
])
def test_a_malformed_resolution_cannot_be_constructed_at_all(bad_splits):
    with pytest.raises(ValueError, match="splits"):
        Resolution(None, "topic", bad_splits)


def test_resolution_normalises_well_formed_splits_to_tuples_of_pairs():
    """After construction `for q, s in splits` is guaranteed to work, so no
    consumer needs a shape check of its own. A caller may hand in lists."""
    res = Resolution(None, "topic", [["hygiene", 0.5], ("growth-driver", 0.5)])
    assert res.splits == (("hygiene", 0.5), ("growth-driver", 0.5))
    assert all(isinstance(pair, tuple) and len(pair) == 2
               for pair in res.splits)


def test_the_malformed_row_that_used_to_kill_the_week_is_now_unbuildable():
    """The reported finding end to end: this row was built happily and then
    aborted aggregate()'s whole loop with ValueError."""
    with pytest.raises(ValueError):
        MeetingRow("standing", Resolution(None, "topic", ("bad",)), 2.0)


@pytest.mark.parametrize("bad", ["banana", "", None, 7, [], "Role"])
def test_a_resolved_by_outside_the_closed_vocabulary_cannot_be_constructed(bad):
    """`resolved_by` names WHICH cascade rule fired and is a closed
    four-value vocabulary. Nothing enforced it anywhere before: an invented
    value flowed into Resolution and was echoed back out to a human in a
    rejection row. An unhashable one must be refused, not raise TypeError."""
    with pytest.raises(ValueError, match="resolved_by"):
        Resolution("hygiene", bad)


def test_the_four_resolved_by_values_are_exactly_the_contract():
    assert RESOLVED_BY == ("role", "topic", "project", "unresolved")
    for value in RESOLVED_BY:
        assert Resolution("hygiene", value).resolved_by == value


@pytest.mark.parametrize("bad", ["banana", "", None, 7, []])
def test_a_payload_resolved_by_costs_its_own_row_never_the_week(bad):
    """The construction guard raises, so summarize() must gate `resolved_by`
    at the payload boundary -- otherwise a drifted value would reach the
    floor and cost the whole week instead of one row. Belt-and-braces means
    the specific rejection stays precise."""
    result = summarize({
        "project_weeks": [{"project": "good", "quadrant": "growth-driver",
                           "offense_pct": 50, "hours": 4.0}],
        "meeting_rows": [
            {"label": "ok", "quadrant": "hygiene", "resolved_by": "role",
             "hours": 1.0},
            {"label": "drifted", "quadrant": "hygiene", "resolved_by": bad,
             "hours": 2.0},
        ],
    })
    assert result["total_hours"] == pytest.approx(5.0)
    reasons = [r["reason"] for r in _row_rejections(result)]
    assert any("resolved_by" in r for r in reasons), reasons
    # Caught by the specific guard, NOT by the floor.
    assert not any(r.startswith("INTERNAL") for r in reasons)


# --- H2: the last-resort floor -------------------------------------------
#
# A 1-tuple (ValueError), a huge JSON integer (OverflowError) and a string
# where a number belonged (TypeError) are all one failure: something
# unanticipated escapes summarize(), the CLI exits 1 with EMPTY stdout, and
# the caller sees nothing at all on the one day this module exists to serve.
# Every specific guard stays; this is the floor underneath them.


class _AbsurdPayload(dict):
    """A payload no JSON document can produce, which is exactly the point:
    the floor exists for the shape nobody has thought of yet."""

    def __contains__(self, key):
        raise RuntimeError("absurd payload: __contains__ exploded")


def test_a_deliberately_absurd_payload_still_yields_parseable_json():
    result = summarize(_AbsurdPayload({"project_weeks": []}))

    json.dumps(result, allow_nan=False)          # strict JSON, not a traceback
    for key in ("by_quadrant", "by_mode", "by_quadrant_mode", "percentages",
                "mode_percentages", "quadrant_mode_percentages",
                "unresolved_hours", "total_hours", "project_hours", "flags"):
        assert key in result
    assert result["total_hours"] == 0.0
    assert result["unresolved_hours"] == 0.0
    assert result["flags"] == []

    # LOUD AND SPECIFIC -- a floor that emitted a clean empty week would be
    # worse than the crash it replaced, because an empty week looks exactly
    # like a light week.
    floor = [r for r in result["rejected"]
             if r["reason"].startswith("INTERNAL")]
    assert len(floor) == 1
    assert floor[0]["kind"] == "payload"
    assert "RuntimeError" in floor[0]["reason"]
    assert "absurd payload" in floor[0]["reason"]
    assert floor[0]["row"]["exception"] == "RuntimeError"
    assert "absurd payload" in floor[0]["row"]["message"]


def test_the_floor_names_the_exception_type_and_message():
    rejection = _crash_rejection(OverflowError("int too large to convert"))
    assert rejection.kind == "payload"
    assert "OverflowError" in rejection.reason
    assert "int too large to convert" in rejection.reason
    assert "bug in companion/portfolio.py" in rejection.reason
    json.dumps({"row": rejection.row}, allow_nan=False)


def test_the_cli_floors_malformed_stdin_json_instead_of_exiting_one():
    """`json.load(sys.stdin)` lives OUTSIDE summarize(), so main() needs the
    floor too. This printed a traceback to stderr and NOTHING to stdout, and
    a caller cannot tell that from a week with no work in it."""
    proc = _run_cli([], "this is not json {{{")

    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)                # must be parseable
    assert out["total_hours"] == 0.0
    floor = [r for r in out["rejected"] if r["reason"].startswith("INTERNAL")]
    assert len(floor) == 1
    assert "JSONDecodeError" in floor[0]["reason"]


def test_a_usage_error_still_exits_non_zero_because_it_is_not_a_data_problem():
    """The floor is for DATA. An unknown argv is a caller bug and must stay
    loud -- flooring it into a JSON rejection would hide a broken
    invocation behind a well-formed empty week."""
    from companion.portfolio import main
    assert main(["--nonsense"]) == 2


def test_parse_daily_mode_floors_a_crash_into_the_skipped_lines_it_reports(
        monkeypatch, capsys):
    """--parse-daily has no `rejected` list, so its floor routes the failure
    into `skipped_lines` / `skipped_count` -- which the skill is ALREADY
    required to report at its confirm gate, per day, even at 0. A new key
    nobody was told to read would be a silent failure in a report's
    clothing."""
    import io

    from companion import portfolio as mod

    def boom(_md):
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(mod, "parse_daily_note", boom)
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO("## Projects Touched\n"))
    assert mod.main(["--parse-daily"]) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["project_weeks"] == []
    assert out["skipped_count"] == 1
    assert "INTERNAL" in out["skipped_lines"][0]
    assert "RuntimeError" in out["skipped_lines"][0]
    assert out["error"]["exception"] == "RuntimeError"


# --- H3: MEASURED means a container was READ, not that a key was present --


@pytest.mark.parametrize("bad_container", ["bad", None, {"oops": 1}, 7, ""])
def test_an_unreadable_row_container_is_not_a_measured_week(bad_container):
    """summarize() set `current_measured` from KEY PRESENCE while
    _payload_rows() next door REJECTED the container -- so
    `project_weeks: "bad"` or `null` counted as a measured zero-hour week
    and, beside one prior zero-reliability week, fired the two-week
    reliability-starvation flag out of a payload from which not one row was
    ever read. This is the tenth instance of absent-input manufacturing a
    flag."""
    history = [{"by_quadrant": {"growth-driver": 5.0,
                                "operating-efficiency": 0.0, "hygiene": 0.0,
                                "reliability": 0.0, "cross-cutting": 0.0},
                "by_mode": {"offense": 5.0, "defense": 0.0}}]
    result = summarize({"project_weeks": bad_container, "history": history,
                        "driver_hours": 0.0, "held_hours": 0.0})

    assert not any("Reliability starving" in f for f in result["flags"])
    # The malformed container is reported, AND the suppression is reported --
    # two different facts a reader needs.
    reasons = [r["reason"] for r in result["rejected"]]
    assert any("not a list" in r for r in reasons), reasons
    assert any("unmeasured week" in r for r in reasons), reasons


def test_an_explicit_empty_container_is_still_a_measured_zero():
    """The other half, and the reason this cannot be a blanket suppression:
    `project_weeks: []` IS a measured empty week (a real holiday), and a
    holiday beside a starved prior week is exactly what the flag is for."""
    history = [{"by_quadrant": {"growth-driver": 5.0,
                                "operating-efficiency": 0.0, "hygiene": 0.0,
                                "reliability": 0.0, "cross-cutting": 0.0},
                "by_mode": {"offense": 5.0, "defense": 0.0}}]
    result = summarize({"project_weeks": [], "meeting_rows": [],
                        "history": history,
                        "driver_hours": 0.0, "held_hours": 0.0})
    assert any("Reliability starving" in f for f in result["flags"])


def test_a_broken_container_poisons_the_week_even_if_its_sibling_read_fine():
    """One readable container is NOT enough. `meeting_rows: []` reads fine and
    says there were no meetings -- but `project_weeks: "bad"` means project
    rows were supplied and are broken, and BOTH feed reliability hours. So a
    0h reliability total is not believable, and the flag must not fire.

    An earlier pass asserted the opposite here, on the reasoning that "the
    builder measured something". They measured MEETINGS. Reliability comes
    from both, so measuring one of two inputs cannot license a zero."""
    history = [{"by_quadrant": {"growth-driver": 5.0,
                                "operating-efficiency": 0.0, "hygiene": 0.0,
                                "reliability": 0.0, "cross-cutting": 0.0},
                "by_mode": {"offense": 5.0, "defense": 0.0}}]
    result = summarize({"project_weeks": "bad", "meeting_rows": [],
                        "history": history,
                        "driver_hours": 0.0, "held_hours": 0.0})
    assert not any("Reliability starving" in f for f in result["flags"]), \
        "a broken project container must not license a 0h reliability claim"
    # And the suppression is reported, naming the untrustworthy total.
    assert any("could not be trusted as measured" in r["reason"]
               for r in result["rejected"])


def test_an_absent_sibling_still_leaves_the_week_measured():
    """ABSENT is not INVALID. A caller that supplies only `meeting_rows` gave
    us everything it had, and an empty read there is a real measured zero --
    otherwise no flag could ever fire for a week with no project rows."""
    history = [{"by_quadrant": {"growth-driver": 5.0,
                                "operating-efficiency": 0.0, "hygiene": 0.0,
                                "reliability": 0.0, "cross-cutting": 0.0},
                "by_mode": {"offense": 5.0, "defense": 0.0}}]
    result = summarize({"meeting_rows": [], "history": history,
                        "driver_hours": 0.0, "held_hours": 0.0})
    assert any("Reliability starving" in f for f in result["flags"])


@pytest.mark.parametrize("bad_container,expected", [
    pytest.param("bad", "was not a list", id="string"),
    pytest.param(None, "was not a list", id="null"),
    pytest.param(7, "was not a list", id="int"),
])
def test_an_unreadable_history_says_so_rather_than_claiming_the_key_is_absent(
        bad_container, expected):
    """`history` has THREE states, not two. Saying "no `history` key in the
    payload" about a key that WAS there is an untrue reason, and a reader
    acts on the reason."""
    result = summarize({"project_weeks": [], "meeting_rows": [],
                        "history": bad_container,
                        "driver_hours": 1.0, "held_hours": 0.0})
    suppressions = _flag_suppressions(result)
    assert len(suppressions) == 1
    assert expected in suppressions[0]["reason"]
    assert "no `history` key in the payload" not in suppressions[0]["reason"]
    assert "is empty" not in suppressions[0]["reason"]


# --- H4: negative driver / held hours ------------------------------------


@pytest.mark.parametrize("key", ["driver_hours", "held_hours"])
@pytest.mark.parametrize("bad", [-1, -1.0, -0.5, -1e308])
def test_negative_driver_or_held_hours_is_reported_not_flagged(key, bad):
    """`driver_hours: -1` with `held_hours: 0` satisfies `held > driver` and
    printed "held projects out-earned drivers (0.0h vs -1.0h)" -- a
    decision-forcing claim about the builder's own prioritisation, computed
    from a number that cannot be hours, with the malformed input never
    reported at all."""
    payload = {"project_weeks": [], "meeting_rows": [],
               "driver_hours": 0.0, "held_hours": 0.0}
    payload[key] = bad
    result = summarize(payload)

    assert not any("out-earned" in f for f in result["flags"])
    reasons = [r["reason"] for r in result["rejected"]]
    assert any(f"{key} {bad!r} is not a non-negative finite number" in r
               for r in reasons), reasons
    # Absent, never 0.0 -- so the flag is suppressed AND says so.
    assert any(key in r and "did not run" in r for r in reasons), reasons


def test_the_exact_false_flag_from_the_finding_no_longer_fires():
    result = summarize({"project_weeks": [], "meeting_rows": [],
                        "driver_hours": -1, "held_hours": 0})
    assert result["flags"] == []
    assert not any("0.0h vs -1.0h" in r["reason"] for r in result["rejected"])


def test_a_genuine_measured_zero_driver_still_fires_the_flag():
    """Non-negative is the rule, not non-zero: 0.0 driver hours beside real
    held hours is a true reading and must still fire."""
    result = summarize({"project_weeks": [], "meeting_rows": [],
                        "driver_hours": 0.0, "held_hours": 3.0})
    assert any("out-earned" in f for f in result["flags"])


# --- H5: topic shares that sum to infinity -------------------------------


def test_topic_shares_summing_to_infinity_do_not_resolve_by_topic():
    """Two 1e308 shares are each finite and their SUM is not. Every share was
    divided by infinity and became 0.0 while the meeting stayed marked
    topic-resolved, so aggregation assigned NONE of its hours to any valid
    quadrant and sent them all silently to unresolved."""
    res = resolve_meeting([], [("growth-driver", 1e308), ("hygiene", 1e308)],
                          "reliability", [])
    # The cascade continues to the project default rather than inventing a
    # topic resolution out of zeros.
    assert res.resolved_by == "project"
    assert res.quadrant == "reliability"
    assert res.splits == ()
    assert "finite range" in res.note

    # And the hours land in that quadrant rather than in unresolved.
    totals = aggregate([], [MeetingRow("standing", res, 2.0)])
    assert totals.by_quadrant["reliability"] == pytest.approx(2.0)
    assert totals.unresolved_hours == pytest.approx(0.0)


def test_topic_shares_summing_to_infinity_with_no_project_default():
    res = resolve_meeting([], [("growth-driver", 1e308), ("hygiene", 1e308)],
                          None, [])
    assert res.resolved_by == "unresolved"
    assert res.quadrant is None
    assert "finite range" in res.note


def test_a_non_finite_or_unreadable_topic_share_never_reaches_the_total():
    """Type before value in the cascade too: `s > 0` on a string or None
    raises, and an unhashable quadrant raises on `q in _VALID` -- either
    would abort the cascade before the boundary that reports such things."""
    res = resolve_meeting(
        [],
        [("growth-driver", float("inf")), ("hygiene", "0.5"),
         (["cross-cutting"], 1.0), ("hygiene", None),
         ("reliability", 0.25)],
        None, [])
    # Only the one readable topic survives -- and it accounted for 0.25 of the
    # meeting, so it does NOT get the whole thing. Four of five topics were
    # unreadable here: booking 100% of the hours to the one share we could read
    # would be inventing attribution out of garbage input. The 0.75 remainder
    # is hours nobody assigned, and it belongs in unresolved.
    assert res.resolved_by == "topic"
    assert res.quadrant is None
    assert res.splits == (("reliability", 0.25),)


def test_a_single_topic_under_one_leaves_its_remainder_unresolved():
    """resolve_meeting() must normalise DOWN only, exactly like aggregate().
    A single topic covering 0.6 of a meeting used to come back as a
    quadrant-only Resolution, and aggregate() books a quadrant-only row's
    WHOLE hours to that quadrant -- so 100% of the meeting landed on a topic
    that accounted for 60% of it. The two sites normalised in opposite
    directions, which is what let it through."""
    res = resolve_meeting([], [("growth-driver", 0.6)], None, [])
    assert res.resolved_by == "topic"
    assert res.quadrant is None, "0.6 must not claim the whole meeting"
    assert res.splits == (("growth-driver", 0.6),)
    assert res.note == "", "nothing was normalised, so say nothing"

    # And the remainder genuinely reaches unresolved once aggregated.
    totals = aggregate([], [MeetingRow("m", res, 2.0)])
    assert totals.by_quadrant["growth-driver"] == pytest.approx(1.2)
    assert totals.unresolved_hours == pytest.approx(0.8)
    assert totals.total_hours == pytest.approx(2.0)


def test_a_single_topic_at_one_still_takes_the_whole_meeting():
    """The shortcut is still correct when the topic accounted for all of it."""
    res = resolve_meeting([], [("growth-driver", 1.0)], None, [])
    assert res.resolved_by == "topic"
    assert res.quadrant == "growth-driver"
    assert res.splits == ()


def test_normal_topic_shares_still_normalise_exactly_as_before():
    res = resolve_meeting([], [("growth-driver", 0.6), ("hygiene", 0.6)],
                          None, [])
    assert res.resolved_by == "topic"
    assert res.note == "shares normalised"
    assert sum(s for _, s in res.splits) == pytest.approx(1.0)


# --- H6: float-max hours with a share a hair over 1.0 --------------------
#
# THE FINITE-OUTPUT INVARIANT, which had survived 40,000 hostile fuzz
# iterations. The fuzz never combined float-max hours with a share a hair
# over 1.0, and the normalisation tolerance (`> 1.0 + 1e-9`) let exactly
# that pair through unscaled.


@pytest.mark.parametrize("share", [
    1.0000000005, 1.0 + 5e-10, 1.0 + 1e-16, 1.0 + 1e-12, 1.5, 2.0,
])
def test_float_max_hours_with_a_share_over_one_keeps_every_output_finite(share):
    row = MeetingRow("boom", Resolution(None, "topic", (("hygiene", share),)),
                     sys.float_info.max)
    totals = aggregate([], [row])

    assert all(math.isfinite(v) for v in totals.by_quadrant.values())
    assert math.isfinite(totals.total_hours)
    assert math.isfinite(totals.unresolved_hours)
    assert totals.unresolved_hours >= 0.0
    assert _reconciles(totals)
    # The whole result must survive the strict JSON the CLI prints.
    json.dumps({"by_quadrant": totals.by_quadrant,
                "unresolved_hours": totals.unresolved_hours,
                "total_hours": totals.total_hours}, allow_nan=False)


def test_the_exact_finding_share_is_normalised_rather_than_tolerated():
    """1.0000000005 is inside the old 1e-9 tolerance and outside 1.0. With
    float-max hours there is no headroom for either, so the threshold is
    1.0 exactly."""
    row = MeetingRow("boom",
                     Resolution(None, "topic", (("hygiene", 1.0000000005),)),
                     sys.float_info.max)
    totals = aggregate([], [row])
    assert totals.by_quadrant["hygiene"] == pytest.approx(
        sys.float_info.max, rel=1e-9)
    assert math.isfinite(totals.by_quadrant["hygiene"])


def test_an_apportionment_that_still_overflows_is_reported_not_stored():
    """The result guard, not just the threshold. Two float-max meeting rows
    into one quadrant cannot both fit, and the second must be REPORTED
    rather than turning the bucket into Infinity."""
    rows = [MeetingRow("a", Resolution(None, "topic", (("hygiene", 1.0),)),
                       sys.float_info.max),
            MeetingRow("b", Resolution(None, "topic", (("hygiene", 1.0),)),
                       sys.float_info.max)]
    totals = aggregate([], rows)

    assert all(math.isfinite(v) for v in totals.by_quadrant.values())
    assert _reconciles(totals)
    assert totals.rejected
    assert all(r.reason for r in totals.rejected)


def test_shares_under_one_are_untouched_by_the_stricter_threshold():
    """Removing the tolerance must not start normalising shares that sum to
    slightly LESS than 1.0 -- that missing slice is unresolved hours by
    design, not a rounding error to absorb."""
    row = MeetingRow("standing",
                     Resolution(None, "topic", (("hygiene", 0.9999999999),)),
                     4.0)
    totals = aggregate([], [row])
    assert totals.by_quadrant["hygiene"] == pytest.approx(4.0, rel=1e-9)
    assert totals.unresolved_hours >= 0.0
    assert _reconciles(totals)


# --- the re-audit: the same class, wherever else it was still per-shape ---


@pytest.mark.parametrize("bad", [None, "topic", {"quadrant": "hygiene"}, 7, ()])
def test_a_meeting_row_needs_a_real_resolution_to_be_built(bad):
    """aggregate() reads `row.resolution.splits` and `.quadrant`
    unconditionally, so a row built with None raised AttributeError three
    frames away and cost the whole week -- the same class as the malformed
    `splits` above, one type up."""
    with pytest.raises(TypeError, match="resolution"):
        MeetingRow("standing", bad, 1.0)


@pytest.mark.parametrize("field_index,bad", [
    (0, "growth-driver"), (0, None), (0, 7),       # by_quadrant
    (1, "offense"), (1, None),                      # by_mode
])
def test_week_totals_mapping_fields_must_be_mappings(field_index, bad):
    """Direct callers build these by hand (history entries, tests), and every
    consumer reads them unconditionally: evaluate_flags calls
    `.by_quadrant.get(...)`, _summary calls `.items()` on all three. A string
    there raised AttributeError deep inside a flag instead of at the mistake."""
    args = [{"growth-driver": 1.0}, {"offense": 1.0, "defense": 0.0}, 0.0, 1.0]
    args[field_index] = bad
    with pytest.raises(TypeError):
        WeekTotals(*args)


def test_week_totals_by_mode_must_name_both_modes():
    """Modes are exactly offense/defense, and _summary indexes both
    directly."""
    with pytest.raises(ValueError, match="by_mode is missing"):
        WeekTotals({"growth-driver": 1.0}, {"offense": 1.0}, 0.0, 1.0)


def test_week_totals_still_accepts_a_half_measured_quadrant_mode():
    """The one shape that must NOT be refused. `{"offense": 5.0}` with no
    `defense` is a HALF-MEASURED quadrant, which this module deliberately
    supports and reports as unmeasured rather than as zero defense. Refusing
    to build it would turn a handled case into a crash."""
    totals = WeekTotals({"growth-driver": 5.0},
                        {"offense": 5.0, "defense": 0.0}, 0.0, 5.0,
                        {"growth-driver": {"offense": 5.0}})
    assert totals.by_quadrant_mode == {"growth-driver": {"offense": 5.0}}


def test_by_quadrant_mode_is_read_the_same_way_by_both_of_its_readers():
    """_summary() indexed modes["offense"] directly while
    _quadrant_defense_share() guarded the same field with .get() and a
    finiteness check -- so a half-written entry was 'unmeasured' to one reader
    and a KeyError to the other. Two readings of one field is how the halves
    of this module have come apart before."""
    from companion.portfolio import _quadrant_defense_share, _summary
    half = WeekTotals({"growth-driver": 5.0},
                      {"offense": 5.0, "defense": 0.0}, 0.0, 5.0,
                      {"growth-driver": {"offense": 5.0}}, (), 5.0)

    assert _quadrant_defense_share(half, "growth-driver") is None
    result = _summary(half, [], [])              # must not raise
    shares = result["quadrant_mode_percentages"]["growth-driver"]
    assert set(shares) == {"offense", "defense"}
    assert all(math.isfinite(v) for v in shares.values())
    json.dumps(result, allow_nan=False)


def test_every_public_entry_point_survives_the_worked_payload():
    """The contract end to end, on the payload the reference doc publishes:
    the invariants hold, nothing is rejected, and the whole result is strict
    JSON."""
    result = summarize({
        "project_weeks": [
            {"project": "atlas", "quadrant": "growth-driver",
             "offense_pct": 70, "hours": 12.0},
            {"project": "beacon", "quadrant": "operating-efficiency",
             "offense_pct": 100, "hours": 4.0},
            {"project": "cinder", "quadrant": "reliability",
             "offense_pct": 0, "hours": 3.0},
            {"project": "delta", "quadrant": "hygiene",
             "offense_pct": 50, "hours": 2.0},
        ],
        "meeting_rows": [
            {"label": "security review sync", "quadrant": "hygiene",
             "resolved_by": "role", "hours": 1.0},
            {"label": "leadership standing meeting", "quadrant": None,
             "resolved_by": "topic", "hours": 1.5,
             "splits": [["growth-driver", 0.6],
                        ["operating-efficiency", 0.4]]},
            {"label": "atlas team sync", "quadrant": "growth-driver",
             "resolved_by": "project", "hours": 1.0},
            {"label": "ad-hoc pull-aside", "quadrant": None,
             "resolved_by": "unresolved", "hours": 0.5},
        ],
        "history": [
            {"by_quadrant": {"growth-driver": 14.0,
                             "operating-efficiency": 5.0, "hygiene": 1.5,
                             "reliability": 0.0, "cross-cutting": 0.0},
             "by_mode": {"offense": 12.0, "defense": 8.5},
             "by_quadrant_mode": {
                 "growth-driver": {"offense": 8.0, "defense": 6.0},
                 "operating-efficiency": {"offense": 4.0, "defense": 0.0},
                 "hygiene": {"offense": 0.0, "defense": 1.5},
                 "reliability": {"offense": 0.0, "defense": 0.0},
                 "cross-cutting": {"offense": 0.0, "defense": 0.0}}},
        ],
        "driver_hours": 12.0,
        "held_hours": 4.0,
    })

    assert result["rejected"] == []
    assert result["total_hours"] == pytest.approx(25.0)
    assert (sum(result["by_quadrant"].values()) + result["unresolved_hours"]
            == pytest.approx(result["total_hours"]))
    assert result["unresolved_hours"] == pytest.approx(0.5)
    assert set(result["by_quadrant"]) == set(QUADRANTS) | {CROSS_CUTTING}
    assert all(math.isfinite(v) for v in result["by_quadrant"].values())
    json.dumps(result, allow_nan=False)
