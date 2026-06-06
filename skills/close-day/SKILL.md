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

Synthesize the builder's full day from seven data sources into a daily note and project session updates. Write carry-over tasks to Asana.

## Data Sources

| Source | What It Covers | Access Method |
|--------|---------------|---------------|
| **Google Calendar** | Meetings scheduled, attendees, times | `gcal_list_events` MCP tool |
| **Familiar** | Screen activity — apps used, window titles, URLs, time distribution | Bash: scan `$HOME/familiar/stills-markdown/session-YYYY-MM-DDT*/*.md` frontmatter |
| **Fathom** | Meeting summaries, topics, action items, decisions | Bash: Python script calling Fathom API (see below) |
| **Sent Email** | Approvals, decisions, outbound communications | `gmail_search_messages` MCP tool (`from:me after:YYYY/M/DD before:YYYY/M/DD+1`) |
| **Sent Slack** | Conversations, decisions, coordination, context | `slack_search_public_and_private` MCP tool (`from:<@${SLACK_USER_ID}> on:YYYY-MM-DD`) |
| **Asana** | Pending tasks, overdue items, what was due today | `mcp__claude_ai_Asana__get_my_tasks` and `mcp__claude_ai_asana__asana_search_tasks` MCP tools |
| **Apple Health** | Personal-goal execution: workouts, exercise minutes, distance, HR, sleep, VO2 max | `mcp__apple-health__apple_health_workouts` and `mcp__apple-health__apple_health_daily` MCP tools |
| **Claude session context** | What was built, decided, and discussed in this conversation | Conversation history in current session |

## Builder Context

Read these from `~/.claude/local-plugins/nsls-personal-toolkit/.env` before running any subsequent step, then substitute `${VAR_NAME}` references throughout this skill with the actual values:

- `${OBSIDIAN_VAULT_PATH}` — vault location (used by daily note writes + session log scans)
- `${SLACK_USER_ID}` — Slack user ID (used in `from:` / `to:` search queries)
- `${ASANA_WORKSPACE_GID}` — Asana workspace
- `${ASANA_USER_GID}` — Asana user
- `${PEOPLE_OPS_BASE_ID}` — People Ops Airtable base
- `${SLT_BASE_ID}` — SLT Meeting Intelligence Airtable base (Step 1h SLT Meeting Actions sync)

Also read `${OBSIDIAN_VAULT_PATH}/50-reference/builder-profile.md` for role/categories/timezone — the categorization logic in Step 1b depends on it.

---

## Step-by-step Execution

### Step 0: Determine the date

Default to today (`date +%Y-%m-%d`). Override by passing the date as an argument: `/close-day 2026-03-21`.

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

**Classify each calendar event as a real meeting or a solo block:**

| Classification | Detection rules | Examples |
|---|---|---|
| **Real meeting** | Has attendees other than Kevin (`attendees` array with 2+ entries, or 1 entry that isn't Kevin) AND has a conferenceUrl or Zoom/Meet link | NSLS Coach Feedback Discussion, Gary / Kevin — FOL, All Staff Meeting |
| **Solo block** | No attendees (Kevin is sole organizer, no `attendees` array), OR description contains "from /open-day", "Priority #N from /open-day", "Vitality block", "Growth block" | Focus: William reply, Prep: Gary FOL, Walk, Learn: Agentic harnesses |

Solo blocks created by `/open-day` are work time, not meetings. They typically appear as gray or colored blocks on the calendar with titles starting with "Focus:", "Prep:", "Walk", "Learn:", or "Review:".

**Impromptu meetings from Fathom:** Some meetings appear in Fathom but NOT on the calendar (e.g., ad-hoc Zoom calls). These are detected in Step 1c. They count as real meetings and should be included in the meeting count and the `## Meetings` section. Cross-reference Fathom results against calendar events by time overlap — any Fathom meeting without a matching calendar event is an impromptu.

The **meeting count** and **meeting time** metrics should include:
- Calendar events classified as real meetings (by attendee detection)
- Impromptu meetings from Fathom (not on calendar)

And should EXCLUDE:
- Solo calendar blocks (focus/prep/walk/learn/vitality/growth)
- Calendar events where Kevin is the only participant

**1b. Familiar — screen activity, time tracking, and work categorization**

This step produces three outputs: (1) app/tool time distribution, (2) total active work hours, and (3) a work-category breakdown by department/function.

**Builder profile:** Before categorizing, read the builder's profile from their Obsidian vault at `[vault_path]/50-reference/builder-profile.md`. This file defines:
- `time_categories` — the work categories to use (varies by role: executive, department lead, manager, IC)
- `time_tracking_mode` — what summary line to produce (doing-vs-orchestrating, deep-vs-meetings, etc.)
- `data_sources` — which integrations are available (familiar, fathom, slack, etc.)

If no builder profile exists, fall back to the **Executive / SLT preset** categories (Coding/Building, Management/People, Product Management, Marketing/Sales, Admin/Ops, Learning/Research) — this is the default for backwards compatibility with Kevin's setup.

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

Every capture gets assigned to exactly one **work category** based on app + window title. The categories represent Kevin's functional roles:

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
3. Zoom/Meet captures that don't match any Fathom meeting → **Meetings (unmatched)** — show separately so Kevin can mentally assign them.

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

This gives Kevin a fast read on how much time he spent building things himself vs. directing others vs. overhead.

The **"Meeting time"** line is an orthogonal metric — it cross-cuts all categories. A 1:1 with Chris counts as both "Management / People" time AND meeting time. This tells Kevin how much of his day was synchronous vs. async, regardless of topic.

**What counts as a meeting (include in count + hours):**
- Calendar events with attendees other than Kevin (detected via `attendees` array)
- Impromptu meetings found in Fathom but NOT on the calendar (detected by comparing Fathom meeting times against calendar event times — no overlap = impromptu)

**What does NOT count as a meeting (exclude from count + hours):**
- Solo calendar blocks created by `/open-day`: titles starting with "Focus:", "Prep:", "Walk", "Learn:", "Review:", or descriptions containing "from /open-day", "Vitality block", "Growth block"
- Calendar events where Kevin is the sole attendee/organizer (no other participants)
- These are work time — they go into the Time Allocation categories (Coding/Building, Admin/Ops, etc.) but not the meeting metric

**Label:** Use `**Meeting time: ~Xh across N meetings**` (not "Meeting time (calendar)") since the count includes both calendar and Fathom-only meetings. If impromptu meetings are included, note them: `— includes N impromptu`.

**1c. Fathom — meeting summaries and action items**

> **IMPORTANT — API URL:** Use ONLY `https://api.fathom.ai/external/v1/meetings`. The domain `api.fathom.video` does NOT exist and will cause a DNS error. Do not try it, do not add it as a first attempt, do not use it as a fallback. One URL. Always.

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
Extract: who Kevin emailed, subject, and the snippet (which captures his reply). Look for approvals, decisions, delegations, and follow-ups.

**1e. Sent Slack — conversations and coordination**

Use the `slack_search_public_and_private` MCP tool:
```
slack_search_public_and_private(
  query="from:<@${SLACK_USER_ID}> on:YYYY-MM-DD",
  sort="timestamp",
  limit=20,
  include_context=false
)
```
Your Slack user ID is in `${SLACK_USER_ID}` from `.env`. Extract: who he messaged, what channels, key topics discussed. Group by conversation thread — don't list every individual message, summarize the thread topic. Distinguish work conversations from personal. Skip trivial messages ("ok", "thanks", reactions).

**1e-pre. Slack follow-up scan (today only)**

> Ported from `nsls-personal-toolkit` PR #12 (Chelsea, "Add Slack follow-up scan to /open-day and /close-day") on 2026-05-27. Catches commitments Kevin made and incoming asks left pending — so they roll into Carrying Over instead of evaporating overnight. The plain Sent-Slack scan in 1e only sees outbound messages; this step adds the inbound side.

**Two parallel queries scoped to today (`on:YYYY-MM-DD`):**

1. **Today's sent messages** — find commitment language
   ```
   slack_search_public_and_private(
     query="from:<@${SLACK_USER_ID}> on:YYYY-MM-DD",
     sort="timestamp",
     limit=20,
     include_context=false
   )
   ```
   Filter for: "I'll", "I will", "I can", "let me", "going to", "I'll put on the calendar", "I'll send", "I'll draft", "by EOD", "by Friday", "happy to", "let's do it", "yes" (when in response to a proposed action).

2. **Today's incoming asks** — find threads where someone asked Kevin something and he didn't reply, OR where his reply was a commitment that wasn't acted on by EOD.
   ```
   slack_search_public_and_private(
     query="to:<@${SLACK_USER_ID}> on:YYYY-MM-DD",
     sort="timestamp",
     limit=20,
     include_context=true
   )
   ```
   For each result, use the context (or `slack_read_channel` with `limit=5` on that channel/DM) to determine the conversation state: did Kevin respond? Was the response substantive or a deferral?

**Cross-reference against today's data:**
- Commitments visible in **Sent Email** (1d) or **Claude session context** (1f) → mark as "kept"
- Commitments mentioned in **Familiar window titles** (1b) showing relevant work → mark as "in progress"
- Otherwise → flag as "open"

**Surface in the Carrying Over section** of today's daily note as:

```markdown
### Slack threads to follow up

- [HH:MM] in [channel/DM]: committed to "[short description]" — status: open / in progress / kept
- [HH:MM] in [channel/DM]: [Name] asked "[question snippet]" — no reply yet — [permalink]
```

Also create P2 Asana tasks for each "open" item via Step 7c (carry-over task creation) with the description noting the Slack source and permalink.

**Rules:**
- Skip Kevin's own bot DMs (SLT EA Bot, Signal) unless they contain a person-facing commitment
- Skip "ok", "thanks", "got it", reactions
- Suppress items that already appear in today's Asana tasks created by other steps
- Limit to 8 entries — beyond that, surface a "and N more" line and let Kevin triage

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

**1f-bis. Apple Health — personal-goal execution + sleep**

Call both tools for the target date AND the day after:
```
mcp__apple-health__apple_health_workouts(date="YYYY-MM-DD")              # target date
mcp__apple-health__apple_health_daily(date="YYYY-MM-DD")                 # target date — activity, exercise, walk evidence
mcp__apple-health__apple_health_daily(date="YYYY-MM-DD+1")               # day after — pulls the sleep that happened during the target night
```

**Sleep semantics (read carefully):** Apple Health keys sleep by the date you wake up. So sleep that happened on the night of the target date appears in the `(target + 1)` record, NOT the target record. By Kevin's rule, **last night's sleep belongs on today's note** — i.e., sleep during the target night belongs on the FOLLOWING day's note next to the Energy line.

When close-day runs the day after the target (the common case), the `(target+1)` data is available and close-day writes the sleep summary into the following day's `## Morning Check-in` section, on a new line above `- Energy:`:

```
- Last night's sleep: 6h 48m total · 36m deep · 1h 53m REM · 36% restorative · HRV 60
- Energy:
```

If `(target+1)` data is not yet synced (export typically syncs by mid-morning), write:
```
- Last night's sleep: _pending — export not yet synced. /open-day will backfill once available._
- Energy:
```
Then `/open-day` next morning replaces the placeholder with the real numbers.

Cross-reference against the morning note's `Top 3` and `Goal cues today` (read the morning note from `01-daily/YYYY-MM-DD.md` if it exists). Extract:
- **Formal workouts** from the target-date `workouts[]` array (logged on Watch)
- **Unlogged exercise** when `activity.exercise_min ≥ 20` AND `activity.distance_mi ≥ 1` AND `heart.hr_max ≥ 110` but `workouts[]` is empty — the activity happened, just wasn't tagged on the Watch
- **Steps + distance** as a baseline vs prior-day comparison
- **Sleep** from the `(target+1)` record — write to the following day's note per the rule above
- **VO2 max** trend when VO2 max is a goal

Distinguish "didn't do it" from "did it but didn't log it on the Watch." An unlogged walk that hit the distance/HR/time threshold is a logging gap, not a discipline gap — say so explicitly in the Insight Reflection and the Personal Goals Activity section.

**Goal-hit booleans:** As part of this step, decide for each active personal goal whether it moved today. This drives the `goal_<slug>_moved` frontmatter key written in Step 5a ("Goal tracking frontmatter") for the exact mapping. The boolean follows the same ✅/🔶/❌/⚪ classification used in the Personal Goals Activity section (Step 3).

**1g. Asana — pending tasks and what was due**

Run in parallel with other data collection. Two calls:

**Call 1: Get all incomplete tasks assigned to Kevin**
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

Include the overdue and due-today lists in the daily note's `## Asana` section. These inform the Carrying Over section and help Kevin see what slipped.

**Filtering:** Skip auto-generated noise like "It's time to update your goal(s)" — only include real tasks Kevin created or was assigned.

**1h. SLT Meeting Actions — open items from the SLT knowledge base**

Pull Kevin's open Meeting Actions from the SLT Meeting Intelligence base. These are action items committed to in SLT meetings, tracked separately from Asana. Many have no due date but are time-sensitive (retreat prep, offsite logistics, quarterly deliverables).

- **Base:** `${SLT_BASE_ID}`
- **Table:** `tblasgjUjadHCqzrg` (Meeting Actions)
- **Auth:** `AIRTABLE_API_KEY` env var (already exported in Kevin's shell)

**CRITICAL — query pattern gotchas:**
- `{assignee_name}` in `filterByFormula` **silently fails** with `INVALID_FILTER_BY_FORMULA: Unknown field names: assignee_name`. The display name in Airtable differs from our schema doc.
- Safe default: filter on `{status}` only (which works), return fields by ID with `returnFieldsByFieldId=true`, then Python-filter by assignee name.
- This is the same pattern documented in the MEMORY.md Airtable gotchas section — field IDs in formulas don't work; schema doc names may drift from display names.

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
          'fldmpu3lN0lrgrdSa',  # assignee_name (text)
          'fldJ1EKcHoncBtkoo',  # Priority
          'fldJpobWjo3J7uWuc',  # action_type
          'fldZlxizRCZnHvWH0']  # meeting (linked)
field_params = '&'.join(f'fields[]={fid}' for fid in fields)

all_records = []
offset = None
while True:
    u = f'https://api.airtable.com/v0/{BASE}/{TABLE}?filterByFormula={urllib.parse.quote(formula)}&{field_params}&returnFieldsByFieldId=true&pageSize=100'
    if offset: u += f'&offset={offset}'
    r = httpx.get(u, headers={'Authorization': f'Bearer {key}'}, timeout=30)
    data = r.json()
    all_records.extend(data.get('records', []))
    offset = data.get('offset')
    if not offset: break

kevin = [r for r in all_records if 'Kevin' in (r.get('fields', {}).get('fldmpu3lN0lrgrdSa') or '')]
# Classify by due_date: overdue / due today / upcoming / no date
# Emit record ID alongside each for Step 7d matching.
"
```

**Field IDs reference (Meeting Actions):**
- `fldiPWq8q3NXyNXil` — action_description (richText)
- `fldJleDMJFfcj5gPN` — status (singleSelect: Not Started / In Progress / Completed / Deferred / Not doing)
- `fldXZJaatwC9FNbtX` — due_date (date)
- `fldmpu3lN0lrgrdSa` — assignee_name (text — safe for Python filter)
- `fldJ1EKcHoncBtkoo` — Priority (1-Today / 2-This week / 3-Later / Waiting on)
- `fldJpobWjo3J7uWuc` — action_type (Task / Decision / Info / Parking-Lot)
- `fldZlxizRCZnHvWH0` — meeting (linked → Meetings table)
- `fldkqhlQRTug3A1ui` — Task Complete (checkbox)
- `fldo7xzjuXIneaw5J` — Notes (richText — context/why)

**Status option IDs for Step 7d writes:**
- Completed: `sel7EJRN91l6qVRHm`
- In Progress: `selfOZiZ8QJ9jfDnw`
- Not Started: `selSlSYN2tjGdZHZa`

**Classify into 4 buckets** for the daily note:
1. **Overdue** — `due_date < today` and status ≠ Completed
2. **Due today / this week** — dated within next 7 days
3. **Retreat blockers / time-sensitive** — no due date BUT action_description mentions retreat, offsite, Tue/Wed/Thu logistics, or known upcoming deadline (infer from Fathom meeting context in Step 1c)
4. **Strategic backlog** — no due date, not time-sensitive. Compress to a single paragraph listing names; don't bullet individually unless ≤5 items.

**Carry each record's Airtable record ID forward** so Step 7d can comment on or complete them without a second lookup.

**Sanity check:** The full open-actions query should return 50-100+ records across all assignees. If it returns 0 or errors, the formula reverted to field IDs — switch back to the working pattern above.

**1i. Task Evidence Detection — find what you finished but haven't checked off**

After Steps 1a–1g are collected, cross-reference Kevin's open Asana tasks and any SLT Meeting Actions against evidence of completion or significant progress. **This step detects — it does not write.** Confirmations happen in Step 7.

**Sources to scan (use data already collected above):**

| Source | What to look for |
|---|---|
| **Obsidian session logs** | Scan `## What Was Done` sections of all `*/sessions/$DATE.md` files found under `20-projects/` |
| **Familiar window titles** | High capture count (≥30) on a window title related to the task — indicates substantial work time |
| **Slack sent messages (1e)** | Kevin's outbound messages mentioning the task or deliverable with completion language ("done", "sent", "finished", "shared", "pushed", "complete") |
| **Fathom meeting notes (1c)** | Action items from meetings confirmed complete, or attendee acknowledged receiving a deliverable |
| **Claude/Warp session context (1f)** | Session title or working directory matching the task's project |
| **Sent email (1d)** | Kevin sent the artifact the task was asking for (attachment, link, approval) |

**Evidence scoring:**

| Signal | Classification |
|---|---|
| Obsidian session log lists it in `## What Was Done` | ✅ Completed |
| Slack: Kevin said "done", "sent", "finished", etc. about this specific task | ✅ Completed |
| Sent email delivers the artifact the task described | ✅ Completed |
| Fathom: deliverable confirmed received or action marked done | ✅ Completed |
| Familiar: 30–49 captures on task-related window title | 🔶 Significant progress |
| Familiar: 50+ captures on task-related window title | ✅ Completed (strong signal) |
| Obsidian session log mentions it without `## What Was Done` | 🔶 Worked on it |

At least one ✅ signal → **Completed candidate**. Moderate signals only → **Progress candidate** (suggest Asana comment, not mark-complete). Skip tasks with no signals — don't surface noise.

**Obsidian session log scan:**
```bash
VAULT="${OBSIDIAN_VAULT_PATH}"
find "$VAULT/20-projects" -path "*/sessions/$DATE.md" 2>/dev/null | while read f; do
  echo "=== $f ==="; cat "$f"
done
```

**Output format (show Kevin before Step 2):**

```
## Task Evidence Check

✅ Likely completed (not yet checked off):
- "All Staff deck" — Familiar: 74 caps on "All Staff Meeting - April 2026 - Google Slides"; Slack: messaged Danielle about it
- "LOP Q2 Reset" — Familiar: 58 caps on "L2 Goal Modifications - Google Docs"; Obsidian session log confirms

🔶 Significant progress (not finished):
- "Finalize hiring contracts" — Familiar: 337 Warp caps on slt-ops session

Do you want me to mark the ✅ items complete in Asana (and SLT if applicable)?
I'll show you the exact changes before writing anything.
```

**Pass-through to Step 7:** The confirmed list feeds Step 7a (mark complete) and 7d (SLT sync). Step 7 still presents the full plan to Kevin before any writes.

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
   - `airtable.com/${PEOPLE_OPS_BASE_ID}` → `people-ops`
   - `airtable.com/${SLT_BASE_ID}` → `meeting-automation`
   - GitHub repo URLs → match to project

Use the project mappings from `~/.claude/skills/log/SKILL.md` as the source of truth.

### Step 3: Draft the daily note

Generate in this format (matching Kevin's existing `01-daily/` structure):

```markdown
---
# Sleep + hrv keys are owned by the morning write (open-day, or close-day-next-day
# writing the following note). PRESERVE them if already present — do not clobber.
sleep_total_hrs: [preserve if present, else from 1f-bis if available]
sleep_restorative_pct: [preserve / compute]
sleep_deep_hrs: [preserve]
sleep_rem_hrs: [preserve]
hrv_ms: [preserve, else target-date heart.hrv_ms]
# Activity + VO2 + goal keys are close-day's to own for the TARGET DATE (see Step 5a).
exercise_min: [target-date activity.exercise_min]
steps: [target-date activity.steps]
active_energy_kcal: [target-date activity.active_energy_kcal]
vo2_max: [target-date body.vo2_max, or null]
goal_<slug>_moved: [true | false]   # one line per active personal goal — see Step 5a
---
# YYYY-MM-DD — [Day of Week]

## Insight Reflection

[Paragraph 1 — primary pattern: what the data reveals that you might not have noticed. One concrete data point must anchor it. Max 3 sentences.]

[Paragraph 2 — second dimension or implication: what this pattern might mean going forward, or a second non-obvious angle. Max 3 sentences. Omit if there's nothing genuinely interesting to add.]

## Personal Goals Activity

Read the morning note's `Goal cues today` and `Top 3` for personal-goal anchors. Compare against Apple Health data from Step 1f-bis. For each personal goal cue, report:
- ✅ **Executed and logged** — formal Watch workout present, goal met
- 🔶 **Executed but unlogged** — exercise_min / distance / hr_max indicate the activity happened without a Watch workout tag (logging gap, not discipline gap)
- ❌ **No signal** — the goal's cue fired today (an expected/scheduled day) but activity metrics don't support it — a genuine miss
- ⚪ **Not goal-relevant today** — no cue fired: a scheduled rest/off day per the goal's `weekly_schedule`/`anchor`, or no personal goal set. Not a miss — Step 5a omits the key for this day.

Include the raw numbers: steps, distance_mi, exercise_min, hr_max, sleep total, VO2 max. Compare against the morning note's "Yesterday" baseline when available. If the goal required a logging step (e.g., "Log on watch as Outdoor Walk for VO2 trigger") and the activity happened but no workout was logged, flag as a workflow fix for tomorrow.

## Time Allocation

| Category | Hours | % | Top tools |
|---|---|---|---|
| [Category] | [X.Xh] | [XX%] | [top 2-3 tools] |
| ... | | | |

**Active work: [X.X] hours** ([first block start] – [last block end])
Work blocks: [HH:MM–HH:MM (X.Xh), ...]
Doing vs. Orchestrating: [X%] hands-on building, [X%] managing/meeting, [X%] admin/research
**Meeting time: ~[X]h across [N] meetings** ([X%] of active work) [— includes N impromptu, if any]

## Time Distribution
- [Category]: [percentage] ([capture count] captures)
- [Category]: [percentage] ([capture count] captures)
- ...
- Other: [percentage] ([count] captures)

## Meetings ([count])
[For each meeting from Calendar + Fathom:]
- **HH:MM–HH:MM** — [Title] (with [attendees])
  - [Key takeaway from Fathom summary, 1-2 bullets max]
  - Action: [any action items assigned to Kevin]

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

## SLT Meeting Actions ([N] open, Kevin-owned)
Source: `${SLT_BASE_ID}/tblasgjUjadHCqzrg` — pulled fresh this evening.

**Overdue:**
- [ ] [Action description] (due [date], [N weeks overdue])

**Due soon / time-sensitive (dated or retreat/offsite-scoped):**
- [ ] [Action]
- [ ] [Action]

**Cross-linked with Asana / already surfaced above:**
- [Action that also appears in Asana section — list by name only, no checkbox]

**Strategic backlog (no dates, compress if >5 items):**
[Single paragraph listing action names separated by • for scanability. Only bullet individually if ≤5 items.]

## Projects Touched
- [[20-projects/[slug]|[slug]]] — [1-line summary of what happened]
- [[20-projects/[slug]|[slug]]] — [1-line summary]

## Carrying Over
- [Unfinished items from Claude tasks, meeting action items, or Asana overdue]

## Brain Dump
*Capture anything on your mind throughout the day — ideas, half-formed plans, decisions to make, things to figure out, reminders. Close-day routes these at end of day.*
-

## End of Day
- Energy:

### AI Suggested: Tomorrow's Top 3 (strategic, high-leverage, Kevin-only)
1. **[Highest-impact item]** — [Why only Kevin can do this. What it blocks or unlocks.]
2. **[Second item]** — [Strategic rationale.]
3. **[Third item]** — [Strategic rationale.]

### AI Suggested: Delegate These
1. **[Task]** → [Person] — [Why they're the right owner. What Kevin's role becomes (review/approve).]
2. **[Task]** → [Person] — [Rationale.]
3. **[Task]** → [Person] — [Rationale.]

### My Top 3 (Kevin fills in)
1.
2.
3.
```

**Rules:**
- Keep the Work Log to concrete outputs, not activities. "Imported 40-file board knowledge base to Obsidian" not "worked on Obsidian."
- Meeting bullets come from Fathom summaries — pull only the 1-2 most important takeaways, not the full summary.
- **Time Allocation** is the new primary time view. It shows work categories (Coding/Building, Management/People, etc.) with estimated hours, percentages, and top tools. The "Doing vs. Orchestrating" summary line gives Kevin a fast read on CEO time allocation. See Step 1b Phase 4 for the full format and category definitions.
- **Time Distribution** still appears below Time Allocation as a flat tool-level breakdown. Uses categorized captures, not raw app names. Chrome captures are broken down by window title into meaningful categories (Gmail, YouTube, Airtable, Google Docs, etc.) and presented as flat peers alongside Slack, Warp, Obsidian, etc. Never show "Google Chrome: X%" — that's useless. Round to whole numbers. Only show categories with ≥1% of total captures. Always **exclude personal finance** captures from the report and totals.
- The `## Morning Check-in` section from Kevin's template is NOT auto-generated — that's for the start of day.
- **Sent Email:** Include approvals, decisions, and delegations as Work Log bullets. Skip routine replies that don't represent a decision or action.
- **Sent Slack:** Summarize by conversation thread/topic, not individual messages. Skip trivial messages ("ok", "thanks", single emoji). Focus on decisions, coordination, and substantive discussions. Group DMs with personal contacts (family) should be noted briefly or omitted — Kevin can decide. Flag any coaching/leadership conversations as those are often important context.
- **AI Suggested Top 3:** Generate 3 strategic priorities for tomorrow based on carry-overs, meeting action items, deadlines, and Asana. Filter for items that are (a) high-impact/high-leverage, (b) fit Kevin's unique skills as CEO — relationship decisions, strategic judgment calls, cross-team visibility, contract/legal calls. Explain *why* each is Kevin-only and what it blocks/unlocks.
- **AI Suggested Delegate:** Generate 3 important items someone else could own. Name the person and why they're the right fit. Kevin's role becomes review/approve, not execute. Look for: operational tasks with a clear domain owner, first-draft work where Kevin adds value in editing not creating, technical setup that doesn't require strategic judgment.
- **My Top 3:** Always left blank for Kevin to fill in manually after reviewing the AI suggestions. Kevin may adopt, modify, or completely replace the AI suggestions.

**Generating the Insight Reflection:**

Apply full-shape thinking to the day itself — treat the day as the subject being analyzed. From all data collected, pick the 2 most interesting dimensions and write one paragraph per dimension. Max 2 paragraphs total.

Dimensions to check (choose the most non-obvious):

| Dimension | Question |
|---|---|
| **Plan vs. reality gap** | What was on Asana / carried over vs. what actually got done? What slipped, and is there a pattern? |
| **Doing vs. Orchestrating skew** | Does the actual time split match what Kevin thinks he's doing? Is there a surprise in the ratio? |
| **Hidden theme** | Is there a thread connecting meetings, work, and decisions that doesn't appear on any single list? |
| **Unrecorded completions** | Did Task Evidence Detection surface things Kevin finished but didn't track? What does that say about how he works? |
| **Negative space** | What was conspicuously absent today that usually shows up? What didn't happen that should have? |
| **Energy distribution** | Did the highest-stake work happen at peak hours, or was it squeezed into leftover time? |

**Rules for what makes a good Insight Reflection:**
- Must be non-obvious — don't restate what's already in the Work Log
- Must be anchored to a specific number, person, task name, or time (not abstract)
- Declarative framing: "The slide deck consumed 4.3x more time than contracted work" not "It's interesting that..."
- "We" or second-person framing where appropriate — Kevin should feel seen, not lectured
- Omit the second paragraph if there's no second insight that clears the bar. One sharp insight beats two generic ones.
- **Never summarize the day.** That's what the rest of the note is for.

### Step 4: Present draft to Kevin

Show the full daily note draft. Ask:
- "Anything to add or correct?"
- "Ready to write?"

### Step 4c. NSLS Knowledge Base harvest

Heartbeat sequence:

```bash
# Everyone harvests: /harvest-meeting self-routes (SLT → company KB, others → local KB)
# and resolves identity cwd-independently in its own Step 0 — no pre-gate here.
echo "Step 4c: invoking /harvest-meeting --date $TODAY (routes to company or local KB)..."
```

Invoke the harvest skill:

```
/harvest-meeting --date $TODAY
```

The skill will:
1. Route to the company KB if you're on SLT, otherwise to your local KB
2. Load KB topic index + rubric
3. Pull Fathom meetings for today
4. Extract → map → dedup → rubric
5. Present numbered approval list to the user
6. Apply edits → commit (push if company KB) → or exit cleanly if cancelled

**After the skill returns:** Append a `## Knowledge Base` section to today's daily note with one of:
- `- Harvested {N} edits to 60-nsls-knowledge ({sha}, {commit_url})`
- `- Harvested {N} edits to local KB`
- `- 0 candidates from today's meetings`
- `- Harvest cancelled (no changes)`

### Step 5: Write daily note

Write to: `${OBSIDIAN_VAULT_PATH}/01-daily/YYYY-MM-DD.md`

**If the file already exists** (Kevin started it in the morning with priorities), **merge** — keep the existing Morning Check-in section and append/update the generated sections below it.

**5a. Health + goal frontmatter (write/merge) — Goal tracking frontmatter**

This is the authoritative end-of-day write of the note's YAML frontmatter. It is what keeps the Obsidian Tracker charts (exercise minutes, VO2 trajectory, goal hit-rate) fed. Do it every run — never skip silently.

**Always ensure a frontmatter block exists.** If the note has no `---` block at the top (open-day didn't run, or ran without Apple Health), **create one**. If a block exists, **merge** — update the keys below, preserve every other key (especially `sleep_*` and `hrv_ms`).

Write these keys from the **target-date** Apple Health pulled in Step 1f-bis (`apple_health_daily(target)`):

| Key | Source | Notes |
|---|---|---|
| `exercise_min` | `activity.exercise_min` | target date — overwrite any provisional value open-day wrote |
| `steps` | `activity.steps` | target date |
| `active_energy_kcal` | `activity.active_energy_kcal` | target date |
| `vo2_max` | `body.vo2_max` | target date; write `null` if absent that day |
| `goal_<slug>_moved` | Step 1f-bis hit decision | one line per active personal goal (see below) |

**Do NOT write or overwrite `sleep_*` / `hrv_ms` here** — sleep is keyed to wake-up date and is owned by the morning write (per the Sleep semantics in 1f-bis). Preserve whatever is already there; only fill `hrv_ms` from `heart.hrv_ms` if the key is entirely absent.

**Goal key mapping.** For each active personal goal (the same set Step 1f-bis evaluated — `10-strategy/goals/*.md` with `status: active` AND `category: personal`):
- Key name = `goal_` + the goal file's **`slug:` frontmatter field** + `_moved`. Example: goal file with `slug: vo2_max` → `goal_vo2_max_moved`. Use the `slug` field verbatim (it may contain underscores); do not re-derive it from the filename.
- Value from the Step 1f-bis classification:
  - ✅ Executed and logged → `true`
  - 🔶 Executed but unlogged (activity happened, Watch tag missing) → `true` *(logging gap ≠ discipline gap — the behavior counts; the Watch VO2 number not moving is captured separately by `vo2_max`)*
  - ❌ No signal (activity doesn't support the goal cue — e.g. cue wanted an outdoor session and only indoor/none happened) → `false`
  - ⚪ Not goal-relevant today → omit the key for that goal

If Apple Health returned an error for the target date (no data synced yet), still ensure the frontmatter block exists, write the goal keys from whatever evidence exists (workouts, morning cue), and leave the numeric health keys you couldn't source as `null` rather than dropping the block.

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

Cross-reference the day's Work Log against Kevin's open Asana tasks (fetched in Step 1g). For each Asana task that was clearly completed today, mark it done:

```
mcp__claude_ai_Asana__update_tasks(
  tasks=[{"task": "[GID]", "completed": true}]
)
```

**How to match:** Compare Asana task names against Work Log bullets, sent emails, Fathom action items marked done, and Claude session accomplishments. Be conservative — only mark complete if there's clear evidence the task is finished, not just worked on.

**7b. Comment on in-progress tasks**

For Asana tasks that Kevin worked on but didn't finish, add a progress comment:

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

Then confirm with `mcp__claude_ai_Asana__create_task_confirm` using workspace `${ASANA_WORKSPACE_GID}`.

**Priority framework (CEO lens):**

| Priority | Due Date | Criteria |
|----------|----------|----------|
| **P1 — Do today/tomorrow** | Next business day | Revenue impact, board/investor commitment, blocking others, legal/compliance deadline, key hire decision |
| **P2 — This week** | End of current week (Friday) | Strategic initiative milestone, team unblocked by this, partner/vendor commitment, product launch dependency |
| **P3 — Next week+** | Next Monday or specific date from context | Internal process improvement, nice-to-have follow-up, research/exploration, relationship maintenance |

**Priority inference rules:**
- Commitments made to external parties (board, partners, candidates) → P1
- Meeting action items Kevin owns with a stated deadline → use that deadline, infer priority from urgency
- Contract/legal/hiring items → P1-P2 (time-sensitive by nature)
- Internal tooling, automation, documentation → P2-P3
- "Would be nice to" or "explore" language → P3
- If a carry-over item was also carry-over from a previous day → bump priority up one level

**Rules for Asana write-back:**
- **Only create tasks for actionable items Kevin owns.** Skip items that are someone else's action (e.g., "Davo sends proposal").
- **Don't duplicate.** Before creating, search Asana for similar task names. If a match exists, skip (or comment on it instead).
- **Include source context** in the description so Kevin knows where the task came from.
- **Present the full Asana sync plan to Kevin** before executing. Show three columns:

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

Kevin approves, modifies, or skips before any Asana writes happen.

**7d. SLT Meeting Actions — comment, complete, and advance status**

The SLT knowledge base has its own action tracking. Meeting Actions are first-class here — not just reflections of Asana tasks. Step 7d writes back three kinds of updates:

**(i) Mark Meeting Actions complete** — when evidence shows the action is done

For each ✅ completion candidate from Step 1i that maps to an SLT Meeting Action (carried forward with its record ID from Step 1h):

```
PATCH https://api.airtable.com/v0/${SLT_BASE_ID}/tblasgjUjadHCqzrg/{record_id}
Body: { "fields": {
  "fldJleDMJFfcj5gPN": "Completed",
  "fldkqhlQRTug3A1ui": true
}}
```

Uses the plain option-name string for the select field (per MEMORY.md: the `{"id": "selXXX"}` format silently fails when using field-ID keys in payloads).

**(ii) Advance Meeting Actions to In Progress** — when evidence shows progress but not completion

For 🔶 progress candidates that map to SLT actions:

```
PATCH ... Body: { "fields": { "fldJleDMJFfcj5gPN": "In Progress" }}
```

Also append a progress note to the Notes field (`fldo7xzjuXIneaw5J`) using a `## Progress YYYY-MM-DD` header so updates stack chronologically without overwriting meeting context. Fetch the current Notes value first (single-record GET), then PATCH the concatenated value.

**(iii) Cross-system sync when Asana fires** — avoid double-tracking

If a completed Asana task's description contains `Source: SLT Meeting` or an explicit Airtable record ID, also run the SLT PATCH. If an Asana comment is added in 7b for an in-progress task that originated from SLT, post the same comment content as a Notes append.

**Finding the Airtable record ID (matching order):**

1. **Preferred — Asana task notes convention.** `/open-day` Step 4a writes an exact line in the form `SLT record: recXXX` into the Asana task description when shadowing an SLT action. Parse the completed Asana task's `notes` (or `html_notes`) field for the regex `SLT record:\s*(rec[A-Za-z0-9]+)`. Case-sensitive match on the prefix. This is deterministic — no text fuzzing required.
2. **Step 1h carry-forward.** Record IDs pulled alongside actions in the morning/evening fetch let you match by action description directly against the in-memory list, skipping a second API call.
3. **Fallback — text-match.** If neither above resolves, fuzzy-match the Asana task name against open Meeting Action `action_description` values from Step 1h. Surface matches for Kevin's approval; never write automatically on a fuzzy hit.

**Presentation to Kevin (before writing):**

```
🧠 SLT Airtable sync plan:
✅ Complete (2):
  - rec123... "Order Thu lunch via Katie's sheet" — Slack: Kevin confirmed in Huddle thread
  - recABC... "Bring wired setup for offsite tech" — Familiar: 30+ caps on SLT prep doc

🔄 Advance to In Progress (1):
  - recXYZ... "Build offsite presentation mental-model deck" — Familiar: 157 caps on Big Idea doc; not done

No Asana-triggered SLT writes today.
```

Kevin approves before any Airtable writes fire. This ensures completing a task in the daily workflow closes the loop in the SLT knowledge base — and surfaces the 40-item open backlog that Asana otherwise misses.

**7e. Brain Dump Routing**

Read the `## Brain Dump` section from today's daily note. If it's empty (just `-` with no content), skip silently.

For each item, classify and propose a route:

| Classification | Criteria | Action |
|---|---|---|
| **Task** | Actionable, owned by Kevin, completable in 1-2 sessions | Create Asana task with priority/due date |
| **Project idea** | Bigger than a task, needs dedicated planning and a note | Suggest creating Obsidian project note or adding to-do to an existing project |
| **Decision** | A fork to resolve before other work can proceed | Surface in tomorrow's AI Suggested Top 3 |
| **Learning / research** | Link, article, tech to explore, skill to build | Add to `40-learning/_inbox.md` |
| **Parking lot** | Interesting but not now, no clear owner or timing | Add to `50-reference/parking-lot.md` |
| **Concern / question** | Something on Kevin's mind that isn't actionable yet | Surface in tomorrow's Morning Check-in |

**Present a triage table before writing anything:**

```
## Brain Dump Routing

| # | Item | Classification | Proposed action |
|---|---|---|---|
| 1 | "gary's enrollment funnel → SLT EA Bot?" | Decision | Add to tomorrow's Top 3: "Decide: Gary funnel routing" |
| 2 | "LOP dashboard split" | Task | Create Asana P2: "Split LOP dashboard from SLT base" — already a carry-over, confirm close? |
| 3 | "NCO quality update" | Task | Create Asana P2: "NCO quality update — who owns this?" |

Approve to route, or tell me which to change/skip.
```

After Kevin confirms, execute: create Asana tasks for Task items (using `create_task_preview` → `create_task_confirm`), append to Obsidian files for Project/Learning/Parking lot items. Decisions surface in Step 8 (tomorrow's note).

**Do not create Asana tasks for items that are already in Asana or already in today's Carrying Over section.** Deduplicate before proposing.

### Step 8: Seed tomorrow's daily note

Check if tomorrow's note exists at `${OBSIDIAN_VAULT_PATH}/01-daily/YYYY-MM-DD+1.md`. If it does NOT exist, create it with this template:

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

### Brain Dump
*Capture anything on your mind throughout the day — ideas, half-formed plans, decisions to make, things to figure out, reminders. Close-day routes these at end of day.*
-

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

This seeds the next day with the AI-suggested priorities so Kevin sees them first thing in the morning. He overwrites "My Top 3" with his actual priorities during `/open-day` or manually.

If the file already exists (Kevin or `/open-day` already created it), do NOT overwrite. Instead, check if it has the AI suggestion sections. If not, insert them after `## Morning Check-in`.

### Step 9: Confirm

Report: "Daily note written to `01-daily/YYYY-MM-DD.md`. Seeded tomorrow's note at `01-daily/YYYY-MM-DD+1.md`. Updated session logs for: [project list]. Asana: [N] completed, [N] updated, [N] created."

---

## Performance Notes

- **Familiar scanning is fast** — grepping frontmatter across 1000+ files takes < 2 seconds. Do NOT read OCR content unless Kevin asks for specific recall.
- **Fathom API is slow** — full paginated fetch can take 30-60 seconds. If Kevin ran `/close-day` already today, skip re-fetching.
- **Calendar is instant** — MCP tool returns in < 1 second.
- **Asana is fast** — MCP tools return in < 2 seconds.
- **The 7-day retention** — Familiar auto-cleans stills after 7 days (`storageAutoCleanupRetentionDays: 7`). Daily notes capture the signal before the raw data expires.

## Edge Cases

- **No meetings today:** Skip the Meetings section entirely.
- **No Familiar data:** Skip Time Distribution, note "No screen capture data available."
- **Weekend/light day:** Still generate — even a short note like "Light day. 2 hours of email and Slack." is valuable for continuity.
- **Multiple Claude sessions:** Check jsonl file dates. Summarize each session's contribution.
