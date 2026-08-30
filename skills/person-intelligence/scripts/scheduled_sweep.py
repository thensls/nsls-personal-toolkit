#!/usr/bin/env python3
"""scheduled_sweep.py — the single entry point an OS scheduler calls.

This exists because the biweekly sweep CANNOT run as a Claude cloud routine.
A routine executes in an isolated cloud sandbox with no local filesystem and no
MCP connectors, so it can reach neither the Obsidian vault nor Fathom/Signal.
The sweep has to run on the user's own machine, under their own credentials.

Scheduler → this script → `claude -p` (headless Claude Code) → the sweep pipeline.

Both platforms call this identically, so there is no shell/PowerShell logic to
drift apart:
    macOS    launchd     → python3.12 scheduled_sweep.py
    Windows  Task Sched. → python      scheduled_sweep.py

Cadence: the scheduler fires WEEKLY; `sweep_due.py` gates it down to biweekly.
Standard cron cannot express "every other Sunday" (`0/2` in the day-of-week
field means Sun/Tue/Thu/Sat), so the every-other-week decision lives here.

Nothing here fails silently. Every run appends a timestamped line to
`~/.cache/person-intelligence/sweep-cron.log`, and a failed or incomplete sweep
is written back into `last-sweep-status.json` so `/open-day` surfaces it the
next morning.

Usage:
    python3.12 scheduled_sweep.py [--dry-run] [--force] [--interval-days 12]
"""

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import load_dotenv_local  # noqa: E402,F401  — populate os.environ for non-interactive runs
from sweep_due import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    DEFAULT_INTERVAL_DAYS,
    DUE,
    ERROR,
    FRESH,
    NEEDS_FINALIZE,
    decide,
)

LOG_NAME = "sweep-cron.log"

# Timeout for the headless Claude run. A 21-relationship sweep takes well under
# an hour; past that something is wedged and we want a recorded failure, not a
# scheduler job that hangs until the next firing.
CLAUDE_TIMEOUT_SECONDS = 3 * 60 * 60

SWEEP_PROMPT = """\
Run the person-intelligence biweekly sweep end to end. This is an unattended \
scheduled run: there is no user present, so never ask a question, never wait for \
approval, and never stop to propose options — make the reasonable choice and \
continue.

Follow the "Mode: Biweekly Sweep" section of the person-intelligence skill:

1. Build the manifest with biweekly_sweep.py.
2. For every relationship in the manifest, run per-person synthesis. Where the \
manifest sets signal_ingest_planned, first run \
`fetch_signal.py --fetch --slug <signal_slug> --weeks 12` and pass the normalized \
result as the `signal` field of the synthesize payload.
3. Generate the team-pulse digest with generate_team_pulse.py.
4. Run `biweekly_sweep.py --finalize`. This step is REQUIRED — without it the \
status file reports zero work and /open-day will falsely claim the sweep is overdue.

Apply the sensitive-content rules in the skill. Do not push anything to git. \
When finished, print a one-line summary: how many profiles were synthesized and \
whether the team-pulse digest was written."""


def log(cache_dir, message):
    """Append a timestamped line to the cron log and echo it to stdout.

    The file append is BEST-EFFORT and must never raise. `log()` is called from error
    handlers — including the one guarding transcript writing — so an OSError escaping here
    propagates out of run_claude() and main() never gets to record the sweep failure. A full
    or read-only cache dir would therefore turn a recorded failure into a bare traceback with
    no status file: the exact silent-failure class this module exists to prevent, triggered by
    the logging of it.

    stdout is unconditional and comes first, so the message still reaches launchd.log via
    StandardOutPath even when the cron log cannot be written.
    """
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with (cache_dir / LOG_NAME).open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        # Announce the degradation on stdout rather than swallowing it — a silently
        # unwritable log is how you end up trusting an empty log later.
        print(f"[{stamp}] WARN: could not append to {LOG_NAME}: {exc}", flush=True)


def record_failure(cache_dir, sweep_date, error):
    """Write a failure into last-sweep-status.json so /open-day surfaces it.

    Never clobbers a good record with a worse one: if the file on disk already
    describes a finalized, complete sweep for a LATER date, leave it alone.
    """
    path = cache_dir / "last-sweep-status.json"
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    if existing.get("finalized") and existing.get("complete"):
        prior = str(existing.get("sweep_date", ""))[:10]
        if prior > str(sweep_date):
            return

    # Recording the failure must not itself raise. main() calls this on the way to returning
    # a non-zero exit code; a traceback here loses both the status record AND the exit code,
    # so the scheduler would report nothing at all.
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "sweep_date": str(sweep_date),
                    "exit_code": 1,
                    "error": error,
                    "relationships_processed": 0,
                    "complete": False,
                    "finalized": True,
                    "source": "scheduled_sweep",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        # Loud on stderr: launchd captures it, and an unrecordable failure is worse than the
        # failure it was trying to record — the next run has no idea a sweep was attempted.
        print(
            f"FATAL: could not write {path} to record the sweep failure ({exc}). "
            "The freshness gate will see no failure record and may treat the cycle as fresh.",
            file=sys.stderr,
        )


def sweep_finalized_for(cache_dir, sweep_date):
    """True if last-sweep-status.json shows a finalized, complete run for today."""
    path = cache_dir / "last-sweep-status.json"
    if not path.exists():
        return False
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return (
        str(status.get("sweep_date", ""))[:10] == str(sweep_date)
        and bool(status.get("finalized"))
        and bool(status.get("complete"))
    )


def allowed_tools(interpreter):
    """Scope the headless session to what the sweep actually needs.

    Deliberately NOT --dangerously-skip-permissions: an unattended run with a
    blank cheque is how a scheduled job quietly does something nobody asked for.
    """
    exe = Path(interpreter).name
    return [
        f"Bash({exe} *)",
        "Read",
        "Write",
        "Edit",
        "Glob",
        "Grep",
        "Skill",
    ]



# stderr lines that always appear and never mean anything, annotated inline so a post-mortem
# does not chase them. The connectors warning cost real diagnostic time on 2026-08-23.
_BENIGN_STDERR = (
    (
        "connectors are disabled",
        "  [BENIGN: expected. ANTHROPIC_API_KEY in the toolkit .env is what makes this run "
        "self-contained, and it takes precedence over the claude.ai login. The sweep's "
        "--allowedTools carries no MCP tools and its scripts call Fathom/Airtable REST "
        "directly, so connectors are irrelevant here. NOT a cause of failure.]",
    ),
)


def _benign_note(line):
    for needle, note in _BENIGN_STDERR:
        if needle in line:
            return note
    return ""



def _as_text(raw):
    """TimeoutExpired.stdout/.stderr are str under text=True and bytes otherwise."""
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw


def _write_transcript(cache_dir, exit_code, stdout, stderr):
    """Persist the FULL claude output. The 5-line cron-log tails cannot diagnose anything.

    The 2026-08-23 failure left exactly three lines ("Request timed out", a connectors
    warning, "exited 1") to explain 12m35s of work, and reconstructing what the run had
    actually completed was impossible.
    """
    # Microseconds, not just seconds: a manually forced run overlapping the scheduled one —
    # or a retry inside the same second — otherwise overwrites the earlier run's transcript,
    # destroying exactly the diagnostic evidence this function exists to preserve.
    transcript = cache_dir / f"claude-run-{datetime.now(timezone.utc):%Y%m%d-%H%M%S-%f}.log"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        transcript.write_text(
            f"# exit={exit_code}\n\n===== STDOUT =====\n{stdout or ''}\n"
            f"\n===== STDERR =====\n{stderr or ''}\n",
            encoding="utf-8",
        )
        log(cache_dir, f"Full claude transcript: {transcript}")
    except OSError as exc:
        log(cache_dir, f"WARN: could not write the claude transcript: {exc}")


def run_claude(cache_dir, interpreter, dry_run):
    cmd = [
        "claude",
        "-p",
        SWEEP_PROMPT,
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        *allowed_tools(interpreter),
    ]
    if dry_run:
        log(cache_dir, f"DRY-RUN: would exec: {' '.join(cmd[:2])} <prompt> {' '.join(cmd[3:])}")
        return 0

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        log(cache_dir, "FAIL: `claude` not found on PATH for the scheduler's environment.")
        return 127
    except subprocess.TimeoutExpired as exc:
        log(cache_dir, f"FAIL: claude -p exceeded {CLAUDE_TIMEOUT_SECONDS}s and was killed.")
        # A wedged run is the case that needs a transcript MOST — it is the only evidence of
        # how far the sweep got before it hung — and it used to be the one case that returned
        # before writing one. TimeoutExpired carries whatever was captured before the kill;
        # with text=True those are str, but normalise defensively since they are bytes when a
        # caller omits it.
        _write_transcript(cache_dir, 124, _as_text(exc.stdout), _as_text(exc.stderr))
        return 124

    _write_transcript(cache_dir, proc.returncode, proc.stdout, proc.stderr)

    tail = (proc.stdout or "").strip().splitlines()[-5:]
    for line in tail:
        log(cache_dir, f"claude: {line}")
    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()[-5:]
        for line in err:
            log(cache_dir, f"claude stderr: {line}{_benign_note(line)}")
    return proc.returncode


def run_finalize(cache_dir, interpreter, sweep_date, dry_run):
    # --cache-dir must be forwarded: without it the subprocess finalizes the
    # DEFAULT cache while we go on to read cache_dir, see no finalized status,
    # and report a successful run as a failure.
    cmd = [
        interpreter,
        str(SCRIPT_DIR / "biweekly_sweep.py"),
        "--finalize",
        "--cache-dir",
        str(cache_dir),
        "--sweep-date",
        str(sweep_date),
    ]
    if dry_run:
        log(cache_dir, f"DRY-RUN: would exec: {' '.join(cmd)}")
        return 0
    proc = subprocess.run(cmd, capture_output=True, text=True)
    for line in (proc.stdout or "").strip().splitlines()[-5:]:
        log(cache_dir, f"finalize: {line}")
    return proc.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval-days", type=int, default=DEFAULT_INTERVAL_DAYS)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--force", action="store_true", help="Sweep regardless of the freshness gate."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Log what would run; execute nothing."
    )
    parser.add_argument(
        "--interpreter",
        default=sys.executable,
        help="Python used for sub-scripts (default: the running interpreter).",
    )
    args = parser.parse_args()

    cache_dir = args.cache_dir
    today = date.today()
    status_path = cache_dir / "last-sweep-status.json"

    if args.force:
        code, reason = DUE, "DUE: --force."
    else:
        code, reason = decide(status_path, args.interval_days, today)
    log(cache_dir, reason)

    if code == FRESH:
        return 0

    if code == ERROR:
        record_failure(cache_dir, today, reason)
        return 2

    if code == NEEDS_FINALIZE:
        try:
            prior = json.loads(status_path.read_text(encoding="utf-8"))
            target = str(prior.get("sweep_date", today))[:10]
        except (json.JSONDecodeError, OSError):
            target = str(today)
        rc = run_finalize(cache_dir, args.interpreter, target, args.dry_run)
        log(cache_dir, f"finalize-only run exited {rc}.")
        return rc

    # DUE
    log(cache_dir, "Starting headless sweep via `claude -p`.")
    rc = run_claude(cache_dir, args.interpreter, args.dry_run)
    if args.dry_run:
        return 0

    if rc != 0:
        record_failure(cache_dir, today, f"claude -p exited {rc}")
        log(cache_dir, f"FAIL: sweep exited {rc}; recorded in last-sweep-status.json.")
        return rc

    # A zero exit is not proof of work. Verify the pipeline actually finalized;
    # this is the check that would have caught the "reports 0 relationships"
    # class of bug instead of letting it sit for three days.
    if not sweep_finalized_for(cache_dir, today):
        log(cache_dir, "claude -p exited 0 but no finalized status for today — finalizing now.")
        run_finalize(cache_dir, args.interpreter, today, dry_run=False)

    if sweep_finalized_for(cache_dir, today):
        log(cache_dir, "OK: sweep complete and finalized.")
        return 0

    record_failure(cache_dir, today, "sweep ran but never finalized")
    log(cache_dir, "FAIL: sweep ran but never finalized; recorded for /open-day.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
