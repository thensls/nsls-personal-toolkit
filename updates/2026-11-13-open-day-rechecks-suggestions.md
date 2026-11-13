---
date: 2026-11-13
slug: open-day-rechecks-suggestions
skills_changed: [open-day]
files_changed: 3
cost_to_adopt: "0 min"
breaking: false
---

# Open-day checks its suggestions before it shows them

## Why

Open-day was copying yesterday's suggestions forward without checking them. A builder would
see "send the comments to Trina" the morning after sending them, or a follow-up a meeting had
already made unnecessary. One stale line like that makes every other suggestion harder to
trust.

## What Changed

- **Every suggestion is re-checked each morning** against what actually happened since the
  last open-day or close-day: your Slack messages, meeting notes, email, calendar and recent
  Claude sessions. Anything you already did comes up pre-ticked as done, with the evidence
  beside it.
- **Things a decision made unnecessary are marked "possibly moot"** instead of being repeated
  or recorded as achievements. One click removes them.
- **New asks are added**, each with where it came from, such as a message from your manager
  or an action item from a meeting.
- **Your task board tops up a short list.** If fewer than 10 suggestions are left, up to 5
  come from your board (Asana by default). Anything someone asked about recently comes in
  regardless.
- **Sources it couldn't read are named** in the morning summary, so a list that couldn't be
  checked never looks checked.

## Cost to Adopt

**0 min.** Arrives on its own. Optional: to use a GitHub project as your board instead of
Asana, add `task_board: github` and `task_board_github: <owner>/<project-number>` to your
builder profile.

## Safe Merge

Only `skills/open-day/SKILL.md` changes. If you've customized open-day, the new text is all in
Step 2n and one line of the companion seeding list.
