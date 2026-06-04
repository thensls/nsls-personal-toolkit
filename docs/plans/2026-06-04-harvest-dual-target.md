# Harvest-Meeting Dual-Target Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/harvest-meeting` usable by every employee — SLT members keep harvesting into the company KB (`thensls/nsls-knowledge`, pushed); everyone else harvests into a self-contained local KB that commits locally and never touches the org repo.

**Architecture:** The `kb_authors.txt` allowlist stops being a write gate and becomes a routing decision. Step 0 resolves `KB_TARGET` (company|local), `KB_DIR`, and `KB_PUSH`, stashing them in `/tmp/harvest-meeting-ctx/target.json` (read by python blocks) and `/tmp/harvest-meeting-ctx/env.sh` (sourced by bash blocks). All later steps read `KB_DIR` instead of the hardcoded company path and branch on `KB_PUSH` for push behavior. A non-SLT user's first run scaffolds a local git repo (no remote) from a bundled org-level seed.

**Tech Stack:** Markdown skill (`SKILL.md`) with embedded bash + `python3.12` (via `PYTHONPATH=/tmp/pptx_deps`). No automated test framework — "tests" are verification runs of the actual Step 0/1/8 blocks against simulated identities and temp KB dirs.

---

## File Structure

- **Modify:** `skills/harvest-meeting/SKILL.md` — Step 0 (routing), Step 1a (local setup + parameterize), Step 1b (parameterize + company-only alarm), Step 8 (parameterize + conditional push), Step 9 (parameterize + always-on write actions), frontmatter + prose.
- **Create:** `skills/harvest-meeting/references/local-kb-seed/CLAUDE.md` — rubric carrier for local KBs.
- **Create:** `skills/harvest-meeting/references/local-kb-seed/_index.md` — local KB orientation note.
- **Create:** `skills/harvest-meeting/references/local-kb-seed/how-nsls-works.md` — org-level seed stub.
- **Create:** `skills/harvest-meeting/references/local-kb-seed/org-structure.md` — org-level seed stub.
- **Create:** `skills/harvest-meeting/references/local-kb-seed/products-and-programs.md` — org-level seed stub.
- **Create:** `skills/harvest-meeting/references/local-kb-seed/chapter-network.md` — org-level seed stub.
- **Modify:** `skills/harvest-meeting/../../skills/close-day/SKILL.md` (Step 4c caller) — wording tweak if needed (Task 8).
- **Modify:** `skills/close-week/SKILL.md` (Step 2b caller) — wording tweak if needed (Task 8).
- **Modify (outside repo):** `~/.claude/skills/harvest-meeting/SKILL.md` stub description (Task 7).

All paths below are relative to `~/nsls-skills/nsls-personal-toolkit/` unless absolute. Work happens on the existing `harvest-dual-target` branch.

---

## Task 1: Build the org-level seed scaffold

**Files:**
- Create: `skills/harvest-meeting/references/local-kb-seed/CLAUDE.md`
- Create: `skills/harvest-meeting/references/local-kb-seed/_index.md`
- Create: `skills/harvest-meeting/references/local-kb-seed/how-nsls-works.md`
- Create: `skills/harvest-meeting/references/local-kb-seed/org-structure.md`
- Create: `skills/harvest-meeting/references/local-kb-seed/products-and-programs.md`
- Create: `skills/harvest-meeting/references/local-kb-seed/chapter-network.md`

- [ ] **Step 1: Create the seed CLAUDE.md (must contain the rubric header Step 1b greps for)**

Create `skills/harvest-meeting/references/local-kb-seed/CLAUDE.md` with exactly this content:

```markdown
# Local NSLS Knowledge Base

This is a **personal, local** knowledge base built by `/harvest-meeting`. It lives only on
this machine (local git repo, no remote) and is never pushed to the company KB. SLT members
write to the shared company KB instead; everyone else builds a KB here.

The same sensitive-content rubric applies. Keeping it uniform means nothing here would be a
problem if you ever choose to share or upstream an entry.

## Sensitive-Content Rubric — REQUIRED before every write

**The test:** *"Could this entry appear in an all-hands email or on the careers page without HR, Finance, Legal, or InfoSec flagging it?"* If no, drop the candidate or reshape it until yes.

**Never write to the KB:**

| Category | Examples |
|---|---|
| **Individual compensation** | Salaries, bonuses, equity/SARs grants tied to a named person, strike prices for specific grantees, OTE targets, day rates |
| **Personnel decisions about named individuals** | Promotions, demotions, role changes, transfers, performance ratings, terminations, hire-offers-in-flight, hours/comp adjustments, who was "let go" |
| **HR-sensitive matters** | Leave, accommodations, health, complaints/investigations, family circumstances, mental health, conduct issues |
| **Confidential financials** | **Profit / margin / EBITDA at any level (org, L1, L2, segment)** — total revenue numbers OK; profit numbers are NEVER shared internally even at the highest level. Also: cash balances, surplus, runway, individual deal economics, lender terms, board-only budget detail |
| **Security gaps** | Specific vulnerabilities, vendor dependencies that name the gap, active incidents, credentials, named single points of failure in security |
| **Active legal / regulatory** | Pending disputes, claims, investigations, settlement terms, audit findings before remediation |
| **Vendor / partner confidential terms** | Contract pricing, exclusivity clauses, partner-specific economics, named financial arrangements with consultants/partners |
| **Board-confidential moves** | Pending M&A, spinoff plans pre-announcement, succession discussions |

**OK to write:**

- Strategic direction, sequencing decisions, market focus
- Product roadmap themes and decisions
- Org structure as "who owns what surface" (NOT named promotions or comp)
- Programs at a level anyone can know exists ("SARs are part of the equity program" — never the grant amounts)
- Customer and market insights from shareable sources
- Process and operating model decisions
- Adoption metrics, product engagement numbers (when not tied to individual performance)
- Total revenue numbers (already broadly shared)

**Edge-case reshape rules:**

- Profit numbers → strip; keep the revenue figure
- Vendor names attached to gaps → drop the vendor; describe the dependency abstractly
- Named individuals tied to neutral org-ownership ("X owns surface Y") → OK
- Named individuals tied to status changes ("X promoted/let go/given Z") → NOT OK; reshape to the structural fact
- Specific dollar figures for non-revenue budget shortfalls → soften to "shortfall" without the figure
- Specific partner names attached to contract clauses → generalize to "B2B partner template includes [clause]"

If unsure, default to the safer reshape. One leak undermines trust more than ten missing entries.
```

- [ ] **Step 2: Create the seed _index.md**

Create `skills/harvest-meeting/references/local-kb-seed/_index.md`:

```markdown
---
type: index
status: stub
last-updated: 1970-01-01
---

# Local Knowledge Base — Index

Topic files in this folder capture how NSLS works and where it's going, harvested from your
meetings by `/harvest-meeting`. This KB is local to your machine. Starter topics below grow
as you harvest; add new topic files freely.

- [[how-nsls-works]]
- [[org-structure]]
- [[products-and-programs]]
- [[chapter-network]]
```

- [ ] **Step 3: Create the four org-level topic stubs**

Create `skills/harvest-meeting/references/local-kb-seed/how-nsls-works.md`:

```markdown
---
type: theme
status: stub
last-updated: 1970-01-01
---

# How NSLS Works

## Current State


## Key Decisions


## Open Questions

```

Create `skills/harvest-meeting/references/local-kb-seed/org-structure.md`:

```markdown
---
type: theme
status: stub
last-updated: 1970-01-01
---

# Org Structure

## Current State


## Key Decisions


## Open Questions

```

Create `skills/harvest-meeting/references/local-kb-seed/products-and-programs.md`:

```markdown
---
type: theme
status: stub
last-updated: 1970-01-01
---

# Products and Programs

## Current State


## Key Decisions


## Open Questions

```

Create `skills/harvest-meeting/references/local-kb-seed/chapter-network.md`:

```markdown
---
type: theme
status: stub
last-updated: 1970-01-01
---

# Chapter Network

## Current State


## Key Decisions


## Open Questions

```

- [ ] **Step 4: Verify the seed is complete and the rubric header is present**

Run:
```bash
cd ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting
ls references/local-kb-seed/
grep -l "## Sensitive-Content Rubric" references/local-kb-seed/CLAUDE.md
for f in references/local-kb-seed/*.md; do
  [ "$(basename "$f")" = "CLAUDE.md" ] && continue
  [ "$(basename "$f")" = "_index.md" ] && continue
  grep -q "## Current State" "$f" && grep -q "## Key Decisions" "$f" && grep -q "## Open Questions" "$f" && echo "OK: $f" || echo "MISSING SECTION: $f"
done
```
Expected:
```
CLAUDE.md  _index.md  chapter-network.md  how-nsls-works.md  org-structure.md  products-and-programs.md
references/local-kb-seed/CLAUDE.md
OK: references/local-kb-seed/chapter-network.md
OK: references/local-kb-seed/how-nsls-works.md
OK: references/local-kb-seed/org-structure.md
OK: references/local-kb-seed/products-and-programs.md
```

- [ ] **Step 5: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/references/local-kb-seed/
git commit -m "feat(harvest): add org-level local-KB seed scaffold"
```

---

## Task 2: Rewrite Step 0 to route by membership instead of gating writes

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` — the `## Step 0: Mode dispatch + SLT allowlist gate` section (the python block + the heartbeat/decision prose that follows it).

The current python block ends at the `looks_misconfigured` print. We extend it to (a) honor a `HARVEST_AUTHORS_FILE` test override, (b) resolve `kb_target`/`kb_dir`/`kb_push`, (c) write `/tmp/harvest-meeting-ctx/target.json` and `env.sh`, and (d) print the resolved target. Then we replace the three decision branches so non-SLT and misconfigured users route to local instead of skipping.

- [ ] **Step 1: Add the test-override hook to the authors-file lookup**

In `SKILL.md`, find:
```python
authors_file = next((p for p in candidates_paths if p.exists()), None)
```
Replace with:
```python
# HARVEST_AUTHORS_FILE lets verification runs point at a temp allowlist.
override = os.environ.get('HARVEST_AUTHORS_FILE')
authors_file = pathlib.Path(override) if override else next((p for p in candidates_paths if p.exists()), None)
```

- [ ] **Step 2: Append target resolution + stash to the end of the Step 0 python block**

In `SKILL.md`, find the final lines of the Step 0 python block:
```python
print(f'looks_misconfigured: {looks_misconfigured}')
if nsls_emails:
    print(f'nsls_emails_detected: {\", \".join(nsls_emails)}')
"
```
Replace with (note: still inside the `python3.12 -c "..."` string, so the trailing `"` stays last):
```python
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

- [ ] **Step 3: Replace the decision/heartbeat prose with routing-aware branches**

In `SKILL.md`, find the heartbeat block that starts with `**Heartbeat the result**` and runs through the end of `## Step 0` (the bullet list of `slt_writer: True` / `False AND looks_misconfigured` / `False AND not misconfigured` / `False AND --week-audit`, the KB-commit-attribution blockquote, and the final `Pass WRITE_AUTHORIZED ...` line). Replace that entire run with:

````markdown
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
````

- [ ] **Step 4: Update the "## SLT Allowlist" section to describe routing**

In `SKILL.md`, find:
```markdown
## SLT Allowlist

Writes require the current git user.email to be present in `kb_authors.txt` (same directory as this SKILL.md). Non-SLT users running `--week-audit` get the audit report; write actions are silently skipped.
```
Replace with:
```markdown
## Allowlist → routing (not a write gate)

`kb_authors.txt` (same directory as this SKILL.md) lists SLT members. It no longer gates
whether you can write — it decides **where** writes go:

- **On the allowlist** → company KB (`thensls/nsls-knowledge`), committed and pushed to `main`.
- **Not on the allowlist** → a self-contained **local KB** (`60-nsls-knowledge-local` in your
  vault), committed locally and never pushed. First run scaffolds it from an org-level seed.

Identity is resolved cwd-independently in Step 0 (same logic as before). Everyone gets a
working harvest; SLT membership only changes the destination.
```

- [ ] **Step 5: Verify routing for an SLT identity**

Run (uses Kevin's email, which is on the real allowlist):
```bash
mkdir -p /tmp/harvest-test && cd /tmp/harvest-test
export OBSIDIAN_VAULT_PATH="/tmp/harvest-test/vault"
GIT_AUTHOR_EMAIL=kprentiss@nsls.org \
PYTHONPATH=/tmp/pptx_deps python3.12 - <<'PYEOF'
# Paste-equivalent: exec the Step 0 python by extracting it is overkill for the test;
# instead re-run the resolution with the real allowlist via the override OFF.
import subprocess, pathlib, json, os
# Run the actual block by sourcing SKILL.md is not practical; verify target.json was written
# by the real block when you run the skill. For this unit check, assert the routing rule:
skill = (pathlib.Path.home()/'nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md').read_text()
assert "kb_target, kb_push = 'company', True" in skill
assert "kb_target, kb_push = 'local', False" in skill
assert "60-nsls-knowledge-local" in skill
print("Step 0 routing rules present in SKILL.md: OK")
PYEOF
```
Expected: `Step 0 routing rules present in SKILL.md: OK`

- [ ] **Step 6: Verify the actual Step 0 block routes correctly under simulated identities**

Extract and run the real Step 0 python with a temp allowlist to confirm both branches and the stash files. Run:
```bash
rm -rf /tmp/harvest-meeting-ctx
printf 'slt@nsls.org\n' > /tmp/test-authors.txt
export OBSIDIAN_VAULT_PATH="/tmp/harvest-test/vault"

# SLT case: identity matches the temp allowlist
GIT_AUTHOR_EMAIL=slt@nsls.org HARVEST_AUTHORS_FILE=/tmp/test-authors.txt \
  bash -c 'sed -n "/PYTHONPATH=\/tmp\/pptx_deps python3.12 -c/,/^\`\`\`$/p" \
    ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md \
    | sed "1d;\$d" | bash'
echo "--- target.json (expect company) ---"; cat /tmp/harvest-meeting-ctx/target.json

# Misconfigured case: nsls email NOT on allowlist
rm -rf /tmp/harvest-meeting-ctx
GIT_AUTHOR_EMAIL=other@nsls.org HARVEST_AUTHORS_FILE=/tmp/test-authors.txt \
  bash -c 'sed -n "/PYTHONPATH=\/tmp\/pptx_deps python3.12 -c/,/^\`\`\`$/p" \
    ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md \
    | sed "1d;\$d" | bash'
echo "--- target.json (expect local, looks_misconfigured true) ---"; cat /tmp/harvest-meeting-ctx/target.json
```
Expected: first `target.json` shows `"kb_target": "company"` and `kb_dir` ending `/60-nsls-knowledge`; second shows `"kb_target": "local"` and `kb_dir` ending `/60-nsls-knowledge-local`, and the run prints `looks_misconfigured: True`. If the `sed` extraction proves fragile, instead copy the Step 0 python into `/tmp/step0.py` by hand and run that with the same env vars — the assertion is the same.

- [ ] **Step 7: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest): route by allowlist (company vs local) instead of gating writes"
```

---

## Task 3: Add local first-run setup and parameterize Step 1a

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` — `### 1a. Ensure KB local clone is fresh`.

- [ ] **Step 1: Replace the Step 1a bash block with a target-aware version**

In `SKILL.md`, find the entire `### 1a. Ensure KB local clone is fresh` code block (the `KB_DIR="$OBSIDIAN_VAULT_PATH/60-nsls-knowledge"` … `echo "Step 1a: KB synced to ..."` block). Replace the whole fenced block with:

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

- [ ] **Step 2: Verify local first-run scaffolds correctly with no remote**

Run:
```bash
rm -rf /tmp/harvest-test/vault
mkdir -p /tmp/harvest-meeting-ctx
printf 'export KB_TARGET=local\nexport KB_DIR="/tmp/harvest-test/vault/60-nsls-knowledge-local"\nexport KB_PUSH=false\n' > /tmp/harvest-meeting-ctx/env.sh

# Extract & run only the Step 1a block (between its ```bash and ```):
sed -n '/^### 1a\. Ensure KB local clone is fresh/,/^### 1b\./p' \
  ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md \
  | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' | bash

echo "--- files ---"; ls "/tmp/harvest-test/vault/60-nsls-knowledge-local"
echo "--- remotes (expect empty) ---"; git -C "/tmp/harvest-test/vault/60-nsls-knowledge-local" remote
echo "--- log ---"; git -C "/tmp/harvest-test/vault/60-nsls-knowledge-local" log --oneline
```
Expected: the seed files (`CLAUDE.md`, `_index.md`, four topic stubs) are present; `remote` prints nothing; log shows `local KB: initial scaffold`.

- [ ] **Step 3: Verify second run is idempotent (ready, not re-scaffolded)**

Run:
```bash
sed -n '/^### 1a\. Ensure KB local clone is fresh/,/^### 1b\./p' \
  ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md \
  | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' | bash
```
Expected: `Step 1a: local KB ready at ...` (NOT "created"), single commit still in log.

- [ ] **Step 4: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest): scaffold local KB on first run (no remote); parameterize Step 1a"
```

---

## Task 4: Parameterize Step 1b (read KB_DIR; company-only file-count alarm)

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` — `### 1b. Load topic index and rubric` python block + its heartbeat note.

- [ ] **Step 1: Read KB_DIR from target.json instead of the hardcoded path**

In `SKILL.md`, in the `### 1b` python block, find:
```python
kb_dir = pathlib.Path(os.environ['OBSIDIAN_VAULT_PATH']) / '60-nsls-knowledge'
```
Replace with:
```python
import json as _json
_t = _json.loads(pathlib.Path('/tmp/harvest-meeting-ctx/target.json').read_text())
kb_dir = pathlib.Path(_t['kb_dir'])
```

- [ ] **Step 2: Make the "fewer than 40 topic files" alarm company-only**

In `SKILL.md`, find the heartbeat note after the 1b block:
```markdown
**Heartbeat expected:** `Step 1b: loaded 60 topic files, rubric is ~5000 chars`. If fewer than 40 topic files, something is wrong with the KB clone.
```
Replace with:
```markdown
**Heartbeat expected:** `Step 1b: loaded N topic files, rubric is ~5000 chars`.
- *Company KB:* expect ~60. Fewer than 40 means something is wrong with the clone — stop and check.
- *Local KB:* a freshly seeded KB legitimately has ~5 files. The count grows as you harvest, so there is no low-count alarm for local.
```

- [ ] **Step 3: Verify 1b loads the seeded local KB and finds the rubric**

Run (reuses the local KB from Task 3):
```bash
printf '{"kb_target":"local","kb_dir":"/tmp/harvest-test/vault/60-nsls-knowledge-local","kb_push":false,"write_authorized":true}\n' > /tmp/harvest-meeting-ctx/target.json
sed -n '/^### 1b\. Load topic index and rubric/,/^## Step 2/p' \
  ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md \
  | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' | bash
echo "--- rubric cached? ---"; head -1 /tmp/harvest-meeting-ctx/rubric.md
```
Expected: heartbeat `Step 1b: loaded 4 topic files, rubric is ~NNNN chars` (the four topic stubs; `_index.md` is skipped by the `startswith('_')` filter and `CLAUDE.md` is not a topic). `rubric.md` first line shows the rubric header. (Rubric chars > 0 confirms the seed CLAUDE.md header was matched.)

- [ ] **Step 4: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest): Step 1b reads KB_DIR; local KB has no low-count alarm"
```

---

## Task 5: Parameterize Step 8 (read KB_DIR; push only when KB_PUSH=true)

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` — Step 8 python block + the end heartbeat.

- [ ] **Step 1: Read KB_DIR + push flag from target.json**

In `SKILL.md`, in the Step 8 python block, find:
```python
kb_dir = pathlib.Path(os.environ['OBSIDIAN_VAULT_PATH']) / '60-nsls-knowledge'
ctx_dir = pathlib.Path('/tmp/harvest-meeting-ctx')
approved = json.loads((ctx_dir / 'approved.json').read_text())
today = datetime.date.today().isoformat()

# Ensure clean tree before write
subprocess.run(['git', '-C', str(kb_dir), 'pull', '--ff-only', '--quiet'], check=True)
```
Replace with:
```python
ctx_dir = pathlib.Path('/tmp/harvest-meeting-ctx')
_t = json.loads((ctx_dir / 'target.json').read_text())
kb_dir = pathlib.Path(_t['kb_dir'])
kb_push = bool(_t.get('kb_push'))
approved = json.loads((ctx_dir / 'approved.json').read_text())
today = datetime.date.today().isoformat()

# Company KB: ensure clean tree before write (rebase on remote). Local KB: no remote, skip.
if kb_push:
    subprocess.run(['git', '-C', str(kb_dir), 'pull', '--ff-only', '--quiet'], check=True)
```

- [ ] **Step 2: Make the push step conditional on KB_PUSH**

In `SKILL.md`, in the Step 8 python block, find the commit + push tail:
```python
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
```
Replace with:
```python
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
            print(f"Step 8: pushed {len(edited_files)} file change(s), {len(approved)} edit(s)")
        except subprocess.CalledProcessError:
            rebase = subprocess.run(['git', '-C', str(kb_dir), 'pull', '--rebase'], capture_output=True, text=True)
            if 'CONFLICT' in (rebase.stdout + rebase.stderr):
                print("Step 8: FATAL — rebase conflict on topic file. Aborting. Resolve manually.")
                subprocess.run(['git', '-C', str(kb_dir), 'rebase', '--abort'])
                raise SystemExit(1)
            subprocess.run(['git', '-C', str(kb_dir), 'push', 'origin', 'main'], check=True)
            print(f"Step 8: pushed after rebase ({len(edited_files)} file change(s), {len(approved)} edit(s))")
else:
    print("Step 8: no approved candidates, nothing to commit.")
```

- [ ] **Step 3: Update the end-of-step heartbeat prose**

In `SKILL.md`, find:
```markdown
**Heartbeat at end:**
```
Step 8: committed <sha> — <N> edits to <M> file(s) in 60-nsls-knowledge
       pushed to origin/main
```
```
Replace with:
```markdown
**Heartbeat at end:**
- *Company KB:* `Step 8: committed <sha> — <N> edits to <M> file(s) in 60-nsls-knowledge` then `pushed to origin/main`.
- *Local KB:* `Step 8: committed <sha> locally — <N> edits to <M> file(s) in 60-nsls-knowledge-local (not pushed — local KB)`.
```

- [ ] **Step 4: Verify Step 8 commits locally and does NOT push**

Run (against the local KB from Task 3/4; craft a minimal approved.json targeting an existing seed topic):
```bash
cat > /tmp/harvest-meeting-ctx/approved.json <<'JSON'
[{"topic_slug":"how-nsls-works","section":"key_decisions","is_new_topic":false,
  "meeting_date":"2026-06-04","text":"Test decision for local harvest verification",
  "meeting_url":"https://fathom.video/calls/0","fathom_timestamp_sec":0,
  "meeting_title":"Local Test Meeting"}]
JSON
printf '{"kb_target":"local","kb_dir":"/tmp/harvest-test/vault/60-nsls-knowledge-local","kb_push":false,"write_authorized":true}\n' > /tmp/harvest-meeting-ctx/target.json
sed -n '/^## Step 8: Apply edits, commit, push/,/^## Step 9/p' \
  ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md \
  | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' | bash
echo "--- log (expect 2 commits, no push errors) ---"
git -C /tmp/harvest-test/vault/60-nsls-knowledge-local log --oneline
echo "--- decision landed? ---"
grep -n "Test decision for local harvest" /tmp/harvest-test/vault/60-nsls-knowledge-local/how-nsls-works.md
```
Expected: heartbeat ends `(not pushed — local KB)`; log shows the scaffold commit + a `harvest:` commit; grep finds the new Key Decision line. No `push` / `origin` error appears.

- [ ] **Step 5: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest): Step 8 reads KB_DIR; push only for company KB"
```

---

## Task 6: Update week-audit (Step 9) for dual target

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` — Step 9a python block, the 9d/9e gating notes, and the 9f section.

- [ ] **Step 1: Parameterize the 9a python block**

In `SKILL.md`, in the `### 9a. Load week context` python block, find:
```python
kb_dir = pathlib.Path(os.environ['OBSIDIAN_VAULT_PATH']) / '60-nsls-knowledge'
```
Replace with:
```python
import json as _json
_t = _json.loads(pathlib.Path('/tmp/harvest-meeting-ctx/target.json').read_text())
kb_dir = pathlib.Path(_t['kb_dir'])
```

- [ ] **Step 2: Re-gate 9d/9e from "SLT-only" to "write-authorized" (now everyone)**

In `SKILL.md`, find the 9d header line:
```markdown
### 9d. Promotion offers (SLT-only)

Skip if `WRITE_AUTHORIZED=false`.
```
Replace with:
```markdown
### 9d. Promotion offers

Available whenever a KB target is set (always, post-routing). Commits respect `kb_push`:
the company KB pushes; a local KB commits only. (Step 8's logic is reused, so this is automatic.)
```

In `SKILL.md`, find the 9e header line:
```markdown
### 9e. Stale-flag offers (SLT-only)
```
Replace with:
```markdown
### 9e. Stale-flag offers
```

- [ ] **Step 3: Replace the 9f non-SLT dead-end with local-aware behavior**

In `SKILL.md`, find the entire `### 9f. Non-SLT path` section:
```markdown
### 9f. Non-SLT path

If `WRITE_AUTHORIZED=false`, after 9c:

```
Step 9: audit-only (not in KB_AUTHORS). To propose changes, edit a topic file
in your local clone and open a PR against thensls/nsls-knowledge.
```

Exit cleanly.
```
Replace with:
```markdown
### 9f. Target note

After 9c, print which KB the audit ran against so the report is unambiguous:

```
Step 9: audit ran against your <company|local> KB (<kb_dir>).
```

There is no audit-only dead-end anymore. Whether company or local, 9d/9e write actions are
available; a local KB commits without pushing.
```

- [ ] **Step 4: Verify 9a loads the local KB week context**

Run:
```bash
printf '{"kb_target":"local","kb_dir":"/tmp/harvest-test/vault/60-nsls-knowledge-local","kb_push":false,"write_authorized":true}\n' > /tmp/harvest-meeting-ctx/target.json
export HARVEST_WEEK="2026-W23"
sed -n '/^### 9a\. Load week context/,/^### 9b\./p' \
  ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md \
  | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' | bash | head -20
```
Expected: JSON output with `"week": "2026-W23"`, a `harvest_commits` array (includes the Task 5 test commit if within the window), and `stale_topics`/`old_open_questions` arrays. No traceback.

- [ ] **Step 5: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "feat(harvest): week-audit reads KB_DIR; write actions available for local KBs"
```

---

## Task 7: Update skill metadata and the .claude stub description

**Files:**
- Modify: `skills/harvest-meeting/SKILL.md` — frontmatter `description`, opening prose line, First-Time Setup framing.
- Modify: `~/.claude/skills/harvest-meeting/SKILL.md` — stub `description`.

- [ ] **Step 1: Update the SKILL.md frontmatter description**

In `SKILL.md`, find:
```yaml
description: Harvest decisions, project definitions, and state changes from SLT meetings into the NSLS Knowledge Base (60-nsls-knowledge). Gated to SLT writers. Use when you've just finished a strategic meeting, want to backfill a specific Fathom URL, or as part of close-day Step 4c / close-week Step 2b.
```
Replace with:
```yaml
description: Harvest decisions, project definitions, and state changes from meetings into a knowledge base. SLT members write to the shared company KB (thensls/nsls-knowledge); everyone else builds a local, private KB (never pushed). Use when you've just finished a strategic meeting, want to backfill a specific Fathom URL, or as part of close-day Step 4c / close-week Step 2b.
```

- [ ] **Step 2: Update the opening prose line**

In `SKILL.md`, find:
```markdown
Pulls decisions, project definitions, and state changes from SLT-recorded meetings, gates them through the employee-facing sensitive-content rubric, and proposes precise edits to topic files in `60-nsls-knowledge`. Approved edits are committed to `main` and pushed.
```
Replace with:
```markdown
Pulls decisions, project definitions, and state changes from recorded meetings, gates them through the employee-facing sensitive-content rubric, and proposes precise edits to topic files. Routing is automatic: SLT members (on `kb_authors.txt`) write to the shared company KB (`60-nsls-knowledge`) and push to `main`; everyone else writes to a local, private KB (`60-nsls-knowledge-local`) that is committed locally and never pushed.
```

- [ ] **Step 3: Add a one-line note to First-Time Setup clarifying it's company-only**

In `SKILL.md`, find the `One-time setup for a new SLT writer:` line and insert a note immediately before it:
```markdown
> **This setup applies only to SLT members writing to the company KB.** Non-SLT users need
> no setup — the local KB is scaffolded automatically on first run.

One-time setup for a new SLT writer:
```

- [ ] **Step 4: Update the .claude stub description**

Read `~/.claude/skills/harvest-meeting/SKILL.md`, then in it find the `description:` value (the "Gated to SLT writers" wording) and replace it with the same new description from Step 1.

- [ ] **Step 5: Verify both descriptions match and drop the "Gated to SLT writers" phrasing**

Run:
```bash
echo "--- repo SKILL.md ---"; grep -m1 "^description:" ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md
echo "--- .claude stub ---"; grep -m1 "Gated to SLT" ~/.claude/skills/harvest-meeting/SKILL.md && echo "STILL PRESENT (fix)" || echo "stub updated: OK"
```
Expected: repo description shows the new dual-target wording; stub check prints `stub updated: OK`.

- [ ] **Step 6: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -m "docs(harvest): describe dual-target routing in skill metadata"
```
(The `.claude` stub is outside the repo and not committed here — it is a generated redirect; note its manual edit in the PR description.)

---

## Task 8: Caller integration check (close-day Step 4c, close-week Step 2b)

**Files:**
- Read + maybe modify: `skills/close-day/SKILL.md` (Step 4c).
- Read + maybe modify: `skills/close-week/SKILL.md` (Step 2b).

- [ ] **Step 1: Read both callers' harvest sections**

Run:
```bash
grep -n -A 25 "harvest-meeting" ~/nsls-skills/nsls-personal-toolkit/skills/close-day/SKILL.md
echo "=============="
grep -n -A 25 "harvest-meeting" ~/nsls-skills/nsls-personal-toolkit/skills/close-week/SKILL.md
```

- [ ] **Step 2: Decide if wording needs a tweak**

Read the output. The invocation (`/harvest-meeting --date $YESTERDAY`, `--week-audit --week ...`) is unchanged and correct for both targets, so **no code change is required**. Apply a wording tweak ONLY if a caller's prose explicitly tells the user the harvest is "SLT-only" or "skipped if you're not on SLT" — that statement is now false. If such a line exists, replace it with: `Harvests to the company KB if you're on SLT, otherwise to your local KB.` If no such line exists, make no edit and record that in the next step.

> **Heartbeat (do not skip silently):** print one line stating what you found, e.g.
> `Task 8: close-day mentions harvest at line N — no SLT-only claim, no edit needed` or
> `Task 8: close-week line N claimed SLT-only — updated`.

- [ ] **Step 3: Commit only if an edit was made**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
if ! git diff --quiet skills/close-day/SKILL.md skills/close-week/SKILL.md; then
  git add skills/close-day/SKILL.md skills/close-week/SKILL.md
  git commit -m "docs(close-day,close-week): harvest is dual-target, not SLT-only"
else
  echo "Task 8: no caller wording changes needed"
fi
```

> **Note:** `skills/close-day/SKILL.md` already had an unrelated uncommitted modification in the
> working tree before this work began. Do NOT stage or commit that unrelated change — if
> `git diff` shows hunks you didn't make in this task, `git add -p` only your harvest-wording
> hunk, or leave the file alone and note it for the PR.

---

## Task 9: End-to-end verification and cleanup

- [ ] **Step 1: Full local-path dry run from a clean state**

Run:
```bash
rm -rf /tmp/harvest-test /tmp/harvest-meeting-ctx
mkdir -p /tmp/harvest-test/vault /tmp/harvest-meeting-ctx
printf 'slt@nsls.org\n' > /tmp/test-authors.txt
export OBSIDIAN_VAULT_PATH=/tmp/harvest-test/vault

# Step 0 (non-SLT identity) → expect local routing + stash files
GIT_AUTHOR_EMAIL=nobody@example.com HARVEST_AUTHORS_FILE=/tmp/test-authors.txt \
  bash -c 'sed -n "/PYTHONPATH=\/tmp\/pptx_deps python3.12 -c/,/^\`\`\`$/p" \
    ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md | sed "1d;\$d" | bash'
echo "=== target.json ==="; cat /tmp/harvest-meeting-ctx/target.json
echo "=== env.sh ==="; cat /tmp/harvest-meeting-ctx/env.sh

# Step 1a → scaffold local KB
sed -n '/^### 1a\. Ensure KB local clone is fresh/,/^### 1b\./p' \
  ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md \
  | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' | bash

# Step 1b → load topics + rubric
sed -n '/^### 1b\. Load topic index and rubric/,/^## Step 2/p' \
  ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md \
  | sed -n '/^```bash$/,/^```$/p' | sed '1d;$d' | bash

echo "=== remotes (must be empty) ==="; git -C /tmp/harvest-test/vault/60-nsls-knowledge-local remote
```
Expected: `target.json` → `local`; local KB scaffolded; 1b loads 4 topics + non-empty rubric; remotes empty. Any traceback or non-empty remote is a failure — stop and fix the offending task before proceeding.

- [ ] **Step 2: Confirm no hardcoded company path remains in parameterized steps**

Run:
```bash
grep -n "60-nsls-knowledge'" ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md
grep -n "OBSIDIAN_VAULT_PATH'\] / '60-nsls-knowledge" ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md
```
Expected: **no matches** from the second grep (all python blocks now read `target.json`). The first grep may match only prose/heartbeat lines and the company-branch in Step 1a — confirm each remaining hit is intentional (company-only branch or descriptive text), not a live python path.

- [ ] **Step 3: Push the branch and open a PR**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git push -u origin harvest-dual-target
gh pr create --title "harvest-meeting: dual-target (company KB for SLT, local KB for everyone)" \
  --body "$(cat <<'BODY'
Makes /harvest-meeting useful for the whole org. The kb_authors.txt allowlist now routes
rather than gates: SLT → company KB (pushed); everyone else → a local, private KB
(committed locally, no remote, scaffolded from an org-level seed on first run).

Spec: docs/specs/2026-06-04-harvest-dual-target-design.md
Plan: docs/plans/2026-06-04-harvest-dual-target.md

Manual step (outside repo): ~/.claude/skills/harvest-meeting/SKILL.md stub description was
updated to match (generated redirect, not tracked here).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)"
```

- [ ] **Step 4: Wait for the Macroscope status check, then address per the PR loop**

Per the repo convention: green check with no comments → reviewed-clean. Posted comments → fix, then re-push. Read inline comments via `gh api repos/thensls/nsls-personal-toolkit/pulls/<N>/comments`, not just `gh pr view`.

---

## Self-Review

**Spec coverage:**
- Routing variables / `WRITE_AUTHORIZED` flip → Task 2 ✓
- `looks_misconfigured` routes local + nags → Task 2 Step 3 ✓
- Local first-run setup, no remote → Task 3 ✓
- Seed scaffold (org-level, rubric carrier) → Task 1 ✓
- Parameterize 1b / 8 / 9 → Tasks 4, 5, 6 ✓
- Company-only low-count alarm → Task 4 Step 2 ✓
- Conditional push → Task 5 ✓
- 9d/9e always-on, 9f replaced → Task 6 ✓
- Metadata/description updates (repo + stub) → Task 7 ✓
- Caller integration check → Task 8 ✓
- Verification (SLT routes company; non-SLT scaffolds + commits + no push; misconfigured note; rubric found; push impossible) → Tasks 2,3,4,5,9 ✓

**Placeholder scan:** Seed file contents, rubric text, and every replacement code block are given in full. Task 8's edit is conditional by design, with an explicit heartbeat and a no-op branch — not a placeholder. No "TBD"/"handle edge cases"/"similar to Task N".

**Type/name consistency:** `KB_TARGET`/`KB_DIR`/`KB_PUSH` (bash, from `env.sh`) and `kb_target`/`kb_dir`/`kb_push`/`write_authorized` (json keys in `target.json`) are used consistently across Tasks 2–9. `HARVEST_AUTHORS_FILE` override defined in Task 2 Step 1 and used in Tasks 2 & 9. `/tmp/harvest-meeting-ctx/{target.json,env.sh,rubric.md,approved.json}` paths consistent throughout.
