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

These are the open questions from the spec. Resolve them in a throwaway Desktop session; they gate everything.

- **0.1 Surface detection (O1).** Find a reliable signal distinguishing Claude Desktop from Claude Code. Document it. Until then, the skill uses the explicit `open day cowork` override + `companion_surface` in builder-profile.md.
- **0.2 Artifact ↔ Claude write-back (O2).** Build the thinnest possible artifact that holds a counter and, on a button press, hands its state back to Claude, who writes it to a scratch file via MCP filesystem. Prove the round-trip end to end before building the real UI.
- **0.3 MCP filesystem mount (claude_desktop_config.json).** Confirm the vault + Familiar paths are readable/writable from a Desktop session. Confirm write granularity (whole-file replace — O4).

**Gate:** do not proceed to Phase 2 until the write-back round-trip works.

## Phase 1 — Shared core (reuse, don't rewrite)

- **1.1** Reuse `companion/parsers.py` logic as the contract reference. The artifact needs JS parsers for the same sections; port the *behavior*, and add a test that feeds the same fixtures to both and asserts equal output. (Or: have the skill do the parsing in Python and seed the artifact with clean JSON — preferred, avoids a second parser. See 2.1.)
- **1.2** Streak rule: keep `companion/streak.py` canonical. Write `streak.js` (display copy). Add a parity test (O3) over the six canonical sequences.
- **1.3** Add `status` frontmatter to the daily-note contract: `planning | active | closed`. Update the CLI companion's `_detect_day_state` to *prefer* `status` when present (backward compatible — fall back to current inference if absent). This benefits both companions and kills the presence-inference fragility.

## Phase 2 — The artifact (daily core)

Prefer **Claude parses, artifact renders**: the skill reads the daily note in Python/MCP, hands the artifact a clean JSON blob (Top 3, Bonus, Unplanned, dispositions, habits+streaks, both energies, mode). The artifact never parses markdown — it just renders JSON and emits JSON on save. This avoids a second markdown parser in JS (only the streak display math is shared logic).

- **2.1** `cowork-dashboard` artifact skeleton: accepts a JSON state prop, renders the four modes off `status`. Tailwind styling matching the CLI companion's aesthetic.
- **2.2** Morning Coach Cards: greet + morning energy → confirm Top 3 (seeded from AI suggestions) → Bonus → habit intentions → vitality → "Lock in". Emits state; Claude writes Top 3 + morning energy, sets `status: active`.
- **2.3** Command Center: Top 3 checklist, Bonus, Unplanned wins (add/edit/delete), Habits row (streak indicator + tap), Vitality, read-only morning energy, Daily Insight quick capture. Batched save.
- **2.4** Evening Coach Cards: stats recap → Insight Reflection → Gratitude → evening energy → Done. Emits state; Claude writes those sections + evening energy, sets `status: closed`.
- **2.5** Evening Results: read-only day summary including both energy values.
- **2.6** Disposition model in the suggestion list: Top 3 / Bonus / Defer / Done / Delete, mutually exclusive (port the CLI semantics exactly — done/deleted/deferred move, don't co-check).

## Phase 3 — Skill integration (surface-detected)

- **3.1** Add the surface-detection branch to `open-day` and `close-day` (beside `visual_mode`). CLI → existing Flask flow; Desktop → render the artifact + write-back protocol.
- **3.2** open-day (Desktop): collect data via MCP connectors (quiet — one summary line per source), write the daily note with `status: planning` + empty Top 3 + seeded AI suggestions, render the artifact, wait for "Lock in".
- **3.3** close-day (Desktop): render evening Coach Cards, on Done reconcile habits into log.md (MAX-merge, unchanged), set `status: closed`, seed tomorrow's AI suggestions.
- **3.4** Habit reconciliation parity: confirm the Desktop write path produces the same log.md the CLI path does.

## Phase 4 — Verify & ship

- **4.1** End-to-end in a real Desktop session: open-day → artifact populates → lock in → file written with `status: active` → tick habits → close-day → reflection → `status: closed` → tomorrow seeded.
- **4.2** Cross-surface test: plan a day in cowork, open it in the CLI/web companion (and vice versa) — confirm identical interpretation.
- **4.3** Token-cost sanity: count Claude turns for a full day's interactions; confirm batched saves keep it reasonable.
- **4.4** Docs: `docs/cowork-companion-quickstart.md` (MCP config, how to invoke, how save works).

## Explicitly out of scope (this plan)

Week rituals in the artifact; onboarding wizard; `/schedule` pre-fetch; `/log` / `/person-intelligence` / `/learn` / `/self-insight` views; mobile. All Phase 2 of the product (a later plan).

## Risk register

- **Write-back cost.** Per-save Claude turn. Mitigation: batched saves, designed save moments. Verify in 4.3.
- **Surface detection reliability.** If we can't find a clean signal, fall back to explicit `open day cowork`. Acceptable for v1.
- **Two companions, one vault, drift.** Mitigation: the identical contract + the cross-surface test (4.2). The `status` frontmatter must be respected by both.
- **Streak rule triple-source.** Mitigation: Python canonical, JS display-only, parity test in CI.

## Recent learnings (2026-06-14) — fold these into the build

Hard-won from dogfeeding the CLI/web companion after this plan was first written. Several **validate** the artifact model; a few add **new requirements**.

1. **Form state must never re-render mid-edit (validates principle #2).** The CLI plan form re-rendered the entire form on every field `change` (htmx `hx-swap=outerHTML`). Result: tabbing into a field and typing destroyed its DOM node ("text disappeared"), and a value typed in Top-3 slot 3 jumped to an earlier slot because the priorities list was **compacted** (empty slots dropped). Fixes that the artifact gets for free if it holds state: (a) **positional slots** — index *i* always maps to slot *i*, never compact empties; (b) save **without** re-rendering the inputs. The artifact must keep all three Top-3 slots and the bonus rows as controlled, positional inputs. Do NOT rebuild the input list from a filtered/compacted array.

2. **Continuous entry for list fields (new requirement).** When adding bonus items, Enter/Tab must keep focus on the *next/empty* field so the user types item after item — never dump focus onto a "Reset/Done" button. Trivial with controlled React inputs; just don't lose it on re-render.

3. **Orient the user at the TOP, and make the closing pass distinct (new requirement).** Users don't scroll to find "what next." The Command Center now shows a **top banner** on the morning/midday entry: *"Good job — type done to complete; come back any time to mark progress."* When **close-day** sends the user in for the end-of-day pass, that banner is replaced by a **bottom line**: *"Good job — type done to close your day."* The CLI signals this with `?closing=1`; cowork should carry an equivalent **entry-context flag** (e.g. `phase: 'planning' | 'active' | 'closing'`) into the artifact so it knows whether this is the plan-confirm, mark-progress, or close pass. Don't bury the call-to-action.

4. **Two-energy model, asymmetric visibility (refines 2.3).** Morning energy shows on the active Command Center (editable). **Evening energy is hidden** there until it's been captured — it belongs to the closing pass. Mirror this: morning energy on the active view, evening energy only in the closing/evening cards + results.

5. **`status` frontmatter still not shipped on the CLI side.** The CLI still infers mode via `_detect_day_state` + a `?mode=` override + the new `?closing=` flag. Plan item 1.3 (add explicit `status: planning|active|closed`) is **still the right move and still pending** — doing it as part of cowork benefits both surfaces and is the clean signal cowork needs anyway. Treat it as a prerequisite, not an afterthought.

6. **Dependency/runtime gotchas that bit the CLI (mostly moot for the artifact, noted so they're not re-learned):**
   - The web companion loaded htmx/Alpine from a CDN; a blocked CDN left every button dead and was invisible in testing because the dev sandbox *could* reach the CDN. Lesson for cowork: **verify in a real Claude Desktop session**, not a simulated/headless proxy — "works in my environment" ≠ "works in the user's." The artifact runtime bundles React/Tailwind, so the CDN class of bug is gone, but the *verification discipline* carries over (see 4.1).
   - The CLI's `tailwind.css` was a hand-written minimal subset, so undefined utility classes silently no-op'd. The artifact runtime ships full Tailwind — this gotcha disappears; don't port the minimal stylesheet.
   - Server ran with template caching → "stale server" confusion on every edit. The artifact has no server; this whole class of pain is gone (validates principle #2). 

7. **Reset-first path (new requirement).** The CLI added `open day -r` → run `/reset-day` (full clear of today's note) before opening, combinable as `open day -v -r`. Cowork's open-day branch should support the same reset-first flag so a botched plan can be redone cleanly.

8. **Disposition + progress are independent and reversible (confirms 2.6, adds detail).** Per-task progress is 0/25/50/75/100 stored as hidden `<!--p:NN-->` markers; delete is a *reversible mark* (moves text to `### Deleted`, keeps the row), and an item can carry a % AND be marked for deletion. Anything <100% auto-carries at close-day (no explicit "carry" control). Port these exact semantics.
