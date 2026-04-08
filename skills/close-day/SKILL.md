---
name: close-day
description: >-
  Automated end-of-day summary — pulls Google Calendar, Familiar screen captures,
  Fathom meeting summaries, sent email, sent Slack messages, and Claude session
  context to generate a daily note and update project session logs. Trigger
  phrases: close day, end of day, daily summary, wrap up, what did I do today,
  close out the day, daily close, eod
---

# Daily Close

Synthesize your full day from seven data sources into a daily note and project session updates. Write carry-over tasks to Asana.

## Data Sources

| Source | What It Covers | Access Method |
|--------|---------------|---------------|
| **Google Calendar** | Meetings scheduled, attendees, times | `gcal_list_events` MCP tool |
| **Familiar** | Screen activity — apps used, window titles, URLs, time distribution | Bash: scan `$HOME/familiar/stills-markdown/session-YYYY-MM-DDT*/*.md` frontmatter |
| **Fathom** | Meeting summaries, topics, action items, decisions | Bash: Python script calling Fathom API (see below) |
| **Sent Email** | Approvals, decisions, outbound communications | `gmail_search_messages` MCP tool (`from:me after:YYYY/M/DD before:YYYY/M/DD+1`) |
| **Sent Slack** | Conversations, decisions, coordination, context | `slack_search_public_and_private` MCP tool (`from:<@$SLACK_USER_ID> on:YYYY-MM-DD`) |
| **Asana** | Pending tasks, overdue items, what was due today | `mcp__claude_ai_Asana__get_my_tasks` and `mcp__claude_ai_asana__asana_search_tasks` MCP tools |
| **Claude session context** | What was built, decided, and discussed in this conversation | Conversation history in current session |

## Asana Reference

Read these from `~/.claude/local-plugins/nsls-personal-toolkit/.env`:
- **Workspace GID:** `$ASANA_WORKSPACE_GID`
- **User GID:** `$ASANA_USER_GID`

---

## Step-by-step Execution

### Step 0: Determine the date

Default to today (`date +%Y-%m-%d`). User can override: `/close-day 2026-03-21`.

### Step 1: Collect data (run in parallel where possible)

**1a. Google Calendar — today's meetings**

Use the `gcal_list_events` MCP tool:
```
gcal_list_events(
  timeMin="YYYY-MM-DDT00:00:00",
  timeMax="YYYY-MM-DDT23:59:59",
  timeZone="America/New_York"
)
```
Extract: meeting title, start/end time, attendees (if `condenseEventDetails=false`).

**1b. Familiar — screen activity, time tracking, and work categorization**

This step produces three outputs: (1) app/tool time distribution, (2) total active work hours, and (3) a work-category breakdown by department/function.

**Builder profile:** Before categorizing, read the builder's profile from their Obsidian vault at `$OBSIDIAN_VAULT_PATH/50-reference/builder-profile.md`. This file defines:
- `time_categories` — the work categories to use (varies by role: executive, department lead, manager, IC)
- `time_tracking_mode` — what summary line to produce (doing-vs-orchestrating, deep-vs-meetings, etc.)
- `data_sources` — which integrations are available (familiar, fathom, slack, etc.)

If no builder profile exists, fall back to the **Executive / SLT preset** categories (Coding/Building, Management/People, Product Management, Marketing/Sales, Admin/Ops, Learning/Research) — this is the default for backwards compatibility with the user's setup.

**IMPORTANT — Fathom dependency:** Step 1c (Fathom) must complete before the work categorization in this step, because Fathom meeting summaries are used to categorize Zoom/Meet time into the correct work category. Run the data collection (bash commands below) in parallel with Fathom, but defer the categorization logic until Fathom results are available. If the builder profile has `fathom: false`, skip the Fathom dependency and categorize meetings by window title only.

**Phase 1: Collect raw data (run in parallel with Fathom)**

```bash
# Step 1: Get top-level app counts
grep -h "^app:" $HOME/familiar/stills-markdown/session-YYYY-MM-DDT*/*.md 2>/dev/null \
  | sort | uniq -c | sort -rn

# Step 2: Break down Chrome by window title
awk '/^app: Google Chrome/{found=1} found && /^window_title_raw:/{print; found=0}' \
  $HOME/familiar/stills-markdown/session-YYYY-MM-DDT*/*.md 2>/dev/null \
  | sort | uniq -c | sort -rn

# Step 3: Break down Slack by window title (channel/DM names)
awk '/^app: Slack/{found=1} found && /^window_title_raw:/{print; found=0}' \
  $HOME/familiar/stills-markdown/session-YYYY-MM-DDT*/*.md 2>/dev/null \
  | sort | uniq -c | sort -rn

# Step 4: Break down Warp by window title (Claude Code session names)
awk '/^app: Warp/{found=1} found && /^window_title_raw:/{print; found=0}' \
  $HOME/familiar/stills-markdown/session-YYYY-MM-DDT*/*.md 2>/dev/null \
  | sort | uniq -c | sort -rn

# Step 5: Session timestamps for time calculation
for s in $HOME/familiar/stills-markdown/session-YYYY-MM-DDT*/; do
  first=$(ls "$s"*.md 2>/dev/null | head -1 | xargs basename | sed 's/.md//')
  last=$(ls "$s"*.md 2>/dev/null | tail -1 | xargs basename | sed 's/.md//')
  count=$(ls "$s"*.md 2>/dev/null | wc -l | tr -d ' ')
  echo "$first|$last|$count"
done
```

**Phase 2: Calculate active work time**

Use this algorithm to compute total active work hours from session data:

1. **Filter cron/screensaver noise:** Remove sessions with ≤3 captures AND duration < 30 seconds. These are typically automated wake-ups (often appearing at :29 or :59 past the hour every 30 min).
2. **Merge into work blocks:** Walk through remaining sessions chronologically. If the gap between the end of one session and the start of the next is ≤ 20 minutes, merge them into one continuous work block. Gaps ≤ 20 min represent short breaks (bathroom, coffee, thinking) — not leaving the desk. Include the gap time in the block duration.
3. **Filter trivial blocks:** Remove work blocks shorter than 5 minutes total — these are brief screen glances, not real work.
4. **Sum work block durations** = total active work hours.

Present work blocks as a compact list:
```
Work blocks: 03:31–11:50 (8.3h), 12:24–17:41 (5.3h)
Total active: 13.6 hours
```

**Phase 3: Categorize captures into work categories (after Fathom completes)**

Every capture gets assigned to exactly one **work category** based on app + window title. The categories represent the user's functional roles:

| Work Category | What maps here |
|---|---|
| **Coding / Building** | Warp (terminal/Claude Code), Claude (desktop app), GitHub, Railway, VS Code |
| **Management / People** | Slack DMs with direct reports, Slack `#nsls-leadership`, Gmail (people-related), Messages, 1:1 meetings (from Fathom), Google Docs that are work journals (e.g. "Journal", "Work Journal") |
| **Product Management** | Slack product/engineering channels (see list below), Figma, Airtable, Clay, product-related Google Docs, product/strategy meetings (from Fathom) |
| **Marketing / Sales** | Slack marketing channels (see list below), recruiting tools, marketing Google Docs, sales meetings (from Fathom) |
| **Admin / Ops** | Obsidian, Asana, Google Calendar, NetSuite, Ramp, billing dashboards, revenue reports, Calendly |
| **Learning / Research** | YouTube, news sites (NYT, CNN, The Athletic), Reddit, documentation sites, tech blogs |
| **Personal** | **EXCLUDE from all totals** — Charles Schwab, Chase, Mercury, Monarch, IRS, SBA, any brokerage/bank/tax/loan/personal finance site |

**Slack channel → category mapping:**

Slack window titles follow the pattern: `ChannelOrPerson (DM|Channel) - theNSLS - N new items - Slack`

| Slack pattern | Category |
|---|---|
| `(DM)` with a single person name | **Management / People** (default for 1:1 DMs) |
| `(DM)` with multiple people (group DM) | **Management / People** |
| Channel contains `marketing`, `lifecycle`, `life-cycle`, `brand`, `content`, `social` | **Marketing / Sales** |
| Channel contains `product`, `engineering`, `tech`, `dev`, `ai-workbench`, `cs-tech` | **Product Management** |
| Channel contains `leadership`, `slt`, `executive` | **Management / People** |
| Channel contains `general`, `random`, `announcements` | **Admin / Ops** |
| `Threads` | **Management / People** (usually follow-ups on DMs) |
| `Search` or `Ignite` (different workspace) | **Admin / Ops** |

**Meeting categorization (using Fathom results):**

Zoom window titles just say "Zoom Meeting" and Google Meet shows the meeting name. To categorize meeting time:

1. Match Zoom/Meet capture timestamps against Fathom meeting time ranges.
2. Use the Fathom meeting title + summary to assign a category:
   - Titles containing "1:1", "1-1", "check-in", person names → **Management / People**
   - Titles containing "product", "roadmap", "sprint", "design review" → **Product Management**
   - Titles containing "marketing", "campaign", "brand", "content" → **Marketing / Sales**
   - Titles containing "board", "investor", "strategy", "all-hands", "SLT" → **Management / People**
   - Titles containing "standup", "sync" → check Fathom summary for topic, default to **Product Management**
3. Zoom/Meet captures that don't match any Fathom meeting → **Meetings (unmatched)** — show separately so the user can mentally assign them.

**Chrome window title → category mapping:**

| Pattern in window_title_raw | Category |
|---|---|
| `YouTube` | Learning / Research |
| `Gmail` or `Leadership and Success Mail` | Management / People |
| `- Airtable` | Product Management |
| `Meet -` (with 🔊 or without) | Meetings — categorize via Fathom (see above) |
| `- NetSuite` | Admin / Ops |
| `- Google Docs` | Inspect title: journals/check-ins → Management; product specs → Product; default → Admin / Ops |
| `- Google Sheets` | Admin / Ops (default) or inspect title for context |
| `Google Calendar` or `endar - Week of` | Admin / Ops |
| `New York Times`, `The Athletic`, `CNN`, news domains | Learning / Research |
| `- Google Slides` | Inspect title: board/strategy decks → Management; product decks → Product |
| `GitHub` or `github.com` | Coding / Building |
| `Railway` | Coding / Building |
| `Figma` | Product Management |
| `Calendly` | Admin / Ops |
| `Claude` (web) | Coding / Building |
| `Fathom` | Admin / Ops |
| `Ramp` | Admin / Ops |
| `Charles Schwab`, `Schwab`, `chase.com`, `Chase`, `Mercury`, `Monarch`, `IRS`, `irs.gov`, `SBA`, `sba.gov` | **Personal — EXCLUDE** |
| Any brokerage, bank, tax, loan, or personal finance site | **Personal — EXCLUDE** |
| Unknown/other | Admin / Ops (catch-all) |

**IMPORTANT — Personal finance exclusion:** Always exclude ALL personal finance captures from the report and from all totals before computing percentages or hours. Company finance tools (NetSuite, Ramp) ARE included.

**Phase 4: Produce the Time Distribution and Time Allocation outputs**

**Time Distribution** (same as before — flat list of tools/apps sorted by capture count):
Present as a flat list sorted by capture count. Do NOT nest Chrome sub-categories under a "Chrome" parent — instead, show each category (YouTube, Gmail, Airtable, etc.) as a peer alongside Slack, Warp, Obsidian, etc. Only show categories with ≥1% of total captures.

**Time Allocation** (NEW — work category breakdown as a table):

```markdown
## Time Allocation

| Category | Hours | % | Top tools |
|---|---|---|---|
| Management / People | 4.1h | 30% | Slack DMs, Gmail, 1:1s |
| Coding / Building | 3.1h | 23% | Warp, Claude Code, GitHub |
| Admin / Ops | 1.7h | 13% | Obsidian, Calendar, NetSuite |
| Meetings | 1.6h | 12% | Zoom, Google Meet |
| Product Management | 1.5h | 11% | Figma, Airtable, product docs |
| Learning / Research | 1.4h | 10% | YouTube, news |
| Marketing / Sales | 0.1h | 1% | Recruiting |

**Active work: 13.6 hours** (3:31 AM – 5:41 PM)
Work blocks: 3:31–11:50 (8.3h), 12:24–5:41 (5.3h)
Doing vs. Orchestrating: 23% hands-on building, 42% managing/meeting, 35% admin/research
**Meeting time (calendar): ~7h across 9 meetings** (50% of active work)
```

The "Doing vs. Orchestrating" line is a quick summary:
- **Doing** = Coding / Building
- **Orchestrating** = Management / People + Meetings + Marketing / Sales
- **Supporting** = Admin / Ops + Learning / Research + Product Management

This gives the user a fast read on how much time he spent building things himself vs. directing others vs. overhead.

The **"Meeting time (calendar)"** line is an orthogonal metric — it cross-cuts all categories. A 1:1 with Chris counts as both "Management / People" time AND meeting time. This tells the user how much of his day was synchronous vs. async, regardless of topic. Derived from Google Calendar scheduled meeting times (not Familiar captures, which only see Zoom/Meet windows and miss categorized meetings). Solo calendar blocks (e.g., "Weekly processing", "Contract drafting") are excluded — only meetings with other attendees count.

**1c. Fathom — meeting summaries and action items**

Fetch today's meetings from Fathom using a focused Python script:

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 -c "
import httpx, json, os, sys
from pathlib import Path

# Get API key
key = os.environ.get('FATHOM_API_KEY', '')
if not key:
    env_file = Path.home() / 'nsls-skills/slt-ops/slt-bot/.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith('FATHOM_API_KEY='):
                key = line.split('=', 1)[1].strip().strip('\"\'')
                break
if not key:
    print('NO_API_KEY'); sys.exit(0)

TARGET_DATE = '$DATE'  # will be replaced by skill
headers = {'X-Api-Key': key}
url = f'https://api.fathom.ai/external/v1/meetings?include_summary=true&include_action_items=true&created_after={TARGET_DATE}T00:00:00Z&created_before={TARGET_DATE}T23:59:59Z'
meetings = []
cursor = None

while True:
    page_url = url + (f'&cursor={cursor}' if cursor else '')
    resp = httpx.get(page_url, headers=headers, timeout=30)
    if resp.status_code != 200: break
    data = resp.json()
    items = data.get('items') or (data if isinstance(data, list) else [])
    meetings.extend(items)
    cursor = data.get('next_cursor') if isinstance(data, dict) else None
    if not cursor: break

todays = meetings  # already date-scoped by API params

for m in sorted(todays, key=lambda x: x.get('scheduled_start_time', '')):
    title = m.get('title', 'Unknown')
    start = m.get('scheduled_start_time', '')
    end = m.get('scheduled_end_time', '')
    summary = (m.get('default_summary') or {}).get('markdown_formatted', '')
    actions = [a.get('description', '') for a in (m.get('action_items') or [])]
    attendees = [inv.get('name', '') for inv in (m.get('calendar_invitees') or []) if inv.get('name')]
    fathom_url = m.get('url', '')

    print(f'### {title}')
    print(f'**Time:** {start[11:16]}–{end[11:16] if end else \"?\"}')
    if attendees: print(f'**With:** {', '.join(attendees)}')
    if fathom_url: print(f'**Fathom:** {fathom_url}')
    if summary:
        # Extract just key takeaways, not full summary
        for line in summary.split('\n'):
            if line.strip().startswith('- [**') or line.strip().startswith('- **'):
                print(line.strip())
    if actions:
        print('**Action items:**')
        for a in actions: print(f'  - {a}')
    print()
"
```

**Fathom API is now date-scoped** — uses `created_after` and `created_before` params to fetch only the target day's meetings. This is fast (< 5 seconds) instead of paginating through all meetings since 2023.

**1d. Sent Email — outbound communications**

Use the `gmail_search_messages` MCP tool:
```
gmail_search_messages(
  q="from:me after:YYYY/M/DD before:YYYY/M/DD+1",
  maxResults=30
)
```
Extract: who was emailed, subject, and the snippet (which captures his reply). Look for approvals, decisions, delegations, and follow-ups.

**1e. Sent Slack — conversations and coordination**

Use the `slack_search_public_and_private` MCP tool:
```
slack_search_public_and_private(
  query="from:<@$SLACK_USER_ID> on:YYYY-MM-DD",
  sort="timestamp",
  limit=20,
  include_context=false
)
```
Your Slack user ID is read from `.env` (`SLACK_USER_ID`). Extract: who was messaged, what channels, key topics discussed. Group by conversation thread — don't list every individual message, summarize the thread topic. Distinguish work conversations from personal. Skip trivial messages ("ok", "thanks", reactions).

**1f. Claude session context**

Review the current conversation for:
- What was built or changed
- Key decisions made
- Projects touched (match against known project mappings from `/log` skill)
- Open items and next steps

Also check if any other Claude Code sessions ran today by scanning:
```bash
ls -la ~/.claude/projects/-Users-k/*.jsonl | grep "$(date +%b\ %d)" 2>/dev/null
```

**1g. Asana — pending tasks and what was due**

Run in parallel with other data collection. Two calls:

**Call 1: Get all incomplete tasks assigned to the user**
```
mcp__claude_ai_Asana__get_my_tasks(
  completed_since="now",
  limit=100,
  opt_fields="name,due_on,projects.name,assignee_section.name"
)
```

**Call 2: Search for tasks that were due today or are overdue**
```
mcp__claude_ai_asana__asana_search_tasks(
  assignee_any="me",
  completed=false,
  due_on_before="YYYY-MM-DD",  // the target date
  sort_by="due_date",
  sort_ascending=true,
  opt_fields="name,due_on,projects.name",
  limit=50
)
```

From the results, extract three lists:
1. **Overdue tasks** — incomplete tasks with `due_on` before today
2. **Due today** — tasks with `due_on` = today's date
3. **Upcoming** — tasks due in the next 3 days (context, not displayed unless relevant)

Include the overdue and due-today lists in the daily note's `## Asana` section. These inform the Carrying Over section and help the user see what slipped.

**Filtering:** Skip auto-generated noise like "It's time to update your goal(s)" — only include real tasks the user created or was assigned.

### Step 2: Identify projects touched

Match activity to projects using these signals (in priority order):

1. **Claude session context** — working directory and conversation topics
2. **Calendar meeting titles** — keyword match to project domains
3. **Familiar window titles** — pattern matching:
   - "Airtable" + people-ops keywords → `people-ops`
   - "Google Slides" + board keywords → `board-intelligence` or specific deck project
   - "GitHub" + repo name → match to project
   - "Slack" + channel name → match to project domain
4. **Familiar URLs** — match known URLs:
   - `airtable.com/$PEOPLE_OPS_BASE_ID` → `people-ops`
   - `airtable.com/$SLT_BASE_ID` → `meeting-automation`
   - GitHub repo URLs → match to project

Use the project mappings from `~/.claude/skills/log/SKILL.md` as the source of truth.

### Step 3: Draft the daily note

Generate in this format (matching the user's existing `01-daily/` structure):

```markdown
# YYYY-MM-DD — [Day of Week]

## Time Allocation

| Category | Hours | % | Top tools |
|---|---|---|---|
| [Category] | [X.Xh] | [XX%] | [top 2-3 tools] |
| ... | | | |

**Active work: [X.X] hours** ([first block start] – [last block end])
Work blocks: [HH:MM–HH:MM (X.Xh), ...]
Doing vs. Orchestrating: [X%] hands-on building, [X%] managing/meeting, [X%] admin/research
**Meeting time (calendar): ~[X]h across [N] meetings** ([X%] of active work)

## Time Distribution
- [Category]: [percentage] ([capture count] captures)
- [Category]: [percentage] ([capture count] captures)
- ...
- Other: [percentage] ([count] captures)

## Meetings ([count])
[For each meeting from Calendar + Fathom:]
- **HH:MM–HH:MM** — [Title] (with [attendees])
  - [Key takeaway from Fathom summary, 1-2 bullets max]
  - Action: [any action items assigned to the user]

## Work Log
[From Claude sessions + Familiar + sent email + sent Slack:]
- [Concrete accomplishment — what was built/decided/shipped]
- [Concrete accomplishment]
- [Non-Claude work detected from Familiar — e.g., "Reviewed board deck in Google Slides (~20min)"]
- [Decisions/approvals from sent email — e.g., "Approved Fathom/Zoom fix (Jim Corriveau)"]
- [Coordination from Slack — e.g., "Sent Red's contractor info to Heather for onboarding"]

## Asana
**Overdue:**
- [ ] [Task name] (due [date]) — [project if any]

**Due today:**
- [ ] [Task name] — [project if any]

## Projects Touched
- [[20-projects/[slug]|[slug]]] — [1-line summary of what happened]
- [[20-projects/[slug]|[slug]]] — [1-line summary]

## Carrying Over
- [Unfinished items from Claude tasks, meeting action items, or Asana overdue]

## End of Day
- Energy:

### AI Suggested: Tomorrow's Top 3 (strategic, high-leverage, high-priority)
1. **[Highest-impact item]** — [Why only the user can do this. What it blocks or unlocks.]
2. **[Second item]** — [Strategic rationale.]
3. **[Third item]** — [Strategic rationale.]

### AI Suggested: Delegate These
1. **[Task]** → [Person] — [Why they're the right owner. What the user's role becomes (review/approve).]
2. **[Task]** → [Person] — [Rationale.]
3. **[Task]** → [Person] — [Rationale.]

### My Top 3 (user fills in)
1.
2.
3.
```

**Rules:**
- Keep the Work Log to concrete outputs, not activities. "Imported 40-file board knowledge base to Obsidian" not "worked on Obsidian."
- Meeting bullets come from Fathom summaries — pull only the 1-2 most important takeaways, not the full summary.
- **Time Allocation** is the new primary time view. It shows work categories (Coding/Building, Management/People, etc.) with estimated hours, percentages, and top tools. The "Doing vs. Orchestrating" summary line gives the user a fast read on CEO time allocation. See Step 1b Phase 4 for the full format and category definitions.
- **Time Distribution** still appears below Time Allocation as a flat tool-level breakdown. Uses categorized captures, not raw app names. Chrome captures are broken down by window title into meaningful categories (Gmail, YouTube, Airtable, Google Docs, etc.) and presented as flat peers alongside Slack, Warp, Obsidian, etc. Never show "Google Chrome: X%" — that's useless. Round to whole numbers. Only show categories with ≥1% of total captures. Always **exclude personal finance** captures from the report and totals.
- The `## Morning Check-in` section from the user's template is NOT auto-generated — that's for the start of day.
- **Sent Email:** Include approvals, decisions, and delegations as Work Log bullets. Skip routine replies that don't represent a decision or action.
- **Sent Slack:** Summarize by conversation thread/topic, not individual messages. Skip trivial messages ("ok", "thanks", single emoji). Focus on decisions, coordination, and substantive discussions. Group DMs with personal contacts (family) should be noted briefly or omitted — the user can decide. Flag any coaching/leadership conversations as those are often important context.
- **AI Suggested Top 3:** Generate 3 strategic priorities for tomorrow based on carry-overs, meeting action items, deadlines, and Asana. Filter for items that are (a) high-impact/high-leverage, (b) fit the user's unique skills as CEO — relationship decisions, strategic judgment calls, cross-team visibility, contract/legal calls. Explain *why* each is high-priority and what it blocks/unlocks.
- **AI Suggested Delegate:** Generate 3 important items someone else could own. Name the person and why they're the right fit. the user's role becomes review/approve, not execute. Look for: operational tasks with a clear domain owner, first-draft work where the user adds value in editing not creating, technical setup that doesn't require strategic judgment.
- **My Top 3:** Always left blank for the user to fill in manually after reviewing the AI suggestions. The user may adopt, modify, or completely replace the AI suggestions.

### Step 4: Present draft to user

Show the full daily note draft. Ask:
- "Anything to add or correct?"
- "Ready to write?"

### Step 5: Write daily note

Write to: `$OBSIDIAN_VAULT_PATH/01-daily/YYYY-MM-DD.md`

**If the file already exists** (user started it in the morning with priorities), **merge** — keep the existing Morning Check-in section and append/update the generated sections below it.

### Step 6: Update project session logs

For each project touched, check if a session log exists for today:
- **Exists:** Append a `---` separator and add today's project-specific bullets
- **Doesn't exist:** Create a new session log following the `/log` skill format

Also update each project's home note:
- `last-touched: YYYY-MM-DD`
- `next-action:` if there's a clear next step
- Add `[[sessions/YYYY-MM-DD|YYYY-MM-DD]]` to the Sessions list

### Step 7: Sync Asana — complete, comment, and create

This step does three things: marks finished tasks done, adds progress notes to in-progress tasks, and creates new tasks from carry-overs.

**7a. Complete finished tasks**

Cross-reference the day's Work Log against the user's open Asana tasks (fetched in Step 1g). For each Asana task that was clearly completed today, mark it done:

```
mcp__claude_ai_Asana__update_tasks(
  tasks=[{"task": "[GID]", "completed": true}]
)
```

**How to match:** Compare Asana task names against Work Log bullets, sent emails, Fathom action items marked done, and Claude session accomplishments. Be conservative — only mark complete if there's clear evidence the task is finished, not just worked on.

**7b. Comment on in-progress tasks**

For Asana tasks that the user worked on but didn't finish, add a progress comment:

```
mcp__claude_ai_asana__add_comment(
  task_id="[GID]",
  text="Progress 3/25: [what was done]. Remaining: [what's left]."
)
```

This keeps Asana as a living record of where things stand.

**7c. Create new carry-over tasks**

For each item in **Carrying Over** that doesn't already exist in Asana, create it with priority and due date:

```
mcp__claude_ai_Asana__create_task_preview(
  taskName="[carry-over item]",
  assignee="me",
  dueDate="YYYY-MM-DD",
  description="Priority: [P1/P2/P3]\nSource: [meeting / email / Claude session]\nContext: [1-line why this matters]"
)
```

Then confirm with `mcp__claude_ai_Asana__create_task_confirm` using workspace `$ASANA_WORKSPACE_GID`.

**Priority framework (CEO lens):**

| Priority | Due Date | Criteria |
|----------|----------|----------|
| **P1 — Do today/tomorrow** | Next business day | Revenue impact, board/investor commitment, blocking others, legal/compliance deadline, key hire decision |
| **P2 — This week** | End of current week (Friday) | Strategic initiative milestone, team unblocked by this, partner/vendor commitment, product launch dependency |
| **P3 — Next week+** | Next Monday or specific date from context | Internal process improvement, nice-to-have follow-up, research/exploration, relationship maintenance |

**Priority inference rules:**
- Commitments made to external parties (board, partners, candidates) → P1
- Meeting action items the user owns with a stated deadline → use that deadline, infer priority from urgency
- Contract/legal/hiring items → P1-P2 (time-sensitive by nature)
- Internal tooling, automation, documentation → P2-P3
- "Would be nice to" or "explore" language → P3
- If a carry-over item was also carry-over from a previous day → bump priority up one level

**Rules for Asana write-back:**
- **Only create tasks for actionable items the user owns.** Skip items that are someone else's action (e.g., "Davo sends proposal").
- **Don't duplicate.** Before creating, search Asana for similar task names. If a match exists, skip (or comment on it instead).
- **Include source context** in the description so the user knows where the task came from.
- **Present the full Asana sync plan to the user** before executing. Show three columns:

```
✅ Complete (2):
  - "Schedule 1:1 with Chris" (GID: 123) — met with Chris today
  - "Draft SNHU deck" (GID: 456) — deck sent to team

💬 Progress update (1):
  - "Automation tracker skill" (GID: 789) — "Built registration form, still need builder import"

➕ Create new (3):
  - "Draft Davo Wood contract w/ IP carve-outs" — P1, due 3/27
  - "Package Obsidian template for Joe" — P2, due 3/28
  - "Create GitHub repo for Red's feedback bot" — P3, due 3/31
```

User approves, modifies, or skips before any Asana writes happen.

### Step 8: Seed tomorrow's daily note

Check if tomorrow's note exists at `$OBSIDIAN_VAULT_PATH/01-daily/YYYY-MM-DD+1.md`. If it does NOT exist, create it with this template:

```markdown
# YYYY-MM-DD+1 — [Day of Week]

## Morning Check-in
- Energy:

### AI Suggested: Tomorrow's Top 3 (from last night's close)
1. **[Item 1 from today's AI suggestions]**
2. **[Item 2]**
3. **[Item 3]**

### AI Suggested: Delegate These
1. **[Item 1]** → [Person]
2. **[Item 2]** → [Person]
3. **[Item 3]** → [Person]

### My Top 3
1.
2.
3.

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

This seeds the next day with the AI-suggested priorities so the user sees them first thing in the morning. He overwrites "My Top 3" with his actual priorities during `/open-day` or manually.

If the file already exists (user or `/open-day` already created it), do NOT overwrite. Instead, check if it has the AI suggestion sections. If not, insert them after `## Morning Check-in`.

### Step 9: Write sentinel file

After successfully writing the daily note, write the sentinel so the 10 PM automated run skips:

```bash
touch /tmp/close-day-YYYY-MM-DD.done
```

This prevents the launchd auto-close-day from re-running if the user already ran `/close-day` manually.

### Step 10: Confirm

Report: "Daily note written to `01-daily/YYYY-MM-DD.md`. Seeded tomorrow's note at `01-daily/YYYY-MM-DD+1.md`. Updated session logs for: [project list]. Asana: [N] completed, [N] updated, [N] created."

---

## Performance Notes

- **Familiar scanning is fast** — grepping frontmatter across 1000+ files takes < 2 seconds. Do NOT read OCR content unless the user asks for specific recall.
- **Fathom API is slow** — full paginated fetch can take 30-60 seconds. If the user ran `/close-day` already today, skip re-fetching.
- **Calendar is instant** — MCP tool returns in < 1 second.
- **Asana is fast** — MCP tools return in < 2 seconds.
- **The 7-day retention** — Familiar auto-cleans stills after 7 days (`storageAutoCleanupRetentionDays: 7`). Daily notes capture the signal before the raw data expires.

## Edge Cases

- **No meetings today:** Skip the Meetings section entirely.
- **No Familiar data:** Skip Time Distribution, note "No screen capture data available."
- **Weekend/light day:** Still generate — even a short note like "Light day. 2 hours of email and Slack." is valuable for continuity.
- **Multiple Claude sessions:** Check jsonl file dates. Summarize each session's contribution.
