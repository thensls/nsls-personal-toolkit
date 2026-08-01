# Receipts → Ramp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/receipts` — find Ramp transactions missing receipts, fetch each receipt from Anthropic's billing API or Gmail, and upload it to Ramp against the exact transaction.

**Architecture:** Shell out to the authenticated `ramp` CLI (no Developer API credentials exist). Build the queue by looping the authoritative per-transaction `transactions missing` check. Fetch receipts from pluggable sources. Match on merchant + amount + date with explicit collision handling. Upload with an idempotency key. Dry run by default.

**Tech Stack:** Python 3.12, stdlib only, `ramp` CLI 0.2.4, `gws` CLI for Gmail.

**Spec:** `docs/specs/2026-08-01-receipts-to-ramp-design.md`

> **Rewritten 2026-08-01** after probing live Ramp data. The prior version assumed
> Developer API client credentials, a `receipts:read` set-difference queue, and email
> forwarding — all three are wrong. See Global Constraints.

## Global Constraints

- **Python 3.12.** Shebang `#!/usr/bin/env python3.12`. Toolkit convention.
- **Tests are dual-mode.** Plain `assert`, `test_*` functions (pytest 9.0.2 collects them), plus an `if __name__ == "__main__":` block that runs each and prints a summary.
- **NEVER inline a secret in a Bash command** (repo `CLAUDE.md`). Print lengths, never values.
- **No new pip dependencies.** stdlib `subprocess`, `json`, `base64`, `urllib`.
- **There are no Ramp API credentials.** That page is gated to admin/owner. All Ramp access goes through the `ramp` CLI at `~/.local/bin/ramp` (v0.2.4), authenticated as Kevin via `ramp auth login`. Env already defaults to **production**.
- **Every `ramp` command requires `--rationale "<text>"`.** It lands in Ramp's audit log. Write honest ones — they are read by humans.
- **⚠️ `missing_items` in `transactions list` is ALWAYS `null`.** It means *not computed*, not *nothing missing*. Trusting it produces a confidently empty queue while the Ramp UI shows 28 items. **The only ground truth is per-transaction:**
  ```
  ramp transactions missing <uuid> --rationale "..."
  → { "missing_receipt": bool, "missing_memo": bool, "missing_accounting_items": [] }
  ```
- **Scopes granted** on Kevin's key: `transactions:read`, `transactions:write`, `receipts:write`, `memos:read`, `accounting:read`, `accounting:write`, `trips:read`. **NOT granted: `receipts:read`, `memos:write`.**
- **Backlog reaches back to at least 2026-02-09.** Default window must be wide. Verified live queue on 2026-08-01: **28 transactions, $10,832.29**.
- **Anthropic billing facts** (verified live 2026-08-01):
  - `GET https://claude.ai/api/stripe/{org}/invoices?limit=100&page=` → `{invoices:[{total (cents), created_ts, status, invoice_pdf_url}], has_more, next_page}`
  - NSLS org uuid `13e93397-1064-4c51-af05-279821a5bf9c`
  - `invoice_pdf_url` resolves with **no authentication** (verified 200, valid PDF, 33,227 bytes)
- **Amounts are integer cents everywhere.** The CLI returns `amount` as a display string like `"$1,085.00"`. Parse at the boundary; never carry floats.
- **Out of scope:** memos and accounting coding. Zero of 145 transactions were missing a memo. See the shelved `2026-08-01-memos-and-coding-design.md`.

### Target repo: `nsls-builder-toolkit` (org-wide), not the personal toolkit

Build in `~/nsls-skills/nsls-builder-toolkit/skills/receipts/` (same `skills/<name>/scripts/` + `tests/` layout, 61 skills, `thensls/nsls-builder-toolkit`, changes land via PR). All task paths below are relative to that repo.

Being org-wide changes four things — **every one of these is a way the skill silently does nothing for a colleague while working perfectly for Kevin:**

1. **Nothing about Kevin may be hardcoded.** The Anthropic org uuid `13e93397-…` is NSLS-specific. Read it from `ANTHROPIC_ORG_UUID`, else discover it at runtime, else raise `SourceUnavailable` with a message naming the env var. Never fall back to a literal.
2. **Most builders are not Anthropic org admins.** For them the invoices endpoint returns 403, not data. That must surface as `SOURCE ANTHROPIC: SKIPPED (not an org admin)` — a plain user should still get full value from the Gmail source.
3. **Ramp roles differ.** `--transactions_to_retrieve my_transactions` is correct and portable; `all_transactions_across_entire_business` requires admin and must never be the default.
4. **Windows parity.** Toolkit hooks mirror `.py`/`.sh`/`.ps1`. This skill is pure Python, so the exposure is path resolution: always `shutil.which(...)` first and `os.path.expanduser` after — never a bare `~/.local/bin/ramp`. Ledger and Playwright-profile paths must go through `expanduser` too.

---

### Task 1: Ramp CLI wrapper

**Files:**
- Create: `skills/receipts/SKILL.md`
- Create: `skills/receipts/scripts/ramp.py`
- Create: `skills/receipts/tests/test_ramp.py`

**Interfaces:**
- Produces:
  - `RampError(Exception)`, `RampAuthError(RampError)`
  - `run(args: list[str], rationale: str) -> list[dict]` — invokes the CLI, returns `data`
  - `parse_amount(text: str) -> int` — `"$1,085.00"` → `108500`
  - `RAMP_BIN` — resolved path to the binary

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_ramp.py`:

```python
#!/usr/bin/env python3.12
"""Tests for ramp.py — the CLI wrapper."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ramp
from ramp import RampAuthError, RampError, parse_amount, run


class FakeProc:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def test_parse_amount_handles_thousands_and_cents():
    assert parse_amount("$1,085.00") == 108500
    assert parse_amount("$214.56") == 21456
    assert parse_amount("$50.00") == 5000


def test_parse_amount_rejects_unparseable():
    try:
        parse_amount("n/a")
    except RampError:
        return
    raise AssertionError("expected RampError on unparseable amount")


def test_run_injects_rationale():
    payload = json.dumps({"schema_version": "1.0", "data": [{"ok": True}]})
    seen = {}

    def fake(cmd, **kw):
        seen["cmd"] = cmd
        return FakeProc(payload)

    with patch("subprocess.run", side_effect=fake):
        out = run(["users", "me"], rationale="why I am calling")

    assert out == [{"ok": True}]
    assert "--rationale" in seen["cmd"]
    assert "why I am calling" in seen["cmd"]
    assert "-o" in seen["cmd"] and "json" in seen["cmd"]


def test_run_raises_on_error_object_despite_exit_zero():
    payload = json.dumps({"error": {"code": 2, "message": "Missing required flags: ID"}, "data": []})
    with patch("subprocess.run", return_value=FakeProc(payload)):
        try:
            run(["transactions", "missing"], rationale="x")
        except RampError as exc:
            assert "Missing required flags" in str(exc)
            return
    raise AssertionError("error object with exit 0 must still raise")


def test_run_raises_auth_error_distinctly():
    payload = json.dumps({"error": {"code": 2, "message": "not authenticated"}, "data": []})
    with patch("subprocess.run", return_value=FakeProc(payload)):
        try:
            run(["users", "me"], rationale="x")
        except RampAuthError:
            return
    raise AssertionError("auth failures must raise RampAuthError, not bare RampError")


def test_run_tolerates_leading_banner_before_json():
    payload = "Using keyring backend: keyring\n" + json.dumps({"data": [{"ok": 1}]})
    with patch("subprocess.run", return_value=FakeProc(payload)):
        assert run(["x"], rationale="y") == [{"ok": 1}]


if __name__ == "__main__":
    print("Running ramp wrapper tests")
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"  ok {n}")
    print("\nAll ramp wrapper tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_ramp.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'ramp'`

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/ramp.py`:

```python
#!/usr/bin/env python3.12
"""Wrapper around the authenticated `ramp` CLI.

There are no Ramp Developer API credentials — that page is gated to admin/owner.
All access goes through the CLI, authenticated as the user via `ramp auth login`.
"""

import json
import os
import re
import shutil
import subprocess

RAMP_BIN = shutil.which("ramp") or os.path.expanduser("~/.local/bin/ramp")
AMOUNT = re.compile(r"-?\$?\s?([0-9][0-9,]*\.[0-9]{2})")
AUTH_HINTS = ("not authenticated", "unauthorized", "401", "auth", "login")


class RampError(Exception):
    """The Ramp CLI refused or returned an error object."""


class RampAuthError(RampError):
    """Ramp auth is dead — run `ramp auth login`."""


def parse_amount(text: str) -> int:
    m = AMOUNT.search(str(text or ""))
    if not m:
        raise RampError(f"Cannot parse amount from {text!r}")
    return round(float(m.group(1).replace(",", "")) * 100)


def run(args: list[str], rationale: str) -> list[dict]:
    if not os.path.exists(RAMP_BIN):
        raise RampError(
            "`ramp` CLI not found. Install: curl -fsSL https://agents.ramp.com/install.sh | sh"
        )
    cmd = [RAMP_BIN, *args, "--rationale", rationale, "-o", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    # The CLI prints a keyring banner before JSON, and reports errors as a JSON
    # object with exit code 0. Both must be handled.
    start = proc.stdout.find("{")
    if start < 0:
        raise RampError(f"No JSON from ramp {' '.join(args)}: {proc.stderr[:200]}")
    payload = json.loads(proc.stdout[start:])

    if payload.get("error"):
        msg = str(payload["error"].get("message", ""))
        if any(h in msg.lower() for h in AUTH_HINTS):
            raise RampAuthError(f"Ramp auth failed: {msg[:200]} — run `ramp auth login`")
        raise RampError(f"ramp {' '.join(args)}: {msg[:200]}")

    return payload.get("data", [])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_ramp.py`
Expected: `All ramp wrapper tests passed.`

- [ ] **Step 5: Verify against the live CLI**

Run: `~/.local/bin/ramp users me --rationale "Verify the receipts skill can reach Ramp as the expected user" -o json`
Expected: JSON containing `kprentiss@nsls.org`. If it reports an auth error, run `ramp auth login` first.

- [ ] **Step 6: Create SKILL.md**

Create `skills/receipts/SKILL.md`. **Do not set `disable-model-invocation`** — it makes the skill invisible in new sessions.

```markdown
---
name: receipts
description: Find Ramp transactions missing receipts, fetch each receipt from Anthropic's billing API or Gmail, and upload it to Ramp against the exact transaction. Use when the user says "receipts", "/receipts", "missing receipts", "Ramp needs a receipt", "receipt cleanup", or forwards a Ramp "transaction needs a receipt" nag. Dry run by default.
---

# Receipts → Ramp

Clears Ramp's missing-receipt queue. Dry run by default; `--send` executes.

## Usage

- `/receipts` — show the plan, change nothing
- `/receipts --send` — execute
- `/receipts --since 2026-01-01` — widen the window (default: 2026-01-01)

Requires `ramp auth login`. Gmail sourcing additionally requires `gws auth login`.
```

- [ ] **Step 7: Commit**

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/receipts
git commit -m "feat(receipts): add ramp CLI wrapper and skill scaffold"
```

---

### Task 2: The missing-receipt queue

**Files:**
- Create: `skills/receipts/scripts/queue.py`
- Create: `skills/receipts/tests/test_queue.py`

**Interfaces:**
- Consumes: `run`, `parse_amount`, `RampError` from Task 1
- Produces:
  - `@dataclass(frozen=True) class Transaction: id: str; merchant: str; amount_cents: int; date: str`
  - `list_transactions(since: str, until: str) -> list[Transaction]` — paginates
  - `needs_receipt(txn_id: str) -> bool` — the authoritative per-transaction check
  - `missing_receipts(since: str, until: str, progress=None) -> list[Transaction]`

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_queue.py`:

```python
#!/usr/bin/env python3.12
"""Tests for queue.py.

Guards the single most dangerous bug in this skill: trusting `missing_items`
from `transactions list`, which is ALWAYS null and means "not computed".
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from queue import Transaction, missing_receipts

PAGE = {
    "transactions": [
        {"transaction_uuid": "t1", "merchant_name": "Anthropic", "amount": "$214.56",
         "transaction_time": "2026-07-23T10:00:00+00:00", "missing_items": None},
        {"transaction_uuid": "t2", "merchant_name": "Macroscope", "amount": "$50.00",
         "transaction_time": "2026-07-30T10:00:00+00:00", "missing_items": None},
    ],
    "total_count": 2,
    "next_page_cursor": None,
}


def test_does_not_trust_missing_items_field():
    """missing_items is null for BOTH rows; only t1 actually needs a receipt."""
    def fake_run(args, rationale):
        if args[1] == "list":
            return [PAGE]
        return [{"missing_receipt": args[2] == "t1", "missing_memo": False,
                 "missing_accounting_items": []}]

    with patch("queue.run", side_effect=fake_run):
        out = missing_receipts("2026-01-01", "2026-08-01")

    assert [t.id for t in out] == ["t1"], (
        "must use per-transaction `transactions missing`, not the null missing_items field"
    )


def test_returns_empty_when_nothing_needs_a_receipt():
    def fake_run(args, rationale):
        if args[1] == "list":
            return [PAGE]
        return [{"missing_receipt": False, "missing_memo": False, "missing_accounting_items": []}]

    with patch("queue.run", side_effect=fake_run):
        assert missing_receipts("2026-01-01", "2026-08-01") == []


def test_parses_amount_to_integer_cents():
    def fake_run(args, rationale):
        if args[1] == "list":
            return [PAGE]
        return [{"missing_receipt": True, "missing_memo": False, "missing_accounting_items": []}]

    with patch("queue.run", side_effect=fake_run):
        out = missing_receipts("2026-01-01", "2026-08-01")
    assert out[0].amount_cents == 21456
    assert isinstance(out[0].amount_cents, int)


def test_normalizes_date_to_iso():
    def fake_run(args, rationale):
        if args[1] == "list":
            return [PAGE]
        return [{"missing_receipt": True, "missing_memo": False, "missing_accounting_items": []}]

    with patch("queue.run", side_effect=fake_run):
        out = missing_receipts("2026-01-01", "2026-08-01")
    assert out[0].date == "2026-07-23"


def test_follows_pagination_cursor():
    p1 = {"transactions": PAGE["transactions"][:1], "next_page_cursor": "CUR"}
    p2 = {"transactions": PAGE["transactions"][1:], "next_page_cursor": None}
    pages = [p1, p2]
    calls = []

    def fake_run(args, rationale):
        if args[1] == "list":
            calls.append(args)
            return [pages[len(calls) - 1]]
        return [{"missing_receipt": True, "missing_memo": False, "missing_accounting_items": []}]

    with patch("queue.run", side_effect=fake_run):
        out = missing_receipts("2026-01-01", "2026-08-01")

    assert len(out) == 2
    assert any("CUR" in a for a in calls[1]), "second page must pass next_page_cursor"


if __name__ == "__main__":
    print("Running queue tests")
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"  ok {n}")
    print("\nAll queue tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_queue.py`
Expected: FAIL — `queue.py` has no `missing_receipts`. (Note: Python has a stdlib `queue`; the `sys.path.insert(0, ...)` puts our scripts dir first so ours wins.)

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/queue.py`:

```python
#!/usr/bin/env python3.12
"""Build the missing-receipt queue from Ramp.

⚠️ `missing_items` in `transactions list` is ALWAYS null — it means "not computed",
not "nothing missing". Trusting it yields an empty queue while the Ramp UI shows 28
items. The only ground truth is `ramp transactions missing <uuid>`, one call per
transaction. Slow, but correct.
"""

from dataclasses import dataclass

from ramp import parse_amount, run

LIST_WHY = "Audit which of my transactions still need a receipt, to attach them automatically"
CHECK_WHY = "Verify whether this specific transaction still needs a receipt before attaching one"


@dataclass(frozen=True)
class Transaction:
    id: str
    merchant: str
    amount_cents: int
    date: str  # ISO yyyy-mm-dd


def list_transactions(since: str, until: str) -> list[Transaction]:
    out, cursor = [], None
    while True:
        args = [
            "transactions", "list",
            "--transactions_to_retrieve", "my_transactions",
            "--from_date", since, "--to_date", until,
            "--page_size", "100",
        ]
        if cursor:
            args += ["--next_page_cursor", cursor]

        page = run(args, rationale=LIST_WHY)[0]
        for t in page.get("transactions", []):
            out.append(
                Transaction(
                    id=t["transaction_uuid"],
                    merchant=t.get("merchant_name") or "",
                    amount_cents=parse_amount(t.get("amount")),
                    date=(t.get("transaction_time") or "")[:10],
                )
            )
        cursor = page.get("next_page_cursor")
        if not cursor:
            return out


def needs_receipt(txn_id: str) -> bool:
    row = run(["transactions", "missing", txn_id], rationale=CHECK_WHY)[0]
    return bool(row.get("missing_receipt"))


def missing_receipts(since: str, until: str, progress=None) -> list[Transaction]:
    txns = list_transactions(since, until)
    out = []
    for i, t in enumerate(txns, 1):
        if progress:
            progress(i, len(txns))
        if needs_receipt(t.id):
            out.append(t)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_queue.py`
Expected: `All queue tests passed.`

- [ ] **Step 5: Verify against live Ramp**

Run a one-off script that calls `missing_receipts("2026-01-01", "2026-08-01")` and prints the count and dollar total.
Expected on 2026-08-01: **28 transactions, $10,832.29**, dominated by Anthropic. If you get 0, you are reading `missing_items` somewhere — go back to Step 3.

- [ ] **Step 6: Commit**

```bash
git add skills/receipts/scripts/queue.py skills/receipts/tests/test_queue.py
git commit -m "feat(receipts): build queue from per-transaction missing checks"
```

---

### Task 3: Source contract

**Files:**
- Create: `skills/receipts/scripts/sources/__init__.py`
- Create: `skills/receipts/scripts/sources/base.py`
- Create: `skills/receipts/tests/test_source_contract.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Receipt: merchant: str; amount_cents: int; date: str; pdf_bytes: bytes; provenance: str`
  - `class SourceUnavailable(Exception)`
  - `normalize_merchant(name: str) -> str`
  - `load_sources() -> list` — every `sources/*.py` module's `SOURCE`

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_source_contract.py`:

```python
#!/usr/bin/env python3.12
"""Contract applied to every source, so new vendors are covered on arrival."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sources.base import Receipt, load_sources, normalize_merchant


def test_normalize_merchant_collapses_case_and_punctuation():
    assert normalize_merchant("Anthropic, PBC") == "anthropicpbc"
    assert normalize_merchant("Neon Tech") == "neontech"
    assert normalize_merchant("ANTHROPIC") == "anthropic"


def test_receipt_is_immutable():
    r = Receipt("anthropic", 21456, "2026-07-23", b"%PDF-1.4", "anthropic:inv A")
    try:
        r.amount_cents = 1
    except AttributeError:
        return
    raise AssertionError("Receipt must be frozen")


def test_every_source_declares_normalized_merchants():
    sources = load_sources()
    assert sources, "load_sources() found no sources"
    for s in sources:
        assert isinstance(s.MERCHANTS, tuple), f"{type(s).__name__}.MERCHANTS must be a tuple"
        for m in s.MERCHANTS:
            assert m == normalize_merchant(m), f"{type(s).__name__}: {m!r} is not normalized"


def test_every_source_exposes_fetch():
    for s in load_sources():
        assert callable(getattr(s, "fetch", None)), f"{type(s).__name__} missing fetch()"


if __name__ == "__main__":
    print("Running source contract tests")
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"  ok {n}")
    print("\nAll source contract tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_source_contract.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources'`

- [ ] **Step 3: Write minimal implementation**

Create `skills/receipts/scripts/sources/__init__.py` (empty).

Create `skills/receipts/scripts/sources/base.py`:

```python
#!/usr/bin/env python3.12
"""Contract every receipt source implements."""

import importlib
import pkgutil
import re
from dataclasses import dataclass


class SourceUnavailable(Exception):
    """Source could not run — auth, network, config. Never a match failure."""


@dataclass(frozen=True)
class Receipt:
    merchant: str        # normalized
    amount_cents: int
    date: str            # ISO yyyy-mm-dd
    pdf_bytes: bytes
    provenance: str      # e.g. "anthropic:invoice 2026-07-19 108500"


def normalize_merchant(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def load_sources() -> list:
    """Every sources/*.py module exposing a SOURCE singleton."""
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
Expected: FAIL with `AssertionError: load_sources() found no sources` — correct; Task 4 makes it pass.

- [ ] **Step 5: Commit**

```bash
git add skills/receipts/scripts/sources skills/receipts/tests/test_source_contract.py
git commit -m "feat(receipts): add source contract"
```

---

### Task 4: Anthropic source

**Files:**
- Create: `skills/receipts/scripts/sources/anthropic.py`
- Create: `skills/receipts/tests/test_source_anthropic.py`

**Interfaces:**
- Produces: `SOURCE` — `AnthropicSource` with `MERCHANTS = ("anthropic", "anthropicpbc")`
  - `parse_invoices(payload: dict) -> list[dict]` — pure

This source alone covers **15 of the 22** in-window gaps.

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
        {"total": 21456, "status": "paid", "created_ts": 1784806673,
         "invoice_pdf_url": "https://pay.stripe.com/invoice/acct_X/live_A/pdf?s=ap"},
        {"total": 108500, "status": "paid", "created_ts": 1784501642,
         "invoice_pdf_url": "https://pay.stripe.com/invoice/acct_X/live_B/pdf?s=ap"},
        {"total": 9999, "status": "draft", "created_ts": 1784501000,
         "invoice_pdf_url": None},
    ],
    "has_more": False,
    "next_page": None,
}


def test_amounts_stay_integer_cents():
    rows = SOURCE.parse_invoices(PAYLOAD)
    assert rows[0]["amount_cents"] == 21456
    assert rows[1]["amount_cents"] == 108500


def test_created_ts_becomes_iso_date():
    rows = SOURCE.parse_invoices(PAYLOAD)
    assert rows[1]["date"] == "2026-07-19", rows[1]["date"]


def test_unpaid_or_pdfless_invoices_dropped():
    rows = SOURCE.parse_invoices(PAYLOAD)
    assert len(rows) == 2
    assert all(r["pdf_url"] for r in rows)


def test_provenance_is_unique_per_invoice():
    rows = SOURCE.parse_invoices(PAYLOAD)
    assert rows[0]["provenance"] != rows[1]["provenance"]
    assert "anthropic" in rows[0]["provenance"]


def test_merchants_declared():
    assert "anthropic" in SOURCE.MERCHANTS


if __name__ == "__main__":
    print("Running anthropic source tests")
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"  ok {n}")
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

Anthropic emails receipts for the subscription charges but NOTHING for
usage-credit auto-recharges — those are 15 of the 22 gaps. The listing call
needs a claude.ai session; the PDF URLs it returns are Stripe secret-token URLs
that resolve with no authentication at all (verified 2026-08-01).
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
            rows.append({
                "amount_cents": int(inv["total"]),
                "date": date,
                "pdf_url": inv["invoice_pdf_url"],
                "provenance": f"anthropic:invoice {date} {inv['total']}",
            })
        return rows

    def _listing(self, page: str = "") -> dict:
        from playwright.sync_api import sync_playwright

        url = LISTING.format(org=ORG_UUID, page=page)
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(PROFILE, headless=True)
            try:
                pg = ctx.new_page()
                resp = pg.goto(url)
                if resp is None or resp.status != 200:
                    raise SourceUnavailable(
                        "claude.ai session expired. Run: python3.12 "
                        "skills/receipts/scripts/sources/anthropic.py --login"
                    )
                return json.loads(pg.inner_text("pre") or "{}")
            finally:
                ctx.close()

    @staticmethod
    def _download(url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
        if not data.startswith(b"%PDF"):
            raise SourceUnavailable(f"Expected PDF from {url[:60]}…, got {data[:16]!r}")
        return data

    def fetch(self, since: str, until: str) -> list[Receipt]:
        rows, page, guard = [], "", 0
        while guard < 20:
            payload = self._listing(page)
            rows.extend(self.parse_invoices(payload))
            if not payload.get("has_more"):
                break
            page = payload.get("next_page") or ""
            guard += 1

        return [
            Receipt(
                merchant="anthropic",
                amount_cents=r["amount_cents"],
                date=r["date"],
                pdf_bytes=self._download(r["pdf_url"]),
                provenance=r["provenance"],
            )
            for r in rows
            if since <= r["date"] <= until
        ]


SOURCE = AnthropicSource()


def _login():
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
Expected: both pass — the contract test now finds one source.

- [ ] **Step 5: Commit**

```bash
git add skills/receipts/scripts/sources/anthropic.py skills/receipts/tests/test_source_anthropic.py
git commit -m "feat(receipts): add Anthropic billing source"
```

---

### Task 5: Matching with collision handling

**Files:**
- Create: `skills/receipts/scripts/match.py`
- Create: `skills/receipts/tests/test_match.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Pairing: transaction: Transaction; receipt: Receipt | None; outcome: str; note: str`
  - `CONFIDENT`, `BALANCED`, `AMBIGUOUS`, `UNFOUND`
  - `match(transactions, receipts, window_days: int = 3) -> list[Pairing]`

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_match.py`. Fixtures are real 2026 data.

```python
#!/usr/bin/env python3.12
"""Tests for match.py — pure, no I/O.

Fixtures are real: the four-way $214.56 collision on 2026-07-23 and the
$1,085.00 single on 2026-07-19, both from Kevin's live Ramp queue.
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
    p = match([txn("t", 108500, "2026-07-19")], [rcpt(108500, "2026-07-19", "inv-b")])
    assert p[0].outcome == CONFIDENT
    assert p[0].receipt.provenance == "inv-b"


def test_four_identical_charges_and_four_receipts_are_balanced():
    txns = [txn(f"t{i}", 21456) for i in range(4)]
    rs = [rcpt(21456, prov=f"inv-{i}") for i in range(4)]
    pairs = match(txns, rs)
    assert {p.outcome for p in pairs} == {BALANCED}
    assert len({p.receipt.provenance for p in pairs}) == 4, "each txn gets a distinct receipt"


def test_balanced_assignment_is_order_independent():
    txns = [txn(f"t{i}", 21456) for i in range(4)]
    rs = [rcpt(21456, prov=f"inv-{i}") for i in range(4)]
    a = [(p.transaction.id, p.receipt.provenance) for p in match(txns, rs)]
    b = [(p.transaction.id, p.receipt.provenance) for p in match(txns, list(reversed(rs)))]
    assert a == b


def test_four_transactions_three_receipts_assigns_nothing():
    txns = [txn(f"t{i}", 21456) for i in range(4)]
    rs = [rcpt(21456, prov=f"inv-{i}") for i in range(3)]
    pairs = match(txns, rs)
    assert {p.outcome for p in pairs} == {AMBIGUOUS}
    assert all(p.receipt is None for p in pairs), "AMBIGUOUS must never assign"


def test_no_receipt_is_unfound():
    p = match([txn("t9", 47838, "2026-06-17")], [])
    assert p[0].outcome == UNFOUND and p[0].receipt is None


def test_settlement_lag_inside_window_matches():
    p = match([txn("t", 21456, "2026-07-25")], [rcpt(21456, "2026-07-23")])
    assert p[0].outcome == CONFIDENT


def test_outside_window_does_not_match():
    p = match([txn("t", 21456, "2026-07-30")], [rcpt(21456, "2026-07-23")])
    assert p[0].outcome == UNFOUND


def test_different_merchant_never_matches():
    p = match([txn("t", 21456, merchant="Neon Tech")], [rcpt(21456, merchant="anthropic")])
    assert p[0].outcome == UNFOUND


def test_receipts_with_no_transaction_produce_no_pairings():
    assert match([], [rcpt(25908)]) == []


if __name__ == "__main__":
    print("Running match tests")
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"  ok {n}")
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


def match(transactions: list[Transaction], receipts: list[Receipt],
          window_days: int = 3) -> list[Pairing]:
    groups: dict[tuple, list[Transaction]] = defaultdict(list)
    for t in transactions:
        groups[(normalize_merchant(t.merchant), t.amount_cents)].append(t)

    used: set[int] = set()
    pairs: list[Pairing] = []

    for (merchant, cents), txns in groups.items():
        txns = sorted(txns, key=lambda t: (t.date, t.id))

        candidates = sorted(
            (r for i, r in enumerate(receipts)
             if i not in used
             and r.amount_cents == cents
             and normalize_merchant(r.merchant) == merchant
             and any(_days_apart(r.date, t.date) <= window_days for t in txns)),
            key=lambda r: (r.date, r.provenance),
        )

        if not candidates:
            pairs.extend(Pairing(t, None, UNFOUND, "no receipt in any source") for t in txns)
            continue

        if len(candidates) != len(txns):
            note = f"{len(txns)} transactions vs {len(candidates)} receipts at ${cents/100:,.2f}"
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
Expected: `All match tests passed.`

- [ ] **Step 5: Commit**

```bash
git add skills/receipts/scripts/match.py skills/receipts/tests/test_match.py
git commit -m "feat(receipts): add matching with collision handling"
```

---

### Task 6: Upload and ledger

**Files:**
- Create: `skills/receipts/scripts/upload.py`
- Create: `skills/receipts/tests/test_upload.py`

**Interfaces:**
- Produces:
  - `idempotency_key(transaction_id: str, provenance: str) -> str`
  - `Ledger(path)` with `.record()`, `.attempts()`, `.status()`, `.save()`
  - `upload(pairing, ledger, dry_run: bool) -> str` — `"UPLOADED"|"SKIPPED"|"ESCALATED"|"DRY_RUN"|"FAILED"`
  - `MAX_ATTEMPTS = 2`

The CLI takes `--idempotency_key` and `--transaction_uuid` directly, so Ramp collapses repeats server-side.

- [ ] **Step 1: Write the failing test**

Create `skills/receipts/tests/test_upload.py`:

```python
#!/usr/bin/env python3.12
"""Tests for upload.py — idempotency, escalation cap, dry-run safety."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from match import CONFIDENT, Pairing
from queue import Transaction
from sources.base import Receipt
from upload import MAX_ATTEMPTS, Ledger, idempotency_key, upload

T = Transaction("t1", "Anthropic", 21456, "2026-07-23")
R = Receipt("anthropic", 21456, "2026-07-23", b"%PDF-1.4", "anthropic:invoice A")
PAIR = Pairing(T, R, CONFIDENT, "")


def _ledger():
    return Ledger(Path(tempfile.mkdtemp()) / "ledger.json")


def test_idempotency_key_stable():
    assert idempotency_key("t1", "inv-A") == idempotency_key("t1", "inv-A")


def test_idempotency_key_differs_per_transaction():
    assert idempotency_key("t1", "inv-A") != idempotency_key("t2", "inv-A")


def test_dry_run_never_calls_ramp():
    calls = []
    with patch("upload.run", side_effect=lambda *a, **k: calls.append(a)):
        assert upload(PAIR, _ledger(), dry_run=True) == "DRY_RUN"
    assert calls == [], "dry run must not invoke the CLI"


def test_upload_passes_transaction_uuid_and_idempotency_key():
    seen = {}

    def fake(args, rationale):
        seen["args"] = args
        return [{"id": "r1"}]

    with patch("upload.needs_receipt", return_value=True):
        with patch("upload.run", side_effect=fake):
            assert upload(PAIR, _ledger(), dry_run=False) == "UPLOADED"

    assert "--transaction_uuid" in seen["args"]
    assert "t1" in seen["args"]
    assert idempotency_key("t1", "anthropic:invoice A") in seen["args"]


def test_already_receipted_is_skipped():
    with patch("upload.needs_receipt", return_value=False):
        with patch("upload.run") as r:
            assert upload(PAIR, _ledger(), dry_run=False) == "SKIPPED"
            r.assert_not_called()


def test_failure_never_marks_uploaded():
    led = _ledger()
    with patch("upload.needs_receipt", return_value=True):
        with patch("upload.run", side_effect=RuntimeError("ramp 500")):
            assert upload(PAIR, led, dry_run=False) == "FAILED"
    assert led.status("t1") != "UPLOADED"


def test_escalates_after_max_attempts():
    led = _ledger()
    for _ in range(MAX_ATTEMPTS):
        led.record("t1", "anthropic:invoice A", "FAILED")
    with patch("upload.needs_receipt", return_value=True):
        with patch("upload.run") as r:
            assert upload(PAIR, led, dry_run=False) == "ESCALATED"
            r.assert_not_called()


def test_ledger_persists():
    p = Path(tempfile.mkdtemp()) / "l.json"
    a = Ledger(p); a.record("t1", "pr", "UPLOADED"); a.save()
    assert Ledger(p).status("t1") == "UPLOADED"


if __name__ == "__main__":
    print("Running upload tests")
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"  ok {n}")
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

import base64
import hashlib
import json
from pathlib import Path

from queue import needs_receipt
from ramp import run

MAX_ATTEMPTS = 2
WHY = "Attach the receipt I located for this transaction so it clears Ramp's missing-items queue"


def idempotency_key(transaction_id: str, provenance: str) -> str:
    return hashlib.sha256(f"{transaction_id}|{provenance}".encode()).hexdigest()


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: dict[str, list[dict]] = {}
        if self.path.exists():
            self.entries = json.loads(self.path.read_text())

    def record(self, txn_id: str, provenance: str, status: str) -> None:
        self.entries.setdefault(txn_id, []).append({"provenance": provenance, "status": status})

    def attempts(self, txn_id: str) -> int:
        return len(self.entries.get(txn_id, []))

    def status(self, txn_id: str) -> str | None:
        rows = self.entries.get(txn_id)
        return rows[-1]["status"] if rows else None

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=2))


def upload(pairing, ledger: Ledger, dry_run: bool) -> str:
    txn, rec = pairing.transaction, pairing.receipt

    if dry_run:
        return "DRY_RUN"

    # Re-check Ramp: the receipt may have landed since the queue was built.
    if not needs_receipt(txn.id):
        ledger.record(txn.id, rec.provenance, "SKIPPED")
        return "SKIPPED"

    if ledger.attempts(txn.id) >= MAX_ATTEMPTS and ledger.status(txn.id) != "UPLOADED":
        ledger.record(txn.id, rec.provenance, "ESCALATED")
        return "ESCALATED"

    args = [
        "receipts", "upload",
        "--transaction_uuid", txn.id,
        "--idempotency_key", idempotency_key(txn.id, rec.provenance),
        "--filename", "receipt.pdf",
        "--content_type", "application/pdf",
        "--file_content_base64", base64.b64encode(rec.pdf_bytes).decode(),
    ]
    try:
        run(args, rationale=WHY)
    except Exception:
        ledger.record(txn.id, rec.provenance, "FAILED")
        return "FAILED"

    ledger.record(txn.id, rec.provenance, "UPLOADED")
    return "UPLOADED"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_upload.py`
Expected: `All upload tests passed.`

- [ ] **Step 5: Commit**

```bash
git add skills/receipts/scripts/upload.py skills/receipts/tests/test_upload.py
git commit -m "feat(receipts): add idempotent upload with ledger and escalation cap"
```

---

### Task 7: CLI and report

**Files:**
- Create: `skills/receipts/scripts/run.py`
- Create: `skills/receipts/tests/test_run.py`

**Interfaces:**
- Produces: `build_report(pairings, results, skipped_sources) -> str`, `main(argv) -> int`

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
T2 = Transaction("t2", "Neon Tech", 55076, "2026-08-01")


def test_skipped_source_gets_its_own_line():
    text = build_report([], {}, ["ANTHROPIC: not authenticated"])
    assert "SOURCE ANTHROPIC: SKIPPED (not authenticated)" in text


def test_no_skip_line_when_nothing_skipped():
    text = build_report([Pairing(T1, R1, CONFIDENT, "")], {"t1": "DRY_RUN"}, [])
    assert "SKIPPED" not in text


def test_unfound_listed_with_merchant_and_amount():
    text = build_report([Pairing(T2, None, UNFOUND, "no receipt")], {}, [])
    assert "Neon Tech" in text and "$550.76" in text


def test_ambiguous_note_is_surfaced():
    pairs = [Pairing(T2, None, AMBIGUOUS, "4 transactions vs 3 receipts at $214.56")]
    text = build_report(pairs, {}, [])
    assert "4 transactions vs 3 receipts" in text


def test_totals_reported():
    pairs = [Pairing(T1, R1, CONFIDENT, ""), Pairing(T2, None, UNFOUND, "")]
    text = build_report(pairs, {"t1": "DRY_RUN"}, [])
    assert "$1,635.76" in text, "must report total dollars still outstanding"


if __name__ == "__main__":
    print("Running run tests")
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"  ok {n}")
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
from ramp import RampAuthError, RampError
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

    outstanding = sum(p.transaction.amount_cents for p in pairings if p.outcome != CONFIDENT
                      or results.get(p.transaction.id) != "UPLOADED")
    lines.append(f"**{len(pairings)} transactions missing receipts — "
                 f"${outstanding/100:,.2f} outstanding**")
    lines.append("")

    ready = [p for p in pairings if p.outcome in ACTIONABLE]
    if ready:
        lines.append(f"## Ready ({len(ready)})")
        for p in ready:
            t = p.transaction
            tag = f" [{p.outcome}]" if p.outcome == BALANCED else ""
            lines.append(f"- {t.date}  {t.merchant}  ${t.amount_cents/100:,.2f}  "
                         f"← {p.receipt.provenance}  {results.get(t.id,'PENDING')}{tag}")
        lines.append("")

    for outcome, title in ((AMBIGUOUS, "Needs your call"), (UNFOUND, "No receipt found")):
        rows = [p for p in pairings if p.outcome == outcome]
        if not rows:
            continue
        lines.append(f"## {title} ({len(rows)})")
        for p in rows:
            t = p.transaction
            suffix = f"  {p.note}" if p.note else ""
            lines.append(f"- {t.date}  {t.merchant}  ${t.amount_cents/100:,.2f}{suffix}")
        lines.append("")

    if not pairings:
        lines.append("Nothing missing a receipt in this window.")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="receipts")
    ap.add_argument("--send", action="store_true", help="execute (default is dry run)")
    ap.add_argument("--since", default="2026-01-01", help="ISO date; backlog reaches to 2026-02")
    ap.add_argument("--until", default=None, help="ISO date; default today")
    args = ap.parse_args(argv)

    until = args.until or dt.date.today().isoformat()

    def progress(i, n):
        print(f"\r  checking {i}/{n}…", end="", file=sys.stderr, flush=True)

    try:
        txns = missing_receipts(args.since, until, progress=progress)
    except RampAuthError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 2
    except RampError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 2
    print("", file=sys.stderr)

    receipts, skipped = [], []
    for src in load_sources():
        try:
            receipts.extend(src.fetch(args.since, until))
        except SourceUnavailable as exc:
            skipped.append(f"{type(src).__name__.replace('Source','').upper()}: {exc}")

    pairings = match(txns, receipts)
    ledger = Ledger(LEDGER_PATH)
    results = {}
    for p in pairings:
        if p.outcome in ACTIONABLE:
            results[p.transaction.id] = upload(p, ledger, dry_run=not args.send)
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
Expected: all pass under pytest as well as standalone.

- [ ] **Step 6: Dry run against live data**

Run:
```bash
python3.12 skills/receipts/scripts/sources/anthropic.py --login   # once
python3.12 skills/receipts/scripts/run.py --since 2026-01-01
```
Expected: **28 transactions, $10,832.29 outstanding**, ~15 Anthropic rows under `## Ready`. Cross-check against the Ramp UI filter "Submission policy status = Missing items" before anyone runs `--send`.

- [ ] **Step 7: Commit**

```bash
git add skills/receipts/scripts/run.py skills/receipts/tests/test_run.py
git commit -m "feat(receipts): add CLI with dry-run default and degradation reporting"
```

---

### Task 8: Gmail source

**Files:**
- Create: `skills/receipts/scripts/sources/gmail.py`
- Create: `skills/receipts/tests/test_source_gmail.py`

Covers the non-Anthropic gaps: Neon Tech, Supabase, Zoom, Asana, Groq, OpenAI, Hex, Kie, Mysecond.

**Prerequisite:** `gws auth login -s gmail,calendar,drive`. Google auth was expired on 2026-08-01.

**Interfaces:**
- Produces: `SOURCE` — `GmailSource`, `MERCHANTS = ()` (empty = candidate for any merchant)
  - `parse_amount(text) -> int | None`, `build_query(since, until) -> str` — both pure

- [ ] **Step 1: The verified `gws` flow (confirmed live 2026-08-01, post-reauth)**

There is **no** `gws gmail search` subcommand. Query params go in `--params` as JSON. Getting one receipt PDF takes **three calls**:

```bash
# 1. list → returns ONLY {id, threadId}. No subject, date, or attachment.
gws gmail users messages list \
  --params '{"userId":"me","q":"<query>","maxResults":100}' --format json

# 2. get → headers, snippet, internalDate, and the MIME parts tree
gws gmail users messages get \
  --params '{"userId":"me","id":"<id>","format":"full"}' --format json

# 3. attachments get → base64url in .data (NOT raw bytes)
gws gmail users messages attachments get \
  --params '{"userId":"me","messageId":"<id>","id":"<attachmentId>"}' --format json
```

Verified structure of a real Anthropic receipt (`19f94f2f9efe8c87`):

```
multipart/mixed
  multipart/alternative
    text/plain   (971 b)
    text/html    (56,648 b)
  application/pdf  filename='Invoice-DSCOITDB-0021.pdf'   attachmentId=…  32,965 b
  application/pdf  filename='Receipt-2422-8527-1659.pdf'  attachmentId=…  34,104 b
```

Three facts `fetch()` must honour:

1. **PDFs are attachment IDs, not inline bytes.** `body.attachmentId` on the part; call 3 retrieves it.
2. **Decode with `base64.urlsafe_b64decode(data + "==")`.** Standard b64 fails on Gmail's URL-safe alphabet. Verified: yields 34,104 bytes starting `%PDF-1.4`.
3. **There are TWO PDFs per Anthropic email.** Prefer the one whose filename starts with `Receipt-`; fall back to `Invoice-`. Attaching the wrong one is not fatal but is wrong.

Headers come from `payload.headers[]` as `{name, value}` pairs — filter for `Subject`, `From`, `Date`. Date is also available as `internalDate` (epoch ms), which is easier to parse.

- [ ] **Step 2: Write the failing test**

Create `skills/receipts/tests/test_source_gmail.py`:

```python
#!/usr/bin/env python3.12
"""Tests for the Gmail source. Pure parsing only; fetch() is verified live."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sources.gmail import SOURCE


def test_parse_amount_handles_thousands():
    assert SOURCE.parse_amount("Total $1,085.00 paid") == 108500


def test_parse_amount_plain():
    assert SOURCE.parse_amount("Amount charged: $99.91") == 9991


def test_parse_amount_absent():
    assert SOURCE.parse_amount("used 75% of its credits") is None


def test_build_query_scopes_by_date():
    q = SOURCE.build_query("2026-07-01", "2026-07-31")
    assert "after:2026/07/01" in q and "before:2026/07/31" in q


def test_empty_merchants_means_any():
    assert SOURCE.MERCHANTS == ()


if __name__ == "__main__":
    print("Running gmail source tests")
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"  ok {n}")
    print("\nAll gmail source tests passed.")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_source_gmail.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.gmail'`

- [ ] **Step 4: Write the implementation**

Create `skills/receipts/scripts/sources/gmail.py`:

```python
#!/usr/bin/env python3.12
"""Gmail receipt source — reads receipt mail via the `gws` CLI.

MERCHANTS is empty, meaning "candidate for any merchant". Gmail is tried after
merchant-specific portal sources. Covers Neon Tech, Supabase, Zoom, Asana,
Groq, OpenAI, Hex, Kie, Mysecond — the non-Anthropic gaps.
"""

import base64
import json
import os
import re
import shutil
import subprocess

from .base import Receipt, SourceUnavailable, normalize_merchant

AMOUNT = re.compile(r"\$\s?([0-9][0-9,]*\.[0-9]{2})")
GWS = shutil.which("gws") or os.path.expanduser("~/bin/gws")


def _gws(args: list[str], params: dict) -> dict:
    if not os.path.exists(GWS):
        raise SourceUnavailable("`gws` CLI not found — see the gws skill")
    proc = subprocess.run(
        [GWS, *args, "--params", json.dumps(params), "--format", "json"],
        capture_output=True, text=True, timeout=120,
    )
    # gws prints a keyring banner before JSON and reports auth failure as a
    # JSON error object with exit code 0. Both must be handled.
    start = proc.stdout.find("{")
    if start < 0:
        raise SourceUnavailable(f"gws returned no JSON: {proc.stderr[:200]}")
    payload = json.loads(proc.stdout[start:])
    if "error" in payload:
        raise SourceUnavailable(
            f"gws: {payload['error'].get('message','')[:160]} — run `gws auth login`"
        )
    return payload


class GmailSource:
    MERCHANTS: tuple[str, ...] = ()

    def parse_amount(self, text: str) -> int | None:
        m = AMOUNT.search(text or "")
        return round(float(m.group(1).replace(",", "")) * 100) if m else None

    def build_query(self, since: str, until: str) -> str:
        return (f"after:{since.replace('-','/')} before:{until.replace('-','/')} "
                f"(subject:receipt OR subject:invoice OR subject:payment)")

    @staticmethod
    def _pdf_parts(part: dict) -> list[dict]:
        """Flatten the MIME tree to PDF parts, Receipt-* preferred over Invoice-*."""
        found = []
        if (part.get("mimeType") == "application/pdf"
                and (part.get("body") or {}).get("attachmentId")):
            found.append(part)
        for sub in part.get("parts") or []:
            found += GmailSource._pdf_parts(sub)
        return sorted(found, key=lambda p: not (p.get("filename") or "").startswith("Receipt-"))

    def fetch(self, since: str, until: str) -> list[Receipt]:
        listing = _gws(
            ["gmail", "users", "messages", "list"],
            {"userId": "me", "q": self.build_query(since, until), "maxResults": 100},
        )

        out = []
        for stub in listing.get("messages", []):
            msg = _gws(
                ["gmail", "users", "messages", "get"],
                {"userId": "me", "id": stub["id"], "format": "full"},
            )
            hdrs = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            cents = self.parse_amount(f"{hdrs.get('Subject','')} {msg.get('snippet','')}")
            parts = self._pdf_parts(msg["payload"])
            if cents is None or not parts:
                continue

            att = _gws(
                ["gmail", "users", "messages", "attachments", "get"],
                {"userId": "me", "messageId": stub["id"], "id": parts[0]["body"]["attachmentId"]},
            )
            # Gmail uses the URL-safe alphabet; standard b64decode fails here.
            pdf = base64.urlsafe_b64decode(att["data"] + "==")
            if not pdf.startswith(b"%PDF"):
                continue

            date = __import__("datetime").datetime.fromtimestamp(
                int(msg["internalDate"]) / 1000, __import__("datetime").UTC
            ).date().isoformat()

            out.append(Receipt(
                merchant=normalize_merchant(re.sub(r"<.*?>", "", hdrs.get("From", ""))),
                amount_cents=cents,
                date=date,
                pdf_bytes=pdf,
                provenance=f"gmail:msg {stub['id']}",
            ))
        return out


SOURCE = GmailSource()
```

**Note on merchant normalization:** the `From` header is `"Anthropic, PBC" <invoice+statements@…>` — the display name normalizes to `anthropicpbc`, which `match.py` will not equate with Ramp's `Anthropic` → `anthropic`. Add an alias map in this file (`anthropicpbc → anthropic`, `clay labs inc → clay`, etc.) or relax matching to prefix comparison. Verify against the real `## No receipt found` list in Step 6 and fix whatever fails to bind.

- [ ] **Step 5: Run tests**

Run: `cd ~/nsls-skills/nsls-personal-toolkit && python3.12 skills/receipts/tests/test_source_gmail.py && python3.12 skills/receipts/tests/test_source_contract.py`
Expected: both pass; the contract test now covers two sources.

- [ ] **Step 6: Dry run and confirm coverage improved**

Run: `python3.12 skills/receipts/scripts/run.py --since 2026-01-01`
Expected: the `## No receipt found` section shrinks from ~13 toward 0 as Gmail supplies the non-Anthropic receipts.

- [ ] **Step 7: Commit**

```bash
git add skills/receipts/scripts/sources/gmail.py skills/receipts/tests/test_source_gmail.py
git commit -m "feat(receipts): add Gmail receipt source"
```

---

### Task 9: Live smoke test and docs

**Files:**
- Create: `skills/receipts/tests/smoke_live.py`
- Modify: `skills/receipts/SKILL.md`, `CLAUDE.md`

- [ ] **Step 1: Write the live smoke test**

Create `skills/receipts/tests/smoke_live.py`:

```python
#!/usr/bin/env python3.12
"""Live smoke test — NOT part of the unit suite. Hits real endpoints.

Catches Anthropic changing the invoices endpoint shape and Ramp auth dying —
the two most likely ways this skill breaks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ramp import run
from sources.anthropic import SOURCE


def main() -> int:
    me = run(["users", "me"], rationale="Smoke test: confirm Ramp auth is alive")[0]
    print(f"OK  ramp auth: {me['users'][0]['email']}")

    payload = SOURCE._listing()
    invoices = payload.get("invoices")
    assert isinstance(invoices, list) and invoices, "invoices endpoint shape changed"
    rows = SOURCE.parse_invoices(payload)
    assert rows, "parse_invoices dropped everything — field names may have changed"
    pdf = SOURCE._download(rows[0]["pdf_url"])
    assert pdf.startswith(b"%PDF"), f"not a PDF: {pdf[:16]!r}"
    print(f"OK  {len(invoices)} invoices, {len(rows)} paid; downloaded {len(pdf):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it**

Run: `python3.12 skills/receipts/tests/smoke_live.py`
Expected: two `OK` lines. As of 2026-08-01 the listing had 100 invoices between 2026-04-29 and 2026-07-23.

- [ ] **Step 3: Expand SKILL.md**

Keep the Task 1 frontmatter. Add: usage, setup (`ramp auth login`, `gws auth login`, `anthropic.py --login`), the four match outcomes, and troubleshooting — `RampAuthError` → `ramp auth login`; `SOURCE ANTHROPIC: SKIPPED` → `anthropic.py --login`; `ESCALATED` → attach manually in Ramp, the skill will not retry; **empty queue but the Ramp UI shows items** → something is reading `missing_items` instead of `transactions missing`.

- [ ] **Step 4: Register in CLAUDE.md**

Add a row: `` | `/receipts` | Find Ramp transactions missing receipts, fetch them from Anthropic billing or Gmail, upload to Ramp (dry run by default; `--send` executes) | ``

- [ ] **Step 5: Commit**

```bash
git add skills/receipts CLAUDE.md
git commit -m "docs(receipts): add live smoke test and skill documentation"
```

---

### Task 10: Publish to the builder toolkit

**Files:**
- Modify: `.claude-plugin/plugin.json` (version bump)
- Modify: `README.md`, `CLAUDE.md` (skill listing)
- Verify: `skills/receipts/SKILL.md`

- [ ] **Step 1: Prove it works for someone who isn't Kevin**

The multi-user failure modes are invisible on Kevin's machine, so force each one:

```bash
cd ~/nsls-skills/nsls-builder-toolkit
# 1. No org uuid → must name the env var, not fall back to the NSLS literal
env -u ANTHROPIC_ORG_UUID python3.12 -c "
import sys; sys.path.insert(0,'skills/receipts/scripts')
from sources.anthropic import SOURCE
try: SOURCE.fetch('2026-07-01','2026-08-01')
except Exception as e: print('OK:', e)"
# 2. Ramp auth dead → RampAuthError naming `ramp auth login`, not an empty queue
# 3. gws auth dead → SOURCE GMAIL: SKIPPED line, Anthropic still runs
```

Expected: each names the fix. **If any returns an empty queue and exit 0, that is the bug** — a colleague would read it as "nothing to do."

- [ ] **Step 2: Confirm no NSLS-specific literals remain**

```bash
grep -rnE "13e93397|kprentiss|/Users/k|nsls\.org" skills/receipts/ --include=*.py --include=*.md
```
Expected: **no matches** outside doc examples clearly marked as such.

- [ ] **Step 3: Bump the plugin version**

Edit `.claude-plugin/plugin.json`: `"version": "3.1.0"` → `"3.2.0"` (new skill, backward compatible). Update `description` if it names a skill count.

- [ ] **Step 4: Add to README.md and CLAUDE.md**

One row each: `` `/receipts` `` — find Ramp transactions missing receipts, fetch them from Anthropic billing or Gmail, upload to Ramp. Dry run by default. Requires `ramp auth login`; Gmail sourcing needs `gws auth login`.

- [ ] **Step 5: Run the full suite in the toolkit repo**

Run: `cd ~/nsls-skills/nsls-builder-toolkit && python3.12 -m pytest skills/receipts/tests/ -v`
Expected: all pass. Run the full build/lint the repo uses before opening a PR — do not let a lint error reach CI.

- [ ] **Step 6: Open the PR**

```bash
git checkout -b feat/receipts-skill
git add skills/receipts .claude-plugin/plugin.json README.md CLAUDE.md
git commit -m "feat(receipts): add /receipts — Ramp missing-receipt automation"
git push -u origin feat/receipts-skill
gh pr create --title "feat(receipts): add /receipts skill" --body "..."
```

Share the **full clickable PR URL**. Then wait for Macroscope and resolve its correctness findings before merging — toolkit PRs are Kevin's to merge.

- [ ] **Step 7: Update the onboarding Google Doc**

The builder-toolkit onboarding doc must be updated whenever skills change. Add `/receipts` with its setup prerequisites (`ramp auth login`, `gws auth login`) — a skill that silently needs auth nobody was told about is the same silent-failure class as everything else in this plan.

---

## Self-Review Notes

**Spec coverage:** queue → Task 2. Sources → Tasks 3, 4, 8. Collision handling → Task 5. Idempotency, ledger, escalation cap, never-mark-uploaded-without-success → Task 6. Dry-run default, degradation announcement, hard stop on Ramp auth failure → Task 7. Live smoke → Task 9.

**Corrections from the prior version, all verified live 2026-08-01:**
1. No Developer API credentials exist — everything routes through the `ramp` CLI.
2. `missing_items` is always null; the queue must loop `transactions missing <id>`. This is the bug most likely to be reintroduced, so Task 2's first test guards it specifically.
3. `receipts:read` and `memos:write` are not granted; `receipts:write` and `transactions:write` are.
4. Email forwarding replaced by `ramp receipts upload --transaction_uuid`.
5. Memos and coding removed — zero of 145 transactions were missing a memo.
6. Default window widened to 2026-01-01; the backlog reaches 2026-02-09.

**Deliberately unverified until build time:** the `gws users messages get` response shape (Task 8, Step 1 is an explicit gate). Everything Ramp and Anthropic is verified against live responses.
