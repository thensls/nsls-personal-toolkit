---
name: quarter-set
description: Define or refine quarterly personal goals tied to behavior change. Runs deep anchor research (calendar + Familiar + journal) and goal-specific web research to design tiny-habit triggers and weekly action patterns. Trigger phrases - quarter set, set goals, quarterly goals, define goals, new quarterly goal, refine goals, goal planning, /quarter-set
---

# /quarter-set — Quarterly Goal Definition

## Goal

Help the builder define up to 3 personal quarterly goals with evidence-based protocols and habit-anchored weekly actions. Each goal becomes a markdown file in `10-strategy/goals/` with research, habit design, and a weekly log. Daily/weekly skills then push behavior toward these goals through cues, reflection, and metric tracking.

## Why

Goals without anchored behavior change drift. BJ Fogg's tiny-habits framework (Behavior = Motivation × Ability × Prompt) shows that consistent triggers anchored to existing routines outperform willpower. This skill builds in the trigger work upfront so the daily/weekly skills can do their job.

## When to Run

- Start of a new quarter (Jan 1, Apr 1, Jul 1, Oct 1) — or any time the builder wants to reset/refine goals
- Mid-quarter when a goal completes or gets abandoned and you want to add a new one
- When `personal-goals.md` shows zero active goals and the builder wants direction

## Constraints

- **Hard cap: 3 active personal goals per quarter.** If the builder is at the cap, /quarter-set won't add a 4th; it'll prompt to archive an existing one first.
- **Personal goals only by default.** Work goals (L3s) live in the LOP Airtable base — phase 2 will mirror those in. For now, `category: work` is allowed but doesn't trigger anchor research (work goals are outcome metrics, not behavior habits).

## Step-by-step Execution

### Step 1: Determine current quarter

Today's date is `$TODAY` (read at runtime). Compute the current quarter:
- Q1: Jan 1 – Mar 31
- Q2: Apr 1 – Jun 30
- Q3: Jul 1 – Sep 30
- Q4: Oct 1 – Dec 31

If today falls mid-quarter and no goals are active for the quarter, ask:
> "We're [X weeks] into Q[N]. Start the goal cycle for the rest of this quarter, or wait until the next quarter starts on [date]?"

Allow a "shakedown" cycle (e.g., start 2026-05-25, end 2026-06-30) when the builder is bootstrapping the system mid-quarter — use a `quarter` value like `2026-Q2-shakedown` for these.

### Step 2: Read existing goals

```
ls $OBSIDIAN_VAULT_PATH/10-strategy/goals/*.md
```

For each, read frontmatter. Build the current state:
- Active personal goals (category=personal, status=active)
- Active work goals (category=work, status=active)
- Recently completed/abandoned (last 90 days)

Present:

```
Current state ([current quarter]):
  Active personal: [N]/3
  - [Title] — [baseline → target unit], ends [date], status: [active]
  ...

  Active work: [N]
  - [Title] — [status]
  ...
```

### Step 3: Decide the action

Ask:
> "What do you want to do?
> 1. Add a new goal (you have [N] of 3 personal slots open)
> 2. Refine an active goal (adjust target, anchor, or weekly action)
> 3. Archive a completed/abandoned goal
> 4. Review research on an active goal"

Branch by choice. The rest of this skill covers the "add new goal" flow (the main path). Other flows are simpler edits.

### Step 4: Define the goal (interactive)

Ask one at a time, not as a single block:

1. **Title.** "What's the goal? One sentence."
2. **Why.** "Why does this matter right now? 1-2 sentences — used to ground the AI's coaching push."
3. **Type.** "Is this a metric goal (something measurable like VO2 max, steps, weight), a behavior goal (a frequency of action like 'meditate 5 days/week'), or a relationship goal (e.g., 'weekly 1:1 with each kid')?"
4. **Baseline + target + unit.** For metric: current value + target value. For behavior: current freq + target freq. For relationship: current state + desired state.
5. **End date.** Default = end of current quarter. Allow custom.
6. **Metric source** (if metric). Options:
   - `apple_health.vo2_max`, `apple_health.sleep_total_avg`, `apple_health.exercise_min_total`, `apple_health.hrv_avg`, `apple_health.steps`, `apple_health.weight`
   - `manual` (builder updates weekly via /close-week)
   - `airtable.<base_id>/<table_id>/<field_id>` (for goals tied to Airtable data)
7. **Category.** "Personal or work?" Default: personal.

Confirm summary back to the builder before research.

### Step 5: Deep anchor research (runs in parallel with Step 6)

This is the "tiny habit anchor" identification. Goal: find 3 candidate anchors — existing routines in the builder's life — that the goal's action can attach to.

**5a. Calendar pattern scan (past 4 weeks):**

```
mcp__claude_ai_Google_Calendar__list_events(
  timeMin="$TODAY - 28 days",
  timeMax="$TODAY",
  timeZone="America/Denver",
  maxResults=500
)
```

Group events by time-of-day window + day-of-week. Identify recurring slots (same DOW + ±30min time-of-day, occurring ≥3 of past 4 weeks). Examples: "Tue 9am SLT meeting (4/4 weeks)", "Mon/Wed/Fri 7:30am walk Red (10/12 days)".

**5b. Familiar routine scan:**

Use the `familiar` skill to surface recurring screen-activity patterns in the past 4 weeks. Look for:
- Consistent app-of-first-use in the morning (Slack? Mail? Specific URL?)
- Consistent "starting work" timestamps
- Consistent "transition" moments (lunch break starts, end-of-day signal)

**5c. Journal phrase scan:**

```bash
grep -h -i -E "morning|after coffee|bedtime|before bed|walk|first thing|every day|routine" \
  $OBSIDIAN_VAULT_PATH/01-daily/*.md \
  | tail -100
```

Surface phrases that describe existing rituals. These are anchors the builder has already named.

**5d. Score and rank candidates:**

For each candidate anchor, score on:
- **Consistency**: % of past 28 days it actually happened
- **Time-fit for goal**: morning anchors fit exercise/learning; evening anchors fit reflection; transition anchors fit short habits
- **Existing-behavior strength**: anchor to something already happening, not something aspirational

Present top 3 candidates with reasoning:
```
Top anchor candidates for [goal title]:

1. **Morning coffee, weekday 6:30-7:00am** (consistency: 26/28 days)
   Fit: high — exercise habits benefit from morning anchors; you already
   have a calm, predictable 30-min window here.

2. **After walking Red, Mon/Wed/Fri 7:45am** (consistency: 10/12 weekdays)
   Fit: high — already physically warmed up; immediate transition.

3. **End of SLT meeting, Tue 10am** (consistency: 4/4 Tuesdays)
   Fit: medium — only 1x/week, not enough for a daily habit.

Recommendation: #2 — strongest existing behavior, lowest friction.
```

Ask the builder to pick or propose a different anchor.

### Step 6: Goal-specific research (runs in parallel with Step 5)

For metric and behavior goals, run evidence-based research on protocols:

```
mcp__claude_ai_web-research(
  query="<goal-specific query — e.g., 'evidence-based VO2 max improvement protocols
        for 40-year-old male, current 36 ml/kg/min, training 3-4x/week'>"
)
```

Or invoke the `web-research` skill (Google AI Mode) for synthesized, cited findings.

Goal-type-specific query templates:
- **Aerobic fitness / VO2 max**: zone 2, intervals, Norwegian 4x4, training principles, adaptation timelines
- **Sleep**: sleep hygiene research, light exposure, circadian rhythm
- **Strength / muscle**: progressive overload, frequency, recovery
- **Focus time with kids**: child-development research on quality vs quantity, ritual vs spontaneous
- **Learning / skill acquisition**: deliberate practice, retrieval, spacing

Extract:
- 2-3 evidence-based principles
- A specific, testable weekly action pattern
- Common failure modes / pitfalls

Synthesize into a "Research" section for the goal file (with source citations).

### Step 7: Synthesize weekly action

Combine Step 5 (anchor) + Step 6 (research) into a concrete weekly action commitment.

Format:
```
Weekly action: [N]x [activity] ([duration]) — [intensity/quality marker]
Anchor: [trigger event], [day-of-week pattern], [time]
First action this week: [specific day + time]
```

Example (VO2 max):
```
Weekly action: 2x zone-2 sessions (45min each) + 1x interval session (4x4, 20min)
Anchor: After walking Red, Mon/Wed/Fri 7:45am
First action this week: Wed 2026-05-27, 7:45am — zone 2 walk, 45min
```

Confirm with builder before writing.

### Step 8: Write the goal file

Filename: `10-strategy/goals/{quarter-slug}-{goal-slug}.md`
- `quarter-slug`: `2026-Q3`, `2026-Q2-shakedown`, etc.
- `goal-slug`: kebab-case of title, e.g., `vo2-max`, `kid-focus-time`

Template:

```markdown
---
quarter: 2026-Q3
slug: vo2-max
title: Hold and improve VO2 max
category: personal
type: metric
baseline: 36.2
target: 37.0
unit: ml/(kg·min)
metric_source: apple_health.vo2_max
start: 2026-05-25
end: 2026-06-30
weekly_action: "2x zone-2 (45min) + 1x intervals (20min)"
anchor: "After walking Red, Mon/Wed/Fri 7:45am"
status: active
created: 2026-05-25
---

# Hold and improve VO2 max

## Why
[Why this matters — pulled from Step 4]

## Research
[2-3 evidence-based principles from Step 6, with source citations]

## Habit Design
**Anchor:** [chosen anchor from Step 5 with reasoning]
**Trigger pattern:** [day-of-week + time-of-day]
**Tiny version (for low-energy days):** [scaled-down minimum viable action]
**Celebration cue:** [BJ Fogg's "celebrate immediately" — what's yours?]

## Weekly Action Commitment
[Concrete weekly action from Step 7]

## Weekly Log

(Auto-populated by /close-week. Format per entry:)

### 2026-W## (week ending YYYY-MM-DD)
- **Metric:** [value if metric-source supplies it]
- **Hit rate:** [N/M days the daily-frontmatter goal_<slug>_moved was true]
- **What worked:** [from /close-week reflection]
- **What got in the way:** [from /close-week reflection]
- **Refinement:** [keep / adjust / abandon decision]

## Progress chart

\```tracker
searchType: frontmatter
searchTarget: goal_{slug}_moved
folder: 01-daily
startDate: -28d
endDate: 0d
bar:
    title: "Goal-of-day hit (last 28 days)"
    yAxisLabel: hit
    barColor: "#26A69A"
\```
```

### Step 9: Optionally seed first weekly action into Asana

Ask:
> "Want me to create an Asana task for the first action ([day + time])?"

If yes:
```
mcp__claude_ai_Asana__create_tasks(...)
```

with task name = the first action, due_on = the anchor day, assignee = builder.

### Step 10: Confirm and close

Show summary:
```
Goal created: [Title]
  File: 10-strategy/goals/[filename].md
  Weekly action: [action]
  Anchor: [anchor]
  Tracking: [metric source or manual]
  First action: [day + time]

Next: /open-week will surface this goal in your weekly view. /open-day will cue
you when today's anchor fires. /close-day will check the daily hit. /close-week
will write back to the Weekly Log.
```

## Edge cases

- **Builder is at 3-goal cap.** Don't add a 4th. Prompt to archive one first.
- **Goal already exists with same slug.** Ask: "[Title] is already an active goal. Refine, archive, or pick a different angle?"
- **Anchor research finds no consistent patterns.** Surface this: "Your past 28 days don't show a strong recurring routine that fits this goal's time-of-day needs. Want to commit to creating one (e.g., 'morning coffee at 6:30am for the next 3 weeks') and re-anchor in 3 weeks?"
- **Metric source returns null for baseline.** For Apple Health metrics, if the latest reading is null, fall back to the most recent non-null reading and note its age in the goal file.

## Hand-offs

- `/open-week` Step 1.4 reads goal files and surfaces them
- `/open-day` Step 2.5 reads anchor patterns and cues today's action
- `/close-day` writes `goal_<slug>_moved` frontmatter to daily notes
- `/close-week` runs structured reflection per goal, writes to Weekly Log

For work goals (L3 LOPs you own), see [[work-goals]] — those flow through the LOP Airtable base in phase 2.
