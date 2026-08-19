#!/usr/bin/env bash
# ensure-companion.sh — resolve the toolkit-companion binary, building it on
# first use when the source is present but the venv was never created — and,
# when the machine has no usable Python at all, provisioning a private one.
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
# Python. The build needs CPython >=3.10, but a stock Mac ships only Apple's
# /usr/bin/python3 (3.9), and telling a non-technical staffer to go install
# Python is where the companion used to die. So this script (a) looks beyond
# PATH — Homebrew, python.org framework installs, pyenv, the Windows
# launcher — and (b) when there is truly none, downloads a private,
# checksum-pinned CPython runtime into companion/.python-runtime/ and builds
# with that. User-space only: no admin password, nothing system-wide is
# upgraded, replaced, or put on PATH. The runtime belongs to the toolkit.
#
# Contract:
#   stdout   absolute path to a working toolkit-companion binary, and exit 0.
#            EMPTY on every failure — callers just test for empty.
#            (--check mode instead prints one status token; see below.)
#   stderr   one line explaining why it could not be provisioned, plus
#            progress notes during a runtime download.
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
#   --check   dry-run: print what a real run would do, and exit 0.
#             ready        binary resolves now; a real run is instant
#             build        venv build needed (~30s)
#             build-python no Python >=3.10 anywhere — a real run downloads the
#                          private runtime first (~25–45 MB by platform, more
#                          on Linux; one-time, 2–5 min)
#             no-python    no Python and provisioning is impossible here
#                          (downloads disabled, or unsupported platform)
#             no-source    toolkit source missing — nothing can be built
#             cooldown     a recent attempt failed; a real run would refuse
#             Callers use this to warn the user about the wait BEFORE the
#             long call — never make someone sit through an unannounced
#             multi-minute build.
#
# Env:
#   NSLS_TOOLKIT_DIR                  override the plugin dir (tests/fixtures)
#   NSLS_COMPANION_NO_DOWNLOAD=1      never download a runtime; behave like the
#                                     old "no Python — install it" failure
#   NSLS_COMPANION_FORCE_PROVISION=1  skip discovery and use the private
#                                     runtime, provisioning it if needed
#                                     (support/debug knob)
#   NSLS_COMPANION_LOCAL_ONLY=1       resolve only this checkout's venv — never
#                                     accept a toolkit-companion found on PATH
#                                     (installers set this so a stale or
#                                     unrelated global binary can't masquerade
#                                     as a fresh local build)
#
# Exit codes (all non-zero mean "fall back to chat"; they exist for debugging):
#   0 ok   1 build failed   2 no Python (and provisioning unavailable)
#   3 no source   4 cooldown active   5 runtime download/verify failed
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
RUNTIME_DIR="$COMPANION_DIR/.python-runtime"

# The private runtime: CPython "install_only" builds from
# https://github.com/astral-sh/python-build-standalone (the same prebuilt
# CPython that uv ships). Pinned by release tag + per-platform sha256 so every
# machine gets byte-identical, verified bits. Bump the tag, version, and ALL
# six checksums together (grep the release's SHA256SUMS file).
PBS_RELEASE="20260814"
PBS_PYVER="3.13.15"

# Don't re-attempt a failing build every single morning — a broken toolchain
# would add a minute to each open-day forever. The log says what went wrong,
# and --force retries on demand.
COOLDOWN_MIN=1440   # 24h
STEP_TIMEOUT=300    # per build step, so a wedged download can't stall a morning
DL_TIMEOUT=300      # curl bound for the runtime download (~25–45 MB), across
                    # ALL retries (--max-time per attempt + --retry-max-time
                    # overall), so a slow link can't hold the lock forever
# Stale-lock takeover must exceed a provision's honest worst case (download
# bounded at DL_TIMEOUT + extract + two pip steps), or a slow-but-live build
# gets its lock stolen and raced. Ownership is checked on release either way.
LOCK_STALE_MIN=45

FORCE=0
CHECK=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --check) CHECK=1 ;;
  esac
done

fail() {
  printf 'ensure-companion: %s\n' "$1" >&2
  exit "$2"
}

# Progress note: stderr for the calling agent, log for post-mortems.
note() {
  printf 'ensure-companion: %s\n' "$1" >&2
  printf '%s\n' "$1" >>"$LOG" 2>/dev/null || true
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
  if [ -z "${NSLS_COMPANION_LOCAL_ONLY:-}" ]; then
    _onpath="$(command -v toolkit-companion 2>/dev/null)"
    if [ -n "$_onpath" ]; then
      printf '%s\n' "$_onpath"; return 0
    fi
  fi
  return 1
}

# --- fast path: already installed -------------------------------------------
if TC="$(resolve)"; then
  if [ "$CHECK" -eq 1 ]; then printf 'ready\n'; else printf '%s\n' "$TC"; fi
  exit 0
fi

# --- is the source even here? ------------------------------------------------
# No pyproject.toml means the toolkit isn't installed at all. That is the
# genuine "nothing to do" case the skills should skip on.
if [ ! -f "$COMPANION_DIR/pyproject.toml" ]; then
  [ "$CHECK" -eq 1 ] && { printf 'no-source\n'; exit 0; }
  fail "no companion source at $COMPANION_DIR — personal toolkit not installed" 3
fi

# Is a file newer than N minutes? (find -mmin is portable; -newermt is not.)
fresher_than() { # $1=path  $2=minutes
  [ -e "$1" ] || return 1
  [ -n "$(find "$(dirname "$1")" -maxdepth 1 -name "$(basename "$1")" \
            -mmin "-$2" 2>/dev/null)" ]
}

if [ "$FORCE" -eq 0 ] && fresher_than "$FAIL_STAMP" "$COOLDOWN_MIN"; then
  [ "$CHECK" -eq 1 ] && { printf 'cooldown\n'; exit 0; }
  fail "a recent build attempt failed; see $LOG (retry: ensure-companion.sh --force)" 4
fi

# --- find a usable interpreter ----------------------------------------------
# Order: PATH (fast, honors the user's own setup) → the toolkit's private
# runtime from an earlier provision → well-known install homes that are often
# NOT on PATH in a fresh non-login shell (Homebrew, python.org, pyenv).
# Also rejects the Windows Store python stub, which exists on PATH but exits
# non-zero when actually run.

py_ok() { # $1=interpreter  $2=extra launcher arg ("" for none)
  if [ -n "${2:-}" ]; then
    "$1" "$2" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
  else
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
  fi
}

# Print the private runtime's interpreter, if one was provisioned earlier —
# but ONLY when its provenance manifest matches the CURRENT pins. A runtime
# from an older release, or an unverified directory that merely looks like
# one, is treated as absent: bumping PBS_RELEASE/PBS_PYVER reprovisions
# instead of silently trusting old bits. The manifest is written only after
# a download passes sha256 verification and the interpreter runs.
runtime_py() {
  # 2>/dev/null FIRST: redirections apply left to right, and a missing file
  # fails at `<` — silencing stderr after that is too late.
  read -r _prov 2>/dev/null <"$RUNTIME_DIR/.provenance" || _prov=""
  case "$_prov" in
    "$PBS_RELEASE $PBS_PYVER "*) ;;
    *) return 0 ;;
  esac
  if [ -x "$RUNTIME_DIR/python/bin/python3" ]; then              # macOS / Linux
    printf '%s\n' "$RUNTIME_DIR/python/bin/python3"
  elif [ -x "$RUNTIME_DIR/python/python.exe" ]; then             # Windows
    printf '%s\n' "$RUNTIME_DIR/python/python.exe"
  fi
}

PY_BIN=""
PY_ARG=""

if [ -z "${NSLS_COMPANION_FORCE_PROVISION:-}" ]; then
  for cand in python3 python py; do
    command -v "$cand" >/dev/null 2>&1 || continue
    if [ "$cand" = py ]; then try_arg="-3"; else try_arg=""; fi
    py_ok "$cand" "$try_arg" || continue
    PY_BIN="$cand"; PY_ARG="$try_arg"; break
  done
fi

if [ -z "$PY_BIN" ]; then
  rt="$(runtime_py)"
  if [ -n "$rt" ] && py_ok "$rt" ""; then PY_BIN="$rt"; fi
fi

if [ -z "$PY_BIN" ] && [ -z "${NSLS_COMPANION_FORCE_PROVISION:-}" ]; then
  # Well-known homes. A glob that matches nothing stays literal; -x filters it.
  # $LOCALAPPDATA is Windows-style (backslashes) under Git Bash — cygpath it.
  _lad="/nonexistent"
  if [ -n "${LOCALAPPDATA:-}" ] && command -v cygpath >/dev/null 2>&1; then
    _lad="$(cygpath -u "$LOCALAPPDATA" 2>/dev/null || printf '/nonexistent')"
  fi
  for cand in \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 \
    "$HOME"/.pyenv/versions/3.*/bin/python3 \
    "$_lad"/Programs/Python/Python3*/python.exe
  do
    [ -x "$cand" ] || continue
    py_ok "$cand" "" || continue
    PY_BIN="$cand"; break
  done
fi

# --- no interpreter anywhere: plan to provision the private runtime ----------
plat_triple() {
  case "$(uname -s 2>/dev/null)" in
    Darwin)
      case "$(uname -m 2>/dev/null)" in
        arm64)   printf 'aarch64-apple-darwin\n' ;;
        x86_64)  printf 'x86_64-apple-darwin\n' ;;
      esac ;;
    Linux)
      case "$(uname -m 2>/dev/null)" in
        x86_64)  printf 'x86_64-unknown-linux-gnu\n' ;;
        aarch64) printf 'aarch64-unknown-linux-gnu\n' ;;
      esac ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
      # Git Bash (and busybox-style shells that report Windows_NT). Explicit
      # architectures only — an unknown arch falls through to empty, which the
      # caller turns into the honest "install Python yourself" message rather
      # than downloading a binary that can't run.
      case "$(uname -m 2>/dev/null)" in
        x86_64|amd64|x64) printf 'x86_64-pc-windows-msvc\n' ;;
        aarch64|arm64)    printf 'aarch64-pc-windows-msvc\n' ;;
      esac ;;
  esac
}

runtime_sha() { # sha256 of the pinned install_only tarball for $1
  case "$1" in
    aarch64-apple-darwin)      printf '7d50bb42813a5644db7c40d3ad79361d0b724bb29d25a91fab1048c2c5c6a8c5\n' ;;
    x86_64-apple-darwin)       printf '44bb8a1d97c070deb30880b2b7fe681c1e9cf727cb950709e022dc195cdfdf4f\n' ;;
    x86_64-unknown-linux-gnu)  printf '45816a2653b47a6cc48d8ada4ea1185758a4c2db389d012b31e0205e5ccb548b\n' ;;
    aarch64-unknown-linux-gnu) printf '303efcce34b86fd8b0d8a260327dbf8d0d4fba6d2d77b2bca311e8bbd19265e1\n' ;;
    x86_64-pc-windows-msvc)    printf '4ca61e4b09c2240cc50cc6910c90664051e93ab7caa2f48b3c6b3c070670c0bd\n' ;;
    aarch64-pc-windows-msvc)   printf 'b75b76d7d5ce6db7af426de8ea09d587fe6ac01d1f4238fb6fccda64bf01aee7\n' ;;
  esac
}

sha256_file() { # portable: sha256sum (Linux, Git Bash) or shasum (macOS)
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" 2>/dev/null | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" 2>/dev/null | cut -d' ' -f1
  fi
}

PLAT=""
if [ -z "$PY_BIN" ]; then
  PLAT="$(plat_triple)"
  if [ "$CHECK" -eq 1 ]; then
    if [ -n "${NSLS_COMPANION_NO_DOWNLOAD:-}" ] || [ -z "$PLAT" ]; then
      printf 'no-python\n'
    else
      printf 'build-python\n'
    fi
    exit 0
  fi
  [ -n "${NSLS_COMPANION_NO_DOWNLOAD:-}" ] &&
    fail "no Python >=3.10 found and NSLS_COMPANION_NO_DOWNLOAD is set — install Python 3.10+, then re-run" 2
  [ -n "$PLAT" ] ||
    fail "no Python >=3.10 found and no prebuilt runtime exists for this platform ($(uname -s 2>/dev/null) $(uname -m 2>/dev/null)) — install Python 3.10+, then re-run" 2
fi
[ "$CHECK" -eq 1 ] && { printf 'build\n'; exit 0; }

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
    if mkdir "$LOCK" 2>/dev/null; then
      # Record ownership: only the process that took the lock may release it,
      # so a stale-lock takeover can never cascade into two runs freeing each
      # other's locks.
      printf '%s\n' "$$" >"$LOCK/owner" 2>/dev/null || true
      return 0
    fi
    # Another run may have finished the build while we waited — use its result.
    if TC="$(resolve)"; then printf '%s\n' "$TC"; exit 0; fi
    # Lock left behind by a killed run: take it over.
    fresher_than "$LOCK" "$LOCK_STALE_MIN" || rm -rf "$LOCK" 2>/dev/null
    sleep 2
    i=$((i + 1))
  done
  return 1
}

release_lock() {
  [ "$(cat "$LOCK/owner" 2>/dev/null)" = "$$" ] && rm -rf "$LOCK" 2>/dev/null
  return 0
}

acquire_lock || fail "another build is holding $LOCK — try again shortly" 1
trap 'release_lock' EXIT INT TERM

: >"$LOG" 2>/dev/null || LOG=/dev/null
log_line "ensure-companion: building the companion (first use on this machine)"

# --- provision the private Python runtime, if this machine needs one ---------
provision_runtime() {
  # Another process may have provisioned while we waited on the lock.
  rt="$(runtime_py)"
  if [ -n "$rt" ] && py_ok "$rt" ""; then
    PY_BIN="$rt"; PY_ARG=""; return 0
  fi

  want_sha="$(runtime_sha "$PLAT")"
  url="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}/cpython-${PBS_PYVER}+${PBS_RELEASE}-${PLAT}-install_only.tar.gz"
  # $$-suffixed staging paths: even if a stale-lock takeover ever produces two
  # concurrent provisions, they cannot clobber each other's downloads.
  tarball="$COMPANION_DIR/.python-runtime.tar.gz.part.$$"

  command -v curl >/dev/null 2>&1 || {
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "curl is required to download the Python runtime and was not found" 5
  }
  command -v tar >/dev/null 2>&1 || {
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "tar is required to unpack the Python runtime and was not found" 5
  }

  note "no Python >=3.10 on this machine — downloading a private CPython $PBS_PYVER runtime for the toolkit (~25–45 MB depending on platform, one-time; user-space only, nothing system-wide is touched)"
  log_line "runtime url: $url"

  rm -f "$tarball"
  if ! curl -fsSL --retry 2 --connect-timeout 15 --max-time "$DL_TIMEOUT" \
       --retry-max-time "$DL_TIMEOUT" \
       -o "$tarball" "$url" >>"$LOG" 2>&1; then
    rm -f "$tarball"
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "could not download the Python runtime (offline? blocked network?) — the companion needs internet once for this setup; it will retry in 24h, or now with --force" 5
  fi

  got_sha="$(sha256_file "$tarball")"
  if [ -z "$got_sha" ] || [ "$got_sha" != "$want_sha" ]; then
    rm -f "$tarball"
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "runtime download failed sha256 verification (expected $want_sha, got ${got_sha:-nothing}) — refusing to install it; will retry in 24h, or now with --force" 5
  fi

  staging="$RUNTIME_DIR.tmp.$$"
  rm -rf "$staging"
  mkdir -p "$staging" || {
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "could not create the staging directory $staging — see $LOG" 5
  }
  if ! tar -xzf "$tarball" -C "$staging" >>"$LOG" 2>&1; then
    rm -rf "$staging"; rm -f "$tarball"
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "could not unpack the Python runtime — see $LOG" 5
  fi
  rm -f "$tarball"
  rm -rf "$RUNTIME_DIR"
  # Verify the old tree is actually gone (Git Bash can fail to remove an
  # in-use directory) — otherwise mv would nest the new runtime INSIDE it.
  if [ -e "$RUNTIME_DIR" ]; then
    rm -rf "$staging"
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "could not clear the old runtime at $RUNTIME_DIR (held open by another process?) — see $LOG" 5
  fi
  mv "$staging" "$RUNTIME_DIR" || {
    rm -rf "$staging"
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "could not move the Python runtime into place at $RUNTIME_DIR" 5
  }

  # Locate the interpreter directly — runtime_py requires the provenance
  # manifest, which is deliberately written LAST, only after the interpreter
  # proves it runs. A crash anywhere before that leaves no manifest, so the
  # next run reprovisions instead of trusting debris.
  rt="$RUNTIME_DIR/python/bin/python3"
  [ -x "$rt" ] || rt="$RUNTIME_DIR/python/python.exe"
  if [ ! -x "$rt" ] || ! py_ok "$rt" ""; then
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "downloaded Python runtime does not run on this machine — see $LOG" 5
  fi
  printf '%s %s %s %s\n' "$PBS_RELEASE" "$PBS_PYVER" "$PLAT" "$want_sha" >"$RUNTIME_DIR/.provenance" || {
    printf 'x\n' >"$FAIL_STAMP" 2>/dev/null
    fail "could not write the runtime provenance manifest" 5
  }
  note "private Python runtime ready at $RUNTIME_DIR"
  PY_BIN="$rt"; PY_ARG=""
}

# Only reachable with PY_BIN empty when provisioning was approved above
# (supported platform, downloads allowed) — every other empty case exited.
[ -n "$PY_BIN" ] || provision_runtime

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
