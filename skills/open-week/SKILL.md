---
name: open-week
description: Sunday/Monday weekly planning — sets week priorities from role, goals, last week's review, and Asana backlog. Includes leadership coaching patterns. Trigger phrases: open week, plan week, week plan, weekly planning, plan my week, what should I focus on this week, weekly priorities, set priorities
---

# Open Week

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

If the close-week AI suggestions exist, present them to the builder as a starting point alongside the open-week recommendations. Show where they agree and where they differ — close-week suggestions are based on last week's data patterns, while open-week recommendations factor in the upcoming calendar and Asana state.

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

**1d. Previous weeks' patterns and insight signals (coaching data)**

Read the last 3-4 weekly reviews from `02-weekly/` to detect patterns:
- Are the same priorities repeating week after week without progress?
- Is time allocation shifting toward or away from strategic work?
- Are certain projects consistently stalled?
- Is the builder doing work that should be delegated?

Also extract the `## Insight Reflection` section from each weekly note. Look for **cross-week insight signals** — dimensions that appear in 2+ consecutive weekly reflections:
- Same structural pattern named twice → it's not a fluke, it's a system
- Same trap recurring → the memo needs updating or the constraint isn't being addressed
- Consistent negative space (something important not happening) → candidate for structural change

If a cross-week signal is found, surface it in Step 3's Coaching Notes as: "For the [N]th consecutive week, [signal]. This suggests [structural implication], not just a scheduling issue."

**1e. Learning goals and progress**

Read from `$OBSIDIAN_VAULT_PATH/40-learning/`:
- `_learning-goals.md` — active learning goals and priorities
- Each active topic's dashboard (e.g., `agentic-harnesses.md`) — check `status`, `next-session`, and Learning Path completion (count `[x]` vs `[ ]` items)
- `_inbox.md` — count unprocessed links

Extract:
- Active goal count and names
- Per-goal progress (X of Y items complete)
- Days since last session per goal (from `next-session` or Progress Log)
- Unprocessed inbox link count

### Step 1.5: Strategy layer check

Check if `$OBSIDIAN_VAULT_PATH/10-strategy/operating-memo.md` exists.

**If it does NOT exist:**
> "A strategy layer is available that connects your projects to company goals, does weekly stack ranking, and checks alignment with your operating memo. It starts with a 15-minute reflective conversation to build your personal operating memo. Set up now, or skip for this week?"

If "now" — pause open-week and walk through the operating memo generation process (5 reflective questions about role, strengths, traps, measures, meetings). Write the result to `10-strategy/operating-memo.md`. Then continue.
If "skip" — proceed with normal open-week, skip all strategy steps (1.6 through 1.10) below.

**If it exists:** Continue to Step 1.6.

Also check if the operating memo's `next-review` date has passed. If so, nudge: "Your operating memo was last updated [date]. Want to review it before planning this week, or keep going?"

### Step 1.55: Automation portfolio check

Check if the builder has automations that could be moved toward Org-Owned.

1. Read builder email from `~/.claude/local-plugins/nsls-personal-toolkit/.env` or `git config user.email`
2. Call `GET https://web-production-6281e.up.railway.app/builder-stats/{email}`
3. If the builder has no automations, skip this step silently
4. If the builder has automations at Prototype or Production, surface them:

> **Automation check:** You have automations that could level up this week:
>
> **[Automation Name]** — at [Stage], [checklist_complete]/[checklist_total] checklist items done.
> Remaining:
> - [ ] [remaining item 1 — with a brief "how": e.g., "Write `docs/runbook.md` with deployment steps and recovery procedures"]
> - [ ] [remaining item 2]
> - [ ] ...
>
> Moving this to Org-Owned is the highest-impact thing you can do for your builder progression. Want to add it to your Top 3 this week?

5. If they say yes: add as a concrete Top 3 item with:
   - The specific checklist tasks as sub-items
   - Estimated time: "~2-3 hours to write runbook + architecture doc"
   - The payoff: "Completing this moves the automation to Org-Owned eligible"
6. If they say no: move on — coaching, not blocking

**Only surface automations at Prototype or Production.** If `days_at_stage` isn't available from the API, surface any Prototype or Production automation.

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
| 1 | [[project-slug]] | [lop] | [role] | [S/M/L] | [S/M/L] | [status note] |
| ... |

**Project column linking rule:** Before writing, check `$OBSIDIAN_VAULT_PATH/20-projects/` for a matching project folder. If a project home exists at `20-projects/<slug>/<slug>.md`, write the cell as `[[<slug>]]` (Obsidian resolves it). If no home exists (goals, contracts, one-off work), write plain text. This makes the table clickable when transcluded into the daily note.

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
- **Learning stagnation:** If an active learning goal hasn't had progress in 3+ weeks, flag it: "[Topic] has been active for [N] weeks with no progress. Either schedule a deep dive this week, park it, or admit it's not a priority right now."
- **Learning vs. filler:** If last week's close-week showed >5h of YouTube/news but <1h of structured learning, note: "Last week had [X]h of media consumption but only [Y]h of intentional learning. Consider converting one filler session into a 15-min micro-learning block."
- **Cross-week insight signal:** If the same theme appeared in the `## Insight Reflection` of 2+ consecutive weekly notes (from Step 1d), escalate it: "This is week [N] of [theme] surfacing in your weekly reflection. That's a structural pattern, not a one-off. What would it take to address it?"

### Step 3: Draft week plan

Present to the builder:

```markdown
## Week Plan: [date range]

### Coaching Notes
[1-2 pattern observations from Step 2 — be direct, not preachy]
[If cross-week insight signal detected: "For the [N]th consecutive week, [signal]. [What this suggests structurally, not as a one-off]."]

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

### Learning & Growth

**Active goals:** [list from _learning-goals.md]

**This week's focus:**
- **Deep dive:** [topic] — [learning path item], ~1.5h. Suggested: [day based on calendar gaps].
- **Daily micro-learning:** 15 min/day from [topic] learning path or inbox links.

**Ask the builder:** "What do you want to learn more about this week? Confirm the above, add a new topic (I'll run `/learn`), or skip learning this week."

**Stale goals:** [any goals with no progress in 3+ weeks — suggest park or schedule]

**Inbox:** [N] unprocessed links. [If >10: "Your learning inbox is backing up. Run `/learn inbox` to process, or I'll triage during `/open-day`."]

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

### Step 4.5: Relationship Health Check Trigger

After weekly priorities are set, check `$OBSIDIAN_VAULT_PATH/30-people/*.md` for the most recent `health_last_assessed` date across all scored profiles.

If **14 or more days** have passed since the last assessment:

```
⏰ Relationship health check is due (last run: [date], [N] days ago).
   Running biweekly check now...
```

Then execute the full Relationship Health Check flow from the person-intelligence skill:
1. Present health dashboard with current scores
2. AI proposes updated scores based on recent data
3. Kevin confirms or adjusts
4. Coaching goal review — new evidence, goal updates, new proposals
5. Personal details prompt for profiles with gaps
6. Growth reflection (Jack's 5 questions)

If fewer than 14 days have passed, skip silently.

### Step 4.6: Coaching Goals Portfolio

Regardless of whether the health check runs, display the active coaching portfolio:

```
🎯 Active Coaching Goals ([N] people)
  [Name] — [goal title] ([duration], [N] evidence items, trending [↑/→/↓])
  [Name] — [goal title] ([duration], [N] evidence items, trending [↑/→/↓])
  [Name] — [goal title] (new, proposed last check)
```

**How to determine trend:**
- Count evidence items in the last 14 days vs. the 14 days before
- More recent evidence = ↑ (trending up)
- Same = → (steady)
- Less or none = ↓ (stalling)

**How to gather this data:**
- Scan all `30-people/*.md` files for `status: active` lines in `## Coaching Goals` sections
- Parse the goal title, created date, and count evidence entries
- If no active coaching goals exist across any profile, skip this section

This gives Kevin a birds-eye view of which relationships he's actively developing and whether momentum is building.

### Step 5: Write week plan

Write to: `$OBSIDIAN_VAULT_PATH/02-weekly/YYYY-[W]WW.md`

If a close-week already wrote this file, **merge** — keep the close-week sections (achievements, learnings, etc.) and add the plan sections below.

The weekly note must include a Learning Plan section after the Top 3:

```markdown
### Learning Plan
- **Deep dive:** [topic] — [item], [day], ~1.5h
- **Micro-learning:** 15 min/day — [topic] learning path
- **Goals:** [N] active, [N] inbox links pending
```

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
