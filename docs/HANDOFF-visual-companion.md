# Handoff — Visual Companion restyle (continue in Claude Code desktop)

**Branch:** `pp-visual-companion` (worktree at `/Users/claw/dev/nsls-personal-toolkit-cowork`)
**Lands in:** PR #29 (https://github.com/thensls/nsls-personal-toolkit/pull/29). Do NOT push or update the PR without Davo's explicit OK. Keep the word "cowork" out of anything that reaches the PR (commit messages, PR text) — squash at push time if needed.
**Full plan:** `docs/plans/2026-06-28-visual-companion-restyle.md` — read it first.

## The decision (context)
We dropped the in-chat "cowork" artifact surface entirely. The **local web companion** (Flask, `localhost:7777`, opened by Claude Code CLI / desktop / VS Code) is now the one and only visual surface; chat is the fallback. The artifact could never be a persistent side panel and dumped JSON into the chat on every save — dead end. The web companion already had the full functionality (writes straight to the Obsidian vault, full disposition controls, live updates); it just needed to look as good as the artifact did. That restyle is what this work is.

## Done so far (all committed on this branch, 185 tests passing)
1. **Branch renamed** `pp-cowork-companion` → `pp-visual-companion`.
2. **Cleanup** (commit 6c4f598): removed the artifact (`cowork-dashboard.jsx`, `cowork-artifact/`, drift-guard test), the dead SAVE_DAY apply code in `companion/parsers.py` (it was cowork-only — the web companion saves via its own `/save` route; parsers.py went 605→208 lines), redundant tests, and the Surface-Selection / Desktop-surface sections in the open-day/close-day SKILLs. KEPT: the `status: planning|active|closed` frontmatter contract, all CLI companion logic.
3. **Day surface restyle** (commit 6ad7d00): NSLS brand theme layer added to `companion/static/tailwind.css` (CSS variables + `.nsls-*` component classes), applied to `templates/base.html` (navy nav), `templates/day.html` (branded cards), `templates/_components/task_list.html` (progress discs + brand segmented control), `_components/habit_row.html` (brand tick boxes). Screenshot-verified — looks on-brand.
4. **State-aware banner**: the Command Center no longer shows the stale "type done" instruction once the day is open. Driven by `day_status` (from the note's `status:` frontmatter), passed in the `/` (day) route in `server.py`. Both states verified.
5. **Add-a-bonus control** in the Command Center: new `/add-bonus` route in `server.py` + `_components/bonus_add.html`, targeting `#tasklist-bonus`. Verified.

## Brand tokens (already in static/tailwind.css `:root`)
navy `#18315A` · bluegray `#33475B` · darkblue `#425B76` · teal `#0091AE` (the one action accent) · gold `#EEB117` (done) · lightblue `#E5F5F8` · disc-empty `#E5EAF1` · red `#C2433B`. Font: Lexend Deca w/ system fallback. **Progress disc:** 22px circle — empty `#E5EAF1`, partial `conic-gradient(teal <pct>%, #E5EAF1 0)` via inline `--p`, done solid gold.

## What's LEFT (in priority order)

### A. Test mode (`-t`) — DO THIS FIRST (Davo's priority)
Goal: `open day -t` / `close day -t` run against a **separate test vault** so trying the companion never touches real daily notes. `reset-day -t` wipes test data only.

Research already done (see the plan doc, Task 6): the whole system keys off ONE variable, `$OBSIDIAN_VAULT_PATH`. `cli.py serve` reads `--vault` or that env var → `create_app(vault_path)` → everything uses `app.config["VAULT_PATH"]`. Skills write to `$OBSIDIAN_VAULT_PATH/01-daily/...`. So `-t` = point that variable at a test vault.

Implementation shape (confirmed in plan):
- Test vault: `~/.claude/local-plugins/nsls-personal-toolkit/companion-test-vault/` (add to `.gitignore`), auto-seeded with subdirs + a sample daily note on first `-t` run (reuse `cli.py:ensure_vault_structure`).
- `-t` flag in open-day / close-day / reset-day SKILLs: when present, set `OBSIDIAN_VAULT_PATH` to the test vault for the duration of the skill, and pass it to `serve --vault`.
- TEST marker is already wired in the UI: `base.html` renders `.nsls-test-bar` / `.nsls-test-flag` when a `test_mode` template var is truthy. You need to PASS `test_mode=True` into the templates when the server is running against the test vault (detect by comparing the resolved vault path to the test-vault path in `server.py`, or pass a flag through `cli.py serve`). The CSS classes already exist.
- **Safety guard (critical):** `reset-day -t` must assert the resolved path ends in `companion-test-vault` before deleting; and reset-day WITHOUT `-t` must never touch the test vault. No accidental real-data wipes.
- Add tests for the path resolution + the reset-day guard.

### B. Restyle the remaining mode screens for visual consistency
The Command Center (the `else` branch of `day.html`) is done. These partials still wear the old plain Tailwind look and need the same `.nsls-*` treatment:
- `templates/_components/coach_morning.html`
- `templates/_components/coach_evening.html`
- `templates/_components/results.html`
- `templates/_components/energy_row.html` (the Low/Med/High buttons — minor)
- The Week and Streaks tabs (`templates/week.html`, `templates/streaks.html`) if you want full consistency.
Reuse the existing `.nsls-card`, `.nsls-card-title`, `.nsls-btn-*`, `.nsls-disc`, `.nsls-seg`, `.nsls-textarea` classes. Screenshot each mode to verify.

## How to run / verify locally
```bash
cd /Users/claw/dev/nsls-personal-toolkit-cowork
# one-time: the companion venv + pytest
python3 -m venv companion/.venv && companion/.venv/bin/pip install -e companion && companion/.venv/bin/pip install pytest
# tests
companion/.venv/bin/pytest companion/tests/ -q
# run against a throwaway vault and screenshot (headless Chrome)
companion/.venv/bin/toolkit-companion serve --vault /tmp/somevault --port 7788 --no-open
```
To see a mode, seed `01-daily/<today>.md` with `status: active` (Command Center) / `status: planning` (coach-morning) / `status: closed` (results), then load `http://127.0.0.1:7788/`. Bonus items must be NUMBERED (`1. [ ] x`), habits.md uses the `- id: / name:` structured format (see `companion/tests/test_habit_management.py` for the exact shape).

## Rules
- Run the test suite after every change; keep it green.
- Don't push, don't open/modify PRs, don't share anything externally without Davo's explicit OK each time (see his global CLAUDE.md).
- Keep "cowork" out of commit messages and anything PR-bound.
