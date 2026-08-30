---
date: 2026-04-07
slug: stabilization
last_commit: 43fed29
commit_range: 8408dd0..43fed29
skills_changed: [setup, log, person-intelligence]
files_changed: 6
cost_to_adopt: "2 min"
breaking: false
backfilled: true
---

# Stabilization: renames, pointer fixes, path portability

## Why

The earliest shared versions of the toolkit had three friction points: `/setup` collided with the builder toolkit's `/setup`, some skill files were broken pointers instead of actual content, and Obsidian paths were hardcoded to Marcus's vault. This release cleans all three — you can safely install alongside the builder toolkit and the skills work with your own vault path.

## What Changed

### `setup` renamed to `personal-setup`
Trigger is now `/personal-setup` so it doesn't fight with the builder toolkit's `/setup`. No functional change — same onboarding flow.

### `log` skill — restored actual content
The `log/SKILL.md` file was a broken pointer in the initial release. Now contains the real skill.

### `person-intelligence` skill — restored actual content
Same issue — the file was a pointer. Now has the full skill body.

### Obsidian paths now use `$OBSIDIAN_VAULT_PATH`
Skills that previously referenced `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP` now read `$OBSIDIAN_VAULT_PATH` from your `.env`. Set this during `/personal-setup`.

## Cost to Adopt

**2 min** — pull the skill files, rerun `/personal-setup` to set `$OBSIDIAN_VAULT_PATH` if you haven't already.

## Safe Merge

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/personal-setup/ skills/log/ skills/person-intelligence/
git commit -m "pull upstream: stabilization"
```

If you customized any of these three skills already, view the upstream diffs first:

```bash
git diff HEAD upstream/main -- skills/<name>/SKILL.md
```

## Opt-Out Guide

- Not using Obsidian? Skip the `$OBSIDIAN_VAULT_PATH` step; point it at whatever directory you use instead.
- Already renamed `setup` → `personal-setup` locally? Just pull the file content updates.

## Manual Steps

- [ ] Run `/personal-setup` to confirm `$OBSIDIAN_VAULT_PATH` is set in your `.env`

## Commits Included

- `fb0c281` — fix: rename /setup to /personal-setup to avoid collision with builder toolkit
- `2579c6e` — fix: replace hardcoded Obsidian paths with $OBSIDIAN_VAULT_PATH from .env
- `a7a1350` — fix: restore actual log skill content (was broken pointer)
- `bd66767` — fix: restore person-intelligence skill (was broken pointer)
