---
date: 2026-04-18
slug: stack-rank-flow
last_commit: 1f8cf9d6ea7272193746e7369fc1482e27fb63f4
commit_range: 5ee6b94..1f8cf9d
skills_changed: [open-week, open-day, close-day]
files_changed: 3
cost_to_adopt: "15 min"
breaking: false
---

# Stack rank flows into daily planning

## Why

Before this release, the weekly stack rank lived in one place (`10-strategy/stack-rank/YYYY-WNN.md`) and the daily note lived somewhere else (`01-daily/YYYY-MM-DD.md`) — and the two didn't talk to each other. You'd do careful weekly prioritization on Sunday, then Monday morning your daily note showed a generic 26-row project list with no rank signal.

After this release, the weekly stack rank is embedded in your daily note. Your Top 3 for the day show their week rank inline (`*(week rank: 3)*` or `*(not in week's Top 5)*`). End-of-day, the projects you touched are annotated the same way — so you can see at a glance whether your day aligned with your week's priorities.

**The closed loop:** weekly priorities → daily planning → daily execution → daily reality check → weekly review. No more prioritizing on Sunday and forgetting by Tuesday.

## What Changed

### `open-week` — writes clickable project links in the stack-rank table

When `/open-week` generates your stack-rank file, it now writes project names as `[[slug]]` wiki-links when a project home exists at `20-projects/<slug>/<slug>.md`, plain text otherwise. This makes the table clickable when embedded in your daily note.

### `open-day` — Top 3 items surface their week rank

Every Top 3 priority is now traced to a project and annotated with its rank in this week's stack rank. Format: `[description] — [[project-slug]] *(week rank: N)*`. Priorities that aren't in the week's Top 5 show `*(not in week's Top 5)*` — an honest signal that you're spending a Top 3 slot on something unranked (sometimes right, sometimes drift to flag).

### `close-day` — Projects Touched annotated with week rank

The Projects Touched section now reads your week's stack rank and tags each project touched today with its rank. Seeing `[[directory-requests]] *(not in week's Top 5)* — 2.5h` alongside `[[product-team-recruiting]] *(week rank: 5)* — 20 min` makes alignment gaps visible without any judgment.

## Cost to Adopt

**15 min** — the skill changes pull automatically via `/update-personal-productivity`, but you also need to edit your daily template (one-time, ~5 min) and make sure you have the `10-strategy/stack-rank/` directory with at least one week's file. If you've never run `/open-week` with a stack rank, you'll need to do that first.

## Safe Merge

**If you haven't customized `open-week`, `open-day`, or `close-day`:**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch origin
git checkout origin/main -- skills/open-week/SKILL.md skills/open-day/SKILL.md skills/close-day/SKILL.md
git commit -m "pull upstream: stack-rank-flow"
```

**If you have customized one or more of these skills:**

First see what changed upstream:

```bash
# See upstream changes per skill
git diff HEAD origin/main -- skills/open-week/SKILL.md
git diff HEAD origin/main -- skills/open-day/SKILL.md
git diff HEAD origin/main -- skills/close-day/SKILL.md
```

Three options per skill:

1. **Accept upstream, lose your changes**: `git checkout origin/main -- skills/<name>/SKILL.md`
2. **Merge manually**: open the file, apply the upstream additions alongside your customizations. The changes are additive (new sections and format rules), so most merges will be clean.
3. **Skip this skill**: you miss the annotation behavior but everything else keeps working.

The three skills work **together** but each piece is useful alone — see Opt-Out Guide below.

## Opt-Out Guide

- **Want clickable stack-rank table but no daily annotations?** Pull `open-week` only. Skip `open-day`, `close-day`, and the daily-template edit.
- **Want Top 3 annotations but not the table embed?** Pull `open-week` + `open-day`. Skip the daily template edit and `close-day`.
- **Want daily alignment tracking but not weekly linking?** Pull `open-day` + `close-day`. Leave `open-week` alone. (Your existing stack-rank files won't have `[[links]]`, but the rank lookup still works on project names.)
- **Don't want any of this?** Skip the release entirely. Your existing skills keep working as before.

## Manual Steps

The following happen in your Obsidian vault, **not in the toolkit repo**, so they can't be pulled automatically.

- [ ] **Edit your daily template.** Open `$OBSIDIAN_VAULT_PATH/_templates/daily-note.md` and replace the existing `## Active Projects` section (or add a new section near the top) with:

  ```markdown
  ## This Week's Stack Rank
  ![[10-strategy/stack-rank/<% tp.date.now("YYYY-[W]WW") %>]]
  ```

- [ ] **Move the full portfolio list to the bottom, collapsed.** Add this at the end of the template so you still have access without cluttering the top:

  ```markdown
  ## Full Portfolio
  > [!note]- All active projects (collapsed)
  > ```dataview
  > TABLE WITHOUT ID link(file.link, title) AS "Project", next-action AS "Next Action", collaborators AS "With"
  > FROM "20-projects"
  > WHERE type = "project" AND status = "active"
  > SORT priority ASC
  > ```
  ```

- [ ] **Create the stack-rank directory** if it doesn't exist: `mkdir -p $OBSIDIAN_VAULT_PATH/10-strategy/stack-rank`

- [ ] **Run `/open-week`** to generate your first stack-rank file using the new link-writing convention. (If you already have a current-week file, it'll have plain-text project names — you can back-fill `[[slug]]` links manually, or just let the next week's file be the first one with links.)

## Commits Included

- `1f8cf9d` — feat: weekly stack rank flows into open-day and open-week
- `5ee6b94` — feat: knowledge graph integration across close-day, close-week, and learn *(close-day's week-rank annotation was bundled into this earlier commit)*
