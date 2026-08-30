import math
import random

import pytest
from companion.portfolio import (
    QUADRANTS, CROSS_CUTTING, RoleRule, parse_role_map,
)


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


def _totals(quadrants, offense=1.0, defense=1.0, total=None):
    base = {q: 0.0 for q in ("growth-driver", "operating-efficiency",
                             "hygiene", "reliability", "cross-cutting")}
    base.update(quadrants)
    return WeekTotals(base, {"offense": offense, "defense": defense}, 0.0,
                      total if total is not None else sum(base.values()))


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
    prior = _totals({"growth-driver": 10.0}, offense=9.0, defense=1.0)
    current = _totals({"growth-driver": 10.0}, offense=5.0, defense=5.0)
    flags = evaluate_flags(current, [prior], driver_hours=10.0, held_hours=0.0)
    assert any("defense" in f.lower() for f in flags)


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
            {"by_quadrant": {"reliability": 1.0, "growth-driver": 9.0},
             "by_mode": {"offense": 9.0, "defense": 1.0}},
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
    # This assertion depends on the history entry's by_mode content: current
    # defense share is 1.0/4.0 = 25% (from project hours only -- the meeting
    # carries no mode); the supplied history recorded a defense share of
    # 1.0/10.0 = 10%. 25% > 10% is a genuine rise, so the flag fires. Delete
    # the history entry, or raise its defense hours to >= 2.5 (>= current's
    # share), and this flag stops firing.
    assert any("defense" in f.lower() for f in result["flags"])


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
            {"by_quadrant": {"growth-driver": 10.0},
             "by_mode": {"offense": 9.0, "defense": 1.0}},
        ],
        "driver_hours": 10.0,
        "held_hours": 0.0,
    }
    result = summarize(payload)
    assert any("defense" in f.lower() for f in result["flags"])


def test_summarize_with_a_by_mode_less_history_entry_produces_no_defense_flag():
    payload = {
        "project_weeks": [
            {"project": "alpha", "quadrant": "growth-driver",
             "offense_pct": 50, "hours": 10.0},
        ],
        "meeting_rows": [],
        "history": [
            {"by_quadrant": {"growth-driver": 10.0}},
        ],
        "driver_hours": 10.0,
        "held_hours": 0.0,
    }
    result = summarize(payload)
    assert not any("defense" in f.lower() for f in result["flags"])


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

    assert len(result["rejected"]) == 2
    assert {r["kind"] for r in result["rejected"]} == {"project", "meeting"}
    assert all(r["reason"] for r in result["rejected"])
    assert result["rejected"][0]["row"]["offense_pct"] == 150
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
    assert result["rejected"] == []


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
    assert len(out["rejected"]) == 1
    assert out["rejected"][0]["row"]["quadrant"] == "made-up"
    assert "made-up" in out["rejected"][0]["reason"]


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
    assert len(result["rejected"]) == 3
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
    assert result["rejected"][0]["row"]["hours"] == "inf"


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
    assert len(out["rejected"]) == 1
    assert out["rejected"][0]["row"]["hours"] == "2"


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
    numbers = [0.0, 1.0, 2.5, -3.0, 0.25,
               "2", "", None, True, False, [], {}, object(),
               float("nan"), float("inf"), float("-inf")]
    quadrants = sorted(_VALID) + [None, "founder-transition", "", 7]
    percents = [0, 50, 100, 150, -20, "80", None, True,
                float("nan"), float("inf")]

    for _ in range(400):
        projects = [
            ProjectWeek(f"p{i}", rng.choice(quadrants),
                        rng.choice(percents), rng.choice(numbers))
            for i in range(rng.randint(0, 4))
        ]
        meetings = []
        for i in range(rng.randint(0, 4)):
            if rng.random() < 0.5:
                splits = tuple(
                    (rng.choice(quadrants), rng.choice(numbers))
                    for _ in range(rng.randint(1, 3))
                )
                res = Resolution(None, "topic", splits)
            else:
                res = Resolution(rng.choice(quadrants),
                                 rng.choice(["role", "project", "unresolved"]))
            meetings.append(MeetingRow(f"m{i}", res, rng.choice(numbers)))

        totals = aggregate(projects, meetings)          # must never raise

        assert math.isfinite(totals.total_hours)
        assert math.isfinite(totals.unresolved_hours)
        assert all(math.isfinite(v) for v in totals.by_quadrant.values())
        assert totals.unresolved_hours >= 0.0
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
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["kind"] == "project"
    assert repr(missing) in result["rejected"][0]["reason"]
    assert "missing required key" in result["rejected"][0]["reason"]


@pytest.mark.parametrize("missing", ["label", "resolved_by", "hours"])
def test_a_meeting_row_missing_a_required_key_is_rejected_not_raised(missing):
    row = {"label": "standing", "quadrant": "hygiene",
           "resolved_by": "role", "hours": 1.0}
    del row[missing]
    result = summarize({"project_weeks": [], "meeting_rows": [row]})

    assert result["total_hours"] == 0.0
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["kind"] == "meeting"
    assert repr(missing) in result["rejected"][0]["reason"]


def test_a_meeting_row_may_still_omit_quadrant_and_splits():
    """Regression guard on the required-key list: both are documented as
    optional, and a split or unresolved meeting carries no quadrant at all.
    Requiring them would reject rows that are perfectly well-formed."""
    result = summarize({"meeting_rows": [
        {"label": "adhoc", "resolved_by": "unresolved", "hours": 1.5},
    ]})
    assert result["rejected"] == []
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
    assert len(result["rejected"]) == 2
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
    assert len(result["rejected"]) == 1
    assert "splits" in result["rejected"][0]["reason"]


@pytest.mark.parametrize("key", ["project_weeks", "meeting_rows", "history"])
def test_a_non_list_rows_container_is_reported_not_read_as_empty(key):
    """`for row in <a dict>` iterates its keys and blows up downstream; a
    silent empty read is a whole week of work vanishing with no signal."""
    result = summarize({key: {"oops": 1}})
    assert result["total_hours"] == 0.0
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["kind"] == "payload"
    assert key in result["rejected"][0]["reason"]


@pytest.mark.parametrize("payload", [None, [], "week", 3])
def test_a_payload_that_is_not_an_object_returns_an_empty_week_and_says_so(payload):
    result = summarize(payload)
    assert result["total_hours"] == 0.0
    assert result["flags"] == []
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["kind"] == "payload"


# --- F (cont.): driver_hours / held_hours ---------------------------------


@pytest.mark.parametrize("key", ["driver_hours", "held_hours"])
@pytest.mark.parametrize("bad", ["4", None, float("nan"), float("inf"), True, []])
def test_bad_driver_or_held_hours_read_as_zero_and_are_reported(key, bad):
    """`held_hours > driver_hours` raises TypeError on a string or None, and
    a NaN compares false forever. These feed only the held-vs-driver flag,
    so a bad one reads 0.0 -- but it is REPORTED, because 0.0 is itself a
    number that can fire (or suppress) that flag."""
    payload = {
        "project_weeks": [{"project": "good", "quadrant": "hygiene",
                           "offense_pct": 0, "hours": 3.0}],
        "meeting_rows": [],
        key: bad,
    }
    result = summarize(payload)                     # must not raise

    assert result["total_hours"] == pytest.approx(3.0)
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["kind"] == "payload"
    assert key in result["rejected"][0]["reason"]
    assert "0.0" in result["rejected"][0]["reason"]
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
    assert len(result["rejected"]) == 2
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
    assert result["rejected"] == []
    assert any("out-earned" in f for f in result["flags"])


@pytest.mark.parametrize("entry", [
    None, "last week", 7, [],
    {"by_quadrant": "hygiene"},
    {"by_quadrant": {"hygiene": "lots"}},
    {"by_quadrant": {"hygiene": float("nan")}},
    {"by_mode": {"offense": "8", "defense": None}},
    {"by_mode": "none"},
])
def test_a_history_entry_of_any_shape_cannot_raise_or_manufacture_a_flag(entry):
    """A malformed prior week reads as an EMPTY week -- the same state as an
    omitted by_mode, which evaluate_flags already treats as 'no data'. It can
    only suppress a trend flag, never invent one."""
    result = summarize({
        "project_weeks": [{"project": "good", "quadrant": "growth-driver",
                           "offense_pct": 0, "hours": 4.0}],
        "meeting_rows": [],
        "history": [entry],
    })
    assert result["total_hours"] == pytest.approx(4.0)
    assert not any("Defense share rose" in f for f in result["flags"])
    assert all(math.isfinite(v) for v in result["by_quadrant"].values())


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
    values = [0.0, 1.0, 2.5, -3.0, "2", "", None, True, [], {},
              float("nan"), float("inf"), float("-inf")]
    quadrants = ["growth-driver", "hygiene", "cross-cutting", None,
                 "founder-transition", "", 7]
    splits_shapes = [
        None, [], "growth-driver", {"hygiene": 1.0}, [["hygiene"]], [None],
        [["growth-driver", 0.7], ["hygiene", 0.6], ["typo", 0.1]],
        [["growth-driver", "x"]], [["hygiene", 1.0]],
    ]

    def drop_keys(row):
        keys = list(row)
        for key in keys:
            if rng.random() < 0.25:
                del row[key]
        return row

    for _ in range(400):
        payload = {
            "project_weeks": [
                drop_keys({"project": f"p{i}",
                           "quadrant": rng.choice(quadrants),
                           "offense_pct": rng.choice(values),
                           "hours": rng.choice(values)})
                for i in range(rng.randint(0, 3))
            ],
            "meeting_rows": [
                drop_keys({"label": f"m{i}",
                           "quadrant": rng.choice(quadrants),
                           "resolved_by": rng.choice(
                               ["role", "topic", "project", "unresolved"]),
                           "hours": rng.choice(values),
                           "splits": rng.choice(splits_shapes)})
                for i in range(rng.randint(0, 3))
            ],
            "history": rng.choice([[], [{}], [None], [{"by_mode": "x"}]]),
            "driver_hours": rng.choice(values),
            "held_hours": rng.choice(values),
        }

        result = summarize(payload)                 # must never raise

        assert math.isfinite(result["total_hours"])
        assert math.isfinite(result["unresolved_hours"])
        assert all(math.isfinite(v) for v in result["by_quadrant"].values())
        assert all(math.isfinite(v) for v in result["percentages"].values())
        assert result["unresolved_hours"] >= 0.0
        assert (sum(result["by_quadrant"].values()) + result["unresolved_hours"]
                == pytest.approx(result["total_hours"]))
        # The whole result -- rejected rows included -- must be printable as
        # strict JSON, because the CLI prints it and the skill reads it.
        json.dumps(result, allow_nan=False)
        for r in result["rejected"]:
            assert r["reason"]
            assert r["kind"] in {"project", "meeting", "payload"}
