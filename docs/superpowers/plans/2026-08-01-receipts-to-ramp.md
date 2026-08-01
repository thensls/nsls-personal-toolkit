# Receipts → Ramp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/receipts`, an on-demand skill that finds Ramp card transactions missing receipts, sources each receipt from Gmail or a vendor portal, and uploads it to Ramp against the exact transaction.

**Architecture:** Exception-driven. `queue.py` computes the missing-receipt set from Ramp, `sources/*.py` fetch candidate receipt PDFs, `match.py` (pure, no I/O) binds receipts to transactions with four confidence outcomes, `upload.py` POSTs to Ramp with an idempotency key and records the outcome in a ledger. Dry-run by default.

**Tech Stack:** Python 3.12, stdlib `urllib` for HTTP, Playwright (existing MCP browser profile) for the Anthropic session, Gmail via the existing `gws` CLI. No new third-party dependencies.

**Spec:** `docs/specs/2026-08-01-receipts-to-ramp-design.md`

## Global Constraints

- **Python 3.12.** Shebang `#!/usr/bin/env python3.12` on every script, matching the toolkit convention (`skills/person-intelligence/scripts/*.py`).
- **Tests are dual-mode.** Plain `assert`, `test_*` functions collectable by pytest 9.0.2, plus an `if __name__ == "__main__":` block that calls each test and prints a summary. Matches `skills/person-intelligence/tests/test_resolve_user.py`.
- **NEVER inline a secret value in a Bash command.** From repo `CLAUDE.md`: patterns like `export RAMP_CLIENT_SECRET=abc123; python3 -c "..."` leak the key into the tool log, the on-disk transcript, and upstream request logs. Read credentials from the environment inside Python only. To verify a variable is set, print its *length*, never its value.
- **Secrets live in `.env`**, which is gitignored. Add new keys to `.env.example` with empty values.
- **No new pip dependencies.** Use `urllib.request` from stdlib.
- **Ramp API facts** (verified against `https://docs.ramp.com/openapi/developer-api.json` on 2026-08-01):
  - Base URL `https://api.ramp.com`
  - `POST /developer/v1/token` — OAuth2 client credentials, HTTP Basic auth with client id/secret
  - `GET /developer/v1/transactions` — scope `transactions:read`; params `from_date`, `to_date`, `page_size` (2–100), `start`
  - `GET /developer/v1/receipts` — scope `receipts:read`; params `from_date`, `to_date`, `transaction_id`, `page_size`, `start`
  - `POST /developer/v1/receipts` — scope `receipts:write`; `multipart/form-data` with `idempotency_key`, `transaction_id` (optional), `user_id` (required)
  - Pagination: response `page.next` is a URL or `null`
- **Anthropic billing facts** (verified live 2026-08-01):
  - `GET https://claude.ai/api/stripe/{org_uuid}/invoices?limit=100&page=` returns `{invoices: [...], has_more, next_page}`
  - NSLS org uuid `13e93397-1064-4c51-af05-279821a5bf9c`
  - Invoice fields used: `total` (cents), `created_ts` (unix seconds), `status`, `invoice_pdf_url`
  - `invoice_pdf_url` resolves with **no** authentication
- **Amounts are integer cents everywhere.** Ramp's `amount` is a float in dollars; convert at the boundary in `queue.py` with `round(amount * 100)` and never carry floats past it.

---

### Task 1: Skill scaffold and Ramp OAuth client

**Files:**
- Create: `skills/receipts/SKILL.md`
- Create: `skills/receipts/scripts/ramp_client.py`
- Create: `skills/receipts/tests/test_ramp_client.py`
- Modify: `.env.example` (append Ramp keys)

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - `RampClient(client_id: str, client_secret: str, base_url: str = "https://api.ramp.com")`
  - `RampClient.from_env() -> RampClient` — reads `RAMP_CLIENT_ID`, `RAMP_CLIENT_SECRET`; raises `RampConfigError` if absent
  - `RampClient.token(scopes: list[str]) -> str` — cached per scope-set for the process lifetime
  - `RampClient.get(path: str, params: dict, scopes: list[str]) -> dict`
  - `RampClient.paginate(path: str, params: dict, scopes: list[str]) -> Iterator[dict]` — yields each item from `data[]` across all pages, following `page.next`
  - `class RampConfigError(Exception)`, `class RampAuthError(Exception)`

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_ramp_client.py`:

```python
#!/usr/bin/env python3.12
"""Tests for ramp_client.py.

Run: python3.12 skills/receipts/tests/test_ramp_client.py
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ramp_client import RampClient, RampConfigError


def test_from_env_raises_without_credentials():
    with patch.dict(os.environ, {}, clear=True):
        try:
            RampClient.from_env()
        except RampConfigError as exc:
            assert "RAMP_CLIENT_ID" in str(exc)
            return
        raise AssertionError("expected RampConfigError")


def test_from_env_reads_credentials():
    env = {"RAMP_CLIENT_ID": "cid", "RAMP_CLIENT_SECRET": "sec"}
    with patch.dict(os.environ, env, clear=True):
        client = RampClient.from_env()
    assert client.client_id == "cid"
    assert client.base_url == "https://api.ramp.com"


def test_paginate_follows_page_next_and_stops():
    client = RampClient("cid", "sec")
    pages = [
        {"data": [{"id": "a"}, {"id": "b"}], "page": {"next": "https://api.ramp.com/x?start=b"}},
        {"data": [{"id": "c"}], "page": {"next": None}},
    ]
    calls = []

    def fake_request(url, headers=None, method="GET", body=None):
        calls.append(url)
        return pages[len(calls) - 1]

    with patch.object(client, "_request", side_effect=fake_request):
        with patch.object(client, "token", return_value="tok"):
            items = list(client.paginate("/developer/v1/transactions", {}, ["transactions:read"]))

    assert [i["id"] for i in items] == ["a", "b", "c"]
    assert len(calls) == 2, f"expected 2 requests, got {len(calls)}"


def test_paginate_returns_nothing_for_empty_data():
    client = RampClient("cid", "sec")
    with patch.object(client, "_request", return_value={"data": [], "page": {"next": None}}):
        with patch.object(client, "token", return_value="tok"):
            items = list(client.paginate("/developer/v1/receipts", {}, ["receipts:read"]))
    assert items == []


if __name__ == "__main__":
    print("Running ramp_client tests")
    test_from_env_raises_without_credentials()
    test_from_env_reads_credentials()
    test_paginate_follows_page_next_and_stops()
    test_paginate_returns_nothing_for_empty_data()
    print("\nAll ramp_client tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_ramp_client.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'ramp_client'`

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/ramp_client.py`:

```python
#!/usr/bin/env python3.12
"""Thin Ramp Developer API client.

Credentials come from the environment only. Never pass secrets on a command line.
"""

import base64
import json
import os
import urllib.parse
import urllib.request
from typing import Iterator

BASE_URL = "https://api.ramp.com"


class RampConfigError(Exception):
    """Required Ramp credentials are missing from the environment."""


class RampAuthError(Exception):
    """Ramp rejected our credentials or token."""


class RampClient:
    def __init__(self, client_id: str, client_secret: str, base_url: str = BASE_URL):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self._tokens: dict[str, str] = {}

    @classmethod
    def from_env(cls) -> "RampClient":
        cid = os.environ.get("RAMP_CLIENT_ID")
        secret = os.environ.get("RAMP_CLIENT_SECRET")
        missing = [n for n, v in (("RAMP_CLIENT_ID", cid), ("RAMP_CLIENT_SECRET", secret)) if not v]
        if missing:
            raise RampConfigError(
                f"Missing {', '.join(missing)}. Add them to .env "
                f"(Ramp → Settings → Developer API)."
            )
        return cls(cid, secret)

    def _request(self, url, headers=None, method="GET", body=None):
        req = urllib.request.Request(url, data=body, method=method)
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        return json.loads(raw) if raw else {}

    def token(self, scopes: list[str]) -> str:
        key = " ".join(sorted(scopes))
        if key in self._tokens:
            return self._tokens[key]
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        body = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": key}).encode()
        try:
            data = self._request(
                f"{self.base_url}/developer/v1/token",
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                method="POST",
                body=body,
            )
        except urllib.error.HTTPError as exc:
            raise RampAuthError(
                f"Ramp token request failed ({exc.code}). Check RAMP_CLIENT_ID/"
                f"RAMP_CLIENT_SECRET and that the app grants: {key}"
            ) from exc
        self._tokens[key] = data["access_token"]
        return self._tokens[key]

    def get(self, path: str, params: dict, scopes: list[str]) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return self._request(url, headers={"Authorization": f"Bearer {self.token(scopes)}"})

    def paginate(self, path: str, params: dict, scopes: list[str]) -> Iterator[dict]:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        while url:
            page = self._request(url, headers={"Authorization": f"Bearer {self.token(scopes)}"})
            yield from page.get("data", [])
            url = (page.get("page") or {}).get("next")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_ramp_client.py`
Expected: `All ramp_client tests passed.`

- [ ] **Step 5: Add credential placeholders to `.env.example`**

Append:

```
# Ramp Developer API — Ramp → Settings → Developer API
# Scopes required: transactions:read, receipts:read, receipts:write
RAMP_CLIENT_ID=
RAMP_CLIENT_SECRET=
RAMP_USER_ID=
```

- [ ] **Step 6: Create the skill entry point**

Create `skills/receipts/SKILL.md` with frontmatter. **Do not set `disable-model-invocation`** — it makes the skill invisible in new sessions.

```markdown
---
name: receipts
description: Find Ramp card transactions missing receipts, source each receipt from Gmail or a vendor billing portal, and upload it to Ramp against the exact transaction. Use when the user says "receipts", "/receipts", "missing receipts", "Ramp needs a receipt", "receipt cleanup", or forwards a Ramp "transaction needs a receipt" nag. Dry-run by default.
---

# Receipts → Ramp

Works Ramp's missing-receipt queue. Dry run by default; `--send` executes.

## Usage

- `/receipts` — show the plan, change nothing
- `/receipts --send` — execute the plan
- `/receipts --since 2026-04-01` — widen the window (default: 90 days)

See `docs/specs/2026-08-01-receipts-to-ramp-design.md` for the design.
```

- [ ] **Step 7: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/receipts .env.example
git commit -m "feat(receipts): add Ramp API client and skill scaffold"
```

---

### Task 2: The missing-receipt queue

**Files:**
- Create: `skills/receipts/scripts/queue.py`
- Create: `skills/receipts/tests/test_queue.py`

**Interfaces:**
- Consumes: `RampClient.paginate` from Task 1
- Produces:
  - `@dataclass(frozen=True) class Transaction: id: str; merchant: str; amount_cents: int; date: str  # ISO yyyy-mm-dd`
  - `missing_receipts(client, since: str, until: str) -> list[Transaction]`
  - `has_receipt(client, transaction_id: str) -> bool`

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_queue.py`:

```python
#!/usr/bin/env python3.12
"""Tests for queue.py."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from queue import Transaction, missing_receipts

TXNS = [
    {"id": "t1", "amount": 214.56, "merchant_name": "Anthropic", "user_transaction_time": "2026-07-23T10:00:00Z"},
    {"id": "t2", "amount": 214.56, "merchant_name": "Anthropic", "user_transaction_time": "2026-07-23T10:03:00Z"},
    {"id": "t3", "amount": 1085.00, "merchant_name": "Anthropic", "user_transaction_time": "2026-07-19T08:00:00Z"},
]


def _client_returning(txns, receipts):
    class FakeClient:
        def paginate(self, path, params, scopes):
            return iter(txns if "transactions" in path else receipts)
    return FakeClient()


def test_subtracts_transactions_that_already_have_receipts():
    client = _client_returning(TXNS, [{"transaction_id": "t3"}])
    result = missing_receipts(client, "2026-07-01", "2026-07-31")
    assert [t.id for t in result] == ["t1", "t2"]


def test_converts_dollars_to_integer_cents():
    client = _client_returning(TXNS[:1], [])
    result = missing_receipts(client, "2026-07-01", "2026-07-31")
    assert result[0].amount_cents == 21456
    assert isinstance(result[0].amount_cents, int)


def test_normalizes_transaction_time_to_iso_date():
    client = _client_returning(TXNS[:1], [])
    result = missing_receipts(client, "2026-07-01", "2026-07-31")
    assert result[0].date == "2026-07-23"


def test_returns_empty_when_every_transaction_has_a_receipt():
    receipts = [{"transaction_id": t["id"]} for t in TXNS]
    client = _client_returning(TXNS, receipts)
    assert missing_receipts(client, "2026-07-01", "2026-07-31") == []


if __name__ == "__main__":
    print("Running queue tests")
    test_subtracts_transactions_that_already_have_receipts()
    test_converts_dollars_to_integer_cents()
    test_normalizes_transaction_time_to_iso_date()
    test_returns_empty_when_every_transaction_has_a_receipt()
    print("\nAll queue tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_queue.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'queue'` resolving to our file — note Python has a stdlib `queue`; the `sys.path.insert(0, ...)` puts our scripts dir first, so ours wins. If the failure says `cannot import name 'Transaction' from 'queue'`, that is the stdlib shadowing and the test path insert is working as intended once our file exists.

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/queue.py`:

```python
#!/usr/bin/env python3.12
"""Compute the set of Ramp transactions missing a receipt.

Ramp has no "missing receipt" filter. `all_requirements_met_and_approved=false`
conflates missing receipts with missing memos and pending approvals, so we
compute a set difference against the receipts endpoint instead.
"""

from dataclasses import dataclass

TXN_SCOPES = ["transactions:read"]
RECEIPT_SCOPES = ["receipts:read"]


@dataclass(frozen=True)
class Transaction:
    id: str
    merchant: str
    amount_cents: int
    date: str  # ISO yyyy-mm-dd


def _iso_date(value: str) -> str:
    return (value or "")[:10]


def missing_receipts(client, since: str, until: str) -> list[Transaction]:
    window = {"from_date": since, "to_date": until, "page_size": 100}

    receipted = {
        r.get("transaction_id")
        for r in client.paginate("/developer/v1/receipts", dict(window), RECEIPT_SCOPES)
        if r.get("transaction_id")
    }

    out = []
    for t in client.paginate("/developer/v1/transactions", dict(window), TXN_SCOPES):
        if t["id"] in receipted:
            continue
        out.append(
            Transaction(
                id=t["id"],
                merchant=t.get("merchant_name") or "",
                amount_cents=round(float(t["amount"]) * 100),
                date=_iso_date(t.get("user_transaction_time", "")),
            )
        )
    return out


def has_receipt(client, transaction_id: str) -> bool:
    page = client.get(
        "/developer/v1/receipts",
        {"transaction_id": transaction_id, "page_size": 2},
        RECEIPT_SCOPES,
    )
    return bool(page.get("data"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_queue.py`
Expected: `All queue tests passed.`

- [ ] **Step 5: Commit**

```bash
git add skills/receipts/scripts/queue.py skills/receipts/tests/test_queue.py
git commit -m "feat(receipts): compute missing-receipt queue via set difference"
```

---

### Task 3: Source contract

**Files:**
- Create: `skills/receipts/scripts/sources/__init__.py`
- Create: `skills/receipts/scripts/sources/base.py`
- Create: `skills/receipts/tests/test_source_contract.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `@dataclass(frozen=True) class Receipt: merchant: str; amount_cents: int; date: str; pdf_bytes: bytes; provenance: str`
  - `class SourceUnavailable(Exception)`
  - `class Source(Protocol): MERCHANTS: tuple[str, ...]; def fetch(self, since: str, until: str) -> list[Receipt]: ...`
  - `normalize_merchant(name: str) -> str` — lowercase, strip non-alphanumerics
  - `load_sources() -> list[Source]` — instantiates every `Source` subclass in `sources/`

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_source_contract.py`:

```python
#!/usr/bin/env python3.12
"""Contract test applied to every source. New vendors are covered on arrival."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sources.base import Receipt, SourceUnavailable, load_sources, normalize_merchant


def test_normalize_merchant_collapses_punctuation_and_case():
    assert normalize_merchant("Anthropic, PBC") == "anthropicpbc"
    assert normalize_merchant("ANTHROPIC") == "anthropic"
    assert normalize_merchant("Clay Labs Inc") == "claylabsinc"


def test_receipt_is_frozen():
    r = Receipt("anthropic", 21456, "2026-07-23", b"%PDF-1.4", "anthropic:invoice 1")
    try:
        r.amount_cents = 1
    except AttributeError:
        return
    raise AssertionError("Receipt must be immutable")


def test_every_source_declares_normalized_merchants():
    sources = load_sources()
    assert sources, "load_sources() found no sources"
    for src in sources:
        assert hasattr(src, "MERCHANTS"), f"{type(src).__name__} missing MERCHANTS"
        assert isinstance(src.MERCHANTS, tuple), f"{type(src).__name__}.MERCHANTS must be a tuple"
        for m in src.MERCHANTS:
            assert m == normalize_merchant(m), (
                f"{type(src).__name__}.MERCHANTS entry {m!r} is not normalized"
            )


def test_every_source_exposes_fetch():
    for src in load_sources():
        assert callable(getattr(src, "fetch", None)), f"{type(src).__name__} missing fetch()"


if __name__ == "__main__":
    print("Running source contract tests")
    test_normalize_merchant_collapses_punctuation_and_case()
    test_receipt_is_frozen()
    test_every_source_declares_normalized_merchants()
    test_every_source_exposes_fetch()
    print("\nAll source contract tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_source_contract.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources'`

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/sources/__init__.py` (empty file).

Create `skills/receipts/scripts/sources/base.py`:

```python
#!/usr/bin/env python3.12
"""Contract every receipt source implements."""

import importlib
import pkgutil
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class SourceUnavailable(Exception):
    """Source could not run — auth, network, config. Never a match failure."""


@dataclass(frozen=True)
class Receipt:
    merchant: str        # normalized
    amount_cents: int
    date: str            # ISO yyyy-mm-dd
    pdf_bytes: bytes
    provenance: str      # e.g. "anthropic:invoice 2422-8527-1659"


@runtime_checkable
class Source(Protocol):
    MERCHANTS: tuple[str, ...]

    def fetch(self, since: str, until: str) -> list[Receipt]:
        ...


def normalize_merchant(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def load_sources() -> list:
    """Instantiate every source module's `SOURCE` singleton."""
    import sources

    found = []
    for mod in pkgutil.iter_modules(sources.__path__):
        if mod.name == "base":
            continue
        module = importlib.import_module(f"sources.{mod.name}")
        if hasattr(module, "SOURCE"):
            found.append(module.SOURCE)
    return found
```

- [ ] **Step 4: Run test to verify it fails on the empty-source assertion**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_source_contract.py`
Expected: FAIL with `AssertionError: load_sources() found no sources` — correct, no sources exist yet. Task 4 makes it pass.

- [ ] **Step 5: Commit**

```bash
git add skills/receipts/scripts/sources skills/receipts/tests/test_source_contract.py
git commit -m "feat(receipts): add source contract and merchant normalization"
```

---

### Task 4: Anthropic source

**Files:**
- Create: `skills/receipts/scripts/sources/anthropic.py`
- Create: `skills/receipts/tests/test_source_anthropic.py`

**Interfaces:**
- Consumes: `Receipt`, `SourceUnavailable`, `normalize_merchant` from Task 3
- Produces: `SOURCE` — an `AnthropicSource` instance with `MERCHANTS = ("anthropic", "anthropicpbc")`
  - `AnthropicSource.parse_invoices(payload: dict) -> list[dict]` — pure; maps raw invoice JSON to `{amount_cents, date, pdf_url, provenance}`

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_source_anthropic.py`:

```python
#!/usr/bin/env python3.12
"""Tests for the Anthropic billing source. Parsing is pure and tested offline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sources.anthropic import SOURCE

# Shape captured live from GET /api/stripe/{org}/invoices on 2026-08-01.
PAYLOAD = {
    "invoices": [
        {
            "total": 21456,
            "currency": "usd",
            "status": "paid",
            "created_ts": 1784806673,
            "invoice_pdf_url": "https://pay.stripe.com/invoice/acct_X/live_A/pdf?s=ap",
            "hosted_invoice_url": "https://invoice.stripe.com/i/acct_X/live_A",
        },
        {
            "total": 108500,
            "currency": "usd",
            "status": "paid",
            "created_ts": 1784501642,
            "invoice_pdf_url": "https://pay.stripe.com/invoice/acct_X/live_B/pdf?s=ap",
            "hosted_invoice_url": "https://invoice.stripe.com/i/acct_X/live_B",
        },
        {
            "total": 9999,
            "currency": "usd",
            "status": "draft",
            "created_ts": 1784501000,
            "invoice_pdf_url": None,
            "hosted_invoice_url": None,
        },
    ],
    "has_more": False,
    "next_page": None,
}


def test_amount_stays_in_integer_cents():
    rows = SOURCE.parse_invoices(PAYLOAD)
    assert rows[0]["amount_cents"] == 21456
    assert rows[1]["amount_cents"] == 108500


def test_created_ts_becomes_iso_date():
    rows = SOURCE.parse_invoices(PAYLOAD)
    assert rows[1]["date"] == "2026-07-19", rows[1]["date"]


def test_unpaid_or_pdfless_invoices_are_dropped():
    rows = SOURCE.parse_invoices(PAYLOAD)
    assert len(rows) == 2, "draft invoice with no PDF must be dropped"
    assert all(r["pdf_url"] for r in rows)


def test_provenance_identifies_the_specific_invoice():
    rows = SOURCE.parse_invoices(PAYLOAD)
    assert rows[0]["provenance"] != rows[1]["provenance"]
    assert "anthropic" in rows[0]["provenance"]


def test_merchants_are_declared_and_normalized():
    assert "anthropic" in SOURCE.MERCHANTS
    assert "anthropicpbc" in SOURCE.MERCHANTS


if __name__ == "__main__":
    print("Running anthropic source tests")
    test_amount_stays_in_integer_cents()
    test_created_ts_becomes_iso_date()
    test_unpaid_or_pdfless_invoices_are_dropped()
    test_provenance_identifies_the_specific_invoice()
    test_merchants_are_declared_and_normalized()
    print("\nAll anthropic source tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_source_anthropic.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.anthropic'`

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/sources/anthropic.py`:

```python
#!/usr/bin/env python3.12
"""Anthropic (claude.ai) billing source.

The listing call needs a claude.ai session cookie. The PDF URLs it returns are
Stripe secret-token URLs that resolve with no authentication at all — verified
2026-08-01 — so only the listing is session-gated.
"""

import datetime as dt
import json
import os
import urllib.request

from .base import Receipt, SourceUnavailable

ORG_UUID = os.environ.get("ANTHROPIC_ORG_UUID", "13e93397-1064-4c51-af05-279821a5bf9c")
LISTING = "https://claude.ai/api/stripe/{org}/invoices?limit=100&page={page}"
PROFILE = os.path.expanduser("~/.claude-receipts-profile")


class AnthropicSource:
    MERCHANTS = ("anthropic", "anthropicpbc")

    def parse_invoices(self, payload: dict) -> list[dict]:
        rows = []
        for inv in payload.get("invoices", []):
            if inv.get("status") != "paid" or not inv.get("invoice_pdf_url"):
                continue
            date = dt.datetime.fromtimestamp(inv["created_ts"], dt.UTC).date().isoformat()
            rows.append(
                {
                    "amount_cents": int(inv["total"]),
                    "date": date,
                    "pdf_url": inv["invoice_pdf_url"],
                    "provenance": f"anthropic:invoice {date} {inv['total']}",
                }
            )
        return rows

    def _listing(self, page: str = "") -> dict:
        """Fetch one page of invoices using the persistent Playwright profile.

        Raises SourceUnavailable if the session is dead; the caller skips this
        source and continues with the others.
        """
        from playwright.sync_api import sync_playwright

        url = LISTING.format(org=ORG_UUID, page=page)
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(PROFILE, headless=True)
            try:
                page_obj = ctx.new_page()
                resp = page_obj.goto(url)
                if resp is None or resp.status != 200:
                    raise SourceUnavailable(
                        "claude.ai session expired. Run: python3.12 "
                        "skills/receipts/scripts/sources/anthropic.py --login"
                    )
                return json.loads(page_obj.inner_text("pre") or "{}")
            finally:
                ctx.close()

    def fetch(self, since: str, until: str) -> list[Receipt]:
        rows, page, guard = [], "", 0
        while guard < 20:
            payload = self._listing(page)
            rows.extend(self.parse_invoices(payload))
            if not payload.get("has_more"):
                break
            page = payload.get("next_page") or ""
            guard += 1

        out = []
        for r in rows:
            if not (since <= r["date"] <= until):
                continue
            out.append(
                Receipt(
                    merchant="anthropic",
                    amount_cents=r["amount_cents"],
                    date=r["date"],
                    pdf_bytes=self._download(r["pdf_url"]),
                    provenance=r["provenance"],
                )
            )
        return out

    @staticmethod
    def _download(url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
        if not data.startswith(b"%PDF"):
            raise SourceUnavailable(f"Expected a PDF from {url[:60]}…, got {data[:16]!r}")
        return data


SOURCE = AnthropicSource()


def _login():
    """Open a visible browser so the user can sign in once."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, headless=False)
        ctx.new_page().goto("https://claude.ai/login")
        input("Sign in, then press Enter here to save the session… ")
        ctx.close()


if __name__ == "__main__":
    import sys

    if "--login" in sys.argv:
        _login()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_source_anthropic.py && python3.12 skills/receipts/tests/test_source_contract.py`
Expected: both print `All … tests passed.` The contract test now finds one source and passes.

- [ ] **Step 5: Commit**

```bash
git add skills/receipts/scripts/sources/anthropic.py skills/receipts/tests/test_source_anthropic.py
git commit -m "feat(receipts): add Anthropic billing source"
```

---

### Task 5: Gmail source

**Files:**
- Create: `skills/receipts/scripts/sources/gmail.py`
- Create: `skills/receipts/tests/test_source_gmail.py`

**Interfaces:**
- Consumes: `Receipt`, `SourceUnavailable`, `normalize_merchant` from Task 3
- Produces: `SOURCE` — a `GmailSource` instance with `MERCHANTS = ()` (empty tuple means "try me for any merchant")
  - `GmailSource.parse_amount(text: str) -> int | None` — pure; extracts cents from a receipt body
  - `GmailSource.build_query(since: str, until: str) -> str` — pure; Gmail search syntax

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_source_gmail.py`:

```python
#!/usr/bin/env python3.12
"""Tests for the Gmail receipt source. Parsing is pure and tested offline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sources.gmail import SOURCE


def test_parse_amount_handles_thousands_separator():
    assert SOURCE.parse_amount("Your receipt ... Total $1,085.00 paid") == 108500


def test_parse_amount_handles_plain_dollars():
    assert SOURCE.parse_amount("Amount charged: $99.91") == 9991


def test_parse_amount_returns_none_when_absent():
    assert SOURCE.parse_amount("Your organization used 75% of its credits") is None


def test_build_query_scopes_by_date_and_receipt_language():
    q = SOURCE.build_query("2026-07-01", "2026-07-31")
    assert "after:2026/07/01" in q
    assert "before:2026/07/31" in q
    assert "receipt" in q.lower()


def test_empty_merchants_means_try_for_any_merchant():
    assert SOURCE.MERCHANTS == ()


if __name__ == "__main__":
    print("Running gmail source tests")
    test_parse_amount_handles_thousands_separator()
    test_parse_amount_handles_plain_dollars()
    test_parse_amount_returns_none_when_absent()
    test_build_query_scopes_by_date_and_receipt_language()
    test_empty_merchants_means_try_for_any_merchant()
    print("\nAll gmail source tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_source_gmail.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.gmail'`

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/sources/gmail.py`:

```python
#!/usr/bin/env python3.12
"""Gmail receipt source — reads receipt mail via the existing `gws` CLI.

MERCHANTS is empty, which means "candidate for any merchant". Gmail is tried
after merchant-specific portal sources.
"""

import json
import re
import shutil
import subprocess

from .base import Receipt, SourceUnavailable, normalize_merchant

AMOUNT = re.compile(r"\$\s?([0-9][0-9,]*\.[0-9]{2})")


class GmailSource:
    MERCHANTS: tuple[str, ...] = ()

    def parse_amount(self, text: str) -> int | None:
        m = AMOUNT.search(text or "")
        if not m:
            return None
        return round(float(m.group(1).replace(",", "")) * 100)

    def build_query(self, since: str, until: str) -> str:
        a = since.replace("-", "/")
        b = until.replace("-", "/")
        return (
            f"after:{a} before:{b} "
            f"(subject:receipt OR subject:invoice OR subject:payment) "
            f"has:attachment OR subject:receipt"
        )

    def fetch(self, since: str, until: str) -> list[Receipt]:
        # Verified 2026-08-01: gws takes query params as a JSON blob via --params.
        # There is no `gws gmail search` subcommand.
        gws = shutil.which("gws") or os.path.expanduser("~/bin/gws")
        if not os.path.exists(gws):
            raise SourceUnavailable("`gws` CLI not found — see the gws skill")
        params = json.dumps(
            {"userId": "me", "q": self.build_query(since, until), "maxResults": 100}
        )
        try:
            proc = subprocess.run(
                [gws, "gmail", "users", "messages", "list", "--params", params, "--format", "json"],
                capture_output=True, text=True, timeout=120, check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise SourceUnavailable(f"gws gmail list failed: {exc.stderr[:200]}") from exc

        # gws prints a keyring banner before the JSON, and reports auth failure
        # as a JSON error object with HTTP 200. Both must be handled.
        body = proc.stdout[proc.stdout.find("{"):]
        payload = json.loads(body or "{}")
        if "error" in payload:
            raise SourceUnavailable(
                f"gws auth: {payload['error'].get('message', '')[:160]} "
                f"— re-authorize Google, then retry"
            )
        raw = json.dumps(payload.get("messages", []))

        out = []
        for msg in json.loads(raw or "[]"):
            cents = self.parse_amount(msg.get("snippet", "") + " " + msg.get("subject", ""))
            pdf = msg.get("attachment_bytes")
            if cents is None or not pdf:
                continue
            out.append(
                Receipt(
                    merchant=normalize_merchant(msg.get("merchant") or msg.get("sender", "")),
                    amount_cents=cents,
                    date=(msg.get("date") or "")[:10],
                    pdf_bytes=bytes(pdf),
                    provenance=f"gmail:msg {msg.get('id')}",
                )
            )
        return out


SOURCE = GmailSource()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_source_gmail.py && python3.12 skills/receipts/tests/test_source_contract.py`
Expected: both pass; the contract test now covers two sources.

- [ ] **Step 5: Verify `gws` returns real message data before trusting `fetch`**

The CLI shape was verified on 2026-08-01 (`gws gmail users messages list --params '{...}'`), but **Google auth was expired at the time, so the response body was never seen.** Two things still need checking against a live, authorized call:

```bash
~/bin/gws gmail users messages list \
  --params '{"userId":"me","q":"from:ramp.com newer_than:1m","maxResults":3}' --format json
```

1. If this returns `{"error": {"code": 401, ...}}`, Google auth is dead — re-authorize before continuing. `fetch()` already converts this into `SourceUnavailable`, so the skill degrades loudly rather than silently returning zero receipts.
2. `messages list` returns only `{id, threadId}` — **it does not return subjects, snippets, dates, or attachments.** `fetch()` as written assumes those fields exist. You will need a second call per message (`gws gmail users messages get`) to retrieve headers and attachment parts. Implement that, extend `test_source_gmail.py` with a fixture of the real `messages get` response shape, and only then trust `fetch()`.

**Do not skip this.** `parse_amount` and `build_query` are unit-tested; the subprocess path is not.

- [ ] **Step 6: Commit**

```bash
git add skills/receipts/scripts/sources/gmail.py skills/receipts/tests/test_source_gmail.py
git commit -m "feat(receipts): add Gmail receipt source"
```

---

### Task 6: Matching — the four outcomes

**Files:**
- Create: `skills/receipts/scripts/match.py`
- Create: `skills/receipts/tests/test_match.py`

**Interfaces:**
- Consumes: `Transaction` (Task 2), `Receipt` and `normalize_merchant` (Task 3)
- Produces:
  - `@dataclass(frozen=True) class Pairing: transaction: Transaction; receipt: Receipt | None; outcome: str; note: str`
  - `CONFIDENT = "CONFIDENT"`, `BALANCED = "BALANCED"`, `AMBIGUOUS = "AMBIGUOUS"`, `UNFOUND = "UNFOUND"`
  - `match(transactions: list[Transaction], receipts: list[Receipt], window_days: int = 3) -> list[Pairing]`

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_match.py`. Fixtures are the real 2026-07 data.

```python
#!/usr/bin/env python3.12
"""Tests for match.py — pure, no I/O.

Fixtures are real transactions from 2026-07, including the four-way
$214.56 collision on 07/23 and the $1,085.00 single on 07/19.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from match import AMBIGUOUS, BALANCED, CONFIDENT, UNFOUND, match
from queue import Transaction
from sources.base import Receipt


def txn(i, cents, date="2026-07-23", merchant="Anthropic"):
    return Transaction(id=i, merchant=merchant, amount_cents=cents, date=date)


def rcpt(cents, date="2026-07-23", prov="p", merchant="anthropic"):
    return Receipt(merchant, cents, date, b"%PDF-1.4", prov)


def test_single_match_is_confident():
    pairs = match([txn("t3", 108500, "2026-07-19")], [rcpt(108500, "2026-07-19", "inv-b")])
    assert len(pairs) == 1
    assert pairs[0].outcome == CONFIDENT
    assert pairs[0].receipt.provenance == "inv-b"


def test_four_identical_transactions_and_four_receipts_are_balanced():
    txns = [txn(f"t{i}", 21456) for i in range(4)]
    rs = [rcpt(21456, prov=f"inv-{i}") for i in range(4)]
    pairs = match(txns, rs)
    assert {p.outcome for p in pairs} == {BALANCED}
    assigned = [p.receipt.provenance for p in pairs]
    assert len(set(assigned)) == 4, "each transaction must get a distinct receipt"


def test_balanced_assignment_is_deterministic():
    txns = [txn(f"t{i}", 21456) for i in range(4)]
    rs = [rcpt(21456, prov=f"inv-{i}") for i in range(4)]
    first = [(p.transaction.id, p.receipt.provenance) for p in match(txns, rs)]
    second = [(p.transaction.id, p.receipt.provenance) for p in match(txns, list(reversed(rs)))]
    assert first == second, "assignment must not depend on input order"


def test_four_transactions_three_receipts_is_ambiguous_and_assigns_nothing():
    txns = [txn(f"t{i}", 21456) for i in range(4)]
    rs = [rcpt(21456, prov=f"inv-{i}") for i in range(3)]
    pairs = match(txns, rs)
    assert {p.outcome for p in pairs} == {AMBIGUOUS}
    assert all(p.receipt is None for p in pairs), "AMBIGUOUS must never assign a receipt"


def test_no_receipt_anywhere_is_unfound():
    pairs = match([txn("t9", 47838, "2026-06-17")], [])
    assert pairs[0].outcome == UNFOUND
    assert pairs[0].receipt is None


def test_settlement_lag_within_window_still_matches():
    pairs = match([txn("t1", 21456, "2026-07-25")], [rcpt(21456, "2026-07-23")])
    assert pairs[0].outcome == CONFIDENT


def test_outside_window_does_not_match():
    pairs = match([txn("t1", 21456, "2026-07-30")], [rcpt(21456, "2026-07-23")])
    assert pairs[0].outcome == UNFOUND


def test_different_merchant_never_matches():
    pairs = match(
        [txn("t1", 21456, merchant="Clay Labs Inc")],
        [rcpt(21456, merchant="anthropic")],
    )
    assert pairs[0].outcome == UNFOUND


def test_ach_case_with_no_card_transaction_yields_no_pairings():
    assert match([], [rcpt(25908, "2026-07-21")]) == []


if __name__ == "__main__":
    print("Running match tests")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok {name}")
    print("\nAll match tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_match.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'match'`

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/match.py`:

```python
#!/usr/bin/env python3.12
"""Bind receipts to transactions. Pure — no network, no filesystem, no clock."""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from queue import Transaction
from sources.base import Receipt, normalize_merchant

CONFIDENT = "CONFIDENT"
BALANCED = "BALANCED"
AMBIGUOUS = "AMBIGUOUS"
UNFOUND = "UNFOUND"


@dataclass(frozen=True)
class Pairing:
    transaction: Transaction
    receipt: Receipt | None
    outcome: str
    note: str


def _days_apart(a: str, b: str) -> int:
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


def match(transactions: list[Transaction], receipts: list[Receipt], window_days: int = 3) -> list[Pairing]:
    # Group transactions by everything that makes them indistinguishable.
    groups: dict[tuple, list[Transaction]] = defaultdict(list)
    for t in transactions:
        groups[(normalize_merchant(t.merchant), t.amount_cents)].append(t)

    used: set[int] = set()
    pairs: list[Pairing] = []

    for (merchant, cents), txns in groups.items():
        txns = sorted(txns, key=lambda t: (t.date, t.id))

        candidates = sorted(
            (
                r
                for i, r in enumerate(receipts)
                if i not in used
                and r.amount_cents == cents
                and normalize_merchant(r.merchant) == merchant
                and any(_days_apart(r.date, t.date) <= window_days for t in txns)
            ),
            key=lambda r: (r.date, r.provenance),
        )

        if not candidates:
            pairs.extend(Pairing(t, None, UNFOUND, "no receipt in any source") for t in txns)
            continue

        if len(candidates) != len(txns):
            note = f"{len(txns)} transactions vs {len(candidates)} receipts at ${cents/100:.2f}"
            pairs.extend(Pairing(t, None, AMBIGUOUS, note) for t in txns)
            continue

        outcome = CONFIDENT if len(txns) == 1 else BALANCED
        note = "" if outcome == CONFIDENT else f"{len(txns)} indistinguishable charges, zipped by date"
        for t, r in zip(txns, candidates):
            used.add(receipts.index(r))
            pairs.append(Pairing(t, r, outcome, note))

    return pairs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_match.py`
Expected: every `ok test_…` line, then `All match tests passed.`

- [ ] **Step 5: Commit**

```bash
git add skills/receipts/scripts/match.py skills/receipts/tests/test_match.py
git commit -m "feat(receipts): add matching with collision and ambiguity handling"
```

---

### Task 7: Upload and ledger

**Files:**
- Create: `skills/receipts/scripts/upload.py`
- Create: `skills/receipts/tests/test_upload.py`

**Interfaces:**
- Consumes: `RampClient` (Task 1), `has_receipt` (Task 2), `Pairing` and outcome constants (Task 6)
- Produces:
  - `idempotency_key(transaction_id: str, provenance: str) -> str` — `sha256` hex digest
  - `Ledger(path: Path)` with `.record(txn_id, provenance, status)`, `.attempts(txn_id) -> int`, `.status(txn_id) -> str | None`, `.save()`
  - `upload(client, pairing, ledger, user_id, dry_run: bool) -> str` — returns `"UPLOADED" | "SKIPPED" | "ESCALATED" | "DRY_RUN" | "FAILED"`
  - `MAX_ATTEMPTS = 2`

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_upload.py`:

```python
#!/usr/bin/env python3.12
"""Tests for upload.py — idempotency, the escalation cap, and dry-run safety."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from match import CONFIDENT, Pairing
from queue import Transaction
from sources.base import Receipt
from upload import MAX_ATTEMPTS, Ledger, idempotency_key, upload

T = Transaction("t1", "Anthropic", 21456, "2026-07-23")
R = Receipt("anthropic", 21456, "2026-07-23", b"%PDF-1.4", "anthropic:invoice A")
PAIR = Pairing(T, R, CONFIDENT, "")


class FakeClient:
    def __init__(self, receipt_exists=False, fail=False):
        self.posts = []
        self.receipt_exists = receipt_exists
        self.fail = fail

    def get(self, path, params, scopes):
        return {"data": [{"id": "r1"}] if self.receipt_exists else []}

    def post_multipart(self, path, fields, file_bytes, scopes):
        if self.fail:
            raise RuntimeError("ramp 500")
        self.posts.append(fields)
        return {"id": "r_new"}


def _ledger():
    return Ledger(Path(tempfile.mkdtemp()) / "ledger.json")


def test_idempotency_key_is_stable_across_runs():
    assert idempotency_key("t1", "inv-A") == idempotency_key("t1", "inv-A")


def test_idempotency_key_differs_per_transaction():
    assert idempotency_key("t1", "inv-A") != idempotency_key("t2", "inv-A")


def test_dry_run_never_posts():
    client = FakeClient()
    result = upload(client, PAIR, _ledger(), "u1", dry_run=True)
    assert result == "DRY_RUN"
    assert client.posts == [], "dry run must not POST"


def test_upload_sends_transaction_id_and_idempotency_key():
    client = FakeClient()
    upload(client, PAIR, _ledger(), "u1", dry_run=False)
    assert len(client.posts) == 1
    sent = client.posts[0]
    assert sent["transaction_id"] == "t1"
    assert sent["user_id"] == "u1"
    assert sent["idempotency_key"] == idempotency_key("t1", "anthropic:invoice A")


def test_already_receipted_transaction_is_skipped():
    client = FakeClient(receipt_exists=True)
    assert upload(client, PAIR, _ledger(), "u1", dry_run=False) == "SKIPPED"
    assert client.posts == []


def test_failure_is_recorded_as_not_uploaded():
    ledger = _ledger()
    client = FakeClient(fail=True)
    assert upload(client, PAIR, ledger, "u1", dry_run=False) == "FAILED"
    assert ledger.status("t1") != "UPLOADED", "must never mark uploaded without a 2xx"


def test_escalates_after_max_attempts_and_stops_posting():
    ledger = _ledger()
    for _ in range(MAX_ATTEMPTS):
        ledger.record("t1", "anthropic:invoice A", "FAILED")
    client = FakeClient()
    assert upload(client, PAIR, ledger, "u1", dry_run=False) == "ESCALATED"
    assert client.posts == [], "escalated items must not be retried forever"


def test_ledger_persists_across_instances():
    path = Path(tempfile.mkdtemp()) / "ledger.json"
    a = Ledger(path)
    a.record("t1", "p", "UPLOADED")
    a.save()
    assert Ledger(path).status("t1") == "UPLOADED"


if __name__ == "__main__":
    print("Running upload tests")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok {name}")
    print("\nAll upload tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_upload.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'upload'`

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/upload.py`:

```python
#!/usr/bin/env python3.12
"""Upload a matched receipt to Ramp and record the outcome."""

import hashlib
import json
from pathlib import Path

from queue import has_receipt

MAX_ATTEMPTS = 2
RECEIPT_WRITE = ["receipts:write"]


def idempotency_key(transaction_id: str, provenance: str) -> str:
    return hashlib.sha256(f"{transaction_id}|{provenance}".encode()).hexdigest()


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: dict[str, list[dict]] = {}
        if self.path.exists():
            self.entries = json.loads(self.path.read_text())

    def record(self, txn_id: str, provenance: str, status: str) -> None:
        self.entries.setdefault(txn_id, []).append(
            {"provenance": provenance, "status": status}
        )

    def attempts(self, txn_id: str) -> int:
        return len(self.entries.get(txn_id, []))

    def status(self, txn_id: str) -> str | None:
        rows = self.entries.get(txn_id)
        return rows[-1]["status"] if rows else None

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=2))


def upload(client, pairing, ledger: Ledger, user_id: str, dry_run: bool) -> str:
    txn = pairing.transaction

    if dry_run:
        return "DRY_RUN"

    # Re-read Ramp: the receipt may have landed since the queue was built.
    if has_receipt(client, txn.id):
        ledger.record(txn.id, pairing.receipt.provenance, "SKIPPED")
        return "SKIPPED"

    if ledger.attempts(txn.id) >= MAX_ATTEMPTS and ledger.status(txn.id) != "UPLOADED":
        ledger.record(txn.id, pairing.receipt.provenance, "ESCALATED")
        return "ESCALATED"

    fields = {
        "idempotency_key": idempotency_key(txn.id, pairing.receipt.provenance),
        "transaction_id": txn.id,
        "user_id": user_id,
    }
    try:
        client.post_multipart(
            "/developer/v1/receipts", fields, pairing.receipt.pdf_bytes, RECEIPT_WRITE
        )
    except Exception:
        ledger.record(txn.id, pairing.receipt.provenance, "FAILED")
        return "FAILED"

    ledger.record(txn.id, pairing.receipt.provenance, "UPLOADED")
    return "UPLOADED"
```

- [ ] **Step 4: Add `post_multipart` to `RampClient`**

Append to `skills/receipts/scripts/ramp_client.py`:

```python
    def post_multipart(self, path: str, fields: dict, file_bytes: bytes, scopes: list[str]) -> dict:
        boundary = "----ReceiptsBoundary" + hashlib.sha1(file_bytes[:64]).hexdigest()[:16]
        parts = []
        for key, value in fields.items():
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()
            )
        parts.append(
            f"--{boundary}\r\nContent-Disposition: attachment; name=\"file\"; "
            f"filename=\"receipt.pdf\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
        )
        parts.append(file_bytes + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        return self._request(
            f"{self.base_url}{path}",
            headers={
                "Authorization": f"Bearer {self.token(scopes)}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
            body=body,
        )
```

Add `import hashlib` to the imports at the top of `ramp_client.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_upload.py && python3.12 skills/receipts/tests/test_ramp_client.py`
Expected: both print their passing summary.

- [ ] **Step 6: Commit**

```bash
git add skills/receipts/scripts/upload.py skills/receipts/scripts/ramp_client.py skills/receipts/tests/test_upload.py
git commit -m "feat(receipts): add idempotent upload with ledger and escalation cap"
```

---

### Task 8: CLI and report

**Files:**
- Create: `skills/receipts/scripts/run.py`
- Create: `skills/receipts/tests/test_run.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7
- Produces:
  - `build_report(pairings: list[Pairing], results: dict[str, str], skipped_sources: list[str]) -> str`
  - `main(argv: list[str]) -> int`

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_run.py`:

```python
#!/usr/bin/env python3.12
"""Tests for the report. Degraded sources must be announced, never silent."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from match import AMBIGUOUS, CONFIDENT, UNFOUND, Pairing
from queue import Transaction
from run import build_report
from sources.base import Receipt

T1 = Transaction("t1", "Anthropic", 108500, "2026-07-19")
R1 = Receipt("anthropic", 108500, "2026-07-19", b"%PDF", "anthropic:invoice A")
T2 = Transaction("t2", "GoDaddy", 2178, "2026-07-30")


def test_report_announces_a_skipped_source_on_its_own_line():
    text = build_report([], {}, skipped_sources=["ANTHROPIC: not authenticated"])
    assert "SOURCE ANTHROPIC: SKIPPED (not authenticated)" in text


def test_report_says_so_when_no_sources_were_skipped():
    text = build_report([Pairing(T1, R1, CONFIDENT, "")], {"t1": "DRY_RUN"}, [])
    assert "SKIPPED" not in text


def test_report_lists_unfound_transactions_with_amounts():
    text = build_report([Pairing(T2, None, UNFOUND, "no receipt in any source")], {}, [])
    assert "GoDaddy" in text
    assert "$21.78" in text


def test_report_separates_ambiguous_from_actionable():
    pairs = [
        Pairing(T1, R1, CONFIDENT, ""),
        Pairing(T2, None, AMBIGUOUS, "4 transactions vs 3 receipts at $214.56"),
    ]
    text = build_report(pairs, {"t1": "DRY_RUN"}, [])
    assert "4 transactions vs 3 receipts" in text
    assert AMBIGUOUS in text


if __name__ == "__main__":
    print("Running run tests")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok {name}")
    print("\nAll run tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_run.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'run'`

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/run.py`:

```python
#!/usr/bin/env python3.12
"""`/receipts` entry point. Dry run by default."""

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

from match import AMBIGUOUS, BALANCED, CONFIDENT, UNFOUND, match
from queue import missing_receipts
from ramp_client import RampAuthError, RampClient, RampConfigError
from sources.base import SourceUnavailable, load_sources
from upload import Ledger, upload

LEDGER_PATH = Path(os.path.expanduser("~/.claude-receipts-ledger.json"))
ACTIONABLE = (CONFIDENT, BALANCED)


def build_report(pairings, results, skipped_sources) -> str:
    lines = ["# Receipts → Ramp", ""]

    for note in skipped_sources:
        name, _, reason = note.partition(": ")
        lines.append(f"SOURCE {name}: SKIPPED ({reason})")
    if skipped_sources:
        lines.append("")

    ready = [p for p in pairings if p.outcome in ACTIONABLE]
    if ready:
        lines.append(f"## Ready ({len(ready)})")
        for p in ready:
            t = p.transaction
            status = results.get(t.id, "PENDING")
            tag = f" [{p.outcome}]" if p.outcome == BALANCED else ""
            lines.append(
                f"- {t.date}  {t.merchant}  ${t.amount_cents/100:,.2f}  "
                f"← {p.receipt.provenance}  {status}{tag}"
            )
        lines.append("")

    blocked = [p for p in pairings if p.outcome == AMBIGUOUS]
    if blocked:
        lines.append(f"## Needs your call ({len(blocked)})")
        for p in blocked:
            t = p.transaction
            lines.append(f"- {t.date}  {t.merchant}  ${t.amount_cents/100:,.2f}  {AMBIGUOUS}: {p.note}")
        lines.append("")

    unfound = [p for p in pairings if p.outcome == UNFOUND]
    if unfound:
        lines.append(f"## No receipt found ({len(unfound)})")
        for p in unfound:
            t = p.transaction
            lines.append(f"- {t.date}  {t.merchant}  ${t.amount_cents/100:,.2f}")
        lines.append("")

    if not pairings:
        lines.append("Nothing missing a receipt in this window.")

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="receipts")
    ap.add_argument("--send", action="store_true", help="execute (default is dry run)")
    ap.add_argument("--since", default=None, help="ISO date; default 90 days ago")
    ap.add_argument("--until", default=None, help="ISO date; default today")
    args = ap.parse_args(argv)

    today = dt.date.today()
    since = args.since or (today - dt.timedelta(days=90)).isoformat()
    until = args.until or today.isoformat()

    try:
        client = RampClient.from_env()
    except RampConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    user_id = os.environ.get("RAMP_USER_ID")
    if args.send and not user_id:
        print("ERROR: RAMP_USER_ID is required to upload. Add it to .env.", file=sys.stderr)
        return 2

    try:
        txns = missing_receipts(client, since, until)
    except RampAuthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    receipts, skipped = [], []
    for src in load_sources():
        try:
            receipts.extend(src.fetch(since, until))
        except SourceUnavailable as exc:
            skipped.append(f"{type(src).__name__.replace('Source', '').upper()}: {exc}")

    pairings = match(txns, receipts)
    ledger = Ledger(LEDGER_PATH)
    results = {}
    for p in pairings:
        if p.outcome not in ACTIONABLE:
            continue
        results[p.transaction.id] = upload(client, p, ledger, user_id or "", dry_run=not args.send)
    ledger.save()

    print(build_report(pairings, results, skipped))
    if not args.send:
        print("\nDry run — nothing uploaded. Re-run with --send to execute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_run.py`
Expected: `All run tests passed.`

- [ ] **Step 5: Run the whole suite**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 -m pytest skills/receipts/tests/ -v`
Expected: all tests pass under pytest collection as well as standalone.

- [ ] **Step 6: Commit**

```bash
git add skills/receipts/scripts/run.py skills/receipts/tests/test_run.py
git commit -m "feat(receipts): add CLI with dry-run default and degradation reporting"
```

---

### Task 9: Live smoke test and documentation

**Files:**
- Create: `skills/receipts/tests/smoke_live.py`
- Modify: `skills/receipts/SKILL.md` (full usage + setup)
- Modify: `CLAUDE.md` (add `/receipts` to the command table)

**Interfaces:**
- Consumes: everything
- Produces: `smoke_live.py` — manual-only, hits real endpoints, asserts no fabricated success

- [ ] **Step 1: Write the live smoke test**

Create `skills/receipts/tests/smoke_live.py`:

```python
#!/usr/bin/env python3.12
"""Live smoke test — NOT run by the unit suite. Hits real endpoints.

Run: python3.12 skills/receipts/tests/smoke_live.py

This is what catches Anthropic changing the invoices endpoint shape, which is
the single most likely way this skill breaks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sources.anthropic import SOURCE


def main() -> int:
    payload = SOURCE._listing()
    invoices = payload.get("invoices")
    assert isinstance(invoices, list), f"expected invoices[], got {type(invoices)}"
    assert invoices, "endpoint returned zero invoices — shape may have changed"

    rows = SOURCE.parse_invoices(payload)
    assert rows, "parse_invoices dropped everything — field names may have changed"
    for field in ("amount_cents", "date", "pdf_url", "provenance"):
        assert field in rows[0], f"missing {field}"

    pdf = SOURCE._download(rows[0]["pdf_url"])
    assert pdf.startswith(b"%PDF"), f"not a PDF: {pdf[:16]!r}"

    print(f"OK  {len(invoices)} invoices, {len(rows)} paid with PDFs")
    print(f"OK  downloaded {len(pdf):,} bytes from {rows[0]['provenance']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Authenticate the browser profile, then run it**

Run:
```bash
cd ~/nsls-skills/nsls-personal-toolkit
python3.12 skills/receipts/scripts/sources/anthropic.py --login   # sign in once
python3.12 skills/receipts/tests/smoke_live.py
```
Expected: two `OK` lines. As of 2026-08-01 the live data had 100 invoices between 2026-04-29 and 2026-07-23, so `len(invoices)` should be substantial.

- [ ] **Step 3: Provision Ramp credentials and verify the queue against reality**

In Ramp → Settings → Developer API, create an app granting **`transactions:read`, `receipts:read`, `receipts:write`**. Put the id and secret in `.env` as `RAMP_CLIENT_ID` / `RAMP_CLIENT_SECRET`, and your Ramp user id as `RAMP_USER_ID`.

**Never echo these values in a shell command.** To confirm they loaded:
```bash
python3.12 -c "import os; print({k: len(os.environ.get(k,'')) for k in ('RAMP_CLIENT_ID','RAMP_CLIENT_SECRET','RAMP_USER_ID')})"
```

Then run the dry run:
```bash
python3.12 skills/receipts/scripts/run.py
```
Expected: a report ending in `Dry run — nothing uploaded.` Cross-check a handful of `## No receipt found` entries against Ramp's UI to confirm the set difference is right **before** anyone runs `--send`.

- [ ] **Step 4: Expand SKILL.md**

Replace `skills/receipts/SKILL.md` body (keep the frontmatter from Task 1) with usage, the setup steps from Step 3, the four match outcomes, and a troubleshooting section covering: `RampConfigError` → credentials missing; `SOURCE ANTHROPIC: SKIPPED` → run `anthropic.py --login`; `ESCALATED` → attach manually in Ramp, the skill will not retry.

- [ ] **Step 5: Register the command in CLAUDE.md**

Add a row to the command table: `| `/receipts` | Find Ramp transactions missing receipts, source them from Gmail or vendor portals, upload to Ramp (dry run by default; `--send` executes) |`

- [ ] **Step 6: Commit**

```bash
git add skills/receipts CLAUDE.md
git commit -m "docs(receipts): add live smoke test and skill documentation"
```

---

## Self-Review Notes

**Spec coverage:** queue set-difference → Task 2. Pluggable sources → Tasks 3–5. Four match outcomes incl. BALANCED zip and AMBIGUOUS non-assignment → Task 6. Idempotency key, ledger, escalation cap, never-mark-uploaded-without-2xx → Task 7. Dry-run default, partial-failure announcement, hard stop on Ramp 401 → Task 8. Live smoke test, real-data fixtures → Tasks 6 and 9.

**Known deviation from the spec:** the spec's `sources/*.py` contract said `fetch(since)`; this plan uses `fetch(since, until)` so sources can honour the `--until` flag. Signature is consistent across Tasks 3, 4, 5, and 8.

**Deliberately unverified until build time:** the exact `gws gmail search` subcommand and flags (Task 5, Step 5 is an explicit verification gate). Everything Ramp and Anthropic is verified against live responses or the published OpenAPI spec.
