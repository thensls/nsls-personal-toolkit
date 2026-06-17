# Cowork Companion — Phase 0 Setup & De-risk

**Audience:** Davo, setting up the Claude Desktop (cowork) project that will host the cowork companion.
**Goal of Phase 0:** before any real UI is built, prove three things in a *real* cowork session:

- **0.3 — File access:** cowork can read **and** write the Obsidian vault (whole-file replace).
- **0.2 — Write-back round-trip:** an artifact can hand its state back to Claude, who writes it to a vault file in one turn.
- **0.1 — Surface signal:** a reliable way for `open-day`/`close-day` to know they're in cowork vs Claude Code.

**Hard gate (from the build plan):** do not build the real artifact UI until the 0.2 write-back round-trip works in a real cowork session. "Works in my environment" ≠ "works for the user."

---

## Paths on this machine

| What | Path |
|---|---|
| Obsidian vault (runtime data — daily notes, habits, log) | `/Users/claw/Obsidian/DW` |
| Toolkit repo (skills, artifact source, streak.js, tests) | `/Users/claw/.claude/local-plugins/nsls-personal-toolkit` |

The companion's *job* is to read/write the **vault**. The **repo** is where the build outputs live.

---

## Step 1 — Create the cowork project

1. New project in Claude Desktop (cowork). Name it something like **"Daily Companion (vault)"**.
2. **Folder(s) to give it:**
   - **If cowork lets you add more than one folder:** add the **vault** (`/Users/claw/Obsidian/DW`) as primary, and the **repo** (`/Users/claw/.claude/local-plugins/nsls-personal-toolkit`) as secondary.
   - **If it only allows one folder:** open it on the **vault** (`/Users/claw/Obsidian/DW`). I'll deliver the skill + artifact as pasteable instructions, so the repo doesn't need to be live-mounted.
3. Paste the contents of [`project-instructions.md`](project-instructions.md) into the project's custom instructions.

> If cowork asks you to configure an MCP filesystem server instead of mounting a folder directly, that's fine — point it at `/Users/claw/Obsidian/DW`. The diagnostic below works the same either way; it's testing the *capability*, not the mechanism.

---

## Step 2 — Run the file-access diagnostic (Phase 0.3)

This is the single most important thing to learn first: **can cowork read and write the vault, and by what mechanism?** Paste this to the cowork agent in the new project:

> Create a file at `50-reference/cowork-test.md` containing exactly two lines: `roundtrip-ok` and the current date+time. Then read the file back and show me its contents verbatim. Then delete the file and confirm it's gone. After you're done, tell me **exactly which tool(s)** you used to write, read, and delete (the tool name) — I need to know whether file access is a native folder mount, an MCP filesystem server, or something else.

**Report back to me (the build side):**
- ✅/❌ Could it write? read? delete?
- The **tool name(s)** it used (e.g. `Filesystem:write_file`, a native file tool, a bash-style tool).
- Whether it needed any extra permission prompt.

That answer resolves Phase 0.3 **and** tells us the write-granularity story (whole-file replace vs patch) — it determines how the real save step is written.

---

## Step 3 — Counter artifact round-trip (Phase 0.2)

Once Step 2 confirms write access, test the artifact→Claude→vault hand-back with the trivial counter in [`../../cowork-artifact/counter-test.md`](../../cowork-artifact/counter-test.md). Instructions for running it are in that file. This is the gate: if the counter value can make it from the artifact into `50-reference/cowork-counter.md`, the model works.

---

## Step 4 — Surface signal (Phase 0.1)

While you're in the session, ask the cowork agent:

> What is your runtime environment? Are you "Claude Desktop / cowork" or "Claude Code"? Is there any tool, env var, or marker you can check that would let a skill reliably tell which one it's running in?

Report what it says. Until we have a clean signal, the skills fall back to the explicit `open day cowork` override + `companion_surface` in `builder-profile.md` (already the spec's plan).

---

## What I'm doing in parallel (no Desktop needed)

While you set this up, I'm building the **shared core** in the repo — all testable here, benefits both surfaces:

- **Phase 1.3:** add `status: planning | active | closed` frontmatter to the daily-note contract; teach the CLI's `_detect_day_state` to prefer it (backward-compatible). This is the clean mode signal cowork needs and it's still unshipped on the CLI side.
- **Phase 1.2:** `streak.js` (display copy of `streak.py`) + a JS↔Python parity test over the six canonical sequences.
- **Phase 1.1:** lock the data flow — Claude parses the note in Python, seeds the artifact with clean JSON; the artifact renders JSON and emits JSON on save. No second markdown parser in JS.

None of that touches the artifact UI, so the Phase 0 gate is respected.
