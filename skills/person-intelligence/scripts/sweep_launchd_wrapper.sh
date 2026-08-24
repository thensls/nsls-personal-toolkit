#!/bin/bash
# sweep_launchd_wrapper.sh — the pre-Python guard for the scheduled sweep.
#
# WHY THIS EXISTS
#
# scheduled_sweep.py writes timestamped lines to sweep-cron.log and records failures into
# last-sweep-status.json, so anything that goes wrong *inside* it is visible. Anything that
# kills the job BEFORE Python starts was completely invisible:
#
#   - launchd appends raw child stderr to StandardErrorPath with NO timestamp
#   - nothing reaches sweep-cron.log
#   - nothing is written to last-sweep-status.json
#   - so /open-day and /open-week see no failure and no staleness signal
#
# On 2026-08-09 and 2026-08-16 the plist pointed at a scheduled_sweep.py that had not shipped
# yet — the plist was deployed ahead of the script (the script landed 2026-08-21). Both Sundays
# died instantly with a bare, undated "can't open file ...: [Errno 2] No such file or directory"
# in launchd.log. sweep-cron.log showed a clean 21-day gap with no explanation, and the
# relationship roster went 30 days stale against a 12-day cadence while every dashboard
# reported healthy.
#
# The general lesson is not "that one path was wrong" — it is that the plist and the script are
# deployed independently, so the window where one exists without the other is permanent and
# recurs on every install, reinstall, branch switch, or partial pull.
#
# This wrapper closes that window: it validates its own preconditions, timestamps everything,
# brackets the child's (undated) output with dated banners so a post-mortem can place it in
# time, and writes a real failure record when it cannot even start Python.
#
# Usage (from the plist):  /bin/bash <this script> [extra args forwarded to scheduled_sweep.py]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SWEEP_PY="${SCRIPT_DIR}/scheduled_sweep.py"
CACHE_DIR="${PI_CACHE_DIR:-${HOME}/.cache/person-intelligence}"
CRON_LOG="${CACHE_DIR}/sweep-cron.log"
STATUS_FILE="${CACHE_DIR}/last-sweep-status.json"

mkdir -p "${CACHE_DIR}" 2>/dev/null || true

stamp() { date -u +"%Y-%m-%dT%H:%M:%S+00:00"; }

log() {
  local line="[$(stamp)] wrapper: $1"
  echo "${line}"
  echo "${line}" >>"${CRON_LOG}" 2>/dev/null || true
}

# Write a failure into last-sweep-status.json so the weekly skills surface it.
#
# Unlike scheduled_sweep.record_failure this does NOT protect an existing good record. That is
# deliberate: we only get here when the sweep cannot start at all, so nothing is sweeping and a
# stale success record is actively misleading. `source` names the writer so a post-mortem can
# tell a pre-Python failure from an in-Python one. sweep_due.py reads exit_code/error and
# returns DUE for any failure record, so this retries on the next firing instead of parking.
record_failure() {
  local reason="$1"
  local py=""
  for cand in python3.12 python3 python; do
    if command -v "${cand}" >/dev/null 2>&1; then py="${cand}"; break; fi
  done

  if [ -n "${py}" ]; then
    PI_REASON="${reason}" PI_STATUS_FILE="${STATUS_FILE}" "${py}" - <<'PY' 2>/dev/null && return 0
import json, os
from datetime import date, datetime, timezone
json.dump(
    {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sweep_date": str(date.today()),
        "exit_code": 1,
        "error": os.environ["PI_REASON"],
        "relationships_processed": 0,
        "complete": False,
        "finalized": True,
        "source": "sweep_launchd_wrapper",
    },
    open(os.environ["PI_STATUS_FILE"], "w"),
    indent=2,
)
open(os.environ["PI_STATUS_FILE"], "a").write("\n")
PY
  fi

  # No usable interpreter at all — the emergency path. Hand-rolled JSON so the failure is
  # still visible to every reader of the status file.
  #
  # `reason` embeds ${PATH} and filesystem paths, so it can carry a backslash or a double
  # quote. Interpolating it raw produced invalid JSON, which made sweep_due.py return ERROR
  # instead of recognising a failure and retrying it — i.e. the unescaped string could defeat
  # the very retry this record exists to trigger. Escape backslashes first, then quotes.
  json_reason="${reason//\\/\\\\}"
  json_reason="${json_reason//\"/\\\"}"
  cat >"${STATUS_FILE}" <<EOF
{
  "timestamp": "$(stamp)",
  "sweep_date": "$(date -u +%Y-%m-%d)",
  "exit_code": 1,
  "error": "${json_reason}",
  "relationships_processed": 0,
  "complete": false,
  "finalized": true,
  "source": "sweep_launchd_wrapper_no_python"
}
EOF
}

fail() {
  log "FAIL (pre-Python): $1"
  record_failure "$1"
  log "Recorded the failure in last-sweep-status.json — sweep_due.py will return DUE and retry."
  exit 1
}

# Keep the banner short — this runs weekly forever. The full PATH is only interesting when a
# binary is missing, and the failure messages below carry it then.
log "BEGIN scheduled sweep."

# --- preconditions -----------------------------------------------------------------------

if [ ! -f "${SWEEP_PY}" ]; then
  fail "scheduled_sweep.py not found at ${SWEEP_PY} — the plist and the script are deployed separately; one of them is out of date (bad install, partial pull, or branch switch)."
fi

# The pipeline needs 3.12 specifically, and not merely for syntax: scheduled_sweep.py derives
# the headless tool allowlist from the interpreter's FILE NAME (`Bash(<name> *)`), while the
# sweep prompt and the skill instruct the agent to invoke `python3.12`. Hand it a binary called
# `python3` and every Bash call the agent makes is DENIED by the allowlist — the sweep starts,
# burns a run, and produces nothing. So accept `python3.12` by name, or a `python3` that
# self-reports >= 3.12; never a bare unknown-version `python3`.
PY_BIN=""
if command -v python3.12 >/dev/null 2>&1; then
  PY_BIN="$(command -v python3.12)"
elif command -v python3 >/dev/null 2>&1 \
  && python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)' 2>/dev/null; then
  PY_BIN="$(command -v python3)"
  log "WARN: no python3.12 on PATH; using ${PY_BIN} which reports $(python3 -V 2>&1). The headless allowlist is derived from this binary's name, so verify the sweep's Bash calls are not denied."
fi
[ -n "${PY_BIN}" ] || fail "no python3.12 (and no python3 >= 3.12) on PATH (${PATH}) — launchd starts with a minimal PATH."

command -v claude >/dev/null 2>&1 \
  || log "WARN: \`claude\` is not on PATH (${PATH}). scheduled_sweep.py will record a 127 failure."

log "Preconditions OK. python=${PY_BIN}, script=${SWEEP_PY}"

# --- run ---------------------------------------------------------------------------------
#
# The child's own lines are already timestamped by scheduled_sweep.log(). Anything it does NOT
# control (a Python traceback, launchd noise) lands undated — the dated BEGIN/END banners here
# are what let a post-mortem place those lines in time.

# Forward the cache dir to the child when PI_CACHE_DIR is set. Without this the wrapper logged
# to the override while scheduled_sweep.py kept writing to its own default — so a "safely
# isolated" test run silently wrote into the real sweep-cron.log and status file. Only pass the
# flag when the caller actually overrode it, so the production path keeps the child's default.
CHILD_ARGS=()
if [ -n "${PI_CACHE_DIR:-}" ]; then
  CHILD_ARGS+=(--cache-dir "${CACHE_DIR}")
  log "PI_CACHE_DIR set — forwarding --cache-dir ${CACHE_DIR} to the child."
fi

log "--- child output begins ---"
"${PY_BIN}" "${SWEEP_PY}" "${CHILD_ARGS[@]+"${CHILD_ARGS[@]}"}" "$@"
rc=$?
log "--- child output ends (exit ${rc}) ---"

if [ "${rc}" -ne 0 ]; then
  log "scheduled_sweep.py exited ${rc}. It records its own failures; check last-sweep-status.json."
else
  log "END scheduled sweep, exit 0."
fi

exit "${rc}"
