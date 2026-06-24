# NSLS Knowledge Base Harvest — Design Spec

**Date:** 2026-05-29
**Status:** Approved, ready for implementation plan
**Author:** Kevin Prentiss (brainstormed with Claude)
**Target repos:**
- `~/nsls-skills/nsls-personal-toolkit` (new `harvest-meeting` skill, modified `close-week` skill)
- `~/.claude/skills/close-day/SKILL.md` (local fork — add Step 4c, port from plugin)
- `github.com/thensls/nsls-knowledge` (KB repo — no schema changes, only content writes)

---

## Problem

The NSLS Knowledge Base (`thensls/nsls-knowledge`) was seeded on 2026-05-19 with 60+ topic files derived from 7,800+ SLT meeting topic mentions. Since seed: **zero content commits**. Every recent commit is an hourly `rippling-sync` org-chart refresh.

Consequence: meeting decisions and project definitions from the last 10 days (including a 2026-05-26 SLT meeting Kevin described as "especially useful") sit only in Fathom transcripts and the SLT Meeting Intelligence Airtable. The employee-facing KB is a frozen snapshot, not a living map.

## Prior Work (discovered 2026-05-29 mid-implementation)

The initial framing of this spec said "the wiring was never built." That was wrong. **A `Step 4c: Knowledge Graph Insight Proposals` lived inside `close-day` SKILL.md from 2026-05-12 (commit `5ee6b94`) through 2026-05-25 (commit `9c8daf7`).** It was accidentally removed in commit `6a1dd15` on 2026-05-28 — the "Apple Health 1f-bis + Personal Goals" commit — without the removal being called out in the commit message.

The prior Step 4c is preserved at `docs/specs/2026-05-29-prior-step-4c-from-9c8daf7.md` (extracted from the last commit where it existed). Its core flow:

1. Match topics in 60-nsls-knowledge against today's meetings
2. Filter for insights against "would a new NSLS employee want to know this?" bar
3. Apply the sensitive-content rubric as a HARD STOP
4. Surface up to 3 candidates as prose proposals
5. Append approved candidates to Key Decisions / Current State
6. Heartbeat unconditionally (per Kevin's heartbeat memory)

Why this spec is still the right direction (v2, not redundant): the prior Step 4c had no `project_definition` / `state_change` kinds, no topic-mapping for NEW topics, no dedup against existing entries, no SLT allowlist for the other 6 SLT members, no auto-commit/push, no week-audit pipeline, and used a one-at-a-time prose UX rather than a numbered bulk-approve list. The new design carries the prior's rubric work forward and adds the missing dimensions.

Implications for implementation:
- The accidental removal in `6a1dd15` is left alone; the new design ships in a standalone `/harvest-meeting` skill rather than re-inlined into close-day, so there's nothing to restore in the close-day inline-Step-4c form.
- The new `Step 4c` in close-day (Task 13 of the plan) is a thin caller that invokes `/harvest-meeting`. Functionally replaces the prior inline Step 4c.
- The KB's `CLAUDE.md` sensitive-content rubric (which was hoisted out of the prior Step 4c on 2026-05-19) remains the source of truth. The new pipeline reads it at runtime.

### What was lost

The `Task 1` subagent (now reverted) reported overwriting pre-existing uncommitted local content in `skills/harvest-meeting/`. That content was never tracked in git and is irrecoverable from the repo. It may exist in Time Machine; pursuit deferred to Kevin's discretion. If recovered later and found to materially differ from this spec, treat it as a design input and revise.

## Goal

Build the missing harvest pipeline so that:
- Decisions, project definitions, and state changes from SLT members' meetings flow into the KB topic files daily.
- A weekly audit catches what daily harvest missed and reconciles resolved Open Questions into Key Decisions.
- The employee-facing rubric (no profit numbers, no named personnel decisions, no individual comp, etc.) is non-negotiably enforced before any KB commit.
- All 7 SLT members are KB writers from day-1, not just Kevin.

## Non-goals (explicit)

- This pipeline does NOT touch `## Insight Reflection` in daily notes — that's a separate self-insight track.
- This pipeline does NOT replace or modify the SLT Meeting Actions flow (Step 1h) in close-day. That's an Airtable system, not the KB.
- This pipeline does NOT generate insights — it harvests existing ones from Fathom-recorded conversations.
- This pipeline does NOT serve non-SLT users for write paths. Audit reports are visible to all; writes are SLT-gated.

---

## Decisions (from brainstorming)

| # | Decision | Locked in |
|---|---|---|
| D1 | Daily writes (Step 4c) + weekly audit (Step 2b). Step 2b promotes resolved Open Questions to Key Decisions and flags stale topics. | Section 2 |
| D2 | Source = ALL Kevin's (and any SLT member's) Fathom-recorded meetings, not just Tuesday SLT meetings. | Section 2 |
| D3 | Filter = candidates must be **Decisions**, **Project definitions**, or **State changes**. Excludes context, status updates, opinions, plans-in-discussion. | Section 2 |
| D4 | Routing = pass rubric → propose KB edit; fail rubric → drop (no separate destination). Personal reflection is a different pipeline. | Section 2 |
| D5 | Approval UX = numbered list of candidates, user replies `all` / `drop N,M` / `edit N: <text>` / `cancel`. | Section 2 |
| D6 | Commit mode = direct push to `main` (SLT are admins; per-edit approval is the review gate). | Section 2 |
| D7 | Architecture = standalone `/harvest-meeting` skill in the personal-toolkit plugin; both Step 4c and Step 2b are thin callers. | Section 2 |
| D8 | Writer model = all 7 SLT members are writers from v1. Hardcoded `kb_authors.txt`. | Section 2 |
| D9 | Step 2b lives in upstream plugin `close-week` (not a local fork). | Section 2 |

### KB_AUTHORS (v1, hardcoded)

```
kprentiss@nsls.org    (Kevin Prentiss)
mobrien@nsls.org      (Michael O'Brien)
gtuerack@nsls.org     (Gary Tuerack)
astone@nsls.org       (Adam Stone)
hdarnell@nsls.org     (Heather Darnell)   # email needs adding to Airtable Members
asmith@nsls.org       (Ashleigh Smith)
cbyers@nsls.org       (Chelsea Byers)
```

---

## Architecture

### File layout

```
PLUGIN: ~/nsls-skills/nsls-personal-toolkit/skills/
├── harvest-meeting/                          # NEW skill
│   ├── SKILL.md                              # core pipeline (modes: --date, --fathom-url, --week-audit)
│   ├── kb_authors.txt                        # 7 SLT emails, v1 hardcode
│   └── references/
│       ├── candidate-extraction.md           # prompt + examples for D/PD/SC extraction
│       └── topic-mapping.md                  # how to map candidates → topic files
├── close-day/SKILL.md                        # MODIFY: add Step 4c (thin invocation)
└── close-week/SKILL.md                       # MODIFY: add Step 2b (thin invocation)

LOCAL FORK: ~/.claude/skills/close-day/SKILL.md  # MODIFY: port Step 4c from plugin

KB REPO: github.com/thensls/nsls-knowledge
  Local clones at $OBSIDIAN_VAULT_PATH/60-nsls-knowledge/ on each SLT member's machine.
  Write flow: edit local → git commit → git push origin main → other SLT pulls on next session.
```

### Invocation contract

| Caller | Command | Behavior |
|---|---|---|
| `close-day` Step 4c | `/harvest-meeting --date YYYY-MM-DD` | SLT-gated. Pulls Fathom meetings for the date, runs harvest pipeline, presents approval list, commits + pushes. |
| `close-week` Step 2b | `/harvest-meeting --week-audit --week YYYY-Www` | Audit-always (all users). SLT users additionally get promote/stale-flag write actions. |
| Manual ad-hoc | `/harvest-meeting --fathom-url <url>` | SLT-gated. Single-meeting harvest for one-off important meetings outside daily ritual. |

---

## Core pipeline (harvest mode)

For modes `--date` and `--fathom-url`. Steps 1, 6, 7 are deterministic (Python + git); steps 2–5 are LLM judgment.

```
[1] LOAD CONTEXT (Python)
    ├─ Fathom meeting(s): title, attendees, summary, transcript, share_url, timestamps
    ├─ KB topic index: _index.md + frontmatter from every *.md in 60-nsls-knowledge/
    │   → builds {topic-slug: {title, parent, related, current_state, key_decisions[], open_questions[]}}
    ├─ KB CLAUDE.md sensitive-content rubric (parsed: never-write categories + reshape rules)
    └─ Current user's email (from `git config user.email`); gate against kb_authors.txt

[2] EXTRACT CANDIDATES (LLM, per meeting)
    Prompt: "Find moments that are DECISIONS, PROJECT DEFINITIONS, or STATE CHANGES.
            DO NOT extract candidates that obviously fall in these never-write categories:
            [paste rubric never-write list].
            Return JSON: [{kind, text, fathom_timestamp_sec, speaker, confidence}]"
    Notes:
      - Rubric pre-filter at extraction time avoids spending tokens on candidates that will
        definitely fail step 5 anyway.
      - Confidence is the model's self-rating; surfaced to user in approval step.

[3] MAP TO TOPICS (LLM, per candidate)
    Prompt: "Given this candidate + KB topic index, which topic file(s) does it belong on?
            Return: {primary_topic, secondary_topics[], section, confidence}
            section ∈ {current_state, key_decisions, open_questions}
            If no good fit, return: {primary_topic: NEW, suggested_slug: <slug>, suggested_parent: <slug>}"
    Notes:
      - LOW confidence (< 0.7) → mark for human disambiguation in approval step
      - NEW topic proposals are batched and shown distinctly in approval ("🆕 NEW")

[4] DEDUP (LLM, per candidate + target topic)
    Prompt: "Is this candidate already covered in the topic's existing Key Decisions /
            Current State? If yes, is this a REFINEMENT (update existing entry) or
            DUPLICATE (drop)?"
    Notes:
      - Refinements present in approval as "REPLACE old: ... → new: ..." diffs
      - Duplicates silently dropped (with one-line summary in heartbeat)

[5] RUBRIC GATE (LLM, per surviving candidate)
    Prompt: "Apply the full sensitive-content rubric to this candidate:
            [paste CLAUDE.md rubric in full — never-write categories AND reshape rules].
            Return: PASS | RESHAPE_TO: <new_text> | DROP_UNSAFE: <reason>"
    Notes:
      - RESHAPE candidates show original-vs-reshaped in approval; user can override inline
      - DROP_UNSAFE candidates are summarized at end of approval list with reasons
        ("⚠ 3 candidates dropped by rubric: 2 individual comp, 1 named personnel decision")

[6] PRESENT NUMBERED LIST (interactive)
    Format:
    
      Harvest candidates from 2026-05-26 meetings (2 meetings, 5 candidates after rubric):
      
      [1] b2b-conversion.md → Key Decisions
          + 2026-05-26: Pausing B2B campaign through July ([▶](fathom://...?ts=1834))
      
      [2] signal.md → Current State (REPLACE)
          - "3 tiers: green/yellow/red"
          + "4 tiers: green/yellow/orange/red"
      
      [3] chapter-health.md → Open Questions
          + How do we measure tier-4 chapters?
      
      [4] 🆕 NEW: ai-personalization-rollout.md (parent: ai-personalization)
          + Project definition: rollout owned by Adam, Q3 2026 scope
      
      [5] compensation-incentives.md → Key Decisions (RESHAPED)
          original: "We increased SARs grants by $X for senior engineers"
          reshaped: "SARs grant tiers were adjusted for senior engineers in May 2026"
      
      ⚠ 3 candidates dropped by rubric:
        - "Q1 EBITDA was $X" (profit number)
        - "Decided to let go of <name>" (named personnel decision)
        - "<vendor> outage exposed our dependency on them" (vendor named in security gap)
      
      Approve? all / drop 1,3 / edit 2: <text> / cancel
      > _

[7] APPLY + COMMIT (Python + git)
    ├─ Pull KB local clone: `git -C $KB_DIR pull --ff-only`
    ├─ For each approved candidate:
    │   ├─ Edit topic file (precise insert/replace by line)
    │   ├─ Update frontmatter `last-updated: YYYY-MM-DD`
    │   └─ If NEW topic: create file with scaffold (type, parent, status: stub)
    ├─ `git -C $KB_DIR add <files>`
    ├─ `git -C $KB_DIR commit -m "harvest: YYYY-MM-DD <meeting-titles> (N edits)"`
    └─ `git -C $KB_DIR push origin main`
    
    Push retry: if push fails (someone else pushed first):
      ├─ `git pull --rebase`
      ├─ If clean rebase → retry push
      └─ If rebase conflict → abort, surface conflict, leave changes uncommitted
```

## Audit pipeline (week-audit mode)

```
[1] LOAD CONTEXT
    ├─ git log --since=<week_start> --until=<week_end> in KB local clone
    │   → list of harvest commits, files touched, meeting titles from commit messages
    ├─ All topic files: frontmatter (last-updated) + body (Open Questions list)
    └─ Fathom meetings in the week (cross-ref against commit list to find unharvested)

[2] AUDIT REPORT (always displayed, all users)
    Format:
    
      Week 2026-W22 KB audit:
      
      Activity:
        - 4 harvest commits, 11 edits across 7 topic files
        - 12 SLT-recorded meetings; 11 harvested (1 unharvested — see below)
      
      Unharvested meetings:
        - 2026-05-28 "Gary 1:1": no harvest commits reference this meeting
      
      Stale topics (last-updated > 60 days):
        - employers.md (last touched 2026-03-15)
        - parents.md (last touched 2026-03-15)
        - non-gpa-students.md (last touched 2026-03-15)
      
      Open Questions older than 30 days (resolution candidates):
        - chapter-health.md: "How do we measure tier-4 chapters?" (opened 2026-04-22)
        - b2b-conversion.md: "Should we re-enter Texas market?" (opened 2026-04-15)

[3] PROMOTION OFFERS (SLT only)
    For each old Open Question, ask Claude:
    "Was this question answered by any of this week's harvest commits, or by any meeting
     in this week's Fathom log? If yes, propose: remove from Open Questions, add to
     Key Decisions with the resolution date and Fathom link."
    
    Present as numbered list (same UX as harvest mode):
    
      Promotion candidates:
      [1] chapter-health.md — Open Question resolved
          - Remove from Open Questions: "How do we measure tier-4 chapters?"
          + Add to Key Decisions: "2026-05-26: Tier-4 measured by chapter activity score
            < 30 over rolling 90d window ([▶](fathom...))"
      
      Approve? all / drop 1 / edit 1: <text> / cancel

[4] STALE FLAGS (SLT only)
    For topics with last-updated > 60 days:
    Per-topic prompt: "Mark `status: stale` in frontmatter? Or is this topic just not
    active and that's fine (leave alone)?"
    Approved → frontmatter edit + commit.

[5] AUDIT-ONLY for non-SLT users
    Heartbeat: "Step 2b: audit-only (you're not in KB_AUTHORS). To propose changes,
    edit a topic file and open a PR against thensls/nsls-knowledge."
```

---

## Caller integration

### close-day Step 4c (plugin + local-fork port)

**Placement:** After Step 1c (Fathom pull) and `## Insight Reflection`, before final write-back steps. Ordering rationale: self-insight may surface a strategic moment worth harvesting; Step 4c's commits appear in the daily note's `## Knowledge Base` section.

```
Step 4c. NSLS Knowledge Base harvest (SLT only)

Heartbeat check sequence:
  1. user_email = git config user.email
  2. If user_email NOT in kb_authors.txt → heartbeat "skipped: not SLT", exit step
  3. meetings = fathom_meetings(date=$TODAY, owner=user_email)
  4. If meetings == 0 → heartbeat "no meetings today, nothing to harvest", exit step
  5. Heartbeat "harvesting {N} meeting(s)..."
  6. Invoke /harvest-meeting --date $TODAY
     (User gets numbered-list approval interaction)
  7. After commit: heartbeat "committed N edits to 60-nsls-knowledge ({sha})"
  8. Write `## Knowledge Base` section to today's daily note with commit link
```

### close-week Step 2b (plugin only, no local fork)

**Placement:** After Step 2a (week synthesis), before Step 2c (Quick Notes formatting).

```
Step 2b. NSLS Knowledge Base week audit

Always runs:
  1. Heartbeat "auditing 60-nsls-knowledge for week $YYYY-Www..."
  2. Invoke /harvest-meeting --week-audit --week $YYYY-Www
     (Audit report displays to all users)
  3. If user in kb_authors.txt:
       /harvest-meeting offers promotion + stale-flag writes; user approves; commits.
     Else:
       Heartbeat "audit-only (not in KB_AUTHORS). To propose changes, open a PR."
  4. Write `## Knowledge Base` section to weekly close note with audit summary.
```

---

## Edge cases

| Case | Handling |
|---|---|
| Two SLT harvest the same meeting | Dedup step detects identical Fathom timestamp reference; second run drops as duplicate. |
| Git push race (someone else pushed first) | `git pull --rebase`, retry. If conflict on topic file, abort cleanly — better to lose a harvest than corrupt KB. |
| Local KB clone missing or stale | Step 4c runs `git pull --ff-only` first. If clone missing entirely, heartbeat "KB not cloned to $OBSIDIAN_VAULT_PATH; run setup" and skip step. |
| New topic needed (no good map) | Mapping step proposes `🆕 NEW: <slug>.md` in approval list. Approval creates the file with scaffolded frontmatter. |
| Fathom returns transcript but no summary | Use full transcript. Heartbeat "using full transcript (slower)" so user knows why this run took longer. |
| User cancels at approval | No writes, no commit. Heartbeat "harvest cancelled, no changes." Close-day continues. |
| Rubric drops everything | Heartbeat lists drops with categories (per heartbeat memory — silent skip would look broken). |
| Multi-day / late-night meeting | Attribute to date meeting ended. Documented in skill; revisit if it causes problems. |
| Reshaped text user disagrees with | `edit N: <new text>` overrides inline. Original sensitive text never persisted. |

---

## YAGNI (intentionally out of v1)

- Auto-source SLT from Airtable `is_slt` field (field doesn't exist yet — follow-up)
- Scheduled/background harvest (interactive approval requires user)
- PR-based workflow for SLT harvest (direct commit is the explicit choice)
- Slack/email notifications of new KB commits (`git pull` is sufficient)
- Per-candidate "defer to next week" action (use `--fathom-url` manually)
- LLM-generated relationship frontmatter on new topics (`feeds`, `related` hand-edited)
- Two-SLT same-hour edit conflict resolution (rare; rebase handles it)
- Non-SLT contribution via `/harvest-meeting` (README's edit + PR path covers it)
- Auto-update of `topic-mentions` counts in frontmatter (one-time seed value, drift is fine)

---

## Rollout

1. **Implementation PR** to `nsls-personal-toolkit`:
   - Create `skills/harvest-meeting/` (SKILL.md + references + kb_authors.txt)
   - Modify `skills/close-week/SKILL.md` (add Step 2b)
   - Modify `skills/close-day/SKILL.md` (add Step 4c)
   - Spec lives at `docs/specs/2026-05-29-kb-harvest-design.md` (this file)

2. **Local-fork port** to `~/.claude/skills/close-day/SKILL.md`: copy Step 4c verbatim from plugin. Add memory entry recording the port date so future drift-reconciliation knows it's in sync.

3. **Soft launch — Kevin solo for 3–5 days**: `kb_authors.txt` ships with all 7 SLT from v1 (per D8), but only Kevin is notified the pipeline exists. Kevin runs close-day with harvest on his own meetings to validate approval UX, extraction quality, and rubric behavior. The other 6 SLT could in principle trigger harvest in this window, but won't — they don't know to run it.

4. **Backfill 2026-05-19 → 2026-05-29 gap**: Kevin runs `/harvest-meeting --fathom-url <url>` on the high-signal meetings from this stretch (including the 2026-05-26 SLT meeting). KB feels alive on day-1 of broader rollout.

5. **Announce to other 6 SLT** via the plugin's auto-update path + a direct message describing the new flow. They run close-day → Step 4c discovers them in `kb_authors.txt` → harvest activates for them with no further config.

---

## Follow-ups (post-v1, tracked but not in scope)

- Add `is_slt` checkbox field to SLT MI Airtable `Members` table (`tbl9GMiujOzOD7xXn`); populate for the 7. Migrate `kb_authors.txt` to read live from Airtable.
- Add Heather Darnell's email to her Members record (currently missing).
- Fix the schema doc's stale "SLT Members (for Friday Script)" section at `~/nsls-skills/slt-ops/slt-meeting-agenda/references/airtable-schema.md` — currently lists Anish (not on SLT) and is missing Heather + Chelsea.
- Update Kevin's MEMORY.md NSLS KB section to reflect "v1 built YYYY-MM-DD" instead of "wiring is planned."
- Add a "current SLT roster" memory entry (the 7 names) to avoid future guessing.

---

## Success criteria for v1

- A typical close-day with one SLT-level meeting produces 1–5 candidate edits, presented as a clean numbered list.
- Approval-to-commit takes less than 30 seconds when bulk-approving.
- Zero rubric leaks (no profit numbers, no individual comp, no named personnel decisions) in the first month of commits. Audited month-end.
- All 7 SLT can run close-week and see a coherent audit report by week 2 of rollout.
- The 2026-05-26 SLT meeting that prompted this work is reflected in the KB within one week of v1 shipping.

---

## Next step

Implementation plan via `superpowers:writing-plans`. The plan should break this spec into ordered, reviewable PR-sized chunks (e.g., (a) `/harvest-meeting` skill core, (b) Step 4c integration, (c) Step 2b integration, (d) local-fork port, (e) backfill run).
