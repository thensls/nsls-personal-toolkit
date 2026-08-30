"""Regression tests for sweep_due.decide() — the freshness gate.

Why this file exists
--------------------
On 2026-08-23 the scheduled sweep timed out. `record_failure()` wrote
`finalized: true` + `complete: false`, and `decide()` classified that as
NEEDS_FINALIZE — which tells the wrapper "finalize only, do NOT re-sweep." So a
single failed run suppressed every retry until the 12-day interval elapsed, and
the following Sunday would have seen a "recent sweep" and skipped again. One
timeout bought weeks of silence on top of an already 30-day-stale roster.

`decide()` is pure — status dict + interval + today in, (code, reason) out — so
the whole failure class is cheap to pin down. These are the five states the gate
has to tell apart. The FRESH/NEEDS_FINALIZE cases are here to prove the fix did
not simply make everything DUE, which would be a different silent failure:
sweeping every single Sunday instead of never.

Run:  python3.12 -m pytest skills/person-intelligence/tests/test_sweep_due.py -q
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import sweep_due  # noqa: E402


INTERVAL = 12


def _status(tmp_path, payload):
    path = tmp_path / "last-sweep-status.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# The verbatim record written by scheduled_sweep.record_failure() on 2026-08-23.
FAILURE_RECORD = {
    "timestamp": "2026-08-23T11:59:41.268626+00:00",
    "sweep_date": "2026-08-23",
    "exit_code": 1,
    "error": "claude -p exited 1",
    "relationships_processed": 0,
    "complete": False,
    "finalized": True,
    "source": "scheduled_sweep",
}


def test_failure_record_is_due_same_day(tmp_path):
    """The regression. A failure is not a sweep, so it must retry immediately."""
    code, reason = sweep_due.decide(
        _status(tmp_path, FAILURE_RECORD), INTERVAL, date(2026, 8, 23)
    )
    assert code == sweep_due.DUE, reason
    assert "FAILED run" in reason


def test_failure_record_still_due_a_week_later(tmp_path):
    """Before the fix this went FRESH once `finalized` was truthy and age < interval."""
    code, reason = sweep_due.decide(
        _status(tmp_path, FAILURE_RECORD), INTERVAL, date(2026, 8, 30)
    )
    assert code == sweep_due.DUE, reason


def test_wrapper_written_failure_is_also_due(tmp_path):
    """sweep_launchd_wrapper.sh records pre-Python failures in the same shape."""
    payload = dict(
        FAILURE_RECORD,
        error="scheduled_sweep.py not found",
        source="sweep_launchd_wrapper",
    )
    code, _ = sweep_due.decide(_status(tmp_path, payload), INTERVAL, date(2026, 8, 24))
    assert code == sweep_due.DUE


def test_unfinalized_success_still_needs_finalize(tmp_path):
    """A genuine mid-sweep record (exit 0, no finalize yet) must NOT re-sweep.

    Guards against over-correcting the fix into "any incomplete record is DUE",
    which would start a second sweep on top of a running one.
    """
    payload = {
        "timestamp": "2026-08-24T02:01:37+00:00",
        "exit_code": 0,
        "error": None,
        "relationships_processed": 0,
        "relationship_count": 26,
    }
    code, reason = sweep_due.decide(
        _status(tmp_path, payload), INTERVAL, date(2026, 8, 24)
    )
    assert code == sweep_due.NEEDS_FINALIZE, reason


def test_healthy_finalized_sweep_is_fresh(tmp_path):
    """Guards against the fix degenerating into sweeping every Sunday."""
    payload = {
        "timestamp": "2026-08-23T20:00:00+00:00",
        "sweep_date": "2026-08-23",
        "exit_code": 0,
        "error": None,
        "relationships_processed": 26,
        "complete": True,
        "finalized": True,
    }
    code, reason = sweep_due.decide(
        _status(tmp_path, payload), INTERVAL, date(2026, 8, 25)
    )
    assert code == sweep_due.FRESH, reason


def test_healthy_but_stale_sweep_is_due(tmp_path):
    payload = {
        "sweep_date": "2026-08-23",
        "exit_code": 0,
        "error": None,
        "relationships_processed": 26,
        "complete": True,
        "finalized": True,
    }
    code, reason = sweep_due.decide(
        _status(tmp_path, payload), INTERVAL, date(2026, 9, 10)
    )
    assert code == sweep_due.DUE, reason


def test_missing_status_file_is_due(tmp_path):
    code, _ = sweep_due.decide(
        tmp_path / "does-not-exist.json", INTERVAL, date(2026, 8, 23)
    )
    assert code == sweep_due.DUE


def test_malformed_status_file_is_an_error_not_a_skip(tmp_path):
    path = tmp_path / "last-sweep-status.json"
    path.write_text("{not json", encoding="utf-8")
    code, _ = sweep_due.decide(path, INTERVAL, date(2026, 8, 23))
    assert code == sweep_due.ERROR


@pytest.mark.parametrize("exit_code", [1, 2, 124, 127])
def test_any_nonzero_exit_code_retries(tmp_path, exit_code):
    """124 = wrapper timeout kill, 127 = `claude` not on PATH. All must retry."""
    payload = dict(FAILURE_RECORD, exit_code=exit_code, error=f"exited {exit_code}")
    code, _ = sweep_due.decide(_status(tmp_path, payload), INTERVAL, date(2026, 8, 23))
    assert code == sweep_due.DUE
