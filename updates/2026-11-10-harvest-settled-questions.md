---
date: 2026-11-10
slug: harvest-settled-questions
last_commit: 8d1514b69db7e79a46ff0d94b0ba57e285505046
skills_changed: [harvest-meeting]
files_changed: 1
cost_to_adopt: "1 min"
breaking: false
---

# Harvest stops asking about questions you've already answered

## Why

A harvest asked whether a question from a meeting was still open, while pointing out that it
had already been answered later in Slack. That spends one of your decisions on something
harvest could see for itself.

## What Changed

- **An answered question is never put to you.** If a later meeting, your own notes or Slack, or
  the knowledge base already answers it, harvest adds the answer as a decision (when the
  knowledge base doesn't have it yet) or leaves it out.
- **A question nothing answers is decided by harvest**: kept as an open question when it matters
  to the organisation, left out when it's minor.

## Cost to Adopt

**1 min.** Arrives on its own at your next session.

## Safe Merge

It changes one reference file in one skill; your own edits to it are kept.

## Opt-Out Guide

- Say "turn off KB harvest" to stop the daily harvest.
