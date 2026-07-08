from companion.streak import compute_concern, status_for, streak_days, DayResult


def test_a_five_hits_streak_5_concern_0():
    log = [DayResult(date=f"2026-05-1{i}", percent=1.0) for i in range(1, 6)]
    assert streak_days(log) == 5
    assert compute_concern(log) == 0
    assert status_for(compute_concern(log)) == "ok"


def test_b_partial_middle_then_full_streak_alive():
    log = [
        DayResult("2026-05-11", 1.0),
        DayResult("2026-05-12", 1.0),
        DayResult("2026-05-13", 0.5),
        DayResult("2026-05-14", 1.0),
        DayResult("2026-05-15", 1.0),
    ]
    assert streak_days(log) == 5
    assert compute_concern(log) == 0


def test_c_two_partials_one_miss_recorded():
    log = [
        DayResult("2026-05-13", 1.0),
        DayResult("2026-05-14", 0.5),
        DayResult("2026-05-15", 0.5),
    ]
    assert compute_concern(log) == 1.0
    assert status_for(1.0) == "one_miss"


def test_d_three_partials_at_risk():
    log = [
        DayResult("2026-05-13", 0.5),
        DayResult("2026-05-14", 0.5),
        DayResult("2026-05-15", 0.5),
    ]
    assert compute_concern(log) == 1.5
    assert status_for(1.5) == "at_risk"


def test_e_four_partials_reset():
    log = [
        DayResult("2026-05-12", 0.5),
        DayResult("2026-05-13", 0.5),
        DayResult("2026-05-14", 0.5),
        DayResult("2026-05-15", 0.5),
    ]
    assert compute_concern(log) == 2.0
    assert status_for(2.0) == "reset"


def test_f_two_misses_reset():
    log = [
        DayResult("2026-05-13", 1.0),
        DayResult("2026-05-14", 0.0),
        DayResult("2026-05-15", 0.0),
    ]
    assert compute_concern(log) == 2.0
    assert status_for(2.0) == "reset"


def test_mixed_miss_then_partial_at_risk():
    log = [DayResult("2026-05-14", 0.0), DayResult("2026-05-15", 0.5)]
    assert compute_concern(log) == 1.5


def test_full_day_mid_chain_clears_concern():
    log = [
        DayResult("2026-05-12", 0.5),
        DayResult("2026-05-13", 0.5),
        DayResult("2026-05-14", 1.0),
        DayResult("2026-05-15", 0.5),
    ]
    assert compute_concern(log) == 0.5


def test_empty_log_returns_zero():
    assert compute_concern([]) == 0
    assert streak_days([]) == 0
