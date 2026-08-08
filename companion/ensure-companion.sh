#!/usr/bin/env bash
# ensure-companion.sh — resolve the toolkit-companion binary, building it on
# first use when the source is present but the venv was never created.
#
# Why this exists. Installing the companion is an *optional, interactive* step
# in install.sh / install.ps1 ("Install the web companion? [Y/n]"). Three common
# paths leave a builder with companion/ source but no .venv and no binary:
#   - they installed the toolkit before the companion shipped,
#   - the installer ran non-interactively (piped to bash, or driven by Claude,
#     which cannot answer a prompt), so the question was never answered,
#   - they answered "n" once, months ago.
# Every skill that looks for the binary then falls back to chat *silently and
# permanently* — no signal that a single install would fix it. This script
# closes that gap: if the source is here, make the binary.
#
# Contract:
#   stdout   absolute path to a working toolkit-companion binary, and exit 0.
#            EMPTY on every failure — callers just test for empty.
#   stderr   one line explaining why it could not be provisioned.
#   log      companion/.install.log — full output of a build attempt.
#
# Fast path: when the binary already resolves, this touches no network and
# spawns no Python. It costs one stat per candidate path.
#
# Usage:
#   TC="$(bash "$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh")"
#   [ -n "$TC" ] || : # companion unavailable — fall back to chat
#
#   --force   ignore the post-failure cooldown and retry the build now
#
# Exit codes (all non-zero mean "fall back to chat"; they exist for debugging):
#   0 ok   1 build failed   2 no Python >=3.10   3 no source   4 cooldown active
#
# Kept POSIX-ish and array-free on purpose: this has to run under Git Bash on
# Windows and under macOS's bash 3.2.

set -u

PLUGIN_DIR="${NSLS_TOOLKIT_DIR:-$HOME/.claude/local-plugins/nsls-personal-toolkit}"
COMPANION_DIR="$PLUGIN_DIR/companion"
VENV="$COMPANION_DIR/.venv"
LOG="$COMPANION_DIR/.install.log"
FAIL_STAMP="$COMPANION_DIR/.install-failed"
LOCK="$COMPANION_DIR/.install.lock"

# Don't re-attempt a failing build every single morning — a broken toolchain
# would add a minute to each open-day forever. The log says what went wrong,
# and --force retries on demand.
COOLDOWN_MIN=1440   # 24h
STEP_TIMEOUT=300    # per build step, so a wedged download can't stall a morning
LOCK_STALE_MIN=10

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

fail() {
  printf 'ensure-companion: %s\n' "$1" >&2
  exit "$2"
}

# Print the binary path and return 0, or return 1 if none of the three
# locations has one. Mirrors what the skills used to inline.
resolve() {
  if [ -x "$VENV/bin/toolkit-companion" ]; then                 # macOS / Linux
    printf '%s\n' "$VENV/bin/toolkit-companion"; return 0
  fi
  if [ -x "$VENV/Scripts/toolkit-companion.exe" ]; then          # Windows
    printf '%s\n' "$VENV/Scripts/toolkit-companion.exe"; return 0
  fi
  _onpath="$(command -v toolkit-companion 2>/dev/null)"
  if [ -n "$_onpath" ]; then
    printf '%s\n' "$_onpath"; return 0
  fi
  return 1
}

# --- fast path: already installed -------------------------------------------
if TC="$(resolve)"; then
  printf '%s\n' "$TC"
  exit 0
fi

# --- is the source even here? ------------------------------------------------
# No pyproject.toml means the toolkit isn't installed at all. That is the
# genuine "nothing to do" case the skills should skip on.
[ -f "$COMPANION_DIR/pyproject.toml" ] ||
  fail "no companion source at $COMPANION_DIR — personal toolkit not installed" 3

# Is a file newer than N minutes? (find -mmin is portable; -newermt is not.)
fresher_than() { # $1=path  $2=minutes
  [ -e "$1" ] || return 1
  [ -n "$(find "$(dirname "$1")" -maxdepth 1 -name "$(basename "$1")" \
            -mmin "-$2" 2>/dev/null)" ]
}

if [ "$FORCE" -eq 0 ] && fresher_than "$FAIL_STAMP" "$COOLDOWN_MIN"; then
  fail "a recent build attempt failed; see $LOG (retry: ensure-companion.sh --force)" 4
fi

# --- find a usable interpreter ----------------------------------------------
# Also rejects the Windows Store python stub, which exists on PATH but exits
# non-zero when actually run.
PY_BIN=""
PY_ARG=""
for cand in python3 python py; do
  command -v "$cand" >/dev/null 2>&1 || continue
  if [ "$cand" = py ]; then try_arg="-3"; else try_arg=""; fi
  if [ -n "$try_arg" ]; then
    "$cand" "$try_arg" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1 || continue
  else
    "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1 || continue
  fi
  PY_BIN="$cand"; PY_ARG="$try_arg"; break
done
[ -n "$PY_BIN" ] ||
  fail "no Python >=3.10 on PATH (tried python3, python, py -3) — install Python, then re-run" 2

TIMEOUT_BIN="$(command -v timeout 2>/dev/null || true)"

log_line() { printf '%s\n' "$1" >>"$LOG"; }

# Run a build step: echo it to the log, bound it with `timeout` when available.
run_step() {
  log_line ""
  log_line "\$ $*"
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" "$STEP_TIMEOUT" "$@" >>"$LOG" 2>&1
  else
    "$@" >>"$LOG" 2>&1
  fi
}

py_run() {
  if [ -n "$PY_ARG" ]; then run_step "$PY_BIN" "$PY_ARG" "$@"
  else run_step "$PY_BIN" "$@"
  fi
}

# --- lock, so two skills starting at once can't race on one venv ------------
acquire_lock() {
  i=0
  while [ "$i" -lt 30 ]; do
    mkdir "$LOCK" 2>/dev/null && return 0
    # Another run may have finished the build while we waited — use its result.
    if TC="$(resolve)"; then printf '%s\n' "$TC"; exit 0; fi
    # Lock left behind by a killed run: take it over.
    fresher_than "$LOCK" "$LOCK_STALE_MIN" || rm -rf "$LOCK" 2>/dev/null
    sleep 2
    i=$((i + 1))
  done
  return 1
}

acquire_lock || fail "another build is holding $LOCK — try again shortly" 1
trap 'rm -rf "$LOCK" 2>/dev/null' EXIT INT TERM

: >"$LOG" 2>/dev/null || LOG=/dev/null
log_line "ensure-companion: building the companion (first use on this machine)"
log_line "python: $PY_BIN $PY_ARG"

# --- build -------------------------------------------------------------------
# Reuse an existing venv if it has an interpreter; only its console script is
# missing (an interrupted install), so re-running the editable install is enough.
VENV_PY="$VENV/bin/python"
[ -x "$VENV_PY" ] || VENV_PY="$VENV/Scripts/python.exe"

if [ ! -x "$VENV_PY" ]; then
  py_run -m venv "$VENV" || {
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "could not create the venv at $VENV — see $LOG (on Debian/Ubuntu: apt install python3-venv)" 1
  }
  VENV_PY="$VENV/bin/python"
  [ -x "$VENV_PY" ] || VENV_PY="$VENV/Scripts/python.exe"
fi
[ -x "$VENV_PY" ] || {
  printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
  fail "venv at $VENV has no interpreter — see $LOG" 1
}

# Python 3.10 ships pip 21.2, which predates PEP 660 and cannot do an editable
# install of a pyproject-only project. Upgrade first, but don't hard-fail on it:
# a newer pip may already be present and the network may be offline.
run_step "$VENV_PY" -m pip install --upgrade pip -q || \
  log_line "(pip self-upgrade failed — continuing with the bundled pip)"

# `cd` matters: pyproject.toml sets package-dir = {"" = ".."}, so the editable
# install must run from companion/, exactly as the installers do.
( cd "$COMPANION_DIR" && run_step "$VENV_PY" -m pip install -e . -q ) || {
  printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
  fail "editable install failed — see $LOG" 1
}

# --- verify ------------------------------------------------------------------
if TC="$(resolve)"; then
  rm -f "$FAIL_STAMP" 2>/dev/null
  log_line ""
  log_line "ok: $TC"
  printf '%s\n' "$TC"
  exit 0
fi

printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
fail "install reported success but no binary appeared under $VENV — see $LOG" 1
