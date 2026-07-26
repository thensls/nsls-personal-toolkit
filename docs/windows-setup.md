# Windows setup

The toolkit runs on Windows. A few things differ from macOS/Linux; this page covers them.

## Prerequisites

- **Python 3.10+** — install from [python.org](https://python.org) and tick **"Add python.exe to PATH"**. (Many Windows installs only have `python`, not `python3` — the installers handle both.)
- **Git** — from [git-scm.com](https://git-scm.com). This also gives you **Git Bash**.

## Install

Two options:

- **PowerShell (native):**
  ```powershell
  powershell -ExecutionPolicy Bypass -File install.ps1
  ```
- **Git Bash:** the same `install.sh` the Mac uses works here:
  ```bash
  bash install.sh
  ```

Both create a virtualenv at `companion\.venv` and install the web companion into it. The companion binary lands at:

```
%USERPROFILE%\.claude\local-plugins\nsls-personal-toolkit\companion\.venv\Scripts\toolkit-companion.exe
```

The skills resolve this `Scripts\…\.exe` path automatically — you don't need it on PATH.

> **Agent-driven / piped installs:** the two installers offer the companion behind
> an interactive prompt, which a piped `irm … | iex` run or an agent driving setup
> will skip. In that case `/personal-setup` (Step 1.5) provisions the same venv —
> so the companion still lands, and `visual_mode` stays truthful, without the prompt.

## Vault path

Point the companion at your Obsidian vault:

```powershell
setx OBSIDIAN_VAULT_PATH "C:\Users\you\Obsidian\YourVault"
```

Open a new terminal afterward (so the variable is picked up).

## Auto-start at login (optional)

macOS uses `launchd`; Windows has no equivalent in the installer. To start the companion automatically:

**Option A — Startup shortcut (simplest):**
1. Press `Win+R`, type `shell:startup`, Enter.
2. Create a shortcut whose target is:
   ```
   "%USERPROFILE%\.claude\local-plugins\nsls-personal-toolkit\companion\.venv\Scripts\toolkit-companion.exe" serve
   ```

**Option B — Task Scheduler (runs hidden, more control):**
1. Open Task Scheduler → Create Basic Task → trigger "When I log on".
2. Action → Start a program:
   - Program: the `toolkit-companion.exe` path above
   - Arguments: `serve`

You don't need auto-start to use it — you can also let `/open-day -v` start it on demand, the same as on Mac.

## Known cross-platform details (handled for you)

- **File encoding** — all vault reads/writes are UTF-8, so notes with emoji or accented characters work despite Windows defaulting to cp1252.
- **Line endings** — files are written with LF; a note saved by a Windows editor with CRLF is normalized on the next write.
- **File locking** — concurrent saves (e.g. ticking habits quickly) are serialized with `msvcrt` locking, so updates don't clobber each other.
- **Atomic writes** — if Obsidian sync or antivirus briefly holds a file open, the write retries instead of failing.

## Editable install note

`companion\pyproject.toml` uses `package-dir = {"" = ".."}`, so `pip install -e .` must be run **from inside `companion\`** (both installers do this for you). If you install by hand, `cd companion` first.
