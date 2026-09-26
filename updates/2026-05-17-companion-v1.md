---
date: 2026-05-17
slug: companion-v1
last_commit: 31d4b12a6aa7606585ed04a824e6b4d4d70532aa
skills_changed: [open-day, close-day, open-week, close-week, reset-day]
cost_to_adopt: "15 min"
breaking: false
---

# Companion v1.0

A local web companion for the toolkit. Browser-based UI on localhost:7777.

## Why

The daily ritual lived only in chat. The companion puts today's plan, the week and your streaks
in a browser tab beside it, reading and writing the same Obsidian notes, so nothing moves out of
the vault.

## What's new

- Day / Week / Streaks tabs in a browser tab alongside your CLI
- Habits and Streaks engine with concern-counter rule
- Bonus list and Gratitude line additions to daily notes
- Real-time sync between CLI and browser via filesystem watcher + SSE
- Optional auto-start at login (macOS launchd)

## What's not changed

- All existing skills work exactly as before
- All existing hooks (`skill-event` etc.) continue to fire
- The Obsidian vault remains the single source of truth

## Install or upgrade

Nothing to do by hand. Say **"update personal productivity"** and it applies this release for you.
The companion sets itself up the first time a day skill opens it.
