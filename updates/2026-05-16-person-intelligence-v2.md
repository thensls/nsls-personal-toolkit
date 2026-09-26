---
date: 2026-05-16
slug: person-intelligence-v2
last_commit: 01881787d490602fceb67a6fb8950cc99d138e78
title: Person Intelligence v2 — manager coaching, biweekly automation, two-way coaching
skills_changed: [person-intelligence]
cost_to_adopt: "2 min"
breaking: false
---

# Person Intelligence v2

## Why

The `/person-intelligence` skill grew from a single-person synthesis tool into a manager-coaching system that runs biweekly across your direct reports, ingests Fathom + Slack + Gmail, and surfaces actionable coaching moves in your daily and weekly routines.

## What's new

### Three coaching artifacts per relationship

For each **direct report**, the synthesizer now produces:
- `## What [Name] Needs to Thrive` — private to you. Strengths to invest in, friction to address, growth edges, conditions for peak performance. Grounded in research-validated frameworks (Paloma Medina's BICEPS, Gallup Q12, SDT, Julie Zhuo's strengths/growth/working-style lens).
- `## How I Work with [Name]` — your own working-style disclosure, personalized for this report. Optionally shareable. Modeled on Lara Hogan's "How to Work with Me" pattern.

For your **own manager**:
- `## My Stance: [emotions]` — name 2-4 emotions that capture the relationship. Reference example: the "Respect, Protect, Resent" pattern.
- `## How I Can Work More Effectively with [Name]` — your own coaching of yourself in this relationship. The managing-up surface.

**Peers** keep a lighter `## Working Pattern` section — no coaching arrows.

### Biweekly automation

A new orchestrator (`biweekly_sweep.py`) composes the tracked relationship set from `org-chart.json` (no Airtable key needed) and identifies what's pending per person. A cross-relational digest generator (`generate_team_pulse.py`) produces one `30-people/_pulse/YYYY-MM-DD-team-pulse.md` per cycle with cadence integrity, drift/thrive/attention patterns, manager-mode review, and proposed coaching updates.

Register the schedule once:

```
/schedule create "Person-intelligence biweekly sweep" \
  --cron "0 7 * * 0/2" \
  --command "/person-intelligence biweekly sweep"
```

### Coaching actions surface in /open-day and /open-week

`extract_coaching_actions.py` parses unchecked actions from each profile's Coaching Goals + Thrive section into `~/.cache/person-intelligence/coaching_actions.json`. `surface_actions_for_day.py` picks up to 3 (daily) or 5 (weekly) actions for today's scheduled people, round-robin across people, with auto-stale decay after 3 surfaces without status change.

Your `/open-day` and `/open-week` skills now call these automatically when you have people on your calendar.

### Frontmatter sync from the org chart

`sync_obsidian_frontmatter.py` flows the hourly-refreshed org-chart fields (email, slack, department, title, manager) into your `30-people/[Name].md` files **without touching body content or curated fields** (tags, role, health\*, last-synthesized).

### Honest backfill of the emoji chart

`backfill_emoji_chart.py` fills cadence gaps with **visibly distinct** rows: backfilled cells use `⚪` in place of `💚/🟢/🟡/🔴` (round, matches the rest of the chart's style) and the Note column reads `Backfilled`. Frontmatter `last-synthesized` does NOT advance — backfill is cadence integrity, not fabricated assessment.

## What's preserved

- Existing single-person synthesis still works: `Synthesize [name]` runs the same pipeline.
- All curated profile sections survive re-synthesis (the synthesizer extracts non-template sections via Python and re-injects them verbatim — no LLM-level instruction relied on for safety).
- The 1-4 emoji health scale + biweekly journal entries are unchanged.

## New env vars

Added to `.env.example`:

```
OPERATING_USER_EMAIL=       # who "you" are in the org chart (defaults to BUILDER_EMAIL)
KEY_RELATIONSHIPS=          # comma-/newline-separated names to track outside the org chart
INCLUDE_MANAGEMENT_PEERS=   # set to 1 to include people who share your manager
SKIP_SLACK_INGEST=          # set to 1 to disable Slack ingest
SKIP_GMAIL_INGEST=          # set to 1 to disable Gmail ingest
INGEST_EXCLUDE_THREADS=     # subject/channel patterns to skip (defaults cover legal/HR/payroll)
```

## Honest call-outs

- The 2025-2026 manager-coaching research grounding was sketched from training-data knowledge of canonical sources (Gallup Q12, SDT, BICEPS, Project Oxygen). If you want to deepen this, run a fresh web-research pass and update `references/manager-coaching-frame.md`.
- Slack/Gmail ingest is scoped to 14-day window + participant-only + low-signal filter + opt-out switches. See `references/ingest-scoping.md` for the full posture. Reads from your own messages only — this is self-applied surveillance, not anything else.
- Backfilled rows look distinct from assessed rows but are not silent fabrications. The "Cadence resumption" journal entry per profile documents the convention.

## For forks

Nothing to do by hand. Say **"update personal productivity"** and it applies this release for you,
one skill at a time, and keeps any changes you have made.

- Your existing single-person `Synthesize [name]` commands keep working. The new modes are additive.
- If you have a profile of your own manager, the next synthesis adds the two new sections without
  overwriting anything you have written.
- The new settings in `.env.example` all have sensible defaults.

The new modes are opt-in by behaviour: nothing runs on a schedule until you set one up.
