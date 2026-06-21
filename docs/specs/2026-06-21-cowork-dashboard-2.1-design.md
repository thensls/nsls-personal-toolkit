# Cowork Dashboard 2.1 — Skeleton Design Spec

**Date:** 2026-06-21
**Author:** Davo Wood (with Claude); architecture cross-reviewed by OpenAI Codex (gpt-5.5)
**Parent spec:** `docs/specs/2026-06-13-cowork-companion-design.md`
**Build plan item:** Phase 2.1 (`docs/plans/cowork-companion-build-plan.md`)
**Status:** Approved direction (visual + architecture); ready for implementation plan.

## Summary

Phase 2.1 is the **skeleton** of the `cowork-dashboard` React artifact: a single self-contained
`.jsx` cowork renders inline, that takes a JSON state blob, routes to one of four modes off a
Claude-resolved `mode`, holds edit state locally, and on an explicit Save hands a versioned
payload back to Claude via `sendPrompt` for a conflict-aware whole-file write. 2.1 ships a **thin
shell + all four modes stubbed** against a hardcoded realistic sample; modes 2.2–2.6 flesh each out.

This spec covers the skeleton only. It locks: the visual language, the JSON state contract, the
mode-routing source of truth, the `SAVE_DAY` protocol, the conflict/draft model, and the
source-file + testing structure.

## Visual language (approved via mockups)

**Direction: "Cockpit, portrait."** A navy (`#18315A`) frame containing white panels, sized for
cowork's narrow right-side panel (single column, ~portrait, target ~420px content width — must not
assume a wide canvas).

NSLS brand tokens (exact):

| token | hex | role |
|---|---|---|
| navy | `#18315A` | frame, the "today" anchor, primary headers |
| bluegray | `#33475B` | primary body text |
| darkblue | `#425B76` | secondary / muted text |
| teal | `#0091AE` | the ONE action accent — primary buttons, in-progress fill, links |
| gold | `#EEB117` | honor-society accent — done state, streak flames, accomplishment (used sparingly) |
| lightblue | `#E5F5F8` | soft section backgrounds, info banners |
| white | `#FFFFFF` | panel surface |
| nearblack | `#191919` | task titles |

**Progress discs (the signature element):** a small **solid filled disc** per task — NOT a hollow
ring. States: not-started = solid light-gray disc; partial = solid disc filled by a teal
conic-gradient sweep (0/25/50/75); full = solid teal disc; done = solid gold disc. Tapping cycles
progress. A **deleted** item (disposition `deleted`) keeps its row but renders muted/struck-through
with a restore affordance — delete is a reversible mark, not a removal (it can still carry a %); it
does not get its own disc color, it desaturates the row.

**Type:** Lexend Deca for headings with a system fallback stack (`-apple-system, system-ui, "Segoe
UI", sans-serif`). **Constraint:** artifact runtimes block external font CDNs, so Lexend can't be
`@import`ed — it renders if locally present, otherwise the system fallback carries; color + spacing
+ hierarchy carry the brand regardless.

**Composition:** stacked panels in one column — header (date + tiny `Energy · High` stat + status
pill) → context banner → Top 3 → Bonus/unplanned → Habits (compact streak chips) → action bar →
reassurance line. Cards only where the card is the interaction (a task row, a habit chip).

Reference mockups: `cowork-artifact/mockups/command-center-cockpit-portrait.html`,
`cowork-artifact/mockups/2.1-command-center-built.html`.

### Flow & per-mode controls (corrected 2026-06-21 — the "type done" instruction was leaking
into the active state)

The closing instruction belongs ONLY to the closing pass, never to the active Command Center.
"Close Day" is the explicit user action that transitions active → closing. The `phase` field
drives the banner + buttons:

| Mode (phase) | Banner | Buttons | On action |
|---|---|---|---|
| `coach-morning` (planning) | greet + "set your plan" | **Done** | write plan, `status: active`, → Command Center |
| `command` (active) | "Good job — mark progress any time." (NO "type done") | **Save progress** (primary) · **Close Day** (secondary) | Save progress → batch-write to vault, stay in day. Close Day → enter Evening Coach Cards |
| `coach-evening` (closing, entered via Close Day) | "Closing the day — finish, then Done." | **Done** (after the guided steps) | write reflection/gratitude/evening-energy, `status: closed`, → Results |
| `results` (closed) | read-only summary | — (optionally "Reopen") | — |

- **Close Day** sets `phase: closing` and renders the Evening Coach Cards (stats recap →
  Insight Reflection → Gratitude → evening energy → Done). It is the staged close, not an
  instant write — the guided reflection is the point of the ritual.
- The active Command Center never shows "type done to close." Its only closing affordance is the
  **Close Day** button.

## Architecture

### Source structure (Codex fix #1 — testable without a build step)

Two files, no build/bundler step (cowork renders the artifact as-is):

- **`cowork-artifact/cowork-logic.js`** — plain JS (NO JSX). All framework-free, unit-testable
  logic: `serializeForSave(state)`, payload/envelope construction, any client-side fallback
  helpers, and re-export of the streak display fns. Dual CommonJS + `window` export, exactly like
  the existing `streak.js`. **Node tests import this directly.**
- **`cowork-artifact/cowork-dashboard.jsx`** — the single self-contained artifact. Inlines (copies)
  the logic from `cowork-logic.js` at the top so the shipped artifact needs no imports, then defines
  presentational components and the four mode components, and the root.

> Rationale: Codex flagged that authoring everything in one `.jsx` blocks Node testing (Node can't
> `require` JSX). We reject adding a JS toolchain (cowork uses no build output; the repo has none).
> Instead we mirror the proven `streak.js` + parity-test pattern: logic in a tested `.js`, the
> artifact inlines it. A small **drift guard test** asserts the inlined copy in the `.jsx` matches
> `cowork-logic.js` (string-compare the delimited block), so the copy can't silently rot.

### Component shape

```
cowork-dashboard.jsx
├─ [inlined from cowork-logic.js]  serializeForSave, buildSaveEnvelope, streak display
├─ presentational: <Disc> <TaskRow> <Panel> <HabitChip> <Header> <Banner> <SaveBar>
├─ modes (stubbed in 2.1): <MorningCoachCards> <CommandCenter> <EveningCoachCards> <Results>
└─ <CoworkDashboard state={SAMPLE}>  — routes on state.mode, holds edit state, owns Save
```

### Mode routing — Python is the source of truth (Codex fix #2, the big one)

The artifact does **NOT** re-derive the mode. `_detect_day_state` in Python already needs the note
sections and Top-3 (e.g. `status: active` + `## Insight Reflection` present → `coach-evening`), so a
JS `deriveMode(status, phase)` could never mirror it and would silently drift.

**Claude resolves the mode in Python and passes `state.mode`** (one of `coach-morning | command |
coach-evening | results`) into the artifact, alongside `status`, `phase`, and display flags. The
root component routes purely on `state.mode`. No mode logic lives in JS. (If a defensive fallback is
ever needed, it would be a clearly-labeled last resort tested against Python fixtures — not in 2.1.)

This also removes the spec's earlier self-contradiction ("status is authoritative" vs. Python
peeking at section presence): the contradiction lived in trying to recompute mode in two places;
resolving it once in Python ends it.

### JSON state contract (the blob Claude seeds → artifact renders → artifact emits)

Locked now (full contract up front). In 2.1 this is a hardcoded `SAMPLE` constant; Phase 3 wires
Claude's Python parse to produce it.

```jsonc
{
  "schemaVersion": 1,
  "date": "2026-06-17",                 // ISO; the note this maps to
  "notePath": "01-daily/2026-06-17.md",
  "baseHash": "<sha256-16 of the note Claude read>",  // for conflict detection on save
  "mode": "command",                    // RESOLVED BY PYTHON — coach-morning|command|coach-evening|results
  "status": "active",                   // planning|active|closed (for display + the banner)
  "phase": "active",                    // planning|active|closing — entry context for banners
  "todayPretty": "Wednesday, June 17",

  "top3": [                             // POSITIONAL — exactly 3 slots, never compacted; empty slots kept
    { "slot": 0, "text": "Finish the toolkit spec", "project": "Toolkit", "weekRank": 1,
      "progress": 75, "disposition": "active" },   // disposition: active|done|deleted|deferred
    { "slot": 1, "text": "Q3 LOP draft", "project": "Growth", "weekRank": 2,
      "progress": 25, "disposition": "active" },
    { "slot": 2, "text": "Reply to vendor", "project": null, "weekRank": null,
      "progress": 100, "disposition": "done" }
  ],
  "bonus":     [ { "text": "Review Red's PR", "progress": 0, "disposition": "active" } ],
  "unplanned": [ { "text": "Unblocked the cowork build", "progress": 100, "disposition": "done" } ],

  "habits": [                           // streak/percent computed by Python from log.md (canonical)
    { "id": "walk",    "name": "Walk",     "emoji": "🚶", "percent": 1.0, "streakDays": 12, "status": "ok" },
    { "id": "read15",  "name": "Read 15m", "emoji": "📖", "percent": 1.0, "streakDays": 5,  "status": "ok" },
    { "id": "workout", "name": "Workout",  "emoji": "💪", "percent": 0.0, "streakDays": 0,  "status": "ok" }
  ],

  "energy": { "morning": "High", "evening": null },  // evening null until the close pass
  "gratitude": "",
  "dailyInsight": "",                   // Command Center quick capture
  "insightReflection": ""               // close-day reflection (evening modes)
}
```

Disposition is mutually exclusive per item (done | deleted | deferred | active), and `progress` is
independent of disposition — an item can carry a % and be marked deleted (port of the CLI semantics).
`<100%` auto-carries at close (handled by close-day, not the artifact).

### Save protocol — `SAVE_DAY` versioned envelope (Codex fix #3)

On explicit Save, the artifact builds an envelope and calls
`sendPrompt("SAVE_DAY " + JSON.stringify(envelope))`. The envelope:

```jsonc
{
  "type": "SAVE_DAY",
  "schemaVersion": 1,
  "saveId": "<nonce>",          // idempotency: Claude ignores a duplicate saveId
  "date": "2026-06-17",
  "notePath": "01-daily/2026-06-17.md",
  "baseHash": "<the hash the artifact was seeded with>",   // conflict detection
  "changes": {                  // ONLY the fields the user edited (field-level patch)
    "top3": [ /* full positional array incl empty slots — never compacted */ ],
    "bonus": [...], "unplanned": [...],
    "habits": [ {"id":"walk","percent":1.0}, ... ],
    "energy": {"morning":"High"},
    "gratitude": "...", "dailyInsight": "...",
    "statusTransition": null    // or "active"/"closed" when a lock-in/close happened
  }
}
```

**Claude's save handler (the prompt contract, Phase 3 — specified here so the artifact and the skill
agree):**
1. Parse the `SAVE_DAY` JSON. **Malformed or schemaVersion-mismatch → refuse to write, tell the user.**
2. Idempotency: if this `saveId` was already applied this session, no-op.
3. **Re-read the LATEST note from disk** (not the artifact's stale snapshot). Compute its hash.
4. If latest hash == `baseHash` → apply `changes` as a field-level patch and whole-file write.
5. If latest hash != `baseHash` (someone — CLI, close-day, manual edit — touched it since): apply the
   field-level patch onto the *latest* content (only the fields in `changes`), preserving every
   section/field the artifact didn't touch. If a touched field genuinely conflicts, stop and surface
   it rather than clobber. **Never write the artifact's whole stale snapshot over the file.**

This turns "whole-file replace, last-writer-wins" into "field-level patch onto latest, with conflict
detection" — closing the lost-update trap Codex flagged (a morning artifact must not overwrite a
close-day section written hours later). Delete is never used (cowork gates `rm`); writes are replace-in-place.

### Local draft durability (Codex fix #4)

React state alone is too fragile for a note open all day (the artifact can unmount, re-render, or be
regenerated; the chat can scroll away). The artifact persists a **local draft** keyed by
`date + baseHash` (e.g. `localStorage`, if available in the artifact runtime — to be verified; else
an in-memory ref that survives re-render). This is local-only and sends **no** chat turns — it is NOT
the forbidden autosave (only chat/vault writes are forbidden ambient). On mount, if a draft for the
same `date + baseHash` exists, offer to restore it. A visible **dirty / saved** indicator shows
whether local edits have been committed to the vault.

> 2.1 scope note: the skeleton wires the draft *mechanism* and the dirty indicator; full restore-UX
> polish can land with the modes. Verifying `localStorage` availability in the cowork artifact runtime
> is an explicit Phase 0-style check before relying on it (fallback: in-memory ref).

### Testing

- **`cowork-logic.js`** logic (`serializeForSave`, envelope construction, positional-slot
  preservation, streak display) — Node tests, run from pytest the same way the streak parity test
  already shells Node. Assert: empty Top-3 slots survive serialization (anti-compaction); a done+%
  item serializes both; envelope carries schemaVersion/saveId/baseHash.
- **Drift guard** — a test asserting the inlined logic block in `cowork-dashboard.jsx` matches
  `cowork-logic.js` verbatim (so the copy can't rot).
- **React components** — verified by eyeball in a real cowork session (the spec's verification
  discipline: works-in-cowork, not works-in-a-simulator). No React test runner added.

## Scope (2.1) and non-goals

**In 2.1:** the two source files; the JSON contract + hardcoded `SAMPLE`; mode routing on
`state.mode`; the four modes as minimal stubs (each renders its name, the relevant slice of state,
and the shared chrome); the `<Disc>`/`<TaskRow>`/`<Panel>`/`<HabitChip>` primitives styled to the
cockpit-portrait language; the `SAVE_DAY` envelope construction + a Save button that emits it; the
local-draft mechanism + dirty indicator; the logic tests + drift guard.

**Not in 2.1 (later phases):** the full interaction detail of each mode (2.2–2.6); the Phase-3 skill
wiring that produces the real state blob and implements Claude's save handler; the
`localStorage`-availability verification (flagged, done before relying on it). Week rituals,
onboarding, scheduling — out of the whole plan.

## What changed from the pre-review architecture (Codex-driven)

1. Mode is **resolved in Python and passed in** as `state.mode`; the artifact does not re-derive it
   (was: JS `deriveMode` mirroring Python — impossible without the note body).
2. `SAVE_DAY` is a **versioned envelope** with `saveId` (idempotent), `baseHash` (conflict), strict
   validation (malformed → no write) — was: bare `"SAVE_DAY " + JSON`.
3. Save is a **field-level patch onto the latest note with conflict detection** — was: whole-file
   replace, last-writer-wins.
4. **Local draft durability** + dirty/saved indicator added — was: React state only.
5. Save payload **preserves positional slot indexes incl. empties** — closes the contradiction with
   the never-compact rule.
6. Logic lives in a **separate tested `cowork-logic.js`**, inlined into the artifact with a drift
   guard — satisfies Node-testability without a build step.
