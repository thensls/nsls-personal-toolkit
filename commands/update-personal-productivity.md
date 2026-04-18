---
name: update-personal-productivity
description: >-
  Pull the latest skills from the personal toolkit template repo, release by
  release. Walks you through each unadopted release in updates/ — shows the Why,
  detects customizations in your local skills, offers three safe-merge paths
  (accept upstream / merge manually / skip), and tracks manual steps as a
  pending checklist. Use when you see an announcement about new skills or want
  to check for updates. Trigger phrases: update personal productivity, update my
  skills, pull latest skills, grab new skills, check for skill updates.
---

# Update Personal Productivity Skills

Walk through unadopted releases in `updates/` one at a time. Safely merge each one with your local customizations. Keep a list of manual steps you still need to do.

---

## Step 1: Prep

```bash
REPO=~/nsls-skills/nsls-personal-toolkit

# Ensure upstream remote exists (forks only)
if ! git -C "$REPO" remote | grep -q '^upstream$'; then
  git -C "$REPO" remote add upstream https://github.com/thensls/nsls-personal-toolkit.git
fi

# Fetch latest
git -C "$REPO" fetch upstream

# Ensure .toolkit-state.json is gitignored
if ! grep -q '^.toolkit-state.json$' "$REPO/.gitignore" 2>/dev/null; then
  echo '.toolkit-state.json' >> "$REPO/.gitignore"
fi
```

---

## Step 2: Load adoption state

Read `~/nsls-skills/nsls-personal-toolkit/.toolkit-state.json`. If missing, initialize with:

```json
{
  "adopted_releases": [],
  "skipped_releases": [],
  "pending_manual_steps": [],
  "last_checked": null,
  "first_run_initialized": false
}
```

**First-run initialization.** If `first_run_initialized: false` (or the file was just created), before prompting the user about any release, auto-detect which releases the fork has already effectively adopted by virtue of prior `git pull`s.

For each release doc in `updates/*.md`, read its `last_commit` frontmatter. Then check:

```bash
git -C "$REPO" merge-base --is-ancestor <last_commit> HEAD
```

If the ancestor check succeeds (exit 0), the fork's HEAD already includes that release's commits — auto-add the slug to `adopted_releases`. If it fails (exit 1), the release is genuinely unadopted.

Show the user a one-time summary:
> "First run — I auto-detected [N] releases already in your fork. [M] unadopted releases to walk through."

Then set `first_run_initialized: true`. Subsequent runs skip this step.

**Caveat:** auto-detection is accurate for the skill files but can't know if the fork completed the **manual steps** for those releases. After the auto-mark, ask: "I marked [N] historical releases as adopted based on your commit history. Want to review their manual-step checklists to confirm you've done them, or trust that you have?" If review, surface manual steps from each auto-adopted release as pending items.

**State schema:**
- `adopted_releases`: release slugs where the user pulled some or all of the changes
- `skipped_releases`: release slugs the user explicitly chose to skip (don't re-prompt)
- `pending_manual_steps`: `[{release, step, added_date}]` — manual steps the user hasn't confirmed done yet
- `last_checked`: ISO date of last run

---

## Step 3: Enumerate releases

List every `updates/*.md` file (excluding `README.md`):

```bash
ls "$REPO/updates/" | grep -v '^README.md$' | sort
```

Filenames are `YYYY-MM-DD-<slug>.md` — sort order = chronological.

For each file, read the frontmatter to get: `date`, `slug`, `skills_changed`, `cost_to_adopt`, `breaking`, `backfilled`.

Filter to **unprocessed** releases: those whose slug is in neither `adopted_releases` nor `skipped_releases`.

If the list is empty:
> "You're caught up. No unadopted releases in upstream."
>
> *(Also show pending manual steps from prior releases — see Step 7.)*

Otherwise, tell the user:
> "You have [N] unadopted release(s) to walk through. Oldest first — let's start with [date] — [title]."

---

## Step 4: Walk each release (loop)

For each unadopted release, in chronological order:

### 4a. Show the Why

Open the release file. Show the user:
- **Title**
- **Why** (the full section)
- **Cost to Adopt**
- **Skills Changed** (from frontmatter)
- **Breaking?** (if `breaking: true`, call it out prominently)
- **Backfilled?** (if `backfilled: true`, note: "This is a backfilled entry — Why may be sparser than newer releases.")

### 4b. Ask the top-level question

> "What do you want to do with this release?
>
> - **adopt** — walk me through each skill change and apply it
> - **skip** — mark as not-for-me, don't re-prompt
> - **defer** — leave it for a later session
> - **read more** — show me the full release doc first"

If `read more`: display the whole file, then re-ask.
If `defer`: move on to the next release without updating state.
If `skip`: add slug to `skipped_releases`, move on.
If `adopt`: go to 4c.

### 4c. Walk each skill in the release

For each skill in `skills_changed`:

**Detect customization** — has the user made **local commits** that touch this skill? This is the clean test because `git diff upstream/main` conflates local changes with "behind upstream."

```bash
# Local-only commits touching this file (not in upstream)
git -C "$REPO" log upstream/main..HEAD --oneline -- skills/<name>/SKILL.md
```

- If empty → user has no local customizations. **Fast path available.**
- If non-empty → user has commits upstream doesn't have. **Merge path needed.** Show the user their local commit history:
  > "You have [N] local commit(s) touching this file:
  >   - <sha>: <subject>"

**Check whether upstream has new content to offer:**

```bash
git -C "$REPO" log HEAD..upstream/main -- skills/<name>/SKILL.md --oneline
```

- If empty → nothing to pull for this skill (may have been adopted earlier, or this release didn't actually change it). Skip.
- Otherwise → list the upstream commits so the user can see what's coming.

**Present the merge choice:**

> "**`<skill-name>`** — [summary from the release doc's `What Changed` section]
>
> Upstream commits since your last sync:
>   - <sha>: <subject>
>   - <sha>: <subject>
>
> You have [no | minor | significant] local customizations to this skill. Options:
>
> - **accept** — checkout upstream's version; your local changes to this skill are lost (but still in git history)
> - **merge** — show me both diffs side-by-side; I'll help you edit a merged version
> - **skip** — keep my version as-is; I'll miss this release's changes for this skill
> - **diff** — show me what upstream changed before deciding"

**For `accept`:**
```bash
git -C "$REPO" checkout upstream/main -- skills/<name>/SKILL.md
```

**For `merge`:**
- Show upstream diff: `git -C "$REPO" diff HEAD upstream/main -- skills/<name>/SKILL.md`
- Show user's local changes: `git -C "$REPO" log -p HEAD -- skills/<name>/SKILL.md | head -200`
- Present both, ask which upstream additions to accept, draft a merged file, show to user, write after confirmation

**For `skip`:** do nothing, move on.

**For `diff`:** show the diff, then re-ask.

After all skills in the release are processed, move to 4d.

### 4d. Queue manual steps

Read the release doc's `## Manual Steps` section. For each checkbox item:

> "**Manual step** for [release slug]:
>
> [step text]
>
> Have you already done this? (yes / no / skip / help)"

- `yes` → don't add to pending
- `no` → add `{release, step, added_date: today}` to `pending_manual_steps`
- `skip` → don't add (user declined this specific step)
- `help` → show the step with full context; re-ask

### 4e. Commit the adoption

If any files changed in 4c:

```bash
git -C "$REPO" add skills/ commands/
git -C "$REPO" commit -m "adopt upstream: <slug>"
```

Add slug to `adopted_releases` in state.

---

## Step 5: Save state

Write `~/nsls-skills/nsls-personal-toolkit/.toolkit-state.json` with updated `adopted_releases`, `skipped_releases`, `pending_manual_steps`, and `last_checked: <today>`.

---

## Step 6: Log to Railway

```bash
curl -sS -X POST https://web-production-6281e.up.railway.app/event \
  -H "Content-Type: application/json" \
  -d '{
    "builder_email": "<from $REPO/.env BUILDER_EMAIL>",
    "event_type": "toolkit_update",
    "points": 0,
    "description": "Adopted releases: <comma-separated slugs>. Skipped: <slugs>. Pending manual steps: <count>."
  }'
```

---

## Step 7: Show pending manual steps

Regardless of whether any new releases were processed, show the user their pending manual-step list:

```
You have [N] manual step(s) pending from past releases:

📋 From 2026-04-18-stack-rank-flow (added Apr 18):
  [ ] Edit your daily template to embed stack rank
  [ ] Create 10-strategy/stack-rank directory

Want to mark any of these done? (enter release+step number, or "skip")
```

Update `pending_manual_steps` based on user confirmations.

---

## Step 8: Confirm

> "Update complete.
>
> - Adopted: [N] releases
> - Skipped: [N] releases
> - Deferred: [N] releases (run again anytime to see them)
> - Manual steps pending: [N]
>
> Changes are in your local fork — they'll be active in your next Claude Code session."

---

## Critical safety rule

**Never run `git checkout upstream/main -- skills/` across multiple releases at once.** This overwrites customizations you preserved in an earlier release's merge. The command walks per-skill, per-release specifically so customizations survive across multiple releases when the same skill is touched more than once.

If you're tempted to "accept all" across several releases at once, run the command once per release — the state file tracks progress, so you can stop and resume anytime.

---

## Edge cases

**User hasn't set up the upstream remote.** Step 1 adds it automatically.

**User is on a branch other than `main`.** Warn: "You're on branch `<X>`, not `main`. Adoptions will commit here. Continue?"

**User has uncommitted local changes.** Before Step 4, warn: "You have uncommitted changes in `<files>`. Stash or commit before adopting upstream? Continue anyway risks messy merges."

**Release doc is malformed** (missing frontmatter, missing sections). Show what you could parse, warn about what's missing, ask the user whether to proceed with limited info or skip the release.

**User customized a skill that upstream deleted.** Edge case — tell the user "Upstream removed `skills/<name>`. Your local version still exists. Keep it, or delete?" Default: keep.

**Network failure on `git fetch`.** Fall back to whatever's already in `upstream/main` locally; warn that data may be stale.

**User runs this with no releases yet** (fresh fork, empty `updates/`). Tell them: "No releases published yet. Run `git pull upstream main` to get the base skills." Continue with a vanilla pull, no release walk.

---

## What this command deliberately does NOT do

- **Does not auto-merge.** Every skill-level decision is explicit. If upstream and local both touched a file, the user reviews before a merge is written.
- **Does not auto-complete manual steps.** Those are vault edits, env vars, external services — outside the repo. The user confirms done, the command just tracks.
- **Does not delete skipped releases.** A skipped release stays in `updates/` forever; the state file just records "don't re-prompt."
- **Does not revert.** If a user accepts upstream and regrets it, they use git. This command is forward-only.
