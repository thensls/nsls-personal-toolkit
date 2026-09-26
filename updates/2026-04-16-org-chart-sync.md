---
date: 2026-04-16
slug: org-chart-sync
last_commit: 7985340
commit_range: 3f5c9b0..7985340
skills_changed: [personal-setup, person-intelligence]
files_changed: 2
cost_to_adopt: "15 min"
breaking: false
backfilled: true
---

# Org chart vault sync

## Why

Before this release, `person-intelligence` knew about people you'd met with (via Fathom) but didn't have a structural view of your org — who reports to whom, who's in what department. That meant weekly relationship health checks and coaching portfolio views were flat lists, not organized by team structure.

After this release, the toolkit syncs your company's org chart into your Obsidian vault and refreshes it at the start of each biweekly health check. Person profiles now reference their place in the org. Weekly views can group relationships by team.

## What Changed

### `personal-setup` — org chart vault sync step
Added a setup step that downloads your org's chart (currently from the NSLS automation tracker, adaptable to other sources) and writes it to `$OBSIDIAN_VAULT_PATH/30-people/org-chart.md`.

### `person-intelligence` — refresh org chart at start of biweekly health check
Before running a health check, re-pulls the org chart so the structure is current. Detects new hires, org changes, and departures.

## Cost to Adopt

**15 min** — skill updates pull fast, but org chart sync requires a source (Airtable base with people data, or a JSON endpoint). If you have NSLS Airtable access, it works out of the box. If not, you'll need to point the skill at your own data source or skip this release.

## Safe Merge

Nothing to do by hand. Say **"update personal productivity"** and it applies this release for
you, one skill at a time, and keeps any changes you have made to those skills.

## Opt-Out Guide

- **No org chart data source?** Skip this release. The rest of `person-intelligence` still works without an org chart.
- **Want only the health-check refresh but not the initial sync?** Pull `person-intelligence` only, skip the `personal-setup` update.

## Manual Steps

- [ ] Identify your org chart source (NSLS Airtable, or your own) and add its credentials to `.env`
- [ ] Run `/personal-setup` and complete the new org chart sync step
- [ ] Verify `$OBSIDIAN_VAULT_PATH/30-people/org-chart.md` exists after sync

## Commits Included

- `58815c3` — feat: add org chart vault sync to /personal-setup
- `7985340` — feat: refresh org chart at start of biweekly health check
