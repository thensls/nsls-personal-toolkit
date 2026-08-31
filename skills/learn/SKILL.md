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
- `/learn oss [query]` → **Search OSS Catalog** (open-source building blocks for Society / Ignite Next)

> **Reserved word:** `oss` is the catalog-search command — never treat `/learn oss …` as a
> New Learning Goal for a topic literally named "oss".

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
- A wikilink to the resource file in `50-reference/` and a 1-sentence description

Present the draft learning path to the user: "Here's what I'd suggest. Want to reorder, add, or remove anything?"

After approval:

1. **Write resource files to `50-reference/`**: For each resource in the learning path, create a file at `$OBSIDIAN_VAULT_PATH/50-reference/[slug].md`:
   ```yaml
   ---
   type: resource
   format: article|video|course|book
   url: "https://..."
   source: "[Site/Author name]"
   date-clipped: YYYY-MM-DD
   topics: []
   learning-goal: "[[topic-slug]]"
   ---

   # [Resource Title]

   [1-sentence description from the learning path]
   ```
   If a topic in `60-nsls-knowledge/` matches (e.g., learning about "retention" and `60-nsls-knowledge/retention.md` exists), add it to the `topics:` list as `"[[retention]]"`.

2. **Update the topic dashboard**: Write the Learning Path (with wikilinks to `50-reference/` files) and Resources sections. The Resources section becomes a list of `[[50-reference/slug|Title]]` wikilinks.

This connects learning resources to the broader vault graph — resources link to knowledge topics, knowledge topics link to people and projects.

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
2. For each unprocessed item (`- [ ]`), first decide **reading vs. OSS project** (see
   "Classifying OSS projects" below):
   - **OSS project** → add a catalog entry to `40-learning/oss-catalog.md` (see "Filing to the
     OSS catalog"), then mark the inbox item `- [x] … ✅ filed YYYY-MM-DD → [[oss-catalog]]`.
     An OSS project can ALSO carry a topic tag (e.g. an agent framework is both catalog + #agentic-harnesses) — file it both places.
   - **Reading with a tag matching an active topic** → present summary, confirm tag, mark `- [x]`, add to that topic dashboard's Resources section.
   - **Reading, no tag** → summarize the link (title + first paragraph via WebFetch), suggest a topic tag or "untagged".
3. Present untagged items to the user: "These links don't match any active goals. Want to tag them, create a new goal, or skip?"
4. Write updates back to `_inbox.md`, any affected topic dashboards, and `oss-catalog.md`.

### Classifying OSS projects

Mark an item as an **OSS project** when it is (or showcases) a *specific* open-source software
project, library, framework, or tool — a GitHub repo link, or a social post (e.g. `x.com/tom_doerr`,
`threads.com/@githubprojects`) highlighting one named OSS project. A post that bundles several
projects becomes several catalog entries. Articles, news, videos, and opinion/leadership threads
are **readings**, not OSS projects — even when they mention a tool in passing.

### Filing to the OSS catalog

`40-learning/oss-catalog.md` is a flat, greppable catalog of open-source building blocks for
**Society / Ignite Next** (repo `ignite-next`) and other NSLS products. Append each project as
one `###` block under `## Projects` (newest first), following the schema documented at the top
of that file:

```
### <Project Name>
- **Repo:** <github url or source>
- **What it does:** <one line>
- **Lang / License:** <language> · <license>
- **Relevance:** <why it could matter for Society / Ignite Next>
- **Tags:** #tag #tag        (from the taxonomy in oss-catalog.md)
- **Status:** candidate
- **Source:** <original link> · captured YYYY-MM-DD
```

Before appending, **dedup**: grep the catalog for the repo URL or project name; if it already
exists, skip (or refine the existing block) rather than adding a duplicate. Enrich `Lang /
License` and `Repo` from GitHub when discoverable (`gh repo view <owner/repo> --json …`, or the
public API) but never block on it — leave a field blank rather than guess. When in doubt about
`Relevance`, write what product surface it could serve (learning, community, AI, auth,
onboarding, dev-tooling…) so search still finds it.

---

## Mode: Refresh Learning Path (`/learn scaffold [topic]`)

1. Read the topic dashboard for current level, target outcome, and completed items
2. Run WebSearch for updated/better resources
3. Check `_inbox.md` for newly tagged links
4. Rebuild the learning path, preserving completed items (`[x]`) and adjusting the remaining sequence
5. Present the updated path for approval
6. Write to the topic dashboard

---

## Mode: Search OSS Catalog (`/learn oss [query]`)

Searches `40-learning/oss-catalog.md` — the catalog of open-source building blocks for Society /
Ignite Next and other NSLS products. Used directly by the builder, and called by `/interrogate` during
new-product planning to surface relevant building blocks.

1. Read `$OBSIDIAN_VAULT_PATH/40-learning/oss-catalog.md`. If it doesn't exist, say so and
   suggest running `/learn inbox` to build it.
2. **No query** (`/learn oss`) → summarize the catalog: total projects, a breakdown by tag, and
   the most recent 5 additions. Suggest a query.
3. **With a query** → match each project block against the query across **name, what-it-does,
   relevance, and tags**. Treat the query loosely:
   - tag-style queries (`auth`, `gamification`, `agent`, `llm`) → match `Tags:` and text
   - capability queries (`"send push notifications"`, `"in-app chat"`) → semantic/keyword match against What it does + Relevance
   - Rank by closeness; prefer `Status: candidate|evaluating|adopted` over `rejected` (mention rejected only if directly on-point, with its rejection reason).
4. Present the top matches as a compact list:
   ```
   OSS candidates for "<query>" (N matches):
   1. <Name> — <what it does>. Relevance: <…>. [repo](<url>) · #tags · status:<status>
   2. …
   ```
   If zero matches, say so and offer to run a live web/GitHub search (WebSearch / `gh search repos`)
   and, with approval, file the best finds into the catalog.

---

## Link Ingestion (runs during /open-day, and the engine behind `/learn inbox`)

When called from `/open-day`, ingest new links based on the builder's configured `learning_capture_method` (from builder profile):

**If `slack`:** Use the Slack connector's `slack_read_channel` (resolve the live `mcp__<uuid>__` name from this session's tools — connector UUIDs are per-machine) to read the builder's self-DM channel (using `$SLACK_USER_ID`, passed as `channel_id`) for messages since the last ingestion. Extract URLs, **resolve shortlinks (below)**, fetch titles, classify, and append to `_inbox.md`. Skip automated reminder messages (e.g. anything containing "person-intelligence sweep" or an `:alarm_clock:` prefix).

**If other method or not configured:** Skip automatic ingestion. The builder adds links to `_inbox.md` manually or via `/learn inbox`. This is the default — automatic ingestion is opt-in.

### Resolving shortlinks (`share.google`, etc.)

Self-DM links are almost all `https://share.google/XXXX` redirect shortlinks. **Resolve
every shortlink to its real destination with `curl` first** — it's fast and reliable:

```bash
curl -sL -o /dev/null -w '%{url_effective}' --max-time 25 "https://share.google/XXXX"
```

Use the resolved URL everywhere downstream (dedup, fetch, the link written to `_inbox.md`).
**Playwright is a fallback, not the default** — only reach for the browser (Playwright MCP:
`browser_navigate` + `browser_snapshot`) when `curl` returns a Google interstitial instead of a
real destination, OR when the *destination itself* (x.com, threads.com, other JS-walled pages)
won't render for content extraction. If a destination stays blocked after one Playwright attempt,
record the title best-effort and append "(unresolved — fetch blocked)" to the summary; do not loop.

> A previous version of this flow opened every link in Playwright. That was slow and flaky —
> `curl` resolves `share.google` in one shot. Keep curl-first.

### Per-URL processing

For each ingested URL (after resolution):
- **Dedup** against `_inbox.md` and `oss-catalog.md` by resolved URL — skip if already present.
- Fetch the page title and first paragraph (WebFetch; Playwright fallback per above).
- Generate a 1-2 sentence factual summary.
- **Classify reading vs. OSS project** (see "Classifying OSS projects" under Process Inbox).
- Always append to `_inbox.md` in the format below (the inbox is the audit trail). Tag OSS
  projects `#oss-project` plus any matching topic; tag readings with the matched topic or `#untagged`:
  ```
  - [ ] [Page Title](resolved-URL) — YYYY-MM-DD, from: [source]
    > [1-2 sentence summary]
    > Tags: #oss-project #[topic]   (or #[matched-topic] / #untagged for readings)
  ```
- For OSS projects, also append a catalog block to `oss-catalog.md` (see "Filing to the OSS
  catalog") and mark the inbox line filed. When run non-interactively from `/open-day`, file
  clear OSS projects straight to the catalog; leave genuinely ambiguous items as `- [ ]` for the
  next `/learn inbox`.
- Report: "Ingested [N] new links. [M] readings matched topics, [K] untagged, [P] OSS projects → catalog."

---

## File Formats Reference

### `_inbox.md`

```markdown
# Learning Inbox

Unprocessed links scraped from Slack and other sources. Run `/learn inbox` to process.
```

### `oss-catalog.md`

Flat catalog of open-source building blocks for Society / Ignite Next. Self-documents its schema
and tag taxonomy in its header; `## Projects` holds one `###` block per project (newest first).
Searched via `/learn oss`, written by `/learn inbox` + `/open-day` ingestion, read by `/interrogate`.

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
