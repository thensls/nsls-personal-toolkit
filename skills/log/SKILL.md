---
name: log
description: >-
  Log session progress to Obsidian project notes — captures what was built,
  decisions made, and what's next. Run at the end of working sessions to keep
  project docs current. Use when the user says "log this", "save progress",
  "update the project doc", "obsidian log", "capture what we did", "write up
  this session", "end of session", or /log. Detects the active project from
  pwd or asks the user. Writes reverse-chron entries to the project's living
  doc in the Obsidian vault.
---

# Obsidian Project Logger

Log progress, decisions, plans, and next steps from a working session into the correct Obsidian project file. Works for any project — skill files, new ideas, ongoing builds.

## When to use

Run `/log` at the end of a working session (or any point mid-session) to capture:
- What was built or changed
- Key decisions and design choices made
- Current plan and architecture
- Open to-dos and next steps
- Optimizations, ideas, open questions

Also use when **starting a brand-new project** — the skill will scaffold a new project file and capture the initial design intent.

---

## Vault location

Resolve the vault in this order:
1. `OBSIDIAN_VAULT_PATH` from `~/.claude/local-plugins/nsls-personal-toolkit/.env` (what `/personal-setup` writes).
2. The `OBSIDIAN_VAULT_PATH` environment variable, if already set.
3. **macOS only, as a last resort:** `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/<vault>` (the default iCloud Obsidian location). This path does **not** exist on Windows/Linux — never gate on it there (the old macOS-only detection made Windows users silently get "no Obsidian").

**If none resolves, STOP and say so explicitly — never skip silently:**
> No Obsidian vault found. Set `OBSIDIAN_VAULT_PATH` — run `/personal-setup`, or on Windows `setx OBSIDIAN_VAULT_PATH "C:\path\to\vault"` (or add it to the toolkit `.env`) — then re-run `/log`.

Project logs live at:
```
$OBSIDIAN_VAULT_PATH/20-projects/[project-slug]/sessions/YYYY-MM-DD.md
```

Each project also has a **home note** at:
```
$OBSIDIAN_VAULT_PATH/20-projects/[project-slug]/[project-slug].md
```
with YAML frontmatter (`status`, `next-action`, `last-touched`).

---

## Step-by-step execution

### Step 1: Identify the project

Check (in order):
1. **Explicit name** — did the user name the project in the invocation? (e.g., `/log for people-ops`)
2. **Working directory** — run `pwd` and check if it matches a known project directory
3. **Conversation context** — scan recent messages for directory paths, skill names, project names
4. **Ask** — if still ambiguous, list the directories under `$OBSIDIAN_VAULT_PATH/20-projects/` and ask which one, plus offer "New project"

**🛑 Confidence gate — a wrong guess here silently corrupts a project's history.** Signals 1 and 2 are *identifying*: an explicit name, or a `pwd` that resolves to a repo you can map to exactly one project. Signal 3 is *suggestive only* — never sufficient on its own.

Before writing anything, state the chosen slug and which signal produced it, then apply these rules:

- **`pwd` is the home directory** (`$HOME`, e.g. `/Users/<name>`) — this is **not** a project match. A home-dir session is the single most common cause of misfiling, because every repo path in the transcript looks equally plausible. Skip to step 4 and ask.
- **Signal 3 alone → ask.** Do not write off conversation context unless exactly one candidate project matches and the match is an exact slug or repo name, not a topical resemblance. Two plausible candidates means ask.
- **Never fall back to the last-used or most-recently-touched project.** Absence of a signal is not evidence for the previous answer.
- **Content sanity check (run this even when confident).** Compare the session content you are about to write against the target project's home note — its title, `## Sessions` history, and stated scope. If the dominant repo, product surface, or topic of this session does not appear anywhere in that project's existing history, **stop and ask.** A session about `market-exploration` does not belong in a project whose history is entirely about onboarding documentation.
- **Home-note `next-action` guard.** You are about to overwrite `next-action` on the home note. If the new `next-action` names a repo, service, or deliverable that appears nowhere else in that project's note, that is proof the project is wrong. Stop and ask.

When you ask, show your best guess first with its reasoning, so confirming is one word.

If it's a **new project** → go to **New Project flow** (Step 2A).
If it matches an **existing project** → go to **Existing Project flow** (Step 2B).

---

### Step 2A: New Project flow

**2A-1. Confirm project details**
Ask:
- What should we call this project? (offer a slug from context as default)
- What is it trying to accomplish? (1-2 sentences)
- What's the approach or design philosophy?
- What are the first to-dos?

**2A-2. Create the Obsidian home note**

Create `$OBSIDIAN_VAULT_PATH/20-projects/[slug]/[slug].md`:

```markdown
---
status: active
priority: 3
energy: medium
domain: [personal-productivity | nsls | slt-ops | people-ops | personal]
blocked-by:
next-action: ""
last-touched: YYYY-MM-DD
---

# [Project Display Name]

## What This Is
[Brief description]

## Current Phase
Starting

## Key Decisions
-

## Open Questions
-
```

**2A-3. Create the first session log**

Create `$OBSIDIAN_VAULT_PATH/20-projects/[slug]/sessions/YYYY-MM-DD.md`:

```markdown
Parent: [[project-slug]]

# Session: YYYY-MM-DD

## What Was Done
- Initial project setup — defined scope and approach

## Still Open
- [first open items]

## New Decisions
- [key initial design choices]

## New Ideas
- [ideas to explore]

## Next Action
[Single most important next step]
```

**2A-4. Confirm and write**
Show the draft home note and first session log. Write after confirmation.

---

### Step 2B: Existing Project flow

**2B-1. Read the current session log (if any)**
Check if `sessions/YYYY-MM-DD.md` already exists for today. If yes, mode is append (add a separator `---`). If no, mode is create.

**2B-2. Synthesize this session's entry**
Review the conversation and extract:
- **What Was Done**: concrete bullets of what was actually accomplished
- **Still Open**: unfinished items, blockers, open threads
- **New Decisions**: choices made and why (this is the most important section)
- **New Ideas**: worth capturing for later
- **Next Action**: single most important next step — imperative, specific

**2B-3. Show draft and confirm**
Present the draft session log. Write after approval (or inline edits).

**2B-4. Update home note YAML**
After writing the session log, update the home note:
- `last-touched: YYYY-MM-DD`
- `next-action: "[Next Action text]"`

**2B-5. Update home note Sessions list**
Add a `[[sessions/YYYY-MM-DD|YYYY-MM-DD]]` wikilink to the `## Sessions` section of the project home note (create the section if it doesn't exist). Insert newest dates first (reverse chronological).

---

## Session log format

```markdown
Parent: [[project-slug]]

# Session: YYYY-MM-DD

## What Was Done
- [concrete bullet]
- [concrete bullet]

## Still Open
- [unfinished item or blocker]

## New Decisions
- [decision made and why]

## New Ideas
- [idea to explore later, or "None"]

## Next Action
[Single imperative sentence — what a future session should do first]
```

Rules:
- **Specific and factual** — not "worked on things", but "renamed 34 files from `work-journal/` to `quick-notes/`"
- **Next Action** is the most time-sensitive — it should be actionable immediately without reading the rest
- **New Decisions** is the institutional memory — capture the *why*, not just the *what*
- 3-5 bullets per section is ideal — not a novel

---

## After writing

Confirm: "Logged to `20-projects/[slug]/sessions/YYYY-MM-DD.md`" and show the session log so it can be verified.

---

## Toolkit Announcement Mode

When running `/log` (or `/log --announce`) inside a toolkit repo (`nsls-personal-toolkit` or `nsls-builder-toolkit`), add an announcement step after writing the session log.

### Detection

Check `pwd` or `git remote -v`. If the repo is:
- `thensls/nsls-personal-toolkit` → target: `personal`
- `thensls/nsls-builder-toolkit` → target: `builder`

If neither, skip this section entirely.

### Announcement Flow

1. Check what skills or files were modified: `git diff --name-only HEAD~1` (or session context)
2. If `/log --announce` was used, skip the question. Otherwise ask:
   > "This session modified **[skill names]**. Create an announcement for [toolkit] users? They'll see it next time they open Claude Code."
3. If yes:
   - Generate a concise announcement:
     - **Title**: "New/Updated: [skill name]" (under 60 chars)
     - **Body**: 1-2 sentences — what changed and why it matters. End with the command to run.
     - **Command**: `/update-personal-productivity` (for personal toolkit changes)
   - Call `POST https://web-production-6281e.up.railway.app/announcement`:
     ```json
     {
       "title": "New skill: /learn",
       "body": "Personal learning management with scaffolded paths and progress tracking. Run /update-personal-productivity to grab it.",
       "target_toolkit": "personal",
       "command": "/update-personal-productivity"
     }
     ```
   - Confirm: "Announcement created. Active [toolkit] users will see it on their next session."
4. If no: skip, log as normal.
