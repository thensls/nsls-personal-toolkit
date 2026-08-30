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

**Hand-hold this. One question at a time, wait for the answer, then continue. Never print a wall of steps for the builder to run themselves.**

### Pick a tier first (ask this, wait)

Don't launch into Obsidian — that's where new builders bail. Offer two paths and let them choose:

```
Two ways to set this up:

  • Light (~3 min, recommended to start) — I use a plain notes folder. Nothing
    to install. /open-day and /close-day work immediately, and if you connected
    Fathom during /setup, your meetings flow in too. You can upgrade anytime.

  • Advanced — the full Obsidian knowledge base: a real app, graph view, and
    8 plugins. More powerful, more setup. Great once you're hooked.

Want to start Light? (yes / I'd rather do Advanced)
```

- **Light** → do Step 0, then **Step 1-Light**, then **Step 1.5** (companion), then Step 2 (accounts), then the wrap-up. **Skip the Obsidian app/plugins entirely.**
- **Advanced** → do Step 0, then **Step 1-Advanced** (invoke `/obsidian-setup`), then **Step 1.5** (companion), then the rest.

Either way, reuse whatever `/setup` already did (BUILDER_EMAIL, connected tools) — never re-ask for it.

## Step 0: Check current state

Read `~/.claude/local-plugins/nsls-personal-toolkit/.env` (if it exists). Identify which values are set and which are empty or missing. If everything is already set, confirm and offer to reconfigure. If `/setup` already wrote `BUILDER_EMAIL`, treat it as done — don't ask again.

## Step 1-Light: Notes folder (default, ~1 min)

The light tier needs somewhere to write notes — no Obsidian app required. In order of preference:

1. If an Obsidian vault already exists (auto-detect below), reuse it — no install needed.
2. Otherwise create a plain folder, e.g. `~/NSLS-notes/`, and use it as `OBSIDIAN_VAULT_PATH`. The daily/weekly skills write plain markdown into it and work immediately; the folder becomes a real Obsidian vault later if the builder upgrades to Advanced.

Confirm in one line: "Your notes will live in `[path]` — /open-day and /close-day work now." Then go to Step 1.5 (install the companion). (Auto-detect logic is shared with Advanced, below.)

## Step 1-Advanced: Knowledge Base (Obsidian) — ~5 min

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

## Step 1.5: Install the visual companion — ~2 min, no admin

The companion is the browser dashboard `/open-day` and `/close-day` open **by
default** (the flagship "run your day in a little browser window" experience).
It ships in the repo but needs a one-time editable install into its own venv so
the `toolkit-companion` binary exists where the day skills look for it. Provision
it now — otherwise `visual_mode` is on but the binary is missing, and every
`/open-day` silently falls back to plain chat. Both tiers use it.

**One command, idempotent.** `companion/ensure-companion.sh` does the whole job —
resolves the binary if it already exists (a no-op), otherwise creates the venv and
runs the editable install from the right directory, then prints the binary path.
When the machine has no Python ≥3.10 anywhere (stock macOS ships 3.9), it first
downloads the toolkit's own checksum-pinned private CPython into
`companion/.python-runtime/` — user-space, no admin password — and builds with
that. **Never send anyone to python.org.** Run `--check` first: `build` → warn
"one-time setup, ~30 seconds"; `build-python` → warn "it's fetching its own
Python — a few minutes, just this once" and give the real call a 10-minute
timeout:

```bash
STATE="$(bash "$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh" --check)"
TC="$(bash "$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh")"
[ -n "$TC" ] && "$TC" --help >/dev/null && echo "visual companion ready: $TC"
```

- **Path printed** → say "visual companion ready" (or "already installed" if it
  returned instantly) and continue to Step 2.
- **Empty output** → it couldn't be provisioned. The script prints the reason on
  stderr and logs detail to `companion/.install.log`; read that before guessing,
  and give the builder the reason in one plain sentence — no options menu.
  Re-run with `--force` after fixing the cause.

Note it **verifies the interpreter actually runs** `>=3.10` rather than trusting
that `python` exists — which is what catches the stock-Win11 Microsoft-Store stub
that prints "Python was not found" and **exits 0 while doing nothing**. And when
NO usable interpreter exists anywhere, it does not give up — it downloads the
toolkit's own checksum-pinned CPython into `companion/.python-runtime/` and
builds with that (the `build-python` state above).

<details>
<summary>Equivalent manual steps (only if the script is unavailable)</summary>

The editable install **must** run from inside `companion/` (its `pyproject.toml`
uses `package-dir = {"" = ".."}`):

**macOS/Linux:**
```bash
cd ~/.claude/local-plugins/nsls-personal-toolkit/companion
python3 -m venv .venv
.venv/bin/python -m pip install -e . -q
```

**Windows (PowerShell)** — use a FULL interpreter path to a Python that is
**provably ≥3.10** (shown here with the toolkit's own provisioned runtime), for
the stub reason above:
```powershell
cd "$env:USERPROFILE\.claude\local-plugins\nsls-personal-toolkit\companion"
& "$env:USERPROFILE\.claude\local-plugins\nsls-personal-toolkit\companion\.python-runtime\python\python.exe" -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -e . -q
```
No `.python-runtime` on the machine yet? Pin the launcher to an explicit
version — `py -3.12 -m venv .venv` — **never bare `py -3`**, which can silently
select a 3.9 and fail the companion's ≥3.10 requirement at install time.

Either way, **verify by running `toolkit-companion --help`** at the resulting path
rather than trusting pip's exit code.
</details>

**Manual Python installation is a last resort, never the first move** — the
script provisions its own Python on every supported platform. Only two outcomes
justify suggesting it: `--check` printed `no-python` (downloads disabled or an
unsupported platform), or repeated `--force` retries keep failing while online.
Then — and only then — say: *"The visual companion needs Python 3.10+ and
couldn't set it up itself on this machine — `winget install Python.Python.3.12`
(Windows) or the org installer, then re-run `/personal-setup`."* Meanwhile
`open day visual off` skips visual mode. Never open with that instruction.

> The `install.ps1` / `install.sh` installers provision the companion too — and
> they now install it **by default** when no terminal is reachable
> (`NSLS_SKIP_COMPANION=1` opts out), so piped and agent-driven installs no
> longer skip it. Full Windows details, including auto-start at login, live in
> [`docs/windows-setup.md`](../../docs/windows-setup.md).

## Step 2: Connect Accounts — ~2 min

Auto-detect everything possible. Only ask about what can't be detected.

### Slack User ID
The Slack MCP provides the user ID automatically in tool descriptions: "Current logged in user's Slack user_id is U...".

- **Detected**: "Your Slack user ID is `UXXXXXXXX` — look right?"
- **Not detected**: "Click your profile picture in Slack → Profile → ⋮ → Copy member ID, then paste it here."

### Asana
Use the Asana connector's `get_me` (resolve the live tool name from this
session's tools — connector tools are `mcp__<uuid>__<tool>` with a
per-machine UUID; if no Asana tools are present, the connector isn't
connected — treat as "not detected" below, don't silently skip):
```
get_me()
```

- **Detected**: "Your Asana workspace GID is `XXXX` and your user GID is `XXXX` — correct?"
- **Not detected**: "Asana integration is only needed for /open-day and /close-day task sync. Want to skip this for now?" If they want to set it up, walk them through finding their GIDs manually.

### Builder Email and GitHub Username

Both may already be set — the org `/setup` collects and validates them — so
check the existing `.env` first and confirm instead of re-asking.

**Email:** propose the signed-in account's address; ask only to confirm.

**GitHub username:** this is how the tracker credits **merged PRs** — a wrong
or empty value silently earns no PR credit (this cost a builder six weeks of
points). **Never guess it from the email**; the email prefix has been wrong
for every known builder. Ask: "Which GitHub account do you open pull requests
as?" — and validate before writing, never store an unverified guess:

1. **Account exists?** `curl -s -o /dev/null -w '%{http_code}' "https://api.github.com/users/<name>"`
   → `200` real; `404` typo — show what you checked and re-ask; anything else
   (rate limit, offline) — accept but say you couldn't verify.
2. **Right account?** `curl -s "https://api.github.com/search/issues?q=type:pr+org:thensls+author:<name>&per_page=1"`
   → `total_count` 0 is normal for a brand-new builder, suspicious for someone
   who's shipped NSLS work before — double-check with them (hint, not proof:
   private-repo PRs may not show unauthenticated).

Skippable if they don't use GitHub yet — leave it empty and note they can
re-run `/personal-setup` (or the org `/setup`) after their first PR.

### Display Name and Privacy Gates

Two `person-intelligence` keys. Both fail **safe but quiet** when unset, which
is exactly why they must be asked for rather than skipped — a builder who never
sets them gets a subsystem that silently does nothing and looks fine.

**`OPERATING_USER_NAME` — your name as it appears in calendar titles.**

`summarize_meeting.py` splits a title like `Ada Lovelace / Grace Hopper 1:1`
into "them" and "me". Without knowing which half is you, the first name-shaped
half wins — wrong half the time — so an unset value **disables title inference
entirely** and every meeting returns `UNKNOWN_SUBJECT`.

Propose variants from the name on the signed-in account and ask them to correct
it: full name, first name, and initials, comma-separated.

> "Your calendar titles — do they say **Ada Lovelace**, **Ada**, or **AL**?
> List every form you actually see; I'll store all of them."

Write every variant they name. A missing variant is the sharp edge here: with
only `Ada Lovelace` stored, a title reading `Ada / Grace Hopper` returns **Ada**
— the builder's own short name — as the meeting subject.

**`SIGNAL_EXCLUDE` — people never swept into coaching profiles.**

Board members and anyone else whose Quick Notes must not reach a profile.

**This one fails CLOSED, and the distinction is the whole point:** an **absent**
key means nobody is `signal_eligible` (ingest off); a **present but empty** key
(`SIGNAL_EXCLUDE=`) is a deliberate "exclude nobody" and makes every eligible
`@nsls.org` relationship sweepable. Never describe either as "leave it blank" —
that phrase maps to both, and guessing wrong in the permissive direction puts
board members into coaching profiles.

Offer the three outcomes explicitly and write exactly what they pick:

> "Anyone whose Quick Notes should never reach a coaching profile — board
> members, usually?
>
> - **Give me names** → I write `SIGNAL_EXCLUDE=<names>`; ingest runs, those
>   people excluded.
> - **'Keep it off'** → I leave the key out entirely; Signal ingest stays off.
> - **'Nobody'** → I write `SIGNAL_EXCLUDE=` with no value; ingest runs with
>   **no** exclusions at all."

Then say back which of the three you wrote. Omitting the key and writing it
empty look nearly identical in a diff and behave as opposites.

## Step 3: Optional Integrations — ~3 min

### Fathom (meetings)

**Check the connector first.** If the builder connected Fathom during `/setup`
(the one-click Authorize connector), `/close-day` and `/person-intelligence`
already read meetings through it — **no API key needed.** Verify with a live
`get_identity` / `list_meetings` call; if it works, say "Fathom's already
connected — nothing to do here" and move on.

Only if there's no Fathom connector available do you fall back to an API key:

```
Do you use Fathom (fathom.video) for meeting recording? If yes and the
one-click connector isn't available to you, I can use an API key instead.

To get one: open fathom.video → Settings → API Access, and copy the key.
(Paste it here, or skip — /close-day still works without it.)
```

> Note: the old `fathom.video/settings/api` deep link 404s — always describe the
> path ("Settings → API Access"), never link it.

If a key is provided, validate with a test call:
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

# Person Intelligence — identity + privacy gates
# Your name as it appears in calendar titles, comma-separated variants.
# UNSET disables 1:1 subject inference (every title returns UNKNOWN_SUBJECT).
OPERATING_USER_NAME=<provided>
# Names never swept into coaching profiles (board members, etc).
# OMIT THIS KEY ENTIRELY to keep Signal ingest off (fails closed).
# Present-but-empty (SIGNAL_EXCLUDE=) is the OPPOSITE: ingest on, nobody
# excluded. Write whichever the builder actually chose -- see Step 2.
SIGNAL_EXCLUDE=<names, or omit the whole line to keep ingest off>

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

**Assert the Asana pair before finishing.** Unless the builder explicitly
skipped Asana in Step 2, read the written `.env` back and check that
`ASANA_WORKSPACE_GID` **and** `ASANA_USER_GID` are both non-empty. Empty GIDs
with Asana "set up" means the `get_me` discovery silently failed — most often
because the connector's tools weren't loaded in this session yet (they load on
restart). Say so plainly and either re-run discovery after the restart or
collect the GIDs manually. Never finish with the pair silently empty:
`/open-day` and `/close-day` task sync fail quietly on it, which reads as "the
day-planner is broken."

### KB writer setup (SLT only — auto-detected)

After writing the .env, check whether the builder is an SLT member who should be able to write to the shared knowledge graph (`thensls/nsls-knowledge`). This is gated by `BUILDER_EMAIL` matching an entry in `skills/harvest-meeting/kb_authors.txt` (the canonical SLT allowlist).

```bash
python3 << 'PYEOF'
import pathlib, re, sys

# Resolve kb_authors.txt at the CANONICAL install path first. The old code
# checked ~/nsls-skills and ~/.claude/plugins only — neither exists on a real
# install — so `authors` was always empty and is_slt was False for EVERYONE,
# including genuine SLT members. local-plugins is where the bootstrapper
# and both installers put it; the other two are pre-migration fallbacks.
authors_candidates = [
    pathlib.Path.home() / '.claude/local-plugins/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt',
    pathlib.Path.home() / 'nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt',
    pathlib.Path.home() / '.claude/plugins/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt',
]
authors_path = next((p for p in authors_candidates if p.exists()), None)

env_path = pathlib.Path.home() / '.claude/local-plugins/nsls-personal-toolkit/.env'
# utf-8-sig tolerates a UTF-8 BOM (PowerShell 5.1's Set-Content writes one) and
# is harmless on BOM-less files — read everything user-written this way.
env = env_path.read_text(encoding='utf-8-sig') if env_path.exists() else ''
m = re.search(r'^BUILDER_EMAIL=(.+)$', env, re.MULTILINE)
# Strip surrounding quotes: .env values are commonly written BUILDER_EMAIL="a@b".
# A quoted address matches no allowlist entry, so is_slt would read False for a
# genuine SLT member -- the same silent-negative this block exists to prevent.
builder_email = m.group(1).strip().strip('"').strip("'") if m else ''

if authors_path is None:
    # Fail LOUDLY — never silently treat everyone as non-SLT (the exact failure
    # the KB-writer setup exists to prevent).
    print('FATAL: kb_authors.txt not found at any known path. Expected at')
    print('  ~/.claude/local-plugins/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt')
    print('  Is the toolkit installed there? SLT detection cannot run.')
    sys.exit(2)

authors = {line.strip() for line in authors_path.read_text(encoding='utf-8-sig').splitlines()
           if line.strip() and not line.startswith('#')}

if not authors:
    # The shipped allowlist is deliberately EMPTY (this repo is PUBLIC; a
    # populated copy is an SLT roster). /personal-setup runs BEFORE the KB repo
    # is cloned, so unlike /kb-owners it has no live list to fall back to.
    #
    # Reporting `is_slt: False` here would be the exact failure the comment
    # above describes -- everyone silently non-SLT -- so report UNKNOWN instead.
    # Blind is not the same as negative.
    print('is_slt: unknown')
    print(f'builder_email: {builder_email}')
    print(f'authors_known: 0 (from {authors_path} -- intentionally empty)')
    print('reason: the shipped allowlist carries no entries by design; the live')
    print('  list is _data/kb_authors.txt in thensls/nsls-knowledge (private).')
    print('  ASK the builder whether they are on SLT rather than assuming not.')
    sys.exit(0)

is_slt = builder_email in authors
print(f'is_slt: {is_slt}')
print(f'builder_email: {builder_email}')
print(f'authors_known: {len(authors)} (from {authors_path})')
PYEOF
```

> **Verify the check actually ran (Windows).** A bare `python3` on stock Windows 11 is the Microsoft-Store stub that prints *"Python was not found…"* and **exits 0** — so an empty result (no `is_slt:` line) means the check **did not run**, not that the builder is non-SLT. If you don't see an `is_slt:`/`FATAL:` line, re-run with the full interpreter path (`"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"`) before trusting the outcome — never conclude "not SLT" from silence.

**Three outcomes, not two.** `is_slt: unknown` means the check ran and could not
decide -- the shipped allowlist is intentionally empty and no live list is
reachable before the KB clone exists. Do **not** treat it as `False`: ask the
builder directly ("Are you on the SLT? I can't tell from here"), and configure the
KB pipeline if they say yes. Silently skipping KB setup for a real SLT member is
the failure this whole block exists to prevent.

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

**First, create the write target.** `sync_org_context.py` errors on a missing
`30-people/` but (today) still **exits 0**, so it looks successful while writing
nothing — the Light tier never scaffolds a vault, so this dir usually is missing.
Create it immediately before the sync, platform-safely:
- macOS/Linux: `mkdir -p "$OBSIDIAN_VAULT_PATH/30-people"`
- Windows (PowerShell): `New-Item -ItemType Directory -Force "$env:OBSIDIAN_VAULT_PATH\30-people" | Out-Null` — **never `mkdir -p`** here.

Then run:
```bash
OBSIDIAN_VAULT_PATH="<vault path from step 1>" python3 \
  ~/.claude/local-plugins/nsls-builder-toolkit/_shared/scripts/sync_org_context.py \
  --update-vault
```

**Verify the outcome, don't trust the exit code:** confirm `30-people/` now
holds people files. If it's still empty, the sync didn't actually run (missing
`org-chart.json`, or the Windows `python3` Store stub) — say so
rather than reporting a synced org chart.

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
