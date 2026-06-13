---
name: reset-day
description: >-
  Start today over. Clears today's daily note so a fresh /open-day rebuilds it
  from your real data (real carry-overs and any real AI suggestions a prior
  close-day wrote — never fabricated). Works whether or not close-day has run.
  Use when you opened the day and want to redo it, or opened and closed it and
  want to reset both. Trigger phrases: reset day, redo day, reset my day, redo
  today, start the day over, reset today.
---

# Reset Day

Clear today so you can run `/open-day` again from a clean slate. Useful any time
you want to redo your day — not just for testing.

**Principle: never fabricate.** This skill deletes/strips today's note; it does
NOT invent priorities, AI suggestions, or carry-overs. The next `/open-day`
re-derives all of that from your real history (prior daily notes, real
close-day seeds). If there's nothing real to seed from, you simply start empty.

## Modes

- **Default (full reset):** clears today's daily note entirely. Both the morning
  plan and any close-day output are removed — a complete redo of the day. Use
  this whether you only opened the day, or opened *and* closed it.
- **`reset-day --close-only`:** strips only what close-day wrote (Work Log,
  Time Allocation, Insight Reflection, End of Day, etc.) and **keeps** your
  morning plan (`### My Top 3`, `### Bonus`, `### Habits`). Use this to re-test
  or redo just the close without re-planning.

## What this does NOT touch

- **Habits config** (`30-habits/habits.md`) — never.
- **Prior days' notes** — never (your real history is the seed source).
- **Connected accounts** — read-only; nothing is written to Calendar/Asana here.

## Steps

1. **Determine the target date.** Default today (`date +%Y-%m-%d`). User may pass
   one: `/reset-day 2026-06-13`. Parse `--close-only` if present.

2. **Read today's note** at `$OBSIDIAN_VAULT_PATH/01-daily/<date>.md`. Detect state:
   - No file → nothing to clear; skip to step 5 (still handle the empty-vault guard).
   - File present, no `## Insight Reflection` → open-day ran, close-day didn't.
   - File present, has `## Insight Reflection` → both ran.

3. **Reset:**
   - **Full reset (default):** delete `01-daily/<date>.md` entirely. The next
     `/open-day` recreates it from real data.
   - **`--close-only`:** preserve everything up to and including `## Calendar`
     (or `## Active Projects` if Calendar is absent); delete everything after
     (Work Log content, Time Allocation, Meetings, Insight Reflection, End of
     Day, etc.); re-add the empty skeleton:
     ```
     ## Work Log
     -

     ## End of Day
     - Energy:
     ```

4. **Clean up close-day's side effects:**
   - Delete the **next-day note** `01-daily/<date+1>.md` ONLY if it was seeded by
     close-day (has `### AI Suggested:` sections AND an empty `## Work Log`). If
     it has real content, leave it.
   - Remove today's row from `30-habits/log.md` if one exists (starts with `<date>`).

5. **Empty-vault guard (the only time we write a stub):** if — and only if —
   there are **no prior daily notes at all** in `01-daily/` (a brand-new/empty
   vault), write a minimal closed stub for yesterday so `/open-day`'s Step 1.5
   doesn't try to auto-close a day that never existed:
   ```
   # <yesterday> — <Day of Week>

   ## Insight Reflection

   (reset-day stub — no prior data in this vault)
   ```
   If any real prior note exists, do nothing here — keep yesterday real.

6. **Report** what was reset, in one or two lines. Remind the user:
   > Cleared <date>. Run `/open-day` to rebuild it from your real carry-overs and
   > suggestions. Add `-v` to open it with the visual companion.

## Notes

- This is a genuinely useful everyday skill (redo a day you opened wrong), which
  is why it carries no "testing" label. The `--close-only` mode covers the
  re-test-the-close case without re-planning.
- It supersedes the older `reset-open-day` / `reset-close-day` skills.
