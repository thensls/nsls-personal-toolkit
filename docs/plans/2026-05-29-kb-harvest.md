---
title: NSLS Knowledge Base Harvest Pipeline
type: feat
status: completed
date: 2026-05-29
completed: 2026-05-30
plan_depth: deep
spec: docs/specs/2026-05-29-kb-harvest-design.md
---

# NSLS Knowledge Base Harvest Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the missing `close-day` Step 4c + `close-week` Step 2b harvest pipeline so SLT meeting decisions, project definitions, and state changes flow into the `60-nsls-knowledge` topic files daily, rubric-gated, with bulk-approve UX and direct commits to main.

**Architecture:** Standalone `/harvest-meeting` skill in the `nsls-personal-toolkit` plugin owns the full pipeline (load → extract → map → dedup → rubric → approve → commit). `close-day` Step 4c and `close-week` Step 2b are thin callers that gate on SLT membership and invoke the skill. KB writes go directly to `main` on `thensls/nsls-knowledge` via the user's local clone.

**Tech Stack:**
- Skill prose (Markdown SKILL.md) — primary implementation surface
- Python 3.12 with `--target /tmp/pptx_deps` — deterministic data loading, file edits, git operations
- `httpx` for Airtable lookups (existing pattern from Step 1h)
- `git` CLI for KB local-clone read/write/push
- Fathom MCP — meeting data source (already connected for Step 1c)

**Spec:** `docs/specs/2026-05-29-kb-harvest-design.md` — comprehensive design, includes rubric and decision rationale. Read first if any task is ambiguous.

**Pre-flight (read before starting):**
```bash
[ -d /tmp/pptx_deps ] || python3.12 -m pip install python-pptx python-docx lxml httpx --target /tmp/pptx_deps -q
[ -d "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge" ] || echo "FATAL: KB not cloned; clone first"
cd ~/nsls-skills/nsls-personal-toolkit && git pull --ff-only
```

---

## File Structure

**Create:**
- `skills/harvest-meeting/SKILL.md` — core skill prose with embedded Python and Claude prompts (~600 lines)
- `skills/harvest-meeting/kb_authors.txt` — 7 SLT emails, v1 hardcode
- `skills/harvest-meeting/references/candidate-extraction.md` — extraction prompt + examples (referenced from SKILL.md)
- `skills/harvest-meeting/references/topic-mapping.md` — mapping prompt + examples
- `skills/harvest-meeting/references/test-fixtures/2026-05-26-slt-sample.md` — synthetic meeting for self-verification

**Modify:**
- `skills/close-day/SKILL.md` (plugin) — append Step 4c block (~30 lines, after Step 1c/1h section)
- `skills/close-week/SKILL.md` (plugin) — append Step 2b block (~30 lines, after Step 2a)
- `~/.claude/skills/close-day/SKILL.md` (Kevin's local fork) — port Step 4c verbatim

**Read-only references** (no edits in this plan):
- `$OBSIDIAN_VAULT_PATH/60-nsls-knowledge/CLAUDE.md` — sensitive-content rubric (parsed at runtime)
- `$OBSIDIAN_VAULT_PATH/60-nsls-knowledge/_index.md` — topic map
- `$OBSIDIAN_VAULT_PATH/60-nsls-knowledge/*.md` — topic files (read for dedup; written by Task 9)

---

## Task 1: Scaffold the skill directory and authors allowlist

**Files:**
- Create: `skills/harvest-meeting/SKILL.md`
- Create: `skills/harvest-meeting/kb_authors.txt`
- Create: `skills/harvest-meeting/references/.gitkeep`

> **2026-05-29 mid-implementation finding:** A prior attempt at this task overwrote uncommitted local content at `skills/harvest-meeting/SKILL.md`. The overwritten content was never tracked in git and is irrecoverable from the repo. The lesson: **before writing any file, check whether it exists with non-trivial content**. If it does, halt and surface to the user. This task adds a Step 0 to enforce that check.

- [ ] **Step 0: Pre-flight — check for prior uncommitted work and HALT if found**

```bash
TARGET="$HOME/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting"
if [ -d "$TARGET" ]; then
    echo "HALT: $TARGET already exists. Inspect contents before proceeding:"
    ls -la "$TARGET"
    echo
    echo "If the existing content is your prior work and you want to preserve it:"
    echo "  - Move it: mv $TARGET ${TARGET}.preserved-\$(date +%Y%m%d-%H%M%S)"
    echo "  - OR commit it on a branch first: git checkout -b prior-work && git add $TARGET && git commit"
    echo "If the existing content can be discarded: rm -rf $TARGET"
    echo "Re-run this task once $TARGET is absent."
    exit 1
fi
```

If `$TARGET` exists, this command halts. The implementer must surface the situation to the user and not proceed automatically.

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references
touch ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references/.gitkeep
```

- [ ] **Step 2: Write the kb_authors.txt allowlist**

Path: `~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt`

```
# SLT members authorized to write to thensls/nsls-knowledge.
# v1 hardcode — eventually replaced by Airtable `is_slt` field lookup.
# One email per line, # comments, blank lines ignored.
kprentiss@nsls.org
mobrien@nsls.org
gtuerack@nsls.org
astone@nsls.org
hdarnell@nsls.org
asmith@nsls.org
cbyers@nsls.org
```

- [ ] **Step 3: Write skeleton SKILL.md with frontmatter and mode dispatch stub**

Path: `~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md`

```markdown
---
name: harvest-meeting
description: Harvest decisions, project definitions, and state changes from SLT meetings into the NSLS Knowledge Base (60-nsls-knowledge). Gated to SLT writers. Use when you've just finished a strategic meeting, want to backfill a specific Fathom URL, or as part of close-day Step 4c / close-week Step 2b.
---

# Harvest Meeting — NSLS Knowledge Base Pipeline

Pulls decisions, project definitions, and state changes from SLT-recorded meetings, gates them through the employee-facing sensitive-content rubric, and proposes precise edits to topic files in `60-nsls-knowledge`. Approved edits are committed to `main` and pushed.

## Modes

| Mode | When | Source |
|---|---|---|
| `--date YYYY-MM-DD` | close-day Step 4c | All Fathom meetings for the date |
| `--fathom-url <url>` | Manual after important meeting | Single meeting |
| `--week-audit --week YYYY-Www` | close-week Step 2b | Git log + topic files for the week |

## SLT Allowlist

Writes require the current git user.email to be present in `kb_authors.txt` (same directory as this SKILL.md). Non-SLT users running `--week-audit` get the audit report; write actions are silently skipped.

## Step 0: Mode dispatch

Parse arguments. Heartbeat which mode is active. Branch into the appropriate flow below.

(Subsequent steps populated by Tasks 2–9.)
```

- [ ] **Step 4: Verify the scaffold loads as a skill**

```bash
ls -la ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/
```
Expected: SKILL.md, kb_authors.txt, references/.gitkeep visible.

```bash
head -5 ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md
```
Expected: frontmatter with `name: harvest-meeting` and `description:` line.

- [ ] **Step 5: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/
git commit -m "feat(harvest-meeting): scaffold skill directory and SLT allowlist"
```

---

## Task 2: SLT allowlist gate function

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` (replace Step 0 with full mode dispatch + allowlist check)

- [ ] **Step 1: Write the allowlist check block into SKILL.md Step 0**

Replace the "Step 0: Mode dispatch" stub from Task 1 with:

````markdown
## Step 0: Mode dispatch + SLT allowlist gate

Parse arguments to determine mode (`--date`, `--fathom-url`, or `--week-audit`).

Then check whether the current user is an SLT writer:

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 -c "
import os, subprocess, sys, pathlib

skill_dir = pathlib.Path(__file__).resolve().parent if '__file__' in dir() else pathlib.Path('$HOME/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting')
authors_file = skill_dir / 'kb_authors.txt'

# Try multiple resolution paths in case the symlink/install path differs
candidates = [
    pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt',
    pathlib.Path.home() / '.claude/plugins/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt',
]
authors_file = next((p for p in candidates if p.exists()), None)
if not authors_file:
    print('FATAL: kb_authors.txt not found in any known path')
    sys.exit(2)

user_email = subprocess.check_output(['git', 'config', 'user.email'], text=True).strip()
authors = {line.strip() for line in authors_file.read_text().splitlines()
           if line.strip() and not line.startswith('#')}

is_slt = user_email in authors
print(f'user: {user_email}')
print(f'slt_writer: {is_slt}')
print(f'authors_file: {authors_file}')
"
```

**Heartbeat the result** (per the skill-heartbeats rule):

- If `slt_writer: True` → "Step 0: SLT writer confirmed ({user_email}), proceeding."
- If `slt_writer: False` AND mode is `--date` or `--fathom-url` → "Step 0: not in KB_AUTHORS, skipping harvest." Exit cleanly with `WRITE_AUTHORIZED=false`.
- If `slt_writer: False` AND mode is `--week-audit` → "Step 0: not in KB_AUTHORS, running audit-only (no write actions)." Continue with `WRITE_AUTHORIZED=false`.

Pass `WRITE_AUTHORIZED` (True/False) through to subsequent steps; they consult it to decide whether to execute write actions.
````

- [ ] **Step 2: Verify with a known-good email (Kevin)**

```bash
git config user.email kprentiss@nsls.org
PYTHONPATH=/tmp/pptx_deps python3.12 -c "
import pathlib
authors_file = pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt'
authors = {line.strip() for line in authors_file.read_text().splitlines() if line.strip() and not line.startswith('#')}
print('kprentiss@nsls.org' in authors)
"
```
Expected output: `True`

- [ ] **Step 3: Verify with a non-SLT email**

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 -c "
import pathlib
authors_file = pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt'
authors = {line.strip() for line in authors_file.read_text().splitlines() if line.strip() and not line.startswith('#')}
print('davowood@nsls.org' in authors)
"
```
Expected output: `False`

- [ ] **Step 4: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest-meeting): add SLT allowlist gate (Step 0)"
```

---

## Task 3: Context loader — KB topic index + rubric parser

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` (append Step 1: Load Context)

- [ ] **Step 1: Append Step 1 block to SKILL.md**

Append after Step 0:

````markdown
## Step 1: Load context

For `--date` and `--fathom-url` modes, load:
1. KB local clone (refresh first), topic file index, rubric
2. Current Fathom meeting data (Step 2 builds on this)

For `--week-audit` mode, load KB local clone + git log for the week (Task 11 fills this in).

### 1a. Ensure KB local clone is fresh

```bash
KB_DIR="$OBSIDIAN_VAULT_PATH/60-nsls-knowledge"
if [ ! -d "$KB_DIR/.git" ]; then
    echo "Step 1a: FATAL — KB not cloned to $KB_DIR. Run: git clone https://github.com/thensls/nsls-knowledge.git \"$KB_DIR\""
    exit 1
fi
git -C "$KB_DIR" pull --ff-only --quiet
echo "Step 1a: KB synced to $(git -C "$KB_DIR" rev-parse --short HEAD)"
```

### 1b. Load topic index and rubric

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import os, pathlib, re, json

kb_dir = pathlib.Path(os.environ['OBSIDIAN_VAULT_PATH']) / '60-nsls-knowledge'

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

**Heartbeat expected:** `Step 1b: loaded 60 topic files, rubric is ~5000 chars`. If fewer than 40 topic files, something is wrong with the KB clone.
````

- [ ] **Step 2: Verify by running Step 1 standalone**

```bash
export OBSIDIAN_VAULT_PATH="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP"
# Run the Step 1b Python block extracted from SKILL.md (copy from skill or run directly):
PYTHONPATH=/tmp/pptx_deps python3.12 -c "
import os, pathlib, re
kb_dir = pathlib.Path(os.environ['OBSIDIAN_VAULT_PATH']) / '60-nsls-knowledge'
topics = [f.stem for f in kb_dir.glob('*.md') if not f.name.startswith('_')]
print(f'Topic files: {len(topics)}')
print(f'Sample: {topics[:5]}')
"
```
Expected: `Topic files: 60` (approximately), 5 slugs listed.

- [ ] **Step 3: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest-meeting): load KB topic index and rubric (Step 1)"
```

---

## Task 4: Fathom meeting loader

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` (append Step 2: Load Fathom meetings)

- [ ] **Step 1: Append Step 2 block to SKILL.md**

````markdown
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
````

- [ ] **Step 2: Verify with a known Fathom date**

Pick a recent date with at least one meeting in Kevin's Fathom. Then in a Claude session:
```
Invoke the Fathom MCP: list_meetings with start_date=2026-05-26, end_date=2026-05-26, owner_email=kprentiss@nsls.org
Expected: at least 1 result with a recording_id and title
```

- [ ] **Step 3: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest-meeting): load Fathom meetings by date or URL (Step 2)"
```

---

## Task 5: Candidate-extraction reference

**Files:**
- Create: `skills/harvest-meeting/references/candidate-extraction.md`

- [ ] **Step 1: Write the extraction prompt + examples**

Path: `~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references/candidate-extraction.md`

````markdown
# Candidate Extraction — Prompt and Examples

The extraction step asks Claude to identify moments in a meeting that are KB-worthy: **decisions**, **project definitions**, or **state changes**.

## Pre-filter via rubric

Before extraction, paste the rubric's **Never write** list from `60-nsls-knowledge/CLAUDE.md` so the model doesn't surface candidates that are guaranteed to fail Step 5 (rubric gate). Saves tokens and avoids "candidate dropped" noise in the approval list.

## Extraction prompt

```
You are extracting candidate KB entries from an SLT meeting at NSLS (a leadership honor society).

OUTPUT FORMAT: JSON array. No prose, no markdown fences.
Each element: {"kind": "decision" | "project_definition" | "state_change",
               "text": "<one-sentence summary>",
               "fathom_timestamp_sec": <integer>,
               "speaker": "<name or 'unknown'>",
               "confidence": <0.0-1.0>}

KINDS:
- decision: an explicit decision made in the meeting. Phrasing like "we decided X",
  "X is approved", "we're going with X", "X is paused/cancelled/rejected".
- project_definition: a project, initiative, or workstream is being scoped or
  introduced. Includes owner if mentioned. Phrasing like "Project X exists",
  "Y owns this", "we're kicking off Z".
- state_change: a material change since the topic's last KB update. Numeric
  shifts ("conversion rate moved from 12% to 18%"), structural shifts
  ("now using 4 tiers instead of 3"), program changes ("SARs grants now
  vest over 4 years not 2").

DO NOT extract:
- Status updates without a decision ("chapter retention has been declining")
- Plans-in-discussion or hypothetical proposals ("we should probably look at pricing")
- Context, observations, or opinions ("Cory raised a good point")
- Anything that falls in these never-write categories from the NSLS sensitive-content
  rubric: [paste the never-write categories table from 60-nsls-knowledge/CLAUDE.md]

For each candidate, provide a 1-sentence summary in the `text` field — not a full
quote. The Fathom transcript URL + timestamp serves as the verbatim source.

INPUT:
Meeting title: <title>
Meeting date: <YYYY-MM-DD>
Attendees: <list>
Summary: <Fathom summary>
Transcript: <full transcript>
```

## Worked examples

### Example 1: A clear decision

**Transcript excerpt:**
> Adam (10:34): "...so I'm proposing we pause the B2B campaign through July to focus on the chapter renewals."
> Kevin (10:35): "Agreed, let's pause through July. Adam, you'll communicate to the partner contacts?"
> Adam: "Yes, will do this week."

**Expected output:**
```json
[{"kind": "decision",
  "text": "Pausing B2B campaign through July to focus on chapter renewals",
  "fathom_timestamp_sec": 634,
  "speaker": "Kevin Prentiss",
  "confidence": 0.95}]
```

### Example 2: A project definition

**Transcript excerpt:**
> Heather (15:22): "I want to formalize the new-hire 90-day check-in program. Red will own the data instrumentation; I'll own the HR side. We're scoping for a Q3 launch."

**Expected output:**
```json
[{"kind": "project_definition",
  "text": "90-day check-in program: Red owns instrumentation, Heather owns HR side, Q3 2026 launch target",
  "fathom_timestamp_sec": 922,
  "speaker": "Heather Darnell",
  "confidence": 0.9}]
```

### Example 3: A state change

**Transcript excerpt:**
> Ashleigh (22:10): "Chapter health used to be 3 tiers — green, yellow, red. We expanded to 4 last sprint: green, yellow, orange, red. Orange is the new 'needs intervention soon but not critical yet' band."

**Expected output:**
```json
[{"kind": "state_change",
  "text": "Chapter health framework expanded from 3 tiers to 4 (added 'orange' for early intervention)",
  "fathom_timestamp_sec": 1330,
  "speaker": "Ashleigh Smith",
  "confidence": 0.92}]
```

### Example 4: SHOULD NOT be extracted

**Transcript excerpt:**
> Kevin (08:15): "I think we have a real problem with chapter retention. We should look at this seriously next month."

This is intent without decision. NOT a candidate. Empty result.

### Example 5: Sensitive — pre-filter drops it

**Transcript excerpt:**
> Anish (45:01): "Q1 net margin was 14.2%, up from 11.8% in Q4. Best in two years."

This is a profit number. Rubric never-write category. Pre-filter drops it without proposing. Empty result.
````

- [ ] **Step 2: Verify the file is readable and has 5 examples**

```bash
grep -c "^### Example" ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references/candidate-extraction.md
```
Expected: `5`

- [ ] **Step 3: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/references/candidate-extraction.md
git commit -m "feat(harvest-meeting): add candidate-extraction reference with examples"
```

---

## Task 6: Wire candidate extraction into SKILL.md

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` (append Step 3: Extract Candidates)

- [ ] **Step 1: Append Step 3 block to SKILL.md**

````markdown
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
````

- [ ] **Step 2: Verify by dry-running extraction on the test fixture**

(Test fixture is created in Task 10, Step 2. For now, just check the SKILL.md updates parsed cleanly.)

```bash
grep -n "^## Step 3" ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md
```
Expected: `## Step 3: Extract candidates` matched on one line.

- [ ] **Step 3: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest-meeting): wire candidate extraction (Step 3)"
```

---

## Task 7: Topic-mapping reference

**Files:**
- Create: `skills/harvest-meeting/references/topic-mapping.md`

- [ ] **Step 1: Write the mapping prompt + examples**

Path: `~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references/topic-mapping.md`

````markdown
# Topic Mapping — Prompt and Examples

Each candidate from extraction is mapped to one or more KB topic files. Mapping picks a primary topic, optionally a secondary, and a section (`current_state` | `key_decisions` | `open_questions`).

## Mapping prompt

```
You are mapping a candidate KB entry to topic files in the NSLS Knowledge Base.

INPUT:
Candidate: {"kind": "...", "text": "...", "speaker": "...", "meeting_title": "..."}

KB topic index (slug → title + parent + brief snapshot of current_state):
{paste topic_index_summary from /tmp/harvest-meeting-ctx/topics.json}

OUTPUT FORMAT: JSON object, no markdown fences.
{"primary_topic": "<slug>" | "NEW",
 "secondary_topics": ["<slug>", ...],
 "section": "current_state" | "key_decisions" | "open_questions",
 "confidence": <0.0-1.0>,
 "suggested_new": {"slug": "<lowercase-hyphenated>",
                   "parent": "<existing-slug>",
                   "type": "kpi" | "theme" | "channel" | "l2" | "l3" | "rubric"}
                  // only if primary_topic == "NEW"
}

RULES:
- Choose section by candidate kind:
  - decision → key_decisions
  - project_definition → key_decisions (for the new project) OR current_state (if it's
    a redefinition of an existing project's scope)
  - state_change → current_state (the body summary) — REPLACE existing content,
    don't append
- For state_change candidates, look at the current `current_state` of the target topic
  and propose a replacement that captures both the new state and necessary context.
- Confidence < 0.7 → flag for human disambiguation in approval step.
- If no existing topic fits well, return primary_topic: "NEW" with a suggested slug
  matching lowercase-hyphenated convention.
- secondary_topics is optional; use sparingly when a candidate genuinely belongs
  on multiple topics (rare).
```

## Worked examples

### Example 1: Decision → existing topic

**Candidate:** `{"kind": "decision", "text": "Pausing B2B campaign through July...", ...}`

**Expected output:**
```json
{"primary_topic": "b2b-conversion",
 "secondary_topics": [],
 "section": "key_decisions",
 "confidence": 0.95}
```

### Example 2: State change → REPLACE current_state

**Candidate:** `{"kind": "state_change", "text": "Chapter health framework expanded from 3 tiers to 4...", ...}`

**Existing chapter-health.md current_state:** "Chapters classified into 3 health tiers (green/yellow/red) based on activity and renewal metrics."

**Expected output:**
```json
{"primary_topic": "chapter-health",
 "secondary_topics": [],
 "section": "current_state",
 "confidence": 0.95}
```

### Example 3: Project definition → NEW topic

**Candidate:** `{"kind": "project_definition", "text": "90-day check-in program: Red owns instrumentation, Heather owns HR side, Q3 launch", ...}`

No existing topic exists for "new-hire onboarding" or "90-day check-in". Closest topics: `people-hr`, `employees`. Neither is project-specific.

**Expected output:**
```json
{"primary_topic": "NEW",
 "secondary_topics": [],
 "section": "key_decisions",
 "confidence": 0.85,
 "suggested_new": {"slug": "ninety-day-check-in-program",
                   "parent": "people-hr",
                   "type": "l3"}}
```

### Example 4: Low confidence → flag for human

**Candidate:** `{"kind": "decision", "text": "Approved the new vendor for analytics tooling", ...}`

Could fit `data-analytics`, `data-infrastructure`, or `tech-debt-modernization`. Genuinely ambiguous.

**Expected output:**
```json
{"primary_topic": "data-analytics",
 "secondary_topics": ["data-infrastructure"],
 "section": "key_decisions",
 "confidence": 0.55}
```

Approval step will surface this candidate with a "?" flag and let the user pick the topic.
````

- [ ] **Step 2: Verify**

```bash
grep -c "^### Example" ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references/topic-mapping.md
```
Expected: `4`

- [ ] **Step 3: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/references/topic-mapping.md
git commit -m "feat(harvest-meeting): add topic-mapping reference with examples"
```

---

## Task 8: Wire topic mapping, dedup, and rubric gate into SKILL.md

This task batches three logically-tight pipeline steps (4, 5, 6 in the SKILL — mapping, dedup, rubric) because each is short and they share the same per-candidate iteration pattern.

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` (append Steps 4, 5, 6)

- [ ] **Step 1: Append Step 4 (mapping) block**

````markdown
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
````

- [ ] **Step 2: Verify the SKILL.md now has Steps 0–6**

```bash
grep -n "^## Step " ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md
```
Expected: lines for Step 0 through Step 6, in order.

- [ ] **Step 3: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest-meeting): wire mapping, dedup, and rubric (Steps 4-6)"
```

---

## Task 9: Approval-list UX and parser

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` (append Step 7: Present approval list)

- [ ] **Step 1: Append Step 7 block**

````markdown
## Step 7: Present numbered approval list

Render the surviving candidates as a numbered list grouped by topic file, with clear diff markers. Then parse the user's response.

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
````

- [ ] **Step 2: Verify**

```bash
grep -A 3 "^## Step 7" ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md | head -4
```
Expected: Step 7 header + first line of body present.

- [ ] **Step 3: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest-meeting): approval list UX and parser (Step 7)"
```

---

## Task 10: Apply edits + commit + push with rebase-retry

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` (append Step 8: Apply and commit)
- Create: `skills/harvest-meeting/references/test-fixtures/2026-05-26-slt-sample.md` (used in Task 11 for end-to-end test)

- [ ] **Step 1: Append Step 8 block**

````markdown
## Step 8: Apply edits, commit, push

For each approved candidate, perform the edit, then commit and push as one batch.

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import os, pathlib, json, re, datetime, subprocess

kb_dir = pathlib.Path(os.environ['OBSIDIAN_VAULT_PATH']) / '60-nsls-knowledge'
ctx_dir = pathlib.Path('/tmp/harvest-meeting-ctx')
approved = json.loads((ctx_dir / 'approved.json').read_text())
today = datetime.date.today().isoformat()

# Ensure clean tree before write
subprocess.run(['git', '-C', str(kb_dir), 'pull', '--ff-only', '--quiet'], check=True)

edited_files = set()

for cand in approved:
    target = cand.get('topic_slug')
    section = cand.get('section')
    is_new_topic = cand.get('is_new_topic', False)

    target_path = kb_dir / f"{target}.md"

    if is_new_topic:
        # Scaffold new topic file
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

- {today}: {cand['text']} ([▶]({cand['meeting_url']}?timestamp={cand['fathom_timestamp_sec']}))

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
        prefix = f'- {today}: ' if section == 'key_decisions' else '- '
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
        # REPLACE the Current State block
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

    # Push with rebase-retry
    try:
        subprocess.run(['git', '-C', str(kb_dir), 'push', 'origin', 'main'], check=True)
        print(f"Step 8: pushed {len(edited_files)} file change(s), {len(approved)} edit(s)")
    except subprocess.CalledProcessError:
        # Rebase + retry once
        rebase = subprocess.run(['git', '-C', str(kb_dir), 'pull', '--rebase'], capture_output=True, text=True)
        if 'CONFLICT' in (rebase.stdout + rebase.stderr):
            print("Step 8: FATAL — rebase conflict on topic file. Aborting. Resolve manually.")
            subprocess.run(['git', '-C', str(kb_dir), 'rebase', '--abort'])
            raise SystemExit(1)
        subprocess.run(['git', '-C', str(kb_dir), 'push', 'origin', 'main'], check=True)
        print(f"Step 8: pushed after rebase ({len(edited_files)} file change(s), {len(approved)} edit(s))")
else:
    print("Step 8: no approved candidates, nothing to commit.")
PYEOF
```

**Heartbeat at end:**
```
Step 8: committed <sha> — <N> edits to <M> file(s) in 60-nsls-knowledge
       pushed to origin/main
```

This is the last step in `--date` and `--fathom-url` modes.
````

- [ ] **Step 2: Create the synthetic test fixture for Task 11**

Path: `~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references/test-fixtures/2026-05-26-slt-sample.md`

```bash
mkdir -p ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references/test-fixtures
```

```markdown
# Synthetic SLT meeting — for harvest-meeting self-verification

Meeting metadata (mimics Fathom output shape):
```json
{
  "recording_id": "synthetic-2026-05-26",
  "title": "SLT Standing — synthetic fixture for harvest testing",
  "url": "https://fathom.video/share/SYNTHETIC",
  "meeting_date": "2026-05-26",
  "attendees": ["Kevin Prentiss", "Ashleigh Smith", "Adam Stone"]
}
```

## Transcript

[00:30] Kevin: "OK let's start. Adam, where are we with B2B?"
[00:35] Adam: "I'm proposing we pause the B2B campaign through July. Chapter renewals need our attention."
[01:14] Kevin: "Agreed. Pause through July. Adam owns partner communication."
[01:30] Adam: "Will do this week."

[15:22] Ashleigh: "Chapter health used to be 3 tiers. Last sprint we moved to 4 — green, yellow, orange, red. Orange is the new early-warning band."
[15:50] Kevin: "Good. Update the framework doc and chapter dashboards."

[22:05] Heather (joined late): "Also wanted to flag — Q1 net margin was 14.2%, up from 11.8% in Q4. Strongest in two years."
[22:30] Kevin: "Great. Let's hold that detail for the board, not the company-wide update."

[30:00] Adam: "One more — let's start a 90-day check-in program. Red owns instrumentation. Heather owns the HR side. Q3 launch."
[30:45] Kevin: "Yes. Good. Make it real."

## Expected harvest output (for verification)

Should produce 4 candidates, 3 KB-eligible, 1 rubric-dropped:

| # | Candidate | Topic | Section | Rubric |
|---|---|---|---|---|
| 1 | Pausing B2B campaign through July | b2b-conversion | key_decisions | PASS |
| 2 | Chapter health 3→4 tiers (added orange) | chapter-health | current_state | PASS |
| 3 | 90-day check-in program: Red+Heather, Q3 launch | NEW: ninety-day-check-in-program | key_decisions | PASS |
| 4 | Q1 net margin 14.2% (up from 11.8%) | finance-operations | — | DROP_UNSAFE (profit) |
```

- [ ] **Step 3: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md skills/harvest-meeting/references/test-fixtures/
git commit -m "feat(harvest-meeting): apply+commit+push with rebase-retry (Step 8) + test fixture"
```

---

## Task 11: End-to-end verification on the synthetic fixture ✅ DONE (2026-05-30)

This task validates the full pipeline (Steps 0–8) using the synthetic meeting from Task 10. No real Fathom call — feed the fixture directly.

**Files:**
- No code changes; this is an integration test.

> **2026-05-30 result:** PASS — 3 candidates + 1 rubric-dropped, matches expectation.
> Results recorded at `references/test-fixtures/2026-05-26-slt-sample-actual-output.md`.
> The test surfaced and fixed two correctness bugs (commit `0e92274`):
> 1. **SLT gate silent-skip** — Step 0 read a cwd-dependent `git config user.email`;
>    from `$HOME` it fell back to the global gmail (not in the allowlist) and skipped
>    every harvest. Now resolves identity across all stable git scopes.
> 2. **Wrong entry date** — Step 8 stamped `today` not the meeting date; would corrupt
>    backfilled history. Now uses `cand['meeting_date']`.
>
> **Open design issue (gates Task 17): `state_change → current_state` REPLACE clobbers.**
> Step 8 regex-replaces the entire Current State block with the candidate's one-line
> summary. Real topic files hold multi-fact narratives (e.g., `chapter-health.md`), so a
> blind REPLACE destroys context. Resolve before backfilling real meetings — see decision
> log appended at end of plan.

- [ ] **Step 1: Stage the synthetic meeting as if it came from Fathom**

```bash
mkdir -p /tmp/harvest-meeting-ctx
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import json, pathlib, re

fixture = pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references/test-fixtures/2026-05-26-slt-sample.md'
text = fixture.read_text()

# Pull the JSON metadata block
meta_match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
meta = json.loads(meta_match.group(1))

# Pull the transcript section
transcript = re.search(r'## Transcript\n(.*?)\n## Expected', text, re.DOTALL).group(1).strip()

meta['transcript'] = transcript
meta['summary'] = 'SLT standing meeting: B2B pause, chapter health framework update, 90-day check-in project, Q1 margin update.'

(pathlib.Path('/tmp/harvest-meeting-ctx') / 'meetings.json').write_text(json.dumps([meta], indent=2))
print('Fixture staged at /tmp/harvest-meeting-ctx/meetings.json')
PYEOF
```

- [ ] **Step 2: Invoke `/harvest-meeting` against the staged fixture**

In Claude:
```
/harvest-meeting --fathom-url https://fathom.video/share/SYNTHETIC
```

The skill should:
1. Step 0: confirm Kevin is an SLT writer
2. Step 1: load 60-nsls-knowledge topic index + rubric, sync local clone
3. Step 2: load the synthetic meeting (already staged; the URL match should pull from the cache or the skill should accept the staged file)
4. Step 3: extract ~4 candidates
5. Step 4: map to topics (b2b-conversion, chapter-health, NEW ninety-day-check-in-program)
6. Step 5: dedup (all new on a fresh KB)
7. Step 6: rubric — the Q1 margin candidate should DROP_UNSAFE
8. Step 7: present numbered list of 3 candidates + 1 dropped

**Expected approval list (3 candidates, 1 NEW topic, 1 dropped):**

```
[1] b2b-conversion.md → Key Decisions
    + 2026-05-26: Pausing B2B campaign through July ([▶](https://fathom.video/share/SYNTHETIC?timestamp=74))
[2] chapter-health.md → Current State (REPLACE)
    - 3 tiers (green/yellow/red)
    + 4 tiers (green/yellow/orange/red)
[3] 🆕 NEW: ninety-day-check-in-program.md (parent: people-hr)
    + Key Decision: 2026-05-26: 90-day check-in program — Red owns instrumentation, Heather owns HR, Q3 launch
⚠ 1 candidate dropped: "Q1 net margin 14.2%" (profit number)
```

- [ ] **Step 3: Respond `cancel` so no real commit lands**

Type `cancel` at the approval prompt. The skill should heartbeat:
```
Step 7: harvest cancelled, no changes.
```

This validates the full pipeline without polluting the KB with synthetic test data.

- [ ] **Step 4: Record results in the test-fixtures dir**

Path: `~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/references/test-fixtures/2026-05-26-slt-sample-actual-output.md`

Paste the actual output from Step 2 (heartbeats + approval list) into this file. Compare against the "Expected harvest output" table in `2026-05-26-slt-sample.md`. Note any deviations.

- [ ] **Step 5: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/references/test-fixtures/
git commit -m "test(harvest-meeting): end-to-end verification on synthetic fixture"
```

---

## Task 12: Week-audit mode

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` (append Step 9: Week audit flow)

- [ ] **Step 1: Append Step 9 block to SKILL.md**

````markdown
## Step 9: Week-audit mode (--week-audit)

Invoked by `close-week` Step 2b. Reads git log for the week + topic file frontmatter to produce an audit report. SLT users additionally get promotion + stale-flag write actions.

### 9a. Load week context

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import os, pathlib, subprocess, datetime, json, re

kb_dir = pathlib.Path(os.environ['OBSIDIAN_VAULT_PATH']) / '60-nsls-knowledge'
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

### 9d. Promotion offers (SLT-only)

Skip if `WRITE_AUTHORIZED=false`.

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

### 9e. Stale-flag offers (SLT-only)

For each stale topic, prompt user:

```
Topic <slug>.md last updated YYYY-MM-DD ({N} days ago).

  [a] Mark `status: stale` in frontmatter
  [b] Leave alone (it's just not active and that's fine)
  [s] Skip all remaining stale prompts

>
```

Per-topic Y/N. Commit the frontmatter changes as a single batch at end.

### 9f. Non-SLT path

If `WRITE_AUTHORIZED=false`, after 9c:

```
Step 9: audit-only (not in KB_AUTHORS). To propose changes, edit a topic file
in your local clone and open a PR against thensls/nsls-knowledge.
```

Exit cleanly.
````

- [ ] **Step 2: Verify the SKILL.md compiles cleanly**

```bash
grep -n "^## Step " ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md
```
Expected: Steps 0 through 9, in order.

```bash
wc -l ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md
```
Expected: 500–800 lines.

- [ ] **Step 3: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest-meeting): week-audit mode (Step 9)"
```

---

## Task 13: Add Step 4c to plugin close-day

**Files:**
- Modify: `skills/close-day/SKILL.md`

- [ ] **Step 1: Find the insertion point**

```bash
grep -n "^\*\*1h\." ~/nsls-skills/nsls-personal-toolkit/skills/close-day/SKILL.md
```
Find the Step 1h section (SLT Meeting Actions). Step 4c is inserted into a later phase — after `## Insight Reflection` and before final write-back to Asana/Airtable. Locate the exact section name.

```bash
grep -n "^## \|^### " ~/nsls-skills/nsls-personal-toolkit/skills/close-day/SKILL.md | head -40
```

- [ ] **Step 2: Insert Step 4c block**

Insert immediately after `## Insight Reflection` section and before the next major section (likely something like `## Step 5` or `## Write-back`). Insert this block:

````markdown
### Step 4c. NSLS Knowledge Base harvest (SLT only)

Heartbeat sequence:

```bash
user_email=$(git config user.email)
authors_file="$HOME/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt"
if [ ! -f "$authors_file" ]; then
    authors_file="$HOME/.claude/plugins/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt"
fi

if ! grep -qE "^${user_email}\$" "$authors_file" 2>/dev/null; then
    echo "Step 4c: skipped (not in KB_AUTHORS: $user_email)."
else
    # Check if there are any meetings today before invoking
    # (the skill itself will also no-op cleanly if 0 meetings, but heartbeat clarity matters)
    echo "Step 4c: SLT writer confirmed, invoking /harvest-meeting --date $TODAY..."
fi
```

If the SLT check passed, invoke the harvest skill:

```
/harvest-meeting --date $TODAY
```

The skill will:
1. Confirm SLT membership (re-check; defense in depth)
2. Load KB topic index + rubric
3. Pull Fathom meetings for today
4. Extract → map → dedup → rubric
5. Present numbered approval list to the user
6. Apply edits → commit → push (or exit cleanly if cancelled)

**After the skill returns:** Append a `## Knowledge Base` section to today's daily note with one of:
- `- Harvested {N} edits to 60-nsls-knowledge ({sha}, {commit_url})`
- `- 0 candidates from today's meetings`
- `- Harvest cancelled (no changes)`
- `- Not an SLT KB author, harvest skipped`
````

- [ ] **Step 3: Verify the insertion**

```bash
grep -n "Step 4c" ~/nsls-skills/nsls-personal-toolkit/skills/close-day/SKILL.md
```
Expected: matched lines near where Insight Reflection lives.

- [ ] **Step 4: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/close-day/SKILL.md
git commit -m "feat(close-day): add Step 4c KB harvest (SLT-gated)"
```

---

## Task 14: Add Step 2b to plugin close-week

**Files:**
- Modify: `skills/close-week/SKILL.md`

- [ ] **Step 1: Find the insertion point**

```bash
grep -n "^## \|^### " ~/nsls-skills/nsls-personal-toolkit/skills/close-week/SKILL.md | head -30
```
Locate Step 2a (week synthesis) and Step 2c (Quick Notes formatting). Step 2b inserts between them.

- [ ] **Step 2: Insert Step 2b block**

````markdown
### Step 2b. NSLS Knowledge Base week audit

Always runs (audit visible to all users; write actions gated to KB_AUTHORS).

```bash
echo "Step 2b: auditing 60-nsls-knowledge for week $WEEK..."
```

Invoke the harvest skill in audit mode:

```
/harvest-meeting --week-audit --week $WEEK
```

The skill displays:
- Activity summary (commits, edits, files touched)
- Unharvested meetings
- Stale topics (last-updated > 60 days)
- Open Questions older than 30 days

If the user is in `kb_authors.txt`, the skill additionally:
- Offers promotions for resolved Open Questions → Key Decisions
- Offers stale-flag updates on old topic frontmatter

The user approves changes via the same numbered-list UX as `/harvest-meeting --date`.

**After the skill returns:** Append a `## Knowledge Base` section to the weekly close note with the audit summary (and any commits made).
````

- [ ] **Step 3: Verify**

```bash
grep -n "Step 2b" ~/nsls-skills/nsls-personal-toolkit/skills/close-week/SKILL.md
```

- [ ] **Step 4: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/close-week/SKILL.md
git commit -m "feat(close-week): add Step 2b KB week audit"
```

---

## Task 15: Push plugin changes and verify auto-pull

**Files:**
- No file changes; deployment step.

- [ ] **Step 1: Push plugin changes to GitHub**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git log --oneline -10
```
Expected: 10+ commits from Tasks 1–14 since the spec commit (`014baf4`).

```bash
git push origin main
```

- [ ] **Step 2: Verify auto-pull works for another fork**

(Simulate by checking the latest commit appears on GitHub.)

```bash
gh api repos/thensls/nsls-personal-toolkit/commits/main --jq '.commit.message' 2>&1 | head -3
```
Expected: latest commit subject matches Task 14's commit.

- [ ] **Step 3: Commit and push the plan itself (with status update)**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
# Update plan frontmatter status: planned → in-progress
sed -i.bak 's/^status: planned$/status: in-progress/' docs/plans/2026-05-29-kb-harvest.md && rm docs/plans/2026-05-29-kb-harvest.md.bak
git add docs/plans/2026-05-29-kb-harvest.md
git commit -m "docs(plans): mark KB harvest plan in-progress" && git push origin main
```

---

## Task 16: Port Step 4c to Kevin's local close-day fork

**Files:**
- Modify: `~/.claude/skills/close-day/SKILL.md`

- [ ] **Step 1: Locate insertion point in local fork**

```bash
grep -n "^### Step \|^## " ~/.claude/skills/close-day/SKILL.md | head -30
```
Find the same Insight Reflection section as in the plugin version. (The forks have diverged; insertion point may differ slightly.)

- [ ] **Step 2: Copy Step 4c block verbatim from plugin**

```bash
# Extract Step 4c from the plugin SKILL.md
sed -n '/^### Step 4c\./,/^### \|^## /p' ~/nsls-skills/nsls-personal-toolkit/skills/close-day/SKILL.md > /tmp/step-4c.md
head -3 /tmp/step-4c.md
```

Manually insert `/tmp/step-4c.md` content into `~/.claude/skills/close-day/SKILL.md` at the post-Insight-Reflection point. Use Edit tool with the exact insertion-point text already found.

- [ ] **Step 3: Verify**

```bash
grep -n "Step 4c" ~/.claude/skills/close-day/SKILL.md
```
Expected: matched lines.

- [ ] **Step 4: Record the port in MEMORY.md**

Add a memory entry recording the port date for future drift-reconciliation tracking. Use the Write tool to create or update:

`/Users/k/.claude/projects/-Users-k/memory/feedback_close_day_step4c_port.md`

```markdown
---
name: feedback-close-day-step4c-port
description: Step 4c (KB harvest) ported from plugin close-day to local close-day fork on YYYY-MM-DD; in sync as of that date
metadata:
  type: feedback
---

Step 4c (NSLS KB harvest) was ported from the plugin close-day SKILL.md to the local fork at `~/.claude/skills/close-day/SKILL.md` on YYYY-MM-DD (replace with implementation date).

**Why:** The local close-day is a drifted fork ([[project_close_day_skill_drift]]). Plugin auto-pull doesn't update the local fork; ports happen manually.

**How to apply:** When future plugin close-day changes ship, check whether they need porting to the local fork. The local fork's Step 4c is canonical for Kevin's runs.

Related: [[feedback_skill_heartbeats]] — Step 4c must heartbeat its skip path.
```

Then add the one-line pointer to MEMORY.md:

```markdown
- [Step 4c ported to local close-day fork YYYY-MM-DD](feedback_close_day_step4c_port.md) — sync as of that date
```

(Insert under the "NSLS Knowledge Base" section.)

- [ ] **Step 5: No commit needed for local-fork edit**

Local fork is not under git management. Memory edit is a separate concern from plugin commits.

---

## Task 17: Backfill the 2026-05-19 → 2026-05-29 gap ✅ DONE (2026-05-30)

> **2026-05-30 result:** Backfilled a curated set of 6 meetings (Kevin chose "SLT + curated
> strategic set"). 2 harvest commits to `thensls/nsls-knowledge`, **24 edits**, 1 new topic
> (`ai-builder-governance`). Rubric dropped ~16 sensitive items across the set (CEO transition,
> profit/EBITDA, owner-distribution/bonus, named comp/promotions, Gary's legal/divorce, reporting
> structure, security/PII research, duty-of-care incident). Heavy transcripts were processed by
> per-meeting subagents (extract→map→dedup→rubric→merge) to keep them out of main context, then a
> cross-meeting dedup pass collapsed overlapping fall-rollout content before one batch commit.
> Commits: `86481cb` (SLT 05-26, 15 edits), `0f4ef68` (mtgs 05-27/29, 9 edits), `3c05240` (title fix).
>
> **Two more bugs surfaced + fixed during backfill:**
> 3. **New-topic clobber** (`979e4fc`) — Step 8 `write_text`'d per candidate, so N decisions to one
>    NEW topic overwrote each other. Now scaffolds once + appends (Claude Builder Sprint → 4 decisions
>    in one `ai-builder-governance.md`).
> 4. **Title casing (KNOWN, not yet fixed in skill)** — `slug.replace('-',' ').title()` produces
>    "Ai Builder Governance"; acronyms (AI, B2B, B2C, SNT, FOL) mistitle. Fixed the one live file by
>    hand. **Follow-up:** add an acronym-aware title map to Step 8's scaffold, or prompt for the H1.
>
> Meetings NOT harvested (excluded as low-KB-signal / mostly never-write): CEO-transition 1:1s (Adam,
> Cory), coaching/relationship 1:1s (Red ×3, Jack), Gary/Kevin board-budget (financial-figure heavy).
> One harvested meeting (WGU/Ashleigh impromptu) yielded 0 candidates — pure exploratory swirl.
>
> Original step-by-step (kept for reference):

**Files:**
- No file changes. Real harvest writes to `thensls/nsls-knowledge`.

- [ ] **Step 1: Identify the high-signal meetings in the window**

```bash
# In Claude, use Fathom MCP:
# list_meetings(start_date='2026-05-19', end_date='2026-05-29', owner_email='kprentiss@nsls.org')
```

Kevin reviews the list and nominates the 3–6 meetings that had real strategic content. Specifically include the 2026-05-26 SLT meeting that prompted this whole project.

- [ ] **Step 2: Run /harvest-meeting on each nominated meeting**

For each nominated Fathom URL:

```
/harvest-meeting --fathom-url <url>
```

Kevin reviews the candidate list, approves/edits/drops as appropriate, allowing commits to land on `main`.

- [ ] **Step 3: Verify the KB now reflects the gap**

```bash
cd "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge"
git log --since="2026-05-19" --oneline | grep "harvest:"
```
Expected: one `harvest:` commit per nominated meeting.

```bash
git log --since="2026-05-19" --diff-filter=M --name-only --pretty=format: -- '*.md' | sort -u | grep -v "^_data" | head -20
```
Expected: 5–15 topic files touched by the backfill (more if a meeting was rich).

- [ ] **Step 4: Update the plan status**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
sed -i.bak 's/^status: in-progress$/status: completed/' docs/plans/2026-05-29-kb-harvest.md && rm docs/plans/2026-05-29-kb-harvest.md.bak
echo "completed: $(date +%Y-%m-%d)" >> /tmp/plan-completed-marker  # add as frontmatter manually
```

Manually add `completed: YYYY-MM-DD` to the YAML frontmatter via Edit tool.

```bash
git add docs/plans/2026-05-29-kb-harvest.md
git commit -m "docs(plans): mark KB harvest plan completed; backfill applied" && git push origin main
```

- [ ] **Step 5: Announce to the other 6 SLT**

(Out of code scope; Kevin sends a Slack DM or 1:1 mention to Michael, Gary, Adam, Heather, Ashleigh, Chelsea explaining the new flow.)

---

## Task 18 (follow-up, not v1): Memory cleanup and Airtable enhancements

These are post-v1 hygiene items captured in the spec's Follow-ups section. Listed here so the implementing engineer doesn't lose track.

- [ ] **Step 1: Update the NSLS KB memory note**

`/Users/k/.claude/projects/-Users-k/memory/project_nsls_knowledge_base.md`:
- Change the wiring status from "planned" to "v1 built YYYY-MM-DD, ships via plugin auto-pull + local fork port"
- Add: "harvest pipeline = /harvest-meeting skill in nsls-personal-toolkit; SLT_AUTHORS hardcoded in skills/harvest-meeting/kb_authors.txt"

- [ ] **Step 2: Add the canonical SLT roster memory entry**

Create: `/Users/k/.claude/projects/-Users-k/memory/project_slt_roster.md`

```markdown
---
name: project-slt-roster
description: NSLS SLT (Senior Leadership Team) roster as of 2026-05-29 — 7 members
metadata:
  type: project
---

NSLS SLT, as of 2026-05-29, has 7 members:

1. Kevin Prentiss (kprentiss@nsls.org) — Head of Product & Technology
2. Michael O'Brien (mobrien@nsls.org) — Strategic Advisory
3. Gary Tuerack (gtuerack@nsls.org) — Founder & Interim CEO
4. Adam Stone (astone@nsls.org) — Head of Marketing
5. Heather Darnell (hdarnell@nsls.org — needs adding to Airtable Members record) — Director, Human Resources
6. Ashleigh Smith (asmith@nsls.org) — VP of Client Services
7. Chelsea Byers (cbyers@nsls.org) — Fractional VP of Operations (FTE go/no-go 2026-06-27)

**Note:** Anish Patel is NOT on SLT (memory previously had this wrong). He's the CFO and attends some meetings.

This roster is the hardcoded source for `kb_authors.txt` in [[nsls-builder-toolkit]] until `is_slt` field lands on the SLT MI Airtable Members table.
```

Add a pointer to MEMORY.md:
```
- [Canonical SLT roster (7 members, 2026-05-29)](project_slt_roster.md) — Kevin, Michael, Gary, Adam, Heather, Ashleigh, Chelsea; NOT Anish
```

- [ ] **Step 3: Fix the stale SLT roster in slt-ops schema doc**

Edit `~/nsls-skills/slt-ops/slt-meeting-agenda/references/airtable-schema.md` — the "SLT Members (for Friday Script)" table. Remove Anish, add Heather and Chelsea, match the canonical 7.

```bash
cd ~/nsls-skills/slt-ops
git add slt-meeting-agenda/references/airtable-schema.md
git commit -m "fix(schema): update SLT roster to canonical 7 (no Anish; +Heather, +Chelsea)"
git push origin main
```

- [ ] **Step 4: Add Heather's email to Airtable Members record**

In Claude:
```
Update Heather Darnell's record in SLT MI Airtable Members table (tbl9GMiujOzOD7xXn,
base appHDEHQA4bvlWwQq). Set email field (fldwk1uKgjMxKyUjY) to hdarnell@nsls.org.
```

(API call via mcp__claude_ai_Airtable__update_records_for_table.)

- [ ] **Step 5: Add `is_slt` checkbox field to Members table**

Via Airtable Metadata API or UI: add a `is_slt` checkbox field to `tbl9GMiujOzOD7xXn`. Tick it for the 7 canonical SLT members.

- [ ] **Step 6: (Eventual) migrate kb_authors.txt to live Airtable lookup**

Once `is_slt` field is populated, modify `skills/harvest-meeting/SKILL.md` Step 0 to query Airtable instead of reading kb_authors.txt. Keep kb_authors.txt as fallback. Separate PR; not part of v1.

---

## Self-Review Notes

Performed after writing the plan, before handing off.

**Spec coverage check:**
- D1 (daily writes, weekly audits): Tasks 1–11 (harvest) + Task 12 (audit). ✓
- D2 (all meetings): Task 4 uses Fathom MCP list_meetings; not filtered. ✓
- D3 (filter = D/PD/SC): Task 5 reference + Task 6 wire-in enforce. ✓
- D4 (rubric routing): Task 8 rubric step DROP_UNSAFE removes; no separate channel. ✓
- D5 (numbered list approval): Task 9 covers UX + parser. ✓
- D6 (direct commit): Task 10 Step 8 pushes to main. ✓
- D7 (standalone skill): Tasks 1–12 build the skill; Tasks 13–14 are thin callers. ✓
- D8 (7 SLT writers): Task 1 kb_authors.txt + Task 2 gate. ✓
- D9 (close-week plugin): Task 14. ✓

**Placeholder scan:** YYYY-MM-DD in commit message templates and frontmatter is intentional template form, not a gap. No TBDs, no "implement later", no "similar to Task N" references. ✓

**Type/name consistency:**
- `kb_authors.txt` named consistently across all tasks. ✓
- `WRITE_AUTHORIZED` flag named consistently in Tasks 2, 12. ✓
- `/tmp/harvest-meeting-ctx/` cache dir used consistently in Tasks 3, 4, 6, 8, 10. ✓
- Section names (current_state, key_decisions, open_questions) match KB topic file structure. ✓
- Heartbeat format (`Step N: <message>`) consistent across all steps. ✓

---

## Execution Handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task. Two-stage review between tasks. Best for a plan with 17+ tasks across multiple skills.

2. **Inline Execution** — Execute in the current session via `superpowers:executing-plans`. Batch with checkpoints. Faster if the engineer wants tight control.

Either way, the plan is bite-sized enough to checkpoint after each task. Recommend pausing for Kevin review after Task 11 (end-to-end verification) before continuing into Tasks 13–17.
