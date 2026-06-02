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

### Step 1.5: Auto-run yesterday's /close-day if it didn't run

`/close-day` is a separate ritual from `/open-day` — it intentionally closes the workday and produces the plan-vs-actual reflection that makes today's Top 3 honest instead of performative. `/open-day` does not subsume it. **But if it didn't run last night, /open-day runs it automatically before continuing — no prompt, no skip.**

**Check:**
```bash
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d 'yesterday' +%Y-%m-%d)
if ! grep -q "^## Insight Reflection" "$OBSIDIAN_VAULT_PATH/01-daily/$YESTERDAY.md" 2>/dev/null; then
  echo "MISSING"
fi
```

(The `## Insight Reflection` header is only written by `/close-day`, so its presence is the reliable signal that yesterday was processed.)

**If MISSING — auto-invoke close-day, no prompt:**

1. Tell {user} in one line: "Yesterday's /close-day didn't run — running it now before opening today."
2. Invoke the close-day skill with yesterday's date (`/close-day $YESTERDAY`). Wait for completion.
3. Continue to Step 2.

The auto-run is the point: morning routine self-heals when the evening ritual was skipped. Builders who want to skip close-day entirely should remove this step from their fork rather than gate it with a prompt.

**Edge case — double-run protection:** If close-day fails or partially writes Insight Reflection, the next /open-day will see the header present and skip. If you suspect a partial state (e.g., header present but the section is empty), surface it explicitly before re-running.

**If present:** Continue silently to Step 2.

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

**2i. Slack follow-up scan**

If `data_sources.slack: true` in the builder profile, scan recent Slack to surface threads where the builder owes a reply or made a commitment they may not have acted on.

**Window:** last 2 work days (skip weekends if today is Mon).

**Two queries to run in parallel:**

1. **Builder's recent sent messages** — surface unverified commitments
   ```
   slack_search_public_and_private(
     query="from:<@$SLACK_USER_ID> after:YYYY-MM-DD",
     sort="timestamp",
     limit=20,
     include_context=false
   )
   ```
   Filter results for commitment language: phrases like "I'll", "I will", "I can", "let me", "I'll put X on the calendar", "going to", "by EOD", "by Friday", "happy to", "I'll send", "I'll draft", "I'll follow up". Each match becomes a candidate "did you do this?" item.

2. **Recent DMs and threads where someone is awaiting a reply** — surface outstanding asks
   ```
   slack_search_public_and_private(
     query="to:<@$SLACK_USER_ID> after:YYYY-MM-DD",
     sort="timestamp",
     limit=20,
     include_context=false
   )
   ```
   For the top channels/DMs that appear, use `slack_read_channel` with `limit=3` to check whether the most recent message is from the builder or someone else. If someone else is the last responder *and* they asked a question or proposed an action, flag as "owes a reply."

**Output in Morning Check-in:**

```markdown
### Slack follow-ups

**Outstanding asks (someone else's message is last in thread):**
- [Channel/DM with Name]: "[last 80-char snippet]" — [permalink]
- ...

**Your commitments (verify these landed):**
- [Date HH:MM] in [channel/DM]: "I'll [thing]" — [permalink]
- ...
```

If the list is empty, omit the section entirely. If a candidate appears in last week's daily notes (already followed up), suppress it.

**Rules:**
- Skip casual reactions, "ok thanks", single emoji, and obvious non-commitments
- Skip the builder's own bot DMs (NSLS Coach, SLT EA Bot, etc.) unless they contain a commitment to a person
- Group by recipient, not by message (one line per person if multiple messages)
- Surface up to 5 outstanding asks and 5 unverified commitments — beyond that the list becomes noise

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

**2i. Open PRs on watched repos**

Surface open pull requests on repos the builder maintains so they don't sit forgotten. Skip silently if `PR_WATCH_REPOS` is not set in `~/.claude/local-plugins/nsls-personal-toolkit/.env`, or if the `gh` CLI is unavailable.

`PR_WATCH_REPOS` format: comma-separated `owner/repo` pairs.
Example: `PR_WATCH_REPOS=thensls/nsls-builder-toolkit,thensls/nsls-personal-toolkit`

```bash
REPOS=$(grep '^PR_WATCH_REPOS=' ~/.claude/local-plugins/nsls-personal-toolkit/.env 2>/dev/null | cut -d= -f2- | tr -d ' ')
# Safety: must have a non-empty list AND it must contain a slash (owner/repo).
# Without this, `gh search prs --state open` would query all of GitHub.
if [ -n "$REPOS" ] && [[ "$REPOS" == *"/"* ]] && command -v gh >/dev/null; then
  gh search prs --state open --repo "$REPOS" --limit 30 \
    --json number,title,author,repository,createdAt,isDraft \
    2>/dev/null
fi
```

Categorize results into two buckets:
- **Yours sitting open** — `author.login == $GITHUB_USERNAME`. These are PRs the builder opened that haven't merged. Flag any older than 7 days.
- **Waiting on you** — everything else, treated as needing the builder's review.

Skip the entire section in Step 3 if both buckets are empty.

**2j. SLT Meeting Actions — open items from the SLT knowledge base**

Pull Kevin's open Meeting Actions from the SLT Meeting Intelligence base. Symmetric with `/close-day` Step 1h. These are action items from SLT meetings tracked separately from Asana — many have no due date but are time-sensitive (retreat prep, offsite logistics, quarterly deliverables).

Skip this step if `$AIRTABLE_API_KEY` is not set or the builder profile does not enable SLT integration.

- **Base:** `${SLT_BASE_ID}`
- **Table:** `tblasgjUjadHCqzrg` (Meeting Actions)
- **Auth:** `AIRTABLE_API_KEY` env var

**CRITICAL — query pattern gotchas:**
- `{assignee_name}` in `filterByFormula` silently fails with `INVALID_FILTER_BY_FORMULA: Unknown field names: assignee_name`. Display name drifts from schema doc.
- Safe default: filter on `{status}` only, return fields by ID with `returnFieldsByFieldId=true`, then Python-filter by assignee name.

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 -c "
import httpx, os, urllib.parse

key = os.environ['AIRTABLE_API_KEY']
BASE = '${SLT_BASE_ID}'
TABLE = 'tblasgjUjadHCqzrg'

formula = \"AND(NOT({status}='Completed'),NOT({status}='Not doing'))\"
fields = ['fldiPWq8q3NXyNXil',  # action_description
          'fldJleDMJFfcj5gPN',  # status
          'fldXZJaatwC9FNbtX',  # due_date
          'fldmpu3lN0lrgrdSa',  # assignee_name
          'fldJ1EKcHoncBtkoo',  # Priority
          'fldJpobWjo3J7uWuc',  # action_type
          'fldZlxizRCZnHvWH0']  # meeting
field_params = '&'.join(f'fields[]={fid}' for fid in fields)

all_records = []
offset = None
while True:
    u = f'https://api.airtable.com/v0/{BASE}/{TABLE}?filterByFormula={urllib.parse.quote(formula)}&{field_params}&returnFieldsByFieldId=true&pageSize=100'
    if offset: u += f'&offset={offset}'
    r = httpx.get(u, headers={'Authorization': f'Bearer {key}'}, timeout=30)
    all_records.extend(r.json().get('records', []))
    offset = r.json().get('offset')
    if not offset: break

my_actions = [r for r in all_records if os.environ.get('BUILDER_NAME', '') in (r.get('fields', {}).get('fldmpu3lN0lrgrdSa') or '')]
# Carry record IDs forward for Step 4a promotion.
"
```

**Classify into 3 morning-relevant buckets:**
1. **Overdue** — `due_date < today` and status ≠ Completed
2. **Today / retreat-critical** — dated ≤ today + 2 days, OR no due date but description mentions retreat/offsite/Tue-Wed-Thu logistics with a known upcoming deadline
3. **Strategic backlog count** — everything else. Don't bullet; just report count.

**Carry each record's Airtable record ID forward** so Step 4a can embed it in Asana shadow tasks for close-day sync.

**Sanity check:** Total open actions across all assignees should return 50-100+. If 0 or errors, formula reverted to field IDs — switch back to the pattern above.

**2k. Apple Health — yesterday's body metrics**

If the `apple-health` MCP is configured (`~/.claude.json` contains `mcpServers.apple-health`), pull yesterday's summary:

```
mcp__apple-health__apple_health_daily(date="YYYY-MM-DD")  # yesterday's date
```

If the response contains `{error: ...}` (no data for that day yet), skip this step silently and omit the "Yesterday's body" line from Step 3 + the health frontmatter from Step 6. Don't surface the error to the builder.

Extract these fields for use in Steps 3 and 6:

| Source path in response | Variable |
|---|---|
| `activity.steps` | `steps` |
| `activity.exercise_min` | `exercise_min` |
| `activity.active_energy_kcal` | `active_energy_kcal` |
| `sleep.total` (e.g. `"6h 32m"`) | parse to `sleep_total_hrs` (decimal) |
| `sleep.deep` (e.g. `"1h 9m"`) | parse to `sleep_deep_hrs` (decimal) |
| `sleep.rem` (e.g. `"1h 33m"`) | parse to `sleep_rem_hrs` (decimal) |
| `heart.hrv_ms` | `hrv_ms` |

Compute `sleep_restorative_pct`:
```
restorative_pct = round((sleep_deep_hrs + sleep_rem_hrs) / sleep_total_hrs * 100) if sleep_total_hrs else None
```

Restorative % (deep + REM as share of total sleep) is the closest proxy to "sleep quality score" derivable from Apple Health stage data. Typical healthy range: 25-50%.

**2l. Quarterly goal anchor cues**

Read active personal goal files from `$OBSIDIAN_VAULT_PATH/10-strategy/goals/*.md` (skip `personal-goals.md`, `work-goals.md`, anything in `archive/`). Filter to `status: active` AND `category: personal`.

For each, parse the `anchor:` frontmatter field. Match against today's day-of-week to decide if today is an anchor day:

- Anchor phrases like `"Mon/Wed/Fri 7:45am"` → today (DOW) matches Mon, Wed, or Fri → fire cue
- Anchor phrases like `"After morning coffee, weekdays"` → today is a weekday → fire cue
- Anchor phrases like `"Sunday evening, before kids' bedtime"` → today is Sunday → fire cue
- Anchor phrases that mention specific events ("After SLT meeting") → check today's calendar for that event

If an anchor fires today, carry forward to Step 3 as a `goal_cues` list:

```python
goal_cues = [{
    "slug": "vo2-max",
    "title": "Hold and improve VO2 max",
    "anchor": "After walking Red, Mon/Wed/Fri 7:45am",
    "weekly_action": "2x zone-2 + 1x intervals",
    "fires_today_because": "today is Wednesday",
}, ...]
```

Skip this step silently if no goal files exist or none fire today.

### Step 3: Draft Morning Check-in

Present to the builder. If AI suggestions were seeded by close-day, show them first:

```markdown
## Morning Check-in

### Yesterday's body
Sleep: [Xh Ym] ([Z]% restorative) · Exercise: [N] min · Steps: [N,NNN]

### Goal cues today
*Populated from Step 2l. Skip entirely if no anchors fire today.*

For each `goal_cues` entry:
- **[Goal title]** — anchor fires today ([fires_today_because]). Action: **[weekly_action]** at [anchor time/event].

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

### Coaching Actions for Today

After displaying today's meetings, collect the names of all attendees who are NSLS people, and pass them to the coaching-action surfacer:

```bash
# First make sure the action cache is fresh — extract from current profiles
OPERATING_USER_EMAIL=$(grep '^OPERATING_USER_EMAIL=' ~/.claude/local-plugins/nsls-personal-toolkit/.env | cut -d= -f2 | tr -d '"') \
OBSIDIAN_VAULT_PATH="$OBSIDIAN_VAULT_PATH" \
python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/extract_coaching_actions.py 2>/dev/null

# Then surface up to 3 actions, prioritized by today's calendar
echo "$ATTENDEE_NAMES" | python3.12 \
  ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/surface_actions_for_day.py \
  --people-stdin
```

The script returns JSON with `surfaced_actions` (up to 3 actions, distributed across scheduled people) and `sweep_status` (last biweekly sweep result).

**Format in the morning note:**

```
👥 Coaching Actions for Today

  🎯 [Person] ([dimension]): [action text]
     (from "[goal title]")

  🎯 [Person] ([dimension]): [action text]
     (from "[goal title]")
```

**Rules:**
- Hard cap: 3 actions across all today's people-meetings
- Distribute across people first (one per scheduled person before stacking)
- Two-way coaching: if your manager is in today's calendar (e.g., Gary 1:1),
  their managing-up actions surface here too
- If `sweep_status.exit_code != 0` or last sweep was >18 days ago, show a
  one-line alert: `⚠️ Last person-intelligence sweep failed/stale — run
  /person-intelligence biweekly sweep`
- If `surfaced_actions` is empty AND no sweep error, skip this section entirely

### Management — today's people (Signal)

Only runs when `SIGNAL_INGEST=1`. For the **direct reports on today's calendar**, pull
live Signal (Quick Notes) and surface the three jobs a great manager does each touchpoint:
celebrate a win, develop toward a goal, remove a friction. Same `$ATTENDEE_NAMES` as above.

```bash
SIGNAL_INGEST=1 OBSIDIAN_VAULT_PATH="$OBSIDIAN_VAULT_PATH" \
echo "$ATTENDEE_NAMES" | python3.12 \
  ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/surface_management_for_day.py \
  --people-stdin --weeks 4
```

Returns `{enabled, buckets:[{person, celebrate, develop, unblock:{text,streak}, cadence_flag,
sentiment_flag}], top3_candidates}`. Raw Quick Notes never touch the vault — the script returns
only the already-distilled, sensitivity-screened fields.

**Format in the morning note** (skip the section entirely if `enabled:false` or `buckets` empty):

```
🧭 Management — today's people

  [Person]
    🎉 Celebrate: [celebrate] — say it in their preferred channel today
    🌱 Develop:   [develop.text] (from "[develop.goal_title]")
    🔧 Unblock:   [unblock.text] (streak [N] wks) — own a fix + close the loop
    ⚠ [cadence_flag / sentiment_flag, if present]
```

**Rules:**
- One line per bucket; drop any bucket that's null for that person.
- **Feed the Top 3:** every entry in `top3_candidates` (friction streak ≥3 or a novel sentiment
  low on a direct report) is a candidate for the Morning Top 3 below — a recurring blocker on a
  report is high-leverage, only-you work. Name it in the Top 3 if present.
- A `cadence_flag` ("no Quick Notes in ≥2 wks" / "not submitting") is a check-in prompt — surface
  it even if the person has no other bucket.
- This complements Coaching Actions above (which is goal-driven); Management is signal-driven.
  If a person appears in both, fold into one block under their name.

### Slack follow-ups
*Populated only if Step 2i found anything. Outstanding asks and unverified commitments surface here so the day starts with the threads visible.*

### Morning Top 3 (fresh from Asana + calendar + carry-overs)
1. [P1 — explain why it's #1]
2. [Next most important]
3. [Third — balance strategic and tactical]

*Based on: [N] overdue Asana tasks, [N] carry-overs from yesterday.*

### Overdue ([count])
- [ ] [Task] (due [date]) — [project]

### SLT Meeting Actions ([N] open)
**Overdue:**
- [ ] [Action] (due [date], [N weeks overdue]) — `recXXX`

**Today / retreat-critical:**
- [ ] [Action] — `recXXX`

*+[N] in strategic backlog. Full list in Airtable `${SLT_BASE_ID}/tblasgjUjadHCqzrg`.*

### Open PRs ([waiting] waiting, [yours] yours)

*Skip this entire section if both lists are empty.*

**Waiting on your review:**
- `repo#NN` — author — Title (opened YYYY-MM-DD, [N]d open)

**Yours sitting open:**
- `repo#NN` — Title (opened YYYY-MM-DD, [N]d open) ⚠️ if >7d

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

**Project mapping for Top 3:** Every Top 3 item should be traced to a project when possible. Use the stack rank file (Step 2f) plus `20-projects/` folder listing as the source of truth.
- If the priority clearly maps to a project with a home at `20-projects/<slug>/<slug>.md`, write it as `[Priority description] — [[<slug>]] *(week rank: N)*`.
- If the project is in this week's Top 5 stack rank, show the rank (`*(week rank: 3)*`).
- If the project exists but isn't in this week's Top 5, show `*(not in week's Top 5)*` — this is an explicit signal the builder is spending a Top 3 slot on something not ranked for the week (sometimes right, sometimes a drift to flag).
- If no project home exists (pure people work, goals, one-off tasks), omit the link and rank annotation.
- Example: `"Get Chelsea comp package settled — [[product-team-recruiting]] *(week rank: 5)*"`

Ask the builder to confirm the project mapping if ambiguous rather than guessing silently.

**Vitality suggestions:** Base these on patterns. If close-day shows coding was 60%+ yesterday, suggest movement. If meetings were 50%+, suggest solo time. If no learning captures in recent days, suggest growth. Default to suggesting at least one movement activity.

**Operating memo check (if strategy layer active):**
Read `10-strategy/operating-memo.md`. Scan today's proposed Top 3 against "I Don't" and "My Traps" sections. If a proposed priority matches a trap pattern, flag it:
> "Heads up: [priority] looks like it falls in your 'I Don't' list. Your memo says: '[quote from memo]'. Still want to include it, or is there a way to teach/delegate instead of doing?"

Also check the teach/delegate/do ladder: if a priority is maintenance work on a project with role containing "->", suggest: "Could you pair with [collaborator] on this instead of doing it solo? Your memo says teach first."

### Step 4: The builder reviews and adjusts

You set your actual Top 3, energy level, and vitality intentions. The AI and morning suggestions are starting points — you may adopt, modify, or completely replace them.

### Step 4a: SLT → Asana shadow creation (if SLT actions were pulled in Step 2i)

After the builder confirms their Top 3 and before scheduling, check whether any Top 3 item corresponds to an open SLT Meeting Action, and whether the builder wants any overdue/retreat-critical SLT items mirrored to Asana for today's flow.

**Present a promotion menu:**

```
🧠 SLT Meeting Actions to shadow in Asana?

Top 3 matches detected:
  [1] "Retreat logistics lockdown" → matches 4 SLT actions:
      - rec123 "Order Thu lunch via Katie's sheet"
      - rec456 "Bring wired setup for offsite tech"
      - rec789 "Schedule buddy check-ins w/ Chelsea"
      - recABC "Research non-Bluetooth speaker-attributed recorder"

Other SLT items ripe for promotion:
  - recDEF "Follow up with Matt MacInnis at Rippling" (overdue 5+ weeks)
  - recGHI "Email Anish & Heather re: Red's comp"

Which should I shadow to Asana? (comma list of rec IDs, "all", or "none")
```

For each selected SLT action, create an Asana companion task:

```
mcp__claude_ai_Asana__create_task_preview(
  taskName="[action_description]",
  assignee="me",
  dueDate="YYYY-MM-DD",
  description="Priority: [P1/P2/P3 inferred from Top 3 placement]
Source: SLT Meeting
SLT record: recXXX
Context: [meeting_title from linked meeting] — [why this matters today]"
)
```

Then confirm with `create_task_confirm` (workspace `${ASANA_WORKSPACE_GID}`).

**CRITICAL — the `SLT record: recXXX` line format is load-bearing.** `/close-day` Step 7d parses Asana task notes for exactly this pattern (case-sensitive, followed by a record ID starting with `rec`) to close the loop back to Airtable when the task is marked complete. Don't reformat it as "SLT: rec..." or "Airtable: rec..." — close-day won't match.

**Deduplication:** Before creating, search Asana for open tasks whose notes already contain the same `SLT record: recXXX` line. If found, skip (already shadowed). This prevents creating duplicate companions day after day.

**After creation:** Proceed to scheduling. The promoted SLT items now appear in today's Asana flow and are included in the scheduling pool the same as any other Top 3 item.

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
---
sleep_total_hrs: 6.5
sleep_restorative_pct: 38
sleep_deep_hrs: 1.15
sleep_rem_hrs: 1.55
exercise_min: 29
steps: 5811
active_energy_kcal: 429
hrv_ms: 61
---
# YYYY-MM-DD — [Day of Week]

## Morning Check-in
- Yesterday: [6h 32m] sleep ([38]% restorative) · [29] min exercise · [5,811] steps
- Mood: [builder's input]
- Goal cues today: [one-line summary per firing goal, OR "—" if none fire]

### AI Suggested: Top 3 (from [previous day]'s close)
[preserved from close-day seed if it existed]

### AI Suggested: Delegate These
[preserved from close-day seed if it existed]

### My Top 3
1. [Priority #1 description] — [[project-slug]] *(week rank: N)*
2. [Priority #2 description] — [[project-slug]] *(week rank: N)*
3. [Priority #3 description] — [[project-slug]] *(week rank: N)*

*Link the project and surface the week rank when a project home exists. Use `*(not in week's Top 5)*` for active projects outside the stack rank. Omit link/rank for pure people work or goals with no project home.*

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

**Health frontmatter rules:**
- The eight `sleep_*`, `exercise_min`, `steps`, `active_energy_kcal`, `hrv_ms` keys come from Step 2k. Use YAML `null` for any value Apple Health didn't provide for yesterday (e.g., `hrv_ms: null`).
- If Step 2k was skipped entirely (no MCP, no data), omit the whole frontmatter block AND drop the "Yesterday:" line from Morning Check-in.
- **If the daily note already exists** (close-day seeded it last night) and has existing frontmatter, merge: update the health keys, preserve everything else. If it has no frontmatter, prepend the block.
- These keys are graphable via the Obsidian Tracker plugin or Dataview — they're stored in structured frontmatter specifically so trends across daily notes can be charted without re-parsing the body.

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
