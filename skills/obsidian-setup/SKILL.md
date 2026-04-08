---
name: obsidian-setup
description: >-
  Set up a new Obsidian knowledge base matching the NSLS builder pattern. This
  skill should be used when the user says "set up Obsidian", "create a vault",
  "obsidian setup", "start my knowledge base", "I want to use Obsidian", or
  mentions wanting a project tracking system like the original builder's. Walks through
  vault creation, folder structure, templates, plugins, and configuration.
---

# Obsidian Setup

Set up a new Obsidian vault for an NSLS builder with project tracking, daily notes, people notes, and dataview queries. Claude automates everything it can via the filesystem, then provides a short manual checklist for steps that require the Obsidian app.

## Prerequisites

Obsidian must be installed first. If not installed:

> Download Obsidian (free) from https://obsidian.md and install it. Then come back here.

## Step 0: Builder Onboarding Interview

Before creating anything, ask these questions **one at a time** to understand the builder's role and configure the skills that depend on this vault (close-day, open-day, plan-week, log). The answers drive what gets generated in daily notes, what time categories are tracked, and what sections appear in templates.

**Question 1: Role and level**

> What's your role at NSLS? (This determines your daily note structure and time tracking categories)
>
> a) **Executive / SLT** — You manage multiple departments, set strategy, attend board meetings. Your time is split across many domains (product, marketing, people, finance, etc.).
> b) **Department lead** — You own one department or function. Most of your time is in your domain with some cross-functional work.
> c) **Manager** — You manage a team within a department. Focus is on your team's output plus 1:1s and coordination.
> d) **Individual contributor** — You do the work directly. Focus is on your craft with some meetings and collaboration.
> e) **Other** — Tell me about your role.

**Question 2: Departments you touch**

> Which departments/functions do you regularly work in? (Pick all that apply — this sets up your time tracking categories)
>
> - Product / Engineering
> - Marketing / Growth
> - Sales / Partnerships
> - People / HR
> - Finance / Operations
> - CS / Member Success
> - Executive / Strategy
> - Other: ___

**Question 3: Time tracking goals**

> What do you want to learn from tracking your time? (Pick the closest)
>
> a) **Doing vs. Orchestrating** — Am I spending too much time doing things myself vs. delegating and directing? (Best for executives/managers)
> b) **Deep work vs. Meetings** — Am I getting enough focus time vs. being stuck in meetings? (Best for ICs and managers)
> c) **Department balance** — Am I spreading my attention correctly across my responsibilities? (Best for department leads)
> d) **All of the above** — Show me everything.

**Question 4: Tools and data sources**

> Which of these do you use? (This determines what close-day pulls from)
>
> - [ ] Familiar (screen capture) — for automatic time tracking
> - [ ] Fathom or Granola — for meeting summaries
> - [ ] Slack — for communication tracking
> - [ ] Gmail / Google Workspace — for email and calendar
> - [ ] Asana — for task management
> - [ ] Claude Code — for coding/building work

**Question 5: Work schedule**

> What's your typical work schedule?
>
> a) Weekdays only (Mon–Fri)
> b) Weekdays plus some weekends
> c) 7 days a week
> d) Non-standard (tell me)

After collecting answers, generate the **builder profile** (see Step 1a) and confirm it with the builder before proceeding.

## Step 1: Create the Vault

Ask the builder:
1. **Where should the vault live?** Recommend `~/Obsidian/KP/` for local, or iCloud for cross-device sync:
   - Local: `~/Obsidian/[initials]/`
   - iCloud: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/[initials]/`
2. **What are your initials?** (Used as the vault folder name)

Create the vault directory:
```bash
mkdir -p $OBSIDIAN_VAULT_PATH
```

## Step 1a: Generate Builder Profile

Based on the onboarding answers, create `$OBSIDIAN_VAULT_PATH/50-reference/builder-profile.md`. This file is the single source of truth that close-day, open-day, and plan-week read to customize their output.

```markdown
---
type: builder-profile
name: [Builder's name]
role: [executive | department-lead | manager | ic]
departments:
  - [department1]
  - [department2]
time_tracking_mode: [doing-vs-orchestrating | deep-vs-meetings | department-balance | all]
work_schedule: [weekdays | weekdays-plus-weekends | daily | custom]
data_sources:
  familiar: [true | false]
  fathom: [true | false]
  slack: [true | false]
  gmail: [true | false]
  asana: [true | false]
  claude_code: [true | false]
time_categories:
  # These are the work categories for time allocation tracking.
  # Each category has a name, description, and mapping rules.
  # close-day uses these to categorize Familiar captures into work types.
  - name: [Category name]
    description: [What this category covers]
    apps: [list of app names that map here]
    slack_channels: [list of channel name patterns]
    chrome_patterns: [list of window title patterns]
    meeting_keywords: [list of Fathom title keywords]
---

# Builder Profile — [Name]

Role: [role description]
Departments: [list]
Time tracking: [mode description]
Schedule: [schedule]

## Time Category Definitions

[Human-readable description of each category and what maps to it]
```

**Preset time categories by role:**

### Executive / SLT preset
Best for: people who touch every department and need to see where their attention goes.

| Category | Description | Default app mappings |
|---|---|---|
| **Coding / Building** | Hands-on creation — writing code, building automations, configuring tools | Warp, Claude (desktop), VS Code, GitHub, Railway |
| **Management / People** | 1:1s, coaching, people decisions, Slack DMs with reports, HR | Slack DMs, Gmail (people-related), Messages, 1:1 meetings |
| **Product Management** | Product strategy, specs, design review, roadmap | Figma, Airtable, product Slack channels, product meetings |
| **Marketing / Sales** | Growth, campaigns, partnerships, recruiting | Marketing Slack channels, recruiting tools, sales meetings |
| **Admin / Ops** | Calendar, task management, finance, internal tools | Obsidian, Asana, Calendar, NetSuite, Ramp, Calendly |
| **Learning / Research** | YouTube, reading, documentation, industry research | YouTube, news sites, Reddit, documentation |

Summary line: "Doing vs. Orchestrating: X% building, X% managing/meeting, X% admin/research"

### Department Lead preset
Best for: people who own one function with some cross-functional work.

| Category | Description |
|---|---|
| **My Department** | Primary function work (configured to their specific department) |
| **Cross-functional** | Work in other departments, coordination |
| **Management / People** | 1:1s, team coaching, hiring |
| **Meetings** | Meetings not categorized by department |
| **Admin / Ops** | Calendar, tasks, internal tools |
| **Learning / Research** | Reading, courses, exploration |

Summary line: "Department focus: X% [dept], X% cross-functional, X% management"

### Manager preset
Best for: people managing a team within one department.

| Category | Description |
|---|---|
| **Hands-on work** | Doing the work yourself — coding, writing, designing |
| **Team management** | 1:1s, coaching, reviewing, Slack with reports |
| **Meetings** | Group meetings, standups, cross-team syncs |
| **Planning / Coordination** | Roadmap, task management, prioritization |
| **Admin** | Calendar, email triage, operational overhead |
| **Learning** | Reading, courses, skill development |

Summary line: "Doing vs. Managing: X% hands-on, X% team management, X% meetings/admin"

### IC preset
Best for: individual contributors focused on one craft.

| Category | Description |
|---|---|
| **Deep work** | Core craft — coding, writing, designing, analyzing |
| **Collaboration** | Pair programming, reviews, Slack discussions about work |
| **Meetings** | Standups, syncs, 1:1 with manager |
| **Communication** | Email, Slack non-work, status updates |
| **Admin** | Calendar, time tracking, process overhead |
| **Learning** | Reading, courses, experimentation |

Summary line: "Deep work ratio: X% focused, X% collaboration, X% meetings/admin"

**Custom overrides:** After generating the profile from a preset, ask the builder:

> Here's your time tracking setup based on the [preset] template. Want to:
> - Rename any categories?
> - Add or remove a category?
> - Change what tools map where?
>
> You can always edit `50-reference/builder-profile.md` later to adjust.

## Step 1b: Connect Data Sources

Based on the data sources the builder selected in Step 0, walk through connecting each one. **Only show steps for sources they said they use.** Skip the rest.

**Familiar (screen capture)**

> 1. Download Familiar from https://familiar.app
> 2. Grant screen recording permission when prompted
> 3. Verify it's capturing: check that `~/familiar/stills-markdown/` has session folders appearing
> 4. The close-day skill reads from this directory automatically — no API key needed

**Fathom (meeting summaries)**

> 1. Go to https://fathom.video/settings/api (or your Fathom dashboard > Settings > API)
> 2. Generate an API key
> 3. Add it to your shell profile (`~/.zshrc` or `~/.bashrc`):
>    ```bash
>    export FATHOM_API_KEY="your-key-here"
>    ```
> 4. Reload your shell: `source ~/.zshrc`
> 5. Test: `curl -s -H "X-Api-Key: $FATHOM_API_KEY" "https://api.fathom.ai/external/v1/meetings?created_after=$(date +%Y-%m-%d)T00:00:00Z" | head -c 200`
>    — you should see JSON with your recent meetings

**Granola (alternative to Fathom)**

> Granola stores meeting notes locally. If you use Granola instead of Fathom, the close-day skill will need to be configured to read from Granola's export format instead of the Fathom API. Open a GitHub issue — this is a customization we can add.

**Slack**

> Slack access is provided through Claude Code's Slack MCP integration. Verify it's connected:
> 1. In Claude Code, try: `slack_search_users(query="your name")`
> 2. If it works, you're connected. If not, you may need to authorize the Slack MCP server in Claude Code settings.

**Gmail / Google Calendar**

> Gmail and Calendar access is provided through Claude Code's Google MCP integrations. Verify:
> 1. Try: `gcal_list_events(timeMin="today", timeMax="today")` — should show today's meetings
> 2. Try: `gmail_search_messages(q="from:me", maxResults=1)` — should show your last sent email
> 3. If either fails, authorize the Google Calendar / Gmail MCP servers in Claude Code settings.

**Asana**

> Asana access is provided through Claude Code's Asana MCP integration. Verify:
> 1. Try: `asana_list_workspaces()` — should show your workspace
> 2. Note your **workspace GID** and **user GID** — you'll need these for the skills. Find your user GID: `asana_get_me()`
> 3. If not connected, authorize the Asana MCP server in Claude Code settings.

**Claude Code**

> Claude Code session tracking is automatic — the close-day skill reads from `~/.claude/projects/` to detect what was built in other sessions. No setup needed.

**After connecting all sources**, run a quick smoke test:

> Let me verify all your data sources are working. I'll pull a small sample from each one...

Run each connected source's test command. Report which ones are working and which need troubleshooting. **Do not proceed to vault creation until at least the core sources (Calendar, Asana) are verified.**

## Step 2: Create Folder Structure

```bash
mkdir -p $OBSIDIAN_VAULT_PATH/{_templates,00-inbox,00-inbox/attachments,01-daily,02-weekly,03-journal,10-slt,20-projects,30-people,40-learning,50-reference}
```

### What each folder is for:

| Folder | Purpose |
|--------|---------|
| `_templates` | Templater templates — daily notes, project homes, person notes |
| `00-inbox` | Default location for new notes. Triage later. |
| `01-daily` | Daily notes (auto-created by Calendar plugin) |
| `02-weekly` | Weekly review notes |
| `03-journal` | Personal journal entries (optional, can be encrypted) |
| `10-slt` | SLT meeting notes (skip if not SLT-adjacent) |
| `20-projects` | One subfolder per project with a home note and sessions folder |
| `30-people` | One note per person — relationship context, 1:1 notes |
| `40-learning` | Notes from reading, courses, ideas |
| `50-reference` | Stable reference material — schemas, docs, policies |

## Step 3: Create Templates

Create these 5 template files in `$OBSIDIAN_VAULT_PATH/_templates/`. Read `references/templates/` for the full content of each template.

| Template | Purpose |
|----------|---------|
| `daily-note.md` | Morning check-in, active projects dataview, work log, end-of-day dump. **Customize based on role** — SLT sections (Friday topic request, Monday prep, Tuesday meeting) only appear if `role: executive` in builder profile. For ICs, replace the "AI Suggested Top 3" with a simpler "Tomorrow's focus" section. |
| `weekly-review.md` | Portfolio review, projects touched/not touched, next week priorities |
| `project-home.md` | YAML frontmatter (status, priority, collaborators), current state, decisions, open questions |
| `person.md` | Role, org, shared projects dataview, 1:1 notes, background |
| `journal-entry.md` | Freeform reflection — what happened, how you feel, what you're carrying |

## Step 4: Configure Obsidian Settings

Create `$OBSIDIAN_VAULT_PATH/.obsidian/app.json`:
```json
{
  "newFileLocation": "folder",
  "newFileFolderPath": "00-inbox",
  "attachmentFolderPath": "00-inbox/attachments",
  "useMarkdownLinks": true,
  "showLineNumber": false,
  "spellcheck": false,
  "strictLineBreaks": false,
  "alwaysUpdateLinks": true
}
```

This sets:
- New notes go to the inbox by default
- Attachments go to `00-inbox/attachments`
- Use `[[wikilinks]]` style (Obsidian's strength)

## Step 5: Configure Plugin List

Create `$OBSIDIAN_VAULT_PATH/.obsidian/community-plugins.json`:
```json
[
  "templater-obsidian",
  "calendar",
  "dataview",
  "table-editor-obsidian",
  "obsidian-kanban",
  "omnisearch",
  "smart-connections",
  "obsidian-tasks-plugin"
]
```

## Step 6: Configure Templater

Create `$OBSIDIAN_VAULT_PATH/.obsidian/plugins/templater-obsidian/` directory and `data.json`:
```json
{
  "command_timeout": 5,
  "templates_folder": "",
  "templates_pairs": [["", ""]],
  "trigger_on_file_creation": true,
  "auto_jump_to_cursor": false,
  "enable_system_commands": false,
  "shell_path": "",
  "user_scripts_folder": "",
  "enable_folder_templates": true,
  "folder_templates": [
    {
      "folder": "01-daily",
      "template": "_templates/daily-note.md"
    }
  ],
  "syntax_highlighting": true,
  "syntax_highlighting_mobile": false,
  "enabled_templates_hotkeys": [["", ""]],
  "startup_templates": [""]
}
```

This auto-applies the daily note template when a note is created in `01-daily/`.

## Step 7: Manual Steps Checklist

After creating all files, present this checklist to the builder:

> I've set up your vault structure, templates, and configuration files. Now open Obsidian and do these steps:
>
> 1. **Open the vault** — Launch Obsidian > "Open folder as vault" > select `$OBSIDIAN_VAULT_PATH`
> 2. **Enable community plugins** — Settings (gear icon) > Community Plugins > Turn on community plugins > click "Turn on"
> 3. **Install plugins** — Settings > Community Plugins > Browse. Install these 8 plugins:
>    - **Templater** — template engine with date/logic support
>    - **Calendar** — calendar sidebar, click a date to create daily notes
>    - **Dataview** — query your notes like a database (powers the project dashboards)
>    - **Table Editor** — edit markdown tables visually
>    - **Kanban** — drag-and-drop kanban boards from markdown
>    - **Omnisearch** — fast full-text search across your vault
>    - **Smart Connections** — AI-powered related notes (needs API key)
>    - **Tasks** — checkbox task tracking with due dates and queries
> 4. **Enable each plugin** — After installing, go back to Community Plugins and toggle each one on
> 5. **Restart Obsidian** — Close and reopen to pick up the Templater config
> 6. **Test** — Click today's date in the Calendar sidebar. It should create a daily note in `01-daily/` with the template applied.
>
> **Optional:**
> - Smart Connections needs an API key (OpenAI or Anthropic) — set it in Settings > Smart Connections if you want AI-related notes
> - Meld Encrypt — install if you want to encrypt sensitive journal entries

## Step 8: Create First Project

After the builder confirms the manual steps are done, offer to create their first project:

> Want to create your first project? Tell me:
> - What's the project name?
> - One sentence — what is it?
> - Who else is involved?

Then create:
- `$OBSIDIAN_VAULT_PATH/20-projects/[slug]/[slug].md` using the project-home template
- `$OBSIDIAN_VAULT_PATH/20-projects/[slug]/sessions/` directory

## Customization Notes

Tell the builder:

> This is a starting point, not a prescription. Common customizations:
> - **Don't need SLT folders?** Delete `10-slt/` and remove the SLT-specific sections from the daily note template.
> - **Don't do weekly reviews?** Delete `02-weekly/` and the weekly-review template.
> - **Want different daily note sections?** Edit `_templates/daily-note.md` to match your workflow.
> - **Prefer a different folder structure?** Rename or reorganize. The templates use relative paths that adapt.
> - **Don't want journaling?** Delete `03-journal/` and the journal-entry template.
> - **Change time categories?** Edit `50-reference/builder-profile.md` — update the `time_categories` list to add, remove, or rename categories, and adjust the `apps`, `slack_channels`, `chrome_patterns`, and `meeting_keywords` mappings. close-day reads this file every time it runs.

The only thing that matters is that `20-projects/` follows the convention (one subfolder per project with a home note) so the `log` and `close-day` skills can find your projects.

## How Builder Profile Connects to Other Skills

The builder profile at `50-reference/builder-profile.md` is read by:

| Skill | What it reads | How it uses it |
|---|---|---|
| **close-day** | `time_categories`, `time_tracking_mode`, `data_sources` | Determines work category breakdown, summary line format, and which data sources to pull |
| **open-day** | `time_tracking_mode`, `work_schedule` | Adjusts morning planning prompts (e.g., "Doing vs. Orchestrating" goal for the day) |
| **plan-week** | `role`, `departments`, `time_tracking_mode` | Frames weekly priorities through the right lens (executive portfolio vs. IC sprint plan) |
| **log** | `time_categories` | Tags session logs with the matching work category |

If the builder changes roles or responsibilities, they update the profile once and all skills adapt.
