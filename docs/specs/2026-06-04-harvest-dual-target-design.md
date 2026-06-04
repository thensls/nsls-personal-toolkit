# Harvest-Meeting Dual-Target Design

**Date:** 2026-06-04
**Skill:** `nsls-personal-toolkit/skills/harvest-meeting`
**Status:** Approved, ready for plan

## Problem

`/harvest-meeting` is installed for everyone via the personal toolkit, but it only
*does* anything for the 7 SLT members on the `kb_authors.txt` allowlist. Non-SLT
users hit a dead end: `--date`/`--fathom-url` modes silently skip, and `--week-audit`
runs audit-only. The skill is visible but unusable for most of the org — a broken
promise.

## Goal

Make the skill useful to everyone without exposing the company KB to non-SLT writers:

- **SLT members** → harvest into the company KB (`thensls/nsls-knowledge`, pushed to
  `main`) — unchanged behavior.
- **Everyone else** → harvest into a self-contained **local KB** that never touches the
  org repo (local git commits, no remote).

The SLT allowlist stops being a *write gate* and becomes a *routing decision*.

## Design decisions (from brainstorm)

1. **Routing: auto by membership.** No prompt. Allowlist match → company; otherwise →
   local.
2. **Local storage: local git repo, no remote.** `git init` in the vault folder, commit
   each harvest with the existing commit machinery, never push. User can add their own
   remote later if they want.
3. **Seeding: ship a starter scaffold.** Bundle a small set of **org-level** seed topic
   files + the rubric `CLAUDE.md`, copied in on first run. Stubs are about NSLS the
   organization, NOT personal/Kevin-specific.

## Architecture

### Routing variables (Step 0)

Keep the existing identity-resolution + `is_slt` machinery untouched. Add exported
variables consumed by every later step:

| Variable | SLT member | Non-SLT |
|---|---|---|
| `KB_TARGET` | `company` | `local` |
| `KB_DIR` | `$OBSIDIAN_VAULT_PATH/60-nsls-knowledge` | `$OBSIDIAN_VAULT_PATH/60-nsls-knowledge-local` |
| `KB_PUSH` | `true` | `false` |
| `WRITE_AUTHORIZED` | `true` | `true` (was `false`) |

**Key semantic flip:** `WRITE_AUTHORIZED` is now `true` for everyone. It no longer means
"may this user write at all" — it means "writes go *somewhere*." Downstream steps (8, 9d,
9e) keep consulting it, so local-KB owners now get promotion/stale-flag offers too.

**`looks_misconfigured` case** (an `@nsls.org` email is present but not in the allowlist):
no longer skips. Routes to local KB, but still prints the existing loud allowlist-gap note
("if you're actually SLT, ask Kevin to add you to kb_authors.txt + tick Members.is_slt;
meanwhile you're writing to your local KB"). A genuinely-SLT-but-unlisted person is never
silently demoted without explanation.

**Genuinely non-SLT case** (no `@nsls.org` email anywhere): route to local, print a short
"writing to your local KB at <path>" heartbeat. No setup-fix nag — local is the expected
home, not a misconfiguration.

### Local KB first-run setup (new sub-step, Step 1a-local)

When `KB_TARGET=local` and `$KB_DIR` is missing or lacks `.git`:

1. `mkdir -p "$KB_DIR"`
2. `git -C "$KB_DIR" init`
3. Set **local** commit identity: the detected email if any, else a generic fallback
   (e.g. `harvest-local@nsls.org` / `NSLS KB (local)`). Local-only config, never global.
4. Copy the seed scaffold (`references/local-kb-seed/*`) into `$KB_DIR`.
5. Initial commit: `"local KB: initial scaffold"`.

**No remote is ever added.** Push is physically impossible — there is no `origin`. This is
the safety guarantee that a non-SLT user cannot reach the company repo through this path.

### Seed scaffold (`references/local-kb-seed/`)

Ships inside the skill, resolved via the same two-candidate-path pattern as
`kb_authors.txt` (repo-clone path first, plugin-install path second).

Contents:
- `CLAUDE.md` — carries the **`## Sensitive-Content Rubric`** section verbatim. Step 1b
  greps the local `CLAUDE.md` for this header to load the rubric, so it must be present.
  **Decision:** the rubric stays active for local KBs too. It's uniform (no pipeline
  branch), costs nothing, and protects the user if they ever share the KB. Documented as
  deliberate, not an oversight.
- `_index.md` — short orientation note explaining this is a personal/local KB.
- Org-level starter topic stubs (empty Current State / Key Decisions / Open Questions),
  e.g.:
  - `how-nsls-works.md`
  - `org-structure.md`
  - `products-and-programs.md`
  - `chapter-network.md`

  These are about NSLS the organization so the topic mapper has real targets on day one.
  **No personal or Kevin-specific stubs.**

### Parameterizing the pipeline

Every Python block currently hardcodes
`pathlib.Path(os.environ['OBSIDIAN_VAULT_PATH']) / '60-nsls-knowledge'`. Replace with
`pathlib.Path(os.environ['KB_DIR'])` (exported by Step 0). Bash blocks already use a
`KB_DIR` shell var — make them read the Step 0 value rather than re-deriving the company
path.

Branches on `KB_PUSH` / `KB_TARGET`:

- **Step 1a (freshness):**
  - company → `git pull --ff-only` as today; FATAL if not cloned (unchanged).
  - local → skip pull (no remote); run the §"first-run setup" to ensure folder + git +
    scaffold exist; heartbeat `Step 1a: local KB ready at <dir> (<short-sha>)`.
- **Step 1b (load topics):** identical logic, reads `KB_DIR`. The "fewer than 40 topic
  files = something's wrong" alarm becomes **company-only** — a fresh local KB legitimately
  has ~5 files.
- **Step 8 (commit/push):**
  - both → `git add` + `git commit`.
  - push + rebase-retry block runs **only when `KB_PUSH=true`**.
  - the pre-write `git pull --ff-only` runs only for company.
  - local heartbeat: `Step 8: committed <sha> locally — <N> edits to <M> file(s) in
    60-nsls-knowledge-local (not pushed — local KB)`.

### Week-audit mode (Step 9)

- **9a/9b/9c (audit report):** work against `KB_DIR` for both targets. 9b unharvested-
  meeting cross-ref compares git log vs Fathom — valid for local too.
- **9d (promotion offers) / 9e (stale-flag offers):** gated on `WRITE_AUTHORIZED`, which is
  now `true` for local owners → these become available to everyone. Commits respect
  `KB_PUSH` (local: commit, no push).
- **9f (non-SLT dead-end):** the old "audit-only, open a PR against thensls/nsls-knowledge"
  message is removed. Replaced by normal local-KB behavior — non-SLT users get the full
  audit + write actions against their local KB.

### Skill metadata

- `SKILL.md` frontmatter `description`: change "Gated to SLT writers" to reflect dual
  target — SLT → company KB, everyone else → a local KB. Update the opening prose and
  "First-Time Setup" / "SLT Allowlist" sections to describe routing rather than a hard gate.
- `.claude/skills/harvest-meeting/SKILL.md` stub description: mirror the same wording.

### Callers (integration check)

- `close-day` Step 4c and `close-week` Step 2b invoke `/harvest-meeting --date` /
  `--week-audit`. Invocation is unchanged. **Action:** read both callers, confirm they
  don't assume company-only semantics or special-case the non-SLT skip. Non-SLT users
  running `/close-day` will now begin building a local KB — this is the intended outcome,
  but the caller prose may need a one-line tweak so it reads correctly for local. Record
  exact edits (if any) in the plan.

## Out of scope

- No UI to choose target (auto-by-membership only).
- No syncing local KB → company KB (a non-SLT user who joins SLT later can re-harvest or
  manually port; not automated here).
- No per-user remote setup for local KBs (user can add their own `origin` by hand).

## Testing / verification

- SLT identity → routes company, pushes (existing behavior intact).
- Non-SLT identity (no nsls email) → first run scaffolds local KB, harvest commits locally,
  no push attempted, no network call to the org repo.
- `looks_misconfigured` identity (nsls email not in allowlist) → routes local + prints the
  allowlist-gap note.
- Local week-audit → audit report + promotion/stale offers commit locally.
- Verify `references/local-kb-seed/CLAUDE.md` rubric header is found by Step 1b.
- Verify push is impossible from a local KB (no `origin`).
