# Receipts → Ramp — Design

**Date:** 2026-08-01
**Status:** Approved, ready for implementation planning
**Skill:** `nsls-personal-toolkit/skills/receipts/`, invoked as `/receipts`

## Problem

NSLS card transactions sit in Ramp without receipts. Two distinct causes, which need
two distinct fixes:

1. **Vendors that email receipts** (Anthropic subscription, Macroscope, Clay, United,
   Have I Been Pwned). The receipt exists in Gmail. Kevin forwards it by hand to
   `receipts@ramp.com` in batches — 15 on 2026-07-31, more on 2026-07-21.
2. **Vendors that email nothing.** Anthropic's usage-credit auto-recharges generate a
   Stripe invoice but no email. Ramp nags ("$1,085.00 at Anthropic needs a receipt",
   07/19) and there is no artifact in the inbox to forward.

Volume is the reason this needs automating: the Anthropic billing API returns **100
invoices between 2026-04-29 and 2026-07-23**, roughly 35/month.

## Findings that shaped the design

Verified live on 2026-08-01 against the logged-in account.

- **`/admin-settings/usage` has no receipts.** It is the credits meter and spend
  controls. Invoices live at `/admin-settings/billing`.
- **There is a JSON API. No DOM scraping is required.**
  ```
  GET https://claude.ai/api/stripe/{org_uuid}/invoices?limit=100&page=
  → { invoices: [{ total, total_excluding_tax, currency, status,
                   created_ts, invoice_pdf_url, hosted_invoice_url, ... }],
      has_more, next_page }
  ```
  NSLS org uuid: `13e93397-1064-4c51-af05-279821a5bf9c`. `total` is in cents.
- **`invoice_pdf_url` resolves with no authentication.** Stripe secret-token URL;
  verified `HTTP 200`, `application/octet-stream`, 33,227 bytes, valid PDF v1.4 with
  no cookies sent. Only the *listing* call is session-gated.
- **Duplicate-amount collisions are real.** Four separate $214.56 charges within six
  minutes on 2026-07-23.
- **Ramp's email matcher fails on non-card spend.** The 07/31 batch returned
  "Couldn't match" for Atlassian, SendGrid, GoDaddy, and both Google Workspace
  invoices — ACH/bill-pay with no card transaction to bind to.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | All vendors, not just Anthropic | The manual batch-forward ritual is the real pain |
| Ramp read | Ramp API, `transactions:read` + `receipts:read` | Need the authoritative missing-receipt queue |
| Ramp write | Ramp API, `POST /developer/v1/receipts` with `transaction_id` | Names the exact target; `idempotency_key` makes retries safe |
| Control flow | Exception-driven (work Ramp's queue) | Self-limiting, idempotent, verifies its own work |
| Trigger | On-demand `/receipts` | Avoids the unattended session-cookie problem entirely |

**Write path revised 2026-08-01, after reading Ramp's OpenAPI spec.** The design
originally chose email forwarding to `receipts@ramp.com` on the assumption that it
avoided provisioning API scopes. That assumption was wrong: there is no
"missing receipt" filter on `GET /developer/v1/transactions`, so the queue must be
built as a set difference against `GET /developer/v1/receipts`, which requires
`receipts:read` regardless. Since a credential is being provisioned either way, adding
`receipts:write` costs one checkbox and buys two things email cannot do — an explicit
target `transaction_id` (resolves the collision case) and an `idempotency_key` (makes a
retried upload provably harmless instead of a duplicate).

## Architecture

```
┌─ queue.py ──────┐   Ramp: transactions:read + receipts:read
│ What's missing? │   set difference over one date window
└─────────────────┘ → [{txn_id, merchant, amount_cents, date}]
         ↓
┌─ sources/ ──────┐   Pluggable fetchers, tried in order
│ gmail.py        │     Gmail search for a matching receipt
│ anthropic.py    │     invoices endpoint → invoice_pdf_url → bytes
└─────────────────┘ → [{merchant, amount_cents, date, pdf_bytes, provenance}]
         ↓
┌─ match.py ──────┐   Pure function, zero I/O
└─────────────────┘ → CONFIDENT | BALANCED | AMBIGUOUS | UNFOUND
         ↓
┌─ upload.py ─────┐   POST /developer/v1/receipts (receipts:write)
│ + ledger.json   │   transaction_id + idempotency_key; record outcome
└─────────────────┘
```

### Component contracts

- **`queue.py`** — returns transactions currently missing a receipt, computed as a set
  difference. Verified against Ramp's OpenAPI spec on 2026-08-01:

  ```
  Base URL: https://api.ramp.com          Auth: OAuth2 client credentials
  GET  /developer/v1/transactions   scope transactions:read
       ?from_date&to_date&page_size&start        → data[].id, .amount, .merchant_*
  GET  /developer/v1/receipts       scope receipts:read
       ?from_date&to_date&page_size&start        → data[].transaction_id
  POST /developer/v1/receipts       scope receipts:write
       multipart: { idempotency_key, transaction_id?, user_id }
  ```

  `missing = {txn.id} - {receipt.transaction_id}` over the same date window. The
  `all_requirements_met_and_approved=false` filter is **not** used: it conflates missing
  receipts with missing memos and pending approvals, so it would produce a queue of
  items this skill cannot act on.
- **`sources/*.py`** — each declares `MERCHANTS`, the normalized merchant names it can
  supply receipts for, so `match.py` only asks sources that could plausibly answer. Each
  exposes `fetch(since) -> list[Receipt]` where
  `Receipt = (merchant, amount_cents, date, pdf_bytes, provenance)`, or raises a typed
  `SourceUnavailable`. `provenance` is a human-readable origin string used in the report
  and the ledger — e.g. `"anthropic:invoice 2422-8527-1659"` or
  `"gmail:msg 19f94f2f9efe8c87"` — so any send can be traced back to its artifact.
  Adding a vendor means adding one file; nothing else changes.
- **`match.py`** — pure, no I/O, so the highest-risk logic is testable against fixtures
  without network access.
- **`upload.py` + `ledger.json`** — posts the PDF to Ramp against a named
  `transaction_id`. `idempotency_key` is derived deterministically as
  `sha256(transaction_id + provenance)`, so the same receipt for the same transaction
  produces the same key on every run and Ramp collapses repeats server-side. The ledger
  records the attempt and its observed outcome, and remains the only thing that can
  distinguish "never uploaded" from "uploaded and rejected".

### Session handling

`sources/anthropic.py` uses a Playwright persistent profile at
`~/.claude-receipts-profile/`. Non-200 on the listing call opens a visible window for
login, then retries. No cookie stored in config, nothing that expires silently.

## Matching

Candidates keyed on **normalized merchant + amount_cents + date within ±3 days**. The
window exists because card settlement lags invoice creation; exact-date matching would
miss real pairs.

| Outcome | Condition | Action |
|---|---|---|
| `CONFIDENT` | 1 receipt ↔ 1 transaction | Send |
| `BALANCED` | N receipts ↔ N transactions, same merchant/amount/date | Sort both by timestamp, zip, send |
| `AMBIGUOUS` | Counts differ, or amount off by more than rounding | Do not send; list for human |
| `UNFOUND` | No receipt in any source | List, with where to look |

**Why `BALANCED` may auto-send.** When four transactions and four receipts are mutually
indistinguishable on merchant, amount, and date, any 1:1 assignment is correct — each
PDF is a genuine receipt for one of those charges and no auditor can distinguish them,
because there is no distinction. Zipping by timestamp makes it deterministic.

**Why 4-vs-3 must not.** Disagreeing counts are real information. Auto-assigning would
destroy it and produce a confidently wrong binding.

## Failure handling

Every run re-reads Ramp before acting. Verification is exact — `GET /developer/v1/receipts
?transaction_id=X` either returns a receipt or it does not:

- Ledger says uploaded, Ramp now shows a receipt → `CLEARED`, never revisited.
- Ledger says uploaded, Ramp still empty → `RETRY` once (same idempotency key, so a
  successful-but-unobserved first attempt cannot double-post).
- Failed twice → `ESCALATED`. **Stop retrying.** Report it for manual attachment.

The escalation cap is required: without it, a transaction Ramp refuses for a reason the
skill cannot see gets retried on every run forever.

Failures are partial and always announced on their own line:

- **Ramp API 401 → hard stop.** The queue is the entire basis of the design; without it
  the run is meaningless and must not proceed on guesswork.
- **Anthropic auth failure →** that source is skipped, Gmail still runs, report emits
  `SOURCE ANTHROPIC: SKIPPED (not authenticated)`.
- **Upload failure →** ledger records **not-uploaded**. Never marked uploaded on
  anything short of a 2xx. Worst case becomes a repeat POST carrying the same
  idempotency key, which Ramp collapses, rather than a missing receipt, which nobody
  catches until close.

## Modes

- `/receipts` — dry run. Prints the plan. **Default**, because the first run faces a
  ~100-invoice backlog.
- `/receipts --send` — execute the plan.

## Testing

- **`match.py` fixtures from real data:** the 07/23 four-way $214.56 collision; the
  07/19 $1,085.00 single; a hand-built 4-receipts-vs-3-transactions variant; an ACH case
  with no card transaction.
- **Non-vacuous assertions:** each test asserts the negative. The 4v3 case must produce
  zero sends, and the test fails if `send.py` is invoked at all.
- **Source contract test:** one shared test over every file in `sources/`, so new
  vendors are covered the day they land.
- **Live smoke test, run manually:** hit the real invoices endpoint, assert ≥1 invoice,
  download the first PDF, assert bytes start with `%PDF`. This is what catches Anthropic
  changing the endpoint shape — the most likely way this breaks.

## Phase 2 — Categorization memos (design not yet done)

Raised 2026-08-01. Ramp supports this directly, and its data model already encodes the
recurring/one-off split:

```
GET  /developer/v1/transactions?requires_memo=true    scope transactions:read
     "Filters for transactions which require a memo, but do not have one."
POST /developer/v1/memos/{transaction_id}             scope memos:write
     { memo: string, is_memo_recurring: boolean }
```

`requires_memo=true` gives a ready-made queue — no set difference needed, unlike
receipts. `is_memo_recurring` maps onto the two classes:

- **Recurring** (Anthropic, Macroscope, Clay, GoDaddy) — memo is derivable from vendor
  plus period. Templated, deterministic, `is_memo_recurring=true` so Ramp reuses it.
- **One-off** (restaurant, travel) — memo needs facts the transaction does not carry:
  which trip, which budget, who attended, what it was for.

**The one-off case is a separate design problem and must not be bolted onto this plan.**
Its hard part is not the API call, it is sourcing context that is only partly
machine-readable — calendar events, the receipt itself (a United eTicket carries the
itinerary; a restaurant charge carries nothing), and Kevin's own knowledge. It needs its
own brainstorm before it gets a plan.

Infrastructure it will reuse unchanged: `ramp_client.py` (Task 1) and the pagination and
window logic in `queue.py` (Task 2).

## Out of scope

- Spend visibility or reconciliation reporting (considered as approach C, rejected).
- Scheduled/unattended runs. Revisit once the matching logic is trusted against the
  real backlog.
- Fixing the ACH-vendor matching gap. Those invoices have no card transaction; the fix
  is a Ramp-side bill-pay workflow, not a receipt forwarder.
