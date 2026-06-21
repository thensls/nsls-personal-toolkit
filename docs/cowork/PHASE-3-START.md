# Cowork Companion — Phase 3 Start (session handoff)

**You are resuming the cowork-companion build after a `/clear`.** Everything you need is on
disk; this note is the entry point. Work in the worktree at `~/dev/nsls-personal-toolkit-cowork`,
branch `pp-cowork-companion`. Don't push/share/PR without Davo's explicit per-action OK.

## Read these first (in order)

1. `docs/plans/cowork-companion-build-plan.md` — the master plan. Phase 0 + 1 + 2 are DONE; **Phase 3 is your scope** (the "Phase 3 — Skill integration" section, items 3.1 / 3.2 / 3.2a / 3.3 / 3.4). Read the "Recent learnings" + risk register too.
2. `docs/specs/2026-06-13-cowork-companion-design.md` — product spec. **O2 is RESOLVED**: the artifact→Claude save channel is `sendPrompt(text)` (a visible chat message), NOT `window.claude.complete()`.
3. `docs/specs/2026-06-21-cowork-dashboard-2.1-design.md` — the artifact design + the **`SAVE_DAY` envelope** + the **save-handler contract you implement in Phase 3** (re-read latest note, field-level patch, base-hash conflict detection, whole-file replace, never delete).
4. The built artifact: `cowork-artifact/cowork-dashboard.jsx` (+ `cowork-artifact/cowork-logic.js`, inlined with a drift-guard). The four modes + flow are done.
5. `skills/open-day/SKILL.md`, `skills/close-day/SKILL.md` — note the **graceful-fallback clause** already names "Claude Desktop / cowork" as a surface that falls back to chat. That clause is the seam: 3.1 replaces "fall back to chat" with "render the artifact + run the save handler."

## State of the world (verified at handoff, 2026-06-21)

- Branch `pp-cowork-companion`, synced with `pp-cli-visual` (default-ON companion + graceful fallback + Windows support are all in). **223 tests passing** (`~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion -q`).
- **Done:** Phase 0 (gate passed — `sendPrompt` round-trip proven in real cowork). Phase 1 (`status` frontmatter contract, `streak.js` parity). Phase 2.1–2.6 (the full artifact: Morning → Command Center → Close Day → closing review → Evening → Results, cockpit-portrait NSLS design, solid progress discs). Codex-reviewed and hardened (functional setState, insight data-loss fixed).
- **The artifact runs on a hardcoded `SAMPLE` state.** Phase 3 is what makes it REAL: the skill produces the state blob from the vault, and Claude implements the `SAVE_DAY` handler that writes it back.

## Phase 3 — what to build (the scope)

Follow the build plan's Phase 3 items. In brief:

- **3.1 Surface detection + branch order.** Add a Desktop/cowork branch to open-day & close-day. Check the artifact branch BEFORE the CLI-binary→chat-fallback path. Until O1 (a clean Desktop-vs-CLI signal) is solved, the interim is: explicit `open day cowork` override + `companion_surface` in builder-profile.md force the artifact; otherwise chat fallback. Reconcile `companion_surface` (cli|cowork|auto) with `visual_mode`.
- **3.2 open-day (Desktop) data collection — RE-IMPLEMENTED per surface (not shared).** CLI uses bash/gcalcli/gh; cowork must use MCP connectors + MCP filesystem. **Enumerate every open-day source and its cowork status (has-MCP / degrades / silently-drops) BEFORE building** — don't let any source silently vanish. Then write the note `status: planning` + seeded AI suggestions, render the artifact, wait for the lock-in `SAVE_DAY`.
- **3.2a Surface-neutral date/path.** No `date +%Y-%m-%d` / `$OBSIDIAN_VAULT_PATH` on the Desktop branch — date from model context, paths from the MCP filesystem mount root.
- **3.3 close-day (Desktop).** Render evening flow; on Done, parse the `SAVE_DAY` close payload, reconcile habits into `log.md` (MAX-merge, unchanged), set `status: closed`, seed tomorrow.
- **3.4 Habit reconciliation parity** — Desktop write path must produce the same `log.md` as the CLI path.

**The `SAVE_DAY` handler is the heart of 3.2/3.3** — implement exactly the contract in the 2.1 spec: parse the envelope (malformed/schema-mismatch → refuse to write), idempotent on `saveId`, re-read the LATEST note, field-level patch onto it (never the artifact's stale snapshot), base-hash conflict check, whole-file replace (never delete — cowork gates `rm`).

## Method

TDD (red→green); keep `companion/` tests green and add tests for new shared logic. Use the venv python above to run pytest (`pytest` is NOT on bare PATH). Use `/codex-review` to get a second opinion on substantial work (two-pass: deep review, then a terse `-c model_reasoning_effort=low` ranked-list pass — `tee|tail` truncates the verdict). Commit per task on `pp-cowork-companion`.

## Open caveats (carry forward, don't re-derive)

- Artifact still needs **real-cowork visual + interaction verification** (static previews are faithful but not the live runtime). The `localStorage` draft path is guarded with a fallback but its availability in cowork is unconfirmed.
- Memory has the durable cross-session facts: `cowork-delivery-model` (cowork loads skills from its own snapshot store / ZIP-upload / marketplace — NOT `~/.claude/`; ship as a Cowork plugin) and `codex-second-opinion` (how to run `/codex-review`).

## Opening prompt to paste in the fresh session

> Resuming the cowork-companion build (worktree `~/dev/nsls-personal-toolkit-cowork`, branch `pp-cowork-companion`). Read `docs/cowork/PHASE-3-START.md` in full first, then the docs it points to, confirm the suite is green, and continue with Phase 3 (skill integration) TDD. Don't push or share without my explicit OK.
