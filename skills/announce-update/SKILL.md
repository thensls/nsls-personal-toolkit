---
name: announce-update
description: >-
  Generate a rich update announcement for the personal toolkit — explains the
  why, walks forks through a safe merge with their customizations (including
  opt-out per change), and surfaces manual steps outside the repo. Writes a
  versioned release doc to updates/YYYY-MM-DD-<slug>.md, appends to the
  updates/README.md release log, commits, pushes, and posts a Railway
  announcement pointing at the file. Use when the user says "announce update",
  "ship toolkit update", "release notes", "/announce-update", or after
  committing skill changes that forks need to know about.
---

# Announce Toolkit Update

Turn a batch of skill changes into a readable, mergeable release. The output is a persistent release doc that forks can read, selectively adopt, and track over time — not a throwaway announcement blurb.

## When to use

Run after you've committed one or more skill changes to `nsls-personal-toolkit` that forks should know about. Common triggers:
- A new skill was added
- An existing skill's behavior or interface changed meaningfully
- A manual setup step is now required (new env var, vault layout change, external dependency)
- A bug fix that forks should adopt

**Don't run for:** internal refactors with no fork-visible change, typo fixes, or changes that forks can't see or use.

## Prerequisites

- `cwd` inside `~/nsls-skills/nsls-personal-toolkit/` (or a symlink to it)
- All changes to announce are already committed and pushed to `origin/main`
- Railway announcement endpoint available: `https://web-production-6281e.up.railway.app/announcement`

---

## Step-by-step execution

### Step 1: Verify location and state

1. Run `pwd` and `git remote -v`. If the remote isn't `thensls/nsls-personal-toolkit`, stop and tell the user: "This skill runs inside the personal toolkit repo. cd to `~/nsls-skills/nsls-personal-toolkit/` first."
2. Run `git status`. If there are uncommitted changes, stop and ask: "There are uncommitted changes. Commit them first, or is there a reason to announce before committing?"
3. Run `git log origin/main..HEAD` to check for unpushed commits. If any exist, ask: "Commit `<hash>` isn't pushed. Push first?" If yes, `git push origin main` before continuing. If no, tell the user announcements without pushed changes mislead forks — confirm they want to proceed anyway.

### Step 2: Determine the commit range

Find the range of commits to cover in this announcement.

1. Check `updates/README.md` for the most recent release entry. Extract the commit hash from its frontmatter (`last_commit`).
2. If found: range is `<last_commit>..HEAD`
3. If not found (first release): ask the user for the starting point — could be a commit hash, a tag, or "everything on main"

Show the user: "This release will cover commits `<range>` — [N] commits across [M] files. Continue?"

### Step 3: Auto-draft from git context

Build a first draft of the release doc so the user isn't starting from blank.

1. Run `git log --pretty=format:"%h|%s|%b" <range>` to get commit messages
2. Run `git diff --stat <range>` to get files changed with line counts
3. For each skill touched, run `git diff <range> -- skills/<name>/SKILL.md | head -100` to sample the kind of change

Assemble a **draft** `updates/YYYY-MM-DD-<slug>.md` with these sections filled from git context:
- Title — derived from commit subjects (user can override)
- Commit range, files changed, skills affected
- "What Changed" — one paragraph per skill, summarizing the diff in plain language

Leave these sections **empty** or marked `[AI: draft based on the diff, user must confirm]` for the user to fill in:
- Why (the value — what the user feels differently after updating)
- Cost to adopt (2 min / 15 min / 30+)
- Manual steps outside the repo
- Opt-out boundaries

### Step 4: Interrogate the user for what only they know

Ask these in sequence, one at a time. Don't batch — each answer shapes the next.

1. **Why** — "What problem does this solve for the user, in one sentence? Avoid describing the mechanism; describe what they feel differently."
   - Good: "Your weekly priorities now surface in the daily note, so you see what you're supposed to focus on at open-day."
   - Bad: "Added a transclusion to the daily template."

2. **Cost to adopt** — "Roughly how long should a fork expect to spend adopting this? 2 min (trivial), 15 min (some manual work), 30+ min (involves vault changes or decisions)?"

3. **Manual steps outside the repo** — "Anything the user has to do that isn't in the git changes? Vault template edits, env vars, external service setup, directory scaffolding, etc. List them as a checklist."

4. **Opt-out boundaries** — "If a fork only wants part of this, what's independently adoptable? For each skill changed, can it be pulled without the others? Can the manual steps be deferred?"

5. **Breaking change?** — "Does this break existing fork behavior if they don't do the manual steps? Or does it degrade gracefully?" (This determines how prominently the announcement flags the manual steps.)

### Step 5: Generate the release doc

Write `updates/YYYY-MM-DD-<slug>.md` with this structure:

```markdown
---
date: YYYY-MM-DD
slug: <slug>
last_commit: <full-sha-of-HEAD-at-publish-time>
commit_range: <range>
skills_changed: [skill1, skill2, ...]
files_changed: <count>
cost_to_adopt: "2 min" | "15 min" | "30+ min"
breaking: true | false
---

# [Human Title]

## Why
[One paragraph — what the user feels differently after updating. From Step 4 question 1.]

## What Changed
[Per-skill summary, auto-drafted from the diff, user-reviewed.]

### `skill-name` — [one-line headline]
- [bullet: what now happens]
- [bullet: what the user sees differently]

## Cost to Adopt
**[2 min | 15 min | 30+ min]** — [one line on what drives the cost]

## Safe Merge

**If you haven't customized these skills:**
```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/<skill-1>/SKILL.md skills/<skill-2>/SKILL.md
git commit -m "pull upstream: [slug]"
```

**If you have customized one or more skills:**

For each skill, first see what changed upstream vs. what you've changed locally:
```bash
# What upstream changed
git diff HEAD upstream/main -- skills/<skill>/SKILL.md

# What you've changed vs upstream's old baseline
git log --oneline <last_commit>..HEAD -- skills/<skill>/SKILL.md
```

Three options per skill:
1. **Accept upstream, lose your changes** — `git checkout upstream/main -- skills/<skill>/SKILL.md`
2. **Merge manually** — `git merge-file` or edit by hand, keeping your customizations
3. **Skip this skill entirely** — don't pull it; you stay on your current version and miss this change

## Opt-Out Guide

[From Step 4 question 4. Which parts are independently adoptable. Example:]
- Want the open-week link writing but not the daily-template embed? Pull `open-week` only, skip the manual step.
- Don't want week-rank annotations? Pull `open-week` and the daily-template step, skip `open-day` and `close-day`.

## Manual Steps

[From Step 4 question 3. Checklist format.]

- [ ] Edit `$OBSIDIAN_VAULT_PATH/_templates/daily-note.md` to add `![[10-strategy/stack-rank/<% tp.date.now("YYYY-[W]WW") %>]]`
- [ ] Create directory `$OBSIDIAN_VAULT_PATH/10-strategy/stack-rank/` if it doesn't exist

[If breaking:] ⚠ **Required for the skill updates to work.** If you skip these, the updated skills will fail or produce broken output.

## Commits Included
[Auto-generated from `git log <range>`]
- `<sha>` — <subject>
- `<sha>` — <subject>
```

Show the draft to the user. Ask: "Anything to change before publishing?"

### Step 6: Update the release log index

Read `updates/README.md`. If it doesn't exist, create it with this header:

```markdown
# Personal Toolkit Release Log

Running history of updates to `nsls-personal-toolkit`. Newest first.

Each release has a per-file detail page describing the change, its cost to adopt, safe-merge guidance, and any manual steps. Read before running `/update-personal-productivity` to decide what's worth pulling.

---

```

Then **prepend** (newest first) one line:

```markdown
- **YYYY-MM-DD** — [Title](YYYY-MM-DD-<slug>.md) — [cost_to_adopt]. [One-sentence Why headline.]
```

### Step 7: Commit and push

```bash
git add updates/
git commit -m "release: [slug] — [one-line summary]"
git push origin main
```

### Step 8: Post Railway announcement

POST to `https://web-production-6281e.up.railway.app/announcement`:

```json
{
  "title": "Toolkit update: [slug headline]",
  "body": "[Why headline — one sentence]. Cost to adopt: [cost]. Read updates/YYYY-MM-DD-<slug>.md before pulling — it walks through safe-merge and any manual steps. Run /update-personal-productivity when ready.",
  "target_toolkit": "personal",
  "command": "/update-personal-productivity"
}
```

Keep the body under 280 characters. The release doc carries the detail; the announcement just points forks to it.

### Step 9: Confirm to the user

Show:
- Release doc path: `updates/YYYY-MM-DD-<slug>.md`
- Release log updated: `updates/README.md`
- Commit pushed: `<sha>`
- Announcement ID: `<id>` from POST response

---

## Output format rules

**The Why section is the hardest to write well. These are the rules:**
- Lead with what the user *feels or sees* differently, not what mechanism changed
- One concrete example beats two paragraphs of explanation
- If you can't write the Why without saying "we changed X to Y," you don't have a Why yet — go back to the user and ask what problem X was actually solving
- No jargon unless it's already toolkit jargon the user knows

**Cost estimate honesty:**
- 2 min = git pull only, no manual steps
- 15 min = git pull + one vault change or env var
- 30+ min = multiple manual steps, decisions about opt-out, or vault restructuring
- If unsure, round up. Forks abandon updates that took longer than promised.

**Opt-out is non-negotiable.** Every release must say which parts are independently adoptable. If nothing is — if it's all-or-nothing — say that explicitly and explain why.

---

## Failure modes

- **User pushes before running `/announce-update` → skill finds no new commits**: tell the user the range is empty and ask what they want to announce
- **User has uncommitted changes**: stop at Step 1.2; don't announce a half-shipped state
- **Railway POST fails**: the release doc is already committed and pushed — that's the durable artifact. Tell the user the announcement POST failed, show the exact payload, and offer to retry
- **`updates/README.md` index drifts out of order**: re-sort by date in frontmatter; don't trust file-system order

---

## What this skill deliberately does NOT do

- **Does not walk forks through the merge.** That's the fork-side job of `/update-personal-productivity`. This skill just produces the artifact that skill will read.
- **Does not decide breaking-vs-non-breaking.** The user decides in Step 4.5.
- **Does not auto-generate the Why from diffs.** Diff-derived text is always mechanical ("moved X from A to B"). Value-level prose has to come from the user.
