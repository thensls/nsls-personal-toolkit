---
date: 2026-06-03
slug: kb-harvest-pipeline
last_commit: 095de7b8930e6b2848842f6b8a33e2d12e6187b9
commit_range: 9c8daf7..095de7b
skills_changed: [harvest-meeting, close-day, close-week, personal-setup]
files_changed: 4
cost_to_adopt: "15 min"
breaking: false
---

# Harvest meetings into the NSLS Knowledge Base

## Why

After a strategic meeting, the decisions, project definitions, and state-changes that used
to evaporate now flow from Fathom into the shared NSLS Knowledge Base — gated so nothing
sensitive (comp, profit, personnel) ever leaks. SLT members get a durable, searchable record
of how NSLS works and where it's going, without anyone hand-transcribing a single thing. Run
it after a meeting, or let it ride along on your `/close-day` and `/close-week`.

## What Changed

### `harvest-meeting` — new skill: meeting → Knowledge Base pipeline
- Three modes: `--date YYYY-MM-DD`, `--fathom-url <url>`, and `--week-audit --week YYYY-Www`.
- Pulls Fathom meetings → extracts candidate KB entries → maps them to topic files → dedups
  against what's already there → runs the **sensitive-content rubric** → shows you a numbered
  approval list → commits approved edits to `thensls/nsls-knowledge` and pushes.
- **SLT-gated**: writes require your `@nsls.org` email in `kb_authors.txt`. Non-SLT users get
  a read-only audit, never a silent failure.
- Includes a **First-Time Setup** section up front so nobody clones the wrong repo (the repo
  is `nsls-knowledge`; `60-nsls-knowledge` is just the local vault folder name).

### `close-day` — Step 4c: end-of-day KB harvest
- Your evening close now offers to harvest that day's strategic meetings into the KB.
- Silently skips if you're not an SLT writer — no noise, no action needed.

### `close-week` — Step 2b: weekly KB audit
- Friday roll-up now flags unharvested meetings, stale topics (untouched 60+ days), and open
  questions older than 30 days — and offers to promote questions that got answered this week.

### `personal-setup` — auto-configures KB writer setup for SLT builders
- `/personal-setup` now handles the one-time KB clone + git-identity step for you if you're on
  SLT, so you don't have to run the clone commands by hand.

## Cost to Adopt

**15 min** — a one-time setup: get added to the KB allowlist + repo (ask Kevin), then clone the
KB repo into your vault and set your git identity. After that it runs from `/close-day`,
`/close-week`, or `/harvest-meeting` with zero extra steps. (Or just run `/personal-setup`,
which now does the clone + identity for you.)

## Safe Merge

**If you haven't customized these skills:**
```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/harvest-meeting skills/close-day/SKILL.md skills/close-week/SKILL.md skills/personal-setup/SKILL.md
git commit -m "pull upstream: kb-harvest-pipeline"
```
(`harvest-meeting` is a new directory, so the whole folder comes over — SKILL.md, `kb_authors.txt`, and `references/`.)

**If you have customized one or more of these skills:**

For each skill, see what changed upstream vs. what you changed locally:
```bash
git diff HEAD upstream/main -- skills/<skill>/SKILL.md
git log --oneline 9c8daf7..upstream/main -- skills/<skill>/SKILL.md
```

Three options per skill:
1. **Accept upstream, lose your changes** — `git checkout upstream/main -- skills/<skill>/SKILL.md`
2. **Merge manually** — edit by hand, keeping your customizations
3. **Skip this skill entirely** — stay on your version and miss this change

## Opt-Out Guide

Everything here is independently adoptable:
- **Want manual harvesting only?** Pull `harvest-meeting`, skip the `close-day`/`close-week`
  changes. Run `/harvest-meeting` yourself after meetings.
- **Don't want it in your evening routine?** Pull `harvest-meeting` + `close-week` audit, skip
  `close-day` Step 4c.
- **Not on SLT?** Nothing to adopt — the close-day/close-week additions no-op for non-writers,
  and `/harvest-meeting` gives you a read-only audit.

## Manual Steps

- [ ] Ask Kevin to (a) add your `@nsls.org` email to `kb_authors.txt` and (b) add your GitHub
      account as a collaborator on `thensls/nsls-knowledge`. Both are quick.
- [ ] Clone the KB into your vault (note: repo is `nsls-knowledge`, folder is `60-nsls-knowledge`):
      ```bash
      git clone https://github.com/thensls/nsls-knowledge.git "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge"
      git -C "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge" config user.email <you>@nsls.org
      ```
- [ ] **Or skip the two steps above** and just run `/personal-setup` — it now automates the clone
      and git identity for SLT builders.

Not breaking — but the harvest **won't write** until the setup above is done. Until then,
`/harvest-meeting` will stop with a clear "clone the repo / ask for access" message rather than
failing silently.

## Commits Included
- `095de7b` — harvest-meeting: add First-Time Setup to prevent wrong-repo clone
- `8302ff9` — feat(personal-setup): auto-config KB writer setup for SLT builders
- `3c72b61` — fix(harvest-meeting): louder Step 0 + .env BUILDER_EMAIL as 5th scope
- `979e4fc` — fix(harvest-meeting): accumulate multiple decisions into one new topic
- `247b6da` — fix(harvest-meeting): merge current_state instead of clobbering it
- `eaa8bfa` — test(harvest-meeting): record Task 11 end-to-end verification results
- `0e92274` — fix(harvest-meeting): cwd-independent SLT gate + meeting-date stamping
- `8d0c3ad` — feat(close-week): add Step 2b KB week audit
- `4ec0806` — feat(close-day): add Step 4c KB harvest (SLT-gated)
- `5925129` — feat(harvest-meeting): week-audit mode (Step 9)
- `739e807` — feat(harvest-meeting): apply+commit+push with rebase-retry (Step 8)
- `3f91a58` — feat(harvest-meeting): approval list UX and parser (Step 7)
- `6abf27f` — feat(harvest-meeting): wire mapping, dedup, and rubric (Steps 4-6)
- `b247253` — feat(harvest-meeting): wire candidate extraction (Step 3)
- `37add8e` — feat(harvest-meeting): load Fathom meetings by date or URL (Step 2)
- `4f7a7a9` — feat(harvest-meeting): load KB topic index and rubric (Step 1)
- `50e6969` — feat(harvest-meeting): add SLT allowlist gate (Step 0)
- `96a50d4` — feat(harvest-meeting): scaffold skill directory and SLT allowlist
