---
date: 2026-05-25
slug: apple-health-and-quarterly-goals
last_commit: 9c8daf747dec6a06fee2c95e9eeacb5810b4dffd
commit_range: de6d64f..9c8daf7
skills_changed: [open-day, open-week, close-day, close-week, quarter-set]
files_changed: 5
cost_to_adopt: "30+ min"
breaking: false
---

# Apple Health integration + quarterly goal system

## Why

You can now turn high-level life intentions (improve VO2 max, more focused time with kids) into something the daily and weekly skills actively push toward. Set a goal once with `/quarter-set` — the AI researches evidence-based protocols, archaeologically finds the strongest anchor in your existing routines, commits a weekly action pattern. Each morning `/open-day` cues anchor days; `/close-day` asks if you moved the goal; `/open-week` surfaces hit rate with coaching pushes when it slips; `/close-week` runs a deep 3-prompt reflection that writes back to the goal's log. Combined with the new Apple Health integration that surfaces yesterday's sleep/exercise/steps + restorative-% in the morning view, it's a closed-loop system: metrics + intentions → behavior over weeks.

## What Changed

### `open-day` — Apple Health snapshot + goal anchor cues

- **New Step 2k**: pulls yesterday's daily summary from the `apple-health` MCP (sleep total + stages, exercise minutes, steps, HRV, active energy). Computes `sleep_restorative_pct` = (deep + REM) / total — the closest proxy to a "sleep quality score."
- **New Step 2l**: reads active personal goals from `10-strategy/goals/`; if today's day-of-week matches a goal's anchor pattern, fires a cue in Morning Check-in ("Goal cue today: zone-2 walk before Slack opens").
- **Morning Check-in draft** opens with a `Yesterday's body` line and a `Goal cues today` block.
- **Daily note template** gains 8-key health frontmatter (`sleep_total_hrs`, `sleep_restorative_pct`, `sleep_deep_hrs`, `sleep_rem_hrs`, `exercise_min`, `steps`, `active_energy_kcal`, `hrv_ms`) for Tracker/Dataview graphing.
- **Subjective "Energy:" line renamed to "Mood:"** since the body metrics now carry the physiological story; the subjective slot stays for emotional/cognitive state.

### `open-week` — Body & Recovery + Active Quarterly Goals

- **New Step 1g**: pulls 28-day `apple_health_trends`; aggregates into weekly metrics (VO2 max latest + 4-week delta, 7d HRV avg + delta vs prior week, total exercise vs 150-min CDC target, sleep average + consistency stddev, restorative %).
- **New Step 1h**: reads active goal files; for metric goals queries the MCP for current value; for behavior goals counts `goal_<slug>_moved` daily booleans; surfaces coaching signals if hit rate < 50% or trajectory wrong-way for 3+ weeks.
- **Step 3 draft** gets a `Body & Recovery` section and an `Active Quarterly Goals` section with target-hit indicators and this-week ask per goal.
- **Step 5 write** adds health frontmatter to the weekly note (`exercise_min_total`, `sleep_total_avg`, `vo2_max_latest`, etc.) plus six target-hit booleans (`hit_exercise_target`, `hit_sleep_target`, `hit_restorative_target`, `hit_consistency_target`, plus stretch variants) and a `date:` field used as the Tracker X-axis.

### `close-day` — daily-light goal touch

- **New Step 1i**: reads active goals to set up the End-of-Day prompt list.
- **End of Day** template gains a "Goals moved today" line — one entry per active goal.
- **Step 5 write** adds `goal_<slug>_moved: true | false` to the daily note's frontmatter for each active goal that got a response. This boolean feeds the 28-day hit-rate Dataview in `personal-goals.md` and the per-goal Tracker chart in each goal file.

### `close-week` — weekly-deep goal reflection

- **New Step 1e**: pulls active goals + computes weekly hit rate from the past 7 daily notes.
- **New Output B.5**: per active goal, runs a structured 3-prompt reflection (what worked / what got in the way / refinement: keep, adjust, or pause). Writes the response to the goal file's Weekly Log section as a dated entry.
- **Auto-graduation prompt** if `weeks_remaining ≤ 1` AND progress ≥ 80%, or **cycle-end prompt** if the goal's `end` date has passed.

### `quarter-set` (new) — goal definition with anchor + protocol research

Interactive skill for defining up to 3 personal quarterly goals. For each:
- Defines title, type (metric/behavior/relationship), baseline, target, end date, metric source
- Runs **deep anchor research**: scans 4 weeks of Google Calendar + Familiar screen activity + journal phrases to identify the 3 strongest existing-routine candidates as habit anchors (consistency-scored, time-of-day fit, behavioral strength)
- Runs **goal-specific web research** via the `web-research` skill (Google AI Mode) for evidence-based protocols, realistic targets, common failure modes
- Synthesizes a concrete weekly action pattern + recommended anchor with reasoning
- Writes a goal file to `10-strategy/goals/<quarter>-<slug>.md` with: frontmatter (status, baseline, target, weekly_action, anchor, metric_source), Why, Research, Habit Design (BJ Fogg tiny-habits framing), Weekly Log, embedded Tracker charts

Hard cap of 3 active personal goals per quarter; `category: personal` vs `category: work` split via frontmatter (work goal integration with the LOP Airtable base is phase 2).

## Cost to Adopt

**30+ min** — most of the cost is one-time setup outside the repo (Apple Health MCP, Tracker plugin, vault directory) plus the 20-30 min interactive `/quarter-set` run for your first goal. The skill changes themselves are git-pull only.

## Safe Merge

**If you haven't customized these skills:**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/quarter-set/SKILL.md \
                              skills/open-day/SKILL.md \
                              skills/open-week/SKILL.md \
                              skills/close-day/SKILL.md \
                              skills/close-week/SKILL.md
git commit -m "pull upstream: apple-health-and-quarterly-goals"
```

**If you have customized one or more of those four planning skills**, do them one at a time:

```bash
# What upstream changed
git diff HEAD upstream/main -- skills/<skill>/SKILL.md

# What you've changed locally
git log --oneline de6d64f..HEAD -- skills/<skill>/SKILL.md
```

Three options per skill:
1. **Accept upstream, lose your changes** — `git checkout upstream/main -- skills/<skill>/SKILL.md`
2. **Merge manually** — keep your customizations, copy in the relevant new step blocks (they're clearly labeled "**1g.**", "**1h.**", "**1i.**", "**1e.**", "**2k.**", "**2l.**", "**Output B.5**")
3. **Skip this skill entirely** — your fork stays on its current version; that skill misses this update

The `quarter-set` skill is new — there's nothing to merge against, just `git checkout upstream/main -- skills/quarter-set/`.

## Opt-Out Guide

The two features are **independent**. You can adopt either without the other:

- **Apple Health integration only** — pull `open-day` (Step 2k + frontmatter + Mood rename) and `open-week` (Step 1g + Body & Recovery + Step 5 health frontmatter). Skip Steps 2l, 1h, 1i, 1e and the `quarter-set` skill.
- **Goal system only** — pull `quarter-set`, plus the goal-related steps in the four planning skills (2l, 1h, 1i, 1e + Output B.5). Skip Step 2k and Step 1g (Apple Health). Goals can use `type: behavior` or `metric_source: manual` to avoid the MCP dependency.
- **Both** — adopt the whole thing.

Each integration point lives in its own clearly-labeled step block. If you only want some, deleting the others by step number is safe — no cross-step dependencies inside this release.

## Manual Steps

- [ ] **Apple Health MCP setup** (if not already done): clone `github.com/daveremy/apple-health-mcp`, configure the iOS Health Auto Export app to write CSV/JSON to iCloud Drive, register the MCP server in `~/.claude.json` user scope with the `APPLE_HEALTH_EXPORT_DIR` env var. Without this, Step 2k and Step 1g skip silently — not fatal but you lose the body metrics.
- [ ] **Obsidian Tracker plugin** (only if you want the graphs): download from `github.com/pyrochlore/obsidian-tracker/releases/latest`, drop `main.js` + `manifest.json` + `styles.css` into `<vault>/.obsidian/plugins/obsidian-tracker/`, add to `community-plugins.json`, restart Obsidian, enable in Settings → Community plugins.
- [ ] **Vault directory** for goals: `mkdir -p $OBSIDIAN_VAULT_PATH/10-strategy/goals/archive`
- [ ] **Dashboard files**:
  - Create `10-strategy/goals/personal-goals.md` with a Dataview block filtering on `category = "personal" AND status = "active"`
  - Create `10-strategy/goals/work-goals.md` (placeholder for phase 2 — the LOP Airtable mirror)
  - Optionally create `03-meta/health-trends.md` and `03-meta/weekly-health-trends.md` with Tracker blocks for daily/weekly graphs
- [ ] **Run `/quarter-set`** to define your first goal (20-30 min interactive). VO2 max is a good first goal if you have Apple Health flowing — the metric source auto-tracks.

Not breaking — if you skip these, the skill changes degrade gracefully. Step 2k/1g report "no data" and skip; Steps 2l/1h/1i/1e see no goal files and skip; the daily note frontmatter just doesn't get populated.

## Commits Included

- `9c8daf7` — feat: Apple Health integration + quarterly goal system
