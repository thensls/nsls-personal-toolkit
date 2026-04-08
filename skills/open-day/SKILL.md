---
name: open-day
description: >-
  Morning planning routine — pulls Google Calendar events, Asana tasks,
  overdue items, and yesterday's carry-overs to set daily priorities and
  populate the Morning Check-in in today's Obsidian daily note. Use when the
  user says "open day", "start my day", "morning", "good morning", "what's on
  my plate", "what do I have today", "plan my day", "daily planning", or opens
  a new session in the morning. Requires Google Calendar and Asana access.
---

# Open Day

Pull today's calendar, Asana tasks, overdue items, and yesterday's carry-overs to populate the Morning Check-in section of today's daily note.

## When to Run

Morning, before first meeting. Can also be triggered mid-day to reset priorities.

## Asana Reference

Read these from `~/.claude/local-plugins/nsls-personal-toolkit/.env`:
- **Workspace GID:** `$ASANA_WORKSPACE_GID`
- **User GID:** `$ASANA_USER_GID`

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
  timeZone="America/New_York",
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
mcp__claude_ai_asana__asana_search_tasks(
  assignee_any="me",
  completed=false,
  due_on_before="YYYY-MM-DD+1",  // include today
  sort_by="due_date",
  sort_ascending=true,
  opt_fields="name,due_on,projects.name",
  limit=50
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

If it exists, extract the `## Next Week Priorities` or `## This Week's Focus` section. These are the strategic priorities for the week.

**2e. AI suggestions from close-day (if seeded)**

Check if today's daily note already exists and contains AI suggestions from last night's `/close-day`:

Look for `### AI Suggested: Tomorrow's Top 3` and `### AI Suggested: Delegate These` sections in the daily note. If found, extract both lists — these are the AI's overnight strategic recommendations.

### Step 3: Draft Morning Check-in

Present to the user. If AI suggestions were seeded by close-day, show them first as a starting point:

```markdown
## Morning Check-in

### Last Night's AI Suggestions (from /close-day)
**Top 3:**
1. [AI suggestion 1 — with rationale from close-day]
2. [AI suggestion 2]
3. [AI suggestion 3]

**Delegate:**
1. [Delegate item 1] → [Person]
2. [Delegate item 2] → [Person]
3. [Delegate item 3] → [Person]

### Today's Meetings ([count])
- **HH:MM** — [Title] (with [key attendees])
  - Prep: [if external/board/candidate, note what to prepare]
- **HH:MM** — [Title]

### Morning Top 3 (fresh from Asana + calendar + carry-overs)
1. [P1 Asana task or carry-over — explain why it's #1]
2. [Next most important — from Asana, carry-over, or week plan]
3. [Third — balance strategic and tactical]

*Based on: [N] overdue Asana tasks, [N] carry-overs from yesterday, week plan priorities.*
*AI suggestions from close-day shown above for comparison — adopt, modify, or replace.*

### Overdue ([count])
- [ ] [Task] (due [date]) — [project]
- [ ] [Task] (due [date])

### Also on the plate
- [ ] [Due today tasks]
- [ ] [Do today section tasks]
- [ ] [Carry-overs not in top 3]
```

If NO AI suggestions were seeded (close-day wasn't run, or this is a fresh week), skip the "Last Night's AI Suggestions" section and just show the regular "Morning Top 3".

**Priority inference for Top 3:**
1. Anything with an external deadline today (meeting prep, deliverable due)
2. P1 Asana tasks that are overdue
3. Carry-overs that have been carrying for multiple days (check previous daily notes)
4. Week plan priorities that haven't gotten attention yet
5. Quick wins that unblock others

### Step 4: the user reviews and adjusts

The user sets their actual Top 3 and energy level. The AI and morning suggestions are starting points — the user may adopt, modify, or completely replace them.

After the user confirms his Top 3, write them to the `### My Top 3` section of the daily note.

### Step 5: Write daily note

Check if `01-daily/YYYY-MM-DD.md` already exists:
- **Exists:** Update the Morning Check-in section only, preserve everything else
- **Doesn't exist:** Create from template with Morning Check-in populated

Write to:
```
$OBSIDIAN_VAULT_PATH/01-daily/YYYY-MM-DD.md
```

The daily note should include:
```markdown
# YYYY-MM-DD — [Day of Week]

## Morning Check-in
- Energy: [blank — user fills in]
- Top 3 priorities today:
  1. [User's chosen or suggested #1]
  2. [#2]
  3. [#3]

## Today's Meetings
- **HH:MM** — [Title] (with [attendees])
- **HH:MM** — [Title]

## Asana
**Overdue:**
- [ ] [Task] (due [date])

**Due today:**
- [ ] [Task]
```

The `## Work Log`, `## Projects Touched`, `## Carrying Over`, and `## End of Day` sections are left empty — `/close-day` fills those in.

### Step 6: Track priority alignment (if AI suggestions existed)

If today's note had AI suggestions from close-day AND the user set his own Top 3, compare them and append a record to:
```
$OBSIDIAN_VAULT_PATH/03-meta/priority-alignment.md
```

Create this file if it doesn't exist, with this header:
```markdown
# Priority Alignment Tracker

Tracks how often the AI's overnight strategic suggestions match the user's morning priorities. Over time, this reveals whether the AI is reading the right signals — and where the user's judgment diverges.

| Date | AI #1 | AI #2 | AI #3 | the user #1 | the user #2 | the user #3 | Adopted | Modified | Replaced |
|------|-------|-------|-------|----------|----------|----------|---------|----------|----------|
```

For each day, append one row. Classification rules:
- **Adopted**: User's item is essentially the same as the AI suggestion (same task, same intent)
- **Modified**: User kept the spirit but changed scope, timing, or framing (e.g., AI said "draft contract" → the user said "review contract draft from legal")
- **Replaced**: User chose something entirely different

Count the totals: e.g., `2 adopted, 0 modified, 1 replaced`

Example row:
```
| 2026-03-28 | Contract w/ IP carve-outs | Julia follow-up after vacation | Cash in cushions table | Contract w/ IP carve-outs | Review Chris's SNHU deck (Sat delivery) | Julia scheduling post-vacation | 2 | 1 | 0 |
```

**Do NOT block the morning flow for this.** If the user is in a hurry, skip the tracker and catch up on the next `/close-day` or `/open-day`. The tracker is a background signal, not a gate.

### Day-of-Week Additions

Include role-specific reminders based on the day:

- **Monday:** "Review topic submissions in Slack. Prepare weekly update + draft agenda. Check Airtable for open action items."
- **Tuesday:** Flag SLT meeting type (tactical or strategic based on week-of-month). "Pre-meeting: Finalize agenda. Post-meeting: Trigger assessment."
- **Friday:** "SLT topic request goes out at 3 PM ET. Run /close-week before quick notes."

## Edge Cases

- **Weekend:** Still generate if the user asks, but skip meeting prep and Asana overdue (he knows it's the weekend).
- **No carry-overs:** Skip that section.
- **Empty calendar:** Note "No meetings today — deep work day?" and suggest tackling overdue Asana items.
