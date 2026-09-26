---
date: 2026-04-11
slug: open-close-learn-announcements
last_commit: db779fd
commit_range: b431dd1..db779fd
skills_changed: [plan-day, plan-week, open-day, open-week, learn, close-week, log]
files_changed: 12
cost_to_adopt: "15 min"
breaking: true
backfilled: true
---

# Open/close pairing, learning system, and toolkit announcements

## Why

Three related changes shipped together. Before this release: daily/weekly planning skills were called `plan-day` and `plan-week`, leaving the closing side feeling asymmetric. Learning was ad-hoc. And there was no way for the toolkit to tell you new skills had shipped — you had to remember to check.

After this release:
- **Daily and weekly planning skills are paired** as `/open-day`–`/close-day` and `/open-week`–`/close-week`. The language matches the lifecycle and makes the ritual obvious.
- **`/learn` captures learning goals, ingests resources, and builds scaffolded paths** — so your learning isn't just links-you-meant-to-read.
- **The toolkit announces itself.** A SessionStart hook checks Railway for new announcements, `/log --announce` posts them, `/update-personal-productivity` pulls them.

## What Changed

### Breaking: `plan-day` → `open-day`, `plan-week` → `open-week`
The skill files were renamed. If you had scripts or custom commands invoking `/plan-day` or `/plan-week`, they'll fail after update. Update your invocations to `/open-day` and `/open-week`.

### `close-week` covers Sat–Fri
Weekly boundary moved. Friday close now covers the 7 days ending Friday, matching the weekly open on Sunday/Monday.

### New: `/learn` skill
Set a learning goal, drop in links or resources, get a scaffolded learning path. Tracks progress in `$OBSIDIAN_VAULT_PATH/40-learning/`. Integrates with `/open-day` (surfaces today's learning suggestions) and `/open-week` (weekly learning review).

### `open-week` — automation portfolio check (Step 1.55)
Weekly planning now surfaces the state of automations you own — what's running, what's stale, what needs attention.

### New: `/update-personal-productivity` command
Pulls upstream skill updates. (This release created the first version; later releases — including the current one you're reading in — extend it.)

### New: `/log --announce` flag
When running `/log` inside a toolkit repo, `--announce` posts a Railway announcement so forks see the update.

### New: SessionStart hook
Every Claude Code session now checks for pending announcements and credits for recent PRs.

### `.env.example` — adds `BUILDER_EMAIL` and `GITHUB_USERNAME`
Required for session tracking, announcements, and PR credits.

## Cost to Adopt

**15 min** — skill updates pull fast, but you need to: update any scripts that call `/plan-day` or `/plan-week`, add the two new env vars, and confirm the SessionStart hook works (it runs automatically).

## Safe Merge

Nothing to do by hand. Say **"update personal productivity"** and it applies this release for
you, one skill at a time, and keeps any changes you have made to those skills.

## Opt-Out Guide

- **Don't want `/learn`?** Skip pulling `skills/learn/`. The other skills don't depend on it.
- **Don't want announcements / session tracking?** Skip the SessionStart hook and leave `.env` vars unset. Toolkit still works, just without the cross-fork coordination layer.
- **Can't rename now?** Pin yourself to `b431dd1` until you have time — `/plan-day` and `/plan-week` still work there.

## Manual Steps

- [ ] Find any local scripts/aliases calling `/plan-day` or `/plan-week`, update to `/open-day` / `/open-week`
- [ ] Add `BUILDER_EMAIL=you@domain.com` and `GITHUB_USERNAME=yourhandle` to `.env`
- [ ] Verify SessionStart hook is active (`ls .claude/hooks/` in your project dir)
- [ ] Create `$OBSIDIAN_VAULT_PATH/40-learning/` if you plan to use `/learn`

## Commits Included

- `c4e6bfe` — rename plan-day to open-day, close-week covers Sat-Fri
- `b7c80b1` — rename plan-week to open-week — complete open/close pairing
- `925eb49` — spec: personal learning management system
- `e6fde1a` — plan: personal learning system implementation (Phase 1)
- `3700c0a` — feat: add /learn skill + integrate learning into open-day and open-week
- `9615881` — feat: add automation portfolio check to open-week (Step 1.55)
- `eeb3a74` — feat: add --announce flag to /log for toolkit update announcements
- `8aa9622` — feat: add /update-personal-productivity command for pulling skill updates
- `9918253` — feat: add SessionStart hook for session tracking, PR credits, and announcements
- `db779fd` — chore: add BUILDER_EMAIL and GITHUB_USERNAME to .env.example
