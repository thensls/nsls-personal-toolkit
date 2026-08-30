---
date: 2026-04-13
slug: person-intelligence-v3-setup-redesign
last_commit: 04d4e1c
commit_range: db779fd..04d4e1c
skills_changed: [person-intelligence, open-day, open-week, close-day, personal-setup]
files_changed: 10
cost_to_adopt: "30+ min"
breaking: false
backfilled: true
---

# Person Intelligence v3: relationship coaching + setup redesign

## Why

Before this release, `person-intelligence` could build individual relationship profiles, but the data didn't flow into your daily or weekly rhythm. You'd have a great profile of someone and then walk into a meeting with them cold. Separately, `/personal-setup` was a long, unclear onboarding that made it hard to know what was optional vs required.

After this release, the person-intelligence layer is **woven through open-day, open-week, and close-day**. You see coaching context on today's meetings when you open your day. You log coaching evidence when you close your day. Weekly planning surfaces biweekly relationship health checks. And `/personal-setup` is a clearly staged 4-step flow with time estimates at each step.

## What Changed

### `person-intelligence` v3 — coaching layer
- **Meeting summarizer** extracts personal facts (names, dates, preferences mentioned in passing) so profiles compound across meetings
- **Known People Registry** is first-class — family members and close collaborators get richer tracking
- **Biweekly health check** — a scheduled ritual (surfaced by `/open-week`) that asks you about relationships you haven't touched

### `open-day` — relationship context block
For every meeting on today's calendar, surfaces: last time you met, any open coaching goals, relationship health score, last 1–2 fact nuggets from prior meetings. Runs as a distinct Step between calendar pull and priority setting.

### `close-day` — coaching check-in
After the work summary, prompts for coaching evidence: "Did you make progress on your coaching goals with [person]? Any new facts worth capturing?" Writes evidence to person profiles.

### `open-week` — biweekly health check trigger + coaching portfolio
Every other week, `/open-week` nudges you to run a relationship health check. Also shows a coaching portfolio — relationships you're actively investing in and their trajectory.

### `personal-setup` — 4-step flow with time estimates
Onboarding is now explicitly staged:
1. Core config (.env, paths) — 3 min
2. Integrations (Fathom, Airtable, Slack) — 5 min
3. Strategy layer (self-insight) — 10 min
4. Optional extras — 5 min

Each step tells you what you'll do, why it matters, and what's optional.

## Cost to Adopt

**30+ min** — the skill updates pull fast, but seeing the value requires building up person profiles (meeting-by-meeting, across weeks), running a health check, and potentially rerunning `/personal-setup` to confirm the new step structure works for you.

## Safe Merge

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/person-intelligence/ skills/open-day/ skills/open-week/ skills/close-day/ skills/personal-setup/
git commit -m "pull upstream: person-intelligence-v3-setup-redesign"
```

All 5 skills changed — if you've customized `open-day`, `open-week`, or `close-day`, the new relationship blocks are additive (inserted between existing steps). Merge by hand, keeping your custom logic before/after the new blocks.

## Opt-Out Guide

- **Don't want relationship context in daily planning?** Skip `open-day`. The other skills still work.
- **Don't want coaching check-ins at close-day?** Skip `close-day`. Person profiles still get built from meeting summaries alone.
- **Don't want the new `personal-setup` flow?** Don't rerun `/personal-setup` — your existing config keeps working.

## Manual Steps

- [ ] Decide which collaborators belong in your Known People Registry (family, inner circle, close reports) — update via `/person-intelligence`
- [ ] Run a first biweekly health check (`/person-intelligence` → "run health check") to establish baseline scores
- [ ] Optional: rerun `/personal-setup` to see the new 4-step flow

## Commits Included

- `fdcaf12` — feat(person-intel): add Lauren Vance to Known People Registry
- `9af792b` — feat(person-intel): add personal facts extraction to meeting summarizer
- `2e55136` — feat(open-day): add relationship context block with coaching goals for today's meetings
- `f925994` — feat(close-day): add coaching check-in with evidence logging after work summary
- `b218261` — feat(open-week): add biweekly health check trigger and coaching portfolio display
- `01ab360` — feat: person-intelligence v3 — relationship coaching layer
- `04d4e1c` — feat: redesign /personal-setup to 4-step flow with time estimates
