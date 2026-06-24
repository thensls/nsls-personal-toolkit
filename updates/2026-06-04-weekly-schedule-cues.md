---
date: 2026-06-04
slug: weekly-schedule-cues
last_commit: eb21cfec83d6ab9f83a84192584f79bbbda84aa5
commit_range: 7e02794..eb21cfe
skills_changed: [open-day]
files_changed: 1
cost_to_adopt: "2 min"
breaking: false
---

# Day-specific goal cues in your morning planner

## Why

Your morning planner stops saying a generic "work toward your goal" and starts telling you exactly what *today* is — "easy 30-min Z2" or "HARD 4×4 intervals." Most real goals have a day-by-day rhythm (training plans, study schedules, practice routines), not one flat weekly action. `/open-day` now reads that rhythm and surfaces the right session for the day you're actually in. And you can set a plan up in advance with a start date, so it won't nag you to go hard during a recovery or ramp-in week.

## What Changed

### `open-day` — goal cues become day-aware
- Goal files in `10-strategy/goals/` can now carry a **`weekly_schedule:`** map (keys `mon`…`sun`). `/open-day` looks up today's day-of-week and shows that specific session in the Morning Check-in, instead of a flat weekly summary.
- **Rest days don't fire.** An entry whose text starts with `Rest` (or is empty) produces no cue — no nag on your off days.
- New **`weekly_schedule_effective:`** date field. Set a schedule up ahead of time; before that date `/open-day` fires a soft "easy / optional" bridge cue instead of prescribing a hard session. Good for ramp-ins and recovery windows.
- **Fully backward-compatible.** Goals without `weekly_schedule` keep using the existing `anchor:` parsing exactly as before. Nothing changes until you opt in.

## Cost to Adopt

**2 min** — it's a one-file `git pull` of `open-day/SKILL.md`, no manual steps. Using the new capability is optional and additive: add a `weekly_schedule` map to a goal whenever you want day-specific cues.

## Safe Merge

**If you haven't customized `open-day`:**
```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/open-day/SKILL.md
git commit -m "pull upstream: weekly-schedule-cues"
```

**If you have customized `open-day`:**
```bash
# What upstream changed (the new goal-cue logic lives in Step 2l)
git diff HEAD upstream/main -- skills/open-day/SKILL.md
```
The change is localized to the **goal anchor cues** step (Step 2l) — it adds a "prefer `weekly_schedule`" path above the existing anchor parsing and an effective-date guard. Three options:
1. **Accept upstream** — `git checkout upstream/main -- skills/open-day/SKILL.md` (loses your open-day edits)
2. **Merge by hand** — paste the new `weekly_schedule` block into your Step 2l, keep everything else of yours
3. **Skip** — stay on your version; you keep flat `weekly_action`/`anchor` cues

## Opt-Out Guide

It's a single skill and a single file — there's nothing to partially adopt. Pulling `open-day` is **risk-free even if you never use the new field**: your existing goals behave identically until you choose to add a `weekly_schedule` map. So the decision is just "pull `open-day` or don't."

## Manual Steps

**None required.** Optional — to actually use day-specific cues, add to any goal file's frontmatter in `10-strategy/goals/`:

```yaml
weekly_schedule:
  mon: "Easy — 30-40 min Z2."
  tue: "Rest."
  wed: "HARD — intervals."
  thu: "Easy — 30-45 min Z2."
  fri: "Moderate — steady effort."
  sat: "Optional — long easy."
  sun: "Rest."
weekly_schedule_effective: 2026-06-08   # optional — omit to activate immediately
```

## Commits Included
- `eb21cfe` — open-day: day-specific goal cues via weekly_schedule + effective-date guard
