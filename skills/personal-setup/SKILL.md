---
name: personal-setup
description: >-
  Set up or reconfigure the personal productivity toolkit. Walks through
  Obsidian knowledge base, account connections, and optional integrations.
  Use when the user says "personal-setup", "/personal-setup", "configure
  personal toolkit", or when .env is missing or incomplete.
---

# Personal Productivity Setup

Set up your personal productivity toolkit — the skills that turn Claude into a daily co-pilot for morning planning, end-of-day summaries, weekly reviews, and project logging.

Show the roadmap upfront:

```
Let's set up your personal productivity toolkit.

This takes about 10 minutes:
  1. Set up your knowledge base (Obsidian)        — 5 min
  2. Connect your accounts (mostly auto-detected)  — 2 min
  3. Optional integrations (Fathom meeting notes)  — 3 min
  4. Done — try "open my day" to see it in action
```

## Step 0: Check current state

Read `~/.claude/local-plugins/nsls-personal-toolkit/.env` (if it exists). Identify which values are set and which are empty or missing. If everything is already set, confirm and offer to reconfigure.

## Step 1: Knowledge Base (Obsidian) — ~5 min

This is the foundation — your notes, project logs, and daily plans all live here.

### Auto-detect existing vaults

1. Check common locations: `~/Obsidian/*/`, `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/*/`
2. Look for directories containing `.obsidian/` (the marker for an Obsidian vault)
3. If found, confirm: "I found an Obsidian vault at `[path]` — is that the one you use?"
4. If multiple found, ask which one

### If no vault found

```
You don't have an Obsidian vault set up yet. Obsidian is where your daily
plans, project logs, and weekly reviews live. It's a free markdown editor
that syncs across devices.

Want me to set one up for you? (~5 min)
```

If yes → invoke `/obsidian-setup` to scaffold the vault structure.
If no → ask for the path to their notes directory (works with any folder, just won't have the full Obsidian features).

### Confirm vault path

Once detected or created, confirm: "Your knowledge base is at `[path]` — I'll use this for all your notes and logs."

## Step 2: Connect Accounts — ~2 min

Auto-detect everything possible. Only ask about what can't be detected.

### Slack User ID
The Slack MCP provides the user ID automatically in tool descriptions: "Current logged in user's Slack user_id is U...".

- **Detected**: "Your Slack user ID is `UXXXXXXXX` — look right?"
- **Not detected**: "Click your profile picture in Slack → Profile → ⋮ → Copy member ID, then paste it here."

### Asana
Use the Asana MCP:
```
mcp__claude_ai_Asana__get_me()
```

- **Detected**: "Your Asana workspace GID is `XXXX` and your user GID is `XXXX` — correct?"
- **Not detected**: "Asana integration is only needed for /open-day and /close-day task sync. Want to skip this for now?" If they want to set it up, walk them through finding their GIDs manually.

### Builder Email and GitHub Username
Ask the user:
```
What's your NSLS email? (e.g., jdoe@nsls.org)
And your GitHub username? (optional, for /register-automation)
```

## Step 3: Optional Integrations — ~3 min

### Fathom API Key

```
Do you use Fathom (fathom.video) for meeting recording?

If yes, your API key lets /close-day pull today's meeting summaries
and /person-intelligence pull 1:1 transcripts.

To get your key:
  1. Go to https://fathom.video/settings/api
  2. Copy your API key

Paste it here, or skip — /close-day works without it.
```

If provided, validate with a test call:
```bash
curl -s -H "X-Api-Key: <key>" "https://api.fathom.ai/external/v1/meetings?created_after=$(date +%Y-%m-%d)T00:00:00Z" | head -c 100
```

### Airtable API Key (optional)

```
Airtable API key is optional. You don't need one for org chart, LOPs,
or strategy — those come from the toolkit automatically.

An API key is only needed if you want /person-intelligence to write
relationship profiles to Airtable (rare). Most people skip this.

Skip? (y/n)
```

If they want it, walk them through creating a personal access token at airtable.com/create/tokens with scopes: `data.records:read`, `data.records:write`, `schema.bases:read`.

### Role Coach (optional, recommended)

```
Want coaching from your seat? /role-coach reads your role (title,
accountabilities, optionally the role you're working toward), looks at
what you actually did each week, and coaches the gap — with a memory,
so the same advice doesn't repeat forever.

Everyone can use it:
  - It works from your role docs + notes alone.
  - If you connect Signal (any employee can mint a token at the Signal
    dashboard → it can read YOUR OWN Quick Notes history and goals —
    nobody else's, and your sentiment data is never included), the
    coaching gets evidence-grounded.
  - Managers additionally see their team's signal, execs org-wide —
    scope is enforced by the server, not by this skill.

Set it up now? (y/n) — you can always run /role-coach later; the first
run is a 5-minute interview about your seat.
```

If yes: tell them the first `/role-coach --week` run starts the interview (role-profile.md + optional role-trajectory.md). If they want Signal evidence, point them at `/signal-setup`. Nothing to write to .env — role-coach activates on the presence of `10-strategy/role-coaching/role-profile.md`.

## Step 4: Write Config and Confirm

Write `~/.claude/local-plugins/nsls-personal-toolkit/.env`:

```
# Personal Toolkit Configuration
# Generated by /personal-setup on YYYY-MM-DD

# Obsidian vault (used by /open-day, /close-day, /close-week, /log)
OBSIDIAN_VAULT_PATH=<detected or provided>

# Slack
SLACK_USER_ID=<detected or provided>

# Asana (needed for /open-day and /close-day task sync)
ASANA_WORKSPACE_GID=<detected or provided or empty>
ASANA_USER_GID=<detected or provided or empty>

# Builder identity
BUILDER_EMAIL=<provided>
GITHUB_USERNAME=<provided or empty>

# Fathom (needed for /close-day meeting summaries, /person-intelligence 1:1 transcripts)
FATHOM_API_KEY=<provided or empty>

# Airtable (optional — only needed for writing to Airtable)
AIRTABLE_API_KEY=<provided or empty>
PEOPLE_OPS_BASE_ID=appnXPTu01esWWbrK
SLT_BASE_ID=appHDEHQA4bvlWwQq
LOP_BASE_ID=appAcnl4o8AQVZR1j
```

If a value wasn't provided, leave it empty with a comment:
```
# FATHOM_API_KEY=  # Run /personal-setup again when you have this
```

### KB writer setup (SLT only — auto-detected)

After writing the .env, check whether the builder is an SLT member who should be able to write to the shared knowledge graph (`thensls/nsls-knowledge`). This is gated by `BUILDER_EMAIL` matching an entry in `skills/harvest-meeting/kb_authors.txt` (the canonical SLT allowlist).

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 << 'PYEOF'
import os, pathlib, re, subprocess

env_path = pathlib.Path.home() / '.claude/local-plugins/nsls-personal-toolkit/.env'
authors_path = pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt'
if not authors_path.exists():
    authors_path = pathlib.Path.home() / '.claude/plugins/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt'

env = env_path.read_text() if env_path.exists() else ''
m = re.search(r'^BUILDER_EMAIL=(.+)$', env, re.MULTILINE)
builder_email = m.group(1).strip() if m else ''

authors = set()
if authors_path.exists():
    authors = {line.strip() for line in authors_path.read_text().splitlines()
               if line.strip() and not line.startswith('#')}

is_slt = builder_email in authors
print(f'is_slt: {is_slt}')
print(f'builder_email: {builder_email}')
print(f'authors_known: {len(authors)}')
PYEOF
```

If `is_slt: True`, the builder is on SLT and needs the KB harvest pipeline configured so `/close-day` Step 4c and `/harvest-meeting` don't silently no-op for them:

```
You're on SLT (BUILDER_EMAIL matches kb_authors.txt) — you can write to the
NSLS Knowledge Base. Let me set up the KB clone so /harvest-meeting works.
```

Two sub-checks, both auto-fixable:

**1. Is the KB cloned at `$OBSIDIAN_VAULT_PATH/60-nsls-knowledge`?**

```bash
KB_DIR="$OBSIDIAN_VAULT_PATH/60-nsls-knowledge"
if [ -d "$KB_DIR/.git" ]; then
    echo "✓ KB clone present at $KB_DIR"
else
    echo "✗ KB not cloned. Cloning now..."
    git clone https://github.com/thensls/nsls-knowledge.git "$KB_DIR"
fi
```

If clone fails (no GitHub access, repo private), surface the error clearly: "KB clone failed — make sure your GitHub account has access to `thensls/nsls-knowledge`. Then re-run `/personal-setup` or clone manually."

**2. Is the KB clone's `user.email` set to the builder's NSLS email?**

```bash
CURRENT=$(git -C "$KB_DIR" config user.email 2>/dev/null || true)
if [ "$CURRENT" = "$BUILDER_EMAIL" ]; then
    echo "✓ KB clone identity: $CURRENT"
else
    echo "Setting KB clone identity: $BUILDER_EMAIL (was: ${CURRENT:-<unset>})"
    git -C "$KB_DIR" config user.email "$BUILDER_EMAIL"
fi
```

Tell the builder:
```
KB writer setup complete:
  ✓ Clone:    $KB_DIR
  ✓ Identity: $BUILDER_EMAIL

You can now run `/harvest-meeting --fathom-url <url>` after any strategic
meeting, and /close-day will auto-harvest your meetings each evening.
```

If `is_slt: False`, skip this section entirely — non-SLT builders don't need (and won't have access to) write to the KB. The harvest skill heartbeats a clean "not in KB_AUTHORS, skipping" with no fix needed.

### Populate org context into knowledge base

After writing the .env, sync the org chart into the builder's Obsidian vault. This creates people files with management relationships (reports-to, manages) as wikilinks so the graph view shows the org tree.

Run:
```bash
OBSIDIAN_VAULT_PATH="<vault path from step 1>" python3.12 \
  ~/.claude/local-plugins/nsls-builder-toolkit/_shared/scripts/sync_org_context.py \
  --update-vault
```

This reads from `_shared/context/org-chart.json` (synced weekly by the builder toolkit) and:
- **Existing people files** → merges `department`, `email`, `slack`, `reports-to`, `manages` into frontmatter without clobbering other fields
- **New people** → creates a minimal stub with org data

Tell the builder:
```
I've populated your knowledge base with the NSLS org chart — 
[N] people files with management relationships. Open Obsidian's
graph view to see the org tree.

These stay current automatically. The org chart syncs weekly 
from Airtable, and running /personal-setup again will refresh
your people files with any new hires or role changes.
```

If the builder toolkit isn't installed or `org-chart.json` doesn't exist, skip this step silently — it's a nice-to-have, not a blocker.

### Confirm and suggest first action

```
Your personal productivity toolkit is configured!

  [check] Knowledge base: [vault path]
  [check] Slack: UXXXXXXXX
  [check or skip] Asana: configured / skipped
  [check or skip] Fathom: configured / skipped
  [check or skip] Airtable: skipped (not needed for org context)
  [check] Org chart: [N] people files synced

Try it now — say "open my day" to see your morning planning.

Other things you can do:
  "close my day"           — end-of-day summary
  "plan my week"           — weekly planning (Sunday/Monday)
  /log                     — capture session progress
  /person-intelligence     — relationship profiles

Your .env file is at:
  ~/.claude/local-plugins/nsls-personal-toolkit/.env

This file is gitignored — your keys stay on your machine.
Edit any skill in the toolkit — they're yours to customize.
```

If any values are missing, note which skills are affected:
```
Note: Fathom not configured — /close-day won't include meeting summaries.
Run /personal-setup again anytime to add it.
```

## Edge Cases

- **User already has a .env**: Read existing values, only ask for missing ones. Don't overwrite values that are already set unless the user explicitly asks to reconfigure.
- **No Slack MCP**: Ask the user to find their Slack ID manually.
- **No Asana MCP**: Ask for GIDs manually or skip.
- **Non-NSLS user**: Leave base IDs empty, tell them to fill in their own if they use Airtable. Skip the org chart vault sync and the KB writer setup (both auto-skip cleanly when `BUILDER_EMAIL` isn't an NSLS address).
- **NSLS-but-not-SLT user**: KB writer setup auto-skips when `BUILDER_EMAIL` isn't in `kb_authors.txt`. They get the rest of the toolkit normally; `/harvest-meeting` heartbeats "not in KB_AUTHORS, skipping" if they try to invoke it.
- **User runs this after /setup already configured some values**: Reuse values from the /setup flow (Slack ID, Asana GIDs) — don't ask again.
- **User re-runs /personal-setup**: This is the refresh path. Skip steps where values are already set, but always re-run the org chart vault sync — it's idempotent and picks up new hires, role changes, and management reshuffles since last run.
