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
| `/person-intelligence` | Build relationship profiles, track 1:1 context |
| `/reset-day` | Start today over — clears today's note so `/open-day` rebuilds it from your real data (`--close-only` keeps the morning plan) |
| `/person-intelligence` | Build relationship profiles, track 1:1 context, biweekly sweep, team-pulse digest, manager-coaching frame (Thrive + How I Work With), managing-up frame for your manager, coaching-action surfacing in /open-day and /open-week |
| `/role-coach` | Coaching from your seat — reads the role you have (and optionally the role you want), diffs stated priorities against what actually happened, and keeps a pattern ledger so advice compounds. Evidence scoped to your access: ICs see only their own data, managers their team, execs org-wide. Wired into close-day/close-week/open-day/open-week |
| `obsidian-setup` | Set up an Obsidian knowledge base |

## Web Companion

The companion runs at `http://localhost:7777`. It is optional — install with `install.sh` or `cd companion && pip install -e .`.

The binary is installed into a venv and is **not on PATH** in a fresh shell. The venv binary dir is OS-specific: `companion/.venv/bin/toolkit-companion` on macOS/Linux, `companion/.venv/Scripts/toolkit-companion.exe` on Windows. To run it: invoke that full path, activate the venv first, or (Unix) symlink it to `~/.local/bin/`. Skills resolve the correct path automatically — see open-day Step 8 for the platform-aware lookup. Windows users: see `docs/windows-setup.md`.

Habits live in `30-habits/habits.md`; daily ticks accumulate in `30-habits/log.md` (append-only). The streak rule is documented in `skills/close-day/SKILL.md` and implemented in `companion/streak.py`. Both must stay in sync.

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

## Keeping Your Fork Updated

If Kevin adds improvements to the template, you can pull them selectively:
```bash
git remote add upstream https://github.com/thensls/nsls-personal-toolkit.git
git fetch upstream
git diff upstream/main -- skills/<skill-name>/SKILL.md  # see what changed
git checkout upstream/main -- skills/<skill-name>/SKILL.md  # pull one skill
```

Or don't. Your fork is yours.
