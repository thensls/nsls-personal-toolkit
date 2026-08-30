# Visual Companion — restyle, cleanup & test mode

**Branch:** `pp-visual-companion` (renamed from `pp-cowork-companion`)
**Lands in:** PR #29 (retarget + squash so no "cowork" wording reaches the PR)
**Decision context:** Dropping the cowork artifact entirely. The visual companion is for the CLI / Claude Code desktop / VS Code extension — the surfaces where it actually works and where Marcus is steering people. See memory: `cowork-artifact-retired`.

## Goals

1. Retire the cowork artifact cleanly (keep the good backend work).
2. Make the web companion look as good as the artifact did (navy/gold/teal, progress discs).
3. Fix the stale "type done" banner.
4. Let users add a Bonus item from the Command Center.
5. Add a `-t` test mode so trying the companion doesn't disturb real open-day/close-day data.

## Task list

| # | Task | Status |
|---|------|--------|
| 1 | Rename branch → `pp-visual-companion` | ✅ done |
| 2 | Cleanup: remove cowork artifact (keep `parsers.py` + tests) | ✅ done (commit 6c4f598; 185 tests pass; also removed dead SAVE_DAY code, parsers.py 605→208) |
| 3 | Restyle day surface (artifact theme + progress discs) | ☐ |
| 4 | Fix stale "type done" banner → state-aware | ☐ |
| 5 | Add-bonus-item control in Command Center | ☐ |
| 6 | `-t` test mode (separate test vault) + `reset-day -t` | ☐ |
| 7 | Verify locally (screenshots) | ☐ |
| 8 | Push → PR #29 (squash to drop "cowork" wording) — **needs Reuben's OK** | ☐ |

---

## Task 2 — Cleanup (remove cowork artifact)

Remove:
- `skills/open-day/cowork-dashboard.jsx`, `skills/close-day/cowork-dashboard.jsx`
- `cowork-artifact/` directory (jsx, logic.js, streak.js, mockups, probe docs)
- `companion/tests/test_cowork_artifact.py` (drift guard — no longer needed)
- Cowork-mode sections added to `skills/open-day/SKILL.md` and `skills/close-day/SKILL.md` (the surface-detection / cowork branch). Revert those skills to their CLI-companion behavior.

Keep (these are real backend wins, not cowork-specific):
- `companion/parsers.py` and its tests: `test_save_day.py`, `test_status_write_paths.py`, `test_streak_parity.py`, `test_detect_day_state.py`, `test_frontmatter.py`
- Decide case-by-case: `test_cowork_logic.py` — drop if it only tests the JSX logic block; keep any assertions that cover shared parser behavior.

Run the full suite after removal; it must stay green.

---

## Task 3 — Restyle the day surface

Port the artifact's visual language onto the web templates.

**Source of truth for the look:** the `T` theme + components in the (about-to-be-deleted) `cowork-dashboard.jsx` — extract the palette (navy / gold / teal), the progress-disc component, card radius/shadow/spacing, and typography BEFORE deleting it in Task 2. (Order note: pull the tokens first, or pull them from git history after.)

Files:
- `companion/static/tailwind.in.css` / `tailwind.css` — palette + fonts
- `companion/templates/base.html` — shell, type scale
- `companion/templates/day.html` — card styling
- `companion/templates/_components/task_list.html` — rebuild the progress indicator as the artifact's **disc** (CSS/SVG)
- `_components/coach_morning.html`, `coach_evening.html`, `results.html` — same treatment for consistency

---

## Task 4 — State-aware banner

The banner is gated only by `ctx["closing"]` (URL `?closing=1`). It never reflects that the day is already open, so the "type done" instruction goes stale.

Fix: drive the banner from `_detect_day_state()` (already exists, `server.py:789`):
- not yet opened → "Pick your Top 3, then type `done` in the terminal."
- day open → "Day's open — mark progress here any time." (no stale instruction)
- closing (`?closing=1`) → existing close line.

Not real-time on the keystroke (terminal ≠ server), but correct on the page's normal refresh/poll. Fold into Task 3.

---

## Task 5 — Add a Bonus item from the Command Center

Today the Bonus section renders existing items but the Command Center has no add-control (only Unplanned has one).

Add an "add bonus" input mirroring the Unplanned pattern (`_components/unplanned_section.html` + its `/save` route). Wire to the Bonus section so it writes through the same parser path. Confirm `parsers.py` already supports appending to Bonus (it splices a Bonus subsection — likely yes; verify).

---

## Task 6 — `-t` test mode  ⚠️ RESEARCH FIRST

Goal: `open day -t` / `close day -t` run against a **separate test vault**, leaving real daily notes untouched. `reset-day -t` wipes **test** data only.

### Research needed before implementing
1. **How is the vault path resolved today?** `cli.py serve --vault` flag + `app.config["VAULT_PATH"]`. Trace the full chain: skill → how it picks the vault → server. Find every place the path is hard-derived (`01-daily/`, `02-weekly/`, etc.).
2. **How do the skills decide what vault to write to?** open-day/close-day write the daily note directly (not only via the server). Find those write paths in the SKILL.md files.
3. **What does `reset-day` delete today, and how does it locate the file?** Confirm it keys off the same vault path so `-t` can redirect it.
4. **Server PID/port file** (`PID_FILE`) — does a test server collide with a real one? May need a separate port / pidfile for test mode, or just document "stop the real one first."

### Research findings (DONE)
The entire system keys off **one variable: `$OBSIDIAN_VAULT_PATH`**:
- `cli.py serve` → `--vault` flag OR `$OBSIDIAN_VAULT_PATH` → `create_app(vault_path)` → everything downstream uses `app.config["VAULT_PATH"]` (single source).
- Skills (open-day/close-day) write directly to `$OBSIDIAN_VAULT_PATH/01-daily/...` etc.
- reset-day deletes `$OBSIDIAN_VAULT_PATH/01-daily/<date>.md` (+ habits log row, + seeded next-day note).

So `-t` = **override `$OBSIDIAN_VAULT_PATH` to a test vault** for that command. No code-path forking needed — just point the var.

### Implementation shape (confirmed)
- Test vault: `~/.claude/local-plugins/nsls-personal-toolkit/companion-test-vault/` (gitignored), auto-seeded with the standard subdirs + a sample daily note on first `-t` run (reuse `ensure_vault_structure`).
- `-t` flag in open-day / close-day / reset-day: when present, set `OBSIDIAN_VAULT_PATH` to the test vault for the duration of the skill (and pass it to `serve --vault`). Companion banner/title should show a clear **"TEST"** marker so you never confuse it with real data.
- The server already takes `--vault`, so test mode needs no server change beyond passing the test path.

**Safety guard:** reset-day, when `-t` is set, must assert the resolved path ends in `companion-test-vault` before deleting. If `-t` is NOT set, it must never touch the test vault. Hard guard — no accidental real-data wipes.

## Theme tokens (extracted from the artifact before deletion)
```
navy     #18315A   (headings / primary)
bluegray #33475B
darkblue #425B76   (secondary text)
teal     #0091AE   (the ONE action accent; partial-progress)
gold     #EEB117   (done / complete)
lightblue#E5F5F8   (subtle fills)
white    #FFFFFF
nearblack#191919   (body text)
empty-disc #E5EAF1
deleted-red #C2433B
font: "Lexend Deca", system-ui fallback
```
**Progress disc:** 24px circle. empty → `#E5EAF1`; partial → `conic-gradient(teal <pct>%, #E5EAF1 0)`; done/100% → solid gold.

---

## Task 7 — Verify
Run companion locally, screenshot day + coach + results, compare to the artifact, iterate.

## Task 8 — Push (needs Reuben's explicit OK)
Squash so commit messages carry no "cowork" wording. Retarget PR #29 to `pp-visual-companion` (or open fresh). Nothing pushed until Reuben says so.
