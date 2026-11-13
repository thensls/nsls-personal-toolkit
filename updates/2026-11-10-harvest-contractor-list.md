---
date: 2026-11-10
slug: harvest-contractor-list
last_commit: 7b16468fc8785d2abfe6b6f36a8a428121e51306
skills_changed: [harvest-meeting]
files_changed: 4
cost_to_adopt: "1 min"
breaking: false
---

# Harvest knows who the contractors are

## Why

Contractors read the knowledge base too, so harvest keeps their rates, renewals and
negotiations out of it. Until now it had to work out from the meeting whether someone was a
contractor. Signal already keeps that list, up to date from Rippling.

## What Changed

- **Harvest reads the contractor list from Signal** before it sorts. A listed contractor's terms
  are kept out even when the meeting never says "contractor".
- **What a contractor is working on still goes in.** Being on the list isn't sensitive.
- **The list stays private.** It's never shown, saved or written to the knowledge base.
- **Only executives can read the list.** Everyone else's harvest works as before, telling
  contractors apart from the conversation.

## Cost to Adopt

**1 min.** Arrives on its own at your next session. The list is used once the matching Signal and
builder toolkit updates are live; until then harvest works as before.
