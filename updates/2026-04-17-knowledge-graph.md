---
date: 2026-04-17
slug: knowledge-graph
last_commit: 5ee6b94
commit_range: 7985340..5ee6b94
skills_changed: [close-day, close-week, learn]
files_changed: 3
cost_to_adopt: "15 min"
breaking: false
backfilled: true
---

# Knowledge graph integration

## Why

Before this release, valuable insights flowed into your daily notes (via Insight Reflection) and your learning system (via `/learn`) but didn't connect to each other. A debate you had in a Monday meeting, a surprising data point from a Wednesday reading, and a position you changed on Friday all lived in isolation — no way to see the thread.

After this release, `/close-day` surfaces 0–3 **insight candidates** each day — strict filter for debates, surprising data, or changed positions. You approve one-liners that become entries in a knowledge topic file. `/close-week` consolidates the week's entries, merges redundancies, and updates Current State sections. `/learn` resources now write to `50-reference/` as individual files with frontmatter linking to knowledge topics and learning goals.

The result: an Obsidian-native knowledge graph that grows as a byproduct of your normal daily/weekly rituals.

## What Changed

### `close-day` — Step 4c insight candidates
Surfaces 0-3 insight candidates from meetings, readings, and Fathom transcripts. Strict filter: only debates, surprising data, or changed positions — not just "interesting" observations. You approve one-liners that become topic-file entries.

### `close-week` — Step 2b knowledge consolidation
Reads all daily insight-candidate entries from the week, consolidates them by topic, updates Current State sections in topic files, merges entries that say the same thing.

### `learn` — resources go to `50-reference/` with linked frontmatter
Instead of inline links, `/learn` now writes each resource as an individual file in `50-reference/` with YAML frontmatter linking to knowledge topics and learning goals. This turns Obsidian's graph view into a real knowledge map.

## Cost to Adopt

**15 min** — skills pull fast, but you need to decide on your topic-file location (`$OBSIDIAN_VAULT_PATH/50-reference/` by default, adjustable) and commit to the daily discipline of reviewing insight candidates at close-day. The graph is only useful if you feed it.

## Safe Merge

Nothing to do by hand. Say **"update personal productivity"** and it applies this release for
you, one skill at a time, and keeps any changes you have made to those skills.

## Opt-Out Guide

- **Don't want the knowledge graph?** Skip this release. Everything else keeps working.
- **Want insight candidates but not weekly consolidation?** Pull `close-day` only. You'll accumulate entries; you just won't get automated merging.
- **Want `/learn` in `50-reference/` but not the insight system?** Pull `learn` only.

## Manual Steps

- [ ] Create `$OBSIDIAN_VAULT_PATH/50-reference/` if it doesn't exist
- [ ] (Optional) Decide on a topic-file naming convention before running `/close-day` for the first time post-update
- [ ] Run `/close-day` tonight to see the insight candidate flow

## Commits Included

- `5ee6b94` — feat: knowledge graph integration across close-day, close-week, and learn
