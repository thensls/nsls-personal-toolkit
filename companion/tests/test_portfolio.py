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
