# install.ps1 — Windows installer for the NSLS Personal Productivity Toolkit.
#
# Native PowerShell alternative to install.sh (which needs Git Bash). Run from
# PowerShell:
#   irm https://raw.githubusercontent.com/<you>/nsls-personal-toolkit/main/install.ps1 | iex
# or, after cloning:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# Prerequisites: Git and Python 3.10+ on PATH (python.org installer — tick
# "Add python.exe to PATH").

$ErrorActionPreference = "Stop"

$PluginDir = Join-Path $HOME ".claude\local-plugins\nsls-personal-toolkit"
$RepoUrl = if ($env:NSLS_PERSONAL_REPO) { $env:NSLS_PERSONAL_REPO } else { "https://github.com/thensls/nsls-personal-toolkit.git" }

# Locate Python (python, then the py launcher).
$Py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py) { $Py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $Py) { Write-Error "Python 3.10+ not found. Install from https://python.org (tick 'Add to PATH') and re-run."; exit 1 }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error "Git not found. Install from https://git-scm.com and re-run."; exit 1
}

Write-Host "Installing NSLS Personal Productivity Toolkit..."
Write-Host "  Repo: $RepoUrl"

# Clone or update.
if (Test-Path $PluginDir) {
  Write-Host "Plugin directory exists; pulling latest..."
  git -C $PluginDir pull --ff-only 2>$null
} else {
  New-Item -ItemType Directory -Force -Path (Split-Path $PluginDir) | Out-Null
  git clone $RepoUrl $PluginDir
}

Write-Host ""
Write-Host "Done! Personal productivity skills installed at:"
Write-Host "  $PluginDir\skills\<name>\SKILL.md"
Write-Host ""

# Optional: web companion (in an explicit venv so the Scripts\ path is stable).
#
# Only ask when a human can actually answer. The documented path is
# `irm ... | iex`, and a non-interactive run (CI, or an agent driving the
# installer) can't respond to Read-Host — which is how builders end up with
# companion\ source but no .venv, leaving every day skill to fall back to chat
# silently. With no console to prompt, install it: the skills expect it.
# $env:NSLS_SKIP_COMPANION = "1" is the explicit opt-out.
if ($env:NSLS_SKIP_COMPANION) {
  $answer = "n"
  Write-Host "NSLS_SKIP_COMPANION set - skipping the web companion."
} elseif ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
  $answer = Read-Host "Install the web companion (browser-based UI)? [Y/n]"
} else {
  $answer = "y"
  Write-Host "Non-interactive run - installing the web companion (set NSLS_SKIP_COMPANION=1 to skip)."
}
if ($answer -eq "" -or $answer -match "^[Yy]") {
  $Companion = Join-Path $PluginDir "companion"
  $Venv = Join-Path $Companion ".venv"
  if (-not (Test-Path $Venv)) {
    & $Py -m venv $Venv
  }
  $VenvPy = Join-Path $Venv "Scripts\python.exe"
  & $VenvPy -m pip install --upgrade pip -q
  Push-Location $Companion
  try {
    & $VenvPy -m pip install -e . -q
  } finally {
    Pop-Location
  }
  $Bin = Join-Path $Venv "Scripts\toolkit-companion.exe"
  Write-Host "Installed the companion. Binary at:"
  Write-Host "  $Bin"
  Write-Host "The skills resolve this path automatically."
  Write-Host ""
  Write-Host "Set your vault path so the companion can find your notes:"
  Write-Host '  setx OBSIDIAN_VAULT_PATH "C:\path\to\your\Obsidian\vault"'
  Write-Host ""
  Write-Host "Auto-start at login (optional): see docs\windows-setup.md."
}

Write-Host "Next: open Claude Code and say /personal-setup to connect your accounts."
