---
title: Manager-Coaching Person Intelligence v2
type: feat
status: completed
date: 2026-05-16
completed: 2026-05-16
plan_depth: deep
---

# Manager-Coaching Person Intelligence v2

## Overview

Upgrade the `person-intelligence` skill from a manual, single-person synthesis tool into an **automated manager-coaching system** that runs biweekly across the operating user's direct reports, ingests Fathom + Slack + Gmail, surfaces cross-relational insights, and keeps the emoji health chart on cadence — all generalized so any NSLS user inheriting the personal toolkit gets the same value relative to their position in the org chart.

The current skill (built 2026-03-22) was "designed for weekly automation" per the memory record but the cadence was never wired. Result: 36 of Kevin's 39 profiles are frozen at the 2026-03-22 batch — eight weeks of cadence integrity already lost. This plan closes that gap, generalizes the system, and adds a coaching frame that goes beyond relationship-health scoring to ask *"what does this person need to thrive?"*

## Problem Frame

The skill today does one thing well: synthesize a single rich profile from Fathom + Airtable on manual trigger. What's missing:

1. **No active cadence.** "Biweekly health check" is a documented practice, not an automation. Profiles go stale silently.
2. **No org-chart awareness.** The skill treats every relationship as equal. Direct reports — the relationships a manager is most accountable for — get no priority.
3. **Single-source ingest.** Fathom transcripts only. Slack DMs and Gmail threads contain the day-to-day signal that 1:1 transcripts miss.
4. **Per-profile, not relational.** Profiles are siloed. There's no surface that says "across your team this period, three people are drifting, one is thriving, and you're spending disproportionate time with the wrong one."
5. **No manager coaching frame.** Health scoring tells you the state of the relationship; it doesn't tell you what to invest in for the *person* — strengths, friction, growth edges, conditions for thriving.
6. **Hardcoded to Kevin.** The Known People Registry, exclusion lists, and meeting filters are bespoke to one user. Anyone else installing the personal toolkit gets a half-working skill.
7. **No backfill.** When automation lands, the emoji chart will have an 8-week hole from 2026-03-22 → 2026-05-17. Without backfill the cadence pattern looks broken from day one.

## Requirements Trace

- **R1.** Biweekly automation runs without manual prompting, surfaces a digest for review, and writes verifiable data updates (Fathom pulls, emoji rows, profile merges) — but never writes Kevin-voice narrative without review.
- **R2.** Direct reports identified via the GitHub-committed `org-chart.json` in the builder toolkit. **No Airtable API key required** for org-chart lookup. The skill verifies the file's freshness before using it.
- **R3.** Multi-source ingest: Fathom (existing pipeline), Slack (user-authorized MCP), Gmail (user-authorized MCP). All credentials are per-user — no shared org secrets beyond what the builder toolkit already commits.
- **R4.** Manager-coaching frame: every direct-report profile carries a "What [Name] Needs to Thrive" section with strengths, friction, growth edges, and concrete investments the manager should make.
- **R5.** Cross-relational digest surfaces patterns across the team — who's drifting, who's thriving, dimension trends, manager-mode review (am I doing this well?).
- **R6.** Works for any NSLS user. Operating identity is read from env vars + org-chart lookup. A non-manager (zero direct reports) still gets value via a "key relationships" curation path.
- **R7.** Backfill writes biweekly emoji rows for the missed periods (2026-03-22 → today) for direct reports + named key relationships so cadence integrity is intact when automation starts.
- **R8.** Manager-coaching insights surface as **actionable items in `/open-day` and `/open-week`** — not just inert profile sections. The morning routine and weekly planning pick up one or two concrete coaching moves the user should make this period (e.g., "Adam's growth-edge is product authority — ask him to lead the next SLT product review").
- **R9.** Profile synthesis applies the **`/full-shape` dimensional discovery pattern** to each relationship rather than forcing every person into a fixed template. The synthesizer casts a wide net to find the dimensions of *this specific relationship*, then provides macro frame + micro evidence per dimension, then lets the dominant patterns emerge. Generic templates produce slop; dimensional discovery produces shape.
- **R10.** **Three-artifact coaching design** (each artifact authored by a different party, serving a different purpose):
  - **Direct report profile** (e.g., Kevin's profile of Adam):
    - `## What [Name] Needs to Thrive` — manager's coaching of the report. *Private to the manager.*
    - `## How I Work with [Name]` — manager's own working-style disclosure FOR the report. *Optionally shareable.* Modeled on Lara Hogan's "how to work with me" pattern but personalized per report (different reports may need different framings of the manager's style).
  - **Upward relationship profile** (e.g., Kevin's profile of Gary):
    - `## My Stance: [emotion], [emotion], [emotion]` — the report's emotional frame for the relationship (the Gary "Respect, Protect, Resent" pattern is *one* example). *Private to the user.*
    - `## How I Can Work More Effectively with [Name]` — the report's own coaching toward their manager. *Private to the user.* The "managing up" surface, owned by the report.
    - `## Coaching Goals` (existing pattern) — concrete behaviors the report is practicing in the relationship.
  - **Peer relationships**: lighter `## Working Pattern` only; no coaching artifacts.

## Scope Boundaries

**In scope:**
- Upgrades to the existing `person-intelligence` skill (no new skill, no parallel system)
- New scripts under the same `scripts/` directory
- New references and a digest template
- Schedule registration via `/schedule` for the operating user
- Backfill of direct-report + SLT profiles only (not all 39)

**Out of scope (explicit non-goals):**
- Rewriting the existing synthesis pipeline architecture (incremental, not rewrite)
- Pulling Rippling data directly (project memory marks that as a separate roadmap)
- Backfilling profiles outside the direct-report + SLT scope (the other 30+ profiles continue to use manual-trigger model)
- Multi-tenant scheduling (each user's schedule lives in their own Claude environment)
- Building a UI; the surface is markdown in Obsidian
- Pushing data anywhere outside the user's Obsidian vault

## Context & Research

### Relevant Code and Patterns

- `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/SKILL.md` — current skill, 411 lines, has the biweekly health check section (line 136) and a "Weekly Automation" section (line 251) describing the incremental pattern but no scheduler
- `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/scripts/synthesize_profile.py` — uses Claude API with a SYSTEM_PROMPT (line 18); manager-coaching frame is added by extending the system prompt + adding new structured prompt sections, not rewriting the script
- `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/scripts/fetch_fathom_1on1s.py` — already supports `--after {date}` for incremental fetch and has a 6-hour cache layer at `~/.cache/person-intelligence/.meeting-cache.json`
- `~/nsls-skills/nsls-builder-toolkit/_shared/context/org-chart.json` — flat array of employee records, each with `manages: []` pre-computed reverse field. Given an email, O(1) direct-reports lookup. **This is the source of truth — no Airtable call needed.**
- `~/nsls-skills/nsls-builder-toolkit/_shared/scripts/sync_org_context.py` — builder toolkit's existing org-chart sync script. The personal toolkit can shell out to its `--update-vault` mode silently before health checks, but for the new skill the read path is just `json.load(org-chart.json)`.
- `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP/30-people/Gary Tuerack.md` — the gold-standard profile shape. Has the new `## Kevin's Stance: Respect, Protect, Resent` section + coaching goal pattern added 2026-05-16.
- `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/references/profile-template.md` — **stale** (39 lines, describes the old shape). Needs replacement to match the actual generated profiles.

### Institutional Learnings (from MEMORY.md)

- **"Close-day primary trigger is manual (removed scheduled auto-run 2026-04-20)"** — Kevin previously had scheduled close-day auto-running and pulled it. Lesson: scheduled writes-without-review feel off. The biweekly run must surface a digest, not silently rewrite profiles.
- **"Avoid jargon in shared materials"** — generalization means other NSLS users will read this. The skill text and digest output need plain language; no "bus factor" / "blast radius" framing.
- **"Auto-pull on session start"** — shared repos have "Before You Start" git pull blocks. The skill should assume builder toolkit is current and just read the JSON; rely on the toolkit's auto-update.
- **"Manager-visible only for health scores"** (from people-ops schema notes) — there's already a precedent for manager-only views. The skill leans into this: manager profiles get the coaching layer, peer/upward profiles get the relationship layer only.
- **"Departed profiles use `health-departed` tag"** — the skill already handles departures. Carry forward.

### External References

**Web research attempted, blocked on one-time CAPTCHA in Google AI Mode setup.** Once Kevin clears the CAPTCHA (Chrome window opens, solve, close — one-time), the two queries below should be re-run and findings folded into this section. For now, framing below is from training-data knowledge of canonical sources — verify before final design.

Queued queries (to re-run after CAPTCHA clear):
- "Manager coaching best practices 2026 (what direct reports need to thrive, Gallup Q12, Self-Determination Theory, strengths-based coaching, evidence-based dimensions)..."
- "Managing up 2026 modern playbook (two-way feedback, biweekly relationship rituals, AI-augmented 1:1 prep, manager attention allocation, Lattice/15Five/Culture Amp)..."

### Research-Grounded Frameworks (from training data — verify with fresh research)

**What direct reports need to thrive — the validated dimensions to track:**

| Source | Framework | Operational Dimensions |
|---|---|---|
| **Gallup Q12** | 12-item engagement survey, decades of meta-analysis | Clear expectations, materials/equipment, do-what-I-do-best, recognition, manager-cares, growth-encouragement, opinions-count, mission-connection, coworker-quality, best-friend-at-work, progress-talked-about, learning-opportunities |
| **Self-Determination Theory** (Deci & Ryan) | Intrinsic motivation backbone | **Autonomy** (control over work), **Competence** (ability to grow and succeed), **Relatedness** (genuine belonging) — when all three are met, intrinsic motivation is sustainable |
| **Daniel Pink's Drive** | Distillation of SDT for managers | Autonomy + Mastery + Purpose |
| **Lencioni's 5 Dysfunctions** | Team-level diagnostic | Trust → Conflict → Commitment → Accountability → Results (the absences) |
| **Paloma Medina's BICEPS** *(verify after CAPTCHA)* | Workplace threat/needs model | Map each report against Belonging, Improvement, Choice, Equality, Predictability, Significance — when any drops, performance suffers |
| **Lara Hogan's "How to Work with Me"** | Manager craft | Each manager writes a doc describing their working style — communication preferences, what helps them help you, what trips them up — and shares it with reports |
| **Kim Scott's Radical Candor** | Feedback frame | Care personally + challenge directly. Two axes; the failures are ruinous empathy, manipulative insincerity, obnoxious aggression |
| **Julie Zhuo (Making of a Manager)** *(specific framework cite to verify)* | Operational manager craft | Identify each report's strengths, growth areas, and working style preferences — three lenses to invest in per person |

**Synthesis for our skill: the "Thrive" section's four subsections map directly to research-validated dimensions:**
- *Strengths to invest in* → Zhuo's strengths lens + Gallup's "do what I do best every day"
- *Friction to address* → Medina's BICEPS gaps (which threat axis is active for this person?) + Lencioni dysfunctions visible at the 1:1 level
- *Growth edges* → Zhuo's growth lens + SDT's competence/mastery
- *Conditions for peak performance* → Medina's BICEPS positives (which axes are currently meeting their bar?) + Pink's autonomy + working-style specifics

**What separates great managers operationally** (per Google's Project Oxygen + Gallup):
- Coach, don't direct (Project Oxygen behavior #1)
- Empower the team, don't micromanage (#2)
- Express interest in success and wellbeing (#3)
- Be productive and results-oriented (#4)
- Be a good communicator (listen + share, #5)
- Help with career development (#6)
- Have a clear vision (#7)
- Have key technical skills (#8)
- *(Later additions: collaborate across teams, be a strong decision-maker)*

These translate to behaviors the skill can detect from Fathom transcripts and surface as coaching prompts: are 1:1s coach-shaped or status-update-shaped? How often does the user listen vs. talk (Fathom speaking %)? Is there evidence of career-development discussion in the last 14 days?

**Managing up — what a direct report tracks the other direction:**
- What does my manager *need* from me to reduce their cognitive load? (Anticipated decisions, summarized data, clear asks)
- What's their preferred communication channel and cadence? (Slack vs email vs meeting; long-form vs bullets)
- Where can I shape their thinking vs. where do I need to align? (Pick battles; commit to the rest)
- What patterns trigger their protective/defensive instincts? (Surprise, public disagreement, etc. — the Gary profile names these directly)

**Biweekly review rituals — emerging conventions:**
- Lattice and 15Five both default to weekly check-ins, manager-of-managers digests biweekly
- Common signals: 1:1 cancellation rate, recognition frequency, action-item carryover %, energy/mood trend, growth-question coverage
- Best-practice format: scorecard for the dashboard, journal for the memory (already what the existing skill does)

**AI-augmented manager coaching — risks specifically observed:**
- Surveillance perception when the data sources feel invasive (especially Slack DMs)
- Over-reliance on AI-generated insights without grounding in observed behavior
- Loss of relationship texture when AI summarizes too aggressively
- Coaching-by-template makes people feel like "a row in someone's spreadsheet"
- The 14-day scoping + participant-only constraints in this plan are direct responses to the surveillance pitfall

## Key Technical Decisions

- **Org chart from JSON, not Airtable.** Read `~/.claude/local-plugins/nsls-builder-toolkit/_shared/context/org-chart.json`. Verify file age before use; if >7 days stale, prompt the user to update the builder toolkit (`/update` or `cd ~/nsls-skills/nsls-builder-toolkit && git pull`). Never block — fall back to "I couldn't confirm org chart freshness, proceeding with cached data" and continue.
- **Operating user identity via env var + email match.** Add `OPERATING_USER_EMAIL` to `.env.example` (Kevin defaults to `kprentiss@nsls.org`). Look up the user in `org-chart.json` by email; read the `manages` array for direct reports. If no record found, fall back to a curated `KEY_RELATIONSHIPS` list (newline-separated names in env) so non-employees and unlisted users still get value.
- **Scheduling via `/schedule` remote routine, not CronCreate.** CronCreate only fires while Claude is running locally; `/schedule` runs as a remote agent and survives sessions — required for "fires reliably even when I'm not in Claude". Schedule: every other Sunday 7:00 AM ET. (Kevin works weekends per his memory; Sunday morning lets the digest land before his /open-week routine.)
- **Write trust ladder (replaces the earlier binary auto/proposal claim).** Auto-write isn't a clean line — meeting summaries are LLM-generated text and score carry-forward is a narrative claim disguised as data. Use a four-rung ladder instead:
  1. **Pure data** — Fathom meeting URLs, timestamps, signal counts, last-synthesized dates → auto-write
  2. **LLM-summarized data** — per-meeting summaries, slack/gmail signal blocks → auto-write *with provenance line* ("summarized by AI on YYYY-MM-DD; verify if used to decide")
  3. **Score continuity** — only with explicit "no-change asserted" marker OR rendered as un-assessed (see Backfill design); never silent carry-forward
  4. **Narrative changes** — Stance updates, coaching goals, Thrive subsections, "How I Work" content → always proposal in the digest, never written to the profile by automation
- **Unreviewed-digest accumulation rule.** If a digest sits unreviewed when the next biweekly fires, the new digest *consolidates* unreviewed proposals from the prior cycle rather than replacing them. Three consecutive unreviewed cycles → the digest's top section becomes "Six weeks of unreviewed proposals — would you like to step back?" so the system flags its own neglect rather than silently piling up.
- **Cross-relational digest as a separate doc.** Write to `$OBSIDIAN_VAULT_PATH/30-people/_pulse/YYYY-MM-DD-team-pulse.md`. Surface a link in `/open-day` and `/open-week`. Keep the digest out of individual profiles to avoid bloat.
- **Slack/Gmail scoping: signal, not surveillance.** Per person per period, pull: (a) DMs in the last 14 days, (b) channel messages where both parties are participants in a thread, (c) Gmail threads where both are direct participants. Don't run keyword searches on the person's name across the workspace — that's noise and feels invasive even when self-applied.
- **Slack/Gmail via MCP tool calls during the digest run, not Python scripts.** The MCPs are auth-bound to the operating user's session; running them inside the orchestrating session is the cleanest path. The fetch_fathom_1on1s.py script stays as Python since Fathom uses an API key in env.
- **Manager-coaching frame as a new top-level profile section.** Add `## What [Name] Needs to Thrive` between `## How They Manage Up / Down / Laterally` (or equivalent) and `## Personal Practices`. Four subsections: Strengths to invest in, Friction to address, Growth edges, Conditions for peak performance. Generated only for direct reports; peer/manager profiles get a lighter "## Working Pattern" instead.
- **Backfill via dated emoji rows + a single "backfill note" journal entry per profile.** Don't fabricate per-period detailed health journals retroactively. Just write the rows (one per missed biweekly date, carried forward at the last known score) and append a journal entry: *"### 2026-05-17 — Backfill\nNo human assessment for these periods; scores carried forward from 2026-03-22 baseline."* Honest about provenance.
- **Profile-template.md gets replaced, not edited.** The current template is from the pre-Gary-profile era and doesn't match the actual generated structure. Replace with a current snapshot that matches what `synthesize_profile.py` produces.
- **`/full-shape` dimensional discovery is the synthesis pattern, not a fixed template.** The synthesizer is instructed to *cast a wide net* for the dimensions of *this specific relationship* — find the ones that surprise, the ones that resist easy categorization, the ones that exceed existing labels. Then provide macro frame + micro evidence per dimension. The "Thrive" subsections are *defaults*, not a straitjacket — if the data reveals a dimension that doesn't fit one of the four buckets, the synthesizer is allowed to surface it under a custom subsection. Generic templates produce slop. Dimensional discovery produces shape.
- **Two-way coaching is built in, not bolted on.** For every direct-report profile, the synthesizer produces both a `## What [Name] Needs to Thrive` section (manager → report) AND a `## Coaching Up: What [Name] Can Ask of Me` section (report → manager — content the user can share with the report to teach managing-up skills). For the user's own manager (e.g., Kevin's Gary profile), the orientation flips: the user becomes the report, and the section becomes `## My Stance + Coaching Up` modeled on the Gary "Respect, Protect, Resent" pattern landed 2026-05-16. Peer relationships skip both.
- **`/open-day` and `/open-week` are the activation surface for coaching tasks.** The team-pulse digest can sit unread; the daily and weekly routines are where action happens. The biweekly sweep writes a small `coaching_actions.json` file to `~/.cache/person-intelligence/` per relationship. `/open-day` reads pending actions for today's calendar (e.g., "Adam 1:1 at 2pm — try the product-authority delegation move"). `/open-week` reads the week's calendar and pre-loads coaching actions per scheduled person.
- **Kevin-defaults vs. user-configurable surface.** The plan contains Kevin-specific defaults (SLT membership, Gary "Respect-Protect-Resent" stance as example, Fathom exclusion lists for Kevin's calendar conventions). These must be cleanly separated from generic skill behavior. The skill ships *example content* for Kevin (in `references/examples/`) and *user-configurable knobs* for everyone else (env vars + per-user config file). SLT membership becomes opt-in via `OPERATING_USER_IS_SLT=true`. The Gary stance is presented as *one example of upward framing*, not as the template. Fathom exclusion lists move to per-user `references/meeting-exclusions.json` with sensible defaults but user override allowed.
- **Preserve human-authored profile content during synthesis.** Profiles will grow human-curated sections over time (Kevin just added the Gary "Stance" section today). The synthesizer must detect zones authored by Kevin (heuristic: any section not in the generated-template list, or any content under a section with a `<!-- human-authored -->` marker the synthesizer can write but never overwrite) and **propose additions** rather than rewriting. Default behavior: if a profile already exists, the synthesizer reads it, identifies template-vs-human zones, and only writes proposals for template zones; human zones get a "consider updating" pointer in the digest, never a silent overwrite.
- **Observability surface.** Each sweep writes a one-line status file to `~/.cache/person-intelligence/last-sweep-status.json` with `{timestamp, exit_code, error, relationships_processed}`. `/open-day` reads this file and surfaces a brief alert if the last sweep failed or hasn't run in >18 days. Without this, scheduled failures are invisible.

## Open Questions

### Resolved During Planning

- **Q: Should the scheduled run write directly or always prompt for review?** Resolved: hybrid. Data writes (emoji row carry-forward, new meeting summaries, Slack/Gmail signal counts) are deterministic and write directly. Narrative changes (new coaching goals, "Stance"-style sections, score shifts) are proposed in the digest and require user review. Rationale: Kevin removed scheduled close-day for this reason (memory: 2026-04-20).
- **Q: Where does the cross-relational digest live?** Resolved: `30-people/_pulse/YYYY-MM-DD-team-pulse.md`. Surfaced in `/open-day` and `/open-week` as a link. Out of individual profiles to avoid bloat.
- **Q: Schedule day/time?** Resolved: Every other Sunday at 7:00 AM ET. Aligns with Kevin's `/open-week` routine and the existing biweekly cadence (Mar 22 → Apr 5 → Apr 19 → May 3 → **May 17 (next slot)**).
- **Q: Backfill scope — all 39 profiles or just managed relationships?** Resolved: Direct reports (from `org-chart.json`) + SLT members + a configurable `KEY_RELATIONSHIPS` list. The other ~30 profiles continue using manual trigger model. Rationale: data-cadence integrity matters most for relationships the user is actively managing; backfilling 30 peer/peripheral profiles is noise.
- **Q: Where does manager-coaching frame appear in the profile?** Resolved: New `## What [Name] Needs to Thrive` section, only for direct reports. Peer/upward relationships get a lighter `## Working Pattern` section instead. Direct-report determination from `org-chart.json` at synthesis time.
- **Q: How are Slack DMs scoped?** Resolved: Last 14 days, between the two participants only. No keyword searches. Channel mentions limited to threads where both are active participants.
- **Q: Should Fathom email + exclusion lists for each person be generalized?** Resolved: Exclusion patterns generalize to the JSON file `references/meeting-exclusions.json` keyed by relationship type (1:1, SLT, board, etc.) rather than per-person. Per-person overrides allowed but most patterns are role-based (e.g., "exclude 'all staff' from any 1:1 fetch") and shouldn't need per-user setup.

### Deferred to Implementation

- Exact Claude API token budget per biweekly run for a manager with ~10 reports. Need to measure on first real run; if costs are high, batch the synthesis or move to Haiku for digest summaries.
- Whether the digest doc should embed the emoji chart visually or just link to per-profile charts. Lean toward embed with a compact summary; verify readability after first generation.
- The exact schedule command syntax for `/schedule`. The skill exists but the interface depends on the runtime — resolve when wiring.
- Whether Gmail thread pulls need OAuth scope verification beyond what the existing MCP grants. Test on first run; document in the skill.
- Failure mode for `/schedule` when the user's machine is offline at 7am Sunday. Test: does it queue or skip? Document the actual behavior, don't speculate.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```
                   ┌──────────────────────────────┐
                   │  /schedule remote routine    │
                   │  every other Sunday 7am ET   │
                   └──────────────┬───────────────┘
                                  │ triggers
                                  ▼
                   ┌──────────────────────────────┐
                   │  scripts/biweekly_sweep.py   │
                   │  (new orchestrator)          │
                   └──────────────┬───────────────┘
                                  │
              ┌───────────────────┼────────────────────┐
              ▼                   ▼                    ▼
   ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
   │ resolve_user.py  │ │ load org-chart   │ │ list relations   │
   │ identity from    │ │ JSON, verify     │ │ = manages[] ∪    │
   │ OPERATING_USER_  │ │ freshness        │ │ KEY_RELATIONSHIPS│
   │ EMAIL            │ │                  │ │ ∪ SLT (if Kevin) │
   └──────────────────┘ └──────────────────┘ └──────┬───────────┘
                                                   │
                            for each relationship: │
              ┌────────────────────────────────────┤
              ▼                                    ▼
   ┌──────────────────┐         ┌─────────────────────────────────┐
   │ Fathom: --after  │         │ MCP calls (orchestrator-driven) │
   │ last-synthesized │         │  • Slack DMs (14d)              │
   │ (existing script)│         │  • Slack thread mentions (14d)  │
   └────────┬─────────┘         │  • Gmail threads (14d)          │
            │                   └────────────┬────────────────────┘
            └──────────────┬─────────────────┘
                           ▼
              ┌─────────────────────────────┐
              │ synthesize_profile.py       │
              │ + new system-prompt section │
              │   for manager-coaching      │
              │ + Slack/Gmail signal blocks │
              └────────────┬────────────────┘
                           │
              ┌────────────┴──────────────────────────┐
              ▼                                       ▼
   ┌──────────────────────┐              ┌──────────────────────────┐
   │ DATA WRITES (auto)   │              │ NARRATIVE PROPOSALS      │
   │ • emoji row          │              │ (digest, not profile)    │
   │ • new meeting refs   │              │ • score shift suggestions│
   │ • signal counts      │              │ • new coaching goals     │
   │ • last-synth bump    │              │ • thrive-frame updates   │
   └──────────────────────┘              └────────────┬─────────────┘
                                                      │
                                                      ▼
                                  ┌─────────────────────────────────┐
                                  │ 30-people/_pulse/YYYY-MM-DD-    │
                                  │ team-pulse.md                   │
                                  │ + cross-relational summary      │
                                  │ + drift/thrive/attention list   │
                                  │ + manager-mode review prompt    │
                                  └─────────────────────────────────┘
                                                      │
                                                      ▼
                                  surfaced in /open-day + /open-week
                                  Kevin reviews → accept/edit/reject
                                  → profile narrative gets written
```

## Implementation Units

- [x] **Unit 1: Identity + org-chart resolution**

**Goal:** Given an operating user, resolve "who do I manage" and "which relationships are biweekly-tracked" without requiring Airtable credentials.

**Requirements:** R2, R6

**Dependencies:** None

**Files:**
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/scripts/resolve_user.py`
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/scripts/list_relationships.py`
- Modify: `~/nsls-skills/nsls-personal-toolkit/.env.example` (add `OPERATING_USER_EMAIL`, `KEY_RELATIONSHIPS`)
- Test: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/tests/test_resolve_user.py`

**Approach:**
- `resolve_user.py` reads `OPERATING_USER_EMAIL` from env, locates the matching record in the builder toolkit's `org-chart.json`. Returns JSON: `{name, email, slack, manages: [...], manager: "..."}`.
- `list_relationships.py` composes the biweekly-tracked set: `manages[] ∪ KEY_RELATIONSHIPS ∪ SLT_MEMBERS (if user is in SLT)`. Outputs JSON list with each person's resolved email, slack ID, and tracking reason ("direct_report", "key_relationship", "slt_peer").
- Freshness check: compare `org-chart.json` mtime to today; if >7 days, emit warning to stderr but still return the data. Never block.
- Path resolution: prefer `~/.claude/local-plugins/nsls-builder-toolkit/_shared/context/org-chart.json` (plugin-installed path). Fallback to `~/nsls-skills/nsls-builder-toolkit/_shared/context/org-chart.json` (dev clone). Emit error if neither exists with the message *"org-chart.json not found. Run `/update` or check builder toolkit installation."*

**Patterns to follow:**
- `sync_org_context.py` for JSON parsing style and stderr-warning convention
- `fetch_fathom_1on1s.py` for env-var resolution with explicit error messages

**Test scenarios:**
- Operating user is found in org chart → returns correct `manages[]` list
- Operating user not in org chart (e.g., contractor) → returns empty `manages` but composed list includes `KEY_RELATIONSHIPS`
- `org-chart.json` missing from both paths → script exits with helpful error
- `org-chart.json` is 30 days stale → warning to stderr, data still returned
- `OPERATING_USER_EMAIL` not set → script exits with the `.env.example` location in the error

**Verification:**
- Running `OPERATING_USER_EMAIL=kprentiss@nsls.org python3.12 list_relationships.py` outputs Kevin's SLT + direct reports without any Airtable call. Confirm via network monitor or by setting `AIRTABLE_API_KEY=invalid` in the test env.

---

- [x] **Unit 2: Multi-source ingest for Slack + Gmail (orchestrator-driven)**

**Goal:** Per relationship per period, pull recent Slack DMs and Gmail threads as additional context for synthesis.

**Requirements:** R3

**Dependencies:** Unit 1

**Files:**
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/references/ingest-scoping.md` (documents the scoping rules so future contributors / the user can audit and adjust)
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/SKILL.md` — add an "## Ingest Sources" section documenting which MCP calls fire per source

**Approach:**
- No new Python; orchestration happens in the skill prompt itself. The skill instructs Claude to make targeted MCP calls per relationship:
  - `mcp__claude_ai_Slack__slack_read_dm` with the target's Slack ID (from `org-chart.json`)
  - `mcp__claude_ai_Slack__slack_search_public_and_private` constrained to threads where both are participants (last 14 days)
  - `mcp__claude_ai_Gmail__search_threads` with `from:{email} OR to:{email}` last 14 days
- The orchestrator (Unit 3) feeds the returned content into `synthesize_profile.py` as new fields: `slack_signals`, `gmail_signals`.
- **Three filters applied before content reaches the synthesizer:**
  1. **Third-party stripping.** Any names other than the operating user and the target person are replaced with role descriptors (e.g., "another SLT member", "a board member") OR omitted from the signal block. The synthesizer never sees other named individuals from a DM thread between two people. This protects people who happen to be cc'd or mentioned in passing.
  2. **Per-user `INGEST_EXCLUDE_THREADS` list.** Stored in `~/nsls-skills/nsls-personal-toolkit/.env` as patterns: Gmail subject regexes + Slack channel ID list. Anything matching is skipped. Defaults: legal/HR/payroll subject keywords; `#hr-*` and `#legal-*` channels.
  3. **Low-signal filter.** Skip messages under 20 characters or pure-emoji/sticker replies. Skip routine logistics messages (regex: `running late|brb|👍|got it`). Configurable per user.
- The scoping doc (`ingest-scoping.md`) spells out the privacy posture, the three filters, and how to extend the exclude list. It also explicitly says: *this is the operating user reading their own messages, not the system reading anyone else's.*
- For users who haven't connected Slack/Gmail MCPs, the skill skips those sources silently and notes it in the digest ("Slack data unavailable — connect via `/connect`").
- **Opt-out per source via env var.** `SKIP_SLACK_INGEST=1` or `SKIP_GMAIL_INGEST=1` disables that source for users who don't want it, even when the MCP is connected.

**Patterns to follow:**
- The skill's existing "discover available data" pattern (SKILL.md line 31) — same fail-soft approach: try each source, work with whatever's available

**Test scenarios:**
- Kevin runs biweekly sweep with Slack MCP connected → DMs from last 14 days appear in synthesis input
- Kevin runs without Gmail MCP connected → skill skips Gmail, notes it, continues
- A direct report has no Slack ID in org-chart.json → skill skips Slack for that person, continues
- Last-14-day window contains zero DMs → synthesis input gets an empty slack_signals block, no error
- A DM thread between Kevin and Adam mentions Cory by name → Cory's name is stripped or replaced in the signal block; doesn't surface in Adam's profile
- A Gmail thread matches an `INGEST_EXCLUDE_THREADS` pattern (legal subject keyword) → entire thread is skipped, doesn't reach the synthesizer
- A DM is "👍" or "running late" → filtered out by low-signal filter
- `SKIP_SLACK_INGEST=1` is set → no Slack MCP calls happen, signal block is empty, synthesis still completes from Fathom + Gmail

**Verification:**
- For a test person, the synthesis prompt visibly includes a "Recent Slack Signal" section with the last-14-day DM count and a summary of topics. Verify by inspecting the assembled JSON before it goes to the Claude API. Manually check that no third-party names appear in the signal block when the test fixture includes a thread with a cc'd third party.

---

- [x] **Unit 3: Biweekly sweep orchestrator**

**Goal:** A single entry point that runs the full biweekly sweep for the operating user — identity resolution, relationship enumeration, per-person multi-source ingest, profile updates, digest generation.

**Requirements:** R1, R5

**Dependencies:** Units 1, 2

**Files:**
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/scripts/biweekly_sweep.py`
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/SKILL.md` (add "## Biweekly Sweep" section with the command to invoke)
- Test: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/tests/test_biweekly_sweep.py`

**Approach:**
- `biweekly_sweep.py` is the orchestrator. It:
  1. Calls `resolve_user.py` and `list_relationships.py` to get the relationship set
  2. For each relationship, calls existing `fetch_fathom_1on1s.py --after {last-synthesized}` to get new meetings only
  3. Returns a structured manifest to stdout describing what's pending: which people, how many new meetings, what data is available — the Claude-side orchestrator then runs the MCP calls for Slack/Gmail and feeds everything into `synthesize_profile.py`
  4. Writes a `biweekly-sweep-{date}.manifest.json` to `~/.cache/person-intelligence/` so re-runs can resume mid-stream
- The Python script handles deterministic work; the Claude session handles the MCP orchestration and the LLM synthesis. Clean separation: Python = data plumbing, Claude = decisions and synthesis.
- Idempotency: re-running on the same day reads the manifest and skips already-completed relationships.
- **Status file:** at the end of each sweep, write `~/.cache/person-intelligence/last-sweep-status.json` with `{timestamp, exit_code, error, relationships_processed, digest_path}`. `/open-day` and `/open-week` read this for failure surfacing (see Unit 8). Without this file, scheduled failures are invisible.

**Patterns to follow:**
- `synthesize_profile.py`'s structured JSON-on-stdin pattern
- `sync_org_context.py`'s `--update-vault` mode for "deterministic file writes from script"

**Test scenarios:**
- Kevin runs the sweep with 6 direct reports and 5 key relationships → manifest lists 11 people with their last-synthesized dates
- One report has no new Fathom meetings since last-synth → still appears in manifest with `new_meetings: 0` so the digest can still note "no signal change"
- Sweep is interrupted mid-stream → re-run resumes from manifest without re-fetching completed people
- A person in `KEY_RELATIONSHIPS` is not in the org chart → still tracked, marked `org_chart_record: null`, synthesis runs from Fathom + manual notes only

**Verification:**
- `python3.12 biweekly_sweep.py` produces a manifest at `~/.cache/person-intelligence/biweekly-sweep-2026-05-17.manifest.json` listing each tracked relationship with their data inventory. No Airtable calls made. Verify by setting `AIRTABLE_API_KEY=invalid` and confirming the run completes.

---

- [x] **Unit 4: Manager-coaching synthesizer with /full-shape discovery and two-way coaching**

**Goal:** Extend `synthesize_profile.py` to apply `/full-shape` dimensional discovery per relationship and to produce both manager → report and report → manager coaching content based on the relationship type.

**Requirements:** R4, R9, R10

**Dependencies:** Unit 1 (needs `manages[]` and `manager` to know relationship type)

**Files:**
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/scripts/synthesize_profile.py`
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/references/profile-template.md` (full replacement; current template is stale)
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/references/manager-coaching-frame.md` (the system-prompt extension for direct reports)
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/references/coaching-up-frame.md` (the system-prompt extension for upward relationships)
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/references/dimensional-discovery-frame.md` (the /full-shape instruction block)

**Approach:**
- Synth script gets a new input field: `relationship_type` ∈ {`direct_report`, `peer`, `manager`, `key_relationship`}. (Collapsed from 5 values — `peripheral` was undifferentiated from `peer` in synthesis behavior.) Resolved at orchestration time from `org-chart.json` (Unit 1):
  - `manages[]` contains the person → `direct_report`
  - The person == operating user's `manager` field → `manager`
  - Same `manager` value as operating user → `peer`
  - Not in org chart but listed in `KEY_RELATIONSHIPS` env → `key_relationship` (treated as a `peer` for synthesis unless overridden)
- **Dimensional discovery (R9, always-on):** The SYSTEM_PROMPT gets a permanent extension instructing the synthesizer to *first cast a wide net for the dimensions of this specific relationship* (what shows up in the data that wouldn't fit a generic template), *then* fit content to the standard sections only where the data supports it, *then* surface custom subsections for dimensions that exceed the template. Lives in `dimensional-discovery-frame.md`.
  - **Custom-subsection guardrail with example:** the synthesizer may add a custom subsection only when (a) the dimension shows up in ≥3 distinct meeting summaries or signal blocks, (b) it doesn't fit any of the default subsections without distortion, and (c) it would be useful again next period. *Good example:* a subsection like "## Negotiation style" for a person who negotiates frequently and visibly. *Bad example:* a one-off "## Recent vacation" subsection that won't apply next sweep. The synthesizer is instructed with both examples.
- **Three coaching artifacts (R10) — applied per relationship type:**

  | relationship_type | Sections the synthesizer produces (in addition to standard structure) |
  |---|---|
  | `direct_report` | `## What [Name] Needs to Thrive` (private to manager) + `## How I Work with [Name]` (manager self-disclosure, optionally shareable) |
  | `manager` | `## My Stance: [emotions]` + `## How I Can Work More Effectively with [Name]` + propose updates to `## Coaching Goals` |
  | `peer` | `## Working Pattern` only |
  | `key_relationship` | Same as `peer` by default; user can override per person via a `coaching_frame:` frontmatter field (`direct_report`, `manager`, `peer`) for cases like contractors who function as direct reports |

- **What [Name] Needs to Thrive section structure (direct_report only):** four default subsections grounded in the research frame — *Strengths to invest in* (Zhuo + Gallup), *Friction to address* (BICEPS gaps), *Growth edges* (Zhuo + SDT competence), *Conditions for peak performance* (BICEPS positives + working style). Empty subsections are omitted, not placeholder-filled.
- **How I Work with [Name] section structure (direct_report only):** the manager's working-style disclosure, **personalized per report** because different reports may benefit from different framings. Subsections: *How I communicate best*, *What helps me help you*, *What trips me up*, *How we should handle disagreement*. Drafted FOR the report — the manager could copy-paste it into a Slack DM or doc share.
- **My Stance + How I Can Work More Effectively (manager type only):** the upward profile pattern, modeled on the Gary 2026-05-16 update. Stance names 2-4 emotions and frames the relationship; How-I-Can-Work surfaces concrete behaviors the user is practicing in the relationship.
- **Preserve human-authored sections (no silent rewrites):** the synthesizer reads any existing profile, identifies sections it doesn't recognize from the template list, and treats them as human-authored. For these, it surfaces a "consider updating: section X is 60+ days old" pointer in the digest but never overwrites. Optionally, sections can be marked `<!-- human-authored -->` to make the boundary explicit.
- **Template replacement:** New template uses Gary Tuerack's profile as the structural reference. Section ordering: Identity → Style → Mental Models → Priorities → Energizes/Concerns → Manages Up/Down/Lat → Personal Practices → Communication → Key Relationships → Quotes → Personal → [conditional coaching sections per relationship_type] → Coaching Goals → Health.

**Patterns to follow:**
- The existing `synthesize_profile.py` system-prompt pattern at line 18 — keep the same voice ("direct, plain-language style. Numbers over adjectives. Short sentences.")
- Gary Tuerack profile as the gold-standard layout for upward relationships
- The /full-shape skill's "cast the net → macro+micro per dimension → filter → name emerges" pattern as the synthesis instruction

**Test scenarios:**
- Running synthesis on a direct report (e.g., Adam Stone) → output includes both `## What [Name] Needs to Thrive` AND `## How I Work with [Name]`, grounded in actual transcript evidence
- Running synthesis on Gary (Kevin's manager) → output includes `## My Stance` + `## How I Can Work More Effectively with [Name]`, no `## What [Name] Needs to Thrive` section
- Running synthesis on a peer (e.g., Cory Capoccia) → no coaching arrows; just `## Working Pattern`
- Running synthesis on Lauren (contractor, in KEY_RELATIONSHIPS with `coaching_frame: direct_report` override) → produces the direct-report shape even though she's not in `org-chart.json`
- Running synthesis on a person whose data surfaces a dimension passing the custom-subsection guardrail (3+ meetings, doesn't fit defaults, durable) → synthesizer adds a custom subsection
- Running synthesis on a person with a borderline dimension (1 meeting, ephemeral) → synthesizer does NOT add a custom subsection
- Running synthesis when `relationship_type` is missing → defaults to `peer` framing (safe default)
- Re-running synthesis on Gary's profile (which has human-authored "Kevin's Stance: Respect, Protect, Resent" added 2026-05-16) → that section is preserved; synthesizer proposes updates in digest, doesn't overwrite

**Verification:**
- Regenerate Adam Stone's profile. Compare against expected output: should have both Thrive and How-I-Work-With sections, with content grounded in his actual Fathom transcripts (not generic management-101 text). The "How I Work with Adam" section should be different in framing from a hypothetical "How I Work with Ashleigh" (personalized, not boilerplate).
- Regenerate Gary Tuerack's profile (upward case). The existing `## Kevin's Stance: Respect, Protect, Resent` section is preserved untouched; any proposed updates appear in the digest's review queue, not in the profile itself.

---

- [x] **Unit 5: Cross-relational digest**

**Goal:** A team-pulse digest document generated each biweekly run, surfacing patterns across relationships (not per-profile) so the user sees the team-shaped picture.

**Requirements:** R5

**Dependencies:** Units 3, 4

**Files:**
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/scripts/generate_team_pulse.py`
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/references/team-pulse-template.md`
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/open-day/SKILL.md` (surface the latest pulse doc link)
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/open-week/SKILL.md` (same)

**Approach:**
- Pulse doc is written to `$OBSIDIAN_VAULT_PATH/30-people/_pulse/YYYY-MM-DD-team-pulse.md`.
- Sections:
  - **Cadence integrity** — list of relationships with last-synthesized dates; flag anyone >21 days
  - **Drift** — health score declined ≥1 point since last assessment, with one-line "why" pulled from the digest reasoning
  - **Thrive** — health score improved ≥1 point or sustained 💚 with strong engagement signal
  - **Attention** — anyone at 🟡 or 🔴, sorted by trend (deteriorating > stable > improving)
  - **Manager mode review** — surfaces a question for the operating user: "Are you over-investing in X (your high-tension relationship) at the expense of Y (your low-engagement direct report)?" Based on Fathom meeting time distribution.
  - **Proposed coaching goal updates** — list per-person, presented as "accept/edit/reject" rather than auto-written
- Generation: `generate_team_pulse.py` reads the biweekly sweep manifest + reads each profile's health frontmatter + recent journal entries. It assembles structured input for a single Claude API call that produces the digest. **One synthesis call, not per-person.**
- The pulse doc is the cross-relational layer. Individual profiles stay focused on the person.

**Patterns to follow:**
- The biweekly health check's existing "Present current state" block (SKILL.md line 173) — the digest extends this same shape across more dimensions
- `synthesize_profile.py`'s JSON-on-stdin pattern for the team-pulse script

**Test scenarios:**
- Three of Kevin's 6 direct reports' scores declined → "Drift" section lists those three with one-line reasoning each
- All scores held steady at 🟢 → digest still produces a valid file; "Drift" empty, "Thrive" empty, "Cadence integrity" populated
- A direct report has zero new Fathom meetings since last sweep → flagged in "Cadence integrity" with "no new 1:1 data — consider scheduling"
- Manager mode review: meeting-time distribution math is calculable from Fathom meeting durations × person tagging in the cache

**Verification:**
- Generated digest at `_pulse/2026-05-17-team-pulse.md` is opened in Obsidian and renders cleanly. Verify it links correctly to each `30-people/[Name].md` and surfaces in `/open-day` next morning.

---

- [x] **Unit 6: Schedule registration**

**Goal:** Wire `/schedule` to fire the biweekly sweep at every other Sunday 7am ET for the operating user.

**Requirements:** R1

**Dependencies:** Units 3, 5

**Files:**
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/SKILL.md` (add a "## Scheduling" section with the exact `/schedule` invocation)
- Modify: `~/nsls-skills/nsls-personal-toolkit/commands/update-personal-productivity.md` (mention the schedule registration as part of setup)

**Approach:**
- The skill itself documents the schedule registration command; the actual `/schedule` invocation happens in Kevin's session (and any subsequent user's setup).
- The scheduled routine fires a prompt that says: *"Run the person-intelligence biweekly sweep for {OPERATING_USER_EMAIL}. Use the `/person-intelligence` skill, biweekly sweep mode."* — the skill picks up the rest from there.
- The schedule writes (or appends to) the team-pulse digest doc. Narrative changes stay as proposals in the digest.
- Documentation includes how to: change the day, pause the schedule, opt out, run manually with `/person-intelligence biweekly sweep`.

**Patterns to follow:**
- The `/schedule` skill's own docs (read at runtime, not pre-decided here)
- Memory: "Close-day primary trigger is manual" — the scheduled run must be opt-in-friendly with clear "how to pause" instructions in the skill

**Test scenarios:**
- Schedule fires on the test date → biweekly sweep runs end-to-end → team-pulse doc appears in Obsidian
- User wants to pause for two weeks (e.g., vacation) → instructions in SKILL.md walk them through `/schedule pause`
- A different NSLS user installs the personal toolkit and runs `/personal-setup` → they're prompted to register their own biweekly schedule

**Verification:**
- Manual test: register a one-time schedule for "5 minutes from now" with a smaller relationship set, confirm the sweep runs end-to-end. Then register the real every-other-Sunday cadence.

---

- [x] **Unit 7: Backfill emoji rows for cadence integrity**

**Goal:** Write biweekly emoji rows for the missed periods (2026-03-22 → today) for direct reports + SLT + key relationships, so the health table has cadence integrity when automation starts.

**Requirements:** R7

**Dependencies:** Units 1, 4

**Files:**
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/scripts/backfill_emoji_chart.py`
- Modify (output): `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP/30-people/*.md` (for the tracked set only)

**Approach:**
- Script reads each tracked profile, finds the `## Relationship Health` table, identifies the last assessed row, computes biweekly dates between that row and today.
- For each missed date, write a **visibly-distinct backfilled row** using a different emoji set so the chart is honest at a glance:
  - **Date column** ends with `⚪` (e.g., `2026-04-05 ⚪`)
  - **State column** uses `⚪ {score}` (the un-assessed rollup marker) instead of a colored emoji
  - **Per-dimension cells** use outlined/muted emoji corresponding to the carried-forward score: `🟩` for what would be `💚`, `🟨` for `🟢`/`🟡`, `🟧` for `🔴`. These render as visually-similar-but-distinguishable from the filled assessed emoji.
  - **Note column** (add to table if not present) reads `Backfilled` for these rows; `Assessed` for human-scored rows
- The latest row (today's date) is a real assessment from the sweep — uses the normal filled emoji set with `Note: Assessed`.
- Append a single journal entry at the bottom of each backfilled profile: *"### 2026-05-17 — Cadence resumption\nBackfilled rows from 2026-03-22 to 2026-05-17 use the outlined emoji set (⚪/🟩/🟨/🟧) to indicate no human assessment. The most recent row is a fresh assessment from the automated sweep."*
- Frontmatter `last-synthesized` advances only on rows actually re-synthesized (today's row); it does NOT advance for backfilled-carryforward rows.
- Dry-run mode (`--dry-run`) prints the diff per file without writing.
- **Migration note for the existing health tables:** The current Gary table doesn't have a `Note` column. Migration adds it lazily — backfilled rows get `Backfilled` in a new column; existing rows above get `Assessed` filled in; older rows get blank (we don't retro-label history we didn't track).

**Patterns to follow:**
- The existing health-table format in Gary Tuerack.md (the gold-standard profile)
- The journal entry format documented in SKILL.md line 217

**Test scenarios:**
- A profile has its last row at 2026-03-22 → backfill writes 3 carry-forward rows (Apr 5, Apr 19, May 3) with the outlined emoji set + `Backfilled` note, plus today's row (May 17) as a fresh assessment with filled emojis + `Assessed` note
- A profile has been updated since 2026-03-22 (e.g., Jack Cohen at 2026-05-07) → backfill writes only today's assessment row (May 17), no carry-forward rows needed
- A profile lacks a `## Relationship Health` section entirely → script skips with a "no health table found" log entry; does not invent one
- A profile already has a `Note` column → script appends to it; doesn't duplicate the column
- Dry-run mode produces a complete diff without touching any file

**Verification:**
- After backfill, open Gary Tuerack.md and visually scan the health table. Backfilled rows should be obviously distinguishable from assessed rows at a glance (outlined vs filled emoji). The journal entry at the bottom explains the convention. Compare to the table rendered in Obsidian — does the visual distinction survive Obsidian's rendering?

---

- [x] **Unit 8: Coaching-action surfacing in `/open-day` and `/open-week`**

**Goal:** Make coaching insights actionable inside the user's daily and weekly routines, not just inert profile sections. After each biweekly sweep, the user's morning and weekly planning routines pre-load specific coaching moves tied to scheduled people.

**Requirements:** R8

**Dependencies:** Units 4, 5

**Files:**
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/scripts/extract_coaching_actions.py`
- Create (cache output): `~/.cache/person-intelligence/coaching_actions.json` (regenerated each sweep)
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/open-day/SKILL.md`
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/open-week/SKILL.md`

**Approach:**
- `extract_coaching_actions.py` runs at the end of the biweekly sweep. It walks each updated profile and pulls the `Actions: [ ]` checkbox items from active coaching goals + the implementation-ready items from the Thrive section's *Friction to address* and *Growth edges* subsections. Each action carries:
  - `person`: name
  - `relationship_type`: direct_report | manager | peer | key_relationship
  - `text`: the action verbatim (so the user recognizes their own wording)
  - `dimension`: which health dimension or coaching goal it ties to
  - `priority`: derived from the relationship's current health (lower scores → higher priority)
  - `times_surfaced`: integer, incremented each time /open-day surfaces this action
  - `status`: `pending | done | stale | dismissed`
- Output is written to `~/.cache/person-intelligence/coaching_actions.json` keyed by person name. /open-day infers timing-fit from the action text (1:1 vs async vs team-meeting) at surface time — no upstream metadata required.
- **`/open-day` integration:** The skill reads today's calendar, identifies people-meetings, and surfaces coaching actions with these hard rules:
  - **Total cap: 3 coaching actions across the whole morning note**, regardless of meeting count. Prioritized by (a) relationship-health score ascending (lowest first), (b) action freshness, (c) explicit meeting today.
  - Format: *"📋 Adam 1:1 @ 2pm — coaching action: 'ask him to lead the next SLT product review' (growth-edge: product authority)"*
- **`/open-week` integration:** The skill reads the week's calendar, groups by person, surfaces at most one action per person scheduled this week (cap: 5 total). Also surfaces the *"Manager mode review"* prompt drawn from the pulse digest only when meaningful skew was flagged.
- **Decay / dismiss model:**
  - When an action is surfaced, `times_surfaced++`
  - When `times_surfaced >= 3` without status change, the action auto-moves to `stale` and drops out of /open-day rotation (still visible in the profile + in a "Stale coaching backlog" section of the team-pulse digest)
  - Each surfaced action in the morning note includes a `[done | stale | snooze 1w]` inline marker the user can edit; running /open-day with that edit recorded updates the cache
- **No silent writes.** Actions are suggestions in the routine notes; the user accepts/edits/dismisses inline.
- **Two-way integration:** Upward-relationship actions (from the manager-type profile) surface the same way before 1:1s with the user's manager. *"📋 Gary 1:1 @ 10am — managing-up move: 'name the gotcha-moment friction from last week before three meetings pass'"*

**Patterns to follow:**
- `/open-day`'s existing pattern of reading calendar + Asana tasks + Obsidian carry-overs and pre-populating the morning check-in note
- The "Coaching Goals → Actions checkboxes" format already established in profiles (Gary's profile has the canonical example)
- Memory: "Close-day suggestions pattern — duplicate in both End of Day and Morning Check-in, name specific people" — apply same shape here

**Test scenarios:**
- Kevin has a 2pm Adam 1:1 scheduled → /open-day morning note includes Adam's top coaching action with the dimension and evidence pointer
- Kevin has no people-meetings on a given day → /open-day skips the coaching-actions section silently
- Kevin has 5 people-meetings → /open-day caps at **3 total** surfaced actions, prioritized by relationship-health-low + action-freshness; doesn't flood the note
- /open-week shows the manager-mode time-allocation prompt only when pulse digest flagged a meaningful skew
- Same action surfaces 3 times without being marked done → 4th cycle, action auto-moves to `stale` and stops surfacing in /open-day; appears in pulse-digest "Stale coaching backlog" section
- Kevin marks an action `[done]` inline in the morning note → next /open-day run reads the mark and updates the cache; action no longer surfaces
- Kevin marks an action `[snooze 1w]` → action skips next 7 days, then resumes surfacing
- Gary 1:1 on the calendar → /open-day surfaces *managing-up* actions toward Gary, not coaching-down actions
- /open-day fires on a day when the last biweekly sweep failed (per `last-sweep-status.json`) → morning note surfaces a one-line alert: *"⚠️ Last person-intelligence sweep failed on YYYY-MM-DD. Run manually with `/person-intelligence biweekly sweep`."*

**Verification:**
- Run a manual /open-day after a biweekly sweep. Verify the morning check-in note includes coaching actions tied to today's people-meetings. Confirm the actions are *the same text* as what's in the profiles (not paraphrased — direct quotes so the user recognizes their own intent).
- Run /open-week on a Monday. Verify each scheduled-person of the week has at most one surfaced action, and the manager-mode review prompt appears only if attention-allocation skew was flagged.

---

- [x] **Unit 9: Generalization, install flow, documentation**

**Goal:** Make sure a fresh NSLS user installing the personal toolkit can opt into this system in under five minutes.

**Requirements:** R6

**Dependencies:** Units 1–8

**Files:**
- Modify: `~/nsls-skills/nsls-personal-toolkit/.env.example` (final pass for any new vars)
- Modify: `~/nsls-skills/nsls-personal-toolkit/CLAUDE.md` (add a row in the skills table about manager-coaching mode, link to setup)
- Modify: `~/nsls-skills/nsls-personal-toolkit/commands/update-personal-productivity.md` (add a "person-intelligence biweekly" setup step)
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/SKILL.md` (final consolidation — remove Kevin-specific Known People Registry, replace with auto-discovery from org-chart + KEY_RELATIONSHIPS)
- Create: `~/nsls-skills/nsls-personal-toolkit/updates/2026-05-XX-person-intelligence-v2.md` (release note documenting the change for forks)

**Approach:**
- Remove all Kevin-hardcoded references from the skill (the SLT names list at SKILL.md line 41 becomes `org-chart.json` driven).
- The "Known People Registry" table at line 389 becomes a runtime-discovery section — explain that the skill auto-discovers people from `org-chart.json` and from cached Fathom emails, no manual table maintenance required.
- Release note explains: what changed, what new env vars to set, how to opt into the biweekly schedule, how to opt out. Plain language, no jargon (per memory).
- The SKILL.md's "Pipeline" section gets a new top-level subsection: *"## Mode: Single-Person Synthesis"* vs *"## Mode: Biweekly Sweep"*. The single-person mode is what exists today; the biweekly sweep is the new mode.

**Patterns to follow:**
- `~/nsls-skills/nsls-personal-toolkit/updates/` existing release notes
- `~/nsls-skills/nsls-personal-toolkit/CLAUDE.md` plain-language style ("This is one person's answer to..." — keep that voice)

**Test scenarios:**
- A fresh NSLS user (simulate by renaming the .env file, running `/personal-setup`) → walked through OPERATING_USER_EMAIL setup, optionally Slack/Gmail connection check, optionally schedule registration
- A fork that opts out of biweekly scheduling but wants manager-coaching frame → can run `/person-intelligence biweekly sweep` manually and gets the same output
- A non-manager NSLS user (e.g., an IC) → `manages[]` is empty, but `KEY_RELATIONSHIPS` is offered as the entry point; skill works with that curated list

**Verification:**
- Walk through the install flow as if a new user. Time it. Document any friction in the release note. The setup should take <5 minutes for someone who already has the builder toolkit installed.

## System-Wide Impact

- **Interaction graph:** New schedule entry, new digest doc surfaced in `/open-day` and `/open-week`, new `coaching_actions.json` cache consumed by daily/weekly routines. The biweekly sweep is a new automated path that touches every direct-report profile + the team-pulse doc. `/open-day` and `/open-week` gain a new dependency on `~/.cache/person-intelligence/coaching_actions.json` — must degrade gracefully when the file is absent (e.g., first-time user, biweekly sweep never run).
- **Error propagation:** Each per-person sweep can fail independently without breaking the whole run. The orchestrator collects errors and surfaces them in the digest's "Errors during sweep" section. Schedule failures should not silently retry — the digest is the failure surface.
- **State lifecycle risks:** `last-synthesized` frontmatter is the cadence clock — must be updated atomically after each successful synthesis. If a synthesis fails mid-write, the frontmatter should not advance (existing scripts already use this pattern; verify it holds for the new flow).
- **API surface parity:** No other skills consume person-intelligence outputs today, but `/open-day` and `/open-week` are gaining new links to the pulse doc. Confirm those skills' SKILL.md updates are deployed before the first scheduled run.
- **Integration coverage:** Slack and Gmail MCPs require per-user auth. If a user installs the personal toolkit without connecting Slack, the skill must degrade gracefully (already designed for this — see Unit 2 fail-soft pattern).

## Risks & Dependencies

- **Risk: scheduled runs feel intrusive.** Mitigation: data-only auto-writes, narrative changes go into the digest for review. Same pattern that worked for the existing biweekly health check.
- **Risk: Claude API token spend grows linearly with team size.** Mitigation: incremental Fathom fetch (only new meetings); single cross-relational synthesis call rather than per-person digests; measure on first run, switch digest to Haiku if needed.
- **Risk: org-chart.json goes stale and a new direct report is missed for an entire biweekly cycle.** Mitigation: freshness check warns at 7 days; the digest's "Cadence integrity" section flags any person whose org-chart record is missing.
- **Risk: Slack/Gmail MCPs return surprisingly large or noisy data.** Mitigation: 14-day window, participant-only scope, no keyword sweeps. If signal-to-noise is bad, tune the scoping doc.
- **Risk: backfill writes look like fake data and erode trust in the chart.** Mitigation: `⏪` annotation per backfilled row + bottom-of-profile journal entry making provenance explicit. No silent fabrication.
- **Risk: a fork of the personal toolkit diverges and breaks the org-chart read path.** Mitigation: skill reads from the builder toolkit's plugin-installed path first, with a clear error message if missing. Forks that don't have the builder toolkit installed get a single-source error rather than a partially-working system.
- **Risk: the Slack/Gmail MCP scope feels too invasive when the data shows up in a profile.** Mitigation: ingest-scoping.md is published in the skill so users (and forks) can audit and adjust before running. Add an opt-out per source via env var (`SKIP_SLACK_INGEST=1`, `SKIP_GMAIL_INGEST=1`).
- **Dependency: builder toolkit must be installed and `org-chart.json` must be current.** This is already a soft dependency in the existing skill (line 165). Make it explicit in the install flow.

## Phased Delivery

### Phase 1: Foundations (Units 1–2)
Identity resolution, org-chart-driven relationship enumeration, multi-source ingest scoping. Ship without changing any existing skill behavior so the existing manual synthesis flow keeps working. Verify by running `list_relationships.py` from CLI and inspecting the output for Kevin.

### Phase 2: Manager Coaching Synthesizer (Unit 4 + profile-template replacement)
Apply `/full-shape` dimensional discovery to the synthesizer. For direct reports add `## What [Name] Needs to Thrive` (manager's private coaching) + `## How I Work with [Name]` (manager self-disclosure, optionally shareable). For the user's manager add `## My Stance: [emotions]` + `## How I Can Work More Effectively with [Name]` modeled on the Gary 2026-05-16 pattern. Preserve human-authored sections during re-synthesis. Test by manually re-synthesizing one direct report (Adam Stone) and one upward relationship (Gary) and reviewing both with Kevin before any backfill or schedule.

### Phase 3: Orchestration + Digest (Units 3 + 5)
Wire the biweekly sweep orchestrator and the team-pulse digest. Run manually on Kevin's data, review the digest, iterate on the format before scheduling.

### Phase 4: Backfill (Unit 7)
Run backfill in dry-run mode first; Kevin reviews the diffs; then real run. This is the most-likely-to-feel-wrong step, so iterate carefully.

### Phase 5: Daily/Weekly Activation (Unit 8)
Wire `/open-day` and `/open-week` to surface coaching actions tied to scheduled people. This is where the system goes from "useful when I read profiles" to "useful in my actual day." Verify by running /open-day on a day with multiple people-meetings.

### Phase 6: Schedule + Generalization (Units 6 + 9)
Register the schedule for Kevin; document the install flow; publish the release note. Other NSLS users opt in via `/personal-setup`.

## Documentation Plan

- **SKILL.md** gets a new "Mode: Biweekly Sweep" section, new "Scheduling" section, new "Ingest Sources" section, and the Known People Registry section is removed (replaced by org-chart auto-discovery).
- **CLAUDE.md (personal toolkit)** gets a one-line entry in the skills table noting the biweekly-sweep mode.
- **References:** new `manager-coaching-frame.md` (downward — Thrive + How I Work sections), `manager-relationship-frame.md` (upward — Stance + How I Can Work More Effectively), `dimensional-discovery-frame.md` (always-on /full-shape instruction), `team-pulse-template.md`, `ingest-scoping.md`. The stale `profile-template.md` gets replaced.
- **Examples folder:** create `references/examples/` with one anonymized example per relationship type (one direct-report profile excerpt, one manager profile excerpt, one peer profile excerpt). These serve as Kevin-specific reference content but live in `examples/` so forks know they're examples, not the template.
- **Release note** at `updates/2026-05-XX-person-intelligence-v2.md` documents the change for forks following the existing release-note pattern.
- **Memory:** add a project memory referencing this plan and the new biweekly cadence so future sessions know to check the pulse doc.

## Operational / Rollout Notes

- **Rollout for Kevin:** Phases 1–5 sequentially over the next session. Backfill is the highest-touch step — present diffs before any write.
- **Rollout for other NSLS users:** they opt in via `/personal-setup` after the plugin auto-updates. The release note explains the new mode and how to enable.
- **Monitoring:** the team-pulse doc itself is the monitor. If a sweep fails, the doc surfaces it under "Errors during sweep". If a user wants more, they can grep `~/.cache/person-intelligence/` for manifests.
- **Backout:** to disable, pause the schedule via `/schedule pause`. To fully remove, delete the schedule entry and the new scripts; the existing manual synthesis flow continues unchanged.

## Sources & References

- **Current skill code:** `~/nsls-skills/nsls-personal-toolkit/skills/person-intelligence/` (SKILL.md, scripts/, references/)
- **Org chart source:** `~/nsls-skills/nsls-builder-toolkit/_shared/context/org-chart.json`
- **Builder toolkit org sync:** `~/nsls-skills/nsls-builder-toolkit/_shared/scripts/sync_org_context.py`
- **Gold-standard profile:** `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/KP/30-people/Gary Tuerack.md`
- **Memory references:** `~/.claude/projects/-Users-k/memory/person-intelligence-skill.md`, `feedback_close_day_suggestions.md`, `user_coaching_patterns.md`
- **Schedule mechanism:** `/schedule` skill (remote routine)
- **Existing release-note pattern:** `~/nsls-skills/nsls-personal-toolkit/updates/`
