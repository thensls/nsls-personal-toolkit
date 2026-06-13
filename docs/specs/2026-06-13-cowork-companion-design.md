# Cowork Companion — Design Spec

**Date:** 2026-06-13
**Author:** Davo Wood (with Claude)
**Status:** Draft — supersedes the never-written `2026-05-15-cowork-toolkit-design.md`. Informed by the now-built CLI/web companion (`2026-05-16-cli-companion-webapp-design.md`) and the lessons from building it.

## Summary

A Claude Desktop (cowork) version of the personal productivity toolkit's visual companion. Same daily/weekly rituals, same Obsidian vault, same markdown contract as the CLI/web companion — but rendered as a **React artifact inline in the Desktop chat** instead of a local web app.

The CLI/web companion (localhost:7777 Flask app) stays as-is for terminal users. The cowork companion is the surface most people will actually use — non-terminal NSLS builders who live in Claude Desktop. Both are interchangeable views over one vault: a day planned in the CLI opens cleanly in cowork and vice versa.

**One skill, two surfaces.** `open-day` / `close-day` (and later the week rituals) stay single skills. They detect the surface they're running on and route to the right companion: CLI/Claude Code → open the Flask web app; Claude Desktop → render the artifact. The ritual logic (data collection, AI suggestions, the markdown contract) is shared; only the rendering surface swaps.

## Why now / why the artifact model

The CLI companion proved the rituals and hardened the data contract. But building it surfaced a class of pain that is **specific to the local-web-server model** and that the artifact model avoids entirely:

- **SSE reload races.** The Flask app pushes Server-Sent Events on vault changes; reloads repeatedly clobbered Alpine/HTMX UI state mid-interaction. We patched it with suppression windows and a `data-suppress-sse-reload` attribute, but it stayed fragile.
- **Server lifecycle.** PID files, stale-process detection, "first free port starting at 7777," debug-mode-off meaning templates don't reload — a whole category of "is the server even running the code I just wrote" confusion.
- **Server-side write locking.** `safe_modify` with a separate lockfile to survive atomic renames; the two-writer problem between CLI and browser.

An artifact has **no server**. State lives in React during the chat session. There is no SSE, no PID, no port, no lockfile. The artifact reads the vault once (via MCP filesystem) when Claude renders it, holds interaction state locally, and writes back **once** on an explicit save. The lessons we learned building the web app are mostly lessons about *why the artifact model is simpler* — plus a hardened data contract that ports over unchanged.

## Goals

1. **Same rituals, same vault, same contract** as the CLI companion. Zero divergence in the markdown.
2. **Render a rich interactive artifact** for the daily loop (Coach Cards → Command Center → evening close) inside Claude Desktop.
3. **Two-way binding via explicit save.** Artifact holds state; on "Lock in" / "Save", Claude reads the artifact state and writes back to Obsidian via the MCP filesystem server.
4. **One skill per ritual, surface-detected.** `open-day` works in CLI and Desktop; it picks the companion.
5. **Shareable to non-terminal NSLS builders** — the primary reason cowork exists.

## Non-goals (v1)

- **Replacing the CLI/web companion.** It stays for terminal users.
- **Weekly rituals + onboarding wizard.** Daily core first (open-day, close-day, Command Center, habits/streaks). Week rituals and the onboarding wizard are Phase 2 — same staging the CLI companion used.
- **Per-keystroke save.** Every write in cowork costs a Claude turn (tokens). Saves are explicit and batched, never per-tap.
- **Scheduling / pre-fetch / notifications.** Same as both prior specs — no `/schedule` pre-write in v1. (The cowork design memory floated 7am pre-fetch; deferred.)
- **`/log`, `/person-intelligence`, `/learn`, `/self-insight` views.** Phase 2.

## Lessons from the CLI companion build (these drive the design)

| Lesson (from building the CLI companion) | Consequence for cowork |
|---|---|
| SSE reloads clobbered live UI state | Artifact holds state in React; no live-reload mechanism at all. Read once, save once. |
| Mode detection by section *presence* was fragile (the `## Insight Reflection` presence check flipped Command Center → results mid-day) | Daily note carries an explicit `status:` frontmatter (`planning` / `active` / `closed`). The artifact reads `status`, never infers mode from which sections exist. |
| Energy was conflated (one field, written to the wrong section, duplicated) | Two distinct fields: morning energy in `## Morning Check-in`, evening energy in `## End of Day`. Artifact shows both; morning captured in Coach Cards, evening in the close flow. |
| Done/Delete shared one `### Dismissed` section → checking one checked both | Three mutually-exclusive disposition sections: `### Done`, `### Deleted`, `### Deferred`. Port the contract exactly. |
| Per-tap server writes were cheap (direct HTTP) | Per-save Claude turns are NOT cheap. Artifact batches: hold all edits, write on explicit save. Design the UI around "Lock in" moments, not ambient autosave. |
| Two-writer reconciliation needed (CLI tap vs close-day) | `30-habits/log.md` stays canonical; MAX-merge in close-day unchanged. Artifact reads log.md for streaks, writes ticks on save. |
| Streak rule risk of living in N languages | Canonical rule stays Python (`companion/streak.py`) + prose in `close-day/SKILL.md`. Artifact embeds a JS port **for display only**, guarded by a parity test asserting JS and Python agree on the six canonical sequences. No Streak Engine MCP needed (simpler than the original memory's Approach B). |
| Raw Bash output flooded the chat | In cowork the data collection uses MCP tools (Calendar, Asana, etc.), not bash — naturally quiet. Keep the "one summary line per source" discipline in the skill. |

## Architecture

### One source of truth, two renderers

```
┌──────────────────────────────────────────────────────────────┐
│  Claude Desktop — cowork                                      │
│  - open-day / close-day skills (surface-detected branch)      │
│  - MCP connectors: Google Calendar, Asana, Slack, Gmail       │
│  - MCP filesystem server → Obsidian vault + Familiar stills   │
│  - Renders cowork-dashboard artifact (React) inline           │
└───────────────────────────┬──────────────────────────────────┘
                            │ reads/writes via MCP filesystem
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  Obsidian Vault — single source of truth                      │
│  - 01-daily/, 02-weekly/, 30-habits/, 50-reference/           │
│  - IDENTICAL markdown contract to the CLI/web companion       │
└───────────────────────────┬──────────────────────────────────┘
                            │ also read/written by:
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  CLI/web companion (unchanged) — localhost:7777 Flask          │
└──────────────────────────────────────────────────────────────┘
```

### Surface detection

`open-day` / `close-day` need to know which surface they're on. Detection order:
1. **Explicit override** in the invocation ("open day cowork" / "open day cli") or `companion_surface` in `builder-profile.md`.
2. **Environment signal:** if the MCP filesystem tool is present and the CLI `toolkit-companion` binary is *not* resolvable → Desktop. If running under Claude Code (CLI) → web companion.
3. **Default:** CLI/web if ambiguous (safest — it's the proven path).

The detection block lives once at the top of each skill's visual-companion section, beside the existing `visual_mode` on/off logic. (Open question O1: nail the exact, reliable signal — see below.)

### The artifact: two-way binding via explicit save

- Claude renders the `cowork-dashboard` artifact, seeding it with today's parsed daily-note state (Top 3, Bonus, Unplanned, habits, energy, etc.).
- The artifact holds all interaction state in React (checkboxes, text edits, habit ticks, disposition toggles, mode-step progress).
- On an explicit **save trigger** — "Lock in →", a Save button, or finishing the evening close — the artifact emits its full state, Claude reads it, and writes back to the vault via MCP filesystem in **one** turn.
- No ambient autosave. The UI is designed around discrete save moments so token cost stays bounded.

### Tech stack

- **Artifact:** React (Claude Desktop artifact runtime). Tailwind for styling (artifact-supported). No build step the user manages — it's a single artifact component Claude renders.
- **File access:** MCP filesystem server (`claude_desktop_config.json`) pointed at the Obsidian vault + Familiar stills paths from `data_sources.familiar.paths[*]` in `builder-profile.md`.
- **Connectors:** standard Anthropic MCP connectors (Google Calendar, Asana, Slack, Gmail) — already wired in cowork.
- **State:** Markdown in the vault. Same files, same sections as the CLI companion. No database.
- **Streak rule:** canonical Python (`companion/streak.py`) + prose in `close-day/SKILL.md`. Artifact embeds a JS display copy with a parity test.

## Data model (IDENTICAL to the CLI companion — this is the contract)

`01-daily/<date>.md`:
- Frontmatter: `status: planning | active | closed` **(new — explicit mode, replaces presence-inference)**
- `## Morning Check-in`
  - `- Energy:` *(morning energy)*
  - `### AI Suggested: Top 3 (from <prev>'s close)` / `### AI Suggested: Delegate These` *(seeded by close-day)*
  - `### My Top 3` — `1. [ ] ...`
  - `### Bonus`
  - `### Unplanned` *(unplanned wins)*
  - `### Done` / `### Deleted` / `### Deferred` *(mutually-exclusive dispositions; legacy `### Dismissed` read as Done)*
  - `### Vitality` — Move / Grow / Connect
  - `### Habits` — `- [ ] **name**` (bolded name matches `habits.md` verbatim)
- `## Calendar`
- `## Daily Insight` *(Command Center quick capture — NOT the day-close section)*
- `## Gratitude`
- `## Work Log`, `## Active Projects`
- `## Insight Reflection` *(close-day; the day-close reflection)*
- `## End of Day`
  - `- Energy:` *(evening energy)*
- `## Carrying Over`, `## Brain Dump`, `## Projects Touched` *(close-day)*

`30-habits/habits.md` — habit config (id, name, emoji, target, frequency; Active/Archived).
`30-habits/log.md` — append-only ticks: `2026-06-13 · theraband:1.0 · weights:0.5`. **Canonical source for streaks.**
`02-weekly/<week>.md` — frontmatter `status: draft|confirmed|closed`, stack rank table, mode, tri-state Top 3 (`[/]` = partial), Quick Notes, AI Suggested next week. *(Phase 2 for the cowork artifact.)*
`50-reference/builder-profile.md` — add `companion_surface: cli | cowork | auto` and (optional) `cowork: { artifact_version }`.

## Artifact modes (mirror the CLI Day-tab states, driven by `status` frontmatter)

| Mode | `status` | What renders |
|---|---|---|
| Morning Coach Cards | `planning` (or no Top 3 yet) | Stepped ritual: greet + **morning energy** → confirm Top 3 (from AI suggestions) → Bonus → habit intentions → vitality → "Lock in" (writes Top 3, sets `status: active`) |
| Command Center | `active` | Dense dashboard: Top 3 checklist, Bonus, **Unplanned wins**, Habits row (streak + tap), Vitality, read-only morning energy, `## Daily Insight` quick capture |
| Evening Coach Cards | close-day invoked | Stats recap → Insight Reflection → Gratitude → **evening energy** → Done (sets `status: closed`) |
| Evening Results | `closed` | Read-only summary: stats, what got done, reflection + gratitude, both energy values |

## Open questions

- **O1 — Surface detection signal.** What's the *reliable* programmatic signal that a skill is running in Claude Desktop vs Claude Code? Candidates: presence/absence of the `toolkit-companion` binary, presence of a specific MCP filesystem tool, an env var cowork sets. Needs verification in a real Desktop session before the skill branch can be trusted. Until confirmed, rely on the explicit override (`open day cowork`).
- **O2 — Artifact save round-trip mechanics.** Exact mechanism for the artifact to hand its state back to Claude for write-back (button that injects a chat message with serialized state? a `window.claude` API?). Verify what the current Desktop artifact runtime supports.
- **O3 — Streak rule parity enforcement.** Where does the JS↔Python parity test run (it's not a normal pytest since one side is JS)? Options: a small Node test in CI, or a Python test that shells the JS through a tiny harness. Decide during build.
- **O4 — MCP filesystem write granularity.** Does the write-back replace the whole daily note or patch sections? Recommend: Claude re-reads, applies the artifact's diffs to the parsed sections, writes the whole file (last-writer-wins, same as CLI). Confirm no clobbering of close-day-only sections.

## Phase 2

- Week rituals in the artifact (stack rank, push/protect mode, tri-state weekly priorities, Quick Notes copy).
- Onboarding wizard artifact (UI version of `/personal-setup`).
- `/schedule`-driven 7am pre-fetch (pre-write today's note before the user opens Desktop).
- `/log`, `/person-intelligence`, `/learn`, `/self-insight` artifact views.
- Mobile (Desktop on iPad, or a thin mobile artifact).

## What's shared vs the CLI companion

**Shared (do not diverge):** the entire markdown contract; the streak rule; the habits engine and log.md MAX-merge; the disposition model; the two-energy model; the AI-suggestion seeding; `builder-profile.md` as runtime config.

**Different:** rendering surface (React artifact vs Flask/HTMX); file access (MCP filesystem vs direct Python); write model (batched per-save Claude turn vs direct HTTP per tap); no server lifecycle; no SSE.
