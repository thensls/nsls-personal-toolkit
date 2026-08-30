---
name: close-week
description: >-
  Friday weekly roll-up — synthesizes the full week (Sat-Fri) of daily notes into
  achievements, learnings, project progress, time allocation, and
  priorities-vs-reality. Formatted for quick notes copy-paste. Trigger phrases:
  close week, weekly review, week summary, week roll up, friday summary, weekly
  wrap, end of week
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

### Step 0.5: Check the visual companion

**Resolving the binary** (same helper as open-day Step 8 — builds the venv on first use; when the machine has no Python ≥3.10 it first downloads the toolkit's own private runtime — never send anyone to python.org). Three steps, **in this order**:

1. Ask what a real run would do:
```bash
STATE="$(bash "$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh" --check)"
```
2. Warn BEFORE any wait: `build` → one-time setup, ~30 seconds. `build-python` → it's fetching its own Python, a few minutes just this once. (`ready` → say nothing.)
3. Resolve — with a 10-minute timeout when the check said `build-python`:
```bash
TC="$(bash "$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh")"
```
Never print the build output; if `$TC` is empty, the stderr reason becomes the FIRST sentence of your reply (one plain line, no options menu).

**Only run this step if the target Friday is this Friday** (i.e., closing the current week). The companion shows data based on the current weekly note — if closing a past week, skip silently.

**Skip entirely if any of these is true:**
- `visual_mode: off` is set in `$OBSIDIAN_VAULT_PATH/50-reference/builder-profile.md`
- `$TC` came back empty (the companion can't be provisioned here — reason on stderr, detail in `companion/.install.log`), or it isn't running
- The weekly note at `02-weekly/YYYY-WNN.md` doesn't exist or has no open-week content (no Top 3 or stack rank to check off)
- This is a backfill run (closing a past week)

**When visual_mode is on and the companion is running:**

1. **Open the companion** at `<url>/week?mode=week-review&week=YYYY-WNN`:
   - macOS: `open "<url>/week?mode=week-review&week=YYYY-WNN"`

2. **Tell the builder:**

   > I opened the companion at `<url>/week`. Before we roll up the week, go mark your Top 3 as done/partial/missed and update your stack rank status.
   >
   > Say **done** when you're ready.

3. **Wait for "done".** Do NOT proceed until the builder explicitly responds. Do NOT treat background hook notifications as user input.

4. **After "done":** Re-read the weekly note to pick up the builder's check-off changes (priority statuses, project statuses). Proceed to Step 1.

**When visual_mode is off or the companion is unavailable:** Proceed to Step 1 as before — the builder confirms priorities via chat during synthesis.

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

**Then fetch the week's Fathom summaries — Step 2a's cascade cannot run without them.** The daily note's `## Meetings` section preserves only time, title, attendees and 1-2 takeaways; it carries no topic sections and no timestamps. Without this fetch the `topic` rung of Step 2a's cascade can never fire and every meeting falls through to project or unresolved, which is precisely the case where the role is broad (a leadership standing meeting) and the topic is the decisive signal.

```
list_meetings(     ← the Fathom connector's tool; resolve the live mcp__<uuid>__ name from this session's tools
  created_after="YYYY-MM-DDT00:00:00Z",   // Saturday (start of range)
  created_before="YYYY-MM-DDT23:59:59Z",  // Friday (end of range)
  include_summary=true,
  max_pages=5
)
```

Always date-scope the call — an unscoped fetch paginates the whole archive. If a meeting's listed summary carries no topic sections, fetch that one with `get_meeting_summary(recording_id=<id>)`; cap those at the handful of meetings whose quadrant is actually in doubt. For each meeting returned, carry forward:

```python
meeting_topics = [{
    "title": "...",                       # matched to the daily note's ## Meetings line
    "date": "YYYY-MM-DD",
    "attendees": ["..."],                 # feeds the cascade's role rung
    "hours": 1.5,
    "topic_sections": [                   # feeds the cascade's topic rung
        {"heading": "...", "timestamp": "00:00"},
        {"heading": "...", "timestamp": "00:34"},
    ],
    "recording_end": "01:00",             # the final section runs to here
}, ...]
```

`topic_sections` and their timestamps are what `portfolio-attribution.md` §3's split rule apportions hours by. Carry them even when a meeting has only one section — a single section still resolves the topic rung. When Fathom returns no summary for a meeting (not recorded, or `fathom: false` in the builder profile), carry the meeting with `topic_sections: []` and say so at Step 2a's confirm gate: that meeting can only resolve at the project rung or fall to unresolved, and the reason is a missing recording, not a missing judgment.

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
search_tasks(     ← the Asana connector's task search (resolve the live mcp__<uuid>__ name; `asana_search_tasks` on older connector versions)
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
search_tasks(     ← the Asana connector's task search (resolve the live mcp__<uuid>__ name; `asana_search_tasks` on older connector versions)
  assignee_any="me",
  completed=false,
  due_on_before="YYYY-MM-DD",  // today (Friday)
  sort_by="due_date",
  sort_ascending=true,
  opt_fields="name,due_on,projects.name",
  limit=50
)
```

**1e. Active quarterly goals + per-goal weekly progress**

Read goal files from `$OBSIDIAN_VAULT_PATH/10-strategy/goals/*.md` with `status: active` (skip dashboards and archive). For each:

1. Parse frontmatter.
2. Compute weekly hit rate: from the 7 daily notes already loaded in 1a, count notes with `goal_{slug}_moved: true` / count of notes that have the key (true/false).
3. If `type: metric` and `metric_source` is `apple_health.*`, query the apple-health MCP for the week's metric value (same logic as `/open-week` Step 1h).
4. If `type: behavior`, weekly progress = hit_rate.

Carry forward as `goals_for_reflection`:
```python
goals_for_reflection = [{
    "slug": "vo2-max",
    "title": "Hold and improve VO2 max",
    "baseline": 36.2, "target": 37.0, "current": 36.4, "unit": "ml/(kg·min)",
    "weekly_action": "2x zone-2 + 1x intervals",
    "anchor": "After walking Red, Mon/Wed/Fri 7:45am",
    "hit_rate": "2/3",  # days with goal_<slug>_moved: true / days with key set
    "weeks_remaining": 4,
    "trend": "stable",  # up | down | stable | no data
}, ...]
```

This feeds Step 2 (synthesis) and Step 3 (weekly goal reflection writeback).

Skip if no goals are active.

### Step 2: Synthesize

**🔢 Business numbers — read these FIRST, before writing anything else in this step.**

This read is structural, not optional, and it comes before achievements, learnings, or priorities. It exists because of a measured pattern (ledger **P002**, "business numbers absent from the weekly field of view"): weekly reviews measure the operating system exhaustively and the business almost never, while the instrumentation to surface the numbers already exists.

Report the current value, the direction since last week, and — for each — **what decision it would change**. A number with no decision attached is a vanity metric; say so and drop it.

| # | Number | Where it lives |
|---|---|---|
| 1 | Revenue vs. plan | NetSuite / finance review |
| 2 | Enrollment pace vs. the fall curve | HubSpot / Hex (Summit RSVP P&L app) |
| 3 | Response rate (the 0→2→5→7 ladder) | Gary push dashboard |
| 4 | Society engagement — signups, track completion, **returning visits / coach use** | Society Pulse, PostHog |
| 5 | Cash position + runway | Finance |

**Rules:**
- **Never write "not available" without naming the owner and the ask.** A number you can't get is a delegation, not a footnote. If Society Pulse can't answer returning visits, that's the dashboard gap — record it as an ask with a name on it.
- **Prefer the decision-relevant number over the available one.** Volume, send counts, and totals describe activity; conversion, return, and retention describe whether it's working. If the only number on offer is activity, write that down as the finding.
- **Owners report movement and what they learned, not volume.** If a workstream produced neither a moved number nor a nameable learning for 4+ weeks, flag it as a **resourcing decision** (prioritize / shrink to maintenance / stop) rather than a reporting problem. That's a personnel call, and it belongs in front of the builder, not buried.
- If a per-team KPI sheet exists at `$OBSIDIAN_VAULT_PATH/10-strategy/kpis/`, read it instead of this generic list — it's the canonical set, named by the builder.

Carry this read into Step 3's priorities. **P002 closes when this read happens because the template forced it, not because the builder happened to look.**

---

**Step 2a — Portfolio attribution.** Runs here, before Achievements and Project Progress, because the quadrant grouping drives how both are written. The judgment calls (mode-inference verbs, meeting-topic→quadrant mapping, the confirm-gate table format) live in `skills/close-week/references/portfolio-attribution.md` — read it, don't re-derive it. The arithmetic lives in `companion/portfolio.py` and is **run, not re-derived**: this step builds a JSON payload and pipes it to `python3 -m companion.portfolio`, then renders the JSON that comes back. Never compute a quadrant total, a percentage, or a flag by hand — if the module didn't say it, it isn't in the output.

1. **Project rows.** Parse the week's daily notes with the module's parse mode — one run per note that EXISTS, the note's markdown on stdin:

   ```bash
   for DATE in $SAT $SUN $MON $TUE $WED $THU $FRI; do   # all 7 days, Sat-Fri
     NOTE="$OBSIDIAN_VAULT_PATH/01-daily/$DATE.md"
     if [ -f "$NOTE" ]; then
       echo "=== $DATE ==="
       python3 -m companion.portfolio --parse-daily < "$NOTE"
     else
       echo "=== $DATE === no daily note — 0 parsed, 0 skipped"
     fi
   done
   ```

   **Iterate over the notes that exist, and report the absent dates.** A normal week is missing Sunday's note (see Step 1a). `< "$OBSIDIAN_VAULT_PATH/01-daily/YYYY-MM-DD.md"` on a file that isn't there fails at shell redirection *before* the module runs, so a hard seven-run loop can never reach the confirm gate. An absent date is a real fact about the week — print it as `0 parsed, 0 skipped`, never omit it quietly, and never invent rows for it.

   It returns `project_weeks` (one row per well-formed `## Projects Touched` line) plus `skipped_lines` / `skipped_count`. Do **not** hand-roll a regex for this — the format contract between close-day and close-week is verified in exactly one place, and that place is this parser.

   **Collapse by `(project, quadrant)`, never by project alone.** Sum `hours` and weight-average `offense_pct` by hours *within each pair*. A project whose week spanned two quadrants yields two rows, not one — quadrant is a property of the activity, not of the project, so merging a project's growth-driver Tuesday into its reliability Thursday destroys the exact dimension this feature exists to measure. A row with no `portfolio-category` stays `uncategorized` (parses to quadrant `null`) — never guessed into a bucket, and it collapses only with other `uncategorized` rows for the same project.

   **Carry every day's `skipped_count` to the confirm gate (step 3), including the zeros.** A skipped line is a project's hours disappearing from the week with no other signal — the same silent failure the flags exist to catch, one layer up. Report it as, e.g., "Tue: 3 of 4 lines parsed — 1 skipped: `<the raw line>`", and offer to fix the daily note before continuing.

2. **Meeting rows.** For each meeting from Step 1a's `## Meetings` data, joined to that meeting's entry in Step 1a's `meeting_topics`, resolve it through the cascade: an attendee match in `~/.claude/portfolio-role-map.txt` (role) → the meeting's `topic_sections` from Step 1a's Fathom fetch, mapped to quadrants per `portfolio-attribution.md` §3 and apportioned by the span between consecutive timestamps (topic — may split across quadrants) → the meeting's mapped project's `portfolio-category` (project) → `unresolved`. Record which rule fired as `resolved_by` for every row. A meeting whose `topic_sections` came back empty skips the topic rung — note the reason at the confirm gate rather than letting it read as a judgment call.

   **Collapse recurring meetings by `(meeting name, quadrant)`, not by name alone** (per `portfolio-attribution.md` §4). Two occurrences of the same standing meeting that resolved to different quadrants stay two rows. Merging them by name would average away the very split the topic rung just made — the same mistake as collapsing project rows by project alone. If a recurring meeting already has an entry in `~/.claude/portfolio-meeting-cache.json`, pre-fill its row from the cache (still editable at the confirm gate).

3. **Confirm gate.** Present the PROPOSED table exactly as formatted in `portfolio-attribution.md` §4 — project rows plus meeting rows, every cell editable. Above the table, print the per-day parse line from step 1 (`N of M lines parsed`, with the raw text of anything skipped; `no daily note — 0 parsed, 0 skipped` for a date with no note). **Write nothing before the user confirms.** Rejecting the whole table is a valid outcome: the weekly note gets no `## Portfolio Allocation` section, rather than a guessed one.

4. **On confirm, build the payload and run the module.** Payload keys (see `portfolio-attribution.md` §7 for the full shape and a worked example): `project_weeks` (from step 1, post-confirm), `meeting_rows` (from step 2, post-confirm), `history`, `driver_hours`, `held_hours`.
   - `history`: read the prior 1-2 closed weekly notes' frontmatter — `portfolio_by_quadrant` / `portfolio_by_mode` (written back by this skill's Step 5) — and **rekey each entry before it goes into the payload**: the frontmatter's `portfolio_by_quadrant` becomes the entry's `by_quadrant`, and `portfolio_by_mode` becomes `by_mode`. This is not optional bookkeeping — `_totals_from_history_entry()` in `companion/portfolio.py` reads only the unprefixed keys via `.get("by_quadrant")` / `.get("by_mode")`; a history entry still carrying the `portfolio_` prefix misses both, reads as an empty week, and silently kills the reliability-starvation and rising-defense-share flags while looking exactly like "no flags fired." Each `history` entry, after rekeying, looks like: `{"by_quadrant": {"growth-driver": 14.0, ...}, "by_mode": {"offense": 12.0, "defense": 8.5}}` — most recent week first. No prior data — first week on this pipeline, or a skipped week — means `"history": []`; `evaluate_flags` treats missing history as "no data," never as a manufactured zero.
   - `driver_hours` / `held_hours`: sum this week's confirmed project hours by each project's `portfolio-role` frontmatter (`driver` vs. `held`). **`--parse-daily` does not return `portfolio-role` — the daily-note line carries hours, quadrant and offense only — so read it yourself, once per distinct project slug in the confirmed table, from that project's home doc frontmatter at `$OBSIDIAN_VAULT_PATH/20-projects/<slug>/<slug>.md`** (the slug is the one inside the daily note's `[[20-projects/<slug>|…]]` link). A project whose home doc is missing, or whose frontmatter has no `portfolio-role`, counts toward **neither** total — say so at the confirm gate rather than defaulting it to `held`, which would manufacture the held-out-earning-drivers flag out of a missing field.

   ```bash
   python3 -m companion.portfolio <<'JSON'
   {"project_weeks": [...], "meeting_rows": [...], "history": [...], "driver_hours": 0.0, "held_hours": 0.0}
   JSON
   ```

5. **Write back, only now.** Append any newly-resolved recurring meetings to `~/.claude/portfolio-meeting-cache.json`.

6. **Render, don't recompute.** The module's stdout (`by_quadrant`, `by_mode`, `by_quadrant_mode`, `unresolved_hours`, `total_hours`, `percentages`, `mode_percentages`, `quadrant_mode_percentages`, `unresolved_pct`, `rejected`, `flags`) is the entire content of the `## Portfolio Allocation` section (Output A, template below) and the quadrant grouping used in Project Progress (both outputs). Every figure in those sections traces back to this one call — including every percentage, which is why there is nothing left for this step to divide.

   **`rejected` is never empty for free — show it.** Each entry is `{kind, row, reason}` for a row the module refused to trust (a quadrant outside the vocabulary, an `offense_pct` outside 0-100, negative hours, a negative split share). Their hours went to unresolved, or — for negative hours — left the week's total entirely. Print one line per entry directly beneath the Flags block: `⚠️ <kind> "<name>": <reason>`. A rejected row you don't render is a number the module deliberately refused to guess at, silently corrected on its way to the page — the exact failure mode this feature exists to catch. If `rejected` is non-empty, the fix is in the source (the daily note or the confirmed table), not in the output.

---

**Achievements:** Scan all Work Log bullets across the week. Pick the 5-8 most impactful — things that shipped, decisions that moved the needle, external commitments met. Prefer concrete outcomes with numbers over activity descriptions.

**Learnings:** Look for:
- Patterns across meetings (Fathom themes)
- Things that failed or were harder than expected
- Insights from conversations (Slack, email)
- Process improvements discovered
- "I wish I had..." moments from carry-overs that piled up

**Project Progress:** For each project that appeared in any daily note's `## Projects Touched`, summarize the week's movement. Status = on-track (touched 2+ days or key milestone hit), needs-attention (touched but blocked), stalled (not touched despite being active). Group the result by portfolio quadrant, using the confirmed quadrant from Step 2a (not the raw frontmatter default) — see the Output A and Output B templates below for the exact grouped shape. Never omit an empty quadrant; print it with "0h, nothing moved" instead.

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

**Capture the weekly total as `work_hours_total`** (a number, hours) for the frontmatter in Step 5. This is *total work time* — the bold **Week** total after adding any off-screen/in-person/travel hours that Familiar can't see (per the builder's total-work-time convention), **not** just screen-active hours. If the week had significant uncaptured in-person work, add it by hand and note the adjustment in the Time Allocation prose. This feeds the "Total weekly work hours" chart in `03-meta/weekly-health-trends.md`.

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
- If >50% of significant work went to reactive/maintenance/fix projects → actual = **protect**
- If most time went to new initiatives, exploratory work, or expanding the surface → actual = **push-to-build**
- If most time went to closing carry-over P1s, finishing handoffs, or clearing the queue without starting new lines → actual = **push-to-close**
- Mixed is fine — note it honestly. Push-to-close is often invisible: it looks like maintenance because the artifacts are emails and decisions, not new builds.

Present and append to the weekly note:
```
## Push/Protect

| Planned | Actual | Notes |
|---------|--------|-------|
| [mode] | [mode] | [1-line honest assessment] |
```

Note the running streak: "This is your Nth consecutive [mode] week." Flags:
- **Protect streak >= 3:** "3 protect weeks in a row. Your push projects haven't moved since W[N]. Structural issue or right call?"
- **Push streak (any flavor) >= 3:** "3+ push weeks in a row. Body and calendar over-extended? Protect mode bias next week unless carry-over forces push-to-close."
- **Push-to-close streak >= 2 with same items recurring:** "Carry-overs aren't closing across 2+ push-to-close weeks. The structure has to change, not the resolve. Break items down smaller, delegate, or kill."

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

### Step 2b. NSLS Knowledge Base week audit

Always runs. Everyone gets the audit; write actions (promotions, stale-flags) apply to your KB — pushed if you're on SLT (company KB), committed locally otherwise.

```bash
echo "Step 2b: auditing your knowledge base for week $WEEK..."
```

Invoke the harvest skill in audit mode:

```
/harvest-meeting --week-audit --week $WEEK
```

The skill displays:
- Activity summary (commits, edits, files touched)
- Unharvested meetings
- Stale topics (last-updated > 60 days)
- Open Questions older than 30 days

The skill additionally (for everyone, against your own KB):
- Offers promotions for resolved Open Questions → Key Decisions
- Offers stale-flag updates on old topic frontmatter

The user approves changes via the same numbered-list UX as `/harvest-meeting --date`.

**After the skill returns:** Append a `## Knowledge Base` section to the weekly close note with the audit summary (and any commits made).

### Step 2c. Role coaching (role-coach weekly block)

Runs when `$OBSIDIAN_VAULT_PATH/10-strategy/role-coaching/role-profile.md` exists; otherwise heartbeat the skip.

```bash
echo "Step 2c: invoking /role-coach --week $WEEK (role coaching from your seat)..."
# or: echo "Step 2c: no role-profile.md — /role-coach not set up, skipping"
```

Invoke the role-coach skill:

```
/role-coach --week $WEEK
```

The skill will:
- Sweep the week's evidence (vault + whatever sources its scope probe finds), every claim cited
- Render the ≤10-line Role Coaching block: Said / Did / Gap + pattern-ledger deltas + Horizon (if a trajectory exists)
- Propose ledger bookkeeping (ok-class) and any moves/proposals (explicit-yes class)
- Write one cue candidate to `~/.cache/role-coach/cues.json` for next week's /open-week pool (after the move is restated)

**After the skill returns:** Append the approved Role Coaching block to the weekly close note as a `## Role Coaching` section. Outcome lines (exactly one):
- `## Role Coaching` section appended — [N] patterns updated, cue queued for open-week
- Role coaching skipped — no role-profile.md (run /role-coach to set up)
- Role coaching declined this week — noted, ledger untouched

### Step 3: Generate two outputs

**Output A: Weekly Review note** (for Obsidian)

Write to: `$OBSIDIAN_VAULT_PATH/02-weekly/YYYY-[W]WW.md`

Full format with Dataview queries for projects touched/not touched.

**Include `## Portfolio Allocation` whenever Step 2a's confirm gate was confirmed**, immediately after the Business Numbers table and before Achievements (Step 2a runs there for exactly this reason). If the builder rejected the whole table at the confirm gate, this section is omitted entirely from the weekly note — per Step 2a #3, a rejected table produces no section, never a guessed one. When it is included, populate it from Step 2a's module output — every cell is a value the module returned, never a hand computation:

```markdown
## Portfolio Allocation

| Quadrant | Hours | % | Offense / Defense | Top items |
|---|---|---|---|---|
| ① Growth driver | 0.0h | 0% | — | — |
| ② Operating efficiency | 0.0h | 0% | — | — |
| ③ Hygiene | 0.0h | 0% | — | — |
| ④ Reliability | 0.0h | 0% | — | — |
| Cross-cutting | 0.0h | 0% | — | — |
| Unresolved | 0.0h | 0% | — | — |

**Week Offense / Defense: X% / Y%** (project work only — meetings carry a quadrant, not a mode)

**Flags:**
- [one line per flag from the module's `flags`, or "none this week"]

**Rejected rows:**
- [one line per entry in the module's `rejected` — `⚠️ <kind> "<name>": <reason>` — omit this whole block only when `rejected` is empty]
```

**Filling the columns.** Every one comes from the module's stdout, and none of them is a division this step performs:

| Column | Source |
|---|---|
| Hours | `by_quadrant[q]`, and `unresolved_hours` for the last row |
| % | `percentages[q]`, and `unresolved_pct` for the last row |
| Offense / Defense | `quadrant_mode_percentages[q]` — **but first check `by_quadrant_mode[q]`.** If its offense and defense hours are both `0.0`, that quadrant recorded no mode: print `—`, never `0% / 0%`. This is the ONLY reason a row prints `—` |
| Top items | the 1-2 largest confirmed project or meeting rows in that quadrant, by hours, from Step 2a's confirmed table — names only, no new numbers |
| Week Offense / Defense | `mode_percentages` |

A row's Hours and its Offense / Defense do not cover the same hours: Hours include that quadrant's meeting time, mode covers only its project time. Say so in one line beneath the table so nobody reads the split as a partition of the row.

**Cross-cutting is a quadrant like any other and takes its mode from `by_quadrant_mode` / `quadrant_mode_percentages`.** It holds project rows with genuine offense/defense splits (founder and seat work outside the org portfolio is still built or still defended), so hard-coding it to `—` renders a 100%-defense cross-cutting week as no data at all — the silent-empty this feature exists to prevent, on the one quadrant nobody would think to check. **Only `Unresolved` has no mode by construction** and always prints `—`: it is not a quadrant and the module records no mode hours against it. Any other row — cross-cutting included — prints `—` when, and only when, its `by_quadrant_mode` hours are both `0.0`, which means the quadrant's hours are entirely meeting hours (mode genuinely unknown) or it has no hours at all.

Never omit a quadrant row, including one with 0h — an omitted row is exactly how reliability disappears from view. The Unresolved row always appears, even at 0h, and is never folded into any quadrant; its hours count toward the week total (`total_hours` includes `unresolved_hours`), so every quadrant's `%` is a true share of the whole week, not just the resolved subset.

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

Project Progress (by portfolio quadrant):
(1) Growth driver - Xh
  <project>: <status> - <one line>
(2) Operating efficiency - Xh
  <project>: <status> - <one line>
(3) Hygiene - Xh
  <project>: <status> - <one line>
(4) Reliability - Xh
  <project>: <status> - <one line>
Cross-cutting - Xh
  <project>: <status> - <one line>
Unresolved - Xh
  <meeting/item>: <one line>

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

When a quadrant has no project movement, print the quadrant heading with `- 0h, nothing moved` rather than omitting it. This includes Cross-cutting and Unresolved — Unresolved dropping out of the copy-paste journal is the same silent-failure the flags exist to catch. An omitted quadrant (or an omitted Unresolved line) is how reliability disappears. Quadrant hours and grouping come from Step 2a's confirmed output, not a fresh guess at synthesis time.

**Output B.5: Per-goal weekly reflection** (interactive — appended to each goal file's Weekly Log)

For each goal in `goals_for_reflection` (from Step 1e), conduct a 3-prompt reflective conversation. Don't batch — ask one goal at a time, one prompt at a time. Keep prompts open-ended, not leading.

Prompts per goal:

> **For [Goal title]:**
> Hit rate this week: [N/M anchor days fired]. Metric: [current] [unit] ([trend vs last week]).
>
> 1. **What worked toward this goal this week?**
> 2. **What got in the way?** (Skip if hit rate is 100% — nothing to diagnose.)
> 3. **Refinement for next week?** — keep the same action/anchor, adjust (specify how), or pause/abandon?

After all goals, write back to each goal file's Weekly Log section:

```markdown
### 2026-W## (week ending YYYY-MM-DD)
- **Metric:** [current] [unit] ([Δ vs last week])
- **Hit rate:** [N/M]
- **What worked:** [from response 1]
- **What got in the way:** [from response 2 — or "—" if 100% hit]
- **Refinement:** [from response 3]
```

If a goal's `weeks_remaining ≤ 1` and progress ≥ 80%, prompt: "Looks like you're closing in on the target. Graduate this goal next week and pick a new one?"

If a goal's `weeks_remaining ≤ 0` (cycle ended), prompt: "Cycle ended. Status: [done | abandoned | extend]?" Then update the goal file's frontmatter `status` accordingly.

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
- **Group Project Progress by portfolio quadrant in both Output A and Output B, reading each project's confirmed quadrant from Step 2a. Never omit an empty quadrant.**

### Step 4: Present to user

Show both outputs. Ask:
- "Anything to add or adjust before I write the weekly note?"
- "Quick notes version ready to paste — want any edits?"

### Step 5: Write weekly note

Write Output A to `02-weekly/YYYY-[W]WW.md`. Include the AI-Suggested Next Week sections at the end — these are picked up by `/open-week` as a starting point for next week's planning.

**Also write Output B (Quick Notes) into the weekly note** as a `### Quick Notes` section at the end, after the AI-Suggested sections. This allows the visual companion to display a copy-to-clipboard block so the builder can paste directly into their Coach journal without scrolling through chat. Format the section as plain text (no markdown formatting inside it).

Set `status: closed` in the weekly note frontmatter. This signals the companion to switch to `week-results` mode, which shows the read-only results dashboard with the Quick Notes copy button.

Also write `work_hours_total: <number>` into the frontmatter (from Step 2's Time Allocation total). This is read by the "Total weekly work hours" chart in `03-meta/weekly-health-trends.md`; omit the key only if the week has no defensible total (e.g., no Familiar data and no in-person estimate) rather than writing a guess.

**Also write `portfolio_by_quadrant` and `portfolio_by_mode` into the frontmatter** — the exact `by_quadrant` and `by_mode` objects Step 2a's module call returned this week. This is the only persistence for portfolio history: next week's Step 2a reads this note's frontmatter back as its `history[0]` entry. **The `portfolio_` prefix exists only to namespace these two keys inside the weekly note's frontmatter (alongside `work_hours_total` and everything else there) — it MUST be stripped back off when the keys are read into the payload's `history` list** (see Step 2a's rekeying instruction). Omit both keys only if Step 2a's confirm gate was rejected this week (no module run happened) — never write a guessed pair.

If the companion is running, tell the builder:
> Weekly note written. The companion has your quick notes ready to copy at `<url>/week`.

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
