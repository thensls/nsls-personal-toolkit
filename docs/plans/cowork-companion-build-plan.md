# Cowork Companion — Build Plan

**Spec:** `docs/specs/2026-06-13-cowork-companion-design.md`
**Scope (this plan):** Daily core — open-day + close-day + Command Center + habits/streaks, as a Claude Desktop React artifact. Week rituals + onboarding are Phase 2.

## Guiding principles (from the CLI build)

1. **Reuse the contract, don't reinvent it.** Every section name, the disposition model, the two-energy model, the habits log format — identical to the CLI companion. The cowork artifact is a *renderer*, not a new data model.
2. **State in the artifact, one write on save.** No autosave, no live-reload. The whole point of the artifact model is to avoid the SSE/server pain. Don't recreate it.
3. **Explicit `status` frontmatter for mode.** Never infer mode from which sections exist (that bug cost us a day on the CLI side).
4. **One canonical streak rule.** Python is canonical; the artifact's JS is a display copy with a parity test.
5. **Surface detection is additive.** The skill keeps its `visual_mode` on/off logic; cowork is a third branch, not a rewrite.

## Phase 0 — De-risk the unknowns (do FIRST, before building UI)

These are the open questions from the spec. Resolved in a real cowork session 2026-06-21.

- **0.1 Surface detection (O1) — PARTIAL.** Cowork is distinguishable from Claude Code on disk (separate read-only snapshot skill store at `~/Library/Application Support/Claude/local-agent-mode-sessions/...`; different skill set; no `~/.claude/` read). A clean *programmatic in-skill* signal is still TBD; until then the skill uses the explicit `open day cowork` override + `companion_surface` in builder-profile.md. Worth asking cowork directly for an env var/marker (Probe D) when convenient.
- **0.2 Artifact ↔ Claude write-back (O2) — ✅ RESOLVED & GATE PASSED.** Channel is **`sendPrompt(text)`** (posts a visible user message into the thread; Claude parses + writes in one turn). `window.claude.complete()` does NOT exist in cowork; `postMessage` posts but never reaches the model. Counter round-trip closed end-to-end: `50-reference/cowork-counter.md` written. The counter-test component's original probe paths were wrong — see updated O2 in the spec.
- **0.3 File access — ✅ RESOLVED.** Cowork can write/read the vault frictionlessly (no prompt). **Delete is gated:** first `rm` fails ("Operation not permitted"), triggers a one-time per-folder grant (`allow_cowork_file_delete`), then works for the session. → save path must be **whole-file replace** (O4), never delete-then-write.

**Gate: ✅ PASSED (2026-06-21).** The write-back round-trip works. Phase 2 (the artifact) is unblocked.

**Marketplace publish OK (Davo, 2026-06-21):** if shipping requires a public Cowork marketplace plugin, that's acceptable **as long as the word "test" is in the skill name** while it's pre-GA. If a publish isn't required, even better.

## Phase 1 — Shared core (reuse, don't rewrite)

- **1.1** Reuse `companion/parsers.py` logic as the contract reference. The artifact needs JS parsers for the same sections; port the *behavior*, and add a test that feeds the same fixtures to both and asserts equal output. (Or: have the skill do the parsing in Python and seed the artifact with clean JSON — preferred, avoids a second parser. See 2.1.) — *Decision locked in 2.1: "Claude parses, artifact renders." No JS markdown parser. Only the streak math is shared JS (1.2). 1.1 effectively folds into 2.1; nothing further to build here.*
- **1.2** ✅ **DONE (2026-06-17).** Streak rule: kept `companion/streak.py` canonical. Wrote `cowork-artifact/streak.js` (display copy, `computeConcern`/`statusFor`/`streakDays`, dual CommonJS + `window.streakRule` export). Parity test (O3) at `companion/tests/test_streak_parity.py` shells `streak.js` through `node` and asserts JS == Python over the six canonical sequences + 3 edge cases; skips cleanly if `node` is absent. Verified the guard catches drift (mutation test). **O3 resolved:** parity runs as a Python test that shells the JS — no separate Node test runner needed.
- **1.3** ✅ **DONE (2026-06-17).** Added `status: planning | active | closed` to the daily-note contract.
  - **1.3a** `parse_frontmatter`/`set_frontmatter` in `companion/parsers.py` (generic daily-note analogues of the weekly versions). +`tests/test_frontmatter.py`.
  - **1.3b** `_detect_day_state` now *prefers* `status` (closed→results; active→command, or coach-evening if `## Insight Reflection` heading present; planning→coach-morning) and falls back to the legacy section/Top-3 inference when status is absent/unknown. +`tests/test_detect_day_state.py`.
  - **1.3c** Companion write paths commit status: `/lock-in` morning→`active`, evening→`closed`; `/reset-plan`→`planning`. +`tests/test_status_write_paths.py`.
  - **1.3d** Skill prose: open-day writes `status: planning` (preserves a later status on re-run); close-day Step 5 sets `status: closed`; reset-day prefers `status` for state detection, `--close-only`→`planning`, empty-vault stub→`closed`.
  - Full suite 180 passing (was 146 baseline).

## Phase 2 — The artifact (daily core)

Prefer **Claude parses, artifact renders**: the skill reads the daily note in Python/MCP, hands the artifact a clean JSON blob (Top 3, Bonus, Unplanned, dispositions, habits+streaks, both energies, mode). The artifact never parses markdown — it just renders JSON and emits JSON on save. This avoids a second markdown parser in JS (only the streak display math is shared logic).

- **2.1** ✅ **DONE (2026-06-21).** `cowork-dashboard` artifact skeleton. Spec `docs/specs/2026-06-21-cowork-dashboard-2.1-design.md`, plan `docs/plans/2026-06-21-cowork-dashboard-2.1.md`. Built TDD (203 tests passing). Design direction is **"cockpit-portrait"** — NSLS navy frame, **solid** progress discs (teal conic = partial, gold = done), compact streak chips, single narrow column for cowork's side panel — NOT the CLI aesthetic (deliberately a better, on-brand design). Architecture cross-reviewed by Codex (the new `/codex-review` skill); fixes folded in: **mode resolved in Python and passed as `state.mode`** (no JS re-derivation); **versioned `SAVE_DAY` envelope** (schemaVersion + saveId + baseHash) emitted via the verified `sendPrompt` channel; save is a **field-level patch onto the latest note with conflict detection** (Claude's save-handler contract, Phase 3); **local-draft durability + dirty indicator**; **positional Top-3 slots never compacted**. Source split: tested `cowork-artifact/cowork-logic.js` (Node-from-pytest) inlined into `cowork-artifact/cowork-dashboard.jsx` with a drift-guard test. Four modes routed; Command Center fully laid out; the other three stubbed (2.2/2.4/2.5). Still needs real-cowork visual verification + the Phase-0-style `localStorage`-availability check (guarded with a fallback already).
- **2.2–2.6** ✅ **DONE (2026-06-21).** All four modes built TDD (plan `docs/plans/2026-06-21-cowork-dashboard-2.2-2.6.md`, suite 217 passing, preview `cowork-artifact/mockups/2.x-all-modes.html`). Corrected button/banner flow per Davo: **Morning** ends with a plain **Done** (energy picker + Top 3 confirm) → **Command Center** (active) shows **Save progress** + **Close Day** and the closing "type done" copy was removed from the active view → **Close Day** transitions (`phase: closing`) into the **Evening Coach Cards** (stats recap + reflection + gratitude + evening energy + **Done**) → `status: closed` → **Results** (read-only, both energies). Interaction logic (cycleProgress, toggleDisposition, dayStats, transition) lives tested in `cowork-logic.js`; `TaskRow` gained tap-disc-to-cycle-progress + done/delete disposition controls (reversible, mutually exclusive). Root `save(stateArg)` takes explicit post-transition state (fixes a stale-snapshot write). Still: per-item add/edit text inputs and Vitality/Daily-Insight capture are minimal (the panels render; richer inline editing can come with Phase 3 wiring), and the whole thing still needs real-cowork visual + interaction verification.
  - **2.2** Morning Coach Cards — energy + Top 3 confirm + Done. ✓
  - **2.3** Command Center — Top 3/Bonus/Unplanned rows with progress discs, habits + streaks, Save progress + Close Day. ✓
  - **2.4** Evening Coach Cards — stats + reflection + gratitude + evening energy + Done. ✓
  - **2.5** Results — read-only summary incl. both energies. ✓
  - **2.6** Disposition model — done/deleted mutually exclusive + reversible, progress independent. ✓

## Phase 3 — Skill integration (surface-detected)

> **Save channel (resolved Phase 0.2, O2):** the artifact hands state back via **`sendPrompt(text)`** — it posts a *visible user message* into the thread (e.g. `SAVE_COUNTER {...}` / `SAVE_DAY {...}`), which Claude parses and writes in one turn. NOT a silent callback; NOT `window.claude.complete()`; NOT `postMessage`. Every save is a real chat turn → batched/explicit saves are mandatory, not optional.

**✅ PHASE 3 COMPLETE (2026-06-24).** All five items below shipped on `pp-cowork-companion`. The save handler is canonical, tested Python (`companion/parsers.py:apply_save_day` + `compute_note_hash`, 38 tests in `test_save_day.py`); the surface branches + Cowork surface sections are in `open-day`/`close-day` SKILL.md; the artifact is bundled into both skill folders with a drift guard. Full suite 262 green. Codex-reviewed — two real save-handler bugs found and fixed (habits-wipe when no name map; explicit-clear not persisted). **Key finding:** `baseHash` has a SINGLE hasher (`compute_note_hash`) — the artifact only echoes it, so there's no JS↔Python hashing boundary (the planned "hash parity test" was unnecessary; the prose instead tells cowork-Claude to compute baseHash the same way at seed time). Remaining before ship: real-cowork E2E verification (Phase 4.1) — ZIPs built for that test.

- **3.1 Surface detection + branch order (absorbs weak-spot #3).** Add a Desktop branch to `open-day`/`close-day`. **Order matters:** check the artifact/Desktop branch *before* the CLI-binary-then-chat-fallback path — otherwise (post the 2026-06 default-ON flip) a cowork user resolves the CLI binary → fails → lands in the **degraded chat fallback** instead of the artifact. Until O1 (a reliable Desktop-vs-CLI signal) is solved, the **interim cowork behavior IS the chat fallback**, and the explicit `open day cowork` override + `companion_surface` in builder-profile.md force the artifact. Reconcile `companion_surface` (cli|cowork|auto) with the new `visual_mode` semantics explicitly: `visual_mode` governs CLI companion on/off; `companion_surface` governs *which* surface; document the interaction so they don't contradict. **Note:** the existing graceful-fallback clause in open-day/close-day already names "Claude Desktop / cowork" as a surface that can't run the local server and falls back to chat — that clause is the exact seam the Desktop artifact branch plugs into (replace "fall back to chat" with "render the artifact" once O2's `sendPrompt` save path is wired).
- **3.2 open-day (Desktop): data collection is RE-IMPLEMENTED per surface, not shared (corrects weak-spot #1).** The spec's "shared ritual logic" overstates it: CLI collects via gcalcli/gh/bash; cowork must collect via MCP connectors. This is the biggest chunk of open-day, not a one-liner. **Enumerate every open-day data source and its cowork status before building** — for each: has-MCP-equivalent / degrades-gracefully / silently-drops. Known sources to map (non-exhaustive — audit the live skill): Google Calendar (MCP ✓), Asana (MCP ✓), Slack (MCP ✓), Gmail (MCP ✓), **GitHub PRs** (MCP? — confirm), **Familiar screen stills** (filesystem read of stills paths — needs MCP filesystem mount, NOT a connector), **SLT/Airtable actions** (MCP ✓ but gated on `slt_member`), **overdue items / free-time calc** (derived from Calendar+Asana — re-derive in the skill, no bash), **learning** (filesystem read). Anything without a cowork path must be explicitly marked dropped, not silently omitted. Then: write the note with `status: planning` + empty Top 3 + seeded AI suggestions, render the artifact, wait for "Lock in" (which `sendPrompt`s `SAVE_DAY` → Claude writes Top 3/energy, sets `status: active`).
- **3.2a Date + path resolution must be surface-neutral (new — covers weak-spot #2).** The skills resolve "today" via `date +%Y-%m-%d` and paths via `$OBSIDIAN_VAULT_PATH`/`$HOME` — all bash-shaped, none of which exist in cowork. On the Desktop branch: **date comes from model context** (the session date), **paths come from the MCP filesystem mount root** (the vault mount), not env vars. Add an explicit work item to make date/path resolution branch on surface so the Desktop path never shells out for them.
- **3.3** close-day (Desktop): render evening Coach Cards, on Done (`sendPrompt`s `SAVE_DAY` close payload) reconcile habits into log.md (MAX-merge, unchanged), set `status: closed`, seed tomorrow's AI suggestions. Same data-collection caveat as 3.2 applies to close-day's seven sources (Fathom, Familiar, sent email, sent Slack, Claude sessions, Calendar, Asana) — enumerate cowork coverage.
- **3.4** Habit reconciliation parity: confirm the Desktop write path produces the same log.md the CLI path does.

**Branch drift — ✅ RESOLVED (2026-06-21).** Merged `pp-cli-visual` into `pp-cowork-companion`: default-ON visual companion + graceful chat fallback + Windows support + concurrent-write fix are now on our branch alongside the Phase 1 work. One conflict (`lock_in` in server.py) resolved keeping both the status-write and the utf-8 encoding. Upstream's new server-side auto-scaffold now also carries `status: planning` (TDD'd). Suite: 186 passing.

## Phase 4 — Verify & ship

- **4.1** End-to-end in a real Desktop session: open-day → artifact populates → lock in → file written with `status: active` → tick habits → close-day → reflection → `status: closed` → tomorrow seeded.
- **4.2** Cross-surface test: plan a day in cowork, open it in the CLI/web companion (and vice versa) — confirm identical interpretation.
- **4.3** Token-cost sanity: count Claude turns for a full day's interactions; confirm batched saves keep it reasonable.
- **4.4** Docs: `docs/cowork-companion-quickstart.md` (MCP config, how to invoke, how save works).

## Phase 5 — Builder unblock (the `~/.claude/` permission trap)

Background: the VS Code extension forces a permission prompt on *every* edit to any path under `~/.claude/` (an over-broad config-protection guardrail outside the permission-mode system — GitHub #15921 / #66525 / #37253). Since the toolkit installs to `~/.claude/local-plugins/nsls-personal-toolkit/`, any builder who tries to *edit their own toolkit* in the VS Code extension hits a wall of prompts. We sidestepped it this build with a git worktree at `~/dev/nsls-personal-toolkit-cowork`. Builders need that escape hatch packaged.

- **5.1 `unblock` skill (✅ built 2026-06-17).** Detects the symptom — builder editing toolkit files under `~/.claude/` in the VS Code extension and hitting repeated permission prompts — and offers a fix: set up a git worktree (or a clone + symlink) outside `~/.claude/` so edits land on a non-protected path while the plugin still loads from `~/.claude/local-plugins/`. Skill at `skills/unblock/SKILL.md`.
- **5.2 Structural install fix (recommended, not yet done).** Change the toolkit installer so the repo is cloned to `~/dev/nsls-personal-toolkit/` (or similar non-protected path) and **symlinked** into `~/.claude/local-plugins/` — so the source of truth a builder edits is never under `~/.claude/` in the first place, and nobody hits the trap. The `unblock` skill is the remediation for builders already in the bad state; 5.2 is the prevention for new installs. Track against the installer (`install.sh` / Builder Toolkit `/setup`).

## Explicitly out of scope (this plan)

Week rituals in the artifact; onboarding wizard; `/schedule` pre-fetch; `/log` / `/person-intelligence` / `/learn` / `/self-insight` views; mobile. All Phase 2 of the product (a later plan).

## Risk register

- **Write-back cost.** Per-save Claude turn. Mitigation: batched saves, designed save moments. Verify in 4.3.
- **Surface detection reliability.** If we can't find a clean signal, fall back to explicit `open day cowork`. Acceptable for v1.
- **Two companions, one vault, drift.** Mitigation: the identical contract + the cross-surface test (4.2). The `status` frontmatter must be respected by both.
- **Streak rule triple-source.** Mitigation: Python canonical, JS display-only, parity test in CI.
- **Cowork file-delete is permission-gated (verified 2026-06-21).** In a real Cowork session, Write/Read are frictionless but `rm` fails the first time ("Operation not permitted") and requires a one-time per-folder grant (`allow_cowork_file_delete`). Mitigation: the save path must be **whole-file replace** (already the contract, item O4) — never delete-then-recreate. Don't put a delete in any save flow.
- **No live bridge from the worktree to Cowork (verified 2026-06-21).** Cowork loads skills only from installed marketplace plugins or ZIP uploads (Customize → Skills), from a read-only snapshot store separate from Claude Code's registry. Mitigation/dev loop: iterate logic in Claude Code; ZIP the skill folder + upload to Cowork at checkpoints; fresh session to test. Ship via a Cowork marketplace plugin. See `docs/cowork/project-instructions.md`.

## Recent learnings (2026-06-14) — fold these into the build

Hard-won from dogfeeding the CLI/web companion after this plan was first written. Several **validate** the artifact model; a few add **new requirements**.

1. **Form state must never re-render mid-edit (validates principle #2).** The CLI plan form re-rendered the entire form on every field `change` (htmx `hx-swap=outerHTML`). Result: tabbing into a field and typing destroyed its DOM node ("text disappeared"), and a value typed in Top-3 slot 3 jumped to an earlier slot because the priorities list was **compacted** (empty slots dropped). Fixes that the artifact gets for free if it holds state: (a) **positional slots** — index *i* always maps to slot *i*, never compact empties; (b) save **without** re-rendering the inputs. The artifact must keep all three Top-3 slots and the bonus rows as controlled, positional inputs. Do NOT rebuild the input list from a filtered/compacted array.

2. **Continuous entry for list fields (new requirement).** When adding bonus items, Enter/Tab must keep focus on the *next/empty* field so the user types item after item — never dump focus onto a "Reset/Done" button. Trivial with controlled React inputs; just don't lose it on re-render.

3. **Orient the user at the TOP, and make the closing pass distinct (new requirement).** Users don't scroll to find "what next." The Command Center now shows a **top banner** on the morning/midday entry: *"Good job — type done to complete; come back any time to mark progress."* When **close-day** sends the user in for the end-of-day pass, that banner is replaced by a **bottom line**: *"Good job — type done to close your day."* The CLI signals this with `?closing=1`; cowork should carry an equivalent **entry-context flag** (e.g. `phase: 'planning' | 'active' | 'closing'`) into the artifact so it knows whether this is the plan-confirm, mark-progress, or close pass. Don't bury the call-to-action.

4. **Two-energy model, asymmetric visibility (refines 2.3).** Morning energy shows on the active Command Center (editable). **Evening energy is hidden** there until it's been captured — it belongs to the closing pass. Mirror this: morning energy on the active view, evening energy only in the closing/evening cards + results.

5. **`status` frontmatter — ✅ now shipped (2026-06-17, plan item 1.3).** The CLI/web companion's `_detect_day_state` now *prefers* `status: planning|active|closed` and only falls back to the old inference (+`?mode=`/`?closing=` overrides still work) when status is absent. The lifecycle is written explicitly by the companion (`/lock-in`, `/reset-plan`) and the skills (open-day, close-day, reset-day). Both surfaces now read one clean signal instead of inferring from section presence.

6. **Dependency/runtime gotchas that bit the CLI (mostly moot for the artifact, noted so they're not re-learned):**
   - The web companion loaded htmx/Alpine from a CDN; a blocked CDN left every button dead and was invisible in testing because the dev sandbox *could* reach the CDN. Lesson for cowork: **verify in a real Claude Desktop session**, not a simulated/headless proxy — "works in my environment" ≠ "works in the user's." The artifact runtime bundles React/Tailwind, so the CDN class of bug is gone, but the *verification discipline* carries over (see 4.1).
   - The CLI's `tailwind.css` was a hand-written minimal subset, so undefined utility classes silently no-op'd. The artifact runtime ships full Tailwind — this gotcha disappears; don't port the minimal stylesheet.
   - Server ran with template caching → "stale server" confusion on every edit. The artifact has no server; this whole class of pain is gone (validates principle #2). 

7. **Reset-first path (new requirement).** The CLI added `open day -r` → run `/reset-day` (full clear of today's note) before opening, combinable as `open day -v -r`. Cowork's open-day branch should support the same reset-first flag so a botched plan can be redone cleanly.

8. **Disposition + progress are independent and reversible (confirms 2.6, adds detail).** Per-task progress is 0/25/50/75/100 stored as hidden `<!--p:NN-->` markers; delete is a *reversible mark* (moves text to `### Deleted`, keeps the row), and an item can carry a % AND be marked for deletion. Anything <100% auto-carries at close-day (no explicit "carry" control). Port these exact semantics.
