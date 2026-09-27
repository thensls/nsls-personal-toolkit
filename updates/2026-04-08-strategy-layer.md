---
date: 2026-04-08
slug: strategy-layer
last_commit: b431dd1
commit_range: 43fed29..b431dd1
skills_changed: [plan-day, plan-week, self-insight, close-week, personal-setup, person-intelligence]
files_changed: 8
cost_to_adopt: "30+ min"
breaking: false
backfilled: true
---

# Strategy layer: daily/weekly planning connected to company goals

## Why

Before this release, the personal toolkit gave you skills that ran independently — `/plan-day` pulled your calendar, `/close-day` summarized it, but nothing tied them to your role, your company goals, or the behavioral patterns that reveal how you actually spend your time. Good planning skills, zero memory of who you are.

After this release, you have an opt-in **strategy layer** — an operating memo ("I Do / I Don't / My Traps"), a personal profile (strengths, energy, working genius), and weekly project stack-ranking connected to Large Outcome Priorities (LOPs). Daily and weekly planning reads from the strategy layer to offer coaching, not just scheduling.

This is the foundation the rest of the personal toolkit is built on. Skip it if you want lightweight planning; adopt it if you want planning that gets smarter about you over time.

## What Changed

### New: `self-insight` skill
Analyzes your calendar, Fathom meeting transcripts, and screen-capture history to generate two artifacts:
- **Operating memo** — what you do well, what you should avoid, patterns that trap you
- **Personal profile** — energy patterns, strengths, values, working genius

Both live at `$OBSIDIAN_VAULT_PATH/10-strategy/`.

### `plan-day` and `plan-week` — strategy-aware
Both skills now read the operating memo and personal profile (if they exist) and surface coaching notes alongside calendar/task data. Plan-week adds project stack ranking and push/protect mode detection.

### New: `close-week`
Friday roll-up covering Sat–Fri. Aggregates daily notes into achievements, stack-rank-vs-reality comparison, push/protect mode assessment, and priorities-vs-alignment scoring.

### `personal-setup` — adds Fathom API key
Fathom meeting recordings power a lot of the strategy layer (self-insight, person-intelligence). Setup now prompts for your Fathom API key.

### `person-intelligence` — Airtable warning softened
Previously hard-failed without Airtable. Now works with a gentle warning if Airtable isn't configured.

## Cost to Adopt

**30+ min** — the strategy layer is opt-in but requires meaningful setup: Fathom API key, vault folder `10-strategy/` created, and your first `/self-insight` run (which takes 10–20 min to process your recent calendar and meetings). You can adopt the skill updates in 2 min, but the **value** only shows up after the strategy artifacts exist.

## Safe Merge

Nothing to do by hand. Say **"update personal productivity"** and it applies this release for
you, one skill at a time, and keeps any changes you have made to those skills.

## Opt-Out Guide

- **Don't want the strategy layer at all?** Pull the skill updates but skip `/self-insight`. The skills degrade gracefully — they just offer less coaching.
- **Want strategy layer but not Fathom?** Skip the Fathom API key. `/self-insight` will work with calendar + Familiar data alone, less rich but functional.
- **Want `/close-week` only?** Pull just that skill; leave the others.

## Manual Steps

- [ ] Get a Fathom API key (Settings → API keys in Fathom) — optional but recommended
- [ ] Run `/personal-setup` to add `FATHOM_API_KEY` to your `.env`
- [ ] Run `/self-insight` to generate your first operating memo + personal profile
- [ ] Create `$OBSIDIAN_VAULT_PATH/10-strategy/` directory if it doesn't exist (`/self-insight` will write here)

## Commits Included

- `5a9d06f` — feat: add strategy layer — plan-day, plan-week, self-insight, close-week updates
- `9bfdedb` — feat: add Fathom API key to personal-setup and .env
- `b431dd1` — fix: soften Airtable warning — person-intelligence works without it
