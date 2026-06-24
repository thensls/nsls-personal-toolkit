---
date: 2026-06-11
slug: role-coach
last_commit: f5206abf174b78d84bccb117cb58c57448606e5c
commit_range: eb21cfe..f5206ab
skills_changed: [role-coach, close-day, close-week, open-day, open-week, person-intelligence, personal-setup, harvest-meeting]
files_changed: 22
cost_to_adopt: "15 min"
breaking: false
---

# Coaching from your seat — /role-coach goes org-wide

## Why

You now have a coach that knows your role. `/role-coach` reads the seat you have (your accountabilities, in your own words) and optionally the seat you're working toward, looks at what you actually did this week, and tells you the gap — with evidence, not vibes. Every claim cites a date and a source. And it remembers: a pattern it named three weeks ago doesn't get re-explained, it gets escalated or dropped. The same advice never nags twice.

It works for every seat. An IC gets coaching grounded in their own Quick Notes and goals (and *only* their own — the server enforces that, not the skill). Managers see their team's signal, execs org-wide. No role file? The first run is a 5-minute interview.

## What Changed

### `role-coach` — NEW: role-scoped coaching with a memory
- `/role-coach --week` renders a ≤10-line weekly block: what you said you'd do, what you did, the gap — plus a pattern ledger that tracks whether named patterns actually change
- `/role-coach --deep` is the full quarterly-style review with section-by-section approval; you can contest any claim and it stays silenced until genuinely new evidence appears
- Optional `role-trajectory.md`: name the role you want and the milestones to it — coaching becomes "here's the next gate," never "grow more"
- Privacy by construction: every claim must cite a source; a redaction rubric gates everything rendered; aspirations and any named-person content never leave your vault

### `close-day` / `close-week` — coaching wired into your cadence
- close-week Step 2c invokes the weekly block automatically; close-day Step 4d surfaces at most one daily cue (zero cues on a quiet day is correct behavior, not a failure)

### `open-day` / `open-week` — one budget, no double-coaching
- The morning Coaching Actions section now renders a `🪑 Role:` cue alongside the `🎯` people actions — hard-capped at 3 total daily / 5 weekly, arbitrated in code
- open-week Step 2.6 reads your pattern ledger into weekly planning (trap-check collisions, Top-3 candidates)

### `person-intelligence` — cue arbiter (script change)
- `surface_actions_for_day.py` gains a second input pool for role-coach cues (≤1, same decay model). If you don't use role-coach, output is unchanged.

### `personal-setup` — Role Coach opt-in
- Setup now offers role-coach with an honest scope explanation; nothing written to .env — it activates when your role file exists

### Smaller items in this range
- `harvest-meeting` dual-target: SLT writes to the company KB, everyone else gets a local private KB (#25, #26)
- `close-day` goal/health frontmatter reliability fixes (#24, #27)
- `open-day`/`open-week`: GAIN feedback framework in the manager Develop bucket

## Cost to Adopt

**15 min** — git pull + a 5-minute first-run interview. Optional Signal connection adds ~5 minutes.

## Safe Merge

**If you haven't customized these skills:**
```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/role-coach skills/close-day/SKILL.md skills/close-week/SKILL.md skills/open-day/SKILL.md skills/open-week/SKILL.md skills/person-intelligence/scripts/surface_actions_for_day.py skills/person-intelligence/tests/test_surface_actions_role_cues.py skills/personal-setup/SKILL.md CLAUDE.md
git commit -m "pull upstream: role-coach"
```

**If you have customized one or more skills:**

For each skill, see what changed upstream vs. your local changes:
```bash
git diff HEAD upstream/main -- skills/<skill>/SKILL.md
git log --oneline eb21cfe..HEAD -- skills/<skill>/SKILL.md
```

Three options per skill: accept upstream (`git checkout upstream/main -- skills/<skill>/SKILL.md`), merge manually, or skip it entirely.

## Opt-Out Guide

Everything is independently adoptable:
- **Just the skill, no automation**: pull `skills/role-coach/` only and run `/role-coach --week` manually on Fridays. Skip all caller edits.
- **Weekly only, no daily cues**: pull role-coach + close-week + open-week; skip close-day/open-day. (This is the recommended starting point — daily cues are the most nag-prone surface.)
- **No Signal**: skip `/signal-setup` entirely — coaching runs from your role docs and notes with an explicit "no Signal evidence" banner.
- **Skip the surfacer script change**: everything works except the `🪑` cue line in open-day/open-week.
- **None of it**: skip this release; every caller step heartbeat-skips when no role file exists, so pulling the cadence skills for other reasons costs you nothing.

## Manual Steps

- [ ] Run `/role-coach --week` once — the first-run interview builds `10-strategy/role-coaching/role-profile.md` (and optionally `role-trajectory.md`)
- [ ] (Optional, for Signal evidence) Run `/signal-setup` — anyone can now mint a token at `https://employee-profiles-production.up.railway.app/me/mcp-token`. ICs get **self scope**: your own Quick Notes history and goals, nobody else's, sentiment excluded server-side.

Not breaking: if you skip everything, all updated skills detect the missing role file and skip with a one-line heartbeat.

## Commits Included
- `f5206ab` — role-coach Phase 3: org-wide — daily mode, tier rules, setup wiring
- `be46052` — role-coach Phase 2: cadence wiring + cue arbiter (TDD)
- `82a8fb6` — role-coach: Phase 1 — role-scoped coaching skill (--week/--deep) + plan
- `d922100` — open-week: mirror GAIN feedback framework into Develop intention
- `2fb4758` — open-day: add GAIN feedback framework to manager Develop bucket
- `9422fdd` — fix(harvest): stamp scaffold date into local-KB seed stubs (#26)
- `f583841` — fix(close-day): align ⚪/❌ goal classification with Step 5a (#27)
- `9202a8d` — harvest-meeting: dual-target (company KB for SLT, local KB for everyone) (#25)
- `e82c231` — fix(close-day): write health + goal frontmatter reliably (Step 5a) (#24)
