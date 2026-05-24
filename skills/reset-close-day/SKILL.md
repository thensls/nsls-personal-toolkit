---
name: reset-close-day
description: >-
  Reset the vault to pre-close-day state for testing. Restores the target date's daily note to its open-day state and deletes any next-day note that close-day seeded. Does NOT touch habits, priorities, bonus items, or log.md. Trigger phrases: reset close day, undo close day, reset for close day test
---

# Reset Close Day

Undo what `/close-day` wrote so you can test it again from a clean state.

## What this resets

1. **Target date's daily note** — restores to its pre-close-day state (keeps `## Morning Check-in` with priorities/bonus/habits, removes `## Work Log` content, `## End of Day` AI suggestions, `## Insight Reflection`, `## Time Allocation`, and any other sections close-day added)
2. **Next day's note** — deletes it entirely if close-day's Step 8 seeded it
3. **Habit log** — removes today's row from `30-habits/log.md` if close-day wrote one

## What this does NOT reset

- **Habits file** (`30-habits/habits.md`) — untouched
- **Priorities and bonus items** in `### My Top 3` and `### Bonus` — preserved
- **AI Suggested sections** in Morning Check-in — preserved (those came from a prior close-day, not this one)
- **`### Dismissed`** — preserved

## Steps

1. Determine the target date. Default to today (`date +%Y-%m-%d`). User can pass a date: `/reset-close-day 2026-05-23`.

2. Read the target date's daily note at `$OBSIDIAN_VAULT_PATH/01-daily/<date>.md`.

3. **Preserve everything up to and including `## Calendar`** (or `## Active Projects` if Calendar is missing). Delete everything after that section — that's where close-day writes its content (Work Log, Time Allocation, Meetings, Insight Reflection, End of Day, etc.).

4. **Re-add the skeleton sections** at the end:
   ```
   ## Work Log
   -

   ## End of Day
   - Energy:
   ```

5. **Delete the next day's note** at `$OBSIDIAN_VAULT_PATH/01-daily/<date+1>.md` — but ONLY if it was seeded by close-day (check if it has `### AI Suggested:` sections and an empty `## Work Log`). If the note has real content (Work Log entries, user-written sections), do NOT delete it.

6. **Remove today's row from log.md** — if `30-habits/log.md` has a row starting with `<date>`, remove it.

7. Report what was reset.
