# Personal Productivity Toolkit

These skills are your personal workflow — edit anything, delete what you don't use, add whatever you want.

This is a fork of Kevin's personal setup. It's one person's answer to "how do I manage my day, week, and notes?" — not a mandate. Take what works, ignore what doesn't.

## First Time?

If you installed this via the Builder Toolkit's `/setup`, your accounts are already connected.

To reconfigure later (change Slack ID, Airtable key, etc.), say `/personal-setup`.

## Skills

| Skill | What it does |
|-------|-------------|
| `/open-day` | Morning planning — calendar, tasks, priorities, schedule focus blocks + vitality time |
| `/open-week` | Weekly planning — project stack ranking, push/protect mode, strategy alignment |
| `/close-day` | End-of-day summary — what happened, what's next |
| `/close-week` | Friday roll-up — weekly achievements, stack rank review, alignment scoring |
| `/learn` | Learning goals, resource ingestion, scaffolded learning paths, progress tracking |
| `/self-insight` | Personal insight — analyzes your calendar, meetings, and behavior to build a personal profile + operating memo |
| `/log` | Log session progress to project notes |
| `/familiar` | Recall past screen activity and work context |
| `/person-intelligence` | Build relationship profiles, track 1:1 context, biweekly sweep, team-pulse digest, manager-coaching frame (Thrive + How I Work With), managing-up frame for your manager, coaching-action surfacing in /open-day and /open-week |
| `/role-coach` | Coaching from your seat — reads the role you have (and optionally the role you want), diffs stated priorities against what actually happened, and keeps a pattern ledger so advice compounds. Evidence scoped to your access: ICs see only their own data, managers their team, execs org-wide. Wired into close-day/close-week/open-day/open-week |
| `/reset-day` | Start today over — clears today's note so `/open-day` rebuilds it from your real data (`--close-only` keeps the morning plan; `-t` wipes the throwaway test vault only) |
| `/unblock` | Fix the VS Code "permission prompt on every edit" trap when editing the toolkit's own files under `~/.claude/` — sets up a git worktree (or clone + symlink) outside `~/.claude/` |
| `/codex-review` | Get an independent review from OpenAI Codex on code, a design/spec, a plan, or the branch's changes — runs Codex headless + read-only and relays its findings |
| `obsidian-setup` | Set up an Obsidian knowledge base |

## Web Companion

The companion runs at `http://localhost:7777`. Anyone with the toolkit installed gets it: the day skills **build it on first use** if it isn't there yet, so no separate install step is required. `install.sh` still sets it up up front, and `cd companion && pip install -e .` still works by hand.

The binary is installed into a venv and is **not on PATH** in a fresh shell. The venv binary dir is OS-specific: `companion/.venv/bin/toolkit-companion` on macOS/Linux, `companion/.venv/Scripts/toolkit-companion.exe` on Windows.

**Never hand-roll that lookup.** `companion/ensure-companion.sh` is the single resolver every skill calls — it checks all three locations, builds the venv when the source is present but the companion was never installed, and prints the binary path (empty output = genuinely unavailable, fall back to chat):

```bash
TC="$(bash "$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh")"
```

It is a no-op costing three stats once the companion exists; the first build takes ~10–30s and logs to `companion/.install.log`. `--force` retries after a failed build (failures cool down for 24h so a broken toolchain can't slow every morning). Windows users: see `docs/windows-setup.md`.

*Why it exists:* installing the companion used to be an interactive prompt in the installers, and under the documented `curl … | bash` path that `read` consumed the script's own next line and killed the installer after "Done!" had printed. Builders were left with `companion/` source, no `.venv`, and day skills that silently fell back to chat forever. Both installers now only prompt when a terminal is actually reachable and install by default otherwise (`NSLS_SKIP_COMPANION=1` opts out).

Habits live in `30-habits/habits.md`; daily ticks accumulate in `30-habits/log.md` (append-only). The streak rule is documented in `skills/close-day/SKILL.md` and implemented in `companion/streak.py`. Both must stay in sync.

**Test mode (`-t`).** `open day -t` / `close day -t` / `reset day -t` run against a throwaway, gitignored test vault (`companion-test-vault/`) so trying the companion never touches real daily notes. It's a pure `$OBSIDIAN_VAULT_PATH` redirect: `toolkit-companion test-vault` creates + seeds it and prints its path; the server flips a gold **TEST** banner whenever the vault it serves is named `companion-test-vault`; `reset day -t` calls `toolkit-companion assert-test-vault` and refuses to delete anything outside it. See `companion/testmode.py`.

## Handling Secrets (hard rule for Claude)

When a skill calls an HTTP API that reads an API key from the environment (e.g., `AIRTABLE_API_KEY`, `FATHOM_API_KEY`):

- **Never** inline the secret value in a Bash command. Patterns like `export AIRTABLE_API_KEY=patW...; python3 -c "..."` echo the literal key into the tool log, the conversation transcript on disk, and any request logs upstream. That key is then leaked even if it was previously private.
- **Always** source the env file first, then reference only the variable name:
  ```bash
  set -a; source /Users/claw/.claude/local-plugins/nsls-personal-toolkit/.env; set +a
  python3 -c "import os; print(len(os.environ['AIRTABLE_API_KEY']))"
  ```
  Only the variable *name* appears in the command; the value stays in the file.
- If a skill's example shows an inline `export` or pastes a literal key, treat that as a bug in the skill — fix it before running, don't reproduce it. Flag it to the user.
- Gates matter. If a skill says "skip this section unless `slt_member: true`," check the gate *before* touching the relevant env var or making the call. Don't run the API step for non-applicable users — it can't succeed, and the attempt can leak the key.

This rule applies to every skill in this toolkit and overrides any inline example that contradicts it.

## Strategy Layer (Optional)

Your first `/open-week` will offer to set up a **strategy layer** — a system that connects your daily/weekly planning to company goals and personal strategy:

- **Operating memo** — "I Do / I Don't / My Traps" generated from your behavioral data
- **Personal profile** — your strengths, energy patterns, values, and working genius
- **Project stack ranking** — weekly priority ordering connected to LOPs
- **Push/protect modes** — are you advancing strategy or stabilizing?
- **Meeting coaching** — are you in too many meetings? Which ones should you challenge?

Run `/self-insight` to generate your operating memo and personal profile. Once created, all the daily/weekly skills read from them to provide personalized coaching.

**This is opt-in.** Everything works without it — just less smart.

## Customizing

Edit any `skills/<name>/SKILL.md` file — or just tell Claude what you want changed ("make close-day skip the Slack section") and it will edit the file for you.

Common modifications:
- **Don't use Obsidian?** Change the vault path in `log` and `close-day` to write wherever you keep notes (Google Docs, Notion, plain files)
- **Want a simpler daily close?** Strip out the Familiar and Slack sections from `close-day`
- **Different time tracking?** Modify `close-week` to output your team's format
- **Don't want any of this?** Delete the whole plugin. The org toolkit works independently.

## How Updates Reach a Builder

`hooks/hooks.json` registers a **SessionStart** hook that `git pull --ff-only`s the
plugin dir on every Claude Code session start, then syncs skill pointers into
`~/.claude/skills/`. `install.sh` clones from `thensls/nsls-personal-toolkit` by
default (override with `NSLS_PERSONAL_REPO`), so for a standard install `origin`
*is* upstream and a merge to `main` reaches everyone on their next session.

Two things to know:

- **`hooks/session-start.py` was unregistered for a long time.** Nothing pointed at
  it — not `install.sh`, not `install.ps1`, not `plugin.json` — so the toolkit never
  actually auto-updated and every fix had to be pulled by hand. `hooks/hooks.json`
  is what wires it in. Don't delete that file assuming it's redundant.
- **An existing install can't self-update into having this hook** — it has to arrive
  by pull first. Anyone installed before it shipped needs one catch-up:
  ```bash
  git -C ~/.claude/local-plugins/nsls-personal-toolkit pull --ff-only
  ```
  After that, updates flow on their own.

`--ff-only` refuses on a dirty tree or a diverged branch, and `## Customizing`
below actively invites editing skills in place — so that's a normal state, not an
edge case. It used to fail silently; now the hook prints one line naming the
reason. If you edit skills locally, commit your changes so fast-forwards keep
working.

## Keeping Your Fork Updated

If you run your own fork, you can pull template improvements selectively:
```bash
git remote add upstream https://github.com/thensls/nsls-personal-toolkit.git
git fetch upstream
git diff upstream/main -- skills/<skill-name>/SKILL.md  # see what changed
git checkout upstream/main -- skills/<skill-name>/SKILL.md  # pull one skill
```

Or don't. Your fork is yours.
