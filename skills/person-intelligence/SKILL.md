---
name: person-intelligence
description: >-
  Build or update a person profile, run a biweekly relationship health check,
  manage coaching goals, or prep for a meeting with someone.
  Trigger: "person intel", "synthesize [name]", "build profile for [name]",
  "update [name]'s profile", "who is [name]", "person intelligence",
  "people profile", "refresh profiles", "relationship check", "health check",
  "biweekly check", "relationship health", "prep for [name]",
  "meeting prep [name]", "coaching goals"
---

# Person Intelligence

Synthesizes rich person profiles into Obsidian (`30-people/[Name].md`) by pulling data from every available source: Fathom 1:1 transcripts, Airtable SLT meeting intelligence, Airtable People Ops, existing Obsidian notes, and conversation context.

Read `OBSIDIAN_VAULT_PATH` from `~/.claude/local-plugins/nsls-personal-toolkit/.env`.

Scripts live at: `~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/`

## Quick Start

"Synthesize Gary Tuerack" or "person intel on Adam Stone" -- the pipeline runs automatically.

## Pipeline

### Step 1: Identify the person

Ask for or confirm: full name, known email(s). Check the Known People Registry below for shortcuts.

### Step 2: Discover available data

Run these in parallel where possible. Each outputs JSON to stdout, status to stderr.

**Fathom 1:1s** (if email known):
```bash
python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/fetch_fathom_1on1s.py \
  --email {email} --list
```

**Airtable SLT** (if SLT member -- Gary, Adam, Ashleigh, Michael, Anish, Kevin):
```bash
python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/fetch_airtable_slt.py "{name}" > /tmp/person-intel-slt.json
```

**Airtable People Ops** (if NSLS employee):
```bash
python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/fetch_airtable_people_ops.py "{name}" > /tmp/person-intel-people-ops.json
```

**Signal — Quick Notes** (only when `SIGNAL_INGEST=1` AND the person is a **direct report**):

Phase 1 is MCP-in-session — *you* (the orchestrator) call the `signal_*` MCP tools, bundle
their raw JSON, and pipe it to `fetch_signal.py`, which caches the raw (cache-only, never the
vault) and emits the normalized, sensitivity-pre-screened signal:

```bash
# 1. Call MCP tools for the slug (exec/manager scope): signal_person, signal_person_history,
#    signal_person_goals. Assemble: {"slug":"...","person":<>,"history":<>,"goals":<>}
echo "$RAW_BUNDLE" | python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/fetch_signal.py \
  --slug {kebab-name} --weeks 12 > /tmp/person-intel-signal.json
# List direct-report slugs in scope:
python3.12 .../scripts/fetch_signal.py --list-reports
```

Then include the normalized output as the `signal` field in the synthesize payload (Step 5).
**Scope: direct reports only.** **Raw Quick Notes never enter the vault** — `fetch_signal.py`
drops HR/health/comp items mechanically, and `synthesize_profile.py` applies the KB
sensitive-content rubric to what remains. Signal-derived coaching evidence surfaces as
`<!-- DIGEST -->` comments for biweekly approval, never written into Coaching Goals directly.

**Existing Obsidian profiles** (vault at `$OBSIDIAN_VAULT_PATH`):
- `30-people/{Name}.md` (display name with spaces)
- `10-slt/members/{slug}.md` (lowercase hyphenated, e.g., `gary-tuerack.md`)
- `20-projects/board-intelligence/members/{Name}.md` (display name with spaces)

### Step 3: Fetch and summarize meetings

**If no email provided or Fathom returns 0 matches, skip this step.** The synthesizer works with Airtable data alone.

Fetch transcripts and summarize each:
```bash
python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/fetch_fathom_1on1s.py \
  --email {email} --fetch-all > /tmp/person-intel-meetings.jsonl

# Summarize each meeting (one Claude API call per meeting)
while IFS= read -r line; do
  echo "$line" | python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/summarize_meeting.py
done < /tmp/person-intel-meetings.jsonl > /tmp/person-intel-summaries.jsonl
```

**For weekly updates:** Add `--after {last-synthesized date}` to only fetch new meetings.

**Performance:** First runs with 20+ meetings take 20+ API calls. This is expected. Subsequent weekly runs are fast (1-3 new meetings).

### Step 4: Infer project connections

Assemble goals, actions, and topics from all sources into a JSON object and pipe to the inference engine:
```bash
python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/infer_projects.py < /tmp/person-intel-data.json
```

Input format: `{"goals": [...], "actions": [...], "topics": [...], "person_name": "..."}`
- Goals: from Airtable L1/L2/LOP goals
- Actions: from Airtable Meeting Actions
- Topics: from meeting summaries "Topics Discussed" sections

### Step 5: Synthesize profile

Assemble ALL collected data into a single JSON payload and synthesize:
```bash
python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/synthesize_profile.py < /tmp/person-intel-combined.json > /tmp/person-intel-profile.md
```

Input format:
```json
{
  "person_name": "...",
  "meeting_summaries": [...],
  "airtable_slt": {...},
  "airtable_people_ops": {...},
  "existing_profile": "...",
  "existing_board_profile": "...",
  "existing_slt_profile": "...",
  "projects": {...}
}
```

All fields except `person_name` are nullable -- the synthesizer handles any combination.

### Step 6: Write to Obsidian

Write the synthesized profile to `$OBSIDIAN_VAULT_PATH/30-people/{Name}.md`.

If the person is an SLT member, also update `$OBSIDIAN_VAULT_PATH/10-slt/members/{slug}.md` with coaching feedback patterns (speaking %, contribution quality trends, start/stop recommendations over time).

If the person is a board member, do NOT overwrite `$OBSIDIAN_VAULT_PATH/20-projects/board-intelligence/members/{Name}.md` -- that has hand-curated board context. The `30-people/` profile links to it instead.

### Step 7: Surface project suggestions

If `infer_projects.py` returned "suggested" projects (1-2 matches, below the 3-match confirmation threshold), present them:

"I found possible project connections for {name}:
- **{project}**: mentioned {N} times ({evidence}). Add to profile?"

If confirmed, add to the profile AND update the project's `collaborators:` frontmatter.

### Step 8: Update project collaborators

For confirmed projects, update `$OBSIDIAN_VAULT_PATH/20-projects/{project}/{project}.md` frontmatter:
```yaml
collaborators: ["[[Gary Tuerack]]", "[[Cory Capoccia]]"]
```

This enables Obsidian dataview queries in `30-people/` hub files.

## Scheduling

The biweekly sweep is designed to run automatically every other Sunday at 7:00 AM ET — before the `/open-week` routine, so the team-pulse digest is ready to inform weekly planning.

Register the schedule once per user via the `/schedule` skill:

```
/schedule create "Person-intelligence biweekly sweep" \
  --cron "0 7 * * 0/2" \
  --command "/person-intelligence biweekly sweep"
```

That cron pattern means "minute 0, hour 7, every other Sunday (day-of-week 0, step 2)". Adjust to your timezone via the dashboard if needed.

**To pause** (e.g., vacation): `/schedule pause "Person-intelligence biweekly sweep"`
**To resume**: `/schedule resume "Person-intelligence biweekly sweep"`
**To run manually any time**: `/person-intelligence biweekly sweep` (no schedule needed)

If a scheduled run fails, `/open-day` will surface an alert the next morning (from the `last-sweep-status.json` cache). You can re-run manually from there.

## Mode: Biweekly Sweep

The biweekly sweep is the recurring cadence that keeps every tracked relationship fresh. Two scripts compose the pipeline:

### Step 1: build the manifest

```bash
OPERATING_USER_EMAIL=you@nsls.org \
OBSIDIAN_VAULT_PATH=/path/to/vault \
python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/biweekly_sweep.py
```

Outputs a manifest at `~/.cache/person-intelligence/biweekly-sweep-YYYY-MM-DD.manifest.json` listing each tracked relationship, last-synthesized date, count of new Fathom meetings since that date, and which ingest sources are available. The Claude orchestrator session reads this manifest and runs per-person synthesis as needed.

**Signal ingest in the sweep:** when `SIGNAL_INGEST=1`, each direct-report relationship carries `signal_ingest_planned: true` + a `signal_slug`. For those, the orchestrator runs `fetch_signal.py --fetch --slug <signal_slug> --weeks 12` (token-direct — no MCP needed, so the headless cron sweep works) and includes the normalized result as the `signal` field in the synthesize payload. Raw Quick Notes stay cache-only; only the distilled `## Signal Read` reaches the profile.

Re-running on the same day is idempotent (`--resume` reads the existing manifest).

### Step 2: generate the team-pulse digest

After per-person synthesis, run:

```bash
ANTHROPIC_API_KEY=... \
OBSIDIAN_VAULT_PATH=/path/to/vault \
python3.12 ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/generate_team_pulse.py
```

Writes `30-people/_pulse/YYYY-MM-DD-team-pulse.md` — one digest per cycle with cross-relational patterns:

- **Cadence Integrity** — who's stale, who's current
- **Drift / Thrive / Attention** — health-score trends across the team
- **Manager Mode Review** — time-allocation skew, attention prompts
- **Proposed Coaching Updates** — per-person suggestions to accept/edit/reject

Empty sections are omitted. Use `--dry-run` to preview the prompt before the API call.

### Observability

`~/.cache/person-intelligence/last-sweep-status.json` records the most recent sweep's exit code, error (if any), and relationships processed. `/open-day` reads this and surfaces a one-line alert if the last sweep failed or hasn't run in 18+ days.

## Keeping Obsidian frontmatter in sync with the org chart

The Rippling → Airtable → GitHub pipeline keeps `org-chart.json` fresh (hourly cron). To flow those updates into the Obsidian people vault without touching curated content, run:

```bash
OBSIDIAN_VAULT_PATH=/path/to/vault python3.12 \
  ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/sync_obsidian_frontmatter.py --dry-run
```

The sync controls exactly **5 frontmatter fields**: `email`, `slack`, `department`, `title`, `manager`. Every other field — `tags`, `role` (your curated description), `health*`, `last-synthesized`, `sources`, `meetings_attended` — is left untouched. Body content is byte-preserved (tests assert this). Always run `--dry-run` first to inspect proposed changes.

Match strategy: by frontmatter `email` first, then by exact filename `{Name}.md`. Employees with no matching file are reported but skipped — create the stub manually if you want them tracked.

## Ingest Sources

The skill pulls signal from four sources. Full scoping and privacy posture in
[`references/ingest-scoping.md`](references/ingest-scoping.md).

| Source | What gets pulled | Auth |
|---|---|---|
| **Fathom** | 1:1 transcripts since the profile's `last-synthesized` date | `FATHOM_API_KEY` env var |
| **Slack** | DMs + shared-thread messages from the last 14 days | User-authorized MCP (`/connect slack`) |
| **Gmail** | Threads where both parties are direct participants, last 14 days | User-authorized MCP (`/connect gmail`) |
| **Signal** | Quick Notes wins/friction/sentiment/goal-health (**direct reports only**, `SIGNAL_INGEST=1`). Raw narration cached-only; distilled into `## Signal Read`. | `signal_*` MCP (Phase 1) |

Three filters apply before content reaches the synthesizer:
1. **Third-party name stripping** — names other than you and the target person become role descriptors
2. **`INGEST_EXCLUDE_THREADS` patterns** — subject/channel keywords skip the ingest entirely (defaults cover legal, payroll, HR)
3. **Low-signal filter** — drops messages under 20 chars, pure emoji, routine logistics

If a source's MCP isn't connected, the skill skips that source silently and notes it in the synthesis input (`sources_unavailable: ["slack"]`). To disable a source even when connected, set `SKIP_SLACK_INGEST=1` or `SKIP_GMAIL_INGEST=1` in your `.env`.

## Identifying who to track

The biweekly sweep composes its relationship set from three sources via [`scripts/list_relationships.py`](scripts/list_relationships.py):

1. **Direct reports** — looked up from the `manages` array in the builder toolkit's `org-chart.json` (no Airtable key required)
2. **Management peers** — people who share your manager, included only when `INCLUDE_MANAGEMENT_PEERS=1`
3. **Key relationships** — newline- or comma-separated names in `KEY_RELATIONSHIPS` env var (contractors, board members, family, externals)

Identity comes from `OPERATING_USER_EMAIL` (or `BUILDER_EMAIL` as fallback). The user's record in `org-chart.json` provides the `manages` list and manager reference.

Run manually with:
```bash
OPERATING_USER_EMAIL=you@nsls.org python3.12 \
  ~/.claude/local-plugins/nsls-personal-toolkit/skills/person-intelligence/scripts/list_relationships.py
```

## Relationship Health Check

Trigger: "relationship check", "health check", "biweekly check"

### Scale (4 states, calibrated toward green)

| Score | Symbol | Label | Meaning |
|-------|--------|-------|---------|
| 1 | 🔴 | Needs Attention | Something's actively wrong |
| 2 | 🟡 | Watch | Drifting, needs course correction |
| 3 | 🟢 | Good | Healthy, productive, steady state (this is normal) |
| 4 | 💚 | Great | Peak collaboration, high trust, energizing |

### Six Dimensions

1. **Alignment** — Are we pulling in the same direction strategically?
2. **Trust** — Do I trust their judgment? Do they trust mine?
3. **Collaboration** — When we work together, is it productive or draining?
4. **Tension** — Is there unresolved friction? (4=none, 3=negligible, 2=some, 1=significant)
5. **Engagement** — Are they invested and showing up, or checked out?
6. **Influence Balance** — Am I leading this relationship or being led?

Rollup = average of 6 dimensions, mapped to emoji: ≥3.5 = 💚, ≥2.5 = 🟢, ≥1.5 = 🟡, <1.5 = 🔴

### How the Check Works

0. **Refresh org chart data first.** Before reading people files, sync any org chart updates into the vault so new hires, role changes, and management reshuffles are reflected in the files you're about to review. Run:
```bash
OBSIDIAN_VAULT_PATH="$OBSIDIAN_VAULT_PATH" python3.12 \
  ~/.claude/local-plugins/nsls-builder-toolkit/_shared/scripts/sync_org_context.py \
  --update-vault
```
If the builder toolkit isn't installed or `org-chart.json` doesn't exist, skip silently — it's a nice-to-have, not a blocker for the health check.

1. Read all `$OBSIDIAN_VAULT_PATH/30-people/*.md` files that have `health:` in frontmatter. **Skip files with `status: departed`** — their history is closed, no new assessments. Departed profiles use `health-departed` tag (dark gray on graph) instead of `health-attention` to avoid visual noise.
2. Present current state:

```
📊 Relationship Health — March 22, 2026

  💚 Gary Tuerack     (3.5) — last: Mar 22
  🟢 Cory Capoccia    (3.2) — last: Mar 22
  🟢 Adam Stone       (3.0) — last: Mar 22

Any changes? ("all good" to carry forward, or name who shifted)
```

3. If "all good" → carry forward all scores with today's date, no journal entry needed
4. If changes named → update those dimensions, recalculate rollup, ask to journal the thinking
5. Write updates:
   - Frontmatter: `health`, `health_score`, `health_last_assessed`, and update the `health-*` tag
   - H1: update emoji prefix (`# 💚 Name` / `# 🟢 Name` / `# 🟡 Name` / `# 🔴 Name`)
   - Append row to the health table
   - Append dated journal entry below the table

6. **Growth Reflection** (after relationship review):

After the relationship scores, prompt with 5 growth questions from Jack's framework:

```
🌱 Growth Check — March 22, 2026

1. Operating system — Did I zoom out this period, or was I in the wash?
2. Hard conversations — Did I have one? Did I avoid one?
3. Hero moments — Did I catch myself doing someone else's job?
4. Presence — How present was I? In meetings, at home?
5. Body — Exercise, sleep, energy?
```

Journal the reflection. Write it to `$OBSIDIAN_VAULT_PATH/20-projects/leadership-growth/leadership-growth.md`
under a new `### YYYY-MM-DD` entry in a `## Growth Journal` section.

Also check the most recent Jack Cohen session summary for any open commitments
and surface them: "Jack's last session (date): you committed to X. How did that go?"

### Journal Entry Format

Below the health table, reverse-chron journal entries. Free-form writing — this is where
you think through *why* the score is what it is. No length limit. The table is the dashboard,
the journal is the memory.

```markdown
### YYYY-MM-DD — 💚 Great

[Free-form thinking about this relationship right now.
Multiple paragraphs fine. This is private intelligence.]
```

### Obsidian Rendering

- **H1 emoji** shows current state when opening the file or in search
- **Graph coloring** via `health-great`, `health-good`, `health-watch`, `health-attention` tags
- **Health table** with emoji cells is a visual heatmap — scan patterns across time
- **Journal entries** below the table for context and reasoning

### CSS Snippet for Graph Coloring

Install at `$OBSIDIAN_VAULT_PATH/.obsidian/snippets/relationship-health.css`:

```css
/* Relationship health graph coloring */
.graph-view.color-fill-tag[data-tag="health-great"] .graph-view-node {
  fill: #22c55e !important;
}
.graph-view.color-fill-tag[data-tag="health-good"] .graph-view-node {
  fill: #86efac !important;
}
.graph-view.color-fill-tag[data-tag="health-watch"] .graph-view-node {
  fill: #facc15 !important;
}
.graph-view.color-fill-tag[data-tag="health-attention"] .graph-view-node {
  fill: #ef4444 !important;
}
```

## Weekly Automation

This skill supports incremental updates:
1. Only fetch Fathom meetings after the `last-synthesized` date from existing profile frontmatter
2. Re-pull Airtable data (goals/actions change frequently)
3. Merge new data with existing profile content
4. Surface new project suggestions if topics have shifted

## Personal Details

### Automatic extraction (from Fathom transcripts)

The meeting summarizer (`summarize_meeting.py`) extracts personal facts mentioned in small talk — kids, hobbies, vacations, life events. These come back as a `personal_facts` array in the summary output.

During profile synthesis (Step 5), deduplicate and merge personal facts into a `## Personal` section in the profile:

```markdown
## Personal

- **Family**: Three kids (ages ~8, 11, 14). Wife Sarah teaches high school math.
- **Interests**: Trail running, woodworking, Denver Nuggets
- **Life events**: Moving to new house (Feb 2026). Daughter started middle school.
- **Last updated**: YYYY-MM-DD
```

### Prompted during health checks

After scoring and coaching goal review, check each person's `## Personal` section:
- **Missing or empty**: "I don't have any personal details for [name] yet — family, hobbies, anything worth remembering?"
- **Stale (60+ days since `Last updated`)**: "[Name]'s personal section was last updated [date]. Anything new?"
- **Fresh and populated**: Skip — no prompt needed.

Kevin types what he knows. "Skip" moves on. Never pressure.

### Privacy rules

- Only include facts explicitly stated in transcripts or provided by Kevin — never inferences
- Sensitive facts (health issues, family conflict, financial) get flagged for Kevin's approval before writing
- The personal section is private intelligence — never shared with the person profiled

## Coaching Goals

### Profile format

Add a `## Coaching Goals` section to scored profiles, after `## How to Work With` and before `## Relationship Health`:

```markdown
## Coaching Goals

### Active: [Goal title]
status: active | created: YYYY-MM-DD | dimension: [health dimension]

**Why**: [1-2 sentences — what the data shows and why this matters]

**Actions**:
- [ ] [Concrete, observable action Kevin can take]
- [ ] [Another action]
- [ ] [Another action]

**Evidence**:
- YYYY-MM-DD: [Specific observation from transcript or meeting]
- YYYY-MM-DD: [Another observation]

### Completed: [Goal title]
status: completed | created: YYYY-MM-DD | completed: YYYY-MM-DD | dimension: [dimension]
**Outcome**: [One sentence — what changed]
```

### Goal generation rules

- Max 2 active goals per person (one professional, one personal/relational)
- Goals are about what **Kevin** does differently — not what the other person should do
- Each goal ties to a specific health dimension (lowest-scoring gets priority)
- Actions must be concrete and observable — things you'd notice in a meeting or Slack message
- Goals are **proposed by AI, approved by Kevin**. Never auto-written to the profile.

### Goal generation pipeline

**Inputs:**
1. The person's profile — patterns, evolution arc, working style, what they care about
2. Kevin's patterns — from Jack's coaching framework (`20-projects/leadership-growth/`), coaching patterns memory ("IC work is my unregulated excitement," hero tendencies)
3. Health scores — which dimensions are lowest?
4. Recent Fathom transcripts — what's actually happening in meetings?

**When goals are generated:**
- During the biweekly health check (after scoring), the AI:
  1. Checks active goals for new evidence from recent Fathom transcripts
  2. Appends evidence lines if found
  3. Proposes goal updates if evidence suggests progress or the goal needs evolving
  4. Proposes new goals if a dimension dropped or a new pattern emerged
- Kevin approves, edits, or rejects each proposal before anything is written

**Presentation format:**

```
🎯 Coaching Goal Updates:
  Lauren — "Support authority growth": 2 new evidence items from Apr retros.
    She opened both meetings and set agendas without prompting.
    → Recommend: upgrade action #1 to "ask her to present sprint status to SLT directly"

  Gary — No active goal. Propose: "Build shared decision framework"
    targeting alignment (🟢 3). Based on pattern: Gary routes ideas
    through Kevin that should go directly to SLT members.

  Accept all / Edit / Skip?
```

## Meeting Prep

Trigger: "prep for [name]", "meeting prep [name]", "prep for my meeting with [name]"

Pull everything into a quick brief:

```
📋 Meeting Prep: [Name]

Role: [role] | Health: [emoji] [score] | Last check: [date]

🎯 Active goal: [goal title] ([dimension] [emoji] [score])
   Actions: [action summary]
   Recent evidence: [latest evidence line]

👤 Personal: [key personal details]

📊 Recent pattern: [behavioral observation from recent transcripts]

💡 For this meeting: [contextual suggestion based on meeting type — if sprint,
   suggest something sprint-specific; if 1:1, suggest a question to ask]
```

**How to generate the contextual suggestion:**
- Read today's calendar to identify the meeting type (sprint, 1:1, product sync, etc.)
- Cross-reference the active coaching goal with the meeting type
- Produce one specific, actionable suggestion for this particular meeting

If no coaching goal exists for this person, skip the 🎯 section and focus on personal details and recent patterns.

## Known People Registry

| Name | Emails | Sources |
|------|--------|---------|
| Gary Tuerack | (check Fathom cache) | Fathom, SLT Airtable, People Ops, Board KB |
| Cory Capoccia | ccapoccia@nsls.org, cory.capoccia@gmail.com, cory@capocciaoffice.com | Fathom, Board KB |
| Adam Stone | (check Airtable) | SLT Airtable, People Ops |
| Ashleigh Smith | (check Airtable) | SLT Airtable, People Ops |
| Michael O'Brien | (check Airtable) | SLT Airtable, People Ops |
| Anish Patel | (check Airtable) | SLT Airtable, People Ops, Board KB |
| Lauren Prentiss | lprentiss@nsls.org | Obsidian daily/weekly notes, cross-profile refs (contractor — not in People Ops) |

Update this table as you profile new people.

## Script Reference

| Script | Input | Output | Requires |
|--------|-------|--------|----------|
| `fetch_fathom_1on1s.py` | `--email`, `--list`/`--fetch-all`/`--date` | JSON lines to stdout | FATHOM_API_KEY |
| `summarize_meeting.py` | JSON on stdin (transcript, title, date, person_name) | JSON line to stdout | ANTHROPIC_API_KEY |
| `fetch_airtable_slt.py` | person name as arg | JSON to stdout | AIRTABLE_API_KEY |
| `fetch_airtable_people_ops.py` | person name as arg | JSON to stdout | AIRTABLE_API_KEY |
| `infer_projects.py` | JSON on stdin (goals, actions, topics) | JSON to stdout | None |
| `synthesize_profile.py` | JSON on stdin (all data combined) | Markdown to stdout | ANTHROPIC_API_KEY |
