# Topic Mapping — Prompt and Examples

Each candidate from extraction is mapped to one or more KB topic files. Mapping picks a primary topic, optionally a secondary, and a section (`current_state` | `key_decisions` | `open_questions`).

## Mapping prompt

```
You are mapping a candidate KB entry to topic files in the NSLS Knowledge Base.

INPUT:
Candidate: {"kind": "...", "text": "...", "speaker": "...", "meeting_title": "..."}

KB topic index (slug → title + parent + brief snapshot of current_state):
{paste topic_index_summary from /tmp/harvest-meeting-ctx/topics.json}

OUTPUT FORMAT: JSON object, no markdown fences.
{"primary_topic": "<slug>" | "NEW",
 "secondary_topics": ["<slug>", ...],
 "section": "current_state" | "key_decisions" | "open_questions",
 "confidence": <0.0-1.0>,
 "suggested_new": {"slug": "<lowercase-hyphenated>",
                   "parent": "<existing-slug>",
                   "type": "kpi" | "theme" | "channel" | "l2" | "l3" | "rubric"}
                  // only if primary_topic == "NEW"
}

RULES:
- Choose section by candidate kind:
  - decision → key_decisions
  - project_definition → key_decisions (for the new project) OR current_state (if it's
    a redefinition of an existing project's scope)
  - state_change → current_state (the body summary) — REPLACE existing content,
    don't append
- For state_change candidates, look at the current `current_state` of the target topic
  and propose a replacement that captures both the new state and necessary context.
- Confidence < 0.7 → flag for human disambiguation in approval step.
- If no existing topic fits well, return primary_topic: "NEW" with a suggested slug
  matching lowercase-hyphenated convention.
- secondary_topics is optional; use sparingly when a candidate genuinely belongs
  on multiple topics (rare).
```

## Worked examples

### Example 1: Decision → existing topic

**Candidate:** `{"kind": "decision", "text": "Pausing B2B campaign through July...", ...}`

**Expected output:**
```json
{"primary_topic": "b2b-conversion",
 "secondary_topics": [],
 "section": "key_decisions",
 "confidence": 0.95}
```

### Example 2: State change → REPLACE current_state

**Candidate:** `{"kind": "state_change", "text": "Chapter health framework expanded from 3 tiers to 4...", ...}`

**Existing chapter-health.md current_state:** "Chapters classified into 3 health tiers (green/yellow/red) based on activity and renewal metrics."

**Expected output:**
```json
{"primary_topic": "chapter-health",
 "secondary_topics": [],
 "section": "current_state",
 "confidence": 0.95}
```

### Example 3: Project definition → NEW topic

**Candidate:** `{"kind": "project_definition", "text": "90-day check-in program: Red owns instrumentation, Heather owns HR side, Q3 launch", ...}`

No existing topic exists for "new-hire onboarding" or "90-day check-in". Closest topics: `people-hr`, `employees`. Neither is project-specific.

**Expected output:**
```json
{"primary_topic": "NEW",
 "secondary_topics": [],
 "section": "key_decisions",
 "confidence": 0.85,
 "suggested_new": {"slug": "ninety-day-check-in-program",
                   "parent": "people-hr",
                   "type": "l3"}}
```

### Example 4: Low confidence → flag for human

**Candidate:** `{"kind": "decision", "text": "Approved the new vendor for analytics tooling", ...}`

Could fit `data-analytics`, `data-infrastructure`, or `tech-debt-modernization`. Genuinely ambiguous.

**Expected output:**
```json
{"primary_topic": "data-analytics",
 "secondary_topics": ["data-infrastructure"],
 "section": "key_decisions",
 "confidence": 0.55}
```

Approval step will surface this candidate with a "?" flag and let the user pick the topic.
