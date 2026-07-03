# KB Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small server ("KB Gateway") that holds the only GitHub credential for `thensls/nsls-knowledge`, so any SLT member can harvest into the KB from Claude Code without a GitHub account or a local clone; then rewire `/harvest-meeting` to read context and write commits through it.

**Architecture:** A standalone `aiohttp` Python service (`thensls/kb-gateway`), deployed in the existing slt-coach Railway/Doppler project. It authenticates per-member bearer tokens, serves parsed KB read-context, and applies approved edits against the **live** repo via the GitHub Git Data API as one atomic commit (author = the SLT member, committer = a dedicated GitHub App). The harvest skill keeps all its local "thinking" (Fathom → extract → map → dedup → rubric → merge → approve) and delegates only Step 1 (context) and Step 8 (write) to the gateway. Hard cut, sequenced so the gateway is dry-run-validated before the skill switches.

**Tech Stack:** Python 3.12, `aiohttp` (server + GitHub REST client), `PyJWT` + `cryptography` (GitHub App JWT → installation token), `pytest` + `pytest-asyncio`. GitHub Git Data API for atomic commits. Doppler for secrets, Railway for hosting.

**Spec:** `docs/specs/2026-05-31-kb-gateway-design.md` — read first if any task is ambiguous.

**Local working dirs:**
- Gateway service: `~/nsls-skills/kb-gateway/`
- Skill changes: `~/nsls-skills/nsls-personal-toolkit/`

**Pre-flight:**
```bash
[ -d /tmp/kbgw-deps ] || python3.12 -m pip install aiohttp pyjwt cryptography pytest pytest-asyncio --target /tmp/kbgw-deps -q
export PYTHONPATH=/tmp/kbgw-deps
```
Run gateway tests throughout with: `PYTHONPATH=/tmp/kbgw-deps python3.12 -m pytest ~/nsls-skills/kb-gateway/tests -v`

---

## File Structure

**New repo `~/nsls-skills/kb-gateway/`:**
- `config.py` — env-driven config (Doppler-injected): app id, private key, installation id, repo, branch, token registry.
- `kb_parse.py` — **pure**: parse a topic markdown file into sections; build the `/kb/context` payload; canonical `current_state` hash. (No I/O.)
- `kb_edits.py` — **pure**: apply one approved candidate to a file's text (append decision / REFINEMENT replace / Current-State guard+merge / new-topic scaffold); acronym-aware title casing. (No I/O.)
- `auth.py` — bearer-token registry + lookup; GitHub App JWT → cached installation token.
- `github_repo.py` — async GitHub client: fetch repo files (context), read a blob, and commit a set of changed files atomically via the Git Data API with ref-move retry.
- `audit.py` — append one audit record per commit.
- `handlers.py` — aiohttp request handlers: `/health`, `/kb/whoami`, `/kb/context`, `/kb/commit`.
- `app.py` — builds the aiohttp app, wires routes, reads config, starts the server.
- `requirements.txt`, `Procfile`, `railway.toml`, `.env.example`, `README.md`.
- `tests/` — `test_kb_parse.py`, `test_kb_edits.py`, `test_auth.py`, `test_commit_flow.py`, `test_handlers.py`.

**Modified in `~/nsls-skills/nsls-personal-toolkit/`:**
- `skills/harvest-meeting/SKILL.md` — Step 0 (gate), Step 1 (context via gateway), Step 6b (record base hash), Step 8 (commit via gateway).
- `skills/harvest-meeting/kb_authors.txt` — **delete** (retired; authz is server-side).
- `skills/kb-setup/SKILL.md` — **create** (configure `KB_GATEWAY_URL` + `KB_GATEWAY_TOKEN`).

**Interfaces locked here (used across tasks):**
- `kb_parse.parse_topic(text: str) -> dict | None` → `{"frontmatter": {...}, "current_state": str, "key_decisions": [str], "open_questions": [str]}`
- `kb_parse.parse_current_state(text: str) -> str`
- `kb_parse.current_state_sha256(current_state: str) -> str`
- `kb_parse.build_context(files: dict[str,str], rubric_text: str) -> dict` → `{"topics": {slug: parse_topic(...)}, "rubric": rubric_text}`
- `kb_edits.title_from_slug(slug: str) -> str`
- `kb_edits.scaffold_empty(slug: str, suggested: dict, today: str) -> str`
- `kb_edits.apply_edit(text: str | None, cand: dict, meeting: dict, today: str) -> tuple[str, dict]` → `(new_text, status)`; `status = {"topic_slug": str, "status": "ok"|"rejected", "reason": str|None, "created": bool}`
- `auth.member_for_token(registry: dict, token: str) -> dict | None` → `{"email","name"}`
- `github_repo.fetch_kb_files(session, token, repo, branch) -> tuple[str, dict[str,str]]` → `(head_sha, {slug: text})`
- `github_repo.commit_changes(session, token, repo, branch, changed: dict[str,str], message: str, author: dict) -> str` → commit sha (raises `RefMoved` to signal caller retry)

---

## Task 1: Scaffold the gateway repo

**Files:**
- Create: `~/nsls-skills/kb-gateway/requirements.txt`, `Procfile`, `railway.toml`, `.env.example`, `README.md`, `tests/__init__.py`

- [ ] **Step 1: Pre-flight halt if the target already exists**

```bash
TARGET="$HOME/nsls-skills/kb-gateway"
if [ -d "$TARGET" ]; then echo "HALT: $TARGET exists; inspect before proceeding:"; ls -la "$TARGET"; exit 1; fi
mkdir -p "$TARGET/tests"
```

- [ ] **Step 2: Write `requirements.txt`**

Path: `~/nsls-skills/kb-gateway/requirements.txt`
```
aiohttp==3.10.11
PyJWT==2.9.0
cryptography==43.0.3
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 3: Write `Procfile` and `railway.toml`** (mirror slt-coach)

Path: `~/nsls-skills/kb-gateway/Procfile`
```
web: python app.py
```
Path: `~/nsls-skills/kb-gateway/railway.toml`
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python app.py"
healthcheckPath = "/health"
healthcheckTimeout = 10
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
```

- [ ] **Step 4: Write `.env.example`**

Path: `~/nsls-skills/kb-gateway/.env.example`
```
PORT=8080
KB_REPO=thensls/nsls-knowledge
KB_BRANCH=main
GH_APP_ID=
GH_APP_INSTALLATION_ID=
GH_APP_PRIVATE_KEY=        # PEM, newlines as literal \n
KB_TOKENS={}              # JSON: {"<sha256(token)>": {"email":"x@nsls.org","name":"X"}}
```

- [ ] **Step 5: Write `tests/__init__.py` (empty) and a minimal `README.md`**

```bash
: > ~/nsls-skills/kb-gateway/tests/__init__.py
printf '# kb-gateway\n\nKB Gateway — the only holder of write access to thensls/nsls-knowledge for the harvest pipeline. See nsls-personal-toolkit/docs/specs/2026-05-31-kb-gateway-design.md.\n' > ~/nsls-skills/kb-gateway/README.md
```

- [ ] **Step 6: Init git + commit**

```bash
cd ~/nsls-skills/kb-gateway && git init -q && git add -A
git commit -q -m "chore: scaffold kb-gateway service"
```

---

## Task 2: `kb_parse.py` — topic parsing + canonical hash (TDD)

**Files:**
- Create: `~/nsls-skills/kb-gateway/kb_parse.py`
- Test: `~/nsls-skills/kb-gateway/tests/test_kb_parse.py`

- [ ] **Step 1: Write the failing tests**

Path: `~/nsls-skills/kb-gateway/tests/test_kb_parse.py`
```python
import kb_parse

TOPIC = """---
type: kpi
parent: "[[revenue-conversion]]"
last-updated: 2026-05-26
---

# B2C Conversion

## Current State

Response rate is the live metric. As of 2026-05-26 ~2% with NCO.

## Key Decisions

- 2026-05-26: Did a thing ([▶](https://f/?timestamp=1))

## Open Questions

- How do we measure tier-4?
"""

def test_parse_topic_sections():
    p = kb_parse.parse_topic(TOPIC)
    assert p["frontmatter"]["type"] == "kpi"
    assert p["current_state"].startswith("Response rate is the live metric.")
    assert p["current_state"].endswith("~2% with NCO.")
    assert p["key_decisions"] == ["- 2026-05-26: Did a thing ([▶](https://f/?timestamp=1))"]
    assert p["open_questions"] == ["- How do we measure tier-4?"]

def test_parse_topic_no_frontmatter_returns_none():
    assert kb_parse.parse_topic("# No frontmatter\n\n## Current State\n") is None

def test_parse_current_state_matches_parse_topic():
    assert kb_parse.parse_current_state(TOPIC) == kb_parse.parse_topic(TOPIC)["current_state"]

def test_current_state_sha256_is_stable_and_strips():
    a = kb_parse.current_state_sha256("  hello world  ")
    b = kb_parse.current_state_sha256("hello world")
    assert a == b and len(a) == 64

def test_build_context_shape():
    ctx = kb_parse.build_context({"b2c-conversion": TOPIC}, "RUBRIC")
    assert ctx["rubric"] == "RUBRIC"
    assert ctx["topics"]["b2c-conversion"]["frontmatter"]["type"] == "kpi"
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=/tmp/kbgw-deps python3.12 -m pytest ~/nsls-skills/kb-gateway/tests/test_kb_parse.py -v`
Expected: FAIL (module `kb_parse` not found).

- [ ] **Step 3: Implement `kb_parse.py`**

Path: `~/nsls-skills/kb-gateway/kb_parse.py`
```python
"""Pure parsing of KB topic files. No I/O."""
import re
import hashlib


def parse_topic(text: str) -> dict | None:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return None
    fm_raw, body = m.groups()
    fm = {}
    for line in fm_raw.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    sections = {"current_state": "", "key_decisions": [], "open_questions": []}
    cur = None
    for line in body.split("\n"):
        if line.startswith("## Current State"):
            cur = "current_state"; continue
        if line.startswith("## Key Decisions"):
            cur = "key_decisions"; continue
        if line.startswith("## Open Questions"):
            cur = "open_questions"; continue
        if line.startswith("## "):
            cur = None; continue
        if cur == "current_state":
            sections["current_state"] += line + "\n"
        elif cur in ("key_decisions", "open_questions") and line.strip().startswith("-"):
            sections[cur].append(line.strip())
    return {
        "frontmatter": fm,
        "current_state": sections["current_state"].strip(),
        "key_decisions": sections["key_decisions"],
        "open_questions": sections["open_questions"],
    }


def parse_current_state(text: str) -> str:
    m = re.search(r"## Current State\n(.*?)(?=\n## )", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def current_state_sha256(current_state: str) -> str:
    return hashlib.sha256(current_state.strip().encode("utf-8")).hexdigest()


def build_context(files: dict, rubric_text: str) -> dict:
    topics = {}
    for slug, text in files.items():
        parsed = parse_topic(text)
        if parsed is not None:
            topics[slug] = parsed
    return {"topics": topics, "rubric": rubric_text}
```

- [ ] **Step 4: Run to verify pass**

Run: `PYTHONPATH=/tmp/kbgw-deps python3.12 -m pytest ~/nsls-skills/kb-gateway/tests/test_kb_parse.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**
```bash
cd ~/nsls-skills/kb-gateway && git add kb_parse.py tests/test_kb_parse.py
git commit -q -m "feat: kb_parse — topic parsing + canonical current_state hash"
```

---

## Task 3: `kb_edits.py` — apply one candidate (TDD; this is the ported Step 8 + bug fixes)

**Files:**
- Create: `~/nsls-skills/kb-gateway/kb_edits.py`
- Test: `~/nsls-skills/kb-gateway/tests/test_kb_edits.py`

- [ ] **Step 1: Write the failing tests** (cover append, REFINEMENT, current_state guard pass/fail, new-topic scaffold+accumulate, acronym title, meeting-date stamping)

Path: `~/nsls-skills/kb-gateway/tests/test_kb_edits.py`
```python
import kb_parse
import kb_edits

MEETING = {"title": "SLT", "url": "https://f/x", "date": "2026-05-26"}
TODAY = "2026-05-31"

EXISTING = """---
type: kpi
last-updated: 2026-01-01
---

# B2C Conversion

## Current State

Old state line.

## Key Decisions

- 2026-01-06: Prior decision

## Open Questions

"""

def test_append_key_decision_uses_meeting_date_and_link():
    cand = {"topic_slug": "b2c", "section": "key_decisions", "dedup_verdict": "NEW",
            "text": "New decision", "fathom_timestamp_sec": 42}
    out, status = kb_edits.apply_edit(EXISTING, cand, MEETING, TODAY)
    assert status["status"] == "ok"
    assert "- 2026-05-26: New decision ([▶](https://f/x?timestamp=42))" in out
    assert "- 2026-01-06: Prior decision" in out          # old kept
    assert "last-updated: 2026-05-31" in out               # frontmatter bumped to today

def test_refinement_replaces_existing_line():
    cand = {"topic_slug": "b2c", "section": "key_decisions", "dedup_verdict": "REFINEMENT",
            "replace_entry": "- 2026-01-06: Prior decision", "text": "Refined decision",
            "fathom_timestamp_sec": 7}
    out, status = kb_edits.apply_edit(EXISTING, cand, MEETING, TODAY)
    assert status["status"] == "ok"
    assert "- 2026-01-06: Prior decision" not in out
    assert "- 2026-05-26: Refined decision ([▶](https://f/x?timestamp=7))" in out

def test_refinement_missing_target_rejects():
    cand = {"topic_slug": "b2c", "section": "key_decisions", "dedup_verdict": "REFINEMENT",
            "replace_entry": "- 2099-01-01: Not present", "text": "x", "fathom_timestamp_sec": 1}
    out, status = kb_edits.apply_edit(EXISTING, cand, MEETING, TODAY)
    assert status["status"] == "rejected" and "not found" in status["reason"]
    assert out == EXISTING

def test_current_state_replace_with_correct_base_hash():
    base = kb_parse.current_state_sha256("Old state line.")
    cand = {"topic_slug": "b2c", "section": "current_state", "dedup_verdict": "REFINEMENT",
            "current_state_base_sha256": base, "new_current_state": "Old state line. PLUS new.",
            "text": "merged", "fathom_timestamp_sec": 1}
    out, status = kb_edits.apply_edit(EXISTING, cand, MEETING, TODAY)
    assert status["status"] == "ok"
    assert "Old state line. PLUS new." in out

def test_current_state_rejects_on_stale_base_hash():
    cand = {"topic_slug": "b2c", "section": "current_state", "dedup_verdict": "REFINEMENT",
            "current_state_base_sha256": "deadbeef", "new_current_state": "clobber",
            "text": "merged", "fathom_timestamp_sec": 1}
    out, status = kb_edits.apply_edit(EXISTING, cand, MEETING, TODAY)
    assert status["status"] == "rejected" and "moved" in status["reason"]
    assert "Old state line." in out and "clobber" not in out

def test_new_topic_scaffold_then_accumulate():
    cand1 = {"topic_slug": "ai-builder-governance", "section": "key_decisions", "is_new_topic": True,
             "suggested_new": {"parent": "tech-debt-modernization", "type": "theme"},
             "dedup_verdict": "NEW", "text": "Decision one", "fathom_timestamp_sec": 10}
    out1, s1 = kb_edits.apply_edit(None, cand1, MEETING, TODAY)
    assert s1["status"] == "ok" and s1["created"] is True
    assert "# AI Builder Governance" in out1                 # acronym-cased title
    assert 'parent: "[[tech-debt-modernization]]"' in out1
    assert "- 2026-05-26: Decision one" in out1
    cand2 = {**cand1, "text": "Decision two", "fathom_timestamp_sec": 20}
    out2, s2 = kb_edits.apply_edit(out1, cand2, MEETING, TODAY)   # feed prior output back
    assert s2["status"] == "ok" and s2["created"] is False
    assert "Decision one" in out2 and "Decision two" in out2     # both present (accumulation)

def test_title_from_slug_acronyms():
    assert kb_edits.title_from_slug("ai-b2b-snt-roadmap") == "AI B2B SNT Roadmap"
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=/tmp/kbgw-deps python3.12 -m pytest ~/nsls-skills/kb-gateway/tests/test_kb_edits.py -v`
Expected: FAIL (module `kb_edits` not found).

- [ ] **Step 3: Implement `kb_edits.py`**

Path: `~/nsls-skills/kb-gateway/kb_edits.py`
```python
"""Pure edit logic: apply one approved candidate to a topic file's text. No I/O."""
import re
import kb_parse

ACRONYMS = {
    "ai": "AI", "b2b": "B2B", "b2c": "B2C", "snt": "SNT", "fol": "FOL",
    "ltd": "LTD", "nsls": "NSLS", "kpi": "KPI", "hr": "HR", "slt": "SLT",
    "lop": "LOP", "arpm": "ARPM", "nco": "NCO", "cs": "CS", "bi": "BI",
}


def title_from_slug(slug: str) -> str:
    return " ".join(ACRONYMS.get(w, w.capitalize()) for w in slug.split("-"))


def scaffold_empty(slug: str, suggested: dict, today: str) -> str:
    suggested = suggested or {}
    return (
        "---\n"
        f"type: {suggested.get('type', 'l3')}\n"
        f'parent: "[[{suggested.get("parent", "")}]]"\n'
        "status: stub\n"
        f"last-updated: {today}\n"
        "---\n\n"
        f"# {title_from_slug(slug)}\n\n"
        "## Current State\n\n\n"
        "## Key Decisions\n\n\n"
        "## Open Questions\n\n"
    )


def _status(slug, ok, reason=None, created=False):
    return {"topic_slug": slug, "status": "ok" if ok else "rejected",
            "reason": reason, "created": created}


def apply_edit(text, cand: dict, meeting: dict, today: str):
    slug = cand["topic_slug"]
    section = cand["section"]
    entry_date = meeting.get("date") or today
    url = meeting.get("url", "")
    ts = cand.get("fathom_timestamp_sec")
    link = f" ([▶]({url}?timestamp={ts}))" if url else ""

    created = False
    if text is None:
        text = scaffold_empty(slug, cand.get("suggested_new"), today)
        created = True

    if section in ("key_decisions", "open_questions"):
        header = "## Key Decisions" if section == "key_decisions" else "## Open Questions"
        prefix = f"- {entry_date}: " if section == "key_decisions" else "- "
        new_line = f"{prefix}{cand['text']}" + (link if section == "key_decisions" else "")
        if cand.get("dedup_verdict") == "REFINEMENT" and cand.get("replace_entry"):
            if cand["replace_entry"] not in text:
                return text, _status(slug, False, "refinement target not found")
            text = text.replace(cand["replace_entry"], new_line, 1)
        else:
            text = text.replace(header + "\n", f"{header}\n\n{new_line}\n", 1)
            text = re.sub(r"\n{3,}", "\n\n", text)

    elif section == "current_state":
        live = kb_parse.parse_current_state(text)
        if kb_parse.current_state_sha256(live) != cand.get("current_state_base_sha256"):
            return text, _status(slug, False, "current_state base moved; re-harvest")
        new_cs = cand.get("new_current_state")
        if not new_cs:
            return text, _status(slug, False, "missing new_current_state")
        # lambda replacement => new_cs is treated as a literal (no regex backreference injection)
        text = re.sub(
            r"(## Current State\n)(.*?)(?=\n## )",
            lambda m: m.group(1) + "\n" + new_cs + "\n",
            text, count=1, flags=re.DOTALL,
        )
    else:
        return text, _status(slug, False, f"unknown section {section}")

    text = re.sub(r"^(last-updated:\s*)\S+", lambda m: m.group(1) + today,
                  text, count=1, flags=re.MULTILINE)
    return text, _status(slug, True, created=created)
```

- [ ] **Step 4: Run to verify pass**

Run: `PYTHONPATH=/tmp/kbgw-deps python3.12 -m pytest ~/nsls-skills/kb-gateway/tests/test_kb_edits.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**
```bash
cd ~/nsls-skills/kb-gateway && git add kb_edits.py tests/test_kb_edits.py
git commit -q -m "feat: kb_edits — apply candidate (append/refine/current_state guard/new-topic accumulate)"
```

---

## Task 4: `auth.py` — token registry + GitHub App installation token (TDD for the pure part)

**Files:**
- Create: `~/nsls-skills/kb-gateway/auth.py`
- Test: `~/nsls-skills/kb-gateway/tests/test_auth.py`

- [ ] **Step 1: Write the failing test (token lookup is pure + unit-testable)**

Path: `~/nsls-skills/kb-gateway/tests/test_auth.py`
```python
import hashlib
import auth

def test_member_for_token_hashes_and_matches():
    tok = "secret-token-123"
    registry = {hashlib.sha256(tok.encode()).hexdigest(): {"email": "k@nsls.org", "name": "Kevin"}}
    assert auth.member_for_token(registry, tok) == {"email": "k@nsls.org", "name": "Kevin"}

def test_member_for_token_unknown_returns_none():
    assert auth.member_for_token({}, "nope") is None

def test_member_for_token_empty_returns_none():
    assert auth.member_for_token({"x": {}}, "") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=/tmp/kbgw-deps python3.12 -m pytest ~/nsls-skills/kb-gateway/tests/test_auth.py -v`
Expected: FAIL (module `auth` not found).

- [ ] **Step 3: Implement `auth.py`**

Path: `~/nsls-skills/kb-gateway/auth.py`
```python
"""Bearer-token registry lookup + GitHub App installation-token minting."""
import time
import hashlib
import jwt  # PyJWT
import aiohttp

_GITHUB_API = "https://api.github.com"
_token_cache = {"token": None, "exp": 0}


def member_for_token(registry: dict, token: str) -> dict | None:
    if not token:
        return None
    return registry.get(hashlib.sha256(token.encode("utf-8")).hexdigest())


def _app_jwt(app_id: str, private_key_pem: str) -> str:
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 540, "iss": app_id}
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


async def installation_token(session: aiohttp.ClientSession, app_id: str,
                             installation_id: str, private_key_pem: str) -> str:
    """Mint (and cache for ~50 min) a GitHub App installation token."""
    now = int(time.time())
    if _token_cache["token"] and _token_cache["exp"] - 120 > now:
        return _token_cache["token"]
    headers = {"Authorization": f"Bearer {_app_jwt(app_id, private_key_pem)}",
               "Accept": "application/vnd.github+json"}
    url = f"{_GITHUB_API}/app/installations/{installation_id}/access_tokens"
    async with session.post(url, headers=headers) as resp:
        resp.raise_for_status()
        data = await resp.json()
    _token_cache["token"] = data["token"]
    _token_cache["exp"] = now + 3000  # ~50 min
    return data["token"]
```

- [ ] **Step 4: Run to verify pass**

Run: `PYTHONPATH=/tmp/kbgw-deps python3.12 -m pytest ~/nsls-skills/kb-gateway/tests/test_auth.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**
```bash
cd ~/nsls-skills/kb-gateway && git add auth.py tests/test_auth.py
git commit -q -m "feat: auth — token registry lookup + GitHub App installation token"
```

---

## Task 5: `config.py` — env config loader

**Files:**
- Create: `~/nsls-skills/kb-gateway/config.py`

- [ ] **Step 1: Implement `config.py`**

Path: `~/nsls-skills/kb-gateway/config.py`
```python
"""Env-driven config (Doppler-injected on Railway)."""
import os
import json

PORT = int(os.environ.get("PORT", "8080"))
KB_REPO = os.environ.get("KB_REPO", "thensls/nsls-knowledge")
KB_BRANCH = os.environ.get("KB_BRANCH", "main")

GH_APP_ID = os.environ.get("GH_APP_ID", "")
GH_APP_INSTALLATION_ID = os.environ.get("GH_APP_INSTALLATION_ID", "")
# Private key PEM with literal \n escaped in the env var:
GH_APP_PRIVATE_KEY = os.environ.get("GH_APP_PRIVATE_KEY", "").replace("\\n", "\n")

# {"<sha256(token)>": {"email": "...", "name": "..."}}
TOKEN_REGISTRY = json.loads(os.environ.get("KB_TOKENS", "{}"))

RUBRIC_HEADER = "## Sensitive-Content Rubric"  # section to extract from CLAUDE.md
```

- [ ] **Step 2: Smoke-check it imports**

Run: `cd ~/nsls-skills/kb-gateway && PYTHONPATH=/tmp/kbgw-deps python3.12 -c "import config; print(config.KB_REPO)"`
Expected: `thensls/nsls-knowledge`

- [ ] **Step 3: Commit**
```bash
cd ~/nsls-skills/kb-gateway && git add config.py
git commit -q -m "feat: config — env-driven settings"
```

---

## Task 6: `github_repo.py` — async GitHub client (fetch context + atomic commit)

**Files:**
- Create: `~/nsls-skills/kb-gateway/github_repo.py`
- Test: `~/nsls-skills/kb-gateway/tests/test_commit_flow.py`

- [ ] **Step 1: Implement `github_repo.py`**

Path: `~/nsls-skills/kb-gateway/github_repo.py`
```python
"""Async GitHub client: read KB files for context; commit changed files atomically
via the Git Data API with ref-move detection."""
import base64
import aiohttp

_API = "https://api.github.com"


class RefMoved(Exception):
    """Raised when the branch ref advanced between read and update (caller retries)."""


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


async def _get(session, token, path):
    async with session.get(f"{_API}{path}", headers=_headers(token)) as r:
        r.raise_for_status()
        return await r.json()


async def _post(session, token, path, body):
    async with session.post(f"{_API}{path}", headers=_headers(token), json=body) as r:
        r.raise_for_status()
        return await r.json()


async def head_sha(session, token, repo, branch) -> str:
    data = await _get(session, token, f"/repos/{repo}/git/ref/heads/{branch}")
    return data["object"]["sha"]


async def _tree_sha(session, token, repo, commit_sha) -> str:
    data = await _get(session, token, f"/repos/{repo}/git/commits/{commit_sha}")
    return data["tree"]["sha"]


async def fetch_kb_files(session, token, repo, branch):
    """Return (head_sha, {slug: text}) for every top-level *.md whose name doesn't start with '_'.
    Also returns CLAUDE.md text under the special key '__claude_md__'."""
    sha = await head_sha(session, token, repo, branch)
    tree_sha = await _tree_sha(session, token, repo, sha)
    tree = await _get(session, token, f"/repos/{repo}/git/trees/{tree_sha}")
    files = {}
    for entry in tree.get("tree", []):
        path = entry["path"]
        if entry["type"] != "blob" or "/" in path or not path.endswith(".md"):
            continue
        blob = await _get(session, token, f"/repos/{repo}/git/blobs/{entry['sha']}")
        text = base64.b64decode(blob["content"]).decode("utf-8")
        if path == "CLAUDE.md":
            files["__claude_md__"] = text
        elif not path.startswith("_"):
            files[path[:-3]] = text  # strip '.md' -> slug
    return sha, files


async def read_file_text(session, token, repo, branch, path) -> str | None:
    """Read a single file's current text at branch HEAD, or None if absent."""
    try:
        data = await _get(session, token, f"/repos/{repo}/contents/{path}?ref={branch}")
    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            return None
        raise
    return base64.b64decode(data["content"]).decode("utf-8")


async def commit_changes(session, token, repo, branch, changed: dict, message: str, author: dict) -> str:
    """Atomically commit {path: text} as one commit. author = {'name','email'}.
    Raises RefMoved if the branch advanced before our ref update."""
    base_commit = await head_sha(session, token, repo, branch)
    base_tree = await _tree_sha(session, token, repo, base_commit)
    tree_entries = []
    for path, text in changed.items():
        blob = await _post(session, token, f"/repos/{repo}/git/blobs",
                           {"content": text, "encoding": "utf-8"})
        tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = await _post(session, token, f"/repos/{repo}/git/trees",
                           {"base_tree": base_tree, "tree": tree_entries})
    commit = await _post(session, token, f"/repos/{repo}/git/commits", {
        "message": message, "tree": new_tree["sha"], "parents": [base_commit],
        "author": {"name": author["name"], "email": author["email"]},
    })
    # Non-force ref update; if base moved, GitHub returns 422 -> signal retry.
    try:
        async with session.patch(
            f"{_API}/repos/{repo}/git/refs/heads/{branch}",
            headers=_headers(token), json={"sha": commit["sha"], "force": False},
        ) as r:
            if r.status == 422:
                raise RefMoved()
            r.raise_for_status()
    except aiohttp.ClientResponseError as e:
        if e.status == 422:
            raise RefMoved()
        raise
    return commit["sha"]
```

- [ ] **Step 2: Write a mocked commit-flow test**

Path: `~/nsls-skills/kb-gateway/tests/test_commit_flow.py`
```python
import pytest
import github_repo


class FakeResp:
    def __init__(self, status=200, json_data=None):
        self.status = status; self._json = json_data or {}
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    def raise_for_status(self):
        if self.status >= 400:
            import aiohttp
            raise aiohttp.ClientResponseError(request_info=None, history=(), status=self.status)
    async def json(self): return self._json


class FakeSession:
    """Replays queued responses by call order; records PATCH calls."""
    def __init__(self, queue): self.queue = queue; self.patched = []
    def get(self, url, headers=None): return self.queue.pop(0)
    def post(self, url, headers=None, json=None): return self.queue.pop(0)
    def patch(self, url, headers=None, json=None):
        self.patched.append(json); return self.queue.pop(0)


@pytest.mark.asyncio
async def test_commit_changes_happy_path():
    q = [
        FakeResp(json_data={"object": {"sha": "BASECOMMIT"}}),   # head_sha
        FakeResp(json_data={"tree": {"sha": "BASETREE"}}),        # _tree_sha
        FakeResp(json_data={"sha": "BLOB1"}),                     # create blob
        FakeResp(json_data={"sha": "NEWTREE"}),                   # create tree
        FakeResp(json_data={"sha": "NEWCOMMIT"}),                 # create commit
        FakeResp(status=200, json_data={}),                       # patch ref
    ]
    s = FakeSession(q)
    sha = await github_repo.commit_changes(s, "tok", "o/r", "main",
                                           {"a.md": "hello"}, "msg",
                                           {"name": "Kevin", "email": "k@nsls.org"})
    assert sha == "NEWCOMMIT"
    assert s.patched[0]["sha"] == "NEWCOMMIT" and s.patched[0]["force"] is False


@pytest.mark.asyncio
async def test_commit_changes_raises_refmoved_on_422():
    q = [
        FakeResp(json_data={"object": {"sha": "B"}}),
        FakeResp(json_data={"tree": {"sha": "T"}}),
        FakeResp(json_data={"sha": "BLOB"}),
        FakeResp(json_data={"sha": "TREE"}),
        FakeResp(json_data={"sha": "COMMIT"}),
        FakeResp(status=422, json_data={}),                       # patch -> ref moved
    ]
    with pytest.raises(github_repo.RefMoved):
        await github_repo.commit_changes(FakeSession(q), "tok", "o/r", "main",
                                         {"a.md": "x"}, "m", {"name": "n", "email": "e"})
```

- [ ] **Step 3: Add pytest asyncio config so `@pytest.mark.asyncio` runs**

Path: `~/nsls-skills/kb-gateway/pytest.ini`
```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 4: Run to verify pass**

Run: `PYTHONPATH=/tmp/kbgw-deps python3.12 -m pytest ~/nsls-skills/kb-gateway/tests/test_commit_flow.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**
```bash
cd ~/nsls-skills/kb-gateway && git add github_repo.py tests/test_commit_flow.py pytest.ini
git commit -q -m "feat: github_repo — fetch KB files + atomic Git Data API commit with ref-move detection"
```

---

## Task 7: `audit.py` — one record per commit

**Files:**
- Create: `~/nsls-skills/kb-gateway/audit.py`

- [ ] **Step 1: Implement `audit.py` (structured stdout log; Railway captures it)**

Path: `~/nsls-skills/kb-gateway/audit.py`
```python
"""Audit sink. v1: structured JSON line to stdout (captured by Railway logs)."""
import json
import logging

_log = logging.getLogger("kb-gateway.audit")


def record(*, email: str, commit_sha: str | None, applied: list, rejected: list, dry_run: bool):
    _log.info(json.dumps({
        "event": "kb_commit",
        "email": email,
        "commit_sha": commit_sha,
        "applied": [a["topic_slug"] for a in applied],
        "rejected": [{"topic": r["topic_slug"], "reason": r["reason"]} for r in rejected],
        "dry_run": dry_run,
    }))
```

- [ ] **Step 2: Smoke-check import**

Run: `cd ~/nsls-skills/kb-gateway && PYTHONPATH=/tmp/kbgw-deps python3.12 -c "import audit; audit.record(email='x', commit_sha='s', applied=[], rejected=[], dry_run=True)"`
Expected: a JSON line on stdout.

- [ ] **Step 3: Commit**
```bash
cd ~/nsls-skills/kb-gateway && git add audit.py
git commit -q -m "feat: audit — structured commit log line"
```

---

## Task 8: `handlers.py` + `app.py` — wire the endpoints (TDD via aiohttp test client)

**Files:**
- Create: `~/nsls-skills/kb-gateway/handlers.py`, `~/nsls-skills/kb-gateway/app.py`
- Test: `~/nsls-skills/kb-gateway/tests/test_handlers.py`

- [ ] **Step 1: Implement `handlers.py`**

Path: `~/nsls-skills/kb-gateway/handlers.py`
```python
"""aiohttp request handlers. Auth via Bearer token against the registry."""
import datetime
from aiohttp import web

import config
import auth
import kb_parse
import kb_edits
import github_repo
import audit


def _member(request):
    hdr = request.headers.get("Authorization", "")
    token = hdr[7:] if hdr.startswith("Bearer ") else ""
    return auth.member_for_token(config.TOKEN_REGISTRY, token)


async def _gh_token(request):
    return await auth.installation_token(
        request.app["session"], config.GH_APP_ID,
        config.GH_APP_INSTALLATION_ID, config.GH_APP_PRIVATE_KEY)


async def health(request):
    return web.Response(text="ok")


async def whoami(request):
    m = _member(request)
    if not m:
        return web.json_response({"error": "unauthorized"}, status=401)
    return web.json_response({"email": m["email"], "name": m["name"], "is_slt": True})


def _extract_rubric(claude_md: str) -> str:
    import re
    m = re.search(rf"{re.escape(config.RUBRIC_HEADER)}.*?(?=\n## |\Z)", claude_md, re.DOTALL)
    return m.group(0) if m else ""


async def context(request):
    m = _member(request)
    if not m:
        return web.json_response({"error": "unauthorized"}, status=401)
    token = await _gh_token(request)
    head, files = await github_repo.fetch_kb_files(
        request.app["session"], token, config.KB_REPO, config.KB_BRANCH)
    rubric = _extract_rubric(files.pop("__claude_md__", ""))
    payload = kb_parse.build_context(files, rubric)
    payload["head_sha"] = head
    return web.json_response(payload)


async def commit(request):
    m = _member(request)
    if not m:
        return web.json_response({"error": "unauthorized"}, status=401)
    body = await request.json()
    meeting = body.get("meeting", {})
    candidates = body.get("candidates", [])
    dry_run = bool(body.get("dry_run", False))
    today = datetime.date.today().isoformat()
    token = await _gh_token(request)

    # Build the evolving working set from live content (accumulation-safe).
    working, applied, rejected = {}, [], []
    for cand in candidates:
        path = f"{cand['topic_slug']}.md"
        if path in working:
            text = working[path]
        else:
            text = await github_repo.read_file_text(
                request.app["session"], token, config.KB_REPO, config.KB_BRANCH, path)
        new_text, status = kb_edits.apply_edit(text if text is not None else None,
                                               cand, meeting, today)
        if status["status"] == "ok":
            working[path] = new_text
            applied.append(status)
        else:
            rejected.append(status)

    commit_sha = None
    if working and not dry_run:
        titles = list({c.get("meeting", {}).get("title", meeting.get("title", "")) for c in [body]})
        msg = f"harvest: {today} {meeting.get('title','')} ({len(applied)} edits)"
        for _ in range(3):
            try:
                commit_sha = await github_repo.commit_changes(
                    request.app["session"], token, config.KB_REPO, config.KB_BRANCH,
                    working, msg, {"name": m["name"], "email": m["email"]})
                break
            except github_repo.RefMoved:
                continue
        else:
            return web.json_response({"error": "ref kept moving; retry"}, status=409)

    audit.record(email=m["email"], commit_sha=commit_sha,
                 applied=applied, rejected=rejected, dry_run=dry_run)
    return web.json_response({"commit_sha": commit_sha, "applied": applied,
                              "rejected": rejected, "dry_run": dry_run})
```

- [ ] **Step 2: Implement `app.py`**

Path: `~/nsls-skills/kb-gateway/app.py`
```python
"""KB Gateway entrypoint."""
import logging
import aiohttp
from aiohttp import web

import config
import handlers


def build_app() -> web.Application:
    app = web.Application()
    app.add_routes([
        web.get("/health", handlers.health),
        web.get("/kb/whoami", handlers.whoami),
        web.get("/kb/context", handlers.context),
        web.post("/kb/commit", handlers.commit),
    ])

    async def _startup(a):
        a["session"] = aiohttp.ClientSession()

    async def _cleanup(a):
        await a["session"].close()

    app.on_startup.append(_startup)
    app.on_cleanup.append(_cleanup)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web.run_app(build_app(), port=config.PORT)
```

- [ ] **Step 3: Write handler tests (aiohttp test client; monkeypatch GitHub calls)**

Path: `~/nsls-skills/kb-gateway/tests/test_handlers.py`
```python
import hashlib
import pytest
from aiohttp import web

import config
import handlers
import github_repo


@pytest.fixture
def client_setup(monkeypatch):
    tok = "tok-kevin"
    monkeypatch.setattr(config, "TOKEN_REGISTRY",
                        {hashlib.sha256(tok.encode()).hexdigest(): {"email": "k@nsls.org", "name": "Kevin"}})

    async def fake_gh_token(request): return "ghtok"
    monkeypatch.setattr(handlers, "_gh_token", fake_gh_token)

    async def fake_fetch(session, token, repo, branch):
        topic = ("---\ntype: kpi\nlast-updated: 2026-01-01\n---\n\n# B2C\n\n"
                 "## Current State\n\nOld.\n\n## Key Decisions\n\n- 2026-01-06: prior\n\n## Open Questions\n\n")
        return "HEAD1", {"b2c": topic, "__claude_md__": "## Sensitive-Content Rubric\nno profit\n"}
    monkeypatch.setattr(github_repo, "fetch_kb_files", fake_fetch)

    async def fake_read(session, token, repo, branch, path):
        if path == "b2c.md":
            return ("---\ntype: kpi\nlast-updated: 2026-01-01\n---\n\n# B2C\n\n"
                    "## Current State\n\nOld.\n\n## Key Decisions\n\n- 2026-01-06: prior\n\n## Open Questions\n\n")
        return None
    monkeypatch.setattr(github_repo, "read_file_text", fake_read)

    captured = {}
    async def fake_commit(session, token, repo, branch, changed, message, author):
        captured["changed"] = changed; captured["author"] = author; captured["message"] = message
        return "NEWSHA"
    monkeypatch.setattr(github_repo, "commit_changes", fake_commit)
    return tok, captured


async def test_whoami_requires_token(aiohttp_client):
    client = await aiohttp_client(handlers_app())
    r = await client.get("/kb/whoami")
    assert r.status == 401


async def test_whoami_ok(aiohttp_client, client_setup):
    tok, _ = client_setup
    client = await aiohttp_client(handlers_app())
    r = await client.get("/kb/whoami", headers={"Authorization": f"Bearer {tok}"})
    assert r.status == 200 and (await r.json())["email"] == "k@nsls.org"


async def test_commit_dry_run_does_not_commit(aiohttp_client, client_setup):
    tok, captured = client_setup
    client = await aiohttp_client(handlers_app())
    body = {"dry_run": True, "meeting": {"title": "SLT", "url": "https://f/x", "date": "2026-05-26"},
            "candidates": [{"topic_slug": "b2c", "section": "key_decisions", "dedup_verdict": "NEW",
                            "text": "New one", "fathom_timestamp_sec": 5}]}
    r = await client.post("/kb/commit", headers={"Authorization": f"Bearer {tok}"}, json=body)
    data = await r.json()
    assert r.status == 200 and data["commit_sha"] is None
    assert data["applied"][0]["topic_slug"] == "b2c" and "changed" not in captured


async def test_commit_real_attributes_to_member(aiohttp_client, client_setup):
    tok, captured = client_setup
    client = await aiohttp_client(handlers_app())
    body = {"dry_run": False, "meeting": {"title": "SLT", "url": "https://f/x", "date": "2026-05-26"},
            "candidates": [{"topic_slug": "b2c", "section": "key_decisions", "dedup_verdict": "NEW",
                            "text": "New one", "fathom_timestamp_sec": 5}]}
    r = await client.post("/kb/commit", headers={"Authorization": f"Bearer {tok}"}, json=body)
    data = await r.json()
    assert data["commit_sha"] == "NEWSHA"
    assert captured["author"] == {"name": "Kevin", "email": "k@nsls.org"}
    assert "- 2026-05-26: New one ([▶](https://f/x?timestamp=5))" in captured["changed"]["b2c.md"]


def handlers_app():
    from app import build_app
    return build_app()
```

- [ ] **Step 4: Run to verify pass**

Run: `PYTHONPATH=/tmp/kbgw-deps python3.12 -m pytest ~/nsls-skills/kb-gateway/tests/test_handlers.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the full suite**

Run: `PYTHONPATH=/tmp/kbgw-deps python3.12 -m pytest ~/nsls-skills/kb-gateway/tests -v`
Expected: all green (kb_parse 5, kb_edits 7, auth 3, commit_flow 2, handlers 4).

- [ ] **Step 6: Commit**
```bash
cd ~/nsls-skills/kb-gateway && git add handlers.py app.py tests/test_handlers.py
git commit -q -m "feat: handlers + app — /health /kb/whoami /kb/context /kb/commit"
```

---

## Task 9: Create the GitHub App + push the repo (manual prerequisite + deploy)

**Files:** none (infra). This task is mostly out-of-band; document exact steps.

- [ ] **Step 1: Create a dedicated GitHub App (org owner action)**

In GitHub → Org `thensls` → Settings → Developer settings → GitHub Apps → New:
- Name: `nsls-kb-gateway`
- Permissions: Repository → **Contents: Read & write**, Metadata: Read-only. No webhook.
- Install it on the org, **scoped to only `nsls-knowledge`**.
- Record the **App ID** and **Installation ID**; generate + download a **private key** (.pem).

Heartbeat to the user: "Need the org owner (you or Davo) to create `nsls-kb-gateway`, install it on `nsls-knowledge` only, and hand me App ID + Installation ID + the .pem."

- [ ] **Step 2: Create the GitHub repo and push**

```bash
cd ~/nsls-skills/kb-gateway
gh repo create thensls/kb-gateway --private --source=. --remote=origin --push
```
Expected: repo created, `main` pushed.

- [ ] **Step 3: Seed Doppler secrets (slt-coach project) for the new service**

Set in the slt-coach Doppler project (so Railway injects them): `GH_APP_ID`, `GH_APP_INSTALLATION_ID`, `GH_APP_PRIVATE_KEY` (PEM with `\n` escaped), `KB_REPO=thensls/nsls-knowledge`, `KB_BRANCH=main`, `KB_TOKENS={}` (filled in Task 11).

Heartbeat: confirm with the user this is the same Doppler project slt-coach uses, per the "shared infra shares a Doppler project" rule.

- [ ] **Step 4: Add the Railway service in the slt-coach project**

Create a new service in the existing slt-coach Railway project from the `thensls/kb-gateway` repo. Confirm healthcheck `/health` passes and the public URL responds:
```bash
curl -fsS "$KB_GATEWAY_URL/health"   # expect: ok
```

- [ ] **Step 5: Commit any infra notes**
```bash
cd ~/nsls-skills/kb-gateway
printf '\n## Deploy\n- Railway service in the slt-coach project. Secrets in the slt-coach Doppler project.\n- GitHub App: nsls-kb-gateway (Contents R/W on nsls-knowledge only).\n' >> README.md
git add README.md && git commit -q -m "docs: deploy notes" && git push origin main
```

---

## Task 10: Live dry-run validation against the real repo

**Files:** none (validation).

- [ ] **Step 1: Issue a temporary token for Kevin and add to `KB_TOKENS`**

```bash
TOK=$(python3.12 -c "import secrets; print(secrets.token_urlsafe(32))")
HASH=$(python3.12 -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" "$TOK")
echo "token (give to setup): $TOK"
echo "registry entry: {\"$HASH\": {\"email\": \"kprentiss@nsls.org\", \"name\": \"Kevin Prentiss\"}}"
```
Put the registry entry into Doppler `KB_TOKENS` and redeploy.

- [ ] **Step 2: Verify identity + context**

```bash
curl -fsS -H "Authorization: Bearer $TOK" "$KB_GATEWAY_URL/kb/whoami"      # {"email":"kprentiss@nsls.org",...}
curl -fsS -H "Authorization: Bearer $TOK" "$KB_GATEWAY_URL/kb/context" | python3.12 -c "import sys,json; d=json.load(sys.stdin); print('topics', len(d['topics']), 'rubric', len(d['rubric']), 'head', d['head_sha'][:7])"
```
Expected: ~66 topics, non-empty rubric, a head sha.

- [ ] **Step 2b: Dry-run a known append candidate**

```bash
curl -fsS -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"dry_run":true,"meeting":{"title":"smoke","url":"https://f/x","date":"2026-05-31"},"candidates":[{"topic_slug":"executive-strategy","section":"key_decisions","dedup_verdict":"NEW","text":"DRY RUN — ignore","fathom_timestamp_sec":1}]}' \
  "$KB_GATEWAY_URL/kb/commit" | python3.12 -m json.tool
```
Expected: `commit_sha: null`, `applied: [executive-strategy]`, no rejection. Confirm via `git -C "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge" fetch && git -C ... log origin/main -1` that NOTHING was committed.

- [ ] **Step 3: No commit needed; record validation in the plan** (check the box; note results inline).

---

## Task 11: Rewire `/harvest-meeting` to the gateway (the hard cut)

**Files:**
- Modify: `~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md`
- Delete: `~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt`

- [ ] **Step 1: Replace Step 0 (gate) — env pre-check, server-side authz**

In `SKILL.md`, replace the entire `## Step 0` body with:
````markdown
## Step 0: Mode dispatch + gateway pre-check

Parse arguments (`--date`, `--fathom-url`, `--week-audit`).

Authorization is enforced **server-side** by the KB Gateway (per-member bearer token). The skill
only pre-checks that the token is configured:

```bash
if [ -z "$KB_GATEWAY_URL" ] || [ -z "$KB_GATEWAY_TOKEN" ]; then
  echo "Step 0: KB gateway not configured — run /kb-setup. Skipping harvest."
  exit 0
fi
WHO=$(curl -fsS -H "Authorization: Bearer $KB_GATEWAY_TOKEN" "$KB_GATEWAY_URL/kb/whoami" || true)
echo "Step 0: gateway identity: ${WHO:-<unreachable>}"
```
If `/kb/whoami` returns 401/unreachable, heartbeat and exit cleanly (no harvest). Otherwise proceed.
````

- [ ] **Step 2: Replace Step 1 (context) — fetch from the gateway**

Replace the `## Step 1` "load context" Python/bash with:
````markdown
## Step 1: Load context (from the KB Gateway)

```bash
mkdir -p /tmp/harvest-meeting-ctx
curl -fsS -H "Authorization: Bearer $KB_GATEWAY_TOKEN" "$KB_GATEWAY_URL/kb/context" \
  -o /tmp/harvest-meeting-ctx/context.json
PYTHONPATH=/tmp/pptx_deps python3.12 - <<'PY'
import json, pathlib
ctx = json.loads(pathlib.Path('/tmp/harvest-meeting-ctx/context.json').read_text())
c = pathlib.Path('/tmp/harvest-meeting-ctx')
(c/'topics.json').write_text(json.dumps(ctx['topics'], indent=2))
(c/'rubric.md').write_text(ctx['rubric'])
(c/'head_sha').write_text(ctx['head_sha'])
print(f"Step 1: loaded {len(ctx['topics'])} topics, rubric {len(ctx['rubric'])} chars, head {ctx['head_sha'][:7]}")
PY
```
Downstream steps read `/tmp/harvest-meeting-ctx/topics.json` + `rubric.md` exactly as before.
No local clone, no `git pull`.
````

- [ ] **Step 3: Update Step 6b to record the current_state base hash**

In `## Step 6b`, after computing `new_current_state`, add:
````markdown
For each `current_state` candidate, also record `current_state_base_sha256` = sha256 of the EXACT
`current_state` string for that topic from `/tmp/harvest-meeting-ctx/topics.json` (strip whitespace
first), so the gateway can reject the write if the live block moved:

```python
import hashlib, json, pathlib
topics = json.loads(pathlib.Path('/tmp/harvest-meeting-ctx/topics.json').read_text())
cand['current_state_base_sha256'] = hashlib.sha256(
    topics[cand['topic_slug']]['current_state'].strip().encode()).hexdigest()
```
````

- [ ] **Step 4: Replace Step 8 (write) — POST to the gateway**

Replace the entire `## Step 8` body (the local-git Python block) with:
````markdown
## Step 8: Commit via the KB Gateway

Build the approved-candidates payload and POST it. The gateway applies edits against live repo
content and commits (author = you, committer = the automation App).

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 - <<'PY'
import json, os, pathlib, urllib.request
approved = json.loads(pathlib.Path('/tmp/harvest-meeting-ctx/approved.json').read_text())
meeting = json.loads(pathlib.Path('/tmp/harvest-meeting-ctx/meeting.json').read_text())  # {title,url,date}
body = json.dumps({"dry_run": False, "meeting": meeting, "candidates": approved}).encode()
req = urllib.request.Request(
    os.environ['KB_GATEWAY_URL'].rstrip('/') + '/kb/commit', data=body,
    headers={"Authorization": "Bearer " + os.environ['KB_GATEWAY_TOKEN'],
             "Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req) as r:
    res = json.load(r)
print("Step 8: commit", res.get("commit_sha"))
for a in res.get("applied", []): print("  applied:", a["topic_slug"])
for x in res.get("rejected", []): print("  REJECTED:", x["topic_slug"], "—", x["reason"], "(re-harvest this topic)")
PY
```
Heartbeat the commit sha + any rejections. Rejections (e.g. a `current_state` whose live block moved)
mean: re-run the harvest for that topic against fresh context.
````

Note for the implementer: ensure earlier steps write `/tmp/harvest-meeting-ctx/meeting.json` (`{title,url,date}`) and that each approved candidate carries `topic_slug, section, is_new_topic, suggested_new, dedup_verdict, replace_entry, text, fathom_timestamp_sec, new_current_state, current_state_base_sha256`.

- [ ] **Step 5: Delete the retired allowlist**

```bash
git -C ~/nsls-skills/nsls-personal-toolkit rm skills/harvest-meeting/kb_authors.txt
```

- [ ] **Step 6: Verify SKILL.md has no remaining local-git references**

Run: `grep -nE "git push|git -C|git pull|origin/main|kb_authors" ~/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/SKILL.md`
Expected: no matches (the harvest path is now gateway-only).

- [ ] **Step 7: Commit**
```bash
cd ~/nsls-skills/nsls-personal-toolkit
git add skills/harvest-meeting/SKILL.md
git commit -q -m "feat(harvest-meeting): hard-cut to KB Gateway (context + commit); retire local git + kb_authors.txt"
```

---

## Task 12: `/kb-setup` skill + token distribution

**Files:**
- Create: `~/nsls-skills/nsls-personal-toolkit/skills/kb-setup/SKILL.md`

- [ ] **Step 1: Write the setup skill**

Path: `~/nsls-skills/nsls-personal-toolkit/skills/kb-setup/SKILL.md`
````markdown
---
name: kb-setup
description: Configure this machine to write to the NSLS Knowledge Base via the KB Gateway. Use when harvest-meeting says the gateway isn't configured, when setting up a new SLT member, or to rotate the KB gateway token. Sets KB_GATEWAY_URL + KB_GATEWAY_TOKEN.
---

# KB Setup — connect to the KB Gateway

The harvest pipeline writes through the KB Gateway (no GitHub account or clone needed). This skill
stores your gateway URL + personal token in the toolkit `.env`.

## Step 1: Locate the .env
The personal toolkit `.env` is at `~/.claude/local-plugins/nsls-personal-toolkit/.env`.

## Step 2: Ask the user for their values
- `KB_GATEWAY_URL` (the gateway's public URL — same for everyone; ask Kevin if unknown).
- `KB_GATEWAY_TOKEN` (the personal token Kevin issued you, via 1Password).

## Step 3: Write them to .env (idempotent — replace if present)
```bash
ENV=~/.claude/local-plugins/nsls-personal-toolkit/.env
touch "$ENV"
grep -q '^KB_GATEWAY_URL=' "$ENV" && sed -i.bak "s#^KB_GATEWAY_URL=.*#KB_GATEWAY_URL=$KB_GATEWAY_URL#" "$ENV" || echo "KB_GATEWAY_URL=$KB_GATEWAY_URL" >> "$ENV"
grep -q '^KB_GATEWAY_TOKEN=' "$ENV" && sed -i.bak "s#^KB_GATEWAY_TOKEN=.*#KB_GATEWAY_TOKEN=$KB_GATEWAY_TOKEN#" "$ENV" || echo "KB_GATEWAY_TOKEN=$KB_GATEWAY_TOKEN" >> "$ENV"
rm -f "$ENV.bak"
```

## Step 4: Validate
```bash
curl -fsS -H "Authorization: Bearer $KB_GATEWAY_TOKEN" "$KB_GATEWAY_URL/kb/whoami"
```
Expected: your `{email, name, is_slt:true}`. If 401, the token is wrong — ask Kevin to reissue.
````

- [ ] **Step 2: Issue the 7 SLT tokens and populate `KB_TOKENS`**

```bash
PYTHONPATH=/tmp/pptx_deps python3.12 - <<'PY'
import secrets, hashlib, json
slt = {"kprentiss@nsls.org":"Kevin Prentiss","mobrien@nsls.org":"Michael O'Brien",
       "gtuerack@nsls.org":"Gary Tuerack","astone@nsls.org":"Adam Stone",
       "hdarnell@nsls.org":"Heather Darnell","asmith@nsls.org":"Ashleigh Smith",
       "cbyers@nsls.org":"Chelsea Byers"}
registry, plain = {}, {}
for email, name in slt.items():
    t = secrets.token_urlsafe(32)
    registry[hashlib.sha256(t.encode()).hexdigest()] = {"email": email, "name": name}
    plain[email] = t
print("KB_TOKENS (Doppler):"); print(json.dumps(registry))
print("\nPer-member tokens (share via 1Password, then DELETE this output):")
for e, t in plain.items(): print(f"  {e}: {t}")
PY
```
Put the `KB_TOKENS` JSON into Doppler (slt-coach project), redeploy, share each plaintext token with its member via 1Password, and **clear the terminal output**.

- [ ] **Step 3: Commit the skill**
```bash
cd ~/nsls-skills/nsls-personal-toolkit && git add skills/kb-setup/SKILL.md
git commit -q -m "feat(kb-setup): configure KB Gateway URL + per-member token"
```

---

## Task 13: Smoke test the full path + close out

**Files:** none (validation) + plan/spec status.

- [ ] **Step 1: Kevin runs a real single-candidate harvest**

Run `/kb-setup` (Kevin's token), then `/harvest-meeting --fathom-url <a-recent-meeting>`. Approve exactly one low-stakes candidate.

- [ ] **Step 2: Verify the commit on GitHub**

```bash
cd "$OBSIDIAN_VAULT_PATH/60-nsls-knowledge" && git fetch -q origin
git log origin/main -1 --format='%an <%ae> | %cn | %s'
```
Expected: author = `Kevin Prentiss <kprentiss@nsls.org>`, committer = the App, subject `harvest: …`.

- [ ] **Step 3: Verify a stale-base rejection path**

Re-submit a `current_state` candidate with a deliberately wrong `current_state_base_sha256` (dry-run) and confirm the gateway returns it under `rejected` (not applied).

- [ ] **Step 4: Mark spec + plan complete**

Edit `docs/specs/2026-05-31-kb-gateway-design.md` frontmatter `status: shipped`; add `completed: <date>` to this plan's frontmatter (add via Edit tool). Commit + push both repos.

```bash
cd ~/nsls-skills/nsls-personal-toolkit && git add docs/ && git commit -q -m "docs: KB Gateway shipped" && git push origin main
```

- [ ] **Step 5: Announce to the other 6 SLT**

DM each: "You can now write to the KB from Claude Code — run `/kb-setup` with the token I sent you (1Password), then `/close-day` harvests your meetings. No GitHub needed." (Out of code scope.)

---

## Self-Review (completed during authoring)

- **Spec coverage:** gateway endpoints (Tasks 6/8), GitHub App + repo-scoped credential (Task 9), edit logic moved server-side incl. current_state guard + new-topic accumulation + acronym titles (Task 3), per-member tokens + attribution (Tasks 4/8/12), read-context via gateway (Tasks 6/8/11), skill hard-cut Step 0/1/6b/8 (Task 11), `/kb-setup` (Task 12), dry-run validation + hard-cut sequencing (Tasks 10/13), audit (Task 7). All spec sections map to a task.
- **Placeholder scan:** code provided in every code step; infra/manual steps (GitHub App, Doppler, Railway) are explicitly out-of-band with exact instructions.
- **Type consistency:** `apply_edit(text|None, cand, meeting, today) -> (text, status)`, `fetch_kb_files -> (head, {slug:text})`, `commit_changes(... ) -> sha / raises RefMoved`, `member_for_token(registry, token)` — names used consistently across Tasks 3/4/6/8/11.
```
