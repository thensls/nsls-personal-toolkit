# Spec: Stale-Asks Sweep (weekly unanswered-inbound pass)

**Status:** proposed · **Author:** Kevin + CC · **Date:** 2026-05-27
**Targets:** `/open-week` (primary) — optionally `/close-week`

## Problem

The daily incoming-asks scan added in PR #12 (`close-day` step `1e-pre`, `open-day` equivalent) is scoped to a single day (`on:YYYY-MM-DD`). It only catches asks that arrive **today**. Anything someone asked you earlier that you never answered silently falls off — it's never in "today" again.

Concrete miss (2026-05-26 close): Lillian's contractor-audit request had been pending since **May 7** (re-pinged May 21). The daily scan correctly returned nothing for it because it wasn't a 5/26 message — it took a manual catch. Aged asks are exactly the ones that erode trust, and they're the ones the daily scan structurally cannot see.

## Goal

A **weekly** pass that surfaces inbound asks from the last N days (default **14**) where you never substantively replied — so aged commitments resurface at week-start instead of rotting.

Weekly, not daily: it does per-thread reads (heavier), and the value is in catching multi-day drift, which a weekly cadence captures fine.

## Placement

Add to **`/open-week`** as a step right after the Asana-backlog triage. Open-week already turns backlog into the week's priorities, so stale asks land where they get scheduled. (Mirror the cross-reference logic from `close-day` `1e-pre`.)

## Query design

```
# N = 14; AFTER = today − N days
slack_search_public_and_private(
  query="to:<@$SLACK_USER_ID> after:AFTER",
  sort="timestamp",
  sort_dir="asc",
  limit=40,
  include_context=true
)
```

`to:<@me>` matches DMs, group DMs, and direct @mentions. Broad channel asks with no @mention are out of scope (acceptable — those aren't personal asks).

For each candidate thread:
1. `slack_read_thread` (or `slack_read_channel` limit=5) to get the tail.
2. Classify the inbound message as an **ask** if: ends in `?`, OR contains request language ("can you", "could you", "would you", "please", "need", "follow up", "waiting on", "by [date]", "let me know").
3. Determine **answered?**: is there a substantive message **from you** in the thread *after* the ask's timestamp? A reaction or "ok/thanks" does **not** count as substantive for a request that needs an action/decision.

## Filters & dedup

- Exclude bots: SLT EA Bot (`U0ADE2TMZMM`), Signal, any `[BOT]`.
- Exclude threads where your post-ask reply delivered the thing (link, doc, decision).
- **Dedup** against: open Asana tasks (name/snippet match) and anything already surfaced by today's `close-day` `1e-pre`.
- Skip purely social ("hope your weekend was lovely").

## Aging buckets & output

Bucket by age of the **oldest unanswered ask** in the thread:

| Age | Flag |
|---|---|
| 3–7 days | 🟡 |
| 8–14 days | 🟠 |
| >14 days | 🔴 |

Output section in the open-week note:

```markdown
### Stale asks (unanswered, last 14 days)
- 🔴 [20d] Lillian Collazo (DM): "complete the contractor tracker + reply" — [permalink]
- 🟠 [9d]  Name (#channel): "can you review X?" — [permalink]
```

Then offer to create Asana tasks:
- 🔴 / external / HR / explicit-commitment → **P1**
- everything else → **P2**

Description carries the Slack permalink + first-asked date.

## Limits

- Cap at **10** entries; beyond that, a "and N more" line — let Kevin triage.
- One `to:` search + ≤40 thread reads. Weekly cadence keeps cost bounded.

## Open questions

1. `after:` vs explicit `after:..before:` window — `after:` alone is simpler and fine for a 14-day look-back.
2. Should `/close-week` also run a lighter version (just the 🔴 >14d bucket) as a Friday backstop? Default: no — avoid double-surfacing; open-week owns it.
3. Make N configurable via builder profile (`stale_asks_lookback_days`, default 14)?

## Implementation notes

- Lives behind `data_sources.slack: true`.
- Reuse `$SLACK_USER_ID` from `.env` (same var PR #12 introduced).
- Ship to `nsls-personal-toolkit` repo via PR; then sync into Kevin's local `~/.claude/skills/open-week` (see [close-day fork drift](../../../.claude/projects/-Users-k/memory/project_close_day_skill_drift.md) — the local copies are hand-maintained forks).
