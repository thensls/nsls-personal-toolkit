---
name: open-day
description: >-
  Morning planning routine — pulls Google Calendar events, Asana tasks,
  overdue items, and yesterday's carry-overs to set daily priorities, schedule
  focus blocks and vitality time on the calendar, and populate the Morning
  Check-in in today's Obsidian daily note. Use when the user says "open day",
  "plan day", "plan my day", "start my day", "morning", "good morning",
  "what's on my plate", "what do I have today", "daily planning", or opens a
  new session in the morning. Requires Google Calendar and Asana access.
---

# Open Day

Pull today's calendar, Asana tasks, overdue items, and yesterday's carry-overs. Help the builder set priorities across work and vitality, schedule them on the calendar, and populate today's daily note.

## Philosophy

Productivity is one pillar of a good day — not the whole thing. This skill plans around three pillars:

1. **Productivity** — Top 3 work priorities. High-leverage, builder-only.
2. **Growth** — Intentional learning from `40-learning/` goals. Daily: 15-min micro-learning block (one article, one tutorial, one inbox link). Weekly: 1.5h deep dive scheduled by `/open-week`. Coaching and skill development also count.
3. **Vitality** — Exercise, hobbies, relationships, rest. The stuff that keeps the engine running.

A day with all three pillars touched is a good day, even if the Asana list didn't shrink.

## When to Run

Morning, before first meeting. Can also be triggered mid-day to reset priorities and reschedule.

## Asana Reference

Read these from `~/.claude/local-plugins/nsls-personal-toolkit/.env` or `$OBSIDIAN_VAULT_PATH/50-reference/builder-profile.md`:
- **Workspace GID:** `$ASANA_WORKSPACE_GID`
- **User GID:** `$ASANA_USER_GID`

## Timezone

Read timezone from `$OBSIDIAN_VAULT_PATH/50-reference/builder-profile.md` (the `timezone` field). Default to `America/Denver` if not set.

## Step-by-step Execution

### Step 1: Determine today's date

```bash
date +%Y-%m-%d
```

### Step 2: Collect data (run in parallel)

**2a. Google Calendar — today's meetings**

```
gcal_list_events(
  timeMin="YYYY-MM-DDT00:00:00",
  timeMax="YYYY-MM-DDT23:59:59",
  timeZone="<builder timezone>",
  condenseEventDetails=false
)
```

Extract: meeting title, start/end time, attendees. Flag meetings that need prep (external attendees, board members, candidates).

**2b. Asana — what's due and overdue**

Two parallel calls:

```
mcp__claude_ai_Asana__get_my_tasks(
  completed_since="now",
  limit=100,
  opt_fields="name,due_on,projects.name,assignee_section.name"
)
```

```
mcp__claude_ai_Asana__search_tasks_preview(
  assignee_any="me",
  completed=false,
  due_on_before="YYYY-MM-DD+1"
)
```

Categorize:
- **Overdue** — due before today
- **Due today** — due today
- **Do today section** — tasks in "Do today" Asana section regardless of due date

Filter out auto-generated noise ("It's time to update your goal(s)").

**2c. Yesterday's carry-overs**

Read yesterday's daily note:
```
$OBSIDIAN_VAULT_PATH/01-daily/YYYY-MM-DD-1.md
```

Extract the `## Carrying Over` section. These are unfinished items from yesterday.

**2d. This week's plan (if it exists)**

Check for a weekly plan note:
```
$OBSIDIAN_VAULT_PATH/02-weekly/YYYY-[W]WW.md
```

If it exists, extract the `## Next Week Priorities` or `## This Week's Focus` section.

**2e. AI suggestions from close-day (if seeded)**

Check if today's daily note already exists and contains AI suggestions from last night's `/close-day`:

Look for `### AI Suggested: Top 3` and `### AI Suggested: Delegate These` sections. If found, extract both — these are the AI's overnight strategic recommendations.

**2f. This week's stack rank (if strategy layer active)**

Read the latest file from:
`$OBSIDIAN_VAULT_PATH/10-strategy/stack-rank/`

Extract: ranked project list, week mode, focus items. If no stack rank exists, skip — strategy layer not active.

**2g. Free time slots**

```
gcal_find_my_free_time(
  calendarIds=["primary"],
  timeMin="YYYY-MM-DDT07:00:00",
  timeMax="YYYY-MM-DDT20:00:00",
  timeZone="<builder timezone>",
  minDuration=30
)
```

This returns all free blocks >= 30 min between 7 AM and 8 PM. Used in Step 5 for scheduling.

**2h. Learning inbox ingestion**

If `learning_capture_method` in the builder profile is set to `slack`, scrape the builder's Slack self-DMs for URLs:

1. Use `mcp__plugin_slack_slack__slack_read_channel` to read the builder's self-DM channel (using `$SLACK_USER_ID`). Look for messages from the last 24 hours containing URLs.
2. For each URL found:
   - Fetch the page title via WebFetch (just the title and first paragraph, not the full page)
   - Generate a 1-2 sentence summary
   - Check if it matches any active learning goal topic (read `$OBSIDIAN_VAULT_PATH/40-learning/_learning-goals.md` for active topic names)
   - Append to `$OBSIDIAN_VAULT_PATH/40-learning/_inbox.md`:
     ```
     - [ ] [Page Title](URL) — YYYY-MM-DD, from: Slack self-DM
       > [1-2 sentence summary]
       > Tags: #[matched-topic] or #untagged
     ```
3. If no new URLs found or capture method is not `slack`, skip silently.
4. If new links were ingested, mention in the morning summary: "Ingested [N] new links into your learning inbox."

Also read:
- `$OBSIDIAN_VAULT_PATH/40-learning/_weekly-plan.md` — today's micro-learning assignment
- `$OBSIDIAN_VAULT_PATH/40-learning/_inbox.md` — count of unprocessed links for active goals

### Step 3: Draft Morning Check-in

Present to the builder. If AI suggestions were seeded by close-day, show them first:

```markdown
## Morning Check-in

### Last Night's AI Suggestions (from /close-day)
**Top 3:**
1. [AI suggestion 1 — with rationale]
2. [AI suggestion 2]
3. [AI suggestion 3]

**Delegate:**
1. [Delegate item 1] → [Person]
2. [Delegate item 2] → [Person]
3. [Delegate item 3] → [Person]

### Today's Meetings ([count])
- **HH:MM** — [Title] (with [key attendees])
  - Prep: [if external/board/candidate, note what to prepare]

*[N] meetings, ~[X]h. Deep work windows: [list gaps >= 60 min].*

### Relationship Context (after calendar display)

After displaying today's meetings, scan attendees against `$OBSIDIAN_VAULT_PATH/30-people/*.md` profiles. For each attendee who has an active coaching goal (grep for `status: active` in `## Coaching Goals`) or a `## Personal` section:

```
👥 Relationship Context for Today

  [time] — [meeting title] ([attendee name])
    🎯 Active goal: [goal title]
       → Today: [one-line contextual action from the goal's action list]
    👤 Personal: [1-2 key personal details if available]
```

**Rules:**
- Only show people with active coaching goals or personal details — skip empty profiles
- Compact: 2-3 lines per person max
- The contextual action should be specific to the meeting type (sprint → sprint-specific action, 1:1 → relationship action)
- If no attendees have coaching goals or personal details, skip this section entirely — don't show an empty block

### Morning Top 3 (fresh from Asana + calendar + carry-overs)
1. [P1 — explain why it's #1]
2. [Next most important]
3. [Third — balance strategic and tactical]

*Based on: [N] overdue Asana tasks, [N] carry-overs from yesterday.*

### Overdue ([count])
- [ ] [Task] (due [date]) — [project]

### Also on the plate
- [ ] [Due today / Do today tasks]
- [ ] [Carry-overs not in top 3]

### Vitality
What non-work activity would make today a good day? Suggest one from each pillar based on what's been missing recently:
- **Move:** [e.g., Morning walk, gym, bike ride]
- **Grow:** [e.g., Read 20 pages, listen to podcast, coaching reflection]
- **Connect:** [e.g., Text a friend, lunch with partner, call family]
```

If NO AI suggestions were seeded, skip the "Last Night's AI Suggestions" section.

**Priority inference for Top 3:**
1. Anything with an external deadline today (meeting prep, deliverable due)
2. Stack rank: if a Top 5 project hasn't been touched yet this week, boost it
3. P1 Asana tasks that are overdue
4. Carry-overs that have been carrying for multiple days
5. Week plan priorities that haven't gotten attention yet
6. Quick wins that unblock others

**Stack rank flag (Wed+):** If it's Wednesday or later and the #1 ranked project for the week hasn't been touched, add a prominent note: "Your #1 project for the week ([name]) hasn't been touched yet. Today might be the day."

**Vitality suggestions:** Base these on patterns. If close-day shows coding was 60%+ yesterday, suggest movement. If meetings were 50%+, suggest solo time. If no learning captures in recent days, suggest growth. Default to suggesting at least one movement activity.

**Operating memo check (if strategy layer active):**
Read `10-strategy/operating-memo.md`. Scan today's proposed Top 3 against "I Don't" and "My Traps" sections. If a proposed priority matches a trap pattern, flag it:
> "Heads up: [priority] looks like it falls in your 'I Don't' list. Your memo says: '[quote from memo]'. Still want to include it, or is there a way to teach/delegate instead of doing?"

Also check the teach/delegate/do ladder: if a priority is maintenance work on a project with role containing "->", suggest: "Could you pair with [collaborator] on this instead of doing it solo? Your memo says teach first."

### Step 4: The builder reviews and adjusts

You set your actual Top 3, energy level, and vitality intentions. The AI and morning suggestions are starting points — you may adopt, modify, or completely replace them.

After you confirm, proceed to scheduling.

### Step 5: Schedule the day on the calendar

After the builder confirms priorities, propose a concrete schedule by mapping priorities + vitality into the free time slots from Step 2g.

**Scheduling rules:**

1. **Work priorities get focus blocks.** Default 90 min for deep work, 60 min for admin/communication tasks, 30 min for quick items. The builder can adjust.

2. **Vitality gets real calendar time.** If you chose a movement activity, schedule it. A block on the calendar is the difference between "I should exercise" and actually doing it. Default 30-45 min.

3. **Micro-learning gets a 15-min block every day.** Read `40-learning/_weekly-plan.md` for today's assignment. If no weekly plan exists, pick the highest-priority unprocessed link from `_inbox.md` that matches an active goal. Schedule in a lower-energy slot (after lunch, late afternoon, between meetings). Use summary: "Learn: [topic] — [item title]". Color: Grape (3).

   **Deep dive gets a longer block on the scheduled day.** If `_weekly-plan.md` shows a deep dive for today, schedule the full block (~1.5h). Use summary: "Deep Dive: [topic] — [item title]". Color: Grape (3).

4. **Respect energy patterns:**
   - Early morning (before 9 AM): Best for deep/creative work
   - Mid-morning: Good for strategic meetings and hard thinking
   - After lunch: Lower energy — admin, email, lighter tasks
   - Late afternoon: Second wind — good for building or coaching calls

5. **Don't over-schedule.** Leave >= 25% of free time unscheduled for slack, interruptions, and spontaneity. A packed calendar is a brittle calendar.

6. **Buffer around meetings.** Don't schedule focus blocks immediately after meetings (5-10 min transition). Don't schedule immediately before important meetings (15 min prep buffer).

**Project-aware block naming:**
When creating focus blocks, use the project name from the stack rank when possible:
- If the priority maps to a known project in `20-projects/`: `Focus: [project-name] — [specific task]`
- If it doesn't map to a project: `Focus: [priority description]`

Example: "Focus: directory-requests — scrape remaining schools" not "Focus: deep work"

**Present the proposed schedule:**

```markdown
### Proposed Schedule

Here's how I'd map your priorities to today's open blocks:

| Time | Block | Priority | Type |
|------|-------|----------|------|
| 7:00-8:30 | Focus: [project] — [task] | #1 | Work |
| 8:30-9:00 | *buffer before meeting* | | |
| 9:00-10:00 | [Meeting title] | meeting | |
| 10:15-11:00 | Focus: [project] — [task] | #2 | Work |
| 11:00-12:30 | [Meeting title] | meeting | |
| 12:30-1:00 | Walk / lunch | | Vitality |
| 1:00-1:30 | Admin: email + Slack catch-up | | |
| 1:30-2:00 | [Meeting title] | meeting | |
| 2:15-3:15 | Focus: [project] — [task] | #3 | Work |
| 3:15-3:45 | Read / learn | | Growth |
| 3:45-5:00 | *unscheduled (slack)* | | |

Want me to create these calendar blocks? You can say:
- "yes" — create all proposed blocks
- "skip vitality" — work blocks only
- "just the top 3" — only focus blocks for priorities
- or adjust any block ("make #1 sixty minutes", "move walk to 3pm")
```

**Calendar event creation:**

Use `gcal_create_event` for each approved block:

- **Focus blocks:**
  - Summary: `Focus: [priority description]`
  - Color: Peacock (7) — blue
  - Description: `Priority #[N] from /open-day\n[Brief context: what specifically to do]`
  - No attendees, no notifications except 5-min popup
  - `sendUpdates: "none"`

- **Vitality blocks:**
  - Summary: `[Activity]` (e.g., "Walk", "Gym", "Read")
  - Color: Basil (10) — green
  - Description: `Vitality block from /open-day`
  - `sendUpdates: "none"`

- **Growth blocks:**
  - Summary: `Learn: [topic]` or `Read: [book]` or `Coaching reflection`
  - Color: Grape (3) — purple
  - Description: `Growth block from /open-day`
  - `sendUpdates: "none"`

- **Admin blocks** (if scheduled):
  - Summary: `Admin: [description]`
  - Color: Graphite (8)
  - `sendUpdates: "none"`

All blocks use the builder's timezone.

**Example:**
```
gcal_create_event(
  event={
    summary: "Focus: directory-requests — scrape remaining schools",
    description: "Priority #1 from /open-day\nDraft subcontractor contract with IP carve-outs.",
    start: { dateTime: "2026-04-08T07:00:00-06:00", timeZone: "<builder timezone>" },
    end: { dateTime: "2026-04-08T08:30:00-06:00", timeZone: "<builder timezone>" },
    colorId: "7",
    reminders: { useDefault: false, overrides: [{ method: "popup", minutes: 5 }] }
  },
  sendUpdates: "none"
)
```

### Step 6: Write daily note

Check if `01-daily/YYYY-MM-DD.md` already exists:
- **Exists:** Update the Morning Check-in section, preserve everything else (especially close-day's AI suggestions in the header)
- **Doesn't exist:** Create from template

Write to:
```
$OBSIDIAN_VAULT_PATH/01-daily/YYYY-MM-DD.md
```

The daily note should include:

```markdown
# YYYY-MM-DD — [Day of Week]

## Morning Check-in
- Energy: [builder's input]

### AI Suggested: Top 3 (from [previous day]'s close)
[preserved from close-day seed if it existed]

### AI Suggested: Delegate These
[preserved from close-day seed if it existed]

### My Top 3
1. [Builder's chosen #1]
2. [#2]
3. [#3]

### Vitality
- [ ] [Movement activity]
- [ ] [Growth activity]
- [ ] [Connection activity]

## Calendar
- **HH:MM-HH:MM** — [Title] (attendees)
- **HH:MM-HH:MM** — Focus: [priority] <- *scheduled by /open-day*
- **HH:MM-HH:MM** — [Vitality block] <- *scheduled by /open-day*

*[N] meetings (~[X]h). [N] focus blocks scheduled. [Vitality/growth blocks noted.]*

## Active Projects
\```dataview
TABLE WITHOUT ID link(file.link, title) AS "Project", next-action AS "Next Action", collaborators AS "With"
FROM "20-projects"
WHERE type = "project" AND status = "active"
SORT priority ASC
\```

## Work Log
-

## End of Day
- Energy:
```

The `## Work Log`, `## Projects Touched`, `## Carrying Over`, and `## End of Day` sections are left empty — `/close-day` fills those in.

### Step 7: Track priority alignment (if AI suggestions existed)

If today's note had AI suggestions from close-day AND the builder set their own Top 3, compare them and append a record to:
```
$OBSIDIAN_VAULT_PATH/03-meta/priority-alignment.md
```

Create this file if it doesn't exist, with this header:
```markdown
# Priority Alignment Tracker

Tracks how often the AI's overnight strategic suggestions match your morning priorities. Over time, this reveals whether the AI is reading the right signals — and where your judgment diverges.

| Date | AI #1 | AI #2 | AI #3 | Your #1 | Your #2 | Your #3 | Adopted | Modified | Replaced |
|------|-------|-------|-------|---------|---------|---------|---------|----------|----------|
```

Classification rules:
- **Adopted**: Your item is essentially the same as the AI suggestion
- **Modified**: You kept the spirit but changed scope, timing, or framing
- **Replaced**: You chose something entirely different

Count the totals: e.g., `2 adopted, 0 modified, 1 replaced`

**Do NOT block the morning flow for this.** If you're in a hurry, skip the tracker.

### Day-of-Week Additions

Include role-specific reminders based on the builder's role and team cadence. Read these from `$OBSIDIAN_VAULT_PATH/50-reference/builder-profile.md` if a `day_reminders` section exists. If no custom reminders are configured, skip this section.

Example format (customize per builder):
- **Monday:** "Review topic submissions. Prepare weekly update."
- **Tuesday:** "Check standing meeting agenda. Finalize prep."
- **Friday:** "Run /close-week. Review weekly metrics."

## Edge Cases

- **Weekend:** Still generate if the builder asks, but lean toward vitality and growth blocks over work. Skip meeting prep and Asana overdue.
- **No carry-overs:** Skip that section.
- **Empty calendar:** Note "No meetings today — deep work day?" Suggest tackling overdue Asana items. Schedule larger focus blocks.
- **Back-to-back meetings all day:** Note the constraint. Suggest one vitality micro-block (15 min walk between meetings). Don't force focus blocks into 20-min gaps.
- **Mid-day reset:** If the builder runs `/open-day` mid-day, pull updated calendar, check what's been accomplished, and reschedule remaining priorities into afternoon blocks. Remove morning blocks that already passed.
- **Builder declines scheduling:** That's fine. The skill works without calendar scheduling — just write the daily note with priorities and move on. Don't push.

## Progressive Opt-in: Strategy Layer

The following features only activate when `$OBSIDIAN_VAULT_PATH/10-strategy/operating-memo.md` exists:

- **Stack rank reading** (Step 2f) — reads `10-strategy/stack-rank/` for weekly project rankings
- **Operating memo check** (Step 3) — scans proposed priorities against "I Don't" and "My Traps" sections
- **Teach/delegate/do ladder** (Step 3) — suggests pairing or delegation based on project roles in the memo

Without an operating memo, the skill runs as a straightforward morning planner: calendar + Asana + carry-overs + vitality. No strategy nudges, no trap warnings. Run `/self-insight` to generate your operating memo when you're ready.
