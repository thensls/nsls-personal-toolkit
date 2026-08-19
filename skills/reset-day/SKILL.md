---
name: reset-day
description: >-
  Start today over. Clears today's daily note so a fresh /open-day rebuilds it
  from your real data (real carry-overs and any real AI suggestions a prior
  close-day wrote). Works whether or not close-day has run. Use when you opened
  the day and want to redo it, or opened and closed it and want to reset both.
  Add `-t` (`reset day -t`) to wipe the throwaway test vault only, never real data.
  Trigger phrases: reset day, redo day, reset my day, redo today, start the day
  over, reset today, reset day -t.
---

# Reset Day

Clear today so you can run `/open-day` again from a clean slate. Useful any time
you want to redo your day — not just for testing.

**This skill never fabricates anything itself** — it only deletes/strips today's
note. The next `/open-day` re-derives suggestions: real carry-overs and real
close-day seeds first; and **only if there's no prior data at all** (fresh vault,
no prior close), open-day offers a few reasonable suggestions drawn from your
role/projects so the planning screen isn't empty (see open-day Step 6). reset-day
itself injects nothing.

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

## Confirm before resetting (safety — ALWAYS, unless already disambiguated)

reset-day **deletes** today's note. Before touching anything, **ask the builder
which day to reset and wait for an answer** — do not delete first. Ask (use the
AskUserQuestion tool, or a plain question):

> **Reset which?**
> - **Your real day** (`<date>`) — clears today's actual note so `/open-day` rebuilds it.
> - **The test sandbox** — wipes only the throwaway `companion-test-vault`; your real day is untouched.
> - **Cancel** — do nothing.

Then:
- **Real day** → proceed against the real vault (the steps below, default `$OBSIDIAN_VAULT_PATH`).
- **Test sandbox** → follow **Test mode** below (redirect + assert guard), then run the same steps.
- **Cancel** → stop. Delete nothing.

**Skip this confirmation only when the intent is already explicit:**
- `-t` was passed (`reset-day -t`) → answer is "test sandbox"; go straight to Test mode.
- reset-day is running as the `-r` pre-step of `/open-day` (e.g. `open day -r`) → the
  `-r` flag is itself the authorization; open-day handles that reset silently, no prompt.

This makes a bare `reset-day` safe by default: a misfired trigger can't silently
wipe a real day, and there's no way to confuse "reset my day" with "reset the test data".

## Test mode (`-t`) — wipes the test vault only

When the builder chose **test sandbox** (or passed `-t`), reset the **throwaway test
vault** instead of your real vault — the `companion-test-vault` that `open day -t` /
`close day -t` write to. This is just an `$OBSIDIAN_VAULT_PATH` redirect, with a
hard safety guard so it can **never** delete real data.

**Before any read or delete**, resolve the companion binary (same helper open-day
Step 8 uses — it builds the venv on first use, and when the machine has no
Python ≥3.10 it first downloads the toolkit's own private runtime; a first build
can take a few minutes — warn the builder up front, don't abort), point the
vault at the test vault, and *assert* it:

Run `--check` first; if it prints `build` or `build-python`, warn the builder
(one line: "~30 seconds" / "a few minutes — it's fetching its own Python, one
time only") before the real call, and give that call a 10-minute timeout for
`build-python`:

```bash
STATE="$(bash "$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh" --check)"
TC="$(bash "$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh")"
[ -n "$TC" ] || { echo "ABORT: no companion binary — cannot verify the test vault"; exit 1; }
export OBSIDIAN_VAULT_PATH="$("$TC" test-vault)"
"$TC" assert-test-vault "$OBSIDIAN_VAULT_PATH" || { echo "ABORT: not a test vault"; exit 1; }
```

**The `[ -n "$TC" ]` guard is load-bearing.** Without a binary there is no way to
resolve *or* verify the test vault, so the only safe move is to stop — never fall
through to the delete steps with an unverified `$OBSIDIAN_VAULT_PATH`.

`assert-test-vault` exits non-zero unless the resolved path is a directory named
`companion-test-vault`. **If it fails, stop — delete nothing.** Only after it passes
do you run the delete steps below (which already key off `$OBSIDIAN_VAULT_PATH`).

**Without `-t`, never touch the test vault.** A plain `reset-day` operates on your
real vault. If the resolved `$OBSIDIAN_VAULT_PATH` is itself named
`companion-test-vault` (e.g. a stray override left in the shell from an earlier
`open day -t`) and `-t` was **not** passed, stop and ask the builder to pass `-t`
explicitly rather than silently resetting the sandbox.

## Steps

1. **Confirm what to reset, then determine the target date.** Run the
   **Confirm before resetting** gate above *first* (unless `-t` or an `open day -r`
   chain already disambiguates) — delete nothing until the builder answers. Default
   the date to today (`date +%Y-%m-%d`); the user may pass one: `/reset-day 2026-06-13`.
   Parse `--close-only` and `-t` if present.

2. **Read today's note** at `$OBSIDIAN_VAULT_PATH/01-daily/<date>.md`. Detect state:
   - No file → nothing to clear; skip to step 5 (still handle the empty-vault guard).
   - **Prefer the `status:` frontmatter** when present (it's the mode contract both
     companions read): `closed` → both ran; `active`/`planning` → open-day ran,
     close-day didn't.
   - **Fall back** to section presence only when there's no `status` frontmatter
     (older notes): no `## Insight Reflection` → open-day ran, close-day didn't;
     has `## Insight Reflection` → both ran.

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
     Also **set `status: planning` in the frontmatter** (re-opening the day for a
     fresh close means it's no longer closed). If the note carries `status:`, set
     it to `planning`; add a frontmatter block if absent.

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
   ---
   status: closed
   ---
   # <yesterday> — <Day of Week>

   ## Insight Reflection

   (reset-day stub — no prior data in this vault)
   ```
   (`status: closed` — the stub represents an already-closed yesterday, so both
   companions render it read-only.)
   If any real prior note exists, do nothing here — keep yesterday real.

6. **Report** what was reset, in one or two lines. Remind the user:
   > Cleared <date>. Run `/open-day` to rebuild it from your real carry-overs and
   > suggestions. Add `-v` to open it with the visual companion.

## Notes

- This is a genuinely useful everyday skill (redo a day you opened wrong), which
  is why it carries no "testing" label. The `--close-only` mode covers the
  re-test-the-close case without re-planning.
- It supersedes the older `reset-open-day` / `reset-close-day` skills.
