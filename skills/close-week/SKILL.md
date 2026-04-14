---
name: close-week
description: Friday weekly roll-up — synthesizes the full week (Sat-Fri) of daily notes into achievements, learnings, project progress, time allocation, and priorities-vs-reality. Formatted for quick notes copy-paste. Trigger phrases: close week, weekly review, week summary, week roll up, friday summary, weekly wrap, end of week
---

# Close Week

Roll up the week's daily notes into a structured weekly review. Output is formatted for copy-paste into the NSLS Coach quick notes journal. Run Friday morning before 10 AM.

## When to Run

Friday morning, before the user's quick notes reminder fires. Output feeds directly into the weekly journal.

## Step-by-step Execution

### Step 0: Determine the week

The week runs **Saturday through Friday** (7 days). Weekend work must be captured if the user works weekends.

Default behavior: find the **previous Saturday** and use it as the start date, with today (Friday) as the end.

If a previous close-week exists (check `02-weekly/` for the most recent file), start from the **day after** that close-week's end date instead. This handles skipped weeks (vacation, holidays) by rolling up all uncovered days.

User can override: `/close-week 2026-03-15` (uses that Saturday as the start).

Calculate:
- Saturday date = start of range (or day after last close-week)
- Friday date = today (or target Friday)
- Date range string for display: "Mar 15 - Mar 21, 2026"

### Step 1: Collect data (run in parallel)

**1a. Read all daily notes for the week**

Read files from `$OBSIDIAN_VAULT_PATH/01-daily/`:
- `YYYY-MM-DD.md` for Saturday through Friday (7 days). Weekend notes may not exist — that's fine, skip missing days.

Extract from each:
- `## Morning Check-in` → Top 3 priorities (especially Monday's — these are the week plan)
- `## Work Log` → all bullets
- `## Meetings` → count and key meetings
- `## Projects Touched` → project list
- `## Carrying Over` → what slipped each day
- `## Time Distribution` → capture counts by category

**1b. Familiar time data for the full week**

```bash
for DATE in $SAT $SUN $MON $TUE $WED $THU $FRI; do  # all 7 days, Sat-Fri
  echo "=== $DATE ==="
  grep -h "^app:" $HOME/familiar/stills-markdown/session-${DATE}T*/*.md 2>/dev/null \
    | sort | uniq -c | sort -rn
done
```

And Chrome breakdown:
```bash
for DATE in $SAT $SUN $MON $TUE $WED $THU $FRI; do  # all 7 days
  echo "=== $DATE ==="
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
  completed_on_after="YYYY-MM-DD",  // Saturday (start of range)
  completed_on_before="YYYY-MM-DD",  // day after Friday (end of range + 1)
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

**Stack Rank Review (if strategy layer active):**

Read this week's stack rank from `$OBSIDIAN_VAULT_PATH/10-strategy/stack-rank/YYYY-WNN.md`.
Cross-reference with daily notes to estimate hours per project.

For each project in the Top 5:
- Estimate hours spent (from daily note Work Log bullets and Familiar time data)
- Compare rank to actual attention

Present as:
```
## Stack Rank vs Reality

| Rank | Project | Planned Focus | Hours Spent | Verdict |
|------|---------|---------------|-------------|---------|
| 1 | [project] | [from stack rank focus section] | [X.Xh] | Hit / Partial / Missed |
| 2 | ... | ... | ... | ... |
| ... |

**Unranked projects that got significant time:**
- [project]: [X]h (not in Top 5 — was this reactive or intentional?)
```

This is the core accountability moment: did you spend time on what you said mattered?

**Push/Protect Mode Review (if strategy layer active):**

Read the planned mode from the stack rank frontmatter. Determine actual mode from behavior:
- If >50% of significant work went to reactive/maintenance/fix projects: actual = protect
- If most time went to new initiatives and push projects: actual = push
- Mixed is fine — note it honestly

Present and append to the weekly note:
```
## Push/Protect

| Planned | Actual | Notes |
|---------|--------|-------|
| [mode] | [mode] | [1-line honest assessment] |
```

Note the running streak: "This is your Nth consecutive [push/protect] week." If protect streak >= 3, flag: "3 protect weeks in a row. Your push projects haven't moved since W[N]. Is there a structural issue to address, or is this the right call?"

**Role Transition Tracking (if strategy layer active):**

For projects tagged with `->` in their `role` frontmatter (e.g., `architect->sponsor`):
- Did time spent decrease compared to last week? (Progress toward handoff)
- Did the collaborator take on more? (Check daily notes for their name)
- Or did you do more IC work on it? (Regression)

Present:
```
## Handoff Progress

| Project | Role | This Week | Last Week | Direction |
|---------|------|-----------|-----------|-----------|
| [project] | architect->sponsor | [X]h | [Y]h | Progressing / Stalled / Regressing |
| ... |

[For each regressing project]: "[project]: You spent more time this week than last. Your memo says teach first — could you pair with [collaborator] next week instead?"
```

**Operating Memo Alignment (if strategy layer active):**

Read `$OBSIDIAN_VAULT_PATH/10-strategy/operating-memo.md`. Categorize this week's work log items and time allocation against "I Do" and "I Don't":

Present:
```
## Memo Alignment

| Category | Hours | % | Examples |
|----------|-------|---|---------|
| I Do work | [X]h | [Y]% | [top 2-3 activities] |
| I Don't work | [X]h | [Y]% | [top 2-3 activities] |
| Teaching/delegating | [X]h | [Y]% | [examples of pairing, training] |
| Neutral | [X]h | [Y]% | admin, learning, meetings |
```

Flag trends: "Your 'I Don't' time [increased/decreased] from [X]% last week to [Y]% this week. Main driver: [specific activity]."

Check the teach/delegate/do ratio: "Of your maintenance work this week, how much was teaching someone vs. doing it yourself?"

**Meeting Retrospective (if strategy layer active):**

Compare actual meeting hours (from calendar) to the target in the operating memo:

Present:
```
## Meetings

**This week:** [X]h meetings (target: [Y]h from operating memo)
**Recurring:** [X]h | **Ad-hoc:** [X]h

Recurring meetings this week: [count]
- [meeting name]: [duration] — [decision made? Y/N]
- ...

**Challenge:** [If any recurring meeting produced no decisions for 3+ weeks, flag it here: "Consider converting [meeting] to async — no decisions in [N] weeks."]
```

**Weekly Insight Reflection:**

After all synthesis above is complete, apply full-shape thinking to the week itself. Pick the 2 most non-obvious dimensions and write one tight paragraph each. Max 3 paragraphs total.

Dimensions to check:

| Dimension | Question |
|---|---|
| **Plan vs. reality gap** | What did Monday's Top 3 predict vs. what actually shipped? Is there a structural cause, not just a bad week? |
| **Doing vs. Orchestrating skew** | Did the time split match the stated push/protect mode? Where did the week actually go vs. where it was supposed to go? |
| **Hidden through-line** | One theme that connected the week's meetings, builds, and decisions that no individual daily note named. |
| **Structural output pattern** | Which day types produced the most output? What does that say about how this week should have been designed? |
| **CEO trap** | What did you do this week that should have been delegated? Where did IC work crowd out strategic work? |
| **Negative space** | What important thing didn't happen? What should have moved but didn't, and why? |
| **Carry-over decay** | How many items appeared in 3+ consecutive carry-overs? Each needs a verdict: break down, delegate, or kill. |

Rules:
- Must be non-obvious — don't restate Achievements or Priorities vs. Reality
- Must be anchored to a specific number, project name, day, or person
- Declarative framing only: "David's first week absorbed 60% of Friday's coordination load" not "onboarding took time"
- Second-person framing — the user should feel seen, not lectured
- Omit a paragraph if it doesn't clear the bar. Two sharp insights beat three generic ones.

The Insight Reflection is the **first section** in the weekly note (Output A), before Achievements. It is also summarized as a single "Insight of the Week" sentence in Output B.

### Step 3: Generate two outputs

**Output A: Weekly Review note** (for Obsidian)

Write to: `$OBSIDIAN_VAULT_PATH/02-weekly/YYYY-[W]WW.md`

Full format with Dataview queries for projects touched/not touched.

**If strategy layer is active**, include the following sections in the weekly note after "Priorities vs. Reality":
- Stack Rank vs Reality
- Push/Protect
- Handoff Progress
- Memo Alignment
- Meetings

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

Insight of the Week:
[One sentence — the sharpest non-obvious thing the week's data revealed. Specific, declarative, anchored.]
```

**Output C: AI-Suggested Next Week Priorities** (seeded into the weekly note for `/open-week` to pick up)

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

These seed into the weekly note so `/open-week` can reference them alongside its own analysis.

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

Write Output A to `02-weekly/YYYY-[W]WW.md`. Include the AI-Suggested Next Week sections at the end — these are picked up by `/open-week` as a starting point for next week's planning.

### Step 6: Asana sync

Create any new tasks surfaced by the weekly review:
- Stalled projects that need CEO attention → P2 task for next week
- Carry-forward items that have been carrying all week → bump to P1
- Process improvements identified in Learnings → P3 tasks

Use the same Asana write-back pattern as `/close-day` — present plan, user approves, then create.

## Edge Cases

- **Missing daily notes:** Some days may not have `/close-day` run (especially weekends). Use whatever exists — even partial daily notes have Morning Check-in priorities. Weekend notes may not exist at all; pull Familiar data directly for those days.
- **No Familiar data for a day:** Skip that day in time allocation, note the gap.
- **Short week (holiday, PTO):** Adjust date range. Still generate — even a 3-day week deserves a roll-up.
- **Weekend work:** If the user works weekends, always check for Saturday and Sunday daily notes and Familiar data. Weekend hours count toward weekly totals and time allocation.
- **User ran /close-week already this week:** Check if `02-weekly/YYYY-[W]WW.md` exists. If so, ask if they want to regenerate or append.
- **Skipped weeks:** If the previous close-week was 2+ weeks ago, the current close-week covers ALL days since. Expand the date range accordingly.
