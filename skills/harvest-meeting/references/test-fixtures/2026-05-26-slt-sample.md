# Synthetic SLT meeting — for harvest-meeting self-verification

Meeting metadata (mimics Fathom output shape):
```json
{
  "recording_id": "synthetic-2026-05-26",
  "title": "SLT Standing — synthetic fixture for harvest testing",
  "url": "https://fathom.video/share/SYNTHETIC",
  "meeting_date": "2026-05-26",
  "attendees": ["Kevin Prentiss", "Ashleigh Smith", "Adam Stone"]
}
```

## Transcript

[00:30] Kevin: "OK let's start. Adam, where are we with B2B?"
[00:35] Adam: "I'm proposing we pause the B2B campaign through July. Chapter renewals need our attention."
[01:14] Kevin: "Agreed. Pause through July. Adam owns partner communication."
[01:30] Adam: "Will do this week."

[15:22] Ashleigh: "Chapter health used to be 3 tiers. Last sprint we moved to 4 — green, yellow, orange, red. Orange is the new early-warning band."
[15:50] Kevin: "Good. Update the framework doc and chapter dashboards."

[22:05] Heather (joined late): "Also wanted to flag — Q1 net margin was 14.2%, up from 11.8% in Q4. Strongest in two years."
[22:30] Kevin: "Great. Let's hold that detail for the board, not the company-wide update."

[30:00] Adam: "One more — let's start a 90-day check-in program. Red owns instrumentation. Heather owns the HR side. Q3 launch."
[30:45] Kevin: "Yes. Good. Make it real."

## Expected harvest output (for verification)

Should produce 4 candidates, 3 KB-eligible, 1 rubric-dropped:

| # | Candidate | Topic | Section | Rubric |
|---|---|---|---|---|
| 1 | Pausing B2B campaign through July | b2b-conversion | key_decisions | PASS |
| 2 | Chapter health 3→4 tiers (added orange) | chapter-health | current_state | PASS |
| 3 | 90-day check-in program: Red+Heather, Q3 launch | NEW: ninety-day-check-in-program | key_decisions | PASS |
| 4 | Q1 net margin 14.2% (up from 11.8%) | finance-operations | — | DROP_UNSAFE (profit) |
