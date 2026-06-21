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
2. **Folder:** cowork allows **one** folder — mount the **vault** (`/Users/claw/Obsidian/DW`). The repo doesn't need to be mounted for Phase 0; the probes are self-contained pasteable prompts.
3. **No custom instructions.** The shipped product never relies on custom instructions — the rules live in the installed `open-day`/`close-day` skill (Builder Toolkit install). For Phase 0 you just paste the probe prompts into chat. See [`project-instructions.md`](project-instructions.md) for the probe prompts and where the contract actually lives.

> If cowork asks you to configure an MCP filesystem server instead of mounting a folder directly, that's fine — point it at `/Users/claw/Obsidian/DW`. The diagnostic below works the same either way; it's testing the *capability*, not the mechanism.

---

## Step 1.5 — Skill availability (decides the delivery model)

Before the plumbing probes, learn whether cowork loads the installed toolkit skills. Paste:

> Without running it: is there an `open-day` (or `/open-day`) skill available to you right now? If so, where is it loaded from — quote the path (is it under `~/.claude/`?). I want to confirm you load the installed Personal Productivity Toolkit skills.

**Answered 2026-06-21:** Cowork does NOT read `~/.claude/` or our worktree. It loads skills from its own read-only snapshot store (separate registry from Claude Code), populated by installed marketplace **plugins** or **ZIP uploads** (Customize → Skills). Our `open-day`/`close-day` are absent from Cowork until packaged in. Shipped model = publish a Cowork marketplace plugin (org plugins surfaced first). Dev loop = iterate in Claude Code → ZIP the skill folder → upload → fresh Cowork session. **None of this blocks Phase 0** (plumbing only; the counter is pasted into chat).

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

## Shared core — DONE (built in parallel, on branch `pp-cowork-companion`)

The shared core is complete and tested (180 passing). None of it touches the artifact UI, so the Phase 0 gate is respected:

- **Phase 1.3 ✅:** `status: planning | active | closed` frontmatter shipped — `parse_frontmatter`/`set_frontmatter`, `_detect_day_state` prefers it (backward-compatible), companion write paths + skills set it.
- **Phase 1.2 ✅:** `cowork-artifact/streak.js` (display copy of `streak.py`) + a JS↔Python parity test over the six canonical sequences.
- **Phase 1.1 ✅ (decision):** "Claude parses, artifact renders." Claude parses the note in Python, seeds the artifact with clean JSON; the artifact renders JSON and emits JSON on save. No second markdown parser in JS — only the streak math is shared (1.2).

**Caveat:** this lives on `pp-cowork-companion`, NOT anywhere Cowork loads. Cowork only ingests a skill via a marketplace plugin or a ZIP upload (Customize → Skills) — there's no live bridge from the worktree. Doesn't matter for Phase 0 (plumbing only; counter is pasted into chat). At Phase 3 (wiring the real cowork skill) we'll package + upload (dev) or publish a plugin (ship).

## After Phase 0 passes — what unblocks

Once Probe C (the counter round-trip) works, we know the artifact→Claude→vault save mechanism and can build the real `cowork-dashboard` artifact (Phase 2). The skill-availability answer (Step 1.5) confirms the delivery model: rely on the installed skill, no custom instructions.
