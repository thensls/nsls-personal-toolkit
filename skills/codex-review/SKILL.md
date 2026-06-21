---
name: codex-review
description: >-
  Get a second opinion from OpenAI Codex (a different AI model) on code, a
  design/architecture doc, a plan, or the current branch's changes. Use when you
  want an independent reviewer's eyes on work before committing to it — Claude
  wrote it, Codex critiques it. Trigger phrases: "codex review", "/codex-review",
  "get a codex review", "have codex look at this", "second opinion from codex",
  "what does codex think", "independent review". Runs Codex headless and
  read-only (it cannot modify your files) and reports back what it found.
---

# Codex Review

Run **OpenAI Codex** headless as an independent reviewer and relay its findings.
Useful when Claude produced something — code, a spec, an architecture, a plan —
and a different model's perspective would catch what the author is blind to.
Codex runs **read-only**: it can read the repo but never edits, commits, or runs
destructive commands.

## When to use

- Before locking in an architecture or design doc (review the thinking, not just code).
- After implementing a change, before it ships (review the diff).
- When the user can't evaluate the work themselves and wants a cross-check.
- Any time the user asks for "another agent's eyes."

## Prerequisites (check once)

```bash
command -v codex   # must resolve; if not, tell the user Codex CLI isn't installed
```

Codex must be logged in (`codex login` — the user does this once, interactively;
the skill does not handle auth). If a run errors with an auth message, tell the
user to run `codex login` and stop.

## Choosing the mode

Pick based on **what** is being reviewed:

| What you're reviewing | Use |
|---|---|
| Uncommitted changes (working tree) | `codex review --uncommitted` |
| The branch vs a base | `codex review --base <branch>` |
| One commit | `codex review --commit <sha>` |
| **A specific file, a doc, an idea, an architecture** | `codex exec -s read-only` with a targeted prompt |

`codex review` is git-diff oriented — best for "critique these code changes."
`codex exec` is the flexible path — best for "read this file/doc and critique the
*approach*," which is the common case for design/spec/architecture review.

## Running it (the exact invocations)

**Always** run from the repo root, read-only, with color off so the output is clean.

### A. Review a design/spec/architecture doc or a specific file (most common)

Pipe the instructions on stdin so nothing sensitive lands in the process args, and
name the exact file(s) for Codex to read:

```bash
cd <repo-root>
cat <<'PROMPT' | codex exec -s read-only --skip-git-repo-check --color never - 2>&1 | tee /tmp/codex-review.txt
You are an independent reviewer. Read <path/to/file> in this repo and critique it.
Focus on: <the specific concerns — correctness, gaps, risky assumptions, simpler
alternatives, anything the author likely missed>. Be concrete and cite line/section.
Do NOT propose edits to make — just review. End with the 3 most important issues,
ranked.
PROMPT
```

### B. Review the current branch's changes (code already written)

```bash
cd <repo-root>
codex review --uncommitted 2>&1 | tee /tmp/codex-review.txt
# or, against the main branch:
codex review --base main 2>&1 | tee /tmp/codex-review.txt
```

You may pass custom review instructions as the prompt arg (or `-` for stdin):

```bash
echo "Focus on the status-frontmatter contract and the sendPrompt save path." \
  | codex review --uncommitted - 2>&1 | tee /tmp/codex-review.txt
```

## Reading the output (important gotchas — several learned the hard way)

- Codex prints a **header block** (workdir, model, sandbox, session id), then its
  **reasoning + every tool call it runs** (it greps/reads files itself — pages of
  `exec` blocks and file dumps), then the **final prose verdict**, then a
  **`tokens used`** footer. Only the final verdict matters; everything before it is
  process noise.
- **The final verdict can be long, and naive capture truncates it.** Piping through
  `tee FILE | tail -N` keeps only the last N lines of the *whole stream* — which is
  often Codex's last file-dump, NOT its conclusion. **Two reliable ways to get a
  clean verdict:**
  1. **Two-pass (recommended for big reviews):** first run the deep review (high
     effort) for the analysis; then run a SECOND cheap pass that asks ONLY for the
     conclusion — e.g. `-c model_reasoning_effort=low` with a prompt like *"Be terse,
     no file dumps, no preamble. Give ONLY a ranked list (max 6) of issues, one line
     each: file:line — issue — why it matters. End with the single highest-priority
     fix."* The terse pass's output fits in `tail` cleanly.
  2. **Ask for the verdict last and structured:** end the review prompt with *"End
     with a section headed `## VERDICT` containing the ranked issues"*, then extract
     from `## VERDICT` to end of file rather than `tail`-ing blindly.
  - If you do capture to a file and it's huge, don't `tail` it — grep for the verdict
    header / the last `codex` block, or Read the file's final ~120 lines with the
    Read tool.
- A line like `ERROR codex_core::session: failed to record rollout items: thread
  ... not found` is a **harmless telemetry warning**. The review still completed.
- **`pytest` is NOT on PATH inside Codex's sandbox.** Codex may try to run the tests
  itself and get `command not found: pytest` — that's expected and harmless; it just
  means Codex reviewed statically. Don't ask Codex to run this repo's tests; run them
  yourself (via the venv python) if you want a test result.
- Runs take 1–2 min at default (high/xhigh) effort. Consider launching the deep pass
  with `run_in_background: true` so you're not blocked; you'll be notified on exit.
  Don't poll aggressively.
- Default model is whatever the user's `~/.codex/config.toml` selects (e.g.
  `gpt-5.5`). To force one: `-m <model>`.

## Relaying findings (the actual job)

Don't dump raw Codex output on the user. Read `/tmp/codex-review.txt`, then:

1. **Summarize Codex's verdict** in 2-4 lines — does it agree, what's its headline concern.
2. **List the substantive findings**, each with: the issue, whether you agree, and
   what you'd do about it. **You are allowed to disagree with Codex** — you wrote
   the work and have context it lacks. Say so explicitly when you do, with reasoning.
3. **Separate signal from noise.** Codex sometimes flags style nits or things that
   don't apply to this codebase's conventions. Call those out as low-priority.
4. If Codex found a real problem, fold the fix into the plan; if it's wrong, say why
   and move on. Either way the user gets a clear "here's what the second opinion
   said and here's what I'm doing with it."

## Safety / boundaries

- Codex runs `-s read-only` — it cannot modify, commit, push, or run destructive
  commands. Never escalate to `workspace-write` or
  `--dangerously-bypass-approvals-and-sandbox` for a review.
- A review reads code/docs that may be private. That's fine — Codex runs locally
  under the user's own login; it's not "sharing with a person." But do not pipe
  secrets (`.env` contents, keys) into the prompt — review the code that *uses* a
  secret, never the secret value (toolkit secret-handling rule still applies).
- This skill only *reads and reports*. It never applies Codex's suggested changes
  automatically — Claude decides what to act on, and edits go through the normal flow.
