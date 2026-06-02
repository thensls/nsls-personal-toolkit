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

**1b. Task backlog**

Pull open tasks from whichever task system the builder uses. Most builders use one of:
- Asana (default — query via Asana MCP)
- Airtable Meeting Actions (NSLS pattern — Fathom auto-extracts SLT/1:1 action items into Airtable)

**Detection:** check `~/.claude/local-plugins/nsls-personal-toolkit/.env` for `ASANA_USER_GID`. If it's set and uncommented, use Asana (1b.1). If it's missing/commented, fall back to Airtable Meeting Actions (1b.2). Run **both** if both are configured — combine the results.

**1b.1 — Asana**

```
mcp__claude_ai_Asana__get_my_tasks(
  completed_since="now",
  limit=100,
  opt_fields="name,due_on,projects.name,assignee_section.name"
)
```

Also pull the "Do today" section items (self-flagged urgent) separately.

**1b.2 — Airtable Meeting Actions** (NSLS)

Query open tasks (status = Not Started or In Progress) assigned to the builder. The builder's name appears in the singleLineText `assignee` field; the linked record sits in `assignee (linked)`.

```
mcp__b9e0ba62-fba1-48c0-8814-6f701844c723__list_records_for_table(
  baseId="${SLT_BASE_ID}",
  tableId="tblasgjUjadHCqzrg",
  filters={
    "operator": "and",
    "operands": [
      {"operator": "contains", "operands": ["fldmpu3lN0lrgrdSa", "<builder full name>"]},
      {"operator": "isAnyOf", "operands": ["fldJleDMJFfcj5gPN", ["selSlSYN2tjGdZHZa", "selfOZiZ8QJ9jfDnw"]]}
    ]
  },
  fieldIds=["fldrD45ouHX2KD52A", "fldiPWq8q3NXyNXil", "fldJleDMJFfcj5gPN", "fldXZJaatwC9FNbtX", "fldJ1EKcHoncBtkoo", "fldZlxizRCZnHvWH0", "fldtGjdcicLNRiFvi", "fldo7xzjuXIneaw5J"],
  pageSize=100
)
```

Field IDs decoded:
- `fldrD45ouHX2KD52A` — action (formula, primary)
- `fldiPWq8q3NXyNXil` — action_description
- `fldJleDMJFfcj5gPN` — status (`selSlSYN2tjGdZHZa` = Not Started, `selfOZiZ8QJ9jfDnw` = In Progress)
- `fldXZJaatwC9FNbtX` — due_date
- `fldJ1EKcHoncBtkoo` — Priority
- `fldmpu3lN0lrgrdSa` — assignee (singleLineText)
- `fldZlxizRCZnHvWH0` — meeting (link to source meeting)
- `fldtGjdcicLNRiFvi` — created_dtm
- `fldo7xzjuXIneaw5J` — Notes

**Categorization rules** (apply to combined Asana + Airtable result):
- **P1** — overdue OR due this week (within the planning window)
- **P2** — due in next 2 weeks
- **P3** — anything else, including:
    - tasks with no due date
    - tasks due more than 2 weeks out (still surface them — they belong in the week's awareness even if not action-this-week)
    - tasks self-flagged "Do today" in Asana
- **De-dupe**: if the same item appears in both Asana and Airtable, prefer the Airtable record (it carries the meeting context).

The full list goes into Step 3's "Also Important" / "What to Say No To" sections. The P1 cluster informs the Top 3 candidates. The P3 cluster — even far-out ones — should be visible in the weekly note so they don't fall off the radar between weeks.

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

**1f. Knowledge context scan** (parallel call to the builder toolkit's `knowledge-researcher` agent)

Launch the agent:

```
Task(
  subagent_type="nsls-builder-toolkit:research:knowledge-researcher",
  prompt="Weekly strategic planning context. Surface:
    - Tier 1: any LOPs at risk or needing attention this week
    - Tier 2 (if available): SLT knowledge graph topics owned by the builder — flag any that are present-but-unpopulated or stale (last-updated > 60 days)
    - Tier 3: active learning goals with no progress in 2+ weeks; any operating-memo 'My Traps' items that match recurring themes
  Keywords: <names of this builder's owned LOPs from tier 1, and any projects in 20-projects/ flagged role: owner>"
)
```

The agent returns structured findings grouped by tier. Use its output to:
- **Enrich Step 1.7 (stack rank):** owned SLT topics that are stale or unpopulated are candidates for Top 5 (structural gap — institutional knowledge not accreting).
- **Feed Step 2 (coaching):** any "trap" overlap the agent surfaces becomes a coaching signal ("your 'I Don't' zone shows up in 3 of your proposed Top 5 — deliberate?").

If the agent returns "Tier 2 not available" or the tier 2 section is empty, that's fine — this step is purely additive. Log the coverage summary so the builder can see which tiers were read.

**1g. Apple Health — weekly body trends**

If the `apple-health` MCP is configured (`~/.claude.json` contains `mcpServers.apple-health`), pull 28 days of data in one call:

```
mcp__apple-health__apple_health_trends(days=28)
```

Returns an array of daily records with: `steps`, `active_energy`, `exercise_min`, `resting_hr`, `hrv`, `sleep_total_hrs`, `sleep_restorative_pct`, `weight`, `vo2_max`. Most days have null for `vo2_max` (Apple Watch only computes it on qualifying outdoor activity) and null for `resting_hr` (HAE's daily-aggregate CSV doesn't include it — gap, not error).

If the call fails or returns `[]`, skip this step silently and omit the "Body & Recovery" section from Step 3. Don't surface the error to the builder.

**Aggregate the 28-day window into these weekly metrics:**

| Metric | How to compute |
|---|---|
| `vo2_max_latest` | most recent non-null `vo2_max` in the array |
| `vo2_max_delta_4w` | `vo2_max_latest` − oldest non-null `vo2_max` in the array (28-day trajectory) |
| `hrv_avg_7d` | mean of `hrv` over the most recent 7 days (skip nulls) |
| `hrv_delta_vs_prior_7d` | `hrv_avg_7d` − mean of days 8-14 |
| `rhr_avg_7d` | mean of `resting_hr` over the most recent 7 days; usually null (gap) |
| `exercise_min_total_7d` | sum of `exercise_min` over the most recent 7 days |
| `sleep_total_avg_7d` | mean of `sleep_total_hrs` over the most recent 7 days |
| `sleep_consistency_stddev` | stddev of `sleep_total_hrs` over the most recent 7 days (lower = more consistent) |
| `sleep_restorative_avg_7d` | mean of `sleep_restorative_pct` over the most recent 7 days |

Carry these forward to Step 3. The CDC target for `exercise_min_total_7d` is 150 minutes/week (moderate-to-vigorous).

**1h. Active quarterly goals**

Read all goal files from `$OBSIDIAN_VAULT_PATH/10-strategy/goals/*.md` with `status: active` (skip `personal-goals.md` and `work-goals.md` — those are dashboards). Parse frontmatter for each.

For each active goal, compute weekly progress:

**Metric goals** (`type: metric`, `metric_source` set):
- If `metric_source` starts with `apple_health.`, query the apple-health MCP for the current value:
  - `apple_health.vo2_max` → latest non-null from `apple_health_trends(days=14).vo2_max`
  - `apple_health.sleep_total_avg` → `apple_health_trends(days=7).sleep_total_hrs` mean
  - `apple_health.exercise_min_total` → `apple_health_trends(days=7).exercise_min` sum
  - `apple_health.hrv_avg` → `apple_health_trends(days=7).hrv` mean
  - `apple_health.steps` → `apple_health_trends(days=7).steps` sum
  - `apple_health.weight` → `apple_health_trends(days=14).weight` latest non-null
- If `metric_source` is `manual`, look in the goal's Weekly Log for the most recent value.
- Compute progress = `(current - baseline) / (target - baseline) * 100`. Clamp to [0, 100+] (100+ means over-target).

**Behavior goals** (`type: behavior`):
- Count days in past 7 where `goal_{slug}_moved: true` in daily note frontmatter.
- Progress = `count / target_freq_per_week * 100`.

**Relationship goals** (`type: relationship`):
- Same as behavior — count moved days from daily frontmatter.

**Hit rate calculation** (used in coaching push):
- Past 7 days: count of `goal_{slug}_moved: true` / count of daily notes that have the key
- Past 28 days: same, longer window
- If 0 daily notes have the key (goal just created), report "no data yet"

Carry forward for Step 3:

```python
goals = [{
    "slug": "vo2-max",
    "title": "Hold and improve VO2 max",
    "category": "personal",
    "type": "metric",
    "current": 36.2, "baseline": 36.2, "target": 37.0, "unit": "ml/(kg·min)",
    "progress_pct": 0,  # baseline = current → no gain yet
    "weekly_action": "2x zone-2 + 1x intervals",
    "anchor": "After walking Red, Mon/Wed/Fri 7:45am",
    "hit_rate_7d": "2/3",  # or "no data yet"
    "hit_rate_28d": "8/12",
    "end": "2026-06-30",
    "weeks_remaining": 5,
}, ...]
```

**Coaching signals** to surface in Step 3 per goal:
- If `hit_rate_7d` < 50% AND not "no data yet": include the coaching question pattern.
- If metric goal is trending wrong direction (current < baseline OR weekly trend negative for 3+ weeks): flag "trajectory needs review".
- If `weeks_remaining` ≤ 2 AND `progress_pct` < 50%: flag "behind on this — accelerate or rescope".

Skip 1h entirely if no goal files exist or none are active.

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

### Step 1.6: Mode detection (push-to-build vs push-to-close vs protect)

Three modes, each with a different constraint:

| Mode | Constraint | What you decline | When to choose |
|---|---|---|---|
| **Push-to-build** | Focus | Scope creep, "while we're at it" additions, exploratory side projects | Low carry-over, energy is fine, the goal is expanding the surface (new initiatives, deck work, retreat prep) |
| **Push-to-close** | Discipline | New initiatives outside Top 3, side builds, scope expansion | High carry-over (especially relationship-decay items), no body/calendar crisis but the queue is burning |
| **Protect** | Capacity | Meetings, new commitments, Friday building, weekend work | Body or calendar over-extended; stabilize before pushing again |

**Signals to scan (objective + vibes):**

*Objective:*
- **Carry-over P1 count** from last week's close-week. ≥3 unfinished P1s with relationship-decay character (overdue emails, slipping contracts, retention items) → push-to-close. ≥5 with body/calendar strain → protect.
- **Asana overdue tasks count.** > 5 overdue total → lean toward protect or push-to-close (not build).
- **Repeat priorities.** Same Top 3 item carrying 3+ weeks → push-to-close (the structure has to change, not the resolve).
- **Hours overshoot.** Last week's actual hours > planned hours by >20% → protect bias.
- **Push streak.** 3+ consecutive push weeks → protect bias unless carry-over forces push-to-close.

*Vibes (ask, don't infer alone):*
- Body — sleep, energy, exercise this week?
- Family — did the people at home get the version they want?
- Mental — racing or settled?
- Decisions weighing — anything heavy that needs a real pause?

The objective signals propose; the vibes confirm. A clean carry-over queue + tired body = protect even though the queue says push-to-close. A loaded queue + good body = push-to-close even though the streak says protect.

Propose the week mode with evidence:
> "**Proposed mode: Push-to-close** — 4 P1 carry-overs with relationship decay. Body OK per /open-day. Push streak is 4, but the queue is burning louder than the streak. Constraint: no new initiatives, no Friday building."
>
> or
>
> "**Proposed mode: Push-to-build** — Carry-over queue is clean (1 P1 open). Energy fine. Constraint: don't accept 'while we're at it' scope — keep the surface narrow."
>
> or
>
> "**Proposed mode: Protect** — 8 Asana overdue, 5th consecutive push week, sleep < 6.5h all week. Constraint: ≤10h meetings, no new commitments."

User confirms or flips. Vibes always override the proposal — the builder reads their own state better than the data does.

### Step 1.7: Project stack rank

Read all active projects from `20-projects/` with enriched frontmatter (`lop`, `role`, `impact`).
Read `10-strategy/operating-memo.md` for "I Do" / "I Don't" / "My Traps".
Read `10-strategy/lops-summary.md` for current LOP health statuses.
Read last week's stack rank from `10-strategy/stack-rank/` (if exists) to see what moved and what stalled.

**Ranking algorithm (in priority order):**
1. Projects tied to at-risk LOPs get boosted (protect mode) or maintained (push modes)
2. Higher `impact` projects rank above lower
3. Projects where `role` = owner rank above sponsor/architect (you're the bottleneck)
4. Projects with `role` containing `->` get a "handoff checkpoint" flag
5. Projects untouched > 2 weeks get flagged as stale
6. In **push-to-build** mode: explorer and new-lever projects get boosted
7. In **push-to-close** mode: projects tied to repeat carry-over P1s get boosted; no new exploratory entries
8. In **protect** mode: fix/stabilize projects get boosted; cap Top 5 at 3 if needed
8. **Knowledge-graph signal (from Step 1f):** if an owned SLT topic is marked present-but-unpopulated or stale, the related project gets a "knowledge gap" note in the "Why This Rank" column. Not a boost — just a visibility flag so the builder can decide if closing the knowledge gap matters this week.

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
mode: push-to-build | push-to-close | protect
mode-rationale: "[evidence string — name the signals that drove the call, both objective and vibes]"
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
- **Knowledge graph accretion gap (from Step 1f):** If the knowledge-researcher flagged owned SLT topics as present-but-unpopulated for 2+ weeks running, surface it: "You own [N] SLT topics in the knowledge graph with no recorded Current State, Key Decisions, or Open Questions. The graph has [X] meeting mentions for these topics but zero synthesis. Either close-day 4c isn't firing on topics you own, or the graph is noise. Which?"

### Step 2.5: Management cadence lane (Signal)

Only runs when `SIGNAL_INGEST=1`. One call to the weekly team summary becomes the
manager's operating rhythm for the week. Pull it:

```bash
SIGNAL_INGEST=1 OBSIDIAN_VAULT_PATH="$OBSIDIAN_VAULT_PATH" python3.12 \
  ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/surface_management_for_week.py
```

Returns `{week_label, submitted, team_size, wins_count, celebrate_candidates,
develop_candidates, unblock_candidates (sorted by streak), cadence_alerts, sensitive_dropped}`.
Friction quotes are sensitivity-screened; raw Quick Notes never reach the vault.

Then reconcile the **durable loop-closure ledger** (Phase 4) — this persists friction
episodes across weeks so a resolved-but-never-closed loop keeps rolling forward:

```bash
SIGNAL_INGEST=1 OBSIDIAN_VAULT_PATH="$OBSIDIAN_VAULT_PATH" python3.12 \
  ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/loop_ledger.py --update
```

Returns `{close_the_loop:[{person,themes,resolved_week}], open:[{person,themes,weeks_open}],
p1_candidates:[{person,weeks_open}]}`. `close_the_loop` = friction that resolved but you
haven't told the person yet (the trust gap); `p1_candidates` = loops open ≥3 weeks.

This drives a **Management Cadence** block in the Week Plan (Step 3) and the
**three weekly management intentions** — the core of the lane:

```
### Management Cadence — week of [week_label]   ([submitted]/[team_size] submitted · [wins_count] wins)

**Set 3 intentions — one each, on three different reports:**
  🎉 Celebrate: [pick from celebrate_candidates] — say it publicly, in their channel
  🌱 Develop:   [pick from develop_candidates]  — the goal-linked move
  🔧 Unblock:   [pick from unblock_candidates]  — top streak first; own a fix + close the loop

**🔁 Close the loop (resolved — go tell them):**
  - [close_the_loop: person — themes] — friction resolved [resolved_week]; confirm the fix and tell them it was heard

**Still open:**
  - [open: person — themes (N wks)] — [⚠ P1 if in p1_candidates: open ≥3 wks, trust risk]

**Cadence:** [cadence_alerts] — [chronic → is Quick Notes right for them? / lapsed → check in]
```

**Rules:**
- The three intentions are the point — exactly one per bucket, each on a *different* report
  (recognition + development + unblocking spread across the team, never stacked on one person).
- **Streak ≥3 / any `p1_candidates` loop is a trust emergency** — it should usually become the
  unblock intention and may warrant a Top-3 slot this week.
- **Closing loops is the highest-leverage habit:** for each `close_the_loop` person, the move is
  to *tell them* it was heard and what changed. When you confirm you've done it, I run
  `loop_ledger.py --close "<name>" --note "<what you told them>"` so it stops rolling forward.
- A `chronic` cadence alert (rarely submits) is a different conversation than a `lapsed` one —
  chronic may mean Quick Notes isn't the right instrument for that person; lapsed is a check-in.
- Skip the whole lane if `enabled:false` or `available:false`.

### Step 3: Draft week plan

Present to the builder:

```markdown
## Week Plan: [date range]

### Coaching Notes
[1-2 pattern observations from Step 2 — be direct, not preachy]
[If cross-week insight signal detected: "For the [N]th consecutive week, [signal]. [What this suggests structurally, not as a one-off]."]

### Management Cadence
[The block from Step 2.5: 3 intentions (celebrate/develop/unblock on 3 different reports) + loop-closure + cadence. Skip if SIGNAL_INGEST disabled.]

### Body & Recovery (last 7 days)
- **VO2 max:** [latest reading] ml/(kg·min) (as of [date]) — 4-week delta: [+/-N.N]
- **Sleep:** [N.N]h avg (consistency: ±[N.N]h) — [N]% restorative
- **Exercise:** [N] min total (CDC target: 150)
- **HRV:** [N] ms avg — Δ vs prior week: [+/-N]
- **RHR:** [N] bpm avg *(or: "not captured — HAE gap")*

*[1-line interpretation: trajectory + most actionable signal. E.g., "Aerobic base trending slightly down; HRV stable; exercise under target — schedule 2 walks this week."]*

*Skip this whole section if Step 1g returned no data.*

### Active Quarterly Goals

*Populated from Step 1h. Skip section if no active goals.*

For each active personal goal:

- **[Goal title]** ([type], ends [date], [weeks remaining]w left)
  - Progress: [baseline] → [current] / [target] [unit] ([progress_pct]%)
  - Last 7 days: [hit rate description, e.g., "2/3 anchor days hit"]
  - This week: **[weekly action commitment]** at [anchor]
  - [Coaching question if hit_rate_7d < 50% OR trajectory_warning]

*If coaching signals fire, surface them as questions, not blame. Examples:*
> "Last week, [goal] fired 1/3 anchor days. What was different about the days it didn't fire?"
> "[Goal] metric has trended down 3 weeks straight. Time to revisit the protocol, the anchor, or the target?"
> "[Goal] has 2 weeks left and you're at 30% of target. Accelerate, rescope, or graduate to next quarter?"

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

### Step 4.6: Coaching Actions for the Week

Collect all NSLS people on this week's calendar and run the action surfacer in weekly mode (cap 5):

```bash
OPERATING_USER_EMAIL=$(grep '^OPERATING_USER_EMAIL=' ~/.claude/local-plugins/nsls-personal-toolkit/.env | cut -d= -f2 | tr -d '"') \
OBSIDIAN_VAULT_PATH="$OBSIDIAN_VAULT_PATH" \
python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/extract_coaching_actions.py 2>/dev/null

echo "$WEEK_ATTENDEES" | python3.12 \
  ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/surface_actions_for_day.py \
  --people-stdin --weekly
```

**Format in the week plan:**

```
🎯 Coaching Actions for the Week ([N])
  [Person] ([dimension]): [action text]
    (from "[goal title]")
  ...
```

**Also check the most recent team-pulse digest** at `$OBSIDIAN_VAULT_PATH/30-people/_pulse/YYYY-MM-DD-team-pulse.md`:
- If a "Manager Mode Review" prompt exists, surface it under the week plan as a question for Kevin to consider
- If "Proposed Coaching Updates" exist, surface them for review

**Rules:**
- Hard cap: 5 actions across the week
- Round-robin distribution: one action per person before stacking
- If `sweep_status.exit_code != 0` or last sweep was >18 days ago, alert
- If no actions surface AND no sweep error, skip this section

This gives Kevin a birds-eye view of which relationship moves to make this week, prioritized by who's actually on the calendar and what the data says is most important.

### Step 5: Write week plan

Write to: `$OBSIDIAN_VAULT_PATH/02-weekly/YYYY-[W]WW.md`

If a close-week already wrote this file, **merge** — keep the close-week sections (achievements, learnings, etc.) and add the plan sections below.

**Health frontmatter (from Step 1g):**

If Step 1g returned data, prepend or merge into the weekly note's frontmatter. These keys are read by `03-meta/weekly-health-trends.md` for graphing trajectory and hit-rate over time.

```yaml
---
# Weekly health aggregates (last 7 days ending Sunday of this week)
date: 2026-05-22  # week's end date — Tracker X axis (KEEP THIS — required for weekly-health-trends.md graphs)
exercise_min_total: 132
exercise_min_avg_per_day: 18.9
sleep_total_avg: 6.4
sleep_consistency_stddev: 0.6
sleep_restorative_avg_pct: 36
hrv_avg: 56
hrv_delta_vs_prior_week: 3
rhr_avg: null
vo2_max_latest: 36.2
vo2_max_delta_4w: -0.9
# Target hits (booleans for graphing hit-rate)
hit_exercise_target: false   # exercise_min_total >= 150
hit_exercise_stretch: false  # exercise_min_total >= 300
hit_sleep_target: false      # sleep_total_avg >= 7.0
hit_sleep_stretch: false     # sleep_total_avg >= 7.5
hit_restorative_target: true # sleep_restorative_avg_pct >= 25
hit_consistency_target: true # sleep_consistency_stddev <= 1.0
---
```

**Target definitions (do not change without updating `weekly-health-trends.md` to match):**
- `hit_exercise_target`: `exercise_min_total >= 150` (CDC moderate-intensity floor)
- `hit_exercise_stretch`: `exercise_min_total >= 300` (CDC upper benefit curve)
- `hit_sleep_target`: `sleep_total_avg >= 7.0` (NSF/AASM consensus floor)
- `hit_sleep_stretch`: `sleep_total_avg >= 7.5` (sweet spot)
- `hit_restorative_target`: `sleep_restorative_avg_pct >= 25` (Whoop/Garmin baseline)
- `hit_consistency_target`: `sleep_consistency_stddev <= 1.0` hour (variance regulates metabolic health more than total)

If a value is null (e.g., `rhr_avg` because HAE doesn't surface daily RHR), use YAML `null`. Don't compute `hit_*_target` for null-valued metrics.

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
