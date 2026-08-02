# Automating the biweekly sweep on Windows

**Read this first: do not use `/schedule`.** It creates a Claude *cloud routine*, which runs in an isolated cloud sandbox with no access to your local disk and no MCP connectors. It cannot see your Obsidian vault, Fathom, or Signal. A routine set up for this sweep will fire on schedule and do nothing, which is worse than no automation at all — the schedule looks healthy while nothing happens.

The sweep has to run on your own PC, under your own credentials. Windows Task Scheduler is how you do that.

---

## Before you start — three checks

Open **PowerShell** and run each of these. All three must succeed.

```powershell
claude --version
python --version
Test-Path "$env:USERPROFILE\.claude\local-plugins\nsls-personal-toolkit\.env"
```

- `claude --version` should print a version. If "not recognized," Claude Code isn't on your PATH — reinstall or add it.
- `python --version` should print **3.12 or newer**. If you get the Microsoft Store stub or a 3.9, install Python 3.12+ and re-check.
- The `Test-Path` must print `True`. That `.env` holds your `OBSIDIAN_VAULT_PATH`, `FATHOM_API_KEY`, `ANTHROPIC_API_KEY`, and Signal token. Without it the sweep runs but silently produces Fathom-only profiles.

Write down the full path that `where.exe python` prints — you'll need it in step 3.

---

## Step 1 — Prove the sweep works by hand

Never schedule something you haven't watched run. In PowerShell:

```powershell
python "$env:USERPROFILE\.claude\local-plugins\nsls-personal-toolkit\skills\person-intelligence\scripts\scheduled_sweep.py" --dry-run --force
```

You should see something like:

```
[2026-08-01T13:03:42+00:00] DUE: --force.
[2026-08-01T13:03:42+00:00] Starting headless sweep via `claude -p`.
[2026-08-01T13:03:42+00:00] DRY-RUN: would exec: claude -p <prompt> --permission-mode acceptEdits --allowedTools ...
```

`--dry-run` executes nothing. If this errors, fix it now — the scheduler will only reproduce the same error at 6:47 on a Sunday where nobody sees it.

---

## Step 2 — Run it for real, once

Drop `--dry-run` and keep `--force`:

```powershell
python "$env:USERPROFILE\.claude\local-plugins\nsls-personal-toolkit\skills\person-intelligence\scripts\scheduled_sweep.py" --force
```

This does the whole sweep and takes a while — it synthesizes every tracked profile. Let it finish. The last line should be `OK: sweep complete and finalized.`

Then confirm the results landed:

```powershell
Get-Content "$env:USERPROFILE\.cache\person-intelligence\last-sweep-status.json"
```

You want `"complete": true` and `"finalized": true`, with a non-zero `relationships_processed`.

---

## Step 3 — Create the scheduled task

1. Press **Win**, type `Task Scheduler`, open it.
2. Right-hand panel → **Create Task…** (not "Create Basic Task" — you need the extra options).

**General tab**
- Name: `Person-intelligence biweekly sweep`
- Select **Run only when user is logged on**. *Do not* pick "Run whether user is logged on or not" — that runs in a session without access to your credential store, and the sweep will fail on auth.
- Leave "Run with highest privileges" **unchecked**. It doesn't need admin.

**Triggers tab** → New…
- Begin the task: `On a schedule`
- **Weekly**, recur every `1` week, check **Sunday**
- Start time: `6:47 AM`
- Click OK.

> Weekly is correct even though the sweep is biweekly. Windows can't express "every other Sunday," so the script itself decides: it skips unless the last completed sweep is 12+ days old. Setting this to every-two-weeks in Windows would fight the script and cause skipped cycles.

**Actions tab** → New…
- Action: `Start a program`
- Program/script: the full python path from `where.exe python` (e.g. `C:\Users\laptop\AppData\Local\Programs\Python\Python312\python.exe`)
- Add arguments:
  ```
  "C:\Users\laptop\.claude\local-plugins\nsls-personal-toolkit\skills\person-intelligence\scripts\scheduled_sweep.py"
  ```
  Replace `laptop` with your username. Keep the quotes.
- Start in:
  ```
  C:\Users\laptop\nsls-skills\nsls-personal-toolkit
  ```
  No quotes on this one — Task Scheduler rejects them here.

**Conditions tab**
- **Uncheck** "Start the task only if the computer is on AC power." Otherwise it silently skips on battery.

**Settings tab**
- **Check** "Run task as soon as possible after a scheduled start is missed." Your laptop is asleep at 6:47 AM most Sundays. The freshness gate makes a late catch-up run safe.
- Set "Stop the task if it runs longer than" to `4 hours`.

Click OK.

---

## Step 4 — Test the task itself

In Task Scheduler, right-click the task → **Run**. Then:

```powershell
Get-Content "$env:USERPROFILE\.cache\person-intelligence\sweep-cron.log" -Tail 10
```

Because you just ran a real sweep in step 2, the correct result is a skip:

```
[...] FRESH: finalized sweep 2026-08-01 is 0d old (21 relationships), interval 12d — skipping.
```

**That is success.** It proves Task Scheduler can find Python, find the script, and read the status file. The gate did its job.

Check the task's **Last Run Result** column reads `The operation completed successfully (0x0)`.

---

## What you'll see from here

- Every Sunday at 6:47 AM the task fires.
- Most Sundays it logs `FRESH ... skipping` and exits in under a second.
- Every other Sunday it runs the full sweep and writes a new team-pulse digest to `30-people/_pulse/`.
- If a run fails, the failure is written into `last-sweep-status.json`, and **`/open-day` will tell you the next morning**. You don't have to watch the log.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `FAIL: claude not found on PATH` | Task Scheduler's environment lacks `claude` | Use the full path to `claude.exe` — find it with `where.exe claude` — and set it in the script's `run_claude` command, or add its folder to your system PATH |
| Last Run Result `0x1` and an empty log | Wrong Python path, or quotes around "Start in" | Re-check the Actions tab; remove quotes from "Start in" |
| Sweep runs but profiles are thin/Fathom-only | `.env` not found | Re-run the `Test-Path` check at the top |
| Task never fires | "Run only when user is logged on" + logged out at 6:47 | Expected; the missed-start setting catches it at next login |
| Runs every Sunday instead of every other | Not a bug | The gate skips the off weeks — check the log to confirm |

## Manual controls

```powershell
# Run now regardless of the gate
python "...\scheduled_sweep.py" --force

# See what it would do, change nothing
python "...\scheduled_sweep.py" --dry-run

# Read the log
Get-Content "$env:USERPROFILE\.cache\person-intelligence\sweep-cron.log" -Tail 20
```

To pause for vacation: right-click the task → **Disable**. Re-enable when back.
