---
date: 2026-11-20
slug: open-day-jira
skills_changed: [open-day, midnight-sweep, personal-setup]
files_changed: 6
cost_to_adopt: "2 min"
breaking: false
---

# Open-day can read your Jira

## Why

Builders whose work lives in Jira saw none of it in their morning plan; open-day
only read Asana or a GitHub board.

## What Changed

- **Your Jira issues become suggestions**: overdue first, then due today, then in
  progress, each with its key so you can find it.
- **Read-only.** Open-day never moves, comments on or creates a Jira issue.
- **Support tickets stay out** by default (the HELP project), because their
  titles can carry member details.
- **The midnight sweep counts an issue you resolved as done**, so it drops off
  tomorrow's list.

## Cost to Adopt

**2 min.** Connect **Atlassian** in claude.ai Settings › Connectors, then tell
Claude "my tasks are in Jira" (or rerun personal setup), which adds
`task_board: jira` to your profile.

## Safe Merge

`skills/open-day/SKILL.md` (Step 2b's new Jira section, one line in 2n),
`skills/midnight-sweep/SKILL.md` (source 9), `skills/personal-setup/SKILL.md`
(where your tasks live), and the test vault's fake issues in `companion/testmode.py`.
