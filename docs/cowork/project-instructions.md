# Cowork — Phase 0 testing notes (NOT custom instructions)

> **Read this; don't paste it.** Earlier drafts framed this file as text to paste into a
> cowork project's custom-instructions field. That was wrong for the product: **the shipped
> user never sets custom instructions.** They install the Builder Toolkit (which installs the
> Personal Productivity Toolkit skill), and the rules ride inside the `open-day` / `close-day`
> skill — one skill, surface-detected, same rules on every surface. Custom instructions would
> be a second, drifting source of truth, which the spec's non-negotiables explicitly forbid.
>
> So this file is now just **what to know when running the Phase 0 probes**, plus where the
> real rules live. The probes themselves are self-contained pasteable prompts (below) — they
> need no project config at all.

## Where the rules actually live (the contract — for reference, not pasting)

These are enforced by the `open-day` / `close-day` skill, the companion code, and the tests —
not by anything the user configures:

1. **Identical markdown contract.** A day planned in cowork opens cleanly in the CLI/web
   companion and vice versa. No new/renamed sections.
2. **Mode is explicit, never inferred.** The daily note's frontmatter carries
   `status: planning | active | closed`. Read `status`; don't guess from section presence.
   (Shipped in `companion/parsers.py` + `_detect_day_state` + the skills, on branch
   `pp-cowork-companion`.)
3. **Write back ONCE, on explicit save.** No autosave/polling/background writes. State lives
   in the artifact during the session; whole file written back only on save / lock-in / close.
4. **Whole-file replace.** On save, re-read the note, apply the artifact's changes to the
   parsed sections, write the whole file back (last-writer-wins). Never clobber
   close-day-only sections you didn't touch.
5. **Quiet output.** One short summary line per data source. No raw tool-output dumps.

## How cowork loads skills (verified 2026-06-21 — earlier drafts had this wrong)

Cowork does **NOT** read `~/.claude/` or any repo/worktree on disk. Cowork and Claude Code
have **separate plugin registries** in the desktop app. Cowork's skill cache is a read-only,
install-time **snapshot** (`~/Library/Application Support/Claude/local-agent-mode-sessions/...`);
in-session edits don't hot-reload. A skill reaches Cowork only via (1) an installed marketplace
**plugin**, or (2) a **ZIP upload** at Customize → Skills (the skill *folder* zipped; re-upload
replaces). Cowork can also author one in-place via its native `skill-creator` — effective next
session.

So our in-progress work (worktree `~/dev/nsls-personal-toolkit-cowork`, branch
`pp-cowork-companion`) is **not visible to Cowork** until we package it in. For **Phase 0 this
doesn't matter**: the probes test plumbing and the counter artifact is pasted straight into
chat (no packaging). The dev loop for the real skill (Phase 3): iterate in Claude Code → ZIP
the skill folder → upload at Customize → Skills → fresh Cowork session. Shipping: publish as a
Cowork marketplace plugin (org plugins are surfaced first).

## Phase 0 setup (minimal)

1. Cowork project mounted on the **vault** only: `/Users/claw/Obsidian/DW`. (Cowork allows one
   folder — the vault is the one that matters; the repo doesn't need to be mounted for Phase 0.)
2. **No custom instructions.** Paste the probe prompts below directly into the chat.

## The four Phase 0 probes (paste each, report back)

**Probe A — skill availability (resolves how delivery works):**
> Without running it, tell me: is there an `open-day` (or `/open-day`) skill available to you
> right now, and if so, where is it loaded from — a path under `~/.claude/`? Quote the path if
> you can. I want to know whether you load the installed Personal Productivity Toolkit skills.

**Probe B — file access (Phase 0.3):**
> Create a file at `50-reference/cowork-test.md` with exactly two lines: `roundtrip-ok` and the
> current date+time. Read it back verbatim. Then delete it and confirm it's gone. Tell me
> exactly which tool(s) you used to write, read, and delete (tool names), and whether any extra
> permission prompt appeared.

**Probe C — counter round-trip (Phase 0.2, THE GATE):**
> Use the prompt + JSX in `cowork-artifact/counter-test.md`. Report how the counter value
> reached you (auto via an API — which one? — or manual copy) and whether
> `50-reference/cowork-counter.md` got written with the right number.

**Probe D — surface signal (Phase 0.1):**
> What is your runtime environment — "Claude Desktop / cowork" or "Claude Code"? Is there any
> tool, env var, or marker a skill could check to reliably tell which one it's running in?
