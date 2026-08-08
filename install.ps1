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

# --- Enable the plugin and register the auto-update hook in settings.json ---
#
# This is what makes updates actually arrive. hooks/hooks.json is the documented
# plugin location, but a *locally enabled* plugin does not reliably load bundled
# hooks — notably on Claude Code desktop — so the global settings.json entry is
# the primary firing path and hooks.json is the fallback.
# (~/.claude/local-plugins/ is not a Claude Code convention; it's just this
# project's checkout location, so nothing loads it unless settings.json says so.)
#
# The pull hook is a bare `git` call deliberately: no python, no bash, so it
# can't be defeated by the Microsoft-Store python stub or a missing Git Bash.
# $HOME (not $env:USERPROFILE) to match $PluginDir above — on a machine with a
# redirected or UNC home these differ under PS 5.1, and the clone and the
# settings file must land under the same root.
$Settings = Join-Path $HOME '.claude\settings.json'
try {
  # Create it when absent rather than bailing: a first-ever install would
  # otherwise register nothing, with nothing to remind the builder later.
  if (Test-Path $Settings) {
    $raw = Get-Content $Settings -Raw
    # Strip a UTF-8 BOM by hand — an older installer may have written one, and
    # ConvertFrom-Json chokes on it.
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }
    $cfg = if ($raw.Trim()) { $raw | ConvertFrom-Json } else { [pscustomobject]@{} }
  } else {
    New-Item -ItemType Directory -Force -Path (Split-Path $Settings) | Out-Null
    $cfg = [pscustomobject]@{}
  }

  if (-not ($cfg.PSObject.Properties.Name -contains 'enabledPlugins') -or $null -eq $cfg.enabledPlugins) {
    $cfg | Add-Member -NotePropertyName enabledPlugins -NotePropertyValue ([pscustomobject]@{}) -Force
  }
  $cfg.enabledPlugins | Add-Member -NotePropertyName 'nsls-personal-toolkit@local' -NotePropertyValue $true -Force

  if (-not ($cfg.PSObject.Properties.Name -contains 'hooks') -or $null -eq $cfg.hooks) {
    $cfg | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{}) -Force
  }
  $ss = @(@($cfg.hooks.SessionStart) | Where-Object { $null -ne $_ })

  $pullCmd = 'git -C "' + $PluginDir + '" pull --ff-only --quiet'
  $pullMarker = $PluginDir + '" pull'

  # Append-only, and idempotency is checked across EVERY entry. Never filter or
  # rewrite another entry: the builder toolkit registers its own SessionStart
  # hook in this same array, and an earlier version of this block dropped whole
  # entries whose commands merely mentioned our path — which silently deleted
  # the builder toolkit's hook (its auto-update, pointer sync and tracker ping)
  # on any machine where install.sh had run first.
  $found = $false
  foreach ($entry in $ss) {
    foreach ($h in @($entry.hooks)) {
      if ($h.command -and $h.command.Contains($pullMarker)) { $found = $true }
    }
  }
  if (-not $found) {
    # startup|resume: a resumed session must update too.
    $ss += , @{ matcher = 'startup|resume'; hooks = @(@{ type = 'command'; command = $pullCmd;
                 timeout = 20; statusMessage = 'Updating personal toolkit...' }) }
  }
  $cfg.hooks | Add-Member -NotePropertyName SessionStart -NotePropertyValue $ss -Force

  # BOM-less write: PowerShell 5.1's `Set-Content -Encoding utf8` emits a BOM,
  # which breaks json.load() for every other consumer of settings.json.
  [System.IO.File]::WriteAllText($Settings, ($cfg | ConvertTo-Json -Depth 12),
    (New-Object System.Text.UTF8Encoding $false))

  # Verify by re-reading rather than trusting that the write happened.
  $chk = Get-Content $Settings -Raw | ConvertFrom-Json
  if ($chk.enabledPlugins.'nsls-personal-toolkit@local') {
    Write-Host "  Enabled plugin + registered the auto-update hook."
  } else {
    Write-Host "  Note: settings.json write did not take effect."
  }
} catch {
  Write-Host "  Note: could not update settings.json - see README (Updates) to add the hook by hand."
}

# Pointer sync is NOT registered here. It needs Python, and a stock Win11
# python/python3 is the Store stub that exits 0 having done nothing. On Windows
# the builder toolkit's own hook (hooks/session-start.ps1) already syncs
# pointers for BOTH toolkits, so registering a Python one here would add a
# failure mode without adding coverage.

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
