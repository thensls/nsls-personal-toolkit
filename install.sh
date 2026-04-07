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
