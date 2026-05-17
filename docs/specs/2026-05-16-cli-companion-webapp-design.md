# CLI + Web Companion — Design Spec

**Date:** 2026-05-16
**Author:** Dave Wood (with Claude)
**Status:** Draft — alternative direction to the cowork toolkit (see `2026-05-15-cowork-toolkit-design.md`)

## Summary

Keep the toolkit in Claude Code CLI exactly as it is today, and add a small **local web companion** running on `http://localhost:7777` that provides the visual UI (Coach Cards, Command Center, Streaks tab, heatmaps, tappable checkboxes) the cowork artifact would have provided.

The CLI continues to be the canonical interface — terminal users get the experience they prefer. The web companion is a purpose-built lens onto the same Obsidian vault: it reads and writes the same markdown files the CLI skills do, in real time. You can use either surface, or both side by side. If the web companion isn't running, nothing breaks.

## Why this instead of the cowork build

1. **Sidesteps every cowork constraint.** No MCP filesystem mount config, no `window.claude.fs` API uncertainty, no Anthropic CSP rules to worry about, no per-tap Claude turn cost, no `cowork:save` protocol round-tripping. The companion has full local power (it's just Python and a browser).
2. **Builders who love the CLI keep it.** This was always one of the goals — *"it could be awesome for everyone, even people who like the terminal"*. The CLI stays the primary surface; the companion is additive.
3. **Smaller surface area to build.** No skill prompt rewrites of the Familiar bash → MCP port. No port of `gh` for Open PRs. No telemetry MCP server (the existing `PreToolUse` hook keeps firing). Most skills stay exactly as they are; only `open-day` and `close-day` get two narrowly-scoped additions (habits row + Bonus + Gratitude section + log-reconciliation step). The companion is a visual lens over the markdown those skills already produce.
4. **Mobile-adjacent for free.** Bind the server to LAN, hit it from your phone. No native app needed.
5. **Independent of Anthropic's product direction.** Cowork's behavior around hooks, artifact APIs, and project skills is evolving. The web companion is plain Python + plain HTML — it does not depend on any of that.

## Goals

1. **Preserve the upstream toolkit untouched.** Every existing skill works exactly as it does today. Builders who don't want the companion ignore it.
2. **Add habits and streaks as first-class features** with the same concern-counter rule from the cowork spec.
3. **Add a Bonus list and a Gratitude line** in the same way.
4. **Render a beautiful visual UI** for daily / weekly / streak views, served locally.
5. **Real-time sync between CLI and browser.** When the CLI writes the daily note, the browser auto-refreshes. When you tap a checkbox in the browser, the markdown updates immediately.
6. **Mobile-friendly** layout — usable on phone or tablet if you choose to expose the server on your LAN.
7. **Zero install ceremony.** `toolkit-companion serve` (one command) starts the server, opens the browser, you're in.

## Non-goals (v1)

- Claude Desktop / cowork support. This is a separate track (see `2026-05-15-cowork-toolkit-design.md`).
- Replacing Obsidian. The companion is a *view*, not a competitor to Obsidian Live or Notion.
- Native macOS app, menu bar app, system tray app. v1 is browser-only.
- Authentication / multi-user. Single-user local-only.
- Cloud hosting. Runs on your machine, period.
- Two-way Asana sync of ad-hoc tasks. Quick-add stays in the existing daily-note shape; no new sections are introduced for it in v1.
- Porting `/log`, `/person-intelligence`, `/learn`, `/self-insight`, `/announce-update` views into the companion. Phase 2.
- Full Week tab (stack rank, push/protect mode, trap check, meeting check, week-at-a-glance grid). v1 ships a minimal read-only weekly-note markdown viewer; the rich Week tab is Phase 2.
- LAN/phone access. Phase 2 (requires shared-secret token).
- Theme switching. Phase 2 (v1 ships a single light theme).

## Background

The toolkit's existing CLI experience is text-heavy. Some users (Dave included) find a dense terminal of priorities, schedules, and reflections cognitively heavier than they need. The original goal of the cowork build was a richer visual UI for non-terminal users — but that build carries significant infrastructure cost (artifact + telemetry MCP + skill prompt rewrites for bash-to-MCP).

A local web companion gets most of the same UX benefits with a fraction of the build cost, and an entirely separate set of risks. Both directions are viable. This spec is for the CLI + companion path; the cowork path is documented separately. They are not mutually exclusive long-term, but should be evaluated and built independently.

## User experience

### One-time setup

1. The user installs the toolkit (existing `install.sh`).
2. `install.sh` adds a new step: *"Install the web companion? [Y/n]"* — if yes, drops a small Python server script and creates `~/Library/LaunchAgents/com.nsls.toolkit-companion.plist` (optional auto-start at login, user choice).
3. First run: companion writes its config (port, theme preference) to `50-reference/companion-config.md`.

That's it. No extra accounts, no MCP registration, no project setup in any app.

### Daily flow

The Day tab has **four states** that auto-detect from the daily note's current contents (overridable via `?mode=...`):

| State | Detection signal | What renders |
|---|---|---|
| Morning Coach Cards | Top 3 not yet filled | 7-step ritual: greet → confirm Top 3 → Bonus → Focus blocks → Habit intentions → Vitality → Lock in |
| Command Center | Top 3 filled, no `## Insight Reflection` heading yet | Dense dashboard: Top 3 checklist, Bonus, Habits row with streaks |
| Evening Coach Cards | `## Insight Reflection` heading present but body empty | 4-step close: today's stats → Insight Reflection textarea → Gratitude textarea → Done |
| Evening Results | `## Insight Reflection` body filled | Read-only summary: stats, what got done, reflection + gratitude text |

**Morning:**
- User opens terminal, runs `/open-day`. Skill writes the daily note with Morning Check-in scaffolding.
- Browser auto-refreshes to **Morning Coach Cards**. User steps through the 7-step ritual, edits as needed (each step auto-saves on input). At Step 7, taps "Lock in →" — transitions to Command Center.

**Throughout the day:**
- **Command Center** is the working view: Top 3 checklist, Bonus, Habits row. Tap a checkbox → markdown updates instantly via HTMX. Tap a habit → log.md updates immediately.
- User can switch to CLI any time for narrative work; skills are unchanged.

**Evening:**
- User runs `/close-day`. Skill writes `## Insight Reflection` and `## Gratitude` headings (with empty bodies the user will fill), updates Habits row, reconciles log.md.
- Browser auto-refreshes to **Evening Coach Cards**. User steps through: stats recap → Insight Reflection (textarea auto-saves) → Gratitude (textarea auto-saves) → Done.
- After Done, the view becomes **Evening Results** — read-only summary of the day.

### Weekly flow

Same pattern, different views. The browser's Week tab shows stack rank, push/protect mode, week-at-a-glance grid, etc. `/open-week` and `/close-week` write the weekly note; the browser reflects.

### Streaks tab

Always available. Browser shows habit list with 30-day heatmap, current streak, longest streak, at-risk indicator. "+ Add habit" button writes to `habits.md`. Per-habit settings (rename, archive) inline.

## Architecture

### Two processes, one source of truth

```
┌─────────────────────────────────────────────────────────────┐
│  Terminal — Claude Code CLI                                  │
│  - All existing skills (open-day, close-day, ...)            │
│  - All existing hooks (skill-event PreToolUse fires here)    │
└────────────────────────┬────────────────────────────────────┘
                         │ reads/writes
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  Obsidian Vault — single source of truth                     │
│  - 01-daily/, 02-weekly/, 30-habits/, 50-reference/          │
└────────────────────────┬────────────────────────────────────┘
                         │ reads/writes; file watcher detects changes
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  Web Companion — local Python server at localhost:7777       │
│  - Flask backend, HTMX + Tailwind + Alpine.js frontend       │
│  - Watches vault for changes, pushes updates to browser via SSE
│  - Renders Day / Week / Streaks tabs                         │
│  - User taps in browser → server writes to vault             │
└─────────────────────────────────────────────────────────────┘
```

No new MCP servers. No Anthropic-side dependencies. The companion runs as a normal user-space process.

### Tech stack

- **Server:** Python 3.10+ (already a toolkit dep). [Flask](https://flask.palletsprojects.com/) for HTTP + SSE. [watchdog](https://github.com/gorakhargosh/watchdog) for filesystem change detection. Standard library for everything else.
- **Frontend:** Plain HTML rendered by Jinja templates on the server. [Tailwind CSS](https://tailwindcss.com/) via CDN (no build step). [HTMX](https://htmx.org/) for partial-HTML interactions (~14kb script tag, no build). [Alpine.js](https://alpinejs.dev/) for inline reactivity (~12kb, no build). All three are CDN-loaded; no `npm install`, no bundler.
- **State:** Markdown in the Obsidian vault. Same files the CLI skills read/write. No second database.
- **Streak rule:** lives as a Python module in `companion/streak.py` *and* the same prose paragraph in `close-day/SKILL.md` (the same dual-implementation pattern as the cowork plan, just with Python instead of JS). Pytest covers the six canonical sequences.

### Process lifecycle

- `toolkit-companion serve` starts the Flask server, opens `http://localhost:7777` in the default browser.
- The server auto-exits after a configurable idle period (default: 4 hours of no requests). User can re-run the command to restart.
- Optionally, launchd plist (offered during install) starts the server at login. User can opt out.
- If port 7777 is taken, server picks the next free port and announces it.

### Real-time updates

- Server keeps a watchdog observer on the vault directory.
- When a file in `01-daily/`, `02-weekly/`, or `30-habits/` changes, the server pushes a Server-Sent Event (SSE) to all connected browser clients.
- Browser receives the event and refreshes only the affected pane (via HTMX `hx-trigger`).
- Conflict handling: file timestamps and last-modified comparison. If the browser had unsaved input (rare — most interactions auto-save instantly), the user is prompted to merge.

## Skills inventory

**Mostly unchanged.** Two skills get narrowly-scoped additions; everything else is untouched.

- **`open-day` — small change**: seeds new `### Bonus` and `### Habits` subsections in the Morning Check-in template, and ensures `30-habits/habits.md` exists (offers to create from template on first run).
- **`close-day` — small change**: reconciles the daily-note `### Habits` checkboxes into `30-habits/log.md` (MAX-merge — see "Habit state canonical source" below), adds a `## Gratitude` section to the output template, and includes a streak-rule reference paragraph for narrative prompts. Existing `## Brain Dump` routing and all other sections are preserved.
- **All other skills** (`open-week`, `close-week`, `log`, `familiar`, `person-intelligence`, `learn`, `self-insight`, `obsidian-setup`, `personal-setup`, `announce-update`) work exactly as they do today. They write to the Obsidian vault as before; the companion is just one of multiple consumers of those markdown files.

**Additions outside skill files:**

- The companion itself is a standalone Python process (not a Claude skill).
- An optional install-time prompt is added to `install.sh` ("Install the web companion?"). There is no new `/personal-setup` skill command in v1 — companion (re)configuration happens via the CLI: `toolkit-companion serve` / `stop` / `status`.

## Habit state canonical source

**`30-habits/log.md` is the canonical source of truth for habit completion.** The companion writes to log.md directly on every tap. close-day merges the daily-note `### Habits` checkboxes into log.md using a **MAX-merge** (max of `log.md[today][habit_id]` and the daily-note checkbox value). This means:

- A tap in the companion (writes `walk:1.0` to log.md) is never undone by close-day running afterwards.
- A manual checkbox tick in Obsidian is never undone by close-day if the companion was already at 1.0.
- Resetting a habit to 0.0 mid-day requires editing log.md directly (rare; users normally just don't tap).

The streak engine in `companion/streak.py` reads only `log.md` — never the daily-note checkboxes. The daily-note checkboxes are a human-readable mirror, not an independent state.

## Data model

Same as the cowork spec, summarized here:

- `01-daily/<date>.md` — daily note with `## Morning Check-in` (with `### My Top 3`, **new** `### Bonus`, `### Habits`, etc.), `## Calendar`, `## Work Log`, `## Insight Reflection`, **new** `## Gratitude`, `## Carrying Over`, `## Brain Dump`, etc. Section names match upstream exactly.
- `02-weekly/<week>.md` — weekly note with stack rank, mode, themes, etc.
- `30-habits/habits.md` — habit config (id, name, emoji, target, frequency)
- `30-habits/log.md` — append-only daily ticks: `2026-05-15 · walk:1.0 · read:0.5`
- `50-reference/builder-profile.md` — extended with `companion: { port, theme, autostart }` fields.

## Companion server structure

```
companion/
├── server.py              # Flask app, routes, SSE endpoint
├── streak.py              # canonical concern-counter rule
├── parsers.py             # habits.md, log.md, daily-note section parsers
├── watcher.py             # watchdog observer wiring
├── templates/
│   ├── base.html          # Tailwind + HTMX + Alpine script tags
│   ├── day.html           # Day tab — Coach Cards or Command Center
│   ├── week.html          # Week tab
│   ├── streaks.html       # Streaks tab with heatmap
│   └── _components/       # partials swapped in via HTMX
└── tests/
    ├── test_streak.py     # six canonical sequences (parity with cowork JS)
    ├── test_parsers.py
    └── test_routes.py
```

### Key routes

- `GET /` → renders `day.html` with today's data
- `GET /week` → renders `week.html`
- `GET /streaks` → renders `streaks.html`
- `POST /tick` → updates `30-habits/log.md` for a habit
- `POST /save` → writes a section back to today's daily note
- `POST /habit` → add/archive habit in `habits.md`
- `GET /events` → SSE stream; emits when vault files change

## Trigger model

**No scheduling. No pre-fetch. No notifications.** Same as the cowork spec.

- Morning: user opens terminal, types `/open-day`. CLI runs, writes the daily note. Browser already showing today's tab auto-refreshes within a second.
- If the user has the companion auto-start at login (via launchd), the server is always there. If not, they run `toolkit-companion serve` when they want it.

## Streak rule

Same canonical rule as the cowork spec. 100% extends streak and clears concern; 50% adds 0.5 concern; 0% adds 1.0 concern. Thresholds 0.5 / 1.0 / 1.5 / 2.0 → ok / one_miss / at_risk / reset. Any full day mid-chain clears concern back to 0.

Implementation: pure Python function in `companion/streak.py`, plus the same prose paragraph in `close-day/SKILL.md`. Pytest covers six canonical sequences. The rule never lives in two languages — only one Python implementation + one prose paragraph.

## Edge cases

- **Companion not running.** Toolkit works exactly as it does today. No visual UI, no UX regression for CLI users. Habits still work (CLI skills write to `habits.md` and `log.md`).
- **Browser tab closed, server still running.** Server keeps watching; next time you open a tab, current state is rendered.
- **Two browser tabs open.** Both subscribe to SSE; both see updates. Last-writer-wins on POST conflicts.
- **Conflicting writes — CLI writes daily note while user is editing in browser.** Browser detects file change via SSE; if the user has unsaved edits in a textarea, they're shown a "merge or discard your edits" prompt. For the common case of checkbox taps (instant save), this never happens.
- **Vault on iCloud with sync lag.** Same trade-off as the cowork spec — companion reads from the local copy; if iCloud hasn't synced yesterday's data yet, the companion's heatmap shows yesterday as empty until sync completes. Acceptable.
- **Port 7777 in use.** Server picks next available port (7778, 7779, ...) and prints the URL.
- **User has multiple machines.** Each machine runs its own companion server. State syncs through iCloud/Obsidian Sync just like the CLI side.

## Open questions

1. **LAN access deferred to Phase 2.** v1 binds `127.0.0.1` only — the `--host` CLI flag is removed entirely. LAN/phone access requires a shared-secret token, which is Phase 2 work. This matches the existing CLI toolkit's security posture (the CLI has no networked surface today, so the companion shouldn't introduce one without auth).
2. **Drag-and-drop for focus blocks.** HTMX is awkward for drag interactions. Decision: ship v1 without drag (use a time picker on each schedule item), revisit if users want it.
3. **Theme switching deferred to Phase 2.** v1 ships a single light theme. localStorage-based theme toggle was scoped out as not load-bearing for v1.

## Phase 2

- Native macOS menu bar app (Swift) that shows habit status + opens the browser tab.
- Native iOS shortcut that hits the LAN URL with a tap-to-tick widget.
- Sync the companion's open / close ritual confirmations back to the CLI session via a small CLI bridge (so confirming in the browser progresses the CLI skill).
- Drag-and-drop for focus blocks (would need a small JS component or upgrade to Alpine+SortableJS).
- Replace HTMX/Alpine with a small React app if the v1 UX hits limits (unlikely).
- Server-side hooks for "after open-day saves, push a desktop notification" — replacing the dropped scheduling work from the cowork direction.

## Implementation outline

(For writing-plans to elaborate. High level:)

1. **`companion/streak.py` + pytest** — six canonical sequences. Smallest, well-defined, copy from the cowork plan's JS.
2. **`companion/parsers.py`** — habits.md, log.md, daily-note section parsers. Parity with the cowork plan's TS parsers.
3. **`companion/server.py` — minimal Flask app** — single route `GET /` rendering a placeholder Day tab. Verify it starts and serves.
4. **`companion/watcher.py`** — watchdog observer + SSE endpoint. Verify file changes push events.
5. **Day tab template** — Coach Cards layout (morning ritual flow) + Command Center layout (workday view). Tab switching via Alpine.
6. **Day tab interactions** — HTMX POSTs for checkbox toggle, habit tick, save reflection. Verify each updates the markdown.
7. **Week tab template + interactions** — stack rank display, mode badge, week glance grid.
8. **Streaks tab template** — habit list with 30-day heatmap (server-rendered CSS grid).
9. **Streaks tab interactions** — add habit form, archive button.
10. **`toolkit-companion` CLI entry point** — `serve`, `stop`, `status` subcommands. Opens browser via `webbrowser.open`.
11. **Install script integration** — offer optional install during `personal-setup`; write launchd plist if user opts in.
12. **Skill updates** — only the two changes needed for habits: `open-day` seeds the habits row; `close-day` reconciles the log. Streak prose paragraph added to `close-day/SKILL.md`.
13. **Docs** — `docs/companion-quickstart.md` walking a new user through `toolkit-companion serve` and first use.
14. **Smoke test** — end-to-end on a fresh vault: open-day, see browser populate, tap a checkbox, see file update, edit file externally, see browser refresh.
15. **Release** — `v1.0-companion` of toolkit-companion. CLI users see one new optional prompt during onboarding; nothing else changes.

## What we're explicitly dropping vs the cowork direction

- No React artifact. No `cowork-dashboard.tsx`. No Vite, no Vitest configuration. The frontend is HTMX + Tailwind CDN.
- No MCP filesystem mount registration in `claude_desktop_config.json`. The companion has direct filesystem access; it doesn't need MCP.
- No telemetry MCP server. The existing `PreToolUse` hook in `nsls-builder-toolkit/hooks/skill-event.sh` continues to fire for CLI skill invocations exactly as it does today.
- No Familiar bash → MCP port. The CLI's existing bash-based Familiar reads work as they do today.
- No `cowork:save` protocol. Browser ↔ server is plain HTTP.
- No artifact-version pinning, no `cowork_artifact_version` field. The companion is a normal app that updates with `git pull`.

## What's similar to the cowork spec

- The same habits engine (concern-counter rule, two markdown files, six canonical test sequences).
- The same daily-note schema additions (`### Bonus`, `## Gratitude`, `## Personal`).
- The same skill prompt changes for habits seeding and reconciliation.
- The same multi-machine support (read whatever paths are in `data_sources.familiar.paths[]` from `builder-profile.md`).
- The same Phase 2 deferrals (log, person-intelligence, learn, self-insight, etc.).

## Summary table — companion vs cowork

| Dimension | CLI + Companion (this spec) | Cowork (separate spec) |
|---|---|---|
| Primary surface | Terminal | Claude Desktop chat |
| Visual UI surface | Local browser at localhost:7777 | React artifact in Desktop |
| Local file access | Direct (Python) | Via MCP filesystem mount |
| New infrastructure | Python web server (~500 lines) | Telemetry MCP + React artifact + MCP filesystem config |
| Skill prompt rewrite | None (just two small additions for habits) | Significant (bash → MCP for Familiar, Open PRs, etc.) |
| Per-interaction cost | $0 — direct HTTP to local server | One Claude turn per Save (tokens) |
| Mobile use | LAN access from phone | Not supported v1 |
| Hook-based event capture | Continues to work (`PreToolUse` fires in CLI) | Needs telemetry MCP fallback |
| Survives Anthropic API changes | Yes | Depends on cowork artifact + project API stability |
| Build effort estimate | ~2 weeks of focused work | ~4-6 weeks of focused work |
| Reach | CLI users + anyone willing to open localhost in a browser | Cowork users + non-terminal builders |

Both directions are real options. This spec captures the lighter-weight one. The cowork spec captures the more ambitious one. They are not mutually exclusive long-term, but should be evaluated and built one at a time.
