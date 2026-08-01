# Categorization Memos + Coding → Ramp — Design

**Date:** 2026-08-01
**Status:** Approved, ready for implementation planning
**Skill:** `nsls-personal-toolkit/skills/memos/`, invoked as `/memos`
**Companion:** `docs/specs/2026-08-01-receipts-to-ramp-design.md` (Phase 1, shares infrastructure)

## Problem

Ramp transactions need memos, and the memo exists so **accounting can code the charge
to a budget**. Two classes with very different difficulty:

1. **Recurring** — Anthropic, Macroscope, Clay, GoDaddy. The right coding is whatever it
   was last time. Deterministic.
2. **One-off** — a restaurant, an Uber, a hotel. The transaction carries no fact about
   *why*: "$83, Ruth's Chris, 2026-07-24" says nothing about which trip or which budget.
   The context has to come from somewhere else.

## Findings that shaped the design

Verified against `https://docs.ramp.com/openapi/developer-api.json` on 2026-08-01.

```
GET  /developer/v1/transactions?requires_memo=true    scope transactions:read
     "Filters for transactions which require a memo, but do not have one."
     ?include_merchant_data=true → Transaction.merchant_location {city,state,country,postal_code}
POST /developer/v1/memos/{transaction_id}             scope memos:write
     { memo: string, is_memo_recurring: boolean }
GET  /developer/v1/accounting/fields                  scope accounting:read
GET  /developer/v1/accounting/field-options           scope accounting:read
POST /developer/v1/accounting/codings                 scope accounting:write
     { object_id, object_type, accounting_coding_selections[] }
GET  /developer/v1/receipts?include_ocr_data=true     scope receipts:read
```

Three consequences:

- **The queue is free.** `requires_memo=true` returns exactly the transactions needing a
  memo and lacking one. No set difference, unlike Phase 1's receipts queue.
- **Ramp already models the recurring/one-off split** via `is_memo_recurring`.
- **`merchant_location` is on the transaction itself.** Trip geography costs no extra
  scope and no extra auth — it comes from the same objects being coded.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Audience | Accounting, for coding | Correct budget assignment matters more than prose |
| Authority | Propose memo + coding; human approves | Coding touches the books; proposal is fully useful without the risk |
| Trip source | Spend geography leads, calendar names | Geography is ground truth for where/when; calendar supplies why |
| Context sources | Trip span → receipt OCR → Obsidian daily note → calendar events | Ordered by how much each knows about *why* |
| Trigger | On-demand `/memos`, dry run by default | Same posture as `/receipts` |

**Why coding and not memo-only.** If the memo exists so a human can look up the right
budget, and Ramp will hand us the field list and allowed values directly, then a
memo-only tool sends a message asking someone to do a lookup the agent could have done.
Proposing the coding also makes the output *verifiable* — an invalid option is rejected
by Ramp, whereas a vague memo fails silently at close.

## Architecture

Shares `ramp_client.py` and `queue.py` pagination with Phase 1, unchanged.

```
┌─ queue.py (shared) ─┐  GET /transactions?requires_memo=true
│                     │       &include_merchant_data=true
└─────────────────────┘ → [{txn_id, merchant, merchant_location, amount_cents, date}]
         ↓
┌─ trips.py ──────────┐  Signal A: cluster merchant_location by city
│ span index          │  Signal B: name each span from calendar
└─────────────────────┘ → [{start, end, city, label, confidence, evidence}]
         ↓
┌─ context.py ────────┐  Resolve one-off charges down the ladder
└─────────────────────┘ → {trip?, ocr_items?, daily_note?, calendar_events?}
         ↓
┌─ classify.py ───────┐  RECURRING | ONE_OFF; pure, no I/O
└─────────────────────┘
         ↓
┌─ fields.py ─────────┐  GET /accounting/fields + /field-options
│ validate proposals  │  reject any option not in the real enum
└─────────────────────┘
         ↓
┌─ report.py ─────────┐  grouped by decision cost; dry run by default
│ + post.py           │  --send → POST /memos/{id} then /accounting/codings
└─────────────────────┘
```

## Trip detection

### Signal A — spend geography (where and when)

Cluster transactions by `merchant_location.city`. Consecutive days of charges in a
non-home city form a candidate span. This is ground truth: you cannot buy coffee in
Asheville without being in Asheville.

**Home is derived, never declared.** Home city = the modal `merchant_location.city` over
a trailing 30-day window, recomputed per run.

> This is not a stylistic choice. Kevin is in Wisconsin on Central time through
> 2026-08-20 while his home zone is Mountain. A hardcoded home city would classify the
> entire Wisconsin stay as one enormous trip and code months of ordinary spend as travel.
> A trailing modal baseline moves when he moves, absorbs a relocation automatically, and
> still leaves a genuine 4-day trip standing out against it.

Gap tolerance: a single day with no charges does not split a span (you don't always spend
every day). Two or more consecutive charge-free days do.

### Signal B — calendar (what and why)

For each candidate span, find overlapping calendar events and take the trip label from
them, preferring in order: a multi-day all-day event, a flight/hotel event, then the
most-attended meeting in the span.

### Join and confidence

| Grade | Condition | Treatment |
|---|---|---|
| `HIGH` | Geographic span **and** an overlapping calendar event | Named span; propose coding for every charge inside |
| `MEDIUM` | Geographic span, no calendar match | Coded as travel, unnamed, surfaced for a name |
| — | Calendar event, no charges | Not a trip. Nothing to code |

Every span records which signals produced it. A `HIGH` span and a `MEDIUM` span are not
equally trustworthy and the report must never collapse them.

## Context ladder — one-off charges

First hit wins. Ordered by how much the source knows about *why*, not by ease of access:

```
1. Date inside a trip span      → trip label, city, dates       (strongest)
2. Receipt OCR line items       → what was actually bought
3. Obsidian daily note          → what you were doing that day
4. Calendar events that date    → who you met
5. nothing                      → UNRESOLVED, listed for you
```

Receipt OCR ranks below the trip span deliberately: it reliably reports two entrées and a
bottle of wine, which is a fact accounting already has from the amount, and never the
fact they need.

## Classification

| Class | Test | Memo | Coding |
|---|---|---|---|
| `RECURRING` | Vendor seen ≥3× with one consistent prior coding | Template: vendor + period | Repeat the prior coding, `is_memo_recurring=true` |
| `ONE_OFF` | Everything else | Built from resolved context | Proposed from trip/context, `is_memo_recurring=false` |

A vendor with ≥3 prior transactions but **inconsistent** prior codings is `ONE_OFF`, not
recurring — disagreement in the history is information, and picking the majority would
destroy it.

## Coding validation

`fields.py` fetches the real field list and allowed options per field. Every proposed
selection is checked against that enum before it is offered.

**An option not present in the enum is a hard error, never a silent drop.** Posting a
partial coding that omits a required field produces a transaction that looks coded and
isn't — the failure surfaces at close, weeks later, to someone who can't diagnose it.

## Report and approval

Nothing posts without `--send`. The report groups by decision cost:

```
## Auto — recurring, prior coding repeated              12 charges
## Trip: SLT offsite Asheville  Jul 8–11   HIGH          6 charges → Travel:Leadership
## Trip: unnamed, Asheville     Jul 8–11   MEDIUM        2 charges → needs a name
## Needs your call                                       3 charges
## Home baseline: Madison WI (modal, trailing 30d)
```

The home baseline is printed every run. It is derived, it can be wrong, and a wrong
baseline silently mis-grades every trip — so it must be visible, not buried.

Memo prose names the trip and the budget in words alongside the machine coding, so the
two can be checked against each other. If the prose and the enum disagree, that is
visible on one line.

## Failure handling

- **Ramp 401 → hard stop.** Same as Phase 1.
- **Calendar unavailable** (Google auth expired — it was expired on 2026-08-01) →
  geography still runs. Every span drops to `MEDIUM` and the report emits
  `SOURCE CALENDAR: SKIPPED (auth expired)` on its own line. The run is degraded, not
  silently narrowed.
- **Obsidian vault missing** → that rung is skipped, announced the same way.
- **Coding POST fails** → memo is *not* posted either. A memo without its coding is the
  worst outcome: it clears Ramp's nag, so nobody chases it, and the coding never lands.
  Memo and coding succeed together or neither is written.

## Testing

- **`trips.py` fixtures from real geography:** a HIGH span (charges + calendar), a MEDIUM
  span (charges only), a single-day gap that must *not* split a span, a two-day gap that
  must, and a relocation that must move the home baseline rather than register as a trip.
- **Non-vacuous assertions:** the relocation test fails if the whole stay is returned as
  a trip; the MEDIUM test fails if a span is silently graded HIGH.
- **`fields.py`:** an invalid option must raise, and the test fails if any POST is
  attempted.
- **`post.py`:** a failing coding POST must leave the memo unposted.
- **Dry run:** asserts zero POSTs of any kind.

## Dependencies

- Phase 1 (`/receipts`) ships `ramp_client.py` and `queue.py`. This plan reuses both.
- Additional Ramp scopes beyond Phase 1: `memos:write`, `accounting:read`,
  `accounting:write`.
- Google Calendar auth must be re-authorized — it was expired on 2026-08-01, for both the
  Gmail MCP connector and the `gws` CLI.

## Out of scope

- Ramp Travel trips (`GET /developer/v1/trips`). Available, but NSLS does not appear to
  book through it; calendar plus spend geography covers the same ground without a new
  scope. Revisit if Ramp Travel adoption changes.
- Attendee capture for meal substantiation. The stated audience is accounting-for-coding,
  not audit substantiation. If the audience changes, `Transaction.attendees[]` is the
  hook.
- Splitting a transaction across budgets (`PATCH /developer/v1/transactions/{id}` with
  `line_items`). Real, and out of scope until single-budget coding is trusted.
