# Personal Learning System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `/learn` skill backed by an Obsidian knowledge graph that integrates into the open/close planning rhythm for intentional, scaffolded learning.

**Architecture:** New `/learn` skill (SKILL.md) in both `~/.claude/skills/` (Marcus-local) and `~/nsls-skills/nsls-personal-toolkit/skills/` (toolkit). Obsidian template files in `40-learning/`. Modifications to open-week, open-day, and toolkit CLAUDE.md. Phase 1 only — close-day/close-week/obsidian-setup changes are Phase 2.

**Tech Stack:** Claude Code skills (SKILL.md files), Obsidian markdown, Slack MCP for link scraping, WebSearch/WebFetch for research.

**Spec:** `docs/specs/2026-04-11-personal-learning-system-design.md`

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `~/.claude/skills/learn/SKILL.md` | Marcus-local learn skill |
| Create | `~/nsls-skills/nsls-personal-toolkit/skills/learn/SKILL.md` | Toolkit learn skill (generic) |
| Create | `[vault]/40-learning/_inbox.md` | Raw link capture template |
| Create | `[vault]/40-learning/_learning-goals.md` | Priority-ranked learning goals |
| Create | `[vault]/40-learning/_weekly-plan.md` | Weekly learning schedule |
| Modify | `~/.claude/skills/open-week/SKILL.md` | Add learning section to weekly planning |
| Modify | `~/nsls-skills/nsls-personal-toolkit/skills/open-week/SKILL.md` | Same, toolkit version |
| Modify | `~/.claude/skills/open-day/SKILL.md` | Add micro-learning + link ingestion |
| Modify | `~/nsls-skills/nsls-personal-toolkit/skills/open-day/SKILL.md` | Same, toolkit version |
| Modify | `~/nsls-skills/nsls-personal-toolkit/CLAUDE.md` | Add /learn to skills table |

`[vault]` = `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP`

---

### Task 1: Create the `/learn` Skill (Marcus-local)

**Files:**
- Create: `~/.claude/skills/learn/SKILL.md`

This is the core skill — the conversation flow, all subcommands, and the Obsidian read/write logic.

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p ~/.claude/skills/learn
```

- [ ] **Step 2: Write the SKILL.md**

Create `~/.claude/skills/learn/SKILL.md` with the full content below. This is the largest single file in the plan — it contains the conversation flow, all subcommands (`/learn`, `/learn [topic]`, `/learn inbox`, `/learn scaffold [topic]`), Obsidian file formats, and link ingestion logic.

```markdown
---
name: learn
description: >-
  Personal learning management — set learning goals, ingest links, build
  scaffolded learning paths, and track progress in Obsidian. Use when the user
  says "learn", "I want to learn about", "learning goals", "what should I
  learn", "process my links", "learning inbox", "scaffold", or references
  skill development and knowledge building. Also triggers on "/learn [topic]",
  "/learn inbox", "/learn scaffold [topic]".
---

# Learn

Personal learning management system backed by an Obsidian knowledge graph in `40-learning/`. Handles goal setting, resource ingestion, summarization, scaffolding, and progress tracking.

## Vault Path

`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP/40-learning/`

## Subcommands

Parse the user's input to determine which mode to run:

- `/learn` (no args) → **Status Check**
- `/learn [topic]` → **New Learning Goal** (if topic doesn't exist) or **Topic Review** (if it does)
- `/learn inbox` → **Process Inbox**
- `/learn scaffold [topic]` → **Refresh Learning Path**

---

## Mode: New Learning Goal (`/learn [topic]`)

When the topic doesn't already have a dashboard in `40-learning/`, run this guided conversation. Ask questions **one at a time**.

### Step 1: Topic Intake

"What specifically interests you about **[topic]**? For example:"
- Building something with it
- Evaluating it for a decision
- Understanding the landscape
- Going deeper on a specific aspect
- Something else

Wait for response. Capture as `interest_angle`.

### Step 2: Current Knowledge Assessment

Based on their interest angle, ask where they are now. This is a self-assessment conversation, not a quiz.

Examples:
- "Have you worked with anything related to [topic]? What felt unclear or limiting?"
- "On a scale from 'heard the term' to 'built production systems,' where would you place yourself?"
- "What's the most advanced thing you've done in this area?"

Wait for response. Capture as `current_level`.

### Step 3: Learning Outcome

"What do you want to be able to do after learning this?"
- a) Evaluate tools/approaches (make decisions)
- b) Build something specific (what?)
- c) Teach someone else on your team
- d) Understand the landscape for informed conversations
- e) Something else

Wait for response. Capture as `target_outcome`.

### Step 4: Time Horizon

"How much time do you want to invest?"
- a) 1-week sprint (~3-4 hours total)
- b) A month of gradual learning (~1.5h/week)
- c) Ongoing interest — feed me resources over time

Wait for response. Capture as `time_horizon`.

### Step 5: Create Topic Dashboard

Write `40-learning/[topic-slug].md`:

```
---
status: active
started: [today's date]
target-outcome: "[target_outcome from Step 3]"
current-level: "[current_level from Step 2]"
time-horizon: [time_horizon from Step 4]
next-session: [next Monday or next available day]
---

# [Topic Name]

## Where I Am
[Narrative summary from the conversation — 2-3 sentences capturing current_level and interest_angle]

## Learning Path
[To be filled by research step]

## Resources
[To be filled by research step]

## Concept Notes
[Empty — populated during deep dive sessions]

## Progress Log
- [today's date]: Goal set. Starting from [current_level]. Target: [target_outcome].
```

### Step 6: Update Learning Goals

Read `40-learning/_learning-goals.md`. Add the new topic to the **Active** section. Place it based on:
- Time horizon (sprints rank higher than ongoing)
- Relevance to current projects (check `20-projects/` for related work)
- Relevance to role (check `10-strategy/operating-memo.md` if it exists)

Present the updated priority list to the user for confirmation.

### Step 7: Research and Scaffold

Run in parallel:
1. **WebSearch** for top resources on [topic] at the user's current level. Search for: "[topic] tutorial beginner/intermediate/advanced" (matching current_level), "[topic] best resources 2025 2026", "[topic] guide for [target_outcome]".
2. **Check `_inbox.md`** for any existing links tagged with or related to this topic.

From the results, build a scaffolded **Learning Path** — a sequence of 4-8 items progressing from the user's current level toward their target outcome. Each item has:
- A checkbox `[ ]`
- A title in bold
- Estimated time in parentheses
- The resource link and a 1-sentence description

Present the draft learning path to the user: "Here's what I'd suggest. Want to reorder, add, or remove anything?"

After approval, write the Learning Path and Resources sections to the topic dashboard.

### Step 8: Confirm

"**[Topic]** is now active in your learning goals. Next session scheduled for [date]. `/open-week` will include it in your weekly plan, and `/open-day` will schedule 15-min micro-learning blocks from the path."

---

## Mode: Topic Review (`/learn [existing-topic]`)

When the topic already has a dashboard in `40-learning/`:

1. Read the topic dashboard
2. Show current progress: "You're X of Y items through the learning path. Last session: [date]. Next up: [item]."
3. Ask: "Want to continue with the next item, adjust the path, or mark this as complete/parked?"

If they want to continue → present the next learning path item with the resource link.
If they want to adjust → re-run the scaffold step.
If they want to complete/park → move it to the appropriate section in `_learning-goals.md`.

---

## Mode: Status Check (`/learn` no args)

1. Read `40-learning/_learning-goals.md`
2. Read each active topic dashboard for progress
3. Read `40-learning/_inbox.md` for unprocessed link count

Present:

```
## Learning Status

**Active Goals:**
1. [Topic] — [X/Y items done], next session [date]. Target: [outcome].
2. [Topic] — [X/Y items done], next session [date]. Target: [outcome].

**Inbox:** [N] unprocessed links

**Suggestion:** [Based on active goals and inbox, suggest what to do next — "Continue with [topic], you're 2 items from finishing" or "Process your inbox — 8 new links waiting"]
```

---

## Mode: Process Inbox (`/learn inbox`)

1. Read `40-learning/_inbox.md`
2. For each unprocessed item (`- [ ]`):
   - If it already has tags matching an active topic → present summary, confirm tag, mark as `- [x]`, add to topic dashboard's Resources section
   - If no tag → summarize the link (read title + first paragraph via WebFetch), suggest a topic tag or "untagged"
3. Present untagged items to the user: "These links don't match any active goals. Want to tag them, create a new goal, or skip?"
4. Write updates back to `_inbox.md` and any affected topic dashboards

---

## Mode: Refresh Learning Path (`/learn scaffold [topic]`)

1. Read the topic dashboard for current level, target outcome, and completed items
2. Run WebSearch for updated/better resources
3. Check `_inbox.md` for newly tagged links
4. Rebuild the learning path, preserving completed items and adjusting the remaining sequence
5. Present the updated path for approval
6. Write to the topic dashboard

---

## Link Ingestion (runs during /open-day)

When called from `/open-day`, scrape Marcus's Slack self-DMs for new links:

1. Use `mcp__plugin_slack_slack__slack_read_channel` to read Marcus's self-DM channel for messages from the last 24 hours
2. Extract any URLs from those messages
3. For each URL:
   - Fetch the page title and first paragraph via WebFetch
   - Generate a 1-2 sentence summary
   - Check if it matches any active learning goal topics (keyword match against topic names and tags)
   - Append to `_inbox.md` in the format:
     ```
     - [ ] [Page Title](URL) — YYYY-MM-DD, from: Slack self-DM
       > [1-2 sentence summary]
       > Tags: #[matched-topic] (or #untagged)
     ```
4. Report: "Ingested [N] new links from Slack. [M] matched active topics, [K] untagged."

If no new URLs found, skip silently.

---

## File Formats Reference

### `_inbox.md`

```markdown
# Learning Inbox

Unprocessed links scraped from Slack and other sources. Run `/learn inbox` to process.

```

### `_learning-goals.md`

```markdown
---
updated: [date]
---

# Learning Goals

## Active

## Completed

## Parked
```

### `_weekly-plan.md`

```markdown
---
week: [YYYY-WNN]
generated-by: open-week
---

# Learning Plan — Week of [date]

## Deep Dive (~1.5h)
- **Topic:** [topic]
- **Item:** [learning path item]
- **Scheduled:** [day, time]
- **Resources:** [links]

## Daily Micro-Learning (15 min/day)
| Day | Topic | Item | Resource |
|-----|-------|------|----------|
| Mon | [topic] | [item] | [link] |
| Tue | [topic] | [item] | [link] |
| Wed | [topic] | [item] | [link] |
| Thu | [topic] | [item] | [link] |
| Fri | [topic] | [item] | [link] |
```
```

- [ ] **Step 3: Verify the skill loads**

Open a new Claude Code session or check the skill list. `/learn` should appear with the description "Personal learning management — set learning goals, ingest links..."

- [ ] **Step 4: Commit**

This is a local-only skill (not in a git repo), so no git commit needed. Verify the directory exists:

```bash
ls -la ~/.claude/skills/learn/SKILL.md
```

---

### Task 2: Create Obsidian Template Files

**Files:**
- Create: `[vault]/40-learning/_inbox.md`
- Create: `[vault]/40-learning/_learning-goals.md`
- Create: `[vault]/40-learning/_weekly-plan.md`

These are the empty starter files that the `/learn` skill reads and writes.

- [ ] **Step 1: Create `_inbox.md`**

Write to `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP/40-learning/_inbox.md`:

```markdown
# Learning Inbox

Unprocessed links scraped from Slack and other sources. Run `/learn inbox` to process.
```

- [ ] **Step 2: Create `_learning-goals.md`**

Write to `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP/40-learning/_learning-goals.md`:

```markdown
---
updated: 2026-04-11
---

# Learning Goals

## Active

## Completed

## Parked
```

- [ ] **Step 3: Create `_weekly-plan.md`**

Write to `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP/40-learning/_weekly-plan.md`:

```markdown
---
week: 2026-W15
generated-by: open-week
---

# Learning Plan

*No learning plan generated yet. Run `/open-week` to create one, or use `/learn [topic]` to set a learning goal first.*
```

- [ ] **Step 4: Verify in Obsidian**

Check the files exist:

```bash
ls ~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/KP/40-learning/
```

Expected: `_inbox.md`, `_learning-goals.md`, `_weekly-plan.md`

---

### Task 3: Add Learning Section to `/open-week` (Marcus-local)

**Files:**
- Modify: `~/.claude/skills/open-week/SKILL.md`

Add a learning step to the weekly planning flow — between coaching insights and the week plan template.

- [ ] **Step 1: Read the current file to find insertion points**

Read `~/.claude/skills/open-week/SKILL.md` lines 195-235 to see the exact context around Step 2 (coaching insights) and Step 3 (draft week plan).

- [ ] **Step 2: Add learning data collection to Step 1**

Find the end of Step 1's data collection section (after the Asana and Calendar queries). Insert a new sub-step:

```markdown
**1e. Learning goals and progress**

Read from `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP/40-learning/`:
- `_learning-goals.md` — active learning goals and priorities
- Each active topic's dashboard (e.g., `agentic-harnesses.md`) — check `status`, `next-session`, and Learning Path completion (count `[x]` vs `[ ]` items)
- `_inbox.md` — count unprocessed links

Extract:
- Active goal count and names
- Per-goal progress (X of Y items complete)
- Days since last session per goal (from `next-session` or Progress Log)
- Unprocessed inbox link count
```

- [ ] **Step 3: Add learning pattern to coaching insights (Step 2)**

Find the "**Pattern detection:**" section. Add after the last pattern bullet:

```markdown
- **Learning stagnation:** If an active learning goal hasn't had progress in 3+ weeks, flag it: "[Topic] has been active for [N] weeks with no progress. Either schedule a deep dive this week, park it, or admit it's not a priority right now."
- **Learning time vs. filler:** If last week's close-week showed >5h of YouTube/news but <1h of structured learning, note: "Last week had [X]h of media consumption but only [Y]h of intentional learning. Consider converting one filler session into a 15-min micro-learning block."
```

- [ ] **Step 4: Add learning section to the week plan template (Step 3)**

Find the week plan template output section (after the Recommended Top 3 and rationale). Insert before the "Also Important" section:

```markdown
### Learning & Growth

**Active goals:** [list from _learning-goals.md]

**This week's focus:**
- **Deep dive:** [topic] — [learning path item], ~1.5h. Suggested: [day based on calendar gaps].
- **Daily micro-learning:** 15 min/day from [topic] learning path or inbox links.

**Ask Marcus:** "What do you want to learn more about this week? Confirm the above, add a new topic (I'll run `/learn`), or skip learning this week."

**Stale goals:** [any goals with no progress in 3+ weeks — suggest park or schedule]

**Inbox:** [N] unprocessed links. [If >10: "Your learning inbox is backing up. Run `/learn inbox` to process, or I'll triage during `/open-day`."]
```

- [ ] **Step 5: Add learning to the weekly note output**

Find where the weekly note is written to `02-weekly/YYYY-[W]WW.md`. In the week plan content that gets written, add after the Top 3 section:

```markdown
### Learning Plan
- **Deep dive:** [topic] — [item], [day], ~1.5h
- **Micro-learning:** 15 min/day — [topic] learning path
- **Goals:** [N] active, [N] inbox links pending
```

- [ ] **Step 6: Verify the edit**

Read the modified file and confirm the learning sections appear in the right places — after data collection, in coaching insights, in the week plan template, and in the weekly note output.

- [ ] **Step 7: Commit (N/A — local skill)**

Local skill, no git commit needed.

---

### Task 4: Add Learning Section to `/open-week` (Toolkit)

**Files:**
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/open-week/SKILL.md`

Apply the same changes as Task 3, but using generic language ("the builder" not "Marcus") and `$OBSIDIAN_VAULT_PATH` instead of the hardcoded vault path.

- [ ] **Step 1: Read the toolkit version**

Read `~/nsls-skills/nsls-personal-toolkit/skills/open-week/SKILL.md` around the same sections as Task 3 to find the corresponding insertion points. The line numbers may differ from the Marcus-local version.

- [ ] **Step 2: Apply the same 4 insertions as Task 3**

Use the same content blocks from Task 3, Steps 2-5, with these substitutions:
- Replace `Marcus` → `the builder`
- Replace the hardcoded vault path → `$OBSIDIAN_VAULT_PATH/40-learning/`
- Replace `"Ask Marcus:"` → `"Ask the builder:"`

- [ ] **Step 3: Verify the edit**

Read the modified file and confirm learning sections are in place.

- [ ] **Step 4: Stage for commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit && git add skills/open-week/SKILL.md
```

---

### Task 5: Add Micro-Learning + Link Ingestion to `/open-day` (Marcus-local)

**Files:**
- Modify: `~/.claude/skills/open-day/SKILL.md`

Add two things: (1) Slack self-DM scraping for links at the start of the day, (2) a 15-min micro-learning block in the calendar scheduling.

- [ ] **Step 1: Read the current file to find insertion points**

Read `~/.claude/skills/open-day/SKILL.md` around:
- The data collection steps (Step 1-3) — to add link scraping
- The Growth pillar section (~line 22) — to connect micro-learning
- The scheduling section (~line 202-215) — to add the Learn block
- The Growth block template (~line 276-280) — to add micro-learning variant

- [ ] **Step 2: Add link ingestion to data collection**

Find the data collection steps (Step 1 or Step 2). Add a new sub-step after the existing data collection:

```markdown
**[N]. Learning inbox ingestion**

Scrape Marcus's Slack self-DMs for URLs sent since the last scrape:

1. Use `mcp__plugin_slack_slack__slack_read_channel` to read Marcus's self-DM channel. Look for messages from the last 24 hours containing URLs.
2. For each URL found:
   - Fetch the page title via WebFetch (just the title and first paragraph, not the full page)
   - Generate a 1-2 sentence summary
   - Check if it matches any active learning goal topic (read `40-learning/_learning-goals.md` for active topic names)
   - Append to `40-learning/_inbox.md` in this format:
     ```
     - [ ] [Page Title](URL) — YYYY-MM-DD, from: Slack self-DM
       > [1-2 sentence summary]
       > Tags: #[matched-topic] or #untagged
     ```
3. If no new URLs found, skip silently.
4. If new links were ingested, mention in the morning summary: "Ingested [N] new links from Slack into your learning inbox."

Also read:
- `40-learning/_weekly-plan.md` — today's micro-learning assignment
- `40-learning/_inbox.md` — count of unprocessed links for active goals
```

- [ ] **Step 3: Expand the Growth pillar description**

Find the Growth pillar description (~line 22). Update it to be more specific:

Replace:
```
2. **Growth** — Coaching, learning, skill development. Reading, courses, exploring ideas.
```

With:
```
2. **Growth** — Intentional learning from `40-learning/` goals. Daily: 15-min micro-learning block (one article, one tutorial, one inbox link). Weekly: 1.5h deep dive scheduled by `/open-week`. Coaching and skill development also count.
```

- [ ] **Step 4: Add micro-learning to the scheduling rules**

Find the Growth scheduling rule (~line 212, "Growth gets a block if there's room"). Replace it with:

```markdown
**Micro-learning gets a 15-min block every day.** Read `40-learning/_weekly-plan.md` for today's assignment. If no weekly plan exists, pick the highest-priority unprocessed link from `_inbox.md` that matches an active goal. Schedule in a lower-energy slot (after lunch, late afternoon, between meetings). Use summary: "Learn: [topic] — [item title]". Color: Grape (3).

**Deep dive gets a longer block on the scheduled day.** If `_weekly-plan.md` shows a deep dive for today, schedule the full block (~1.5h). Use summary: "Deep Dive: [topic] — [item title]". Color: Grape (3).
```

- [ ] **Step 5: Verify the edit**

Read the modified sections and confirm: link ingestion is in data collection, Growth description is updated, micro-learning scheduling rule is in place.

- [ ] **Step 6: Commit (N/A — local skill)**

Local skill, no git commit needed.

---

### Task 6: Add Micro-Learning + Link Ingestion to `/open-day` (Toolkit)

**Files:**
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/open-day/SKILL.md`

Apply the same changes as Task 5, with generic language and configurable paths.

- [ ] **Step 1: Read the toolkit version**

Read the toolkit open-day SKILL.md to find the corresponding insertion points.

- [ ] **Step 2: Apply the same insertions as Task 5**

Same content blocks with these substitutions:
- Replace Marcus-specific Slack scraping with: "If `learning_capture_method` in builder profile is set to `slack`, scrape the builder's Slack self-DMs using their `$SLACK_USER_ID`. For other capture methods, skip automatic ingestion — the builder adds links to `_inbox.md` manually or via `/learn inbox`."
- Replace hardcoded vault path → `$OBSIDIAN_VAULT_PATH/40-learning/`
- Replace `Marcus` → `the builder`

- [ ] **Step 3: Verify and stage**

```bash
cd ~/nsls-skills/nsls-personal-toolkit && git add skills/open-day/SKILL.md
```

---

### Task 7: Create `/learn` Skill (Toolkit Version)

**Files:**
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/learn/SKILL.md`

The toolkit version of the `/learn` skill. Same structure as Task 1, but with generic language and configurable paths.

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p ~/nsls-skills/nsls-personal-toolkit/skills/learn
```

- [ ] **Step 2: Write the SKILL.md**

Copy the content from Task 1's SKILL.md with these substitutions throughout:
- Replace `Marcus` → `the builder`
- Replace the hardcoded vault path `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP/40-learning/` → `$OBSIDIAN_VAULT_PATH/40-learning/`
- Replace the Marcus-specific Slack scraping section with:

```markdown
## Link Ingestion (runs during /open-day)

When called from `/open-day`, ingest new links based on the builder's configured `learning_capture_method` (from builder profile):

**If `slack`:** Use `mcp__plugin_slack_slack__slack_read_channel` to read the builder's self-DM channel (using `$SLACK_USER_ID`) for messages from the last 24 hours. Extract URLs, fetch titles via WebFetch, and append to `_inbox.md`.

**If other method or not configured:** Skip automatic ingestion. The builder adds links to `_inbox.md` manually or via `/learn inbox`. This is the default — automatic ingestion is opt-in.
```

- [ ] **Step 3: Stage for commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit && git add skills/learn/SKILL.md
```

---

### Task 8: Update Toolkit CLAUDE.md

**Files:**
- Modify: `~/nsls-skills/nsls-personal-toolkit/CLAUDE.md`

Add `/learn` to the skills table.

- [ ] **Step 1: Read the current skills table**

Read `~/nsls-skills/nsls-personal-toolkit/CLAUDE.md` lines 15-25 to see the skills table.

- [ ] **Step 2: Add `/learn` to the table**

Insert after the `/open-day` row (or in alphabetical position among the skills):

```markdown
| `/learn` | Learning goals, resource ingestion, scaffolded learning paths, progress tracking |
```

- [ ] **Step 3: Stage for commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit && git add CLAUDE.md
```

---

### Task 9: Commit and Push Toolkit Changes

**Files:**
- All staged files from Tasks 4, 6, 7, 8

- [ ] **Step 1: Review staged changes**

```bash
cd ~/nsls-skills/nsls-personal-toolkit && git status && git diff --staged --stat
```

Expected: 4 files changed — `skills/learn/SKILL.md` (new), `skills/open-week/SKILL.md` (modified), `skills/open-day/SKILL.md` (modified), `CLAUDE.md` (modified).

- [ ] **Step 2: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit && git commit -m "feat: add /learn skill — personal learning management system

New skill for intentional learning backed by Obsidian knowledge graph.
Integrates into /open-week (deep dive scheduling) and /open-day
(15-min micro-learning + link ingestion from Slack).

Phase 1 MVP — close-day/close-week integration is Phase 2.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 3: Push**

```bash
cd ~/nsls-skills/nsls-personal-toolkit && git push
```

---

### Task 10: Smoke Test — Run `/learn` on a Real Topic

**Files:**
- Read/write: `40-learning/` files

This is the functional test — run the skill and verify it works end-to-end.

- [ ] **Step 1: Run `/learn agentic harnesses`**

In a new Claude Code session (or this one), run `/learn agentic harnesses`. Walk through the conversation flow:
1. Confirm it asks about interest angle
2. Confirm it asks about current knowledge
3. Confirm it asks about learning outcome
4. Confirm it asks about time horizon
5. Confirm it creates the topic dashboard in `40-learning/agentic-harnesses.md`
6. Confirm it updates `_learning-goals.md`
7. Confirm it runs web research and presents a scaffolded learning path
8. Confirm the learning path looks reasonable and can be edited

- [ ] **Step 2: Verify the Obsidian files**

```bash
cat ~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/KP/40-learning/agentic-harnesses.md
cat ~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/KP/40-learning/_learning-goals.md
```

Confirm: topic dashboard has frontmatter, Where I Am section, Learning Path with items, Resources section. Learning goals has the new topic in Active.

- [ ] **Step 3: Run `/learn` (no args)**

Verify it shows the status: active goals, inbox count, suggestion for what to do next.

- [ ] **Step 4: Run `/learn inbox`**

Verify it reads `_inbox.md` and either reports "no unprocessed links" or processes any that exist.
