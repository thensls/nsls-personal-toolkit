# Handoff Prompt — Build the Cowork Companion (daily core)

Paste this into a fresh Claude session (Claude Code, in the toolkit repo).

---

You're building the **cowork companion** for the NSLS personal productivity toolkit — a Claude Desktop (cowork) React-artifact version of the visual companion. A CLI/web companion already exists and works (Flask app at `companion/`); you are NOT replacing it. You're adding a second rendering surface over the same Obsidian vault.

**Read these first, in order:**
1. `docs/specs/2026-06-13-cowork-companion-design.md` — the design spec (architecture, lessons learned, data contract, open questions).
2. `docs/plans/cowork-companion-build-plan.md` — the phased build plan. Follow its phases. **Read the "Recent learnings (2026-06-14)" section at the end carefully** — it captures fixes made after the plan was first written and several are new requirements.
3. `docs/specs/2026-05-16-cli-companion-webapp-design.md` — the CLI companion spec (the surface you're mirroring).
4. `companion/parsers.py`, `companion/server.py`, `companion/streak.py` — the working CLI companion. This is your contract reference. The cowork artifact must read/write the **identical** markdown sections. In `server.py`, study the **plan-form routes** (`set_top_3`, `set_bonus`, `delete_bonus`, `_build_plan_context`, `_render_bonus_list`) and the **Command Center messaging** in `templates/day.html` — they encode hard-won UX fixes (below).
5. `skills/open-day/SKILL.md` and `skills/close-day/SKILL.md` — especially the "Visual Companion Mode" / surface branch, the `-r` reset-first flag, the `?closing=1` close-day entry, and "Output Discipline".

**Non-negotiable constraints (these came from painful CLI lessons — do not relitigate them):**
- **Identical markdown contract.** Same sections: Morning Check-in (Energy, AI Suggested Top 3/Delegate, My Top 3, Bonus, Unplanned, Done/Deleted/Deferred, Vitality, Habits), Daily Insight, Gratitude, Insight Reflection, End of Day (Energy), plus habits.md / log.md. A day planned in cowork must open cleanly in the CLI companion and vice versa.
- **Explicit mode via `status:` frontmatter** (`planning|active|closed`). NEVER infer mode from which sections are present — that exact bug flipped the CLI Command Center into read-only mid-day.
- **Two energy captures**, not one: morning energy in `## Morning Check-in`, evening energy in `## End of Day`. Don't conflate or duplicate.
- **Mutually-exclusive dispositions:** Done / Deleted / Deferred are separate sections; selecting one moves the item, never co-checks. (Legacy `### Dismissed` reads as Done.)
- **State lives in the artifact; write back ONCE on explicit save.** No autosave, no live-reload. Every write costs a Claude turn — design around discrete "Lock in" / "Save" moments. This is the whole reason the artifact model beats the Flask model; do not recreate SSE/server/PID complexity.
- **One canonical streak rule.** `companion/streak.py` (Python) stays canonical. The artifact gets a JS display copy guarded by a parity test over the six canonical sequences. No Streak Engine MCP.
- **log.md is canonical for habits**, MAX-merge in close-day unchanged.
- **One skill per ritual, surface-detected.** Do not fork open-day into a separate cowork skill. Add a surface-detection branch beside the existing `visual_mode` logic.

**UX non-negotiables (learned the hard way on the CLI form — see plan §"Recent learnings"):**
- **Positional slots, never compacted.** Top-3 has exactly 3 slots; slot *i* ↔ index *i* always. Never rebuild the input list from a filtered array — a value typed in slot 3 must not jump to slot 1. (This bug cost real trust.)
- **Never re-render an input while it's being edited.** Hold form state in the artifact and write once on save. (The artifact model gives this for free — don't defeat it with mid-edit re-renders.)
- **Continuous list entry.** Adding bonus items: Enter/Tab keeps focus on the next/empty field, never on a button. The user types item after item.
- **Orient at the top; distinguish the closing pass.** On the planning/active entry, the Command Center shows a TOP banner ("Good job — type done to complete; come back any time to mark progress"). On the close-day entry it shows a BOTTOM "type done to close your day" line instead. Carry an **entry-context flag** (`phase: planning|active|closing`) into the artifact — the CLI uses `?closing=1`. Don't bury the call-to-action where users won't scroll.
- **Evening energy is hidden on the active view** — it only appears in the closing/evening pass and results. Morning energy shows (editable) on the active Command Center.
- **Progress + delete are independent and reversible.** Per-task progress 0/25/50/75/100; delete marks the row (reversible, moves text to `### Deleted`) without removing it; an item can be both partial and marked-for-delete; anything <100% auto-carries at close (no explicit carry control).

**Scope for THIS build (daily core only):** open-day + close-day + Command Center + habits/streaks, as the `cowork-dashboard` artifact. Week rituals, onboarding wizard, /schedule pre-fetch, and the other skill views are Phase 2 — do not build them.

**Start with Phase 0 (de-risk) before any UI:**
1. Find the reliable signal that distinguishes Claude Desktop from Claude Code (spec open question O1). Until confirmed, gate on an explicit `open day cowork` override + `companion_surface` in builder-profile.md.
2. Prove the artifact→Claude→vault write-back round-trip with a trivial artifact (a counter that saves to a scratch file via MCP filesystem) BEFORE building the real dashboard (O2).
3. Confirm the MCP filesystem mount can read+write the vault, and the write granularity (O4 — recommend whole-file replace after re-parse).

**Do not proceed to the artifact UI until the write-back round-trip works.**

**Preferred data flow:** the skill parses the daily note in Python (reuse `companion/parsers.py` behavior) and seeds the artifact with a clean JSON blob; the artifact renders JSON and emits JSON on save; Claude applies the diffs and writes the whole file back. This avoids a second markdown parser in JavaScript — only the streak display math is shared logic.

**Verification discipline (learned the hard way):** a blocked CDN once left every button dead and it was invisible in testing because the dev sandbox could reach the CDN — "works in my environment" ≠ "works for the user." **Verify in a real Claude Desktop session**, not a simulated proxy, before calling anything done (plan 4.1).

**Working agreement:** ask me clarifying questions before building if anything in the spec/plan is ambiguous. Commit as you go on a `pp-`-prefixed feature branch; pushing that branch to origin is fine, but do NOT open a PR, merge, or share anything (Slack/docs/links) without my explicit per-action go-ahead. Run the existing companion test suite (`companion/tests/`, currently 146 tests) after any change that touches shared Python — it must stay green, and add tests for new shared logic.
