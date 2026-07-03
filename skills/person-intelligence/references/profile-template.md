# Profile template — current layout

This template documents the structure the synthesizer produces. The Gary Tuerack profile is the gold-standard reference for layout, voice, and depth.

## Frontmatter

```yaml
---
type: person
tags: [leadership, slt|board|health-good|health-watch|...]  # Kevin/user curated
role: "Founder & Interim CEO"                                # Kevin's editorial role description
org: NSLS
last-synthesized: YYYY-MM-DD                                 # advanced by synthesizer only when content updated
sources: [fathom-1on1s, airtable-slt, airtable-people-ops, slack, gmail, existing-profile]
meetings_attended: N                                          # computed from Fathom + SLT data
health: great|good|watch|attention|departed                  # health rollup
health_score: 3.33                                            # 1-4 scale rollup
health_last_assessed: YYYY-MM-DD
department: Executive                                         # synced from org-chart.json
email: foo@nsls.org                                           # synced
slack: U0XXXXXX                                               # synced
title: "Senior Director, X"                                   # synced
manager: "Manager Name"                                       # synced
---
```

Sync-controlled fields (from `sync_obsidian_frontmatter.py`): `email`, `slack`, `department`, `title`, `manager`.
Synthesizer-controlled: `last-synthesized`, `sources`, `meetings_attended`.
User-curated: `tags`, `role`, `health`, `health_score`, `health_last_assessed`.

## Body structure

The full ordering, with conditional sections by relationship type:

```markdown
# [health-emoji] [Name]

> SLT coaching: [[10-slt/members/...]]    # if SLT
> Board profile: [[20-projects/board-intelligence/members/...]]   # if board

— Person Intelligence Profile

**Role:** ...
**Relationship to [Operating User]:** Direct report | Direct superior | Peer | Key collaborator
**Data span:** N recorded meetings, [date range]

---

## Core Identity & Self-Concept

[How they frame themselves and the work. Direct quotes where available.]

---

## Leadership Style

[2-5 short subsections with bold-lead phrases:]
**Pattern name.** [One sentence explaining + evidence.]

---

## Mental Models (Recurring)

| Model | How They Use It |
|---|---|
| **Model name** | One-line description with evidence |

---

## Strategic Priorities (Active as of [period])

[3-7 priorities, each as bold-lead paragraph with specific evidence and quotes.]

---

## What Energizes Them

- [Specific energizing thing, grounded in observable evidence]

## What Concerns Them

- [Specific concern, with quote if available]

---

## How They Manage Up / Down / Laterally

**To [person/role]:** [paragraph with evidence]
**To the team:** [paragraph]
**Laterally:** [paragraph]

---

## Personal Practices & Interests

- [Observed practices, often non-work — meditation, hobbies, etc.]

---

## Communication Patterns

- **Pattern name:** [behavior + evidence]

---

## Key Relationships (Their Lens)

| Person | Their Read |
|---|---|
| **Name** | One-paragraph synthesis |

---

## Quotes That Capture Them

> *"Direct quote."* — context

---

[CONDITIONAL SECTIONS BY relationship_type]

### If direct_report:

## What [Name] Needs to Thrive
### Strengths to invest in
### Friction to address
### Growth edges
### Conditions for peak performance

## How I Work with [Name]
### How I communicate best
### What helps me help you
### What trips me up
### How we should handle disagreement

### If manager (upward):

## My Stance: [emotion], [emotion], [emotion]
[paragraphs per emotion]
### How I feel about the relationship
### The arc
### How it shows up day to day
### Guardrail (if warranted)

## How I Can Work More Effectively with [Name]
### What they respond best to
### What surprises or destabilizes them
### Where I have latitude
### Where I need to bring them in early

### If peer or key_relationship:

## Working Pattern
[Single paragraph or short bulleted summary of how they collaborate.]

---

## Projects Together

- [[20-projects/.../...]] — context

---

## Personal

- **Interests**: ...
- **Family**: ...
- **Last updated**: YYYY-MM-DD

---

## Coaching Goals

### Active: [Goal title]
status: active | created: YYYY-MM-DD | dimension: [health dimension]

**Why**: ...
**Actions**:
- [ ] action item
**Evidence**:
- YYYY-MM-DD: observation

### Completed: [Goal title]
status: completed | ...

---

## Relationship Health

| Date         | State  | Align | Trust | Collab | Tension | Engage | Influence | Note     |
|--------------|--------|-------|-------|--------|---------|--------|-----------|----------|
| YYYY-MM-DD   | 🟢 N.N | 🟢   | 🟢   | 🟢    | 🟢     | 🟢    | 🟢       | Assessed |
| YYYY-MM-DD ⚪ | ⚪ N.N | 🟩   | 🟩   | 🟩    | 🟩     | 🟩    | 🟩       | Backfilled |

### YYYY-MM-DD — [emoji] [Label]

[Free-form journal entry — why the score is what it is.]
```

## Section ordering invariant

The synthesizer follows this order. Sections may be omitted if the data doesn't support them, but the relative order is fixed.

## Human-authored content

Any section not in the template above is treated as **human-authored** and preserved. The synthesizer reads it, may surface proposed updates in the digest, but never overwrites. Example: Kevin manually added a "## Kevin's Stance: Respect, Protect, Resent" section to Gary's profile on 2026-05-16. The next synthesizer run reads it, proposes updates if the recent data suggests refinements, and keeps the original until Kevin reviews.
