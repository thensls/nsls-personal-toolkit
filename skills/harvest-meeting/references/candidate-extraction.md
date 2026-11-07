# Candidate Extraction — Prompt and Examples

The extraction step asks Claude to identify moments in a meeting that are KB-worthy: **decisions**, **project definitions**, or **state changes**.

## Pre-filter via the REJECT list

Before extraction, paste the **REJECT** section of `references/sorting-guidelines.md` so the model
doesn't surface candidates that are guaranteed to be rejected. Only that list is withheld here:
business facts (deal terms, software vendor pricing, security gaps, open legal questions) are extracted
and go through the sort like anything else.

## Extraction prompt

```
You are extracting candidate KB entries from an SLT meeting at NSLS (a leadership honor society).

OUTPUT FORMAT: one JSON object. No prose, no markdown fences.
{"candidates": [ ... ], "withheld": [{"category": "<label>", "gist": "<≤10 words>", "fathom_timestamp_sec": <int>}, ...]}
"withheld" lists the moments you left out because they are on the REJECT list, using these
labels only: individual pay, people decision, private life, profit and cash, not yet announced,
access secrets, member data, legal claim, contractor terms. "gist" is a vague pointer the builder, who was in the meeting, will
recognise ("Kevin's private meeting-prep skill content"), never the sensitive detail itself.
Each candidate: {"kind": "decision" | "project_definition" | "state_change" | "how_we_work" | "open_issue",
               "text": "<one-sentence summary>",
               "fathom_timestamp_sec": <integer>,
               "speaker": "<name or 'unknown'>",
               "confidence": <0.0-1.0>}

KINDS:
- decision: an explicit decision made in the meeting. Phrasing like "we decided X",
  "X is approved", "we're going with X", "X is paused/cancelled/rejected".
- project_definition: a project, initiative, or workstream is being scoped or
  introduced. Includes owner if mentioned. Phrasing like "Project X exists",
  "Y owns this", "we're kicking off Z".
- open_issue: a problem or gap the meeting found that has no decision yet, which colleagues
  should know about ("the collector records private skill names; Kevin is checking"). Files
  under the topic's Open Questions.
- how_we_work: a standing practice stated as current fact by someone who runs it, that a
  colleague elsewhere would look up ("partner onboarding takes about six weeks", "legal turns
  data-sharing agreements around in two to three weeks"). Not one-off logistics.
- state_change: a material change since the topic's last KB update. Numeric
  shifts ("conversion rate moved from 12% to 18%"), structural shifts
  ("now using 4 tiers instead of 3"), program changes ("SARs grants now
  vest over 4 years not 2").

DO NOT extract:
- Status updates without a decision ("chapter retention has been declining")
- Plans-in-discussion or hypothetical proposals ("we should probably look at pricing")
- Context, observations, or opinions ("Dana raised a good point")
- Logistics and scheduling (offsites, meeting times, expense tools, holiday closures)
- Anything in the REJECT list: [paste the REJECT section of references/sorting-guidelines.md]

For each candidate, provide a 1-sentence summary in the `text` field — not a full
quote. The Fathom transcript URL + timestamp serves as the verbatim source.

INPUT:
Meeting title: <title>
Meeting date: <YYYY-MM-DD>
Attendees: <list>
Summary: <Fathom summary>
Transcript: <full transcript>
```

## Worked examples

Each example shows the `candidates` array only; the real output wraps it in
`{"candidates": [...], "withheld": [...]}`, e.g.
`{"candidates": [{"kind": "decision", "text": "...", "fathom_timestamp_sec": 634, "speaker": "...", "confidence": 0.95}], "withheld": [{"category": "individual pay", "gist": "a raise discussed for one person", "fathom_timestamp_sec": 812}]}`.

### Example 1: A clear decision

**Transcript excerpt:**
> Adam (10:34): "...so I'm proposing we pause the B2B campaign through July to focus on the chapter renewals."
> Marcus (10:35): "Agreed, let's pause through July. Adam, you'll communicate to the partner contacts?"
> Adam: "Yes, will do this week."

**Expected output:**
```json
[{"kind": "decision",
  "text": "Pausing B2B campaign through July to focus on chapter renewals",
  "fathom_timestamp_sec": 634,
  "speaker": "Marcus Vance",
  "confidence": 0.95}]
```

### Example 2: A project definition

**Transcript excerpt:**
> Heather (15:22): "I want to formalize the new-hire 90-day check-in program. Robin will own the data instrumentation; I'll own the HR side. We're scoping for a Q3 launch."

**Expected output:**
```json
[{"kind": "project_definition",
  "text": "90-day check-in program: Robin owns instrumentation, Heather owns HR side, Q3 2026 launch target",
  "fathom_timestamp_sec": 922,
  "speaker": "Heather Voss",
  "confidence": 0.9}]
```

### Example 3: A state change

**Transcript excerpt:**
> Priya (22:10): "Chapter health used to be 3 tiers — green, yellow, red. We expanded to 4 last sprint: green, yellow, orange, red. Orange is the new 'needs intervention soon but not critical yet' band."

**Expected output:**
```json
[{"kind": "state_change",
  "text": "Chapter health framework expanded from 3 tiers to 4 (added 'orange' for early intervention)",
  "fathom_timestamp_sec": 1330,
  "speaker": "Priya Nakamura",
  "confidence": 0.92}]
```

### Example 4: SHOULD NOT be extracted

**Transcript excerpt:**
> Marcus (08:15): "I think we have a real problem with chapter retention. We should look at this seriously next month."

This is intent without decision. NOT a candidate. Empty result.

### Example 5: Sensitive — pre-filter drops it

**Transcript excerpt:**
> Devan (45:01): "Q1 net margin was 14.2%, up from 11.8% in Q4. Best in two years."

This is a profit number, which is on the REJECT list. Pre-filter drops it without proposing. Empty result.
