---
date: 2026-08-13
slug: visual-companion-auto-update
last_commit: 861f20f9f611e2e141cc3c0c4bdf8f3b11491f1f
commit_range: 7177b93..861f20f
skills_changed: [open-day, close-day, reset-day, open-week, close-week, announce-update, personal-setup, harvest-meeting, person-intelligence, log, learn, obsidian-setup, quarter-set]
files_changed: 61
cost_to_adopt: "15 min"
breaking: false
---

# The visual companion shows up — and updates finally reach you

> **TL;DR:**
> - Your day-planner visuals now work — `/open-day` builds the panel itself, even fetching its own Python when your machine's is too old.
> - Haven't customized your toolkit? Do nothing — it now updates itself.
> - Customized? Run `/update-personal-productivity` once and you're caught up.

## Why

Run `/open-day` and the visual command center just appears. If it was never
built on your machine, it now builds itself on first use — a one-time ~30-second
pause (a few minutes if it also has to fetch its own Python) — instead of
silently dropping you to chat-only forever with nothing saying why. And this
should be the last update you ever fetch by hand: the toolkits now keep
themselves current, and when yours can't update (customized fork, local
edits), it tells you instead of staying quiet.

## What Changed

### The visual companion — appears on first use, or tells you why not
- All six day/week skills now resolve the companion through one script
  (`companion/ensure-companion.sh`). Binary present → instant. Source present
  but never built → builds once (~10–30s) and continues.
- Failures are soft and visible: the reason lands on stderr and in
  `companion/.install.log`, retries back off for 24h, `--force` retries now.
- The root cause is fixed too: both installers used to *ask* before installing
  the companion, and under the documented `curl … | bash` install that prompt
  ate itself — the installer died mid-run after printing "Done!". Installers
  now install by default when no terminal is reachable (`NSLS_SKIP_COMPANION=1`
  opts out).
- `reset-day` aborts clearly when no companion exists instead of proceeding
  against an unverified vault path.
- **No Python? Also not your problem.** If your machine has no Python ≥3.10
  anywhere (stock Macs ship 3.9), the companion downloads its own
  checksum-verified Python into `companion/.python-runtime/` — user-space, no
  admin password, nothing system-wide touched — announces the one-time wait
  up front, and builds. You are never sent to python.org.

### Updates now reach you
- The auto-update hook is now actually registered at install time — it sat in
  the repo unwired, which is why nothing you've ever shipped upstream arrived
  on macOS by itself.
- The builder kit's session hook now pulls the personal toolkit too on
  macOS/Linux (it always did on Windows) — existing standard installs start
  receiving updates automatically, no action needed.
- `/update-personal-productivity` — the guided fork-update flow — was pointing
  at the toolkit's pre-2026 install path, so it failed immediately for
  everyone. It now resolves the real location. This release is the first one
  you can actually adopt through it.
- Pointer sync can no longer overwrite a real cloud-synced skill with a stub
  when the skill text happens to mention the plugin path.

### Also in this range (since July 22)
- **Companion round-2 buffs** — click-only day close with an "I'm done" button,
  durable multi-day close, date discipline (fresh/absolute dates, timezone
  pinning), a warning when the companion runs in the app's embedded panel, and
  a startup grace window so booting servers aren't reaped.
- **harvest-meeting** — no longer reads private recordings; exclusions are
  opt-in; DST-correct day boundaries; dry-run is truly non-mutating.
- **open-day / close-day** — HRV baseline band replaces trust in a single
  morning reading; everything seeds as a priority candidate (Bonus never
  pre-fills).
- **close-week / log** — close-week reads the business numbers before
  synthesizing; `/log` only matches a project on identifying signals.
- **person-intelligence** — misattribution guard, preferred names, sweep
  finalize, and local scheduling for the biweekly sweep.
- **personal-setup** — validates your GitHub username and Asana GID; Windows
  installs are more robust end-to-end.
- **close-week** — writes `work_hours_total` into the weekly note frontmatter
  again, so the "Total weekly work hours" chart keeps getting fed (omits the
  key rather than guessing when a week has no defensible total).
- **close-day** — audits its catch-all time buckets before publishing Time
  Allocation.

## Cost to Adopt

**15 min** — a straight pull if you haven't customized anything (2 min);
budget the rest for merge decisions if you've edited the day/week skills,
which changed in this range.

## Safe Merge

The guided path (recommended — it walks releases one at a time and respects
your customizations):

```
/update-personal-productivity
```

Manual, **if you haven't customized these skills** (from your fork checkout —
usually `~/.claude/local-plugins/nsls-personal-toolkit`):

```bash
cd ~/.claude/local-plugins/nsls-personal-toolkit
git fetch upstream
git merge --ff-only upstream/main   # clean forks fast-forward
```

**If you have customized skills:** for each one, see what upstream changed
(`git diff HEAD upstream/main -- skills/<skill>/SKILL.md`), then per skill:
accept upstream (`git checkout upstream/main -- skills/<skill>/SKILL.md`),
merge by hand, or skip it and keep your version.

## Opt-Out Guide

- **The companion bundle moves together:** `companion/` +
  `companion/ensure-companion.sh` + the six day/week skills. Pulling a day
  skill without the resolver script (or vice versa) breaks the handoff — adopt
  these as a set, or not at all.
- **Independently adoptable:** the `harvest-meeting` fixes, the
  `person-intelligence` update, the `log`/`close-week` gating, and
  `personal-setup` hardening each stand alone.
- **Installers** only matter for fresh installs — existing machines never
  re-run them; nothing to do.

## Manual Steps

None. The companion builds itself on first use; update registration is
installer-side; existing standard installs update automatically via the
builder kit. If your fork is heavily customized, the one thing worth doing is
running `/update-personal-productivity` soon so you're current before the next
release stacks on this one.

## Commits Included

Merged PRs in this range (see `git log 7177b93..861f20f` for the full list):
- `#53` — close-day: audit the catch-all buckets before publishing Time Allocation
- `#45` — companion self-provisions Python — no machine left behind
- `#44` — close-week: write work_hours_total so the weekly hours chart keeps getting fed
- `#43` — visual companion auto-build on first use + make updates reach builders
- `#42` — harvest-meeting: private-recording exclusion + scoping fixes
- `#41` — close-week business-numbers gate + /log project-match gating
- `#40` — round-2 final polish (Asana write gating, connector portability, status grace)
- `#39` — HRV baseline band for open-day/close-day
- `#38` — person-intelligence: misattribution guard, preferred names, local scheduling
- `#36` — Windows first-run fixes (toolkit + companion)
- `#34` — companion embedded-panel guard
