"""The sweep's own bookkeeping must not raise when the cache dir is unwritable.

Macroscope, 2026-08-23 (round 3), 🟠 High: `_write_transcript` caught its OSError and then
called `log()` from the handler — but `log()` does `mkdir` + `open` with no guard of its own,
so on a full or read-only cache dir the exception escaped `_write_transcript`, propagated out
of `run_claude()`, and `main()` never recorded the sweep failure or returned an exit code.

A disk problem would therefore turn a *recorded* failure into a bare traceback with no status
file — the exact silent-failure class this module exists to prevent, triggered by the act of
logging it. The root cause was `log()`, not the one call site, so `log()` is what was fixed;
these tests pin every path that runs inside an error handler.

`/dev/null/...` is used as the unwritable directory: `mkdir` under a non-directory raises
NotADirectoryError (an OSError subclass) on both macOS and Linux, with no privileges needed
and nothing to clean up.

Run: python3 -m pytest skills/person-intelligence/tests/test_sweep_io_resilience.py -q
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import scheduled_sweep as ss  # noqa: E402

UNWRITABLE = Path("/dev/null/definitely-not-a-directory")


def test_log_does_not_raise_on_unwritable_cache_dir(capsys):
    ss.log(UNWRITABLE, "hello")
    out = capsys.readouterr().out
    # The message itself must still reach stdout — that is what lands in launchd.log.
    assert "hello" in out
    # And the degradation must be announced, not swallowed.
    assert "could not append" in out


def test_write_transcript_does_not_raise_on_unwritable_cache_dir(capsys):
    """This is the reported defect: the handler's own log() call used to escape."""
    ss._write_transcript(UNWRITABLE, 1, "some stdout", "some stderr")
    out = capsys.readouterr().out
    assert "could not write the claude transcript" in out


def test_record_failure_does_not_raise_on_unwritable_cache_dir(capsys):
    """main() calls this on the way to returning non-zero; a raise loses the exit code too."""
    ss.record_failure(UNWRITABLE, date(2026, 8, 23), "claude -p exited 1")
    err = capsys.readouterr().err
    assert "FATAL" in err
    assert "freshness gate" in err


def test_write_transcript_succeeds_normally(tmp_path):
    """Guard against the resilience fix quietly disabling the feature."""
    ss._write_transcript(tmp_path, 0, "OUT-MARKER", "ERR-MARKER")
    logs = list(tmp_path.glob("claude-run-*.log"))
    assert len(logs) == 1
    body = logs[0].read_text(encoding="utf-8")
    assert "OUT-MARKER" in body and "ERR-MARKER" in body
    assert "# exit=0" in body


def test_write_transcript_keeps_both_runs_within_one_second(tmp_path):
    """Microsecond precision — a forced run overlapping the scheduled one must not clobber it."""
    for i in range(3):
        ss._write_transcript(tmp_path, i, f"out{i}", f"err{i}")
    assert len(list(tmp_path.glob("claude-run-*.log"))) == 3


def test_record_failure_writes_a_retryable_record(tmp_path):
    """End-to-end with sweep_due: a recorded failure must come back DUE, not NEEDS_FINALIZE."""
    ss.record_failure(tmp_path, date(2026, 8, 23), "claude -p exited 1")
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "sweep_due.py"),
            "--cache-dir",
            str(tmp_path),
            "--today",
            "2026-08-30",
        ],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stdout + out.stderr  # 0 == DUE
    assert "FAILED run" in out.stdout


def test_record_failure_does_not_clobber_a_newer_complete_sweep(tmp_path):
    """Pre-existing guard; pinned so the resilience refactor cannot have dropped it."""
    path = tmp_path / "last-sweep-status.json"
    path.write_text(
        '{"sweep_date": "2026-09-01", "complete": true, "finalized": true, '
        '"relationships_processed": 26, "exit_code": 0, "error": null}',
        encoding="utf-8",
    )
    ss.record_failure(tmp_path, date(2026, 8, 23), "stale failure")
    assert "stale failure" not in path.read_text(encoding="utf-8")
