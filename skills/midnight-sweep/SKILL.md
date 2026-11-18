---
name: midnight-sweep
description: >-
  Overnight prep for open-day and close-day. Each night after a workday, Claude
  checks everything that happened that day (Slack, meetings, email, calendar,
  Claude threads, the builder's own notes, GitHub, the task board), re-checks
  every suggestion against it one by one, drafts the day's coaching, and, when
  the day wasn't closed, estimates progress on its tasks (shown light blue). The
  morning's open-day then starts from this file and only checks what happened
  since, so it is faster and its suggestions are current. Runs as a scheduled
  task in the Claude desktop app. Use when the scheduled run fires, or when the
  builder says "midnight sweep", "run the sweep", "sweep now", "turn on the
  midnight sweep", "turn off the midnight sweep", "test the midnight sweep",
  "turn off Claude's estimates" or "turn Claude's estimates back on".
---

# Midnight Sweep

Open-day has two jobs that pull against each other: be quick in the morning,
and get the suggestions right. Getting them right means checking every
candidate against every thread, which takes minutes. The sweep moves that work
to the night: it does the slow, thorough check while nobody is waiting, and
writes the result to a file. The morning only looks at what happened since.

It also gets coaching started early. Coaching isn't time-sensitive, so the
sweep works it out from the whole day, and close-day only has to look at what
changed after the sweep.

| Phrase | What happens |
|---|---|
| The scheduled run, "run the sweep", "sweep now" | **The run** below |
| "turn on the midnight sweep" (also open-day's one-time question) | **Turning it on** |
| "turn off the midnight sweep" | **Turning it off** |
| "turn off Claude's estimates" / "turn Claude's estimates back on" | `claude_estimates: off` / remove that line, in the builder profile |
| "test the midnight sweep" or `midnight sweep -t [path]` | **The run**, writing only a test file (see **Test mode**) |

**Never send anything to anyone.** The sweep reads, and writes only to the
builder's own vault. No Slack messages, emails, comments or calendar changes.

## Setup: paths and keys

Resolve the two keys open-day uses, without opening the whole `.env` (it holds
secrets):

```bash
grep -E '^(OBSIDIAN_VAULT_PATH|SLACK_USER_ID)=' ~/.claude/local-plugins/nsls-personal-toolkit/.env
```

`$V` below is `$OBSIDIAN_VAULT_PATH`. The builder profile is
`$V/50-reference/builder-profile.md`; read `timezone`, `work_schedule`,
`task_board`, `task_board_github`, `data_sources`, `claude_estimates` and
`midnight_sweep` from it. Sweep files live in `$V/50-reference/sweeps/`.

## Turning it on

1. **It needs the Claude desktop app**, which can run Claude on a schedule (the
   scheduled-tasks tools: `list_scheduled_tasks`, `create_scheduled_task`,
   `update_scheduled_task`). If this session doesn't have them, say in one line:
   "The midnight sweep needs the Claude desktop app, where Claude can run on a
   schedule. Ask me again there." Record nothing, so open-day can ask again in
   the app.
2. **Look before creating.** `list_scheduled_tasks`; if a task with id
   `midnight-sweep` exists, re-enable it with `update_scheduled_task` instead of
   making a second one.
3. **Create it** with `create_scheduled_task`:
   - `taskId`: `midnight-sweep`, `title`: `🌙 Midnight sweep`
   - `description`: `Nightly: check the day so tomorrow's open-day is fast and current`
   - `cronExpression`: `0 0 * * 2-6` (local midnight after each weekday) when
     `work_schedule` is `weekdays` or absent; `0 0 * * *` otherwise. The app
     adds a few minutes of spread on its own.
   - `notifyOnCompletion`: `false`
   - `prompt`: `This is the scheduled run. Run the midnight-sweep skill from
     the NSLS Personal Toolkit (the skill named exactly midnight-sweep), with
     its defaults. Never send messages, emails or Slack posts to anyone. Keep
     the chat reply to two lines.`
4. **Record it**: set `midnight_sweep: on` in the builder profile's top block
   (add the line if missing; never rewrite the rest of the file).
5. **Tell them, in plain words** (three lines at most): it runs at midnight
   after each workday while the Claude app is open; if the computer is asleep
   it runs when it wakes, and if the app was closed it runs the next time the
   app opens; tomorrow's open-day starts from it. Offer to run it now if today
   is a workday and it's evening, so tomorrow already benefits.

## Turning it off

`list_scheduled_tasks`, then `update_scheduled_task` on `midnight-sweep` with
`enabled: false`. Set `midnight_sweep: off` in the builder profile. One line to
confirm. Old sweep files stay where they are; open-day ignores them once they
are more than three days old.

## The run

### Step 1: Dates, and whether this run is needed

Run `date` fresh (Date Discipline in open-day applies here in full: never reuse
a cached date, and name absolute dates with the weekday in anything you write).

- **`SWEEP_DAY`, the scheduled run** (its prompt says "This is the scheduled
  run"): always yesterday's date. The schedule fires at midnight after a
  workday, so the day it's for is the one before the day it runs on, even when
  it fires hours late because the computer was asleep or the app was closed.
  Never work it out from the time of day: a catch-up at 7 PM still belongs to
  yesterday. If it missed several nights, the window below still reaches back
  to the last sweep, so nothing is skipped; only the most recent day gets
  estimates and coaching.
- **`SWEEP_DAY`, a run by hand:** a date the builder names ("sweep Monday"),
  otherwise today's date if it's 18:00 or later, otherwise yesterday's.
- **Already done?** For the scheduled run, if `$V/50-reference/sweeps/<SWEEP_DAY>.md`
  exists with `status: complete` and a `swept_through` after the end of
  `SWEEP_DAY`, stop and reply "Already swept at <time>." (A missed run and its
  catch-up can both fire.) A run by hand always runs, replacing the file.
- **The window.** From the previous sweep file's `swept_through` minus 15
  minutes (messages and meeting summaries can land late), or from the start of
  `SWEEP_DAY` when there is none. **A source the previous sweep couldn't read**
  is listed under `missed:` in its frontmatter with the time it was last read
  up to; read that source from that time instead, so a connector that was down
  last night loses nothing. When checking a candidate, also look back at
  least three days and from the date in the candidate's own text.
- **Note the start time** now. It becomes `swept_through`, so anything that
  happens while the sweep runs is caught by the next look, not lost.

### Step 2: Read the day

Read `SWEEP_DAY`'s daily note (`$V/01-daily/<SWEEP_DAY>.md`): its `status`,
the Top 3 and Bonus with their markers, `### Done`, `### Deleted`,
`### Deferred`, `### Unplanned`, `## Carrying Over`, and any AI suggestions.
This is what the builder marked in the Command Center. If there is no note
(a day off), still sweep: asks may have arrived. Skip Steps 4 and 5 for that
day.

Then gather the day from every source the profile turns on, in parallel where
the surface allows. Resolve each connector's live tool name from this
session's tools.

1. **Slack**: the builder's own messages (`from:<@$SLACK_USER_ID>`), messages
   to them and their DMs, and threads they took part in, all in the window.
2. **Meetings** (Fathom, or whatever records them): every meeting in the window,
   with its summary and action items.
3. **Email**: sent and received in the window. Skip newsletters and
   notifications.
4. **Calendar**: what happened on `SWEEP_DAY`, and the next working day's
   events.
5. **Claude Code and Cowork sessions** in the window: the session tools when
   the surface has them, otherwise `~/.claude/projects/*/` transcripts,
   searched by key word, never read whole. **The builder's own words in a
   thread count as their word** ("I've recorded the video").
6. **The builder's own files**: notes in the vault changed in the window,
   outside `01-daily/` (a meeting-prep list, a project note). An item already
   added to a list the builder keeps is done for "add X to that list".
   ```bash
   find "$V" -name '*.md' -newermt "<window start>" -not -path '*/01-daily/*' -not -path '*/.toolkit-companion/*' -not -path '*/50-reference/sweeps/*' | head -40
   ```
7. **GitHub**: the builder's PRs opened, merged or reviewed, and issues they
   touched, in the window.
8. **The task board**: `task_board` in the profile (Asana by default, or the
   GitHub project in `task_board_github`), read as open-day's Step 2n does.

**If a source can't be read, record it** under `## Sources` and in the
frontmatter's `missed:` map with the start of its window (carry the older time
forward if it was already missed last time), and keep going. Never imply a
source was checked when it wasn't.

### Step 3: Build tomorrow's list, checking every candidate on its own

**The pool:** `SWEEP_DAY`'s unfinished Top 3 and Bonus items and its
`### Deferred` items (deferred means "not today, but keep it"; keep each
`<!--e:X-->` remaining estimate), `## Carrying Over`, AI suggestions the
builder never dispositioned, **the `### AI Suggested: …` lines close-day
already seeded into the next working day's note** (when the day was closed
before the sweep), **the previous sweep file's suggestions and waiting items
that are still unresolved** (so a rerun never drops an ask from before its
window), new asks and action items from Step 2, and task board items (top-ups by open-day Step 2n's rule: anything someone asked about,
plus up to five when fewer than ten are open).

**Check each candidate separately.** For every one, search each source for its
key words and the people in it. One shared "messages I sent today" search is
not a check of thirty candidates; that shortcut is how a finished video and an
already-logged ask ended up on a morning list. Open-day's Step 2n
(`skills/open-day/SKILL.md`) holds the evidence rules; follow them, plus these:

- **Never hand the builder a checking job.** "Check that Sam confirmed the
  account merge" is Claude's job: search for the confirmation now. Confirmed:
  it's done, cited. Not yet: rewrite it as the action that follows ("Nudge
  Sam: the merge link expires 6 PM Wednesday") and add a line to
  `## Re-check in the morning` so open-day looks again before showing it.
- **Deadlines travel with the item.** Keep the date and time in the text, and
  if the deadline passes before the morning, say so.
- **Waiting on someone else** is not the builder's task. Put it under
  `## Waiting on others` with who and since when; it only becomes a suggestion
  when a nudge is due (three working days, or a deadline).

Classify every candidate as open, done (cited), possibly moot (cited), or
waiting. **If a source that would settle a candidate couldn't be read, say so
in its citation** ("not checked: Slack was unreadable") rather than presenting
it as confirmed open. Rank the open ones as open-day would, a fresh ask from a manager near
the top, and keep the three strongest first.

### Step 4: Claude's progress estimates (unclosed days only)

Only when `SWEEP_DAY`'s note is not `status: closed`, has no `close_ready: 1`
(a close is waiting or running), and the profile doesn't say
`claude_estimates: off`.

**Writing to a daily note, safely** (this step and the next). The builder, the
Command Center and close-day can all be changing the same note. So: never
rewrite the whole file; change one line (or the one `## Coaching` block) at a
time with the Edit tool, which refuses if the file changed since you read it.
**Re-read the note right before each edit.** If it is now `status: closed` or
has `close_ready: 1`, stop writing to it. If the line you meant to change has
changed (the builder marked the task), leave it. If an edit is refused, re-read
and try once more, then skip that line.

For each Top 3 and Bonus item the builder hasn't marked (still `[ ]`, no
`<!--p:NN-->` of any value, `<!--p:0-->` included, which is the builder
setting it to zero over an earlier estimate; not under `### Done` or
`### Deleted`), estimate 25, 50, 75 or
100 from the evidence in Step 2: a merged PR or a sent deliverable is 100; a
shared draft is 50 to 75; work started in a thread is 25. **No evidence, no
estimate**: leave the line alone.

Write the estimate as a `<!--c:NN-->` marker at the end of the item's line in
`SWEEP_DAY`'s note, replacing any earlier `<!--c:NN-->` and leaving everything
else on the line exactly as it was (text, checkbox, `<!--e:X-->`). Use the Edit
tool, one line at a time: the Command Center may be open. It shows the
estimate in very light blue until the builder clicks a level of their own,
which replaces it. Never write `<!--p:NN-->`, never tick a box: those are the
builder's.

### Step 5: Coaching

- **`SWEEP_DAY` is closed:** close-day already wrote its coaching. Leave it.
- **Not closed:** write two to four short bullets about the day, from what the
  builder marked in the Command Center and what they did across meetings,
  Slack and Claude threads: one thing that went well and why it matters, one
  pattern worth noticing, and the one focus for the next day. If Step 4 wrote
  estimates, add: "I estimated progress on <N> tasks from what I could see
  (light blue). Click a level to set your own when you close the day." Put the
  bullets in `SWEEP_DAY`'s note under `## Coaching` (create it as its own `##`
  section before `## Morning Check-in`), at the top of the section after
  `<!-- from: last night's sweep -->`. Keep any other labelled bullets below
  it; replace an earlier sweep's block if this is a re-run.
- **Either way**, put the forward-looking bullets for the next working day
  (its focus, its shape, anyone to follow up with) under
  `## Coaching for the morning` in the sweep file. Open-day copies them.

Plain words, one idea per bullet, nothing private about another person.

### Step 6: Write the sweep file

Write `$V/50-reference/sweeps/<SWEEP_DAY>.md` (create the folder if needed).
**Write it to `<SWEEP_DAY>.md.tmp` first, then rename it into place**, so a run
that dies halfway never leaves a file that looks finished. `swept_through` is
the start time from Step 1, with its UTC offset.

Suggestion lines use open-day's format exactly, so open-day can copy them:
the citation in a trailing parenthetical (never after a dash, which the
Command Center strips) and the remaining estimate as `<!--e:X-->`.

```markdown
---
sweep_day: 2026-11-17
swept_through: 2026-11-18T00:03:00-05:00
status: complete
missed:
  email: 2026-11-16T00:02:00-05:00
---
# Midnight sweep: Tuesday, Nov 17

## The day
- Meeting: security test with your manager (Fathom): the test passed. Your action: write the rollout plan.
- Shipped: four PRs merged (reporting-repo 233–237).
- Sent: six colleague notes on Slack.
- Claude threads: "Security test" (rollout plan drafted, not finished).

## Suggestions for Wednesday, Nov 18
1. Answer Alex on where the storage key lives (Slack DM, Nov 18 2:05 AM: "where does the key live?") <!--e:0.25-->
2. …

## Likely already done
1. Record the demo video (Claude thread "Launch prep", Nov 17: "I've recorded it")

## Possibly moot
1. …

## Waiting on others
- Your manager: admin rights on the repos (asked Nov 17 10:47, no reply)

## Re-check in the morning
- Sam's account-merge confirmation (link expires Wednesday 6 PM): search Slack from Sam since the sweep.

## Claude's progress estimates
- Write the rollout plan: 50% (draft in Claude thread "Security test", Nov 17)

## Coaching for the morning
- …

## Sources
- Read: Slack, Fathom, Gmail, Google Calendar, Claude sessions, vault notes, GitHub, task board
- Couldn't read: none
```

`## The day` is the record close-day builds the Work Log and meeting notes
from when the day is closed after the sweep: every meeting with its takeaways
and the builder's action items, what they shipped or sent, and where each
Claude thread got to, one line each with its source. Leave `missed:` out when
every source was read, and leave out any section that would be empty, except
`## Sources`.

### Step 7: Reply

Two lines at most, in this thread: what was swept and what's ready, e.g.
"Swept Tuesday, Nov 17: 14 suggestions ready for Wednesday, 3 already done,
2 progress estimates. Tomorrow's open-day starts from this." Name any source
that couldn't be read.

## Test mode

`midnight sweep -t [path]` or "test the midnight sweep": run every step, but
write nothing to the vault. The sweep file goes to `[path]` (or this session's
scratch folder), the estimates and coaching appear only inside it, under the
sections above, with the exact lines the run would have written, and the
idempotency check is skipped.

## Edge cases

- **Weekends.** The weekday schedule skips Saturday and Sunday nights.
  Monday's open-day starts from Friday's sweep and checks everything since.
- **The builder is still working when it runs.** Fine: estimates only go on
  unmarked tasks, any click of theirs replaces them, and every note edit
  re-reads first (Step 4).
- **Close-day runs while the sweep is still working.** The sweep file only
  appears, complete, at the very end, so close-day either finds none (and
  reads the day in full) or a finished one. The sweep stops writing to the
  note the moment it sees `close_ready: 1` or `status: closed`.
- **The day gets closed after the sweep.** Close-day starts from the sweep's
  work and replaces its coaching block with tonight's close (see close-day
  Step 0.7).
- **A source is switched off or disconnected.** Record it under `## Sources`;
  open-day says so in its capacity line.
