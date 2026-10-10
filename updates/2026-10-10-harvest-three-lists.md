---
date: 2026-10-10
slug: harvest-three-lists
skills_changed: [harvest-meeting, close-day, close-week]
files_changed: 6
cost_to_adopt: "2 min"
breaking: false
---

# Harvest asks you less: one short list, at most four questions

## Why

Harvest used to hand you every candidate and ask you to approve them one by one, so private
material slipped through on a tired "sure". Now it sorts first and asks you to decide only the
few things it genuinely can't call.

## What Changed

- **Three lists instead of one long one.** ✅ what it's adding, approved with one `yes`.
  ❓ at most four items it's unsure about, which stay out unless you name them. 🚫 a count of
  what it held back, by category, never the content itself.
- **Stricter sorting rules** (`references/sorting-guidelines.md`): pay, people decisions,
  private life, profit, deal and vendor terms, security, unresolved legal and anything not yet
  announced never reach the list. Good decisions carrying one risky detail get the detail cut
  (marked ✂) instead of being dropped.
- **1:1s are treated strictly**: expect most to add nothing, which is the intent.
- **Standing practices are captured** ("partner onboarding takes about six weeks"), not only
  decisions.
- **A counts-only log** (`.harvest-log.jsonl` in your vault) records list sizes per run, never
  content, so we can tell whether the list got shorter.

## Cost to Adopt

**2 min** — pull the three skills. Nothing to set up.

## Safe Merge

Say **"update personal productivity"**; it applies this release and keeps your own changes to
those skills.

## Opt-Out Guide

- Say "turn off KB harvest" to stop the daily harvest. `/harvest-meeting` still works on demand.
