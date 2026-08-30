---
name: kb-owners
description: Map owners and contributors across the NSLS Knowledge Base catalog, and repair person-reference wikilinks after a name change (e.g. a rename in Rippling/employees.json). Use when the user says "kb owners", "map owners", "owner campaign", "/kb-owners", "assign topic owners", "kb rename", or wants to sweep the KB for unowned nodes or fix stale "[[Old Name]]" links after someone's name changed.
---

# KB Owners — Ownership Mapping & Rename Repair

Two jobs against the shared NSLS Knowledge Base (`thensls/nsls-knowledge`):

1. **Owner mapping campaign** (default) — batch through catalog nodes missing an `owner` or `contributors`, suggest a pick with a one-line reason, and write confirmed picks as frontmatter.
2. **Rename repair** (`--rename "Old Name" "New Name"`) — sweep every root topic file for stale `[[Old Name]]` wikilinks (owner, contributors, any other reference) and fix them in one commit. This is the plan's R5/AE4 rename repair — the concrete trigger was a staff member's legal name change (Morgan Ellis → Morgan Reyes).
3. **Light links append** (`--links <slug>`) — append reference links to a single node.

This skill only ever writes to the **company** KB. Unlike `harvest-meeting`, there is no local-KB variant: owner mapping and rename repair are only meaningful against the shared catalog and the shared people directory (`_data/employees.json`), which don't exist in a private local KB. If you're not an SLT writer, the skill refuses cleanly rather than scaffolding something you'd have no reason to run this against.

## First-Time Setup

Same clone, same allowlist as `harvest-meeting` — if that skill works for you, this one will too. Read `skills/harvest-meeting/SKILL.md`'s **First-Time Setup** section for the full walkthrough. The short version:

```bash
git clone https://github.com/thensls/nsls-knowledge.git "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge"
git -C "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge" config user.email <you>@nsls.org
```

Prerequisites: your `@nsls.org` email is in `skills/harvest-meeting/kb_authors.txt` (this skill reads that same file — not a copy), and your GitHub account is a collaborator on `thensls/nsls-knowledge`. If the clone 404s, ping Marcus.

## Modes

| Mode | When | What it does |
|---|---|---|
| (none) | Default | Owner/contributor mapping campaign, ~10 nodes per batch |
| `--rename "Old Name" "New Name"` | A person's name changed | Sweep + fix every `[[Old Name]]` wikilink, one commit |
| `--links <slug>` | Adding reference material to one node | Append `- "Title \| https://url"` entries to that node's `links:` |

## Step 0: Mode dispatch + SLT gate

Parse the invocation for `--rename`, `--links <slug>`, or neither (default campaign mode).

This mirrors `harvest-meeting`'s Step 0 identity resolution — same allowlist file, same cwd-independent scope check — but the outcome is binary (write or refuse), not a company/local route, since there's nothing meaningful to route to.

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 -c "
import os, subprocess, sys, pathlib, re, json

candidates_paths = [
    pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt',
    pathlib.Path.home() / '.claude/plugins/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt',
]
override = os.environ.get('HARVEST_AUTHORS_FILE')
authors_file = pathlib.Path(override) if override and pathlib.Path(override).exists() else next((p for p in candidates_paths if p.exists()), None)
if not authors_file:
    print('FATAL: kb_authors.txt not found (shared with harvest-meeting)'); sys.exit(2)
authors = {l.strip() for l in authors_file.read_text().splitlines() if l.strip() and not l.startswith('#')}

def git_email(*scope):
    try: return subprocess.check_output(['git', *scope, 'config', 'user.email'], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: return ''

def env_file_email(path, *keys):
    try: text = pathlib.Path(path).read_text()
    except Exception: return ''
    for key in keys:
        m = re.search(rf'^{re.escape(key)}=(.+)\$', text, re.MULTILINE)
        if m: return m.group(1).strip()
    return ''

vault = pathlib.Path(os.environ.get('OBSIDIAN_VAULT_PATH', ''))
kb_dir = vault / '60-nsls-knowledge'
toolkit_dir = pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit'
env_candidates = [
    pathlib.Path.home() / '.claude/local-plugins/nsls-personal-toolkit/.env',
    pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit/.env',
]
env_file = next((p for p in env_candidates if p.exists()), None)
env_email = env_file_email(env_file, 'BUILDER_EMAIL', 'OPERATING_USER_EMAIL') if env_file else ''

scopes = [
    ('kb-repo', git_email('-C', str(kb_dir))),
    ('global', git_email('--global')),
    ('toolkit-repo', git_email('-C', str(toolkit_dir))),
    ('env-var', os.environ.get('GIT_AUTHOR_EMAIL', '')),
    ('toolkit-.env', env_email),
]
matched = [(s, e) for s, e in scopes if e and e in authors]
is_slt = bool(matched)

print('emails_checked: ' + ' | '.join(f'{s}={e or \"-\"}' for s, e in scopes))
print(f'slt_writer: {is_slt}')
if is_slt: print(f'matched_via: {matched[0][0]} ({matched[0][1]})')

nsls_emails = sorted({e for _, e in scopes if e and e.endswith('@nsls.org')})
looks_misconfigured = (not is_slt) and bool(nsls_emails)
print(f'looks_misconfigured: {looks_misconfigured}')
if nsls_emails: print('nsls_emails_detected: ' + ', '.join(nsls_emails))

pathlib.Path('/tmp/kb-owners-ctx').mkdir(exist_ok=True)
pathlib.Path('/tmp/kb-owners-ctx/gate.json').write_text(json.dumps({'is_slt': is_slt, 'kb_dir': str(kb_dir)}, indent=2))
"
```

**Heartbeat + gate:**

- `slt_writer: True` → "Step 0: SLT writer ({matched_email} via {scope}) → proceeding against the company KB." Continue.
- `slt_writer: False` and `looks_misconfigured: True` → heartbeat the same allowlist-gap note as harvest-meeting (checked scopes, detected `@nsls.org` emails, "ping Marcus to add you to `kb_authors.txt`"), then **stop — do not write**.
- `slt_writer: False` and `looks_misconfigured: False` → "Step 0: not on the SLT allowlist — kb-owners only operates on the shared company KB, so there's nothing to do here. This is expected if you're not SLT." Stop cleanly, no error tone.

## Step 1: Load KB clone + catalog + people directory

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import pathlib, json, re, subprocess

gate = json.loads(pathlib.Path('/tmp/kb-owners-ctx/gate.json').read_text())
kb_dir = pathlib.Path(gate['kb_dir'])

if not (kb_dir / '.git').exists():
    print(f"Step 1: FATAL — company KB not cloned to {kb_dir}. See First-Time Setup."); raise SystemExit(1)

subprocess.run(['git', '-C', str(kb_dir), 'pull', '--ff-only', '--quiet'], check=True)
head = subprocess.check_output(['git', '-C', str(kb_dir), 'rev-parse', '--short', 'HEAD'], text=True).strip()

people = json.loads((kb_dir / '_data' / 'employees.json').read_text())['people']
active = [p for p in people if p.get('status') == 'Active']

nodes = {}
for md in sorted(kb_dir.glob('*.md')):
    if md.name.startswith('_') or md.name in ('README.md', 'CLAUDE.md'):
        continue
    text = md.read_text()
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.DOTALL)
    if not m:
        continue
    fm_raw, body = m.groups()
    fm = {}
    for line in fm_raw.split('\n'):
        if ':' in line:
            k, _, v = line.partition(':')
            fm[k.strip()] = v.strip()
    kd = re.search(r'## Key Decisions\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    decisions = re.findall(r'^- .+$', kd.group(1), re.MULTILINE) if kd else []
    nodes[md.stem] = {'frontmatter': fm, 'decision_count': len(decisions), 'body_len': len(body), 'path': str(md)}

ctx = pathlib.Path('/tmp/kb-owners-ctx')
ctx.mkdir(exist_ok=True)
(ctx / 'nodes.json').write_text(json.dumps(nodes, indent=2))
(ctx / 'people.json').write_text(json.dumps(people, indent=2))
(ctx / 'kb_dir.txt').write_text(str(kb_dir))

print(f"Step 1: KB synced to {head}")
print(f"Step 1: loaded {len(nodes)} topic nodes, {len(people)} people ({len(active)} active) from _data/employees.json")
PYEOF
```

If node count is under ~40, stop and check the clone — that's a sign it's stale or corrupt (mirrors harvest-meeting's same low-count alarm).

---

## Flow 1: Owner Mapping Campaign (default)

### Step 2: Identify nodes needing attention

A node needs attention if `owner` is missing/empty **or** `contributors` is missing/empty. Skip anything typed `l2` or `l3` — those are structural nodes that get owners assigned deliberately at the offsite, not via batch campaign (see Guardrails).

```python
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import json, pathlib

nodes = json.loads(pathlib.Path('/tmp/kb-owners-ctx/nodes.json').read_text())
EXCLUDED_TYPES = {'l2', 'l3'}

def clean(v):
    return (v or '').strip().strip('"').strip('[]').strip()

candidates = []
for slug, n in nodes.items():
    fm = n['frontmatter']
    if fm.get('type') in EXCLUDED_TYPES:
        continue
    owner = clean(fm.get('owner'))
    contributors_missing = not clean(fm.get('contributors'))
    owner_missing = not owner
    if not (owner_missing or contributors_missing):
        continue
    candidates.append({
        'slug': slug, 'type': fm.get('type', ''), 'title': slug.replace('-', ' ').title(),
        'owner': owner or None, 'owner_missing': owner_missing,
        'contributors_missing': contributors_missing,
        'decision_count': n['decision_count'], 'body_len': n['body_len'],
        'parent': clean(fm.get('parent')),
    })

# Thinnest-first: unowned KPIs surface before owned-but-no-contributors nodes,
# and within a group, fewer Key Decisions / shorter body comes first.
candidates.sort(key=lambda c: (
    0 if c['type'] == 'kpi' else 1,
    0 if c['owner_missing'] else 1,
    c['decision_count'],
    c['body_len'],
))

pathlib.Path('/tmp/kb-owners-ctx/candidates.json').write_text(json.dumps(candidates, indent=2))
unowned = sum(1 for c in candidates if c['owner_missing'])
print(f"Step 2: {len(candidates)} nodes need attention ({unowned} fully unowned, "
      f"{len(candidates) - unowned} owned but missing contributors) — l2/l3 excluded")
print(f"Step 2: batch 1 of {-(-len(candidates)//10)} queued ({min(10, len(candidates))} nodes)")
PYEOF
```

### Step 3: Generate a suggested owner + one-line why, per node in the current batch

Gather signals programmatically, then ask Claude to synthesize one suggestion per node.

**Signals to gather per candidate:**

1. **`proposed_by`** frontmatter field, if present — strongest signal (someone already flagged themselves as the proposer).
2. **Sibling-owner mode** — among all nodes sharing this node's `parent`, tally existing `owner` values; a majority owner is a strong suggestion (`"N of M sibling nodes under [[parent]] are owned by X"`).
3. **Harvest attribution** — `git -C <kb_dir> log --follow --pretty=format:%s -- <slug>.md` to pull every commit subject that touched this file (harvest commits embed meeting titles, e.g. `"harvest: 2026-06-02 Marcus <> Kyle (3 edits)"`). Extract name-like tokens from those subjects and fuzzy-match against `people.json` names; tally frequency.
4. **Department/topic match** — pass the node's slug/title/parent plus the people directory (name, department, role_title, status) to Claude and ask for a semantic match (e.g. `chapter-health` → Client Services / Member Experience department).

Ask Claude, per node:

```
Node: <slug> (type: <type>, parent: <parent>)
Signals:
  - proposed_by: <value or "none">
  - sibling owners: <tally, e.g. "Priya Nakamura (3/4)">
  - harvest attribution (name mentions in commit subjects): <tally>
  - candidate people (name, department, role, active): <compact people list>

Suggest ONE owner (must be a name from the people list) with a one-line why,
weighting proposed_by > sibling mode > department match > harvest attribution.
If signals conflict or are all weak, say so and suggest the department-closest
active person as a tentative pick. Also suggest 0-2 contributors if a
secondary person shows up in the signals (e.g. second-most-frequent harvest
name, or a sibling co-owner).

Return JSON: {"suggested_owner": "<Name>", "why": "<one sentence>",
"suggested_contributors": ["<Name>", ...], "confidence": "high"|"medium"|"low"}
```

Stash results back onto each candidate in `/tmp/kb-owners-ctx/candidates.json`.

**Heartbeat:** `Step 3: suggested owner for N/N nodes in batch (K high, M medium, J low confidence)`

### Step 4: Present the batch, confirm/override

Use `AskUserQuestion` in batches of ~10 (one question per node, sent together). Show per node:

```
<slug>.md (<type>) — current owner: <owner or "none">, contributors: <list or "none">
  SUGGESTED owner: <Name> — <why>
  suggested contributors: <Name, Name or "none">
```

Options per node: accept suggestion / pick a different name (free text — validated in Step 5) / skip (leave as-is) / edit contributors only.

**Heartbeat:** `Step 4: presented batch of N, user confirmed K as-suggested, J overridden, I skipped`

### Step 5: Apply picks as frontmatter edits

For every confirmed pick, validate the name resolves in `people.json` (exact match on `name`, non-empty `email`) before writing it. This is the same "never invent a name" discipline as the rest of the toolkit.

```python
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import json, pathlib, re, datetime

ctx = pathlib.Path('/tmp/kb-owners-ctx')
kb_dir = pathlib.Path(ctx.joinpath('kb_dir.txt').read_text())
people = json.loads((ctx / 'people.json').read_text())
by_name = {p['name']: p for p in people}
picks = json.loads((ctx / 'picks.json').read_text())  # [{slug, owner, contributors: [...]}]
today = datetime.date.today().isoformat()

warnings = []
edited = []
for pick in picks:
    target = kb_dir / f"{pick['slug']}.md"
    text = target.read_text()

    def resolve(name):
        p = by_name.get(name)
        if not p:
            warnings.append(f"{pick['slug']}: '{name}' not found in people directory — writing anyway, verify by hand")
        elif not p.get('email'):
            warnings.append(f"{pick['slug']}: '{name}' matched but has no email on file — verify this is the right person")
        return name

    if pick.get('owner'):
        owner_line = f'owner: "[[{resolve(pick["owner"])}]]"'
        if re.search(r'^owner:.*$', text, re.MULTILINE):
            text = re.sub(r'^owner:.*$', owner_line, text, count=1, flags=re.MULTILINE)
        else:
            text = re.sub(r'^(---\n)', rf'\1{owner_line}\n', text, count=1)

    if pick.get('contributors'):
        names = [resolve(n) for n in pick['contributors']]
        contrib_line = 'contributors: [' + ', '.join(f'"[[{n}]]"' for n in names) + ']'
        if re.search(r'^contributors:.*$', text, re.MULTILINE):
            text = re.sub(r'^contributors:.*$', contrib_line, text, count=1, flags=re.MULTILINE)
        else:
            text = re.sub(r'^(owner:.*$)', rf'\1\n{contrib_line}', text, count=1, flags=re.MULTILINE)

    text = re.sub(r'^(last-updated:\s*)\S+', rf'\g<1>{today}', text, count=1, flags=re.MULTILINE)
    target.write_text(text)
    edited.append(pick['slug'])

pathlib.Path('/tmp/kb-owners-ctx/edited.json').write_text(json.dumps(edited, indent=2))
pathlib.Path('/tmp/kb-owners-ctx/warnings.json').write_text(json.dumps(warnings, indent=2))
print(f"Step 5: applied {len(edited)} edit(s); {len(warnings)} name-resolution warning(s)")
for w in warnings:
    print(f"Step 5: ⚠ {w}")
PYEOF
```

### Step 6: Commit the batch, push

Same idiom as harvest-meeting Step 8: `pull --ff-only` first, `git add` the touched files, one commit per batch, push with rebase-retry.

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import json, pathlib, subprocess

ctx = pathlib.Path('/tmp/kb-owners-ctx')
kb_dir = pathlib.Path(ctx.joinpath('kb_dir.txt').read_text())
edited = json.loads((ctx / 'edited.json').read_text())

if not edited:
    print("Step 6: nothing to commit."); raise SystemExit(0)

subprocess.run(['git', '-C', str(kb_dir), 'pull', '--ff-only', '--quiet'], check=True)
rel = [f"{s}.md" for s in edited]
subprocess.run(['git', '-C', str(kb_dir)] + ['add'] + rel, check=True)
msg = f"kb-owners: map owners/contributors for {len(edited)} node(s) ({', '.join(edited[:5])}{'...' if len(edited) > 5 else ''})"
subprocess.run(['git', '-C', str(kb_dir), 'commit', '-m', msg], check=True)

try:
    subprocess.run(['git', '-C', str(kb_dir), 'push', 'origin', 'main'], check=True)
except subprocess.CalledProcessError:
    rebase = subprocess.run(['git', '-C', str(kb_dir), 'pull', '--rebase'], capture_output=True, text=True)
    if 'CONFLICT' in (rebase.stdout + rebase.stderr):
        print("Step 6: FATAL — rebase conflict. Aborting, resolve manually."); subprocess.run(['git', '-C', str(kb_dir), 'rebase', '--abort']); raise SystemExit(1)
    subprocess.run(['git', '-C', str(kb_dir), 'push', 'origin', 'main'], check=True)

head = subprocess.check_output(['git', '-C', str(kb_dir), 'rev-parse', '--short', 'HEAD'], text=True).strip()
print(f"Step 6: committed {head} — {len(edited)} node(s), pushed to origin/main")
PYEOF
```

Repeat Steps 3–6 for the next batch of ~10 until `candidates.json` is exhausted or Marcus stops the campaign.

---

## Flow 2: Rename Repair (`--rename "Old Name" "New Name"`)

The one guardrail exemption in this skill: rename repair runs against **every** root topic file, including `l2`/`l3` — this is a mechanical reference-integrity fix (a stale wikilink after a real-world name change), not an editorial ownership decision, so the l2/l3 exclusion from Flow 1 does not apply here.

### Step R1: Validate the new name

Check `New Name` resolves in `people.json` (exact match, email present). If not found, warn but continue — a rename can legitimately run ahead of the next Rippling sync (this was the actual Morgan Ellis → Morgan Reyes case).

### Step R2: Sweep for `[[Old Name]]`

```python
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import pathlib, sys, json

kb_dir = pathlib.Path(pathlib.Path('/tmp/kb-owners-ctx/kb_dir.txt').read_text())
old_name, new_name = sys.argv[1], sys.argv[2]
old_link, new_link = f"[[{old_name}]]", f"[[{new_name}]]"

diffs = {}
for md in sorted(kb_dir.glob('*.md')):
    if md.name.startswith('_'):
        continue
    text = md.read_text()
    count = text.count(old_link)
    if count:
        diffs[md.stem] = count

pathlib.Path('/tmp/kb-owners-ctx/rename.json').write_text(json.dumps({
    'old_name': old_name, 'new_name': new_name, 'diffs': diffs,
}, indent=2))
print(f"Step R2: found {sum(diffs.values())} occurrence(s) of {old_link} across {len(diffs)} file(s)")
for slug, n in diffs.items():
    print(f"  - {slug}.md: {n} occurrence(s)")
PYEOF
```

If zero occurrences: heartbeat `Step R2: no "[[Old Name]]" references found — nothing to rename.` and stop.

### Step R3: Show diff summary, confirm

```
Rename [[Old Name]] → [[New Name]] across N files:
  - <slug>.md (K occurrence(s)) — fields: owner, contributors
  ...

Proceed? yes / cancel
```

### Step R4: Apply, one rename commit, push

```python
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import pathlib, json, subprocess

ctx = pathlib.Path('/tmp/kb-owners-ctx')
kb_dir = pathlib.Path(ctx.joinpath('kb_dir.txt').read_text())
rename = json.loads((ctx / 'rename.json').read_text())
old_link, new_link = f"[[{rename['old_name']}]]", f"[[{rename['new_name']}]]"

subprocess.run(['git', '-C', str(kb_dir), 'pull', '--ff-only', '--quiet'], check=True)

touched = []
for slug in rename['diffs']:
    p = kb_dir / f"{slug}.md"
    text = p.read_text().replace(old_link, new_link)
    p.write_text(text)
    touched.append(f"{slug}.md")

subprocess.run(['git', '-C', str(kb_dir), 'add'] + touched, check=True)
msg = f"kb-owners: rename {old_link} -> {new_link} across {len(touched)} file(s)"
subprocess.run(['git', '-C', str(kb_dir), 'commit', '-m', msg], check=True)

try:
    subprocess.run(['git', '-C', str(kb_dir), 'push', 'origin', 'main'], check=True)
except subprocess.CalledProcessError:
    rebase = subprocess.run(['git', '-C', str(kb_dir), 'pull', '--rebase'], capture_output=True, text=True)
    if 'CONFLICT' in (rebase.stdout + rebase.stderr):
        print("Step R4: FATAL — rebase conflict. Aborting, resolve manually."); subprocess.run(['git', '-C', str(kb_dir), 'rebase', '--abort']); raise SystemExit(1)
    subprocess.run(['git', '-C', str(kb_dir), 'push', 'origin', 'main'], check=True)

head = subprocess.check_output(['git', '-C', str(kb_dir), 'rev-parse', '--short', 'HEAD'], text=True).strip()
print(f"Step R4: committed {head} — renamed across {len(touched)} file(s), pushed to origin/main")
PYEOF
```

---

## Flow 3: Light Links Append (`--links <slug>`)

### Step L1: Validate

Confirm `<kb_dir>/<slug>.md` exists. Same l2/l3 exclusion as Flow 1 (this is an additive-but-still-editorial write — a link is curated content, so it follows the same "structural nodes get curated at the offsite" rule). If the slug is `l2`/`l3`-typed, refuse: `Step L1: <slug>.md is type <l2|l3> — links on structural nodes are curated manually, not via kb-owners.`

### Step L2: Prompt for pairs

Loop, asking for `Title | URL` pairs until the user says "done". Validate each URL starts with `http`.

### Step L3: Append, commit

```python
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import pathlib, json, re, subprocess

ctx = pathlib.Path('/tmp/kb-owners-ctx')
kb_dir = pathlib.Path(ctx.joinpath('kb_dir.txt').read_text())
payload = json.loads((ctx / 'links.json').read_text())  # {"slug": "...", "links": [{"title": "...", "url": "..."}]}
slug, links = payload['slug'], payload['links']
target = kb_dir / f"{slug}.md"
text = target.read_text()

# Flat strings, never dicts: "- \"Title | https://url\""
new_lines = '\n'.join(f'  - "{l["title"]} | {l["url"]}"' for l in links)

if re.search(r'^links:', text, re.MULTILINE):
    text = re.sub(r'(^links:\s*\n)', rf'\1{new_lines}\n', text, count=1, flags=re.MULTILINE)
else:
    text = re.sub(r'(^---\n)', rf'\1links:\n{new_lines}\n', text, count=1, flags=re.MULTILINE)

target.write_text(text)

subprocess.run(['git', '-C', str(kb_dir), 'pull', '--ff-only', '--quiet'], check=True)
subprocess.run(['git', '-C', str(kb_dir), 'add', f"{slug}.md"], check=True)
subprocess.run(['git', '-C', str(kb_dir), 'commit', '-m', f"kb-owners: add {len(links)} link(s) to {slug}.md"], check=True)
subprocess.run(['git', '-C', str(kb_dir), 'push', 'origin', 'main'], check=True)
head = subprocess.check_output(['git', '-C', str(kb_dir), 'rev-parse', '--short', 'HEAD'], text=True).strip()
print(f"Step L3: committed {head} — added {len(links)} link(s) to {slug}.md, pushed to origin/main")
PYEOF
```

---

## Guardrails (recap)

- **SLT gate before any write** (Step 0). No local-KB fallback — refuse cleanly if not on `kb_authors.txt`.
- **Never touch `l2`/`l3`-typed files** in Flow 1 (owner campaign) or Flow 3 (links) — structural nodes are curated deliberately, not batched. **Exception: Flow 2 (rename) runs against all files including `l2`/`l3`**, since a stale wikilink is a correctness bug, not an editorial call.
- **Validate every assigned/renamed name** against `_data/employees.json` (exact name match, email present). Warn — don't silently write — on any miss (not found, or found with no email on file).
- **The sensitive-content rubric does not apply here.** This skill only ever writes frontmatter (owner/contributors/links) — no narrative Key Decisions or Current State text — so there's nothing for the rubric to gate. `harvest-meeting` still owns rubric enforcement for actual content.

## After a run

Confirm what was written, which KB (`60-nsls-knowledge`) and commit sha(s), and any outstanding warnings (unresolved names, `looks_misconfigured` notes). Point at remaining candidates if the campaign wasn't finished in one session — `candidates.json` in `/tmp/kb-owners-ctx` persists until the next Step 1 reload.
