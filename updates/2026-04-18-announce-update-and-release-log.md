---
date: 2026-04-18
slug: announce-update-and-release-log
last_commit: 2f5dcf9
commit_range: 1f8cf9d..2f5dcf9
skills_changed: [announce-update, update-personal-productivity]
files_changed: 14
cost_to_adopt: "15 min"
breaking: false
---

# Release log + guided update flow

## Why

Before this release, toolkit updates were announced as one-sentence blurbs in Railway. You got told "skills changed, run /update-personal-productivity" but no explanation of **why**, no guidance on how to merge safely with your customizations, and no record of what had shipped over time. Forks either pulled blindly (and sometimes overwrote their work), or skipped updates entirely because the cost-vs-value was unclear.

After this release, the toolkit treats itself like a real product:
- **Every release has a per-file doc** explaining the value, the cost to adopt, safe-merge paths, opt-out boundaries, and manual steps.
- **A running release log** (`updates/README.md`) gives everyone a changelog.
- **`/update-personal-productivity` walks you through unadopted releases interactively** — shows the Why, detects your customizations, offers three safe-merge options per skill (accept / merge / skip), and tracks manual steps as a pending checklist.

You decide what's worth pulling with enough information to make the call, and your customizations survive.

## What Changed

### New: `/announce-update` skill (authoring side)
For toolkit maintainers. Analyzes your recent commits, asks you for the Why / cost / manual steps / opt-out boundaries, writes a versioned release doc to `updates/YYYY-MM-DD-<slug>.md`, prepends to `updates/README.md`, commits + pushes, and posts a Railway announcement pointing at the doc.

Forks don't run this — only maintainers with push access to the toolkit repo. But the skill is in the repo so forks can see how the release docs they consume get made.

### Rewritten: `/update-personal-productivity` (fork side)
Now release-aware. On each run:
1. Fetches upstream
2. Lists unadopted releases from `updates/` (tracks state in gitignored `.toolkit-state.json`)
3. For each: shows Why, cost, asks adopt/skip/defer/read-more
4. For adopt: walks each affected skill, detects your local customizations, offers accept/merge/skip per skill
5. Queues manual steps as a pending checklist
6. Commits per-release with meaningful message

Your existing customizations are detected via `git diff HEAD upstream/main -- <file>`. If the diff is empty, you get the fast path (`git checkout upstream/main -- <file>`). If you've customized, you see both diffs and choose.

### New: `updates/` directory with backfilled history
Every meaningful release since the toolkit's March 31 starter kit now has a release doc. You can walk the full history — stabilization fixes, strategy layer, open/close pairing, person intelligence v3, insight reflection, org chart sync, knowledge graph, stack rank flow — and choose what to adopt.

### New: `updates/README.md` release log
Running history, newest first. GitHub renders this as the default view at `github.com/thensls/nsls-personal-toolkit/tree/main/updates`.

## Cost to Adopt

**15 min** — pull the command changes (2 min), then run `/update-personal-productivity` to walk through the backfilled releases (variable — could be fast if most apply to you, longer if you want to carefully review each one). You can spread the backfill walk across multiple sessions via the `defer` option.

## Safe Merge

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/update-personal-productivity/ skills/announce-update/ updates/ .gitignore
git commit -m "pull upstream: announce-update-and-release-log"
```

After pulling, run `/update-personal-productivity`. It will find all the backfilled release docs and walk you through them one at a time. You can skip any that don't apply (e.g., if you never adopted the strategy layer, skip the 2026-04-08 release).

## Opt-Out Guide

- **Don't want to walk the backfill?** After pulling, manually mark all backfilled releases as skipped by editing `.toolkit-state.json`:
  ```json
  {
    "adopted_releases": [],
    "skipped_releases": ["stabilization", "strategy-layer", "open-close-learn-announcements", "person-intelligence-v3-setup-redesign", "insight-reflection-brain-dump", "org-chart-sync", "knowledge-graph", "stack-rank-flow"],
    "pending_manual_steps": []
  }
  ```
  Future releases will still get prompted.
- **Don't want release tracking at all?** Don't pull `commands/update-personal-productivity.md`. The old simple-pull version keeps working — you just lose the guided walk.

## Manual Steps

- [ ] After pulling, run `/update-personal-productivity` to initialize `.toolkit-state.json` and walk backfilled releases
- [ ] (Optional) Bookmark `github.com/thensls/nsls-personal-toolkit/tree/main/updates` for future reference

## Commits Included

- `2f5dcf9` — feat: release-aware /update-personal-productivity + backfilled log
- `fea5ed2` — feat: /announce-update skill + updates/ release log
