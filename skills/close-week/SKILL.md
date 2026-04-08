---
name: close-week
description: Friday morning weekly roll-up — synthesizes Mon-Thu daily notes into achievements, learnings, project progress, time allocation, and priorities-vs-reality. Formatted for quick notes copy-paste. Trigger phrases: close week, weekly review, week summary, week roll up, friday summary, weekly wrap, end of week
---

# Close Week

Roll up the week's daily notes into a structured weekly review. Output is formatted for copy-paste into the NSLS Coach quick notes journal. Run Friday morning before 10 AM.

## When to Run

Friday morning, before the user's quick notes reminder fires. Output feeds directly into the weekly journal.

## Step-by-step Execution

### Step 0: Determine the week

Default to the current week (Monday through today). User can override: `/close-week 2026-03-17` (uses that Monday as the start).

Calculate:
- Monday date = start of week
- Friday date = today (or target Friday)
- Date range string for display: "Mar 24 - Mar 28, 2026"

### Step 1: Collect data (run in parallel)

**1a. Read all daily notes for the week**

Read files from `$OBSIDIAN_VAULT_PATH/01-daily/`:
- `YYYY-MM-DD.md` for Monday through Thursday (Friday's may not exist yet)

Extract from each:
- `## Morning Check-in` → Top 3 priorities (especially Monday's — these are the week plan)
- `## Work Log` → all bullets
- `## Meetings` → count and key meetings
- `## Projects Touched` → project list
- `## Carrying Over` → what slipped each day
- `## Time Distribution` → capture counts by category

**1b. Familiar time data for the full week**

```bash
for d in Mon Tue Wed Thu Fri; do
  DATE=$(date -v-${offset}d +%Y-%m-%d)  # compute each day
  grep -h "^app:" $HOME/familiar/stills-markdown/session-${DATE}T*/*.md 2>/dev/null \
    | sort | uniq -c | sort -rn
done
```

And Chrome breakdown:
```bash
for d in Mon-Fri dates; do
  awk '/^app: Google Chrome/{found=1} found && /^window_title_raw:/{print; found=0}' \
    $HOME/familiar/stills-markdown/session-${DATE}T*/*.md 2>/dev/null
done | sort | uniq -c | sort -rn
```

Use the same categorization rules from `/close-day` (Gmail, YouTube, Airtable, etc.). Exclude personal finance. Compute weekly totals and percentages.

**1c. Asana tasks completed this week**

```
mcp__claude_ai_asana__asana_search_tasks(
  assignee_any="me",
  completed=true,
  completed_on_after="YYYY-MM-DD",  // Monday
  completed_on_before="YYYY-MM-DD",  // Saturday
  sort_by="completed_at",
  opt_fields="name,completed_at,projects.name",
  limit=100
)
```

**1d. Asana tasks still overdue**

```
mcp__claude_ai_asana__asana_search_tasks(
  assignee_any="me",
  completed=false,
  due_on_before="YYYY-MM-DD",  // today (Friday)
  sort_by="due_date",
  sort_ascending=true,
  opt_fields="name,due_on,projects.name",
  limit=50
)
```

### Step 2: Synthesize

**Achievements:** Scan all Work Log bullets across the week. Pick the 5-8 most impactful — things that shipped, decisions that moved the needle, external commitments met. Prefer concrete outcomes with numbers over activity descriptions.

**Learnings:** Look for:
- Patterns across meetings (Fathom themes)
- Things that failed or were harder than expected
- Insights from conversations (Slack, email)
- Process improvements discovered
- "I wish I had..." moments from carry-overs that piled up

**Project Progress:** For each project that appeared in any daily note's `## Projects Touched`, summarize the week's movement. Status = on-track (touched 2+ days or key milestone hit), needs-attention (touched but blocked), stalled (not touched despite being active).

**Time Allocation:** Aggregate Familiar data across all 5 (or 7) days using the same work categories and time calculation algorithm from `/close-day`:

1. Read the builder profile from `$OBSIDIAN_VAULT_PATH/50-reference/builder-profile.md` for time categories. If no profile exists, use the Executive preset (Coding/Building, Management/People, Product Management, Marketing/Sales, Admin/Ops, Learning/Research).
2. For each day, compute active work hours using the session-merge algorithm (filter cron micro-sessions, merge gaps ≤ 20 min, filter trivial blocks < 5 min).
3. Categorize captures using the same app/Slack-channel/Chrome/Fathom rules from close-day.
4. Sum across the week for totals and daily breakdown.

Present as:
```
| Day | Hours | Top category | Second category |
|---|---|---|---|
| Mon | 12.1h | Management (35%) | Coding (28%) |
| Tue | 10.4h | Meetings (40%) | Product (22%) |
| ... | | | |
| **Week** | **52.3h** | **Management (30%)** | **Coding (25%)** |
```

Plus the weekly summary line matching the builder's `time_tracking_mode`:
- `doing-vs-orchestrating`: "Doing vs. Orchestrating: X% building, X% managing/meeting, X% admin/research"
- `deep-vs-meetings`: "Deep work ratio: X% focused, X% collaboration, X% meetings/admin"
- `department-balance`: "Department focus: X% [primary], X% [secondary], X% other"

**Priorities vs. Reality:** Pull Monday's Top 3 from the daily note. For each, assess:
- **Done** — clear evidence in Work Log
- **Partial** — worked on but not finished (note what remains)
- **Missed** — no evidence of progress (note why if detectable)

### Step 3: Generate two outputs

**Output A: Weekly Review note** (for Obsidian)

Write to: `$OBSIDIAN_VAULT_PATH/02-weekly/YYYY-[W]WW.md`

Full format with Dataview queries for projects touched/not touched.

**Output B: Quick Notes format** (for copy-paste into NSLS Coach journal)

Present this in the conversation for the user to copy:

```
Achievements:
- [Concrete outcome — shipped, decided, or delivered]
- [Concrete outcome]
- [Concrete outcome]

Learnings:
- [What I'd do differently or insight gained]
- [Pattern noticed across the week]

Project Progress:
[Project]: [on-track/needs-attention/stalled] — [1-line summary]
[Project]: [status] — [1-line]

Time Allocation:
- Meetings: Xh (Y%)
- Building: Xh (Y%)
- Communication: Xh (Y%)
- Deep work: Xh (Y%)
- Content/learning: Xh (Y%)

Priorities vs. Reality:
1. [Monday priority] → [Done/Partial/Missed] — [1-line]
2. [Monday priority] → [Done/Partial/Missed]
3. [Monday priority] → [Done/Partial/Missed]
```

**Output C: AI-Suggested Next Week Priorities** (seeded into the weekly note for `/plan-week` to pick up)

Generate next week's priorities using the same pattern as close-day's "AI Suggested: Tomorrow's Top 3" but at weekly scope:

```markdown
### AI Suggested: Next Week's Top 3 (from weekly close)
1. **[Highest-impact item for next week]** — [Why this week. What it blocks/unlocks. Why only this person can do it.]
2. **[Second item]** — [Strategic rationale.]
3. **[Third item]** — [Strategic rationale.]

### AI Suggested: Delegate Next Week
1. **[Task]** → [Person] — [Why they're the right owner. What the builder's role becomes.]
2. **[Task]** → [Person] — [Rationale.]
3. **[Task]** → [Person] — [Rationale.]

### AI Suggested: Stop Doing
1. **[Activity consuming time without proportional value]** — [Evidence from this week's time data. What to do instead.]
```

**Rules for weekly AI suggestions:**
- **Top 3** — filter for items that are (a) high-impact, (b) match the builder's unique role (from builder profile), (c) have been carrying over or are deadline-driven. Use the week's data to identify what stalled and needs CEO/lead attention.
- **Delegate** — surface tasks that consumed the builder's time but could be owned by someone else. Use Familiar data to find patterns: "You spent 3.2h in Airtable this week — could [person] own the data entry?"
- **Stop Doing** — NEW for weekly scope. Identify one activity that consumed disproportionate time relative to its impact. Use time allocation data as evidence. This is the coaching equivalent of "you're spending 15% of your week on X — is that the best use of your role?"

These seed into the weekly note so `/plan-week` can reference them alongside its own analysis.

**Rules for quick notes format:**
- Keep it tight. This goes into a Slack bot journal — not a novel.
- Lead with achievements, not activities.
- Learnings should be genuine insights, not platitudes. "Discovered DDC IT overage is $15k/mo — need to renegotiate" not "Learned about vendor management."
- Project progress should flag what needs CEO attention, not just list updates.
- Time allocation should make the user think: "Am I spending time on what matters?"
- Priorities vs. Reality is the accountability moment — be honest.

### Step 4: Present to user

Show both outputs. Ask:
- "Anything to add or adjust before I write the weekly note?"
- "Quick notes version ready to paste — want any edits?"

### Step 5: Write weekly note

Write Output A to `02-weekly/YYYY-[W]WW.md`. Include the AI-Suggested Next Week sections at the end — these are picked up by `/plan-week` as a starting point for next week's planning.

### Step 6: Asana sync

Create any new tasks surfaced by the weekly review:
- Stalled projects that need CEO attention → P2 task for next week
- Carry-forward items that have been carrying all week → bump to P1
- Process improvements identified in Learnings → P3 tasks

Use the same Asana write-back pattern as `/close-day` — present plan, user approves, then create.

## Edge Cases

- **Missing daily notes:** Some days may not have `/close-day` run. Use whatever exists — even partial daily notes have Morning Check-in priorities.
- **No Familiar data for a day:** Skip that day in time allocation, note the gap.
- **Short week (holiday, PTO):** Adjust date range. Still generate — even a 3-day week deserves a roll-up.
- **User ran /close-week already this week:** Check if `02-weekly/YYYY-[W]WW.md` exists. If so, ask if they want to regenerate or append.
