# Cowork Companion — Session Handoff

**Paste the prompt at the bottom into a fresh Claude Code session opened on the worktree.**
Everything above it is context the new session should internalize.

---

## Where you are (read this first)

You are building the **cowork companion** for the NSLS personal productivity toolkit — a
Claude Desktop (cowork) **React-artifact** rendering of the daily ritual companion. A
CLI/web companion already exists and works (Flask app in `companion/`); you are **NOT**
replacing it — cowork is a second rendering surface over the same Obsidian vault and the
**same markdown contract**.

You are working in a **git worktree at `~/dev/nsls-personal-toolkit-cowork`**, branch
`pp-cowork-companion`. This is deliberate: the real repo lives at
`~/.claude/local-plugins/nsls-personal-toolkit`, but the VS Code extension **forces a
permission prompt on every edit to any path under `~/.claude/`** (an over-broad
config-protection guardrail, outside the permission-mode system — GitHub issues
#15921 / #66525 / #37253). Editing in the worktree (outside `~/.claude/`) sidesteps it
entirely. The main checkout is parked on `pp-cli-visual`; do your work here and commit to
`pp-cowork-companion` — same shared git history.

Do **not** move back into `~/.claude/local-plugins/...` to edit; stay in the worktree.

## Read these, in order

1. `docs/specs/2026-06-13-cowork-companion-design.md` — design spec
2. `docs/plans/cowork-companion-build-plan.md` — phased plan; read "Recent learnings (2026-06-14)" carefully
3. `docs/specs/2026-05-16-cli-companion-webapp-design.md` — CLI companion spec
4. `companion/parsers.py`, `companion/server.py` (the plan-form routes: `set_top_3`,
   `set_bonus`, `delete_bonus`, `_build_plan_context`, `_render_bonus_list`,
   `_detect_day_state`; the `?closing=1` banner in `templates/day.html`), `companion/streak.py`
5. `skills/open-day/SKILL.md`, `skills/close-day/SKILL.md` (surface branch, `-r` reset flag,
   `?closing=1` close entry, "Output Discipline")

## Non-negotiables (painful CLI lessons — do not relitigate)

Identical markdown contract (a day planned in cowork opens cleanly in the CLI and vice
versa); explicit mode via `status:` frontmatter (never infer from which sections exist);
two energy captures (morning in Morning Check-in, evening in End of Day);
mutually-exclusive Done/Deleted/Deferred; state lives in the artifact, write back ONCE on
explicit save (no autosave/SSE/server); one canonical streak rule (`streak.py` canonical,
JS display copy + parity test); `log.md` canonical for habits (MAX-merge); one skill per
ritual, surface-detected. UX: positional slots never compacted; never re-render an input
mid-edit; continuous list entry; entry-context `phase: planning|active|closing`; evening
energy hidden on the active view; progress + delete independent and reversible, <100%
auto-carries.

**Scope (daily core only):** open-day + close-day + Command Center + habits/streaks as the
cowork-dashboard artifact. Week rituals, onboarding, `/schedule`, other views = Phase 2,
do not build. **Phase 0 gate:** do not build the artifact UI until the
artifact→Claude→vault write-back round-trip is proven in a real Claude Desktop session.

**Working method:** TDD (red→green), keep `companion/tests/` green (146+) and add tests for
new shared logic. Commit on `pp-cowork-companion`; **no push/PR/merge/sharing without
Davo's explicit per-action OK** (his #1 rule; the global `~/.claude/settings.json`
PreToolUse hook also re-gates push/gh/curl-POST/rm-rf even under bypassPermissions).

## State as of this handoff

**Done:**
- Branch `pp-cowork-companion` created off `pp-cli-visual`.
- Phase 0 deliverables (in `docs/cowork/`): `README-phase0-setup.md` (cowork project setup +
  file-access diagnostic), `project-instructions.md` (paste into the cowork project),
  `cowork-artifact/counter-test.md` (the write-back round-trip probe artifact). These are
  ready for Davo to run in a real Claude Desktop session (vault: `/Users/claw/Obsidian/DW`).
- The VS Code permission saga is resolved via this worktree. A global PreToolUse hook at
  `~/.claude/hooks/permission-gate.py` auto-allows edits/safe-bash and re-gates sharing.

**In progress — pick up here (Phase 1.3a, TDD):**
- `companion/tests/test_frontmatter.py` was authored but never landed (it kept being blocked
  by the permission bug). RE-CREATE it (tests for `parse_frontmatter` / `set_frontmatter`),
  watch it fail, then implement those two generic helpers in `companion/parsers.py`
  (mirror `parse_weekly_frontmatter`/`set_weekly_frontmatter` in `companion/week_parsers.py`;
  do NOT touch week_parsers — Davo is testing the week path). The test content is in this
  session's transcript if recoverable; otherwise re-derive from the weekly frontmatter tests
  in `companion/tests/test_week_parsers.py`.

**Then (the todo list):**
1. Phase 1.3b — `_detect_day_state` prefers `status:` frontmatter, backward-compatible
   (status closed→results, active→command [empty Insight Reflection heading→coach-evening],
   planning→coach-morning; no status → existing inference). +tests.
2. Phase 1.3c — companion write paths set status (open/reset→planning, `/lock-in`→active,
   close→closed). +tests.
3. Phase 1.3d — skill prose: open-day writes `status: planning`; close-day sets
   `status: closed`.
4. Phase 1.2 — `streak.js` display copy + JS↔Python parity test over the six canonical
   sequences.
5. Full suite green (146+).

**Two NEW meta-tasks Davo requested:**
- Add to `docs/plans/cowork-companion-build-plan.md` a task to create an **"unblock" skill**:
  detects when someone is editing the toolkit under `~/.claude/` in the VS Code extension and
  hitting permission prompts, and offers to set up a worktree/symlink outside `~/.claude/`.
- Build that skill (and consider the structural install fix: clone toolkit to `~/dev/...`,
  symlink into `~/.claude/local-plugins/` — so builders never hit this).

---

## PASTE THIS as the opening prompt in the new session

> You're continuing the cowork-companion build for the NSLS personal toolkit, now in the
> worktree at `~/dev/nsls-personal-toolkit-cowork` (branch `pp-cowork-companion`). Read
> `docs/cowork/HANDOFF.md` in full first — it has the full context, the non-negotiables, and
> exactly where to resume (Phase 1.3a: re-create `companion/tests/test_frontmatter.py` TDD-style,
> then implement `parse_frontmatter`/`set_frontmatter` in `companion/parsers.py`). Then read the
> spec + plan it points to, confirm the test suite runs, and continue the plan with TDD. Don't
> push or share anything without my explicit OK.
