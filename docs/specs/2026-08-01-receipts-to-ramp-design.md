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
| Ramp read | Ramp API, `transactions:read` | Need the authoritative missing-receipt queue |
| Ramp write | Email to `receipts@ramp.com` | Lower-risk, reversible, no write scope to provision |
| Control flow | Exception-driven (work Ramp's queue) | Self-limiting, idempotent, verifies its own work |
| Trigger | On-demand `/receipts` | Avoids the unattended session-cookie problem entirely |

**Known limitation, accepted:** the email write path cannot name a target transaction.
For `BALANCED` collisions this is acceptable (see below). If collisions become frequent
or Ramp mis-binds, revisit by provisioning `receipts:write` and posting against a
specific transaction ID.

## Architecture

```
┌─ queue.py ──────┐   Ramp API (read-only, transactions:read)
│ What's missing? │ → [{txn_id, merchant, amount_cents, date}]
└─────────────────┘
         ↓
┌─ sources/ ──────┐   Pluggable fetchers, tried in order
│ gmail.py        │     Gmail search for a matching receipt
│ anthropic.py    │     invoices endpoint → invoice_pdf_url → bytes
└─────────────────┘ → [{amount_cents, date, pdf_bytes, provenance}]
         ↓
┌─ match.py ──────┐   Pure function, zero I/O
└─────────────────┘ → CONFIDENT | BALANCED | AMBIGUOUS | UNFOUND
         ↓
┌─ send.py ───────┐   Forward via gws → receipts@ramp.com
│ + ledger.json   │   Record txn_id, invoice id, amount, ts, outcome
└─────────────────┘
```

### Component contracts

- **`queue.py`** — returns transactions currently missing a receipt. The exact Ramp
  filter parameter and receipt field name must be **read from Ramp's API docs at build
  time**, not assumed.
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
- **`send.py` + `ledger.json`** — the ledger distinguishes "never sent" from "sent and
  Ramp didn't match". Those need opposite responses, and nothing else can tell them apart.

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

Every run re-reads Ramp before acting:

- Ledger says sent, Ramp now shows a receipt → `CLEARED`, never revisited.
- Ledger says sent, Ramp still empty → `RETRY` once.
- Failed twice → `ESCALATED`. **Stop resending.** Report it for manual attachment.

The escalation cap is required: without it, receipts Ramp structurally cannot bind (the
ACH cases) get re-forwarded on every run forever.

Failures are partial and always announced on their own line:

- **Ramp API 401 → hard stop.** The queue is the entire basis of the design; without it
  the run is meaningless and must not proceed on guesswork.
- **Anthropic auth failure →** that source is skipped, Gmail still runs, report emits
  `SOURCE ANTHROPIC: SKIPPED (not authenticated)`.
- **`gws` send failure →** ledger records **not-sent**. Never marked sent on anything
  short of a confirmed success response. Worst case becomes a duplicate forward, which
  Ramp deduplicates, rather than a missing receipt, which nobody catches until close.

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

## Out of scope

- Spend visibility or reconciliation reporting (considered as approach C, rejected).
- Scheduled/unattended runs. Revisit once the matching logic is trusted against the
  real backlog.
- Fixing the ACH-vendor matching gap. Those invoices have no card transaction; the fix
  is a Ramp-side bill-pay workflow, not a receipt forwarder.
