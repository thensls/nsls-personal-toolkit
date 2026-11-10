---
date: 2026-11-10
slug: companion-restarts-after-update
skills_changed: []
files_changed: 2
cost_to_adopt: "1 min"
breaking: false
---

# The visual companion restarts itself after an update

## Why

The companion keeps running in the background for days, but the page it shows is read fresh
every time. After a toolkit update, the page asked the old background copy for things only the
new one knows, and buttons such as **Bonus** showed a red "404 Not Found" banner until the
computer restarted.

## What Changed

- **An out-of-date companion is replaced, not reused.** When `/open-day` or `/close-day` checks
  on the companion and finds one started before the latest update, it stops it and starts a
  fresh one. You may see the page reload once.

## Cost to Adopt

**1 min.** Arrives on its own at your next session. The first `/open-day` after it lands
restarts your companion once.

## Safe Merge

It changes the companion's start-up and status check only; no skill files change.

## Opt-Out Guide

Nothing to opt out of: a companion running current code is left exactly as it was.
