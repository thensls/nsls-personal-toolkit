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

`$OBSIDIAN_VAULT_PATH/40-learning/`

## Subcommands

Parse the user's input to determine which mode to run:

- `/learn` (no args) → **Status Check**
- `/learn [topic]` → **New Learning Goal** (if topic doesn't exist in `40-learning/`) or **Topic Review** (if it does)
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

Write `$OBSIDIAN_VAULT_PATH/40-learning/[topic-slug].md` (use kebab-case for the filename):

```markdown
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

Read `$OBSIDIAN_VAULT_PATH/40-learning/_learning-goals.md`. Add the new topic to the **Active** section. Place it based on:
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
If they want to adjust → re-run the scaffold step (Step 7 from New Learning Goal).
If they want to complete/park → move it to the appropriate section in `_learning-goals.md`, update topic dashboard status.

---

## Mode: Status Check (`/learn` no args)

1. Read `$OBSIDIAN_VAULT_PATH/40-learning/_learning-goals.md`
2. Read each active topic dashboard for progress
3. Read `$OBSIDIAN_VAULT_PATH/40-learning/_inbox.md` for unprocessed link count

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

1. Read `$OBSIDIAN_VAULT_PATH/40-learning/_inbox.md`
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
4. Rebuild the learning path, preserving completed items (`[x]`) and adjusting the remaining sequence
5. Present the updated path for approval
6. Write to the topic dashboard

---

## Link Ingestion (runs during /open-day)

When called from `/open-day`, ingest new links based on the builder's configured `learning_capture_method` (from builder profile):

**If `slack`:** Use `mcp__plugin_slack_slack__slack_read_channel` to read the builder's self-DM channel (using `$SLACK_USER_ID`) for messages from the last 24 hours. Extract URLs, fetch titles via WebFetch, and append to `_inbox.md`.

**If other method or not configured:** Skip automatic ingestion. The builder adds links to `_inbox.md` manually or via `/learn inbox`. This is the default — automatic ingestion is opt-in.

For each ingested URL:
- Fetch the page title and first paragraph via WebFetch
- Generate a 1-2 sentence summary
- Check if it matches any active learning goal topics (keyword match against topic names and tags in `_learning-goals.md`)
- Append to `_inbox.md` in the format:
  ```
  - [ ] [Page Title](URL) — YYYY-MM-DD, from: [source]
    > [1-2 sentence summary]
    > Tags: #[matched-topic] (or #untagged)
  ```
- Report: "Ingested [N] new links. [M] matched active topics, [K] untagged."

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
