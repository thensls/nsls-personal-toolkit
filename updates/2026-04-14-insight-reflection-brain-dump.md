---
date: 2026-04-14
slug: insight-reflection-brain-dump
last_commit: 3f5c9b0
commit_range: 04d4e1c..3f5c9b0
skills_changed: [close-day, close-week, open-week]
files_changed: 3
cost_to_adopt: "15 min"
breaking: false
backfilled: true
---

# Insight Reflection, Brain Dump, and cross-week signal tracking

## Why

Before this release, `/close-day` produced a good structural summary (calendar, projects, time tracking) but nothing that captured the **meta** of your day — the pattern you'd only see by standing a step back. And day-to-day thinking that wasn't a task, a decision, or a calendar item had nowhere to go.

After this release:
- **`/close-day` leads with an Insight Reflection** — a full-shape synthesis at the top of the daily note that captures what the data reveals you might not have noticed.
- **Brain Dump** becomes a first-class section in your daily note — a place to capture half-formed thoughts throughout the day, which `/close-day` then routes into projects, tasks, or parking lots.
- **`/close-week` and `/open-week` track cross-week signals** — insights that appear in the reflection of 2+ consecutive weeks become structural patterns to act on, not one-off noise.

## What Changed

### `close-day` — Insight Reflection at top of daily note
The daily note template now starts with `## Insight Reflection` — a 1-2 paragraph synthesis of the day's pattern, anchored in specific data points. Moved from the bottom (where it lived briefly) to the top, so it's visible when you open past notes.

### `close-day` — Brain Dump section
New `## Brain Dump` section in the daily note, seeded each morning by `/open-day`. You capture thoughts into it throughout the day, and `/close-day` Step 7d routes each entry into: Project notes, Asana tasks, parking lots, or deletion.

### `close-day` — Step 1h Task Evidence Detection
Detects completed task evidence in your Claude sessions, Familiar captures, and meeting transcripts. Surfaces "you finished [X] but didn't mark it done in Asana" prompts.

### `close-day` — Fathom API URL warning
Prevents using the wrong Fathom domain (a real issue Marcus hit).

### `close-week` and `open-week` — cross-week signal tracking
Every weekly note gets a `## Insight Reflection` (full-shape synthesis of the week). `/open-week` reads the last N weeks' reflections and flags themes that appear repeatedly: "This is week 3 of '[theme]' in your reflection — that's structural."

## Cost to Adopt

**15 min** — skill pulls are fast, but you need to update your daily note template (add `## Brain Dump` section if yours doesn't have it) and decide whether to adopt the Insight Reflection format (the old format still works).

## Safe Merge

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/close-day/ skills/close-week/ skills/open-week/
git commit -m "pull upstream: insight-reflection-brain-dump"
```

Customized `close-day`? The new sections are additive (Step 1h, Step 7d, daily-note format). Merge by hand.

## Opt-Out Guide

- **Want Brain Dump but not Insight Reflection?** Pull `close-day` updates, manually remove the Insight Reflection section from your daily note template.
- **Want daily changes but not weekly signal tracking?** Pull `close-day` only. Leave `close-week` and `open-week` alone.
- **Fine with old structure?** Skip the whole release — previous close-day behavior still works.

## Manual Steps

- [ ] Update your daily note template at `$OBSIDIAN_VAULT_PATH/_templates/daily-note.md` to add `## Brain Dump` and `## Insight Reflection` sections (or let `/open-day` seed them)
- [ ] If using Fathom, verify API URL is correct in your `.env` (skill warns you now, but check once)

## Commits Included

- `a1c678c` — fix(close-day): add Fathom API URL warning to prevent wrong domain
- `ef63d2c` — close-day: add Step 1h Task Evidence Detection
- `b9495b0` — close-day: add Insight Reflection section (full-shape synthesis)
- `971395d` — close-day: add Brain Dump section and routing step (7d)
- `f1d6af3` — close-day: Brain Dump in seed template; Insight Reflection moved to top
- `3f5c9b0` — close-week + open-week: add full-shape Weekly Insight Reflection and cross-week signal tracking
