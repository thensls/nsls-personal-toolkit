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

  # Resolve vault path via Python (handles env var, builder-profile, and prompt)
  local vault_path
  vault_path=$("$PY" "$plugin_dir/companion/install_helper.py" resolve-vault)
  if [ -z "$vault_path" ] || [ ! -d "$vault_path/01-daily" ]; then
    echo "✗ Could not find a vault with 01-daily/ at: $vault_path"
    echo "  Set OBSIDIAN_VAULT_PATH or add the vault to builder-profile.md, then re-run install."
    return 1
  fi

  # Generate the plist via Python (handles quoting correctly)
  "$PY" "$plugin_dir/companion/install_helper.py" write-plist \
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
  if [ -n "$PY" ]; then
    COMPANION_DIR="$HOME/.claude/local-plugins/nsls-personal-toolkit/companion"
    VENV_DIR="$COMPANION_DIR/.venv"
    # Create the venv the rest of this block already assumes exists (it resolves
    # companion/.venv/bin/toolkit-companion below). Without it, `pip install -e .`
    # on an externally-managed (PEP-668/Homebrew) Python errors with
    # "externally-managed-environment", -q hides it, and the companion silently
    # never builds — every /open-day then falls back to plain chat.
    if [ ! -x "$VENV_DIR/bin/python" ] && [ ! -x "$VENV_DIR/Scripts/python.exe" ]; then
      "$PY" -m venv "$VENV_DIR"
    fi
    if [ "$OS_CLASS" = "windows" ]; then
      VENV_PY="$VENV_DIR/Scripts/python.exe"
    else
      VENV_PY="$VENV_DIR/bin/python"
    fi
    [ -x "$VENV_PY" ] || VENV_PY="$PY"
    (cd "$COMPANION_DIR" && "$VENV_PY" -m pip install -e . -q)
    echo "✓ Installed nsls-toolkit-companion CLI"

    if [ "$OS_CLASS" = "windows" ]; then
      # On Windows the console script is companion/.venv/Scripts/toolkit-companion.exe.
      # Symlinks need admin/developer mode, so don't try — the skills resolve
      # the Scripts/ path directly.
      win_bin="$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/Scripts/toolkit-companion.exe"
      echo "  ℹ Windows: the companion binary is at"
      echo "      $win_bin"
      echo "    The skills resolve this automatically; no symlink needed."
    else
      # Externally-managed Python forces pip into a venv, so the binary lives at
      # companion/.venv/bin/toolkit-companion and is NOT on PATH in fresh shells.
      # Symlink it to ~/.local/bin (on $PATH by default in modern shells).
      venv_bin="$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/toolkit-companion"
      if [ -x "$venv_bin" ]; then
        mkdir -p "$HOME/.local/bin"
        link_target="$HOME/.local/bin/toolkit-companion"
        if [ -L "$link_target" ] || [ ! -e "$link_target" ]; then
          ln -sf "$venv_bin" "$link_target"
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
    fi
  else
    echo "⚠ python not found; skipping companion install. Install Python 3.10+ and re-run."
  fi

  # Auto-start at login is macOS-only (launchd). Windows users: see
  # docs/windows-setup.md for a Task Scheduler / startup-shortcut recipe.
  if [ "$OS_CLASS" = "macos" ]; then
    read -p "Auto-start the companion at login? [y/N] " auto
    if [[ "${auto:-n}" =~ ^[Yy] ]]; then
      install_companion_launchd
    fi
  fi
fi
