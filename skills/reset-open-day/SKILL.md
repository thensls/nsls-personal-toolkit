---
name: reset-open-day
description: >-
  Reset the vault to pre-open-day state for testing. Deletes the target date's daily note entirely so /open-day can create it fresh. Does NOT touch habits or log.md. Trigger phrases: reset open day, undo open day, reset for open day test
---

# Reset Open Day

Undo what `/open-day` wrote so you can test it again from a clean state.

## What this resets

1. **Target date's daily note** — deletes `$OBSIDIAN_VAULT_PATH/01-daily/<date>.md` entirely

## What this does NOT reset

- **Habits file** (`30-habits/habits.md`) — untouched
- **Habit log** (`30-habits/log.md`) — untouched
- **Prior day's notes** — untouched (carry-overs will re-surface from the most recent prior note)
- **AI Suggested sections from close-day** — if you want those to appear again, seed them manually or run `/reset-close-day` on the prior day first

## Steps

1. Determine the target date. Default to today (`date +%Y-%m-%d`). User can pass a date: `/reset-open-day 2026-05-23`.

2. Delete `$OBSIDIAN_VAULT_PATH/01-daily/<date>.md`.

3. **Ensure yesterday appears closed** so `/open-day` doesn't auto-run close-day. Check if yesterday's note exists at `$OBSIDIAN_VAULT_PATH/01-daily/<yesterday>.md`:
   - If it exists and already has `## Insight Reflection` with content: no action needed.
   - If it exists but has no `## Insight Reflection`: append `## Insight Reflection\n\n(reset-open-day stub — close-day was skipped for testing)\n` to the end.
   - If it doesn't exist: create a minimal stub at `$OBSIDIAN_VAULT_PATH/01-daily/<yesterday>.md`:
     ```
     # <yesterday> — <Day of Week>

     ## Insight Reflection

     (reset-open-day stub — close-day was skipped for testing)
     ```
   This prevents `/open-day` from triggering a full close-day run during testing.

4. Report: "Deleted daily note for <date>. Yesterday appears closed. Run `/open-day` to recreate it."

5. If the companion is running, note: "The companion will show Plan Your Day mode on next refresh."
