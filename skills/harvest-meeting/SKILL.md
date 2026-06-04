---
name: harvest-meeting
description: Harvest decisions, project definitions, and state changes from meetings into a knowledge base. SLT members write to the shared company KB (thensls/nsls-knowledge); everyone else builds a local, private KB (never pushed). Use when you've just finished a strategic meeting, want to backfill a specific Fathom URL, or as part of close-day Step 4c / close-week Step 2b.
---

# Harvest Meeting — NSLS Knowledge Base Pipeline

Pulls decisions, project definitions, and state changes from recorded meetings, gates them through the employee-facing sensitive-content rubric, and proposes precise edits to topic files. Routing is automatic: SLT members (on `kb_authors.txt`) write to the shared company KB (`60-nsls-knowledge`) and push to `main`; everyone else writes to a local, private KB (`60-nsls-knowledge-local`) that is committed locally and never pushed.

## First-Time Setup (read before you clone)

> ⚠️ **The GitHub repo is `thensls/nsls-knowledge` — NOT `60-nsls-knowledge`.**
> The `60-` prefix is only the *local Obsidian vault folder name* this skill clones into.
> Cloning `60-nsls-knowledge` fails with "Repository not found" — and on a private repo,
> "not found" also means *you don't have access yet*. If the clone command below 404s,
> ping Kevin to be added as a collaborator on `thensls/nsls-knowledge`.

> **This setup applies only to SLT members writing to the company KB.** Non-SLT users need
> no setup — the local KB is scaffolded automatically on first run.

One-time setup for a new SLT writer:

```bash
# 1. Clone the repo (nsls-knowledge) INTO the folder the skill expects (60-nsls-knowledge)
git clone https://github.com/thensls/nsls-knowledge.git "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge"

# 2. Set this clone's commit identity to your @nsls.org email so harvest commits are
#    attributed to you AND the SLT writer gate matches via the kb-repo scope (Step 0).
git -C "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge" config user.email <you>@nsls.org
```

Prerequisites (both are quick adds — ask Kevin):
- Your `@nsls.org` email is in `kb_authors.txt` (same directory as this skill).
- Your GitHub account is a collaborator on `thensls/nsls-knowledge`.

## Modes

| Mode | When | Source |
|---|---|---|
| `--date YYYY-MM-DD` | close-day Step 4c | All Fathom meetings for the date |
| `--fathom-url <url>` | Manual after important meeting | Single meeting |
| `--week-audit --week YYYY-Www` | close-week Step 2b | Git log + topic files for the week |

## Allowlist → routing (not a write gate)

`kb_authors.txt` (same directory as this SKILL.md) lists SLT members. It no longer gates
whether you can write — it decides **where** writes go:

- **On the allowlist** → company KB (`thensls/nsls-knowledge`), committed and pushed to `main`.
- **Not on the allowlist** → a self-contained **local KB** (`60-nsls-knowledge-local` in your
  vault), committed locally and never pushed. First run scaffolds it from an org-level seed.

Identity is resolved cwd-independently in Step 0 (same logic as before). Everyone gets a
working harvest; SLT membership only changes the destination.

## Step 0: Mode dispatch + allowlist routing

Parse arguments to determine mode (`--date`, `--fathom-url`, or `--week-audit`).

Then check whether the current user is an SLT writer.

**Identity resolution must be cwd-independent.** `git config user.email` with no scope reads
the config for the *current working directory*. close-day invokes this skill from the user's
home directory, which is usually not a git repo, so a bare `git config user.email` silently
falls back to the global config — which may be a personal email that isn't in the allowlist.
That produced a silent skip of the entire harvest. To avoid it, gather candidate identities
from every stable scope (the KB repo, global, the toolkit repo, `$GIT_AUTHOR_EMAIL`, and the
personal-toolkit `.env` `BUILDER_EMAIL`/`OPERATING_USER_EMAIL`) and treat the user as an SLT
writer if **any** candidate is in the allowlist.

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 -c "
import os, subprocess, sys, pathlib, re

# Locate the allowlist (handle both repo-clone and plugin-install paths)
candidates_paths = [
    pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt',
    pathlib.Path.home() / '.claude/plugins/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt',
]
# HARVEST_AUTHORS_FILE lets verification runs point at a temp allowlist.
override = os.environ.get('HARVEST_AUTHORS_FILE')
authors_file = pathlib.Path(override) if override and pathlib.Path(override).exists() else next((p for p in candidates_paths if p.exists()), None)
if not authors_file:
    print('FATAL: kb_authors.txt not found in any known path')
    sys.exit(2)
authors = {line.strip() for line in authors_file.read_text().splitlines()
           if line.strip() and not line.startswith('#')}

def git_email(*scope):
    try:
        return subprocess.check_output(['git', *scope, 'config', 'user.email'],
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ''

def env_file_email(path, *keys):
    try:
        text = pathlib.Path(path).read_text()
    except Exception:
        return ''
    for key in keys:
        m = re.search(rf'^{re.escape(key)}=(.+)$', text, re.MULTILINE)
        if m: return m.group(1).strip()
    return ''

kb_dir = pathlib.Path(os.environ.get('OBSIDIAN_VAULT_PATH', '')) / '60-nsls-knowledge'
toolkit_dir = pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit'

# .env candidates — local-plugins symlink path first (canonical), then repo path
env_candidates = [
    pathlib.Path.home() / '.claude/local-plugins/nsls-personal-toolkit/.env',
    pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit/.env',
]
env_file = next((p for p in env_candidates if p.exists()), None)
env_email = env_file_email(env_file, 'BUILDER_EMAIL', 'OPERATING_USER_EMAIL') if env_file else ''

# cwd-independent identity scopes, in order of authority
scopes = [
    ('kb-repo',      git_email('-C', str(kb_dir))),        # identity that authors KB commits
    ('global',       git_email('--global')),
    ('toolkit-repo', git_email('-C', str(toolkit_dir))),
    ('env-var',      os.environ.get('GIT_AUTHOR_EMAIL', '')),
    ('toolkit-.env', env_email),
]
matched = [(s, e) for s, e in scopes if e and e in authors]
is_slt = bool(matched)

print('emails_checked: ' + ' | '.join(f'{s}={e or \"-\"}' for s, e in scopes))
print(f'slt_writer: {is_slt}')
if is_slt:
    print(f'matched_via: {matched[0][0]} ({matched[0][1]})')
print(f'authors_file: {authors_file}')

# Detect 'looks-like-SLT-misconfigured': any detected email is @nsls.org but none
# matched the allowlist. Usually means the allowlist is stale OR there's a typo.
# Distinct from 'genuinely non-SLT user' (no @nsls.org email anywhere) — where the
# skip is the expected behavior and no action is needed.
nsls_emails = sorted({e for _, e in scopes if e and e.endswith('@nsls.org')})
looks_misconfigured = (not is_slt) and bool(nsls_emails)
print(f'looks_misconfigured: {looks_misconfigured}')
if nsls_emails:
    print(f'nsls_emails_detected: {\", \".join(nsls_emails)}')

# --- Routing: allowlist match -> company; otherwise -> local (never skip) ---
vault = pathlib.Path(os.environ.get('OBSIDIAN_VAULT_PATH', ''))
if is_slt:
    kb_target, kb_push = 'company', True
    kb_dir = vault / '60-nsls-knowledge'
else:
    kb_target, kb_push = 'local', False
    kb_dir = vault / '60-nsls-knowledge-local'

# write_authorized is now TRUE for everyone: writes always go SOMEWHERE.
ctx_dir = pathlib.Path('/tmp/harvest-meeting-ctx')
ctx_dir.mkdir(exist_ok=True)
import json as _json
(ctx_dir / 'target.json').write_text(_json.dumps({
    'kb_target': kb_target, 'kb_dir': str(kb_dir),
    'kb_push': kb_push, 'write_authorized': True,
}, indent=2))
(ctx_dir / 'env.sh').write_text(
    f'export KB_TARGET={kb_target}\n'
    f'export KB_DIR={_json.dumps(str(kb_dir))}\n'
    f'export KB_PUSH={\"true\" if kb_push else \"false\"}\n'
)
print(f'kb_target: {kb_target}')
print(f'kb_dir: {kb_dir}')
print(f'kb_push: {kb_push}')
"
```

**Heartbeat the result** (per the skill-heartbeats rule — always print the scopes checked and
the resolved target so a future silent misroute is debuggable):

- **If `kb_target: company`** (SLT writer confirmed) →
  "Step 0: SLT writer ({matched_email} via {scope}) → company KB, pushing to thensls/nsls-knowledge."

- **If `kb_target: local` AND `looks_misconfigured: True`** (an `@nsls.org` email was detected
  but none matched the allowlist) → route to local, AND print the allowlist-gap note so a
  genuinely-SLT-but-unlisted person is never silently demoted:

  ```
  Step 0: ⚠ NSLS email detected but NOT in KB_AUTHORS — writing to your LOCAL KB
    checked: <emails_checked>
    NSLS emails detected: <nsls_emails_detected>
    local KB: <kb_dir>

    If you ARE on SLT and should be writing to the company KB, ping Kevin to add you to
    skills/harvest-meeting/kb_authors.txt and tick Members.is_slt = true, then re-run.
    If you have an @nsls.org typo, fix it in the appropriate git scope or your toolkit .env.
    Otherwise this is expected — your harvest goes to your local KB.
  ```

- **If `kb_target: local` AND `looks_misconfigured: False`** (genuinely non-SLT) →
  "Step 0: not on the SLT allowlist → writing to your local KB at <kb_dir> (not pushed)."
  This is the normal, expected path for most of the org — no setup fix needed.

In every case the pipeline continues. There is no longer a skip/abort path based on membership.

> **KB commit attribution:**
> - *Company KB:* harvest commits are authored by whatever `git -C "$KB_DIR" config user.email`
>   resolves to. Set the company clone's local identity to your NSLS email so commits are
>   attributed to you AND the allowlist matches via the `kb-repo` scope regardless of cwd:
>   `git -C "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge" config user.email <you>@nsls.org`.
> - *Local KB:* the local repo's identity is set automatically on first run (Step 1a). No
>   remote is ever configured, so a push is impossible — your local KB cannot reach the
>   company repo.

`Step 0` has stashed `/tmp/harvest-meeting-ctx/target.json` (`kb_target`, `kb_dir`, `kb_push`,
`write_authorized`) and `/tmp/harvest-meeting-ctx/env.sh`. Every later step reads these: python
blocks `json.load` the file; bash blocks `source` the `env.sh`. Do NOT re-derive the company
path anywhere downstream.

## Step 1: Load context

For `--date` and `--fathom-url` modes, load:
1. KB local clone (refresh first), topic file index, rubric
2. Current Fathom meeting data (Step 2 builds on this)

For `--week-audit` mode, load KB local clone + git log for the week (Task 11 fills this in).

### 1a. Ensure KB local clone is fresh

```bash
source /tmp/harvest-meeting-ctx/env.sh   # sets KB_TARGET, KB_DIR, KB_PUSH (from Step 0)

if [ "$KB_TARGET" = "company" ]; then
    if [ ! -d "$KB_DIR/.git" ]; then
        echo "Step 1a: FATAL — company KB not cloned to $KB_DIR."
        echo "  The repo is 'nsls-knowledge' (NOT '60-nsls-knowledge' — that's just the local folder)."
        echo "  Run: git clone https://github.com/thensls/nsls-knowledge.git \"$KB_DIR\""
        echo "  If that 404s, you need collaborator access — ask Kevin. See First-Time Setup."
        exit 1
    fi
    git -C "$KB_DIR" pull --ff-only --quiet
    echo "Step 1a: company KB synced to $(git -C "$KB_DIR" rev-parse --short HEAD)"
else
    # Local KB: scaffold on first run, never add a remote (push is impossible by design).
    SEED_CANDIDATES=(
        "$HOME/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references/local-kb-seed"
        "$HOME/.claude/plugins/nsls-personal-toolkit/skills/harvest-meeting/references/local-kb-seed"
    )
    SEED_DIR=""
    for c in "${SEED_CANDIDATES[@]}"; do [ -d "$c" ] && SEED_DIR="$c" && break; done
    if [ -z "$SEED_DIR" ]; then
        echo "Step 1a: FATAL — local-kb-seed not found in any known path."; exit 1
    fi
    if [ ! -d "$KB_DIR/.git" ]; then
        mkdir -p "$KB_DIR"
        git -C "$KB_DIR" init --quiet
        # Local-only identity; prefer a detected nsls email if present, else a generic fallback.
        WHO="$(git config --global user.email 2>/dev/null)"
        case "$WHO" in *@nsls.org) : ;; *) WHO="harvest-local@nsls.org" ;; esac
        git -C "$KB_DIR" config user.email "$WHO"
        git -C "$KB_DIR" config user.name "NSLS KB (local)"
        cp -R "$SEED_DIR"/. "$KB_DIR"/
        git -C "$KB_DIR" add -A
        git -C "$KB_DIR" commit -q -m "local KB: initial scaffold"
        echo "Step 1a: local KB created at $KB_DIR (seeded $(ls "$SEED_DIR"/*.md | wc -l | tr -d ' ') files)"
    else
        echo "Step 1a: local KB ready at $KB_DIR ($(git -C "$KB_DIR" rev-parse --short HEAD))"
    fi
    # Guard: a local KB must never have a remote.
    if git -C "$KB_DIR" remote | grep -q .; then
        echo "Step 1a: ⚠ local KB unexpectedly has a remote — refusing to proceed."; exit 1
    fi
fi
```

### 1b. Load topic index and rubric

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import os, pathlib, re, json

_t = json.loads(pathlib.Path('/tmp/harvest-meeting-ctx/target.json').read_text())
kb_dir = pathlib.Path(_t['kb_dir'])

# Parse frontmatter + body for every topic file
topics = {}
for md_file in kb_dir.glob('*.md'):
    if md_file.name.startswith('_'): continue  # _index.md, etc.
    text = md_file.read_text()
    fm_match = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.DOTALL)
    if not fm_match: continue
    fm_raw, body = fm_match.groups()
    fm = {}
    for line in fm_raw.split('\n'):
        if ':' in line:
            k, _, v = line.partition(':')
            fm[k.strip()] = v.strip()

    # Extract Current State, Key Decisions, Open Questions sections
    sections = {'current_state': '', 'key_decisions': [], 'open_questions': []}
    cur = None
    for line in body.split('\n'):
        if line.startswith('## Current State'): cur = 'current_state'; continue
        if line.startswith('## Key Decisions'): cur = 'key_decisions'; continue
        if line.startswith('## Open Questions'): cur = 'open_questions'; continue
        if line.startswith('## '): cur = None; continue
        if cur == 'current_state':
            sections['current_state'] += line + '\n'
        elif cur in ('key_decisions', 'open_questions') and line.strip().startswith('-'):
            sections[cur].append(line.strip())

    topics[md_file.stem] = {
        'frontmatter': fm,
        'current_state': sections['current_state'].strip(),
        'key_decisions': sections['key_decisions'],
        'open_questions': sections['open_questions'],
    }

# Parse rubric from CLAUDE.md
claude_md = (kb_dir / 'CLAUDE.md').read_text()
rubric_match = re.search(r'## Sensitive-Content Rubric.*?(?=\n## |\Z)', claude_md, re.DOTALL)
rubric_text = rubric_match.group(0) if rubric_match else ''

print(f"Step 1b: loaded {len(topics)} topic files, rubric is {len(rubric_text)} chars")

# Stash for downstream steps
ctx_dir = pathlib.Path('/tmp/harvest-meeting-ctx')
ctx_dir.mkdir(exist_ok=True)
(ctx_dir / 'topics.json').write_text(json.dumps(topics, indent=2))
(ctx_dir / 'rubric.md').write_text(rubric_text)
print(f"Step 1b: cached context at {ctx_dir}")
PYEOF
```

**Heartbeat expected:** `Step 1b: loaded N topic files, rubric is ~5000 chars`.
- *Company KB:* expect ~60. Fewer than 40 means something is wrong with the clone — stop and check.
- *Local KB:* a freshly seeded KB legitimately has ~5 files. The count grows as you harvest, so there is no low-count alarm for local.

## Step 2: Load Fathom meetings

This step is mode-specific.

### Mode: `--date YYYY-MM-DD`

Use the Fathom MCP to list meetings for the date where the current user was a participant or owner:

```
Call: mcp__claude_ai_Fathom__list_meetings
Parameters:
  - start_date: YYYY-MM-DD
  - end_date: YYYY-MM-DD
  - owner_email: <current user.email>
```

For each returned recording_id, call `get_meeting_summary` and `get_meeting_transcript` to get the full content. Stash in `/tmp/harvest-meeting-ctx/meetings.json` as a list of:

```json
{"recording_id": "...", "title": "...", "url": "...", "summary": "...", "transcript_url": "...", "attendees": [...]}
```

Heartbeat: `Step 2: loaded N meeting(s) for YYYY-MM-DD: <comma-separated titles>`

If N == 0, heartbeat `Step 2: no meetings for YYYY-MM-DD, nothing to harvest` and exit step (the rest of the pipeline can't run with no input).

### Mode: `--fathom-url <url>`

Call `mcp__claude_ai_Fathom__get_recording_by_url` with the URL. Then `get_meeting_summary` and `get_meeting_transcript`. Stash same as above (single-item list).

Heartbeat: `Step 2: loaded 1 meeting from URL: <title>`

### Mode: `--week-audit`

Defer; this mode's data load is handled in Task 11.

## Step 3: Extract candidates

For each meeting loaded in Step 2, ask Claude to extract candidate KB entries.

**Prompt construction:** Read `references/candidate-extraction.md` for the full prompt template and examples. Substitute:
- The `[paste the never-write categories table]` placeholder with the actual rubric table from `/tmp/harvest-meeting-ctx/rubric.md`
- The `INPUT` block with the meeting's title, date, attendees, summary, and transcript

**Invocation:** Call Claude with the constructed prompt. Parse the JSON response. Expect 0–10 candidates per meeting; flag if > 15 (probably mis-parsing). Stash all candidates in `/tmp/harvest-meeting-ctx/candidates.json`:

```json
[{
  "meeting_id": "<recording_id>",
  "meeting_title": "...",
  "meeting_url": "...",
  "meeting_date": "YYYY-MM-DD",
  "kind": "...", "text": "...", "fathom_timestamp_sec": ..., "speaker": "...", "confidence": ...
}, ...]
```

**Heartbeat per meeting:**
```
Step 3: meeting "<title>" → N candidates (D decisions, P projects, S state-changes)
```

**Edge cases:**
- 0 candidates from a meeting: heartbeat "Step 3: meeting '<title>' → 0 candidates (likely not strategic)". Continue.
- JSON parse fail: heartbeat error, dump the raw response to `/tmp/harvest-meeting-ctx/extract-error-<meeting_id>.txt`, skip that meeting, continue with the rest.
- All meetings yield 0 candidates: heartbeat "Step 3: no candidates from any meeting today. Nothing to harvest." Exit cleanly.

## Step 4: Map candidates to topic files

For each candidate in `/tmp/harvest-meeting-ctx/candidates.json`, ask Claude to map it to topic file(s).

**Prompt construction:** Read `references/topic-mapping.md` for the full prompt and examples. Substitute the topic index summary using a compact form of `/tmp/harvest-meeting-ctx/topics.json` (slug, title from frontmatter, parent, first 200 chars of current_state).

**Invocation:** Call Claude once per candidate. Parse JSON. Annotate the candidate with the mapping result. Stash updated candidates back to `/tmp/harvest-meeting-ctx/candidates.json`.

**Heartbeat:**
```
Step 4: mapped N candidates → M topic files (K NEW topics, J low-confidence flagged for review)
```

**Edge cases:**
- Mapping returns invalid topic slug (typo, hallucination): re-prompt with explicit warning. If still invalid, mark candidate `mapping: ERROR` and surface in approval.
- All candidates map to the same topic: surface "Step 4: ⚠ all N candidates mapped to <topic>. Sanity-check this is real." Continue.

## Step 5: Dedup against existing topic content

For each candidate + its primary_topic, ask Claude:

```
Candidate: <candidate text>
Topic file: <topic slug>
Existing Key Decisions:
  - <list from topics.json>
Existing Current State: <text from topics.json>

Is this candidate already covered? Return JSON:
{"verdict": "NEW" | "REFINEMENT" | "DUPLICATE",
 "replace_entry": "<text>",  // only for REFINEMENT
 "reason": "<one-sentence>"}

- NEW: not covered. Add fresh.
- REFINEMENT: a similar entry exists but this candidate updates it (e.g.,
  new date, refined wording, expanded scope). The existing entry should be
  replaced by the new one.
- DUPLICATE: substantively the same as an existing entry. Drop.
```

Annotate each candidate with the dedup verdict. Drop DUPLICATEs. Mark REFINEMENTs with the existing entry to replace.

**Heartbeat:**
```
Step 5: dedup → N NEW, M REFINEMENT (replacing existing), K DUPLICATE (dropped)
```

## Step 6: Apply sensitive-content rubric

For each surviving candidate (NEW or REFINEMENT), apply the full rubric from `/tmp/harvest-meeting-ctx/rubric.md`:

```
Apply this rubric to the candidate text:

<paste full rubric from /tmp/harvest-meeting-ctx/rubric.md, including never-write
table AND reshape rules>

Candidate text: "<candidate.text>"

Return JSON:
{"verdict": "PASS" | "RESHAPE" | "DROP_UNSAFE",
 "reshape_to": "<reshaped text>",  // only for RESHAPE
 "category": "<which never-write category triggered>",  // for DROP_UNSAFE or RESHAPE
 "reason": "<one-sentence>"}
```

Annotate each candidate. DROP_UNSAFE candidates are removed from the proposal list but logged for the summary at end of approval display.

**Heartbeat:**
```
Step 6: rubric → N PASS, M RESHAPE, K DROP_UNSAFE
  Dropped categories: <comma-separated list, e.g., "individual comp (2), profit number (1)">
```

## Step 6b: Merge current_state replacements (never clobber)

A `state_change` candidate maps to `section: current_state`, which is a **whole-block replace**.
Topic files hold multi-fact narratives in Current State, so replacing the block with the
candidate's one-line summary would destroy existing context. Before approval, generate a full
merged replacement for each such candidate.

For each surviving candidate with `section == current_state`, ask Claude:

```
You are updating the Current State of an NSLS Knowledge Base topic. Produce a complete,
rewritten Current State that PRESERVES all still-true existing context and folds in the new
change. Do not drop facts that are still accurate. Do not invent detail. Apply the
sensitive-content rubric (no profit/comp/personnel/etc.).

Topic: <slug>.md
Existing Current State:
<full current_state from /tmp/harvest-meeting-ctx/topics.json>

New change (from meeting <date>): <candidate.text>
(If the rubric reshaped this candidate, use the reshaped text: <candidate.reshape_to>)

Return JSON: {"new_current_state": "<full rewritten block>",
              "dropped_context": "<anything you removed and why, or 'none'>"}
```

Store `new_current_state` on the candidate. If the model reports it dropped non-trivial context,
surface that in the approval list so the human can check.

**Heartbeat:** `Step 6b: merged N current_state replacement(s) (M flagged for dropped context)`

If Current State is empty, skip the merge — write the candidate text directly.

## Step 7: Present numbered approval list

Render the surviving candidates as a numbered list grouped by topic file, with clear diff markers. Then parse the user's response.

> **Current State diffs must show the FULL existing block** (not a truncated snippet) as the
> `-` lines, and the full `new_current_state` as the `+` lines, so clobbering or dropped context
> is visible before the user types `all`.

**Render format:**

```
Harvest candidates from YYYY-MM-DD ({M} meeting(s), {N} candidates after rubric):

[1] <topic-slug>.md → Key Decisions
    + YYYY-MM-DD: <candidate text> ([▶](<fathom_url>?timestamp=<sec>))

[2] <topic-slug>.md → Current State (REPLACE)
    - <existing text>
    + <new text>

[3] <topic-slug>.md → Open Questions
    + <candidate text>

[4] 🆕 NEW: <suggested_slug>.md (parent: <parent_slug>, type: <type>)
    + Key Decision: YYYY-MM-DD: <candidate text> ([▶](<fathom_url>?timestamp=<sec>))

[5] <topic-slug>.md → Key Decisions (RESHAPED)
    original: <original candidate text>
    reshaped: <rubric-reshape>
    category: <which never-write category drove reshape>

[?6] <topic-slug>.md → Key Decisions  (LOW CONFIDENCE — please confirm topic)
    + YYYY-MM-DD: <candidate text>
    alternatives: <secondary_topics>

⚠ N candidates dropped by rubric:
  - "<candidate text>" (<never-write category>)
  - "<candidate text>" (<never-write category>)

Approve? all / drop 1,3 / edit 2: <new text> / topic ?6: <slug> / cancel
> _
```

**Parser:** Accept input. Parse against this grammar:
- `all` → approve every numbered item (including `?` items as-is)
- `cancel` → abort, no writes
- `drop <comma-separated-numbers>` → exclude those numbers, approve the rest
- `edit <N>: <text>` → replace candidate N's text with `<text>`, then approve the rest (assumed `all` unless another action follows)
- `topic <?N>: <slug>` → resolve a low-confidence flag by picking the topic, then approve
- Compound: `drop 1,3 edit 2: foo topic ?6: bar` → apply each action

Re-render after any `edit` or `topic` so the user sees the result before final approval. Loop until user types `all`, `cancel`, or unambiguous full-list approval.

**Heartbeat:**
```
Step 7: presenting N candidates for approval...
[after user response]
Step 7: user approved K candidates (M edited, J dropped)
```

If the user types `cancel`, heartbeat `Step 7: harvest cancelled, no changes.` and exit cleanly.

## Step 8: Apply edits, commit, push

For each approved candidate, perform the edit, then commit and push as one batch.

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import os, pathlib, json, re, datetime, subprocess

ctx_dir = pathlib.Path('/tmp/harvest-meeting-ctx')
_t = json.loads((ctx_dir / 'target.json').read_text())
kb_dir = pathlib.Path(_t['kb_dir'])
kb_push = bool(_t.get('kb_push'))
approved = json.loads((ctx_dir / 'approved.json').read_text())
today = datetime.date.today().isoformat()

# Company KB: ensure clean tree before write (rebase on remote). Local KB: no remote, skip.
if kb_push:
    subprocess.run(['git', '-C', str(kb_dir), 'pull', '--ff-only', '--quiet'], check=True)

edited_files = set()

for cand in approved:
    target = cand.get('topic_slug')
    section = cand.get('section')
    is_new_topic = cand.get('is_new_topic', False)

    # Entries are stamped with the MEETING date (the date the decision was made),
    # not the harvest date — so backfilling an old meeting keeps the historical
    # record honest. Existing KB entries follow this convention. Fall back to
    # today only if the candidate is missing a meeting_date.
    entry_date = cand.get('meeting_date') or today

    target_path = kb_dir / f"{target}.md"

    if is_new_topic:
        # New topic. Multiple approved candidates can target the SAME new topic — scaffold
        # once, then APPEND subsequent decisions. Never write_text twice (that would drop
        # all but the last decision). If the file somehow already exists, append rather than
        # clobber.
        kd_line = f"- {entry_date}: {cand['text']} ([▶]({cand['meeting_url']}?timestamp={cand['fathom_timestamp_sec']}))"
        if target_path.exists():
            text = target_path.read_text()
            text = text.replace('## Key Decisions\n', f"## Key Decisions\n\n{kd_line}\n", 1)
            text = re.sub(r'\n{3,}', '\n\n', text)
            target_path.write_text(text)
        else:
            suggested = cand.get('suggested_new', {})
            scaffold = f"""---
type: {suggested.get('type', 'l3')}
parent: "[[{suggested.get('parent', '')}]]"
status: stub
last-updated: {today}
---

# {target.replace('-', ' ').title()}

## Current State


## Key Decisions

{kd_line}

## Open Questions

"""
            target_path.write_text(scaffold)
        edited_files.add(target_path)
        continue

    # Existing topic: edit in place
    text = target_path.read_text()

    if section == 'key_decisions' or section == 'open_questions':
        # Append a new line under the section header
        section_header = '## Key Decisions' if section == 'key_decisions' else '## Open Questions'
        prefix = f'- {entry_date}: ' if section == 'key_decisions' else '- '
        new_line = f"{prefix}{cand['text']}"
        if section == 'key_decisions':
            new_line += f" ([▶]({cand['meeting_url']}?timestamp={cand['fathom_timestamp_sec']}))"

        # Handle REFINEMENT: replace the matched existing entry
        if cand.get('dedup_verdict') == 'REFINEMENT' and cand.get('replace_entry'):
            text = text.replace(cand['replace_entry'], new_line, 1)
        else:
            # Insert under the section header
            new_text = text.replace(
                section_header + '\n',
                f"{section_header}\n\n{new_line}\n",
                1
            )
            # Avoid double blank line if existing content followed immediately
            text = re.sub(r'\n{3,}', '\n\n', new_text)

    elif section == 'current_state':
        # REPLACE the Current State block — use the FULL merged block from Step 6b,
        # never the one-line candidate summary (that would clobber existing context).
        new_text = cand.get('new_current_state')
        if not new_text:
            existing = (cand.get('existing_current_state') or '').strip()
            if existing:
                # Fail safe, not fail clobber: a non-empty Current State with no merged
                # replacement means Step 6b did not run. Skip rather than destroy content.
                print(f"Step 8: SKIP {target}.md current_state — no merged block from Step 6b; "
                      f"refusing to clobber existing content. Re-run with Step 6b.")
                continue
            # Empty Current State: safe to write the candidate directly.
            new_text = cand.get('reshape_to') or cand['text']
        text = re.sub(
            r'(## Current State\n)(.*?)(?=\n## )',
            rf'\1\n{new_text}\n',
            text,
            count=1,
            flags=re.DOTALL,
        )

    # Update last-updated frontmatter
    text = re.sub(r'^(last-updated:\s*)\S+', rf'\g<1>{today}', text, count=1, flags=re.MULTILINE)

    target_path.write_text(text)
    edited_files.add(target_path)

# Commit
if edited_files:
    rel_files = [str(p.relative_to(kb_dir)) for p in edited_files]
    subprocess.run(['git', '-C', str(kb_dir), 'add'] + rel_files, check=True)

    meeting_titles = list({c['meeting_title'] for c in approved})
    title_str = '; '.join(meeting_titles[:3])
    if len(meeting_titles) > 3:
        title_str += f' (+{len(meeting_titles) - 3} more)'

    msg = f"harvest: {today} {title_str} ({len(approved)} edits)"
    subprocess.run(['git', '-C', str(kb_dir), 'commit', '-m', msg], check=True)
    head = subprocess.check_output(['git', '-C', str(kb_dir), 'rev-parse', '--short', 'HEAD'], text=True).strip()

    if not kb_push:
        # Local KB: commit only, never push (no remote exists by design).
        print(f"Step 8: committed {head} locally — {len(edited_files)} file change(s), "
              f"{len(approved)} edit(s) in {kb_dir.name} (not pushed — local KB)")
    else:
        # Company KB: push with rebase-retry.
        try:
            subprocess.run(['git', '-C', str(kb_dir), 'push', 'origin', 'main'], check=True)
            print(f"Step 8: committed {head} — {len(approved)} edit(s) to {len(edited_files)} file(s) "
                  f"in {kb_dir.name}, pushed to origin/main")
        except subprocess.CalledProcessError:
            rebase = subprocess.run(['git', '-C', str(kb_dir), 'pull', '--rebase'], capture_output=True, text=True)
            if 'CONFLICT' in (rebase.stdout + rebase.stderr):
                print("Step 8: FATAL — rebase conflict on topic file. Aborting. Resolve manually.")
                subprocess.run(['git', '-C', str(kb_dir), 'rebase', '--abort'])
                raise SystemExit(1)
            # After rebase, HEAD sha may have changed; recompute for an accurate heartbeat.
            head = subprocess.check_output(['git', '-C', str(kb_dir), 'rev-parse', '--short', 'HEAD'], text=True).strip()
            subprocess.run(['git', '-C', str(kb_dir), 'push', 'origin', 'main'], check=True)
            print(f"Step 8: committed {head} — {len(approved)} edit(s) to {len(edited_files)} file(s) "
                  f"in {kb_dir.name}, pushed to origin/main after rebase")
else:
    print("Step 8: no approved candidates, nothing to commit.")
PYEOF
```

**Heartbeat at end:**
- *Company KB:* `Step 8: committed <sha> — <N> edit(s) to <M> file(s) in 60-nsls-knowledge, pushed to origin/main`.
- *Local KB:* `Step 8: committed <sha> locally — <N> edits to <M> file(s) in 60-nsls-knowledge-local (not pushed — local KB)`.

This is the last step in `--date` and `--fathom-url` modes.

## Step 9: Week-audit mode (--week-audit)

Invoked by `close-week` Step 2b. Reads git log for the week + topic file frontmatter to produce an audit report. Everyone additionally gets promotion + stale-flag write actions against their own KB — company-KB edits push, local-KB edits commit only.

### 9a. Load week context

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import os, pathlib, subprocess, datetime, json, re

_t = json.loads(pathlib.Path('/tmp/harvest-meeting-ctx/target.json').read_text())
kb_dir = pathlib.Path(_t['kb_dir'])
week = os.environ['HARVEST_WEEK']  # YYYY-Www format
year, w = week.split('-W')
year = int(year); w = int(w)

# Compute week boundaries (Mon-Sun)
jan4 = datetime.date(year, 1, 4)
week_start = jan4 + datetime.timedelta(weeks=w - 1, days=-jan4.isoweekday() + 1)
week_end = week_start + datetime.timedelta(days=7)

# Pull git log for the week
log = subprocess.check_output([
    'git', '-C', str(kb_dir), 'log',
    f'--since={week_start.isoformat()}',
    f'--until={week_end.isoformat()}',
    '--pretty=format:%H|%ad|%s', '--date=short'
], text=True)

harvest_commits = [
    line.split('|') for line in log.split('\n')
    if line and line.split('|')[2].startswith('harvest:')
]

# Scan topic files for stale + old open questions
today = datetime.date.today()
stale_threshold = today - datetime.timedelta(days=60)
old_q_threshold = today - datetime.timedelta(days=30)

stale_topics = []
old_open_qs = []

for md_file in kb_dir.glob('*.md'):
    if md_file.name.startswith('_'): continue
    text = md_file.read_text()
    fm_match = re.search(r'last-updated:\s*(\S+)', text)
    if fm_match:
        try:
            last = datetime.date.fromisoformat(fm_match.group(1))
            if last < stale_threshold:
                stale_topics.append({'topic': md_file.stem, 'last_updated': last.isoformat()})
        except ValueError:
            pass

    # Open Questions section
    oq_match = re.search(r'## Open Questions\n(.*?)(?=\n## |\Z)', text, re.DOTALL)
    if oq_match:
        for line in oq_match.group(1).split('\n'):
            if line.strip().startswith('-'):
                # Heuristic: extract date from question line if present
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
                if date_match:
                    q_date = datetime.date.fromisoformat(date_match.group(1))
                    if q_date < old_q_threshold:
                        old_open_qs.append({'topic': md_file.stem, 'question': line.strip(), 'opened': q_date.isoformat()})

print(json.dumps({
    'week': week,
    'window': [week_start.isoformat(), week_end.isoformat()],
    'harvest_commits': harvest_commits,
    'stale_topics': stale_topics,
    'old_open_questions': old_open_qs,
}, indent=2))
PYEOF
```

### 9b. Cross-reference unharvested meetings

Pull Fathom meetings in the week window via MCP, compare against meeting titles in `harvest_commits[*].subject`. List meetings not found in any commit subject.

### 9c. Audit report — always displayed

```
Week YYYY-Www KB audit:

Activity:
  - {N} harvest commits, {M} edits across {K} topic files
  - {J} SLT-recorded meetings; {I} harvested ({J-I} unharvested — listed below)

Unharvested meetings:
  - YYYY-MM-DD "<title>": no harvest commits reference this meeting
  (or "All meetings harvested ✓")

Stale topics (last-updated > 60 days):
  - <slug>.md (last touched YYYY-MM-DD)
  ...
  (or "No stale topics ✓")

Open Questions older than 30 days:
  - <slug>.md: "<question text>" (opened YYYY-MM-DD)
  ...
  (or "No old open questions ✓")
```

### 9d. Promotion offers

Available whenever a KB target is set (always, post-routing). Commits respect `kb_push`:
the company KB pushes; a local KB commits only. (Step 8's logic is reused, so this is automatic.)

For each old open question, ask Claude:

```
Question: "<question text>" (from <slug>.md, opened <date>)

Week's harvest commits (with their meeting context):
<list of harvest commit subjects + brief notes>

Fathom meetings this week (titles + summaries):
<list>

Was this question answered? If yes, return JSON:
{"resolved": true, "resolution_text": "<new Key Decision summary>",
 "source_url": "<fathom url if applicable>", "source_date": "YYYY-MM-DD"}
Else: {"resolved": false}
```

For each resolved question, render in the same approval list pattern as harvest mode:

```
Promotion candidates:

[1] chapter-health.md — Open Question resolved
    - Remove from Open Questions: "How do we measure tier-4 chapters?"
    + Add to Key Decisions: "YYYY-MM-DD: <resolution_text> ([▶](<source_url>))"

Approve? all / drop 1 / edit 1: <text> / cancel
```

On approval, edit the topic file (remove from Open Questions section, append to Key Decisions), commit, push (Step 8 reused).

### 9e. Stale-flag offers

For each stale topic, prompt user:

```
Topic <slug>.md last updated YYYY-MM-DD ({N} days ago).

  [a] Mark `status: stale` in frontmatter
  [b] Leave alone (it's just not active and that's fine)
  [s] Skip all remaining stale prompts

>
```

Per-topic Y/N. Commit the frontmatter changes as a single batch at end.

### 9f. Target note

After 9c, print which KB the audit ran against so the report is unambiguous:

```
Step 9: audit ran against your <company|local> KB (<kb_dir>).
```

There is no audit-only dead-end anymore. Whether company or local, 9d/9e write actions are
available; a local KB commits without pushing.
