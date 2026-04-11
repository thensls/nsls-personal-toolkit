---
name: plan-week
description: Sunday/Monday weekly planning — sets week priorities from role, goals, last week's review, and Asana backlog. Includes leadership coaching patterns. Trigger phrases: plan week, week plan, weekly planning, plan my week, what should I focus on this week, weekly priorities, set priorities
---

# Plan Week

Set the week's priorities by reviewing last week's close-week output, the Asana backlog, upcoming calendar, and the builder's role/goals. Includes leadership coaching — pattern detection across weeks to surface misalignments between stated priorities and actual behavior.

## When to Run

Sunday evening or Monday morning, before the first meeting of the week.

## Asana Reference

Read these from `~/.claude/local-plugins/nsls-personal-toolkit/.env`:
- **Workspace GID:** `$ASANA_WORKSPACE_GID`
- **User GID:** `$ASANA_USER_GID`

## Role Context

Read the builder's operating memo from:
`$OBSIDIAN_VAULT_PATH/10-strategy/operating-memo.md`

Use the "I Do" / "I Don't" / "My Traps" / "My Meeting Rules" sections to inform priority recommendations and coaching feedback. If no operating memo exists, fall back to the builder profile at `$OBSIDIAN_VAULT_PATH/50-reference/builder-profile.md` for role context.

## Timezone

Read the `timezone` field from `$OBSIDIAN_VAULT_PATH/50-reference/builder-profile.md`. If not set, detect from the system (`date +%Z`) or ask the builder. Use this timezone for all calendar API calls.

## Step-by-step Execution

### Step 1: Collect data (run in parallel)

**1a. Last week's close-week review**

Read: `$OBSIDIAN_VAULT_PATH/02-weekly/YYYY-[W]WW-1.md`

Extract:
- Achievements (what went well)
- Priorities vs. Reality (what slipped)
- Carry-forward items
- Stalled projects
- Time allocation percentages
- **AI Suggested: Next Week's Top 3** (if present — seeded by `/close-week`)
- **AI Suggested: Delegate Next Week** (if present)
- **AI Suggested: Stop Doing** (if present)

If the close-week AI suggestions exist, present them to the builder as a starting point alongside the plan-week recommendations. Show where they agree and where they differ — close-week suggestions are based on last week's data patterns, while plan-week recommendations factor in the upcoming calendar and Asana state.

**1b. Asana backlog**

```
mcp__claude_ai_Asana__get_my_tasks(
  completed_since="now",
  limit=100,
  opt_fields="name,due_on,projects.name,assignee_section.name"
)
```

Categorize:
- P1 (overdue or due this week)
- P2 (due next 2 weeks)
- P3 (backlog, no date)
- "Do today" section items (self-flagged urgent)

**1c. This week's calendar**

```
gcal_list_events(
  timeMin="YYYY-MM-DDT00:00:00",  // Monday
  timeMax="YYYY-MM-DDT23:59:59",  // Friday
  timeZone="<from builder-profile.md or system>",
  condenseEventDetails=true
)
```

Count: total meetings, total meeting hours, key meetings (external, board, candidates).

**1d. Previous weeks' patterns (coaching data)**

Read the last 3-4 weekly reviews from `02-weekly/` to detect patterns:
- Are the same priorities repeating week after week without progress?
- Is time allocation shifting toward or away from strategic work?
- Are certain projects consistently stalled?
- Is the builder doing work that should be delegated?

### Step 1.5: Strategy layer check

Check if `$OBSIDIAN_VAULT_PATH/10-strategy/operating-memo.md` exists.

**If it does NOT exist:**
> "A strategy layer is available that connects your projects to company goals, does weekly stack ranking, and checks alignment with your operating memo. It starts with a 15-minute reflective conversation to build your personal operating memo. Set up now, or skip for this week?"

If "now" — pause plan-week and walk through the operating memo generation process (5 reflective questions about role, strengths, traps, measures, meetings). Write the result to `10-strategy/operating-memo.md`. Then continue.
If "skip" — proceed with normal plan-week, skip all strategy steps (1.6 through 1.10) below.

**If it exists:** Continue to Step 1.6.

Also check if the operating memo's `next-review` date has passed. If so, nudge: "Your operating memo was last updated [date]. Want to review it before planning this week, or keep going?"

### Step 1.6: Mode detection (push vs protect)

Scan for crisis indicators:
- Carry-overs from last week that mention "urgent", "crisis", "blocked", "at risk"
- Asana overdue tasks count (if > 5 overdue, lean toward protect)
- Last week's close-week: did actual mode match planned mode?
- Known signals from recent daily notes

Propose the week mode with evidence:
> "**Proposed mode: Push** — No active crises detected. Last week was protect; you have room to push this week."
> 
> or
>
> "**Proposed mode: Protect** — 8 Asana tasks overdue, 2 carry-overs flagged urgent. Recommend stabilizing before pushing new initiatives."

User confirms or flips.

### Step 1.7: Project stack rank

Read all active projects from `20-projects/` with enriched frontmatter (`lop`, `role`, `impact`).
Read `10-strategy/operating-memo.md` for "I Do" / "I Don't" / "My Traps".
Read `10-strategy/lops-summary.md` for current LOP health statuses.
Read last week's stack rank from `10-strategy/stack-rank/` (if exists) to see what moved and what stalled.

**Ranking algorithm (in priority order):**
1. Projects tied to at-risk LOPs get boosted (protect mode) or maintained (push mode)
2. Higher `impact` projects rank above lower
3. Projects where `role` = owner rank above sponsor/architect (you're the bottleneck)
4. Projects with `role` containing `->` get a "handoff checkpoint" flag
5. Projects untouched > 2 weeks get flagged as stale
6. In push mode: explorer and new-lever projects get boosted
7. In protect mode: fix/stabilize projects get boosted

**Present Top 5 with rationale:**
> "Here's your proposed stack rank for this week:
> 
> | # | Project | LOP | Role | Impact | Why This Rank |
> |---|---------|-----|------|--------|---------------|
> | 1 | [project] | [lop] | [role] | [L/M/S] | [rationale] |
> | 2 | ... | ... | ... | ... | ... |
> | 3 | ... | ... | ... | ... | ... |
> | 4 | ... | ... | ... | ... | ... |
> | 5 | ... | ... | ... | ... | ... |
> 
> **Parked this week:** [list of active projects not in Top 5]
> 
> Adjust the ranking?"

User reorders, cuts, or adds.

**Effort gut-check:**
For each project in the final Top 5, ask: "Heavy lift or quick win this week?" Record as `effort-this-week: S/M/L`.

### Step 1.8: Trap check

Compare the confirmed stack rank against the operating memo:

- Count projects where `role` = architect or contains "->". If > 3 of the Top 5 are maintenance/handoff work, flag: "3 of your Top 5 are maintenance projects. Your memo's 'I Don't' list says to teach/delegate first. Is this intentional, or should you swap one for a push project?"
- Check if any Top 5 items match patterns in "My Traps". Flag specifically: "This looks like [trap name] — [quote from memo]."
- Check the teach/delegate/do ladder: "For your maintenance projects this week, are you teaching someone, delegating to someone, or doing it yourself? Your memo says teach first."

This is coaching, not blocking. User can override.

### Step 1.9: Meeting check

Read this week's calendar (already fetched in Step 1c).
Read operating memo's "My Meeting Rules" section.

Compare:
- Total meeting hours this week vs. target from memo (default: <= 10h)
- Flag meetings that don't match the attendance criteria (deciding, unblocking, coaching, vision/alignment)
- Flag double-bookings
- If meetings > target: "You have [X]h of meetings this week against your [Y]h target. Which meetings could you decline, delegate, or convert to async?"
- Flag recurring meetings: "Any standing meeting that hasn't produced a decision or alignment moment in 3 weeks should be challenged."

### Step 1.10: Write stack rank

Save the confirmed stack rank to:
`$OBSIDIAN_VAULT_PATH/10-strategy/stack-rank/YYYY-WNN.md`

Format:
```
---
week: YYYY-WNN
mode: push | protect
mode-rationale: "[evidence string]"
---

# WNN Project Stack Rank

| Rank | Project | LOP | Role | Impact | Effort | Status |
|------|---------|-----|------|--------|--------|--------|
| 1 | [project] | [lop] | [role] | [S/M/L] | [S/M/L] | [status note] |
| ... |

## Focus This Week
1. **[project]** — [what to do this week, suggested time blocks]
2. **[project]** — [what to do]
3. **[project]** — [what to do]

## Parked (active but not this week)
- [list of active projects not in Top 5]
```

Then proceed to existing Step 2 (coaching insights) and Step 3 (draft week plan). The Top 3 for the week should be informed by the stack rank — typically the top 3 ranked projects become the Top 3, but user may choose differently based on calendar and deadlines.

### Step 2: Generate coaching insights

Before suggesting priorities, surface patterns:

**Pattern detection:**
- **Repeat priorities:** If the same item appeared in Top 3 for 2+ consecutive weeks without completion, flag it: "This is week 3 of '[priority]' in your Top 3. Either it needs to be broken down smaller, delegated, or explicitly deprioritized."
- **Time misalignment:** If the builder said something was #1 but spent <10% of time on it, flag: "[Priority] was your stated #1 but got [X]% of your time. [Top activity] dominated. Is this the right allocation for your role?"
- **Doing-vs-delegating trap:** If building/coding time exceeds 20% of the week for someone in a leadership role, flag: "You spent [X]% of your time building. That's valuable but consider: is there someone else who could build this while you focus on [strategic item]?" (Skip this check for IC roles.)
- **Stalled projects:** If a project has been in `status: active` but `last-touched` is >2 weeks ago, flag: "These projects are marked active but haven't been touched in 2+ weeks: [list]. Kill, delegate, or schedule time."

### Step 3: Draft week plan

Present to the builder:

```markdown
## Week Plan: [date range]

### Coaching Notes
[1-2 pattern observations from Step 2 — be direct, not preachy]

### Calendar Reality
- [N] meetings this week ([X] hours)
- Key meetings: [list external/board/candidate meetings]
- Estimated deep work windows: [identify gaps in calendar]

### Recommended Top 3
1. **[Priority]** — [why this week, what "done" looks like]
   - Asana tasks: [link to related tasks]
   - Time needed: ~[X] hours
2. **[Priority]** — [why, what done looks like]
3. **[Priority]** — [why, what done looks like]

*Rationale: [1-2 sentences on why these 3, what's deliberately being left off]*

### Also Important (but not Top 3)
- [Item] — due [date], can be done in [time estimate]
- [Item] — delegate to [person] if possible

### Carry-Forward from Last Week
- [Item] — [status: needs finishing / needs delegation / needs killing]

### Stalled Projects to Address
- [Project] — last touched [date]. Action: [kill / delegate / schedule 1hr this week]

### What to Say No To
- [Specific things you should decline or defer this week to protect the Top 3]
```

### Step 4: Builder reviews and sets priorities

The builder adjusts the Top 3, accepts or rejects coaching, and commits to the week's focus.

### Step 5: Write week plan

Write to: `$OBSIDIAN_VAULT_PATH/02-weekly/YYYY-[W]WW.md`

If a close-week already wrote this file, **merge** — keep the close-week sections (achievements, learnings, etc.) and add the plan sections below.

### Step 6: Asana sync

Update Asana to reflect the week plan:
- Set due dates on tasks that are part of the Top 3
- Add comments on carry-forward tasks with new plan
- Create any new tasks from "What to Say No To" (delegation tasks assigned to others if appropriate)

### Step 7: Seed Monday's daily note

Write the Monday daily note `01-daily/YYYY-MM-DD.md` with:
- Morning Check-in pre-populated with Top 3
- Today's meetings from calendar
- Overdue Asana items

This means Monday morning, the builder can skip `/open-day` — it's already done.

## Leadership Coaching Philosophy

The coaching in this skill is **not generic productivity advice.** It's grounded in:

1. **Your actual data** — time allocation, priorities, completions
2. **Role context** — what only you can do vs. what should be delegated (read from builder-profile.md and operating memo)
3. **Pattern detection** — trends across weeks, not just this week
4. **Direct language** — no corporate-speak, no sugarcoating, just "here's what the data says"

The goal is to be the coaching equivalent of a good CFO review: "Here's what you said you'd spend on, here's what you actually spent on, here's the gap."

## Edge Cases

- **No close-week from last week:** Generate without coaching patterns. Note: "No weekly review data from last week — coaching insights will improve as we build history."
- **First time running:** Bootstrap from whatever daily notes exist. Set a baseline.
- **Mid-week run:** If the builder runs this on Wednesday (re-planning), use Mon-Tue data as partial week and adjust.
- **Builder pushes back on coaching:** That's fine. The observations are suggestions, not mandates. But the data is the data.
