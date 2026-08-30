# Handoff — Visual Companion, round 2 (continue in a fresh session)

**Branch:** `pp-visual-companion` (worktree at `/Users/claw/dev/nsls-personal-toolkit-cowork`), pushed to `origin/pp-visual-companion` @ `bb60435`. Installed copy at `~/.claude/local-plugins/nsls-personal-toolkit/` is fast-forwarded to the same commit (so `open day` / `close day` in any session use this code). **212 tests pass.**

**Lands in:** PR #29 (`pp-cli-visual` → `main`, open). Our branch fully contains `pp-cli-visual` (it's an ancestor). Do NOT push to `main`/`pp-cli-visual`, force-push, or open/modify the PR without the repo owner's explicit OK each time. Branch pushes to `origin/pp-visual-companion` are fine and expected — do them proactively after each change.

---

## HOW THE REPO OWNER WANTS YOU TO WORK (read first — these are hard-won)

- **Be concise.** Lead with the answer/result + his next action. No process narration. He gets genuinely annoyed by long status dumps.
- **NEVER open `.html`/source files for him.** Editing a template pops a "Launch preview panel" showing raw Jinja (`{% %}` — "code with percentages"); it's useless to him and irritating. **Verify ONLY with headless-Chrome screenshots of the running companion, and actually Read the screenshot yourself before claiming it looks right.** He has caught "looks fine" claims that were wrong on his screen. Take the screenshot every time; show him the file path.
- **Always give a clickable `http://localhost:<port>` link** (never `127.0.0.1`, never bare text).
- **Push working branches to origin proactively** — it's auto-allowed now (settings + `~/.claude/hooks/permission-gate.py`). Force-push / push to `main`/`master` / any `gh pr` action still require his explicit OK.
- **Don't hand-write/overwrite the test-vault daily note carelessly** — an earlier `cat >` clobbered his in-progress markup. Reseed deliberately and tell him.
- `-t` → test vault (`companion-test-vault/`) on port **7788**, own pidfile. No `-t` → real vault on **7777**. They never collide.

## IMMEDIATE WORK (in order)

### 1. BUG — progress click collapses the table formatting
**Symptom (reported with a screenshot):** on a fresh page load the one-table Command Center looks perfect, but **after clicking a progress button** the layout collapses — no gap between the hours and progress columns, a divider line reappears between Top 3 and Bonus, and the Bonus rows' hours/progress no longer align with Top 3's. Looks like "two tables again."

**Root cause:** `/set-progress`, `/set-estimate`, `/delete-task`, `/add-bonus` all return `_render_task_list()` → `_components/task_rows.html`, which is a **bare `<tbody>`**, and the controls swap it with `hx-target="#tasklist-<section>" hx-swap="outerHTML"`. HTMX parsing a bare `<tbody>` fragment outside a `<table>` context hits the classic browser table-fragment pitfall — `<tbody>/<tr>/<td>` get stripped/mangled, so the swapped-in rows lose their cell structure and the table's column widths recompute wrong. That's the collapse.

**Fix (make it robust — the per-tbody approach was called brittle, and that's right):** swap the **whole table**, not a tbody.
- Give the `<table>` a single id, e.g. `id="task-table"`.
- Make a `_components/task_table.html` partial that renders the FULL table: `<thead>` (once) + the Top 3 `<tbody>` + the Bonus `<tbody>` (reuse `task_rows.html` for each `<tbody>`).
- Point every control (`/set-progress`, `/set-estimate`, `/delete-task` in `task_rows.html`, and the add-bonus input in `bonus_add.html`) at `hx-target="#task-table" hx-swap="outerHTML"`.
- Change `_render_task_list()` (server.py ~1594) and the `/add-bonus` route (~1437) to render `task_table.html` (the whole table) instead of a single tbody.
- `day.html` includes `task_table.html` inside the card (below the "Top 3 · ≈ Xh planned today" header, above the add-bonus input + the single note).
- Add/adjust a test asserting a progress/estimate POST returns the full `<table ... id="task-table">` (not a bare tbody).

### 2. Relabel the estimate column → "Estimated remaining time", stacked vertically
Feedback: people may read "Estimated time" as time *spent*. Make it clearly **time remaining to completion**. Column header text = **"Estimated remaining time"**, **stacked on 3 lines** (Estimated / remaining / time) — he thinks vertical stacking looks best there. It's the `<th class="tt-est">` in the table header (currently in `day.html`, will move into `task_table.html`). Keep the ⓘ timeboxing tooltip. Screenshot to confirm the stacked header aligns over the hours column.

### 3. Get a Codex review of this work
Explicitly asked for (the layout is felt to be brittle). The **`/codex-review`** skill exists (`skills/codex-review/SKILL.md`) — run it on the est-hours + one-table + close-day changes (e.g. review the diff `main..pp-visual-companion` for the companion/templates + server.py routes) and relay findings. He's open to setting up whatever's needed to let you review your own work regularly.

## WHAT'S ALREADY DONE (this branch)
- **Visual restyle** of the whole companion (navy shell w/ rounded frame, brand tokens, Week "coming soon" popover, state-aware open-day banner top+bottom, restyled coach-morning/coach-evening/results/energy).
- **Test mode `-t`** — separate `companion-test-vault/` (gitignored), port 7788, own pidfile, `assert-test-vault` guard; `reset-day` asks real-vs-test confirmation. Skills wired.
- **Per-task time estimates (timeboxing)** — decimal-hours `<!--e:1.5-->` marker per Top 3/Bonus item; editable on Command Center + Plan-your-day; read-only on Results; "≈ Xh planned today" total. Survives progress edits. `/set-estimate` route, `_set_nth_est`, `.nsls-est` + tooltip. (This is what needs the bug fix + relabel above.)
- **Command Center one-table merge** — Top 3 + Bonus in a single `<table>`; Bonus is an in-table label row; headers + "carries forward" note appear once; goal column capped ~25.3rem (wraps long goals); planned-hours total in the card header.
- **close-day routing fix** — defaults to starting the companion + sending the builder to the Command Center to finalize (opens `?closing=1`, gives the link, waits for "done"); `-b` bypasses to a chat close (note: `-v` = verbose in close-day). New Step 10 offers "open tomorrow now?".
- **open-day suggestions** — prefer curated AI set over raw carry-overs (kills reworded dupes), normalize-dedupe, never resurface deleted/done items.
- **Permissions** — branch pushes auto-allowed; PRs/force/main gated. Global `~/.claude/CLAUDE.md` updated with the "push branches freely, PRs need OK" split.

## OPEN DECISIONS (need the repo owner)
- **`CLOSE_DAY_FIX.md`** (repo root) — a stray spec another session left, accidentally committed via `git add -A`; its fix is implemented. Keep / move to `docs/` / remove?
- **Windows test** — the repo owner will run it (fresh install: `install.ps1` + Git Bash `install.sh`; then `open day -t` resolves the `.exe`, serves, a close→results round-trips). Cross-platform invariants: utf-8 + `newline=""` on all writes; `bin/` vs `Scripts\*.exe` (see `docs/windows-setup.md`, commit `79025fe`).
- **Merge `main`** before PR (we're ~73 commits behind; 3 conflicts: `CLAUDE.md`, `open-day`, `close-day` — `main` added an Apple-Health / personal-goals / `/role-coach` line AND renamed "user"→the owner's own first name). **Naming decision needed:** keep `main`'s personal-name style or our generic "builder"?
- **PR #29:** update it in place by fast-forwarding `origin/pp-cli-visual` to our branch (keeps its review history — `pp-cli-visual` is our ancestor), OR close it + open fresh from `pp-visual-companion`. Either way = his explicit OK to push.

## RUN / VERIFY
```bash
cd /Users/claw/dev/nsls-personal-toolkit-cowork
companion/.venv/bin/pytest companion/tests/ -q          # keep 212+ green

TC="$PWD/companion/.venv/bin/toolkit-companion"; TV="$PWD/companion-test-vault"
"$TC" stop --test; pid=$(lsof -ti tcp:7788); [ -n "$pid" ] && kill "$pid"; sleep 1
nohup "$TC" serve --vault "$TV" --port 7788 --no-open >/tmp/tc.log 2>&1 & disown   # runs the WORKTREE code
# seed a Command Center day with estimates + progress into $TV/01-daily/<today>.md
#   status: active; Top 3 items like:  1. [ ] Task <!--p:50--> <!--e:1.5-->  ; Bonus similar
# screenshot (headless Chrome — never open the .html source):
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --hide-scrollbars \
  --screenshot=/tmp/cc.png --window-size=1000,900 --force-device-scale-factor=2 "http://127.0.0.1:7788/"
```
Modes: seed `status: active` → Command Center; `status: planning` (+ `### AI Suggested: Top 3` items) → Plan-your-day; `status: closed` → Results. Or force with `?mode=command|coach-morning|results`. **After any server.py change, restart the server; templates auto-reload.**

## KEY FILES (est-hours + table)
- `companion/templates/day.html` — Command Center; the one-table markup + card header + note live here (move the `<table>` into a `task_table.html` partial per the fix).
- `companion/templates/_components/task_rows.html` — a `<tbody>` (rows + optional section label); reused per section.
- `companion/templates/_components/bonus_add.html` — add-bonus input (retarget to `#task-table`).
- `companion/server.py` — `_strip_est`/`_set_nth_est`/`_EST_RE` (~86-620), `_render_task_list` (~1594), `/set-estimate` (~1610), `/set-progress`, `/add-bonus`, `_build_plan_context` (`top3_est`).
- `companion/static/tailwind.css` — `.nsls-tasktable` + `.tt-*`, `.nsls-est`, `.nsls-tip`.
- Skills: `skills/close-day/SKILL.md` (Step 0.5 routing, `-b`, Step 10), `skills/open-day/SKILL.md`, `skills/reset-day/SKILL.md`.
