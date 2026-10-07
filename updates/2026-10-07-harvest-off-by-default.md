---
date: 2026-10-07
slug: harvest-off-by-default
skills_changed: [close-day, close-week, harvest-meeting]
files_changed: 6
cost_to_adopt: "2 min"
breaking: false
---

# Knowledge Base harvest is now off by default

## Why

The end-of-day harvest was surfacing too much from private meetings — compensation, personnel
and 1:1 material — and asking you to catch it item by item. That's too easy to wave through. Until
its filters are rebuilt and tested, `/close-day` and `/close-week` no longer harvest at all: no
step, no question.

## What Changed

- **`close-day` Step 4c and `close-week` Step 2b skip harvest** unless you've turned it on. They
  print one line saying it's off and move on.
- **`harvest-meeting` is unchanged when you call it yourself.** `/harvest-meeting --fathom-url …`
  works exactly as before, approval list and all.
- **One switch to bring it back:** say **"turn on KB harvest"** (or "turn off KB harvest"). It sets
  `kb_harvest: on` in your `50-reference/builder-profile.md`. We'd suggest leaving it off until the
  filter update ships.

## Cost to Adopt

**2 min** — pull the three skills. Nothing to set up. Everyone ends up off, including anyone who
harvested every day before.

## Safe Merge

Say **"update personal productivity"** and it applies this release, keeping any changes you've
made to those skills. If you've customized close-day Step 4c or close-week Step 2b, keep your
version's wording but take the on/off check at the top of each step.

## Opt-Out Guide

- To keep harvesting daily, take the update and say "turn on KB harvest".
- Skipping this release leaves harvest running every day as before.
