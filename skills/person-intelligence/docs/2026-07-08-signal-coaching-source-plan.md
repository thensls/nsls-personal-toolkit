# Signal as a Coaching Source — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Signal (Quick Notes) a first-class coaching source in Person Intelligence — broadened beyond direct reports, turned into an advisory "How to Support" section and pulse line, woven into relationship context, and kept out of the health score.

**Architecture:** Deterministic changes to four scripts + docs. Eligibility is a pure function in `list_relationships.py` that tags each relationship; `biweekly_sweep.py` gates Signal ingest on that tag; `synthesize_profile.py` adds prompt instructions (the profile is a single LLM call, so "sections" are prompt directives, not post-processing); `generate_team_pulse.py` surfaces the profile's new section. The scoring pipeline is untouched.

**Tech Stack:** Python 3.12, pytest-style tests in `skills/person-intelligence/tests/` (subprocess-driven for CLI scripts, direct-import for pure functions). No new dependencies.

## Global Constraints

- Python interpreter is `python3.12` everywhere (verbatim; the repo pins it).
- Signal must NEVER contribute to `health_score` / the scoring pipeline — coaching/context only.
- Never auto-write the `## Coaching Goals` section — it is user-curated (accept/edit/reject).
- Preserve all existing Signal sensitivity safeguards: raw Quick Notes stay cache-only; the mechanical HR/health/comp filter and KB rubric still apply; never emit comp/health/family/personnel-status content.
- All work on branch `feat/signal-coaching-actions` in `/Users/k/nsls-skills/nsls-personal-toolkit`.
- Scripts self-load `.env` via `load_dotenv_local`; don't add new env plumbing.

---

### Task 1: `signal_eligible` eligibility rule in `list_relationships.py`

**Files:**
- Modify: `skills/person-intelligence/scripts/list_relationships.py` (add `is_signal_eligible()`; tag each relationship dict in `main()` before output, near the `relationships.append(...)` sites ~135/179 — do it as a single post-build loop before the JSON dump)
- Test: `skills/person-intelligence/tests/test_list_relationships.py` (add cases)

**Interfaces:**
- Produces: `is_signal_eligible(name: str, email: str, tracking_reason: str) -> bool` and a `"signal_eligible": bool` key on every relationship dict emitted by `list_relationships.py`.
- Rule: `True` iff `email` ends with `@nsls.org` AND `tracking_reason != "key_relationship_external"` AND `name not in SIGNAL_EXCLUDE`. `SIGNAL_EXCLUDE` defaults to `{"Dana Ashford"}`, overridable via env `SIGNAL_EXCLUDE` (comma-separated).
  > **SUPERSEDED (2026-08-30).** This repository is public, so no name is hardcoded any more. `SIGNAL_EXCLUDE` has **no default** and must be set in `.env`; **unset fails closed** (nobody is eligible, and the script says so on stderr). The code blocks below are the original plan, kept for history — do not copy the hardcoded default back in. See `scripts/list_relationships.py` and `tests/test_list_relationships.py`.

- [ ] **Step 1: Write the failing test**

Add to `skills/person-intelligence/tests/test_list_relationships.py`:

```python
def test_signal_eligible_rule():
    import importlib.util
    spec = importlib.util.spec_from_file_location("list_relationships", LIST_RELATIONSHIPS)
    lr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lr)

    # direct report with nsls email -> eligible
    assert lr.is_signal_eligible("Report A", "a@nsls.org", "direct_report") is True
    # SLT peer with nsls email -> eligible
    assert lr.is_signal_eligible("Adam Ferris", "aferris@nsls.org", "peer") is True
    # board member on the exclude list -> not eligible
    assert lr.is_signal_eligible("Dana Ashford", "dashford@nsls.org", "key_relationship") is False
    # external (no nsls email) -> not eligible
    assert lr.is_signal_eligible("Red External", "", "key_relationship_external") is False
    # non-nsls email -> not eligible
    assert lr.is_signal_eligible("Gmail Person", "x@gmail.com", "key_relationship") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_list_relationships.py::test_signal_eligible_rule -v`
Expected: FAIL — `module 'list_relationships' has no attribute 'is_signal_eligible'`

- [ ] **Step 3: Add the function + env constant near the top of `list_relationships.py`** (after the imports, before `parse_key_relationships`)

```python
import os

SIGNAL_EXCLUDE = {
    n.strip() for n in os.environ.get("SIGNAL_EXCLUDE", "Dana Ashford").split(",") if n.strip()
}


def is_signal_eligible(name, email, tracking_reason):
    """True when a tracked person plausibly has NSLS Signal Quick Notes.

    Signal is coaching/context only; this only decides whether to ATTEMPT a
    fetch. A no-match still degrades to empty in fetch_signal.py.
    """
    email = (email or "").strip().lower()
    if not email.endswith("@nsls.org"):
        return False
    if tracking_reason == "key_relationship_external":
        return False
    if name in SIGNAL_EXCLUDE:
        return False
    return True
```

- [ ] **Step 4: Tag every relationship in `main()`** — immediately before the `print(json.dumps(...))` that emits the output, add:

```python
    for rel in relationships:
        rel["signal_eligible"] = is_signal_eligible(
            rel.get("name", ""), rel.get("email", ""), rel.get("tracking_reason", "")
        )
```

(Place this after the `relationships` list is fully assembled and before it is serialized. If `main()` builds a wrapper dict `{"relationships": relationships, ...}`, tag the list before wrapping.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_list_relationships.py::test_signal_eligible_rule -v`
Expected: PASS

- [ ] **Step 6: Add an output-shape test** confirming the key is present on emitted dicts. Add:

```python
def test_relationships_carry_signal_eligible(tmp_path):
    chart = tmp_path / "org-chart.json"
    chart.write_text(json.dumps(FIXTURE_EMPLOYEES))
    env = {**os.environ, "OPERATING_USER_EMAIL": "test@example.com",
           "BUILDER_ORG_CHART": str(chart)}  # match how the suite injects the chart
    out = subprocess.check_output(["python3.12", str(LIST_RELATIONSHIPS)], env=env, text=True)
    data = json.loads(out)
    for rel in data["relationships"]:
        assert "signal_eligible" in rel
```

(If the existing suite injects the org chart differently, mirror that mechanism — reuse the same fixture setup already present in this file.)

- [ ] **Step 7: Run the full file + commit**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_list_relationships.py -v`
Expected: PASS (all)

```bash
git add skills/person-intelligence/scripts/list_relationships.py skills/person-intelligence/tests/test_list_relationships.py
git commit -m "feat(person-intelligence): signal_eligible rule + tag on relationships"
```

---

### Task 2: Gate Signal ingest on `signal_eligible` in `biweekly_sweep.py`

**Files:**
- Modify: `skills/person-intelligence/scripts/biweekly_sweep.py:287-290`
- Test: `skills/person-intelligence/tests/test_biweekly_signal_gate.py` (new)

**Interfaces:**
- Consumes: `rel["signal_eligible"]` (Task 1), `signal_available` (existing local).
- Produces: manifest relationships where `signal_ingest_planned == (signal_available and rel["signal_eligible"])`, and `signal_slug` set for every planned rel.

- [ ] **Step 1: Write the failing test** — `tests/test_biweekly_signal_gate.py`:

```python
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_gate_uses_eligibility_not_direct_report_only():
    bws = _load("biweekly_sweep")
    # a peer that is signal_eligible should be planned when signal is available
    rel = {"name": "Adam Ferris", "email": "aferris@nsls.org",
           "tracking_reason": "peer", "signal_eligible": True}
    planned = bws.plan_signal(rel, signal_available=True)
    assert planned["signal_ingest_planned"] is True
    assert planned["signal_slug"] == "adam-ferris"
    # ineligible person never planned
    rel2 = {"name": "Dana Ashford", "email": "dashford@nsls.org",
            "tracking_reason": "key_relationship", "signal_eligible": False}
    assert bws.plan_signal(rel2, signal_available=True)["signal_ingest_planned"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_biweekly_signal_gate.py -v`
Expected: FAIL — `module 'biweekly_sweep' has no attribute 'plan_signal'`

- [ ] **Step 3: Extract a pure `plan_signal` helper** in `biweekly_sweep.py` (module level), and call it from the loop. Add:

```python
def plan_signal(rel, signal_available):
    """Set signal_ingest_planned + signal_slug on a relationship dict. Pure/testable."""
    eligible = bool(rel.get("signal_eligible"))
    rel["signal_ingest_planned"] = bool(signal_available) and eligible
    if rel["signal_ingest_planned"]:
        rel["signal_slug"] = (
            rel["name"].lower().replace("'", "").replace(".", "").replace(" ", "-")
        )
    return rel
```

- [ ] **Step 4: Replace the inline gating at lines 287-290** with a call:

```python
        rel["slack_ingest_planned"] = slack_available and bool(rel.get("slack"))
        rel["gmail_ingest_planned"] = gmail_available and bool(rel.get("email"))
        plan_signal(rel, signal_available)
```

(Delete the old `is_direct_report = ...` / `rel["signal_ingest_planned"] = ...` / slug lines.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_biweekly_signal_gate.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add skills/person-intelligence/scripts/biweekly_sweep.py skills/person-intelligence/tests/test_biweekly_signal_gate.py
git commit -m "feat(person-intelligence): gate Signal ingest on signal_eligible (not direct-report-only)"
```

---

### Task 3: Broaden the cron eligible-slug listing in `fetch_signal.py`

**Files:**
- Modify: `skills/person-intelligence/scripts/fetch_signal.py` (`list_reports()` ~144-160 and the `--list-reports` arg handling)
- Test: `skills/person-intelligence/tests/test_fetch_signal_listing.py` (new)

**Interfaces:**
- Consumes: `list_relationships.py` JSON (now carrying `signal_eligible`).
- Produces: `list_signal_slugs() -> list[dict]` returning `{"name","slug"}` for every `signal_eligible` relationship; new CLI flag `--list-signal` prints it as JSON. `--list-reports` is unchanged (back-compat).

- [ ] **Step 1: Write the failing test** — `tests/test_fetch_signal_listing.py`:

```python
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("fetch_signal", SCRIPTS / "fetch_signal.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_list_signal_slugs_filters_eligible(monkeypatch):
    fs = _load()
    fake = {"relationships": [
        {"name": "Adam Ferris", "signal_eligible": True},
        {"name": "Dana Ashford", "signal_eligible": False},
        {"name": "Report A", "signal_eligible": True},
    ]}
    monkeypatch.setattr(fs, "_relationships_json", lambda: fake)
    slugs = fs.list_signal_slugs()
    names = {s["name"] for s in slugs}
    assert names == {"Adam Ferris", "Report A"}
    assert {"name": "Adam Ferris", "slug": "adam-ferris"} in slugs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_fetch_signal_listing.py -v`
Expected: FAIL — `module 'fetch_signal' has no attribute 'list_signal_slugs'`

- [ ] **Step 3: Refactor `list_reports()` to share a JSON loader + add `list_signal_slugs()`.** In `fetch_signal.py`, replace the body of `list_reports()` so both use a helper:

```python
def _relationships_json():
    """Run list_relationships.py and return its parsed JSON (seam for tests)."""
    env = dict(os.environ)
    env.setdefault("OPERATING_USER_EMAIL", env.get("BUILDER_EMAIL", ""))
    out = subprocess.check_output(
        ["python3.12", str(SCRIPT_DIR / "list_relationships.py")],
        env=env, text=True, stderr=subprocess.DEVNULL,
    )
    return json.loads(out)


def list_reports():
    """Direct reports only (back-compat)."""
    data = _relationships_json()
    return [{"name": r["name"], "slug": slugify(r["name"])}
            for r in data.get("relationships", [])
            if r.get("tracking_reason") == "direct_report"]


def list_signal_slugs():
    """Every signal_eligible relationship (the broadened set)."""
    data = _relationships_json()
    return [{"name": r["name"], "slug": slugify(r["name"])}
            for r in data.get("relationships", [])
            if r.get("signal_eligible")]
```

- [ ] **Step 4: Add the CLI flag** in `main()` — register `--list-signal` and handle it alongside `--list-reports`:

```python
    ap.add_argument("--list-signal", action="store_true",
                    help="Print all signal_eligible slugs (broadened set) as JSON.")
    ...
    if args.list_signal:
        print(json.dumps(list_signal_slugs(), indent=2))
        return
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_fetch_signal_listing.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add skills/person-intelligence/scripts/fetch_signal.py skills/person-intelligence/tests/test_fetch_signal_listing.py
git commit -m "feat(person-intelligence): --list-signal for the broadened eligible set"
```

---

### Task 3B: Restrict ingest to the shareable signal tier (add `growth`, strip work-journal narrative) in `fetch_signal.py`

**Files:**
- Modify: `skills/person-intelligence/scripts/fetch_signal.py` (`normalize_history`, `normalize`, and the cache-write path so `narration_raw`/`entry_text` are stripped before caching)
- Test: `skills/person-intelligence/tests/test_fetch_signal_tier.py` (new)

**Interfaces:**
- Produces: normalized signal now includes a `growth: list[{week,text}]` field; cached raw history no longer contains `narration_raw` or `entry_text`. Adds `strip_work_journal(bundle: dict) -> dict`.
- Constraint: Person Intelligence consumes ONLY sentiment + `wins` + `friction` + `growth` (the shareable tier). The private work-journal narrative is never surfaced and never cached.

- [ ] **Step 1: Write the failing tests** — `tests/test_fetch_signal_tier.py`:

```python
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("fetch_signal", SCRIPTS / "fetch_signal.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_normalize_history_includes_growth():
    fs = _load()
    hist = {"history": [{"week_of": "2026-06-29", "extraction": {
        "wins": [{"description": "shipped X"}],
        "challenges": [],
        "growth": [{"description": "learning graph DBs"}],
    }}]}
    out = fs.normalize_history(hist)
    assert any(g["text"] == "learning graph DBs" for g in out["growth"])

def test_strip_work_journal_removes_narrative():
    fs = _load()
    bundle = {"history": {"history": [
        {"week_of": "2026-06-29", "narration_raw": "PRIVATE JOURNAL",
         "entry_text": "PRIVATE", "extraction": {"wins": [{"description": "shipped X"}]}}
    ]}}
    clean = fs.strip_work_journal(bundle)
    wk = clean["history"]["history"][0]
    assert "narration_raw" not in wk and "entry_text" not in wk
    assert wk["extraction"]["wins"][0]["description"] == "shipped X"  # signal kept
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_fetch_signal_tier.py -v`
Expected: FAIL — `normalize_history` returns no `growth` key; no attribute `strip_work_journal`.

- [ ] **Step 3: Add `growth` to `normalize_history`.** In its loop over `history`, alongside the wins/challenges handling, add growth collection and include it in the return dict:

```python
        for g in ex.get("growth", []):
            desc = g.get("description", "")
            if is_sensitive(desc):
                sensitive_dropped.append({"week": week, "kind": "growth", "reason": "sensitivity"})
                continue
            growth.append({"week": week, "text": desc})
```

Initialize `growth = []` at the top of the function (next to `wins, friction, ...`), and add `"growth": growth` to the returned dict.

- [ ] **Step 4: Surface `growth` in `normalize()`** — add `"growth": hist["growth"],` to the dict `normalize()` returns (next to `wins`/`friction`).

- [ ] **Step 5: Add `strip_work_journal` and apply it before caching.** Add the function:

```python
def strip_work_journal(bundle):
    """Remove the private work-journal narrative before anything is cached/surfaced.

    Person Intelligence consumes only the shareable signal tier (sentiment, wins,
    friction, growth). narration_raw/entry_text are the employee<->manager journal
    and must never be cached or surfaced here.
    """
    hist = (bundle.get("history") or {}).get("history")
    if isinstance(hist, list):
        for wk in hist:
            wk.pop("narration_raw", None)
            wk.pop("entry_text", None)
    return bundle
```

Then in `main()` (and `fetch_bundle` usage), call it immediately after the bundle is obtained and before `write_raw_cache`:

```python
    bundle = strip_work_journal(bundle)
    p = write_raw_cache(args.slug, bundle)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_fetch_signal_tier.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add skills/person-intelligence/scripts/fetch_signal.py skills/person-intelligence/tests/test_fetch_signal_tier.py
git commit -m "feat(person-intelligence): shareable-tier only — add growth, strip work-journal narrative"
```

---

### Task 4: `## How to Support`, provenance line, and relationship-context weave in `synthesize_profile.py`

**Files:**
- Modify: `skills/person-intelligence/scripts/synthesize_profile.py` — `build_user_prompt(data)` (def at line 151; Signal block ~244-292)
- Test: `skills/person-intelligence/tests/test_synthesize_prompt.py` (new)

**Interfaces:**
- Consumes: `data` with keys `person_name`, `relationship_type`, `meeting_summaries`, `signal`.
- Produces: the assembled prompt string contains (a) an instruction to emit `## How to Support {name}` with the three labeled buckets whenever Signal OR meeting evidence exists; (b) a provenance-line instruction for `## Signal Read`; (c) a weave instruction. No behavior change to scoring (synthesize doesn't score).

- [ ] **Step 1: Write the failing tests** — `tests/test_synthesize_prompt.py`:

```python
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("synthesize_profile", SCRIPTS / "synthesize_profile.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_how_to_support_instruction_present_with_signal():
    sp = _load()
    data = {"person_name": "Robin Alder", "relationship_type": "direct_report",
            "meeting_summaries": [{"date": "2026-07-01", "title": "1:1", "summary": "x"}],
            "signal": {"wins": [{"week": "2026-06-29", "text": "shipped auth gate"}],
                       "friction": [{"week": "2026-06-29", "text": "excluded from architecture", "category": "process"}],
                       "growth": [{"week": "2026-06-29", "text": "learning graph DBs"}],
                       "sentiment": {}, "goals": [], "submitted_weeks": ["2026-06-29"]}}
    prompt = sp.build_user_prompt(data)
    assert "## How to Support Robin Alder" in prompt
    assert "Remove friction" in prompt and "Celebrate wins" in prompt and "Support growth" in prompt
    assert "Signal source:" in prompt  # provenance-line instruction
    assert "learning graph DBs" in prompt  # growth signal rendered into the prompt

def test_how_to_support_present_from_meetings_without_signal():
    sp = _load()
    data = {"person_name": "Juan Salinas", "relationship_type": "direct_report",
            "meeting_summaries": [{"date": "2026-07-01", "title": "1:1", "summary": "x"}],
            "signal": None}
    prompt = sp.build_user_prompt(data)
    assert "## How to Support Juan Salinas" in prompt

def test_no_support_section_without_any_evidence():
    sp = _load()
    data = {"person_name": "Ghost", "relationship_type": "peer",
            "meeting_summaries": [], "signal": None}
    prompt = sp.build_user_prompt(data)
    assert "## How to Support" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_synthesize_prompt.py -v`
Expected: FAIL — assertions on missing "## How to Support" / "Signal source:" text.

- [ ] **Step 2.5: Render `growth` signals into the Signal block.** In `build_user_prompt`, inside `if signal:`, right after the friction-rendering loop (`fr = signal.get("friction") ...`), add:

```python
        gr = signal.get("growth") or []
        if gr:
            sections.append("- Growth signals (their own aspirations / learning):")
            for g in gr[:8]:
                sections.append(f"  - [{g.get('week','')}] {g.get('text','')}")
```

- [ ] **Step 3: Add the provenance-line instruction to the Signal block.** In `build_user_prompt`, inside `if signal:`, change the "produce a `## Signal Read` section" instruction so its first bullet is the provenance line. Replace the line that starts the Signal Read instruction with:

```python
        relation = {
            "direct_report": "direct report", "manager": "your manager",
            "peer": "SLT peer", "key_relationship": "key relationship",
        }.get(data.get("relationship_type", "peer"), "colleague")
        latest_week = (signal.get("submitted_weeks") or ["recent"])[0]
        sections.append(
            f"\nUsing ONLY the distilled signal above, produce a `## Signal Read` section. "
            f"Begin it with this exact provenance line:\n"
            f"*Signal source: {relation} — Quick Notes through {latest_week}.*\n"
            "Then these lines:\n"
            "- **Sentiment:** trajectory in plain words. No raw score dump.\n"
            "- **Recent wins:** 1-3, named + week.\n"
            "- **Recurring friction (themes):** theme + streak weeks; de-personalize anything sensitive.\n"
            "- **Goal health:** counts + any flagged.\n"
            "- **Submission cadence:** weekly, or a gap of N weeks.\n"
            "Then, if the signal shows evidence relevant to an ACTIVE coaching goal, emit a "
            "`<!-- DIGEST: Signal evidence for [goal] — [observation] -->` comment. NEVER write "
            "directly into Coaching Goals. NEVER include comp, health, family, or personnel content."
        )
```

(This replaces the existing final `sections.append("\nUsing ONLY the distilled signal above...")` block — keep the sensitivity language.)

- [ ] **Step 4: Add the weave instruction** right after the block above (still inside `if signal:`):

```python
        sections.append(
            "Also let this distilled signal inform 'What Energizes/Concerns Them' and any "
            "relational-patterns narrative where it genuinely adds insight — do not silo it to "
            "Signal Read. Same sensitivity rubric applies."
        )
```

- [ ] **Step 5: Add the `## How to Support` instruction** near the end of `build_user_prompt`, AFTER the signal/existing/projects blocks and BEFORE the final return/assembly. It must fire whenever meetings OR signal exist:

```python
    if (data.get("meeting_summaries") or data.get("signal")):
        nm = data.get("person_name", "them")
        srcs = []
        if data.get("signal"): srcs.append("their Signal Quick Notes (wins/friction/goals above)")
        if data.get("meeting_summaries"): srcs.append("the meeting evidence above")
        sections.append(
            f"\n## Instruction: emit a `## How to Support {nm}` section (advisory)\n"
            f"Draw on {' and '.join(srcs)}. Prefer Signal (their own words) when present. "
            f"Start the section with the HTML comment `<!-- advisory: regenerated each sweep -->` "
            f"then three bolded buckets, each with 1-3 concrete, observable actions the operating "
            f"user can take:\n"
            f"- **Remove friction:** the top friction to clear for {nm}.\n"
            f"- **Celebrate wins:** specific wins worth naming/recognizing.\n"
            f"- **Support growth:** growth or aspiration signals to back.\n"
            f"This section is ADVISORY context — it must NOT modify or duplicate the user-curated "
            f"`## Coaching Goals`. Omit any bucket with no real evidence. Same sensitivity rubric."
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_synthesize_prompt.py -v`
Expected: PASS (all 3)

- [ ] **Step 7: Commit**

```bash
git add skills/person-intelligence/scripts/synthesize_profile.py skills/person-intelligence/tests/test_synthesize_prompt.py
git commit -m "feat(person-intelligence): How-to-Support section, Signal provenance line, context weave"
```

---

### Task 5: Surface "How to Support" in `generate_team_pulse.py`

**Files:**
- Modify: `skills/person-intelligence/scripts/generate_team_pulse.py` (`load_profile_data` ~84, `build_pulse_input` ~110, `build_user_prompt` ~138)
- Test: `skills/person-intelligence/tests/test_team_pulse_support.py` (new)

**Interfaces:**
- Consumes: profile markdown that may contain a `## How to Support` section (Task 4).
- Produces: `extract_support_section(profile_text) -> str | None`; per-person prompt lines include the support section; the template instructs one "Support:" line per person.

- [ ] **Step 1: Write the failing test** — `tests/test_team_pulse_support.py`:

```python
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("generate_team_pulse", SCRIPTS / "generate_team_pulse.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_extract_support_section():
    gtp = _load()
    text = ("# X\n\n## Signal Read\n\nstuff\n\n## How to Support X\n"
            "**Remove friction:** give her a seat.\n**Celebrate wins:** name the ship.\n\n## Personal\n\nz\n")
    out = gtp.extract_support_section(text)
    assert out is not None
    assert "Remove friction" in out and "seat" in out
    assert "Personal" not in out

def test_extract_support_section_absent():
    gtp = _load()
    assert gtp.extract_support_section("# X\n\n## Personal\n\nz\n") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_team_pulse_support.py -v`
Expected: FAIL — `no attribute 'extract_support_section'`

- [ ] **Step 3: Add `extract_support_section`** (near `latest_journal_entry` ~63):

```python
def extract_support_section(profile_text, max_chars=800):
    """Return the '## How to Support' section body, or None."""
    import re
    m = re.search(r"^## How to Support[^\n]*\n", profile_text, re.MULTILINE)
    if not m:
        return None
    after = profile_text[m.end():]
    nxt = re.search(r"^## ", after, re.MULTILINE)
    body = (after[:nxt.start()] if nxt else after).strip()
    return body[:max_chars] or None
```

- [ ] **Step 4: Include it in `build_pulse_input`** — where each `entry` is built from `profile` (~123-129), add:

```python
            entry["how_to_support"] = extract_support_section(profile["text"]) \
                if profile.get("text") else None
```

(Ensure `load_profile_data` returns the raw `text`; if it currently returns only `frontmatter`/`latest_journal`, add `"text": text` to its return dict at ~90-99.)

- [ ] **Step 5: Include it in the per-person prompt + template** — in `build_user_prompt` after the journal lines (~156), add:

```python
        if r.get("how_to_support"):
            lines.append(f"  - How to support:\n{r['how_to_support']}")
```

And in the pulse template/system prompt (the instruction text near the top of the file, ~30-46), add one bullet to the per-person output spec:

```
- Support: one line — the single highest-leverage move this cycle (remove [friction] / celebrate [win]), drawn from the person's "How to support" block when present.
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd skills/person-intelligence && python3.12 -m pytest tests/test_team_pulse_support.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add skills/person-intelligence/scripts/generate_team_pulse.py skills/person-intelligence/tests/test_team_pulse_support.py
git commit -m "feat(person-intelligence): surface How-to-Support in team pulse"
```

---

### Task 6: Docs — scope + score-free assertion

**Files:**
- Modify: `skills/person-intelligence/SKILL.md`, `skills/person-intelligence/references/ingest-scoping.md`

**Interfaces:** none (documentation).

- [ ] **Step 1: Update the Ingest Sources table + scoping note in `SKILL.md`.** Change the Signal row from "direct reports only" to describe the broadened, eligibility-gated scope, and add a bolded assertion:

```markdown
**Signal never contributes to `health_score`.** Scoring reads Fathom-meeting
evidence only; Signal feeds the `## Signal Read` and `## How to Support` sections
and relationship context — coaching, not the number.
```

Update the Signal scope line to: "any tracked person who is `signal_eligible` (NSLS email, not board/external; see `list_relationships.py`), `SIGNAL_INGEST=1`. Distilled into `## Signal Read` + advisory `## How to Support`."

- [ ] **Step 2: Update `references/ingest-scoping.md`** Signal section to match: broadened scope, the `SIGNAL_EXCLUDE` default, provenance line, and the score-free rule. (Mirror the SKILL.md wording; keep the privacy posture paragraph.)

- [ ] **Step 3: Commit**

```bash
git add skills/person-intelligence/SKILL.md skills/person-intelligence/references/ingest-scoping.md
git commit -m "docs(person-intelligence): broadened Signal scope + score-free assertion"
```

---

## Self-Review

**Spec coverage:**
- R1 coaching action → Task 4 (`## How to Support`). ✓
- R2 broaden scope → Tasks 1, 2, 3. ✓
- R3 weave into relationship context → Task 4 Step 4. ✓
- R4 score stays Signal-free → Task 6 assertion (no code change needed; scoring never reads `data["signal"]`). ✓
- R5 sensitivity + provenance → Task 4 Step 3 provenance line; safeguards preserved (constraint). ✓
- R6 pulse surfacing → Task 5. ✓
- R7 shareable-tier boundary (+ growth) → Task 3B (add `growth`, strip `narration_raw`/`entry_text` before caching). ✓

**Placeholder scan:** No TBD/TODO; every code step shows real code; test bodies are concrete. One conditional ("if the suite injects the org chart differently, mirror it") is a real instruction to match existing fixtures, not a placeholder — the implementer reads `test_list_relationships.py` which is already present.

**Type consistency:** `signal_eligible` (bool key) produced in Task 1, consumed in Tasks 2 & 3. `is_signal_eligible(name, email, tracking_reason)` signature consistent. `list_signal_slugs()` / `_relationships_json()` names consistent across Task 3. `extract_support_section(profile_text)` consistent in Task 5. `plan_signal(rel, signal_available)` consistent in Task 2. `build_user_prompt(data)` matches the existing signature in `synthesize_profile.py`.

**Risk note for implementer:** the LLM-output tests (does the model actually emit a good `## How to Support`?) are NOT unit-testable — the unit tests assert the *prompt* contains the instructions. Validate model output once manually via an end-to-end run on one direct report (e.g. Robin Alder) after Task 4, and confirm the health score is identical whether `signal` is present or `None` in the payload (proves R4).
