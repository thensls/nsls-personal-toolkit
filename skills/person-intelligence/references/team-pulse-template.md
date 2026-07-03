# Team-pulse digest template

The biweekly sweep produces one of these per cycle, written to:
`$OBSIDIAN_VAULT_PATH/30-people/_pulse/YYYY-MM-DD-team-pulse.md`

The structure is below. The synthesizer fills each section from the manifest + each tracked profile's health frontmatter + recent journal entries.

```markdown
---
type: team-pulse
date: YYYY-MM-DD
operating_user: kprentiss@nsls.org
relationships_tracked: 11
---

# Team Pulse — YYYY-MM-DD

> Biweekly digest. Review and act on the proposed coaching updates below
> — they don't get auto-written to profiles.

## Cadence Integrity

Relationships and when each was last synthesized. Anyone over 21 days gets a 🟡 flag.

| Person | Last Synthesized | Status |
|---|---|---|
| Adam Stone | 2026-05-17 | ✅ |
| Ashleigh Smith | 2026-04-12 | 🟡 (34 days) |

## Drift

People whose health score dropped at least 1 point since the prior assessment.
One line per person with the one-line "why" from the digest reasoning.

- **Adam Stone** — 💚 → 🟢. Two cancelled 1:1s in a row; communication going async-only.

## Thrive

People whose health score improved at least 1 point OR sustained 💚 with strong engagement signals.

- **Lauren Prentiss** — 🟢 → 💚. Opened the last three sprint reviews and set agendas without prompting.

## Attention

Anyone at 🟡 or 🔴, sorted by trend (deteriorating > stable > improving).

- **Ashleigh Smith** — 🟡 stable. The legacy chapter-management split hasn't been named directly in two cycles.

## Manager Mode Review

A single prompt for the operating user, drawn from time allocation across the team.

> You spent ~4 hours with Adam (high-tension, recovering) last period and 0 hours
> with Ashleigh (stable, but the unaddressed structural question is starting to
> compound). Worth rebalancing the next two weeks?

## Proposed Coaching Updates

Per person, the AI's proposed changes to the active coaching goals.
**These do NOT get auto-written.** Accept / edit / reject each one.

### Adam Stone
- Add evidence to "Build sprint cadence": he led the May 12 review unprompted.
- Propose new action: "Pair Adam with David on the agent-driven insight project."

### Gary Tuerack (managing up)
- Add evidence to "Clean up resentment in real time": no friction this cycle, but
  the SLT goal-setting conversation has a gotcha-shaped pattern worth pre-managing.

## Errors During Sweep

If anything failed, it appears here. Otherwise this section is omitted.

- Fathom fetch timed out for Chris Higbee (will retry next cycle)
```

## Generation rules

- Sections only appear if data supports them. "Drift" / "Thrive" / "Attention" / "Errors" are omitted when empty.
- "Cadence Integrity" always renders.
- "Manager Mode Review" only renders when time-allocation skew is meaningful (>2x imbalance between high-attention and zero-attention direct reports).
- Voice: terse, plain, declarative. No corporate-speak.
- Proposed coaching updates are written as suggestions, not commands.
