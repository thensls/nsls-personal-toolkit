#!/usr/bin/env bash
# Install the NSLS Personal Productivity Toolkit as a Claude Code local plugin.
#
# Usage (from your fork):
#   curl -fsSL https://raw.githubusercontent.com/<you>/nsls-personal-toolkit/main/install.sh | bash
#
# Or from the NSLS template (you should fork first):
#   curl -fsSL https://raw.githubusercontent.com/thensls/nsls-personal-toolkit/main/install.sh | bash

set -euo pipefail

PLUGIN_DIR="$HOME/.claude/local-plugins/nsls-personal-toolkit"

# Cross-platform Python launcher: python3 on macOS/Linux, often just `python`
# on Windows. Prefer python3, fall back to python. Use "$PY -m pip" everywhere
# instead of pip3 (which many Windows installs lack).
PY="$(command -v python3 || command -v python || true)"

# OS class for the platform-specific steps (symlink, launchd autostart).
case "$(uname -s 2>/dev/null)" in
  Darwin) OS_CLASS="macos" ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT) OS_CLASS="windows" ;;
  *) OS_CLASS="linux" ;;
esac

install_companion_launchd() {
  local plugin_dir="$HOME/.claude/local-plugins/nsls-personal-toolkit"
  local plist_dest="$HOME/Library/LaunchAgents/com.nsls.toolkit-companion.plist"

  # Prefer the companion venv's interpreter (>=3.10 by construction) — a stock
  # Mac's system 3.9 cannot parse install_helper.py's `str | None` type hints.
  local helper_py="${COMPANION_PY:-$PY}"
  if [ -z "$helper_py" ]; then
    echo "✗ No Python available for the launchd helper — skipping auto-start."
    return 1
  fi

  # Resolve vault path via Python (handles env var, builder-profile, and prompt)
  local vault_path
  vault_path=$("$helper_py" "$plugin_dir/companion/install_helper.py" resolve-vault)
  if [ -z "$vault_path" ] || [ ! -d "$vault_path/01-daily" ]; then
    echo "✗ Could not find a vault with 01-daily/ at: $vault_path"
    echo "  Set OBSIDIAN_VAULT_PATH or add the vault to builder-profile.md, then re-run install."
    return 1
  fi

  # Generate the plist via Python (handles quoting correctly)
  "$helper_py" "$plugin_dir/companion/install_helper.py" write-plist \
    --vault "$vault_path" \
    --dest "$plist_dest"

  launchctl load -w "$plist_dest"
  echo "✓ Auto-start enabled. Companion will run at login."
  echo "  Vault: $vault_path"
  echo "  To disable later: launchctl unload -w $plist_dest"
}

# Detect the repo URL from the install script URL (passed via curl | bash)
# Fall back to the NSLS template if we can't detect it
REPO_URL="${NSLS_PERSONAL_REPO:-https://github.com/thensls/nsls-personal-toolkit.git}"

echo "Installing NSLS Personal Productivity Toolkit..."
echo "  Repo: $REPO_URL"
echo ""

if [ -d "$PLUGIN_DIR" ]; then
  echo "Plugin directory already exists at $PLUGIN_DIR"
  echo "Pulling latest changes..."
  cd "$PLUGIN_DIR" && git pull --ff-only 2>/dev/null || true
else
  mkdir -p "$(dirname "$PLUGIN_DIR")"
  git clone "$REPO_URL" "$PLUGIN_DIR"
fi

# --- Enable the plugin and register the auto-update hook in settings.json ---
#
# This is what makes updates actually arrive. `hooks/hooks.json` in the plugin
# root is the documented location, but a *locally enabled* plugin (as opposed to
# a marketplace install) does not reliably load bundled hooks — notably on Claude
# Code desktop. The builder toolkit hit the same wall and solved it by merging
# into the global settings.json; do the same here and treat hooks.json as the
# secondary path.
#
# `~/.claude/local-plugins/` is not a Claude Code convention at all — it's just
# where this project keeps its checkout — so nothing loads it automatically
# unless settings.json says so.
#
# The hook is a bare `git` invocation on purpose: no python, no bash, nothing
# that Windows might lack. Pointer sync (which does need python) is registered
# separately below and is allowed to be absent.
SETTINGS="$HOME/.claude/settings.json"
_SETTINGS_REGISTERED=0
COMPANION_PY=""

# A function, not inline: on a machine with NO usable Python this step must be
# re-runnable AFTER the companion step below provisions one — its venv
# interpreter then fills in for the missing system Python.
register_settings() {
  if [ ! -f "$SETTINGS" ] || [ -z "$PY" ]; then
    echo "  Note: no settings.json (or no Python) — see README (Updates) to register the hook"
    return 0
  fi
  # Use "$PY" (python3 → python), not a hardcoded python3: on Windows Git Bash
  # python3 often doesn't exist, and the sentinel check below is OUTSIDE the
  # heredoc so a Store-stub interpreter that exits 0 having run nothing is
  # detected rather than reported as success.
  #
  # Capture via a temp file, NOT _out="$( <<heredoc )": bash 3.2 — stock macOS
  # /bin/bash, which is what the documented `curl … | bash` runs — mis-scans
  # quote characters inside a command substitution that contains a heredoc. An
  # apostrophe in a Python comment below was enough to kill the WHOLE installer
  # at parse time ("syntax error near unexpected token '('"), before a single
  # line ran. `|| true` keeps a Python failure (e.g. unparseable settings.json)
  # on the graceful "add the hook by hand" path instead of dying under set -e.
  # mktemp or nothing: a predictable /tmp fallback name would be a symlink
  # hazard. Every supported platform (macOS, Linux, Git Bash) ships mktemp.
  _settings_tmp="$(mktemp 2>/dev/null || true)"
  if [ -z "$_settings_tmp" ]; then
    echo "  Note: could not update settings.json (mktemp unavailable) — see README (Updates) to add the hook by hand"
    return 0
  fi
  PLUGIN_DIR="$PLUGIN_DIR" PY_BIN="$PY" "$PY" - >"$_settings_tmp" 2>/dev/null <<'PYEOF' || true
import json, os
from pathlib import Path

plugin_dir = os.environ["PLUGIN_DIR"]
py_bin = os.environ["PY_BIN"]
path = Path(os.path.expanduser("~/.claude/settings.json"))

# utf-8-sig: an older PowerShell installer may have left a BOM, which plain
# utf-8 would choke on.
with open(path, encoding="utf-8-sig") as f:
    cfg = json.load(f)

cfg.setdefault("enabledPlugins", {})["nsls-personal-toolkit@local"] = True

# Absolute interpreter path, so the entry can't be broken later by PATH order.
PULL_CMD = f'git -C "{plugin_dir}" pull --ff-only --quiet'
SYNC_CMD = f'"{py_bin}" "{plugin_dir}/hooks/session-start.py" --no-pull'
PULL_MARKER = f'{plugin_dir}" pull'
SYNC_MARKER = "nsls-personal-toolkit/hooks/session-start.py"

hooks = cfg.setdefault("hooks", {})
session_start = hooks.setdefault("SessionStart", [])

# Idempotency is checked across EVERY entry, and we only ever append our own
# entry. Two rules learned the hard way:
#   - never mutate or filter another entry: the builder toolkit registers its
#     SessionStart hook in this same array, and dropping it would kill its
#     auto-update, pointer sync and tracker ping.
#   - never append into someone else's entry either, or the Windows installer
#     (which matches on entry contents) can't tell ours from theirs.
def already(marker):
    return any(marker in h.get("command", "")
               for e in session_start if isinstance(e, dict)
               for h in e.get("hooks", []) if isinstance(h, dict))

new_hooks = []
if not already(PULL_MARKER):
    new_hooks.append({"type": "command", "command": PULL_CMD, "timeout": 20,
                      "statusMessage": "Updating personal toolkit..."})
if not already(SYNC_MARKER):
    new_hooks.append({"type": "command", "command": SYNC_CMD, "timeout": 20})

if new_hooks:
    # "startup|resume" — a resumed session must update too; startup-only leaves
    # long-lived sessions frozen.
    session_start.append({"matcher": "startup|resume", "hooks": new_hooks})

with open(path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)

chk = json.load(open(path, encoding="utf-8-sig"))
if chk.get("enabledPlugins", {}).get("nsls-personal-toolkit@local"):
    print(f"NSLS_SETTINGS_OK Enabled plugin + registered {len(new_hooks)} auto-update hook(s).")
PYEOF
  _settings_out="$(cat "$_settings_tmp" 2>/dev/null || true)"
  rm -f "$_settings_tmp"
  case "$_settings_out" in
    *NSLS_SETTINGS_OK*)
      _SETTINGS_REGISTERED=1
      echo "  ${_settings_out#*NSLS_SETTINGS_OK }" ;;
    *) echo "  Note: could not update settings.json — see README (Updates) to add the hook by hand" ;;
  esac
}
register_settings

# Fire an install event to the Automation Tracker (best-effort, never blocks).
# Tracks personal-toolkit installs and auto-registers brand-new builders
# server-side. install_source must be exactly "personal-toolkit" — the server
# maps it to the Personal Toolkit Installed checkbox + its one-time credit.
# Until the tracker's POST /install-event endpoint ships this 404s, harmlessly.
fire_install_event() {
  local tracker_url="https://web-production-6281e.up.railway.app/install-event"
  local email platform gh_user
  # Email precedence (matches the tracker hooks): toolkit .env → git → fallback
  email="$(grep -E '^BUILDER_EMAIL=' "$PLUGIN_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)"
  [ -n "$email" ] || email="$(git config user.email 2>/dev/null || true)"
  [ -n "$email" ] || email="${USER:-unknown}@$(hostname -s 2>/dev/null || echo unknown)"
  gh_user="$(gh api user --jq .login 2>/dev/null || true)"
  case "$OS_CLASS" in
    macos) platform="mac" ;;
    windows) platform="windows" ;;
    *) platform="linux" ;;
  esac
  curl -s --max-time 10 -X POST "$tracker_url" \
    -H "Content-Type: application/json" \
    -d "{\"builder_email\":\"$email\",\"github_username\":\"$gh_user\",\"platform\":\"$platform\",\"install_source\":\"personal-toolkit\"}" \
    >/dev/null 2>&1 || true
}
fire_install_event || true

echo ""
echo "Done! Personal productivity skills installed."
echo ""
echo "Skills available:"
echo "  /open-day      — Morning planning"
echo "  /close-day     — End-of-day summary"
echo "  /close-week    — Friday weekly review"
echo "  /log           — Log session progress"
echo "  /familiar      — Recall screen activity"
echo "  /person-intelligence — Relationship profiles"
echo "  obsidian-setup — Set up Obsidian knowledge base"
echo ""
echo "Next: Open Claude Code and say /personal-setup to connect your accounts."
echo ""
echo "These are YOUR skills. Edit anything in:"
echo "  $PLUGIN_DIR/skills/<name>/SKILL.md"
echo ""

# Optional: install web companion
#
# NEVER `read` from stdin here. The documented install path is `curl … | bash`,
# which makes stdin the *script itself* — a bare `read` then swallows the next
# lines of this file as the "answer", mangling the control flow that follows
# (observed: it ate the `if` below and died with a syntax error, after "Done!"
# had already printed). That is how builders ended up with companion/ source,
# no .venv, and an install that looked like it succeeded — every later /open-day
# silently fell back to chat.
#
# So: ask on the terminal directly when there is one, and when there's no
# terminal at all (CI, an agent driving the installer) install without asking,
# because every day skill expects the companion to exist.
# NSLS_SKIP_COMPANION=1 is the explicit opt-out.
if [ -n "${NSLS_SKIP_COMPANION:-}" ]; then
  yn="n"
  echo "NSLS_SKIP_COMPANION set — skipping the web companion."
elif [ -t 0 ]; then
  read -p "Install the web companion (browser-based UI)? [Y/n] " yn || yn="y"
elif { : </dev/tty; } 2>/dev/null; then
  # Piped install, but the user's terminal is still reachable — prompt there.
  # (Test by *opening* /dev/tty, not `[ -r /dev/tty ]`: the node can exist and
  # pass -r in a container while opening it fails with ENXIO.)
  read -p "Install the web companion (browser-based UI)? [Y/n] " yn </dev/tty || yn="y"
else
  yn="y"
  echo "No terminal detected — installing the web companion (set NSLS_SKIP_COMPANION=1 to skip)."
fi
if [[ "${yn:-y}" =~ ^[Yy] ]]; then
  # Delegate to the same resolver every day-skill uses. It finds a usable
  # Python beyond PATH (Homebrew, python.org framework, pyenv, the Windows
  # launcher) and — when the machine has none >=3.10 at all (stock macOS ships
  # 3.9) — first downloads the toolkit's own checksum-pinned CPython runtime
  # into companion/.python-runtime/, then creates the venv and runs the
  # editable install. This replaces a hand-rolled venv block that died under
  # `set -e` on Python-3.9-only machines (pip rejects requires-python>=3.10),
  # killing the whole install mid-run. Never fatal now: a machine that can't
  # build today (offline) finishes installing cleanly, and the first /open-day
  # builds the companion through this same script.
  # LOCAL_ONLY: never let a stale toolkit-companion on PATH (e.g. an old
  # ~/.local/bin symlink) masquerade as this checkout's build. --force: running
  # the installer is an explicit retry, so it bypasses the resolver's 24h
  # post-failure cooldown.
  companion_bin="$(NSLS_COMPANION_LOCAL_ONLY=1 bash "$PLUGIN_DIR/companion/ensure-companion.sh" --force)" || companion_bin=""
  # Trust nothing that doesn't run: the resolver's fast path stats files only.
  if [ -n "$companion_bin" ] && ! "$companion_bin" --help >/dev/null 2>&1; then
    echo "  ⚠ Resolved companion at $companion_bin does not run — treating as not built."
    companion_bin=""
  fi
  if [ -n "$companion_bin" ]; then
    echo "✓ Installed nsls-toolkit-companion CLI"
    # The venv interpreter that owns the binary: used for the launchd helper
    # below (a stock Mac's 3.9 cannot parse install_helper.py's type hints) and
    # to register settings when this machine had no usable Python at all.
    COMPANION_PY="$(dirname "$companion_bin")/python"
    [ -x "$COMPANION_PY" ] || COMPANION_PY="$(dirname "$companion_bin")/python.exe"
    [ -x "$COMPANION_PY" ] || COMPANION_PY=""
    if [ "$_SETTINGS_REGISTERED" -eq 0 ] && [ -n "$COMPANION_PY" ]; then
      PY="$COMPANION_PY"
      register_settings
    fi
    if [ "$OS_CLASS" = "windows" ]; then
      # Symlinks need admin/developer mode on Windows, so don't try — the
      # skills resolve the venv's Scripts/ path directly.
      echo "  ℹ Windows: the companion binary is at"
      echo "      $companion_bin"
      echo "    The skills resolve this automatically; no symlink needed."
    else
      # The binary lives inside the venv and is NOT on PATH in fresh shells.
      # Symlink it to ~/.local/bin (on $PATH by default in modern shells).
      mkdir -p "$HOME/.local/bin"
      link_target="$HOME/.local/bin/toolkit-companion"
      if [ -L "$link_target" ] || [ ! -e "$link_target" ]; then
        ln -sf "$companion_bin" "$link_target"
        echo "✓ Symlinked toolkit-companion → $link_target"
        case ":$PATH:" in
          *":$HOME/.local/bin:"*) ;;
          *) echo "  ℹ ~/.local/bin is not on PATH. Add this to your shell rc:"
             echo "      export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
        esac
      else
        echo "  ⚠ $link_target already exists and is not a symlink; skipping. Run by full path or remove the file."
      fi
    fi
  else
    echo "  ⚠ Companion not built yet (reason above). Not fatal — it will build itself on the first /open-day."
  fi

  # Auto-start at login is macOS-only (launchd). Windows users: see
  # docs/windows-setup.md for a Task Scheduler / startup-shortcut recipe.
  #
  # Same stdin rule as the companion prompt above — a bare `read` under
  # `curl … | bash` eats the following lines of this script. This one is
  # macOS-only, so on a Mac it used to break the tail of the installer.
  # Default here stays **no**: installing a launchd login item is a system-level
  # change, so a run with nobody to ask must not do it silently.
  # NSLS_AUTOSTART_COMPANION=1 opts in without a prompt.
  # Offered only when the local companion actually built — a login item
  # pointing at a binary that doesn't exist would fail every boot.
  if [ "$OS_CLASS" = "macos" ] && [ -n "${companion_bin:-}" ]; then
    if [ -n "${NSLS_AUTOSTART_COMPANION:-}" ]; then
      auto="y"
    elif [ -t 0 ]; then
      read -p "Auto-start the companion at login? [y/N] " auto || auto="n"
    elif { : </dev/tty; } 2>/dev/null; then
      read -p "Auto-start the companion at login? [y/N] " auto </dev/tty || auto="n"
    else
      auto="n"
      echo "No terminal detected — skipping the login item (set NSLS_AUTOSTART_COMPANION=1 to enable)."
    fi
    if [[ "${auto:-n}" =~ ^[Yy] ]]; then
      install_companion_launchd
    fi
  fi
fi
