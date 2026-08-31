# Portfolio Quadrant Allocation (Part A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Report each week's working time by portfolio quadrant (① growth-driver / ② operating-efficiency / ③ hygiene / ④ reliability) **and** by offense/defense mode, with every number traceable to the rule that produced it.

**Architecture:** Split deterministic from judgment. A new `companion/portfolio.py` holds the pure functions — role-map parsing, the meeting cascade, week aggregation, flag evaluation — unit-tested in `companion/tests/test_portfolio.py`. Judgment that only an LLM can do (inferring offense/defense from Work Log prose, mapping a Fathom topic to a quadrant) stays as prose in `skills/close-week/references/portfolio-attribution.md`. This mirrors the existing `companion/streak.py` pattern, whose docstring states the rule "lives in exactly two places: this module and the prose paragraph in close-day's prompt."

**Tech Stack:** Python 3.10+, pytest (existing suite at `companion/tests/`, config in `companion/pyproject.toml`), Markdown skill prose.

**Spec:** `docs/specs/2026-08-29-portfolio-quadrant-and-alignment-design.md`

## Global Constraints

- **Quadrant vocabulary is exactly five values**, copied verbatim from the spec: `growth-driver`, `operating-efficiency`, `hygiene`, `reliability`, `cross-cutting`. No others. No synonyms.
- **Mode vocabulary is exactly two values:** `offense`, `defense`.
- **Nothing that names a person goes in this repo.** `~/.claude/portfolio-role-map.txt` and `~/.claude/portfolio-meeting-cache.json` live outside it. Tests use fictional names.
- **Every resolution records `resolved_by`** — one of `role`, `topic`, `project`, `unresolved`. A quadrant with no `resolved_by` is a bug.
- **Unresolved is a reported outcome, never a silent absorb.** Unresolved hours appear as their own line and still count toward the week total.
- **④ starvation flag fires at 0h for 2 consecutive weeks.** ② over-share flag fires above 40%.
- **Run tests from the `companion/` directory** — `pytest.ini_options` sets `testpaths = ["tests"]` and `pythonpath = [".."]`.
- **Part B does not begin until Task 9 passes.**

---

## Prerequisites (human decisions — not code, and they block Task 7 onward)

These come from spec §6. Tasks 1–6 can proceed without them; Task 7 cannot.

- [ ] **P1. Categorize the five active projects lacking a category.** Assistant proposes a `portfolio-category` and `portfolio-role` for each; the builder confirms or corrects. The projects are named only in the builder's own vault, never in this repo — this repo is public and real internal project names do not appear in it.
- [ ] **P2. Re-scope the open Asana task** that proposes promoting reliability items into tracked project files so quadrant ④ stops reading zero. Under quadrant × mode it models the wrong thing. The builder decides: re-scope, or close as superseded. (The task is identified in the builder's own tracker; its id is not recorded here.)
- [ ] **P3. Seed `~/.claude/portfolio-role-map.txt`.** Assistant drafts from the org chart; the builder corrects. Only roles narrow enough to be decisive. Broad roles are deliberately omitted so the topic rule fires.

---

## File Structure

| File | Responsibility | New? |
|---|---|---|
| `companion/portfolio.py` | Deterministic quadrant logic: role map, cascade, aggregation, flags | **create** |
| `companion/tests/test_portfolio.py` | Unit tests for the above | **create** |
| `skills/close-week/references/portfolio-attribution.md` | Judgment prose: mode vocabulary, topic mapping, worked examples, confirm-gate format | **create** |
| `skills/close-day/SKILL.md` | Emit per-project hours + provisional quadrant/mode in `## Projects Touched` | modify |
| `skills/close-week/SKILL.md` | New Step 2a; Output A `## Portfolio Allocation`; Output B grouped by quadrant | modify |
| `~/.claude/portfolio-role-map.txt` | person → quadrant (outside repo) | **create, P3** |

---

### Task 1: Quadrant vocabulary and role-map parsing

**Files:**
- Create: `companion/portfolio.py`
- Test: `companion/tests/test_portfolio.py`

**Interfaces:**
- Consumes: nothing
- Produces: `QUADRANTS: tuple[str, ...]`, `CROSS_CUTTING: str`, `RoleRule(match: str, quadrant: str, comment: str)`, `parse_role_map(text: str) -> list[RoleRule]`

- [ ] **Step 1: Write the failing test**

```python
# companion/tests/test_portfolio.py
import pytest
from companion.portfolio import (
    QUADRANTS, CROSS_CUTTING, RoleRule, parse_role_map,
)


def test_quadrant_vocabulary_is_exactly_the_five_spec_values():
    assert QUADRANTS == (
        "growth-driver",
        "operating-efficiency",
        "hygiene",
        "reliability",
    )
    assert CROSS_CUTTING == "cross-cutting"


def test_parse_role_map_reads_a_basic_rule():
    text = "Dana Vance  → hygiene   # security / governance\n"
    rules = parse_role_map(text)
    assert rules == [RoleRule(match="dana vance", quadrant="hygiene",
                              comment="security / governance")]


def test_parse_role_map_accepts_ascii_arrow():
    rules = parse_role_map("Dana Vance -> hygiene\n")
    assert rules[0].quadrant == "hygiene"


def test_parse_role_map_skips_comments_and_blank_lines():
    text = "# a comment\n\n   \nDana Vance → hygiene\n# trailing note\n"
    assert len(parse_role_map(text)) == 1


def test_parse_role_map_drops_unknown_quadrants_rather_than_guessing():
    text = "Dana Vance → nonsense-quadrant\nRio Okafor → reliability\n"
    rules = parse_role_map(text)
    assert [r.match for r in rules] == ["rio okafor"]


def test_parse_role_map_handles_an_absent_file_as_empty():
    assert parse_role_map("") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd companion && pytest tests/test_portfolio.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'companion.portfolio'`

- [ ] **Step 3: Write minimal implementation**

```python
# companion/portfolio.py
"""Deterministic portfolio-quadrant logic for the NSLS toolkit.

Mirrors the prose in skills/close-week/references/portfolio-attribution.md.
The judgment half (inferring offense/defense from Work Log prose, mapping a
Fathom topic to a quadrant) lives only in that prose; the arithmetic and the
cascade live only here. Keep both in sync — same contract as streak.py.
"""

from dataclasses import dataclass

QUADRANTS: tuple[str, ...] = (
    "growth-driver",
    "operating-efficiency",
    "hygiene",
    "reliability",
)
CROSS_CUTTING = "cross-cutting"
_VALID = set(QUADRANTS) | {CROSS_CUTTING}


@dataclass(frozen=True)
class RoleRule:
    match: str      # lowercased substring matched against attendee name/email
    quadrant: str
    comment: str = ""


def parse_role_map(text: str) -> list[RoleRule]:
    """Parse ~/.claude/portfolio-role-map.txt. Unknown quadrants are dropped,
    never guessed — a typo must lose its rule loudly, not silently mis-file
    a whole category of meetings."""
    rules: list[RoleRule] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        body, _, comment = line.partition("#")
        arrow = "→" if "→" in body else ("->" if "->" in body else None)
        if arrow is None:
            continue
        left, _, right = body.partition(arrow)
        quadrant = right.strip().lower()
        match = left.strip().lower()
        if not match or quadrant not in _VALID:
            continue
        rules.append(RoleRule(match=match, quadrant=quadrant,
                              comment=comment.strip()))
    return rules
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd companion && pytest tests/test_portfolio.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add companion/portfolio.py companion/tests/test_portfolio.py
git commit -m "feat(portfolio): quadrant vocabulary and role-map parsing"
```

---

### Task 2: Project quadrant lookup from frontmatter

**Files:**
- Modify: `companion/portfolio.py`
- Test: `companion/tests/test_portfolio.py`

**Interfaces:**
- Consumes: `QUADRANTS`, `CROSS_CUTTING` from Task 1
- Produces: `project_quadrant(frontmatter: dict[str, str]) -> str | None`, `is_driver(frontmatter: dict[str, str]) -> bool`

- [ ] **Step 1: Write the failing test**

```python
from companion.portfolio import project_quadrant, is_driver


def test_project_quadrant_reads_portfolio_category():
    assert project_quadrant({"portfolio-category": "growth-driver"}) == "growth-driver"


def test_project_quadrant_returns_none_when_absent_so_caller_must_handle_it():
    assert project_quadrant({}) is None
    assert project_quadrant({"portfolio-category": ""}) is None


def test_project_quadrant_rejects_a_value_outside_the_vocabulary():
    # 'founder-transition' exists in the vault today and is NOT a quadrant.
    assert project_quadrant({"portfolio-category": "founder-transition"}) is None


def test_project_quadrant_accepts_cross_cutting():
    assert project_quadrant({"portfolio-category": "cross-cutting"}) == "cross-cutting"


def test_is_driver_reads_portfolio_role():
    assert is_driver({"portfolio-role": "driver"}) is True
    assert is_driver({"portfolio-role": "held"}) is False
    assert is_driver({}) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd companion && pytest tests/test_portfolio.py -k "project_quadrant or is_driver" -v`
Expected: FAIL — `ImportError: cannot import name 'project_quadrant'`

- [ ] **Step 3: Write minimal implementation**

```python
def project_quadrant(frontmatter: dict[str, str]) -> str | None:
    """The project's DEFAULT quadrant. Returns None when absent or outside the
    vocabulary, so the caller surfaces it rather than inventing a bucket.
    Note: 'founder-transition' appears in the vault as a legacy value and is
    deliberately not accepted — such projects map to cross-cutting by hand."""
    value = (frontmatter.get("portfolio-category") or "").strip().lower()
    return value if value in _VALID else None


def is_driver(frontmatter: dict[str, str]) -> bool:
    return (frontmatter.get("portfolio-role") or "").strip().lower() == "driver"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd companion && pytest tests/test_portfolio.py -v`
Expected: PASS, 11 tests

- [ ] **Step 5: Commit**

```bash
git add companion/portfolio.py companion/tests/test_portfolio.py
git commit -m "feat(portfolio): project quadrant lookup from frontmatter"
```

---

### Task 3: The meeting cascade

**Files:**
- Modify: `companion/portfolio.py`
- Test: `companion/tests/test_portfolio.py`

**Interfaces:**
- Consumes: `RoleRule`, `_VALID` from Task 1
- Produces: `Resolution(quadrant, resolved_by, splits, note)`, `resolve_meeting(attendees, topics, project_quadrant, role_map) -> Resolution`
  - `attendees: list[str]` — names or emails
  - `topics: list[tuple[str, float]]` — `(quadrant, share)` pairs the LLM supplied; share sums to 1.0
  - `project_quadrant: str | None`
  - `splits: tuple[tuple[str, float], ...]` — empty unless the topic rule split the meeting

- [ ] **Step 1: Write the failing test**

```python
from companion.portfolio import Resolution, resolve_meeting

ROLE_MAP = [RoleRule(match="dana vance", quadrant="hygiene")]


def test_role_rule_wins_over_topic_and_project():
    r = resolve_meeting(
        attendees=["Dana Vance", "kp@example.org"],
        topics=[("growth-driver", 1.0)],
        project_quadrant="operating-efficiency",
        role_map=ROLE_MAP,
    )
    assert r.quadrant == "hygiene"
    assert r.resolved_by == "role"


def test_role_matches_on_email_local_part():
    r = resolve_meeting(["dana.vance@example.org"], [], None, ROLE_MAP)
    assert r.resolved_by == "role"


def test_topic_decides_when_no_role_matches():
    r = resolve_meeting(["Rio Okafor"], [("growth-driver", 1.0)],
                        "operating-efficiency", ROLE_MAP)
    assert r.quadrant == "growth-driver"
    assert r.resolved_by == "topic"
    assert r.splits == ()


def test_topic_splits_a_meeting_across_two_quadrants():
    r = resolve_meeting(
        ["Rio Okafor"],
        [("growth-driver", 0.6), ("operating-efficiency", 0.4)],
        None, ROLE_MAP,
    )
    assert r.resolved_by == "topic"
    assert r.quadrant is None            # no single quadrant when split
    assert r.splits == (("growth-driver", 0.6), ("operating-efficiency", 0.4))


def test_project_is_the_fallback_when_no_role_and_no_topic():
    r = resolve_meeting(["Rio Okafor"], [], "reliability", ROLE_MAP)
    assert r.quadrant == "reliability"
    assert r.resolved_by == "project"


def test_unresolved_is_reported_not_absorbed():
    r = resolve_meeting(["Rio Okafor"], [], None, ROLE_MAP)
    assert r.quadrant is None
    assert r.resolved_by == "unresolved"


def test_topic_shares_that_do_not_sum_to_one_are_normalised_and_noted():
    r = resolve_meeting(["Rio Okafor"],
                        [("growth-driver", 1.0), ("hygiene", 1.0)],
                        None, ROLE_MAP)
    assert r.splits == (("growth-driver", 0.5), ("hygiene", 0.5))
    assert "normalised" in r.note
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd companion && pytest tests/test_portfolio.py -k resolve_meeting -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_meeting'`

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class Resolution:
    quadrant: str | None
    resolved_by: str                                   # role|topic|project|unresolved
    splits: tuple[tuple[str, float], ...] = ()
    note: str = ""


def resolve_meeting(
    attendees: list[str],
    topics: list[tuple[str, float]],
    project_quadrant: str | None,
    role_map: list[RoleRule],
) -> Resolution:
    """First rule that resolves wins: role -> topic -> project -> unresolved."""
    for person in attendees:
        needle = person.lower()
        local = needle.split("@")[0].replace(".", " ")
        for rule in role_map:
            if rule.match in needle or rule.match in local:
                return Resolution(rule.quadrant, "role")

    valid_topics = [(q, s) for q, s in topics if q in _VALID and s > 0]
    if valid_topics:
        total = sum(s for _, s in valid_topics)
        note = ""
        if abs(total - 1.0) > 1e-6:
            valid_topics = [(q, s / total) for q, s in valid_topics]
            note = "shares normalised"
        if len(valid_topics) == 1:
            return Resolution(valid_topics[0][0], "topic", note=note)
        return Resolution(None, "topic", tuple(valid_topics), note)

    if project_quadrant in _VALID:
        return Resolution(project_quadrant, "project")

    return Resolution(None, "unresolved")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd companion && pytest tests/test_portfolio.py -v`
Expected: PASS, 18 tests

- [ ] **Step 5: Commit**

```bash
git add companion/portfolio.py companion/tests/test_portfolio.py
git commit -m "feat(portfolio): meeting cascade with resolved_by provenance"
```

---

### Task 4: Week aggregation by quadrant and mode

**Files:**
- Modify: `companion/portfolio.py`
- Test: `companion/tests/test_portfolio.py`

**Interfaces:**
- Consumes: `Resolution` from Task 3
- Produces: `ProjectWeek(project, quadrant, offense_pct, hours)`, `MeetingRow(label, resolution, hours)`, `aggregate(project_weeks, meeting_rows) -> WeekTotals`
  - `WeekTotals(by_quadrant: dict[str, float], by_mode: dict[str, float], unresolved_hours: float, total_hours: float)`

- [ ] **Step 1: Write the failing test**

```python
from companion.portfolio import ProjectWeek, MeetingRow, aggregate


def test_aggregate_sums_project_hours_into_quadrants():
    totals = aggregate(
        [ProjectWeek("alpha", "growth-driver", 100, 3.0),
         ProjectWeek("beta", "reliability", 0, 1.0)],
        [],
    )
    assert totals.by_quadrant["growth-driver"] == 3.0
    assert totals.by_quadrant["reliability"] == 1.0
    assert totals.total_hours == 4.0


def test_aggregate_splits_project_hours_by_mode():
    totals = aggregate([ProjectWeek("alpha", "growth-driver", 65, 4.0)], [])
    assert totals.by_mode["offense"] == pytest.approx(2.6)
    assert totals.by_mode["defense"] == pytest.approx(1.4)


def test_aggregate_apportions_a_split_meeting_across_quadrants():
    row = MeetingRow(
        "standing",
        Resolution(None, "topic", (("growth-driver", 0.6),
                                   ("operating-efficiency", 0.4))),
        1.5,
    )
    totals = aggregate([], [row])
    assert totals.by_quadrant["growth-driver"] == pytest.approx(0.9)
    assert totals.by_quadrant["operating-efficiency"] == pytest.approx(0.6)


def test_unresolved_meeting_hours_are_reported_and_still_count_to_total():
    row = MeetingRow("adhoc", Resolution(None, "unresolved"), 1.0)
    totals = aggregate([], [row])
    assert totals.unresolved_hours == 1.0
    assert totals.total_hours == 1.0
    assert sum(totals.by_quadrant.values()) == 0.0


def test_meetings_carry_no_mode_so_mode_totals_come_only_from_projects():
    row = MeetingRow("sync", Resolution("growth-driver", "project"), 2.0)
    totals = aggregate([ProjectWeek("alpha", "growth-driver", 50, 2.0)], [row])
    assert totals.by_mode["offense"] == pytest.approx(1.0)
    assert totals.by_mode["defense"] == pytest.approx(1.0)
    assert totals.by_quadrant["growth-driver"] == pytest.approx(4.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd companion && pytest tests/test_portfolio.py -k aggregate -v`
Expected: FAIL — `ImportError: cannot import name 'ProjectWeek'`

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class ProjectWeek:
    project: str
    quadrant: str
    offense_pct: int        # 0-100; defense is the remainder
    hours: float


@dataclass(frozen=True)
class MeetingRow:
    label: str
    resolution: Resolution
    hours: float


@dataclass(frozen=True)
class WeekTotals:
    by_quadrant: dict[str, float]
    by_mode: dict[str, float]
    unresolved_hours: float
    total_hours: float


def aggregate(project_weeks: list[ProjectWeek],
              meeting_rows: list[MeetingRow]) -> WeekTotals:
    """Mode comes only from project work. A meeting has a quadrant but no
    offense/defense reading — inferring one from a transcript would be a
    judgment this module deliberately does not make."""
    by_quadrant: dict[str, float] = {q: 0.0 for q in (*QUADRANTS, CROSS_CUTTING)}
    by_mode = {"offense": 0.0, "defense": 0.0}
    unresolved = 0.0
    total = 0.0

    for pw in project_weeks:
        total += pw.hours
        if pw.quadrant in by_quadrant:
            by_quadrant[pw.quadrant] += pw.hours
        else:
            unresolved += pw.hours
        by_mode["offense"] += pw.hours * pw.offense_pct / 100.0
        by_mode["defense"] += pw.hours * (100 - pw.offense_pct) / 100.0

    for row in meeting_rows:
        total += row.hours
        res = row.resolution
        if res.splits:
            for quadrant, share in res.splits:
                by_quadrant[quadrant] += row.hours * share
        elif res.quadrant in by_quadrant:
            by_quadrant[res.quadrant] += row.hours
        else:
            unresolved += row.hours

    return WeekTotals(by_quadrant, by_mode, unresolved, total)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd companion && pytest tests/test_portfolio.py -v`
Expected: PASS, 23 tests

- [ ] **Step 5: Commit**

```bash
git add companion/portfolio.py companion/tests/test_portfolio.py
git commit -m "feat(portfolio): week aggregation by quadrant and mode"
```

---

### Task 5: Flag evaluation

**Files:**
- Modify: `companion/portfolio.py`
- Test: `companion/tests/test_portfolio.py`

**Interfaces:**
- Consumes: `WeekTotals` from Task 4
- Produces: `evaluate_flags(current: WeekTotals, history: list[WeekTotals], driver_hours: float, held_hours: float) -> list[str]`
  - `history` is prior weeks, most recent first

- [ ] **Step 1: Write the failing test**

```python
from companion.portfolio import evaluate_flags, WeekTotals


def _totals(quadrants, offense=1.0, defense=1.0, total=None):
    base = {q: 0.0 for q in ("growth-driver", "operating-efficiency",
                             "hygiene", "reliability", "cross-cutting")}
    base.update(quadrants)
    return WeekTotals(base, {"offense": offense, "defense": defense}, 0.0,
                      total if total is not None else sum(base.values()))


def test_reliability_starvation_fires_at_two_consecutive_zero_weeks():
    prior = _totals({"growth-driver": 5.0})
    current = _totals({"growth-driver": 5.0})
    flags = evaluate_flags(current, [prior], driver_hours=5.0, held_hours=0.0)
    assert any("reliability" in f.lower() for f in flags)


def test_reliability_starvation_does_not_fire_on_a_single_zero_week():
    prior = _totals({"reliability": 1.0})
    current = _totals({"growth-driver": 5.0})
    flags = evaluate_flags(current, [prior], driver_hours=5.0, held_hours=0.0)
    assert not any("reliability" in f.lower() for f in flags)


def test_operating_efficiency_over_forty_percent_fires():
    current = _totals({"operating-efficiency": 5.0, "growth-driver": 4.0})
    flags = evaluate_flags(current, [], driver_hours=9.0, held_hours=0.0)
    assert any("operating-efficiency" in f for f in flags)


def test_rising_defense_share_fires():
    prior = _totals({"growth-driver": 10.0}, offense=9.0, defense=1.0)
    current = _totals({"growth-driver": 10.0}, offense=5.0, defense=5.0)
    flags = evaluate_flags(current, [prior], driver_hours=10.0, held_hours=0.0)
    assert any("defense" in f.lower() for f in flags)


def test_held_out_earning_driver_fires():
    current = _totals({"growth-driver": 6.0})
    flags = evaluate_flags(current, [], driver_hours=1.0, held_hours=5.0)
    assert any("held" in f.lower() for f in flags)


def test_a_clean_week_produces_no_flags():
    prior = _totals({"reliability": 1.0, "growth-driver": 9.0},
                    offense=8.0, defense=2.0)
    current = _totals({"reliability": 1.0, "growth-driver": 9.0},
                      offense=8.0, defense=2.0)
    assert evaluate_flags(current, [prior], driver_hours=9.0, held_hours=1.0) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd companion && pytest tests/test_portfolio.py -k flags -v`
Expected: FAIL — `ImportError: cannot import name 'evaluate_flags'`

- [ ] **Step 3: Write minimal implementation**

```python
RELIABILITY_ZERO_WEEKS = 2
OPERATING_EFFICIENCY_CEILING = 0.40


def evaluate_flags(current: WeekTotals, history: list[WeekTotals],
                   driver_hours: float, held_hours: float) -> list[str]:
    """Each flag names the decision it forces. A flag with no decision
    attached does not belong here."""
    flags: list[str] = []

    recent = [current, *history][:RELIABILITY_ZERO_WEEKS]
    if (len(recent) == RELIABILITY_ZERO_WEEKS
            and all(w.by_quadrant.get("reliability", 0.0) == 0.0 for w in recent)):
        flags.append(
            f"Reliability starving — 0h for {RELIABILITY_ZERO_WEEKS} consecutive "
            "weeks. Fund it, or say out loud you are not."
        )

    if current.total_hours > 0:
        share = current.by_quadrant.get("operating-efficiency", 0.0) / current.total_hours
        if share > OPERATING_EFFICIENCY_CEILING:
            flags.append(
                f"operating-efficiency at {share:.0%} — the machine is eating "
                "the output it exists to produce."
            )

    if history:
        def defense_share(w: WeekTotals) -> float:
            spent = w.by_mode["offense"] + w.by_mode["defense"]
            return w.by_mode["defense"] / spent if spent else 0.0
        if defense_share(current) > defense_share(history[0]):
            flags.append(
                f"Defense share rose to {defense_share(current):.0%} — your best "
                "assets are decaying under you."
            )

    if held_hours > driver_hours:
        flags.append(
            f"held projects out-earned drivers ({held_hours:.1f}h vs "
            f"{driver_hours:.1f}h) — the ranking is not what you are doing."
        )

    return flags
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd companion && pytest tests/test_portfolio.py -v`
Expected: PASS, 29 tests

- [ ] **Step 5: Commit**

```bash
git add companion/portfolio.py companion/tests/test_portfolio.py
git commit -m "feat(portfolio): flag evaluation with decisions attached"
```

---

### Task 6: The judgment prose reference

**Files:**
- Create: `skills/close-week/references/portfolio-attribution.md`

**Interfaces:**
- Consumes: the module contract from Tasks 1–5 (names it explicitly so the two halves stay in sync)
- Produces: the prose contract that close-day and close-week both read

- [ ] **Step 1: Write the reference file**

It must contain, and nothing more:

1. A **sync header** naming `companion/portfolio.py` as the other half, in the style of `streak.py`'s docstring: arithmetic and cascade live in the module; mode inference and topic mapping live here; changing one without the other is the bug this header exists to prevent.
2. The **five-value quadrant vocabulary**, verbatim.
3. The **mode vocabulary table** copied from spec §3.4 — offense verbs (built, shipped, launched, scoped, designed, decided, drafted, prototyped, negotiated) and defense verbs (fixed, migrated, rotated, restored, unblocked, renewed, patched, reconciled, recovered, verified) — plus the rule that ambiguous bullets default to offense and are surfaced in the gate.
4. **Topic → quadrant mapping guidance** with the split rule from spec §3.3 rule 2, including the `even-split (no timestamps)` fallback.
5. **The confirm-gate table format**, verbatim from spec §3.5.
6. **Three worked examples** drawn from the week of 2026-08-22 — one role resolution, one topic split, one project fallback — with the expected `resolved_by` for each.
7. **The unresolved rule:** reported as its own line, never absorbed, still counted in the total.

- [ ] **Step 2: Verify the vocabularies match the module exactly**

Run:
```bash
cd ~/nsls-skills/nsls-personal-toolkit
python3 - <<'EOF'
import re, pathlib, sys
sys.path.insert(0, ".")
from companion.portfolio import QUADRANTS, CROSS_CUTTING
prose = pathlib.Path("skills/close-week/references/portfolio-attribution.md").read_text()
missing = [q for q in (*QUADRANTS, CROSS_CUTTING) if q not in prose]
print("MISSING FROM PROSE:", missing or "none")
assert not missing
EOF
```
Expected: `MISSING FROM PROSE: none`

- [ ] **Step 3: Commit**

```bash
git add skills/close-week/references/portfolio-attribution.md
git commit -m "docs(close-week): portfolio attribution judgment reference"
```

---

### Task 7: close-day emits per-project hours and a provisional quadrant

**Files:**
- Modify: `skills/close-day/SKILL.md` — the `## Projects Touched` format block in Step 3, and Step 2 ("Identify projects touched")

**Blocked by:** P1, P3

**Interfaces:**
- Consumes: `portfolio-attribution.md` (Task 6)
- Produces: a `## Projects Touched` line format that close-week Task 8 parses:
  `- [[20-projects/<slug>|<slug>]] — <summary> · <X.X>h · <quadrant> · <NN>% offense`

- [ ] **Step 1: Update the Projects Touched format in Step 3**

Replace the existing format line with the one above, and add beneath it:

> Hours come from the same Familiar attribution that produced Time Allocation. Quadrant is the project's `portfolio-category` frontmatter — **provisional**, because close-week's confirm gate may override it when the week's activity says otherwise. Offense/offense-defense split is inferred from this note's own Work Log bullets using the vocabulary in `skills/close-week/references/portfolio-attribution.md`. A project with no `portfolio-category` renders `· uncategorized ·` and is **not** guessed.

- [ ] **Step 2: Add a pointer in Step 2**

Add to the project-mapping signal list: *"Read `skills/close-week/references/portfolio-attribution.md` for the quadrant vocabulary and the mode-inference verbs. Do not invent quadrant values."*

- [ ] **Step 3: Verify by running one real close-day against a known day**

Run `/close-day` against a known recent day and confirm the `## Projects Touched` section renders hours, a quadrant, and an offense percentage for at least one project that carries a `portfolio-category`, and renders `uncategorized` rather than a guess for any project lacking frontmatter.
Expected: the format above, with the categorized project carrying a quadrant.

- [ ] **Step 4: Commit**

```bash
git add skills/close-day/SKILL.md
git commit -m "feat(close-day): emit per-project hours and provisional quadrant"
```

---

### Task 8: close-week Step 2a, Output A, and Output B

**Files:**
- Modify: `skills/close-week/SKILL.md` — new Step 2a after the Business Numbers block in Step 2; Output A section list; Output B template

**Blocked by:** Tasks 6, 7

**Interfaces:**
- Consumes: close-day's `## Projects Touched` line format (Task 7); `companion/portfolio.py` (Tasks 1–5)
- Produces: `## Portfolio Allocation` in the weekly note; a quadrant-grouped Project Progress block in Quick Notes

- [ ] **Step 1: Add Step 2a — Portfolio attribution**

Insert immediately after the Business Numbers table and before Achievements, because the grouping drives them. It must specify: read the seven daily notes' `## Projects Touched` lines for hours and provisional quadrants; read `~/.claude/portfolio-role-map.txt`; read `~/.claude/portfolio-meeting-cache.json` for cached recurring meetings; resolve each meeting through the cascade; present the confirm-gate table from `portfolio-attribution.md`; **write nothing before confirmation**; on confirm, write new recurring answers back to the cache.

- [ ] **Step 2: Add `## Portfolio Allocation` to Output A**

```markdown
## Portfolio Allocation

| Quadrant | Hours | % | Offense / Defense | Top items |
|---|---|---|---|---|
| ① Growth driver | 0.0h | 0% | 0% / 0% | — |
| ② Operating efficiency | 0.0h | 0% | 0% / 0% | — |
| ③ Hygiene | 0.0h | 0% | 0% / 0% | — |
| ④ Reliability | 0.0h | 0% | 0% / 0% | — |
| Cross-cutting | 0.0h | 0% | — | — |
| Unresolved | 0.0h | 0% | — | — |

**Offense / Defense: X% / Y%** (project work only — meetings carry a quadrant, not a mode)

**Flags:**
- [one line per flag from evaluate_flags, or "none this week"]
```

- [ ] **Step 3: Restructure Output B's Project Progress**

Replace the flat list with a quadrant-grouped block, keeping it paste-safe plain text:

```
Project Progress (by portfolio quadrant):
(1) Growth driver - Xh
  <project>: <status> - <one line>
(2) Operating efficiency - Xh
  <project>: <status> - <one line>
(3) Hygiene - Xh
  <project>: <status> - <one line>
(4) Reliability - Xh
  <project>: <status> - <one line>
```

Add the rule: *when a quadrant has no project movement, print the quadrant with `- 0h, nothing moved` rather than omitting the heading. An omitted quadrant is how reliability disappears.*

- [ ] **Step 4: Add the 2×2 grouping rule to the Rules block**

*"Group Project Progress by portfolio quadrant in both Output A and Output B, reading each project's `portfolio-category`. Never omit an empty quadrant."*

- [ ] **Step 5: Commit**

```bash
git add skills/close-week/SKILL.md
git commit -m "feat(close-week): portfolio attribution step and quadrant-grouped outputs"
```

---

### Task 9: Acceptance test — reproduce W35 (THE GATE)

**Files:**
- Create: `companion/tests/test_portfolio_w35.py`

**Blocked by:** Tasks 1–8. **Part B does not start until this passes.**

**Interfaces:**
- Consumes: everything above

- [ ] **Step 1: Write the acceptance test with the known W35 answers**

The week of 2026-08-22 → 2026-08-28 was closed by hand; the answers are known. Encode the hand-built figures as fixtures and assert the pipeline reproduces them.

```python
# companion/tests/test_portfolio_w35.py
"""Acceptance test: reproduce a week whose answer is already known.

Hand-built close for 2026-08-22..28 recorded 52.6h total, ~23.75h of meetings
across 26, a parked build lane at ~4h, and a 30-day silent-outage fix. If the
pipeline cannot reproduce this week, it is not ready for one we do not know.

Project slugs and meeting labels are ANONYMISED (project-a .. project-g,
generic ceremony names) because this repo is public and real internal project
or person names never appear in it. Only the names were swapped; every
quadrant, mode and hours value is exactly as hand-built, because the numbers
are what reproduce the week and the names are not.
"""
import pytest
from companion.portfolio import (
    ProjectWeek, MeetingRow, Resolution, aggregate, evaluate_flags,
)

# Hours from the hand-built W35 close. Quadrants per project frontmatter;
# mode per the Work Log bullets recorded in each daily note.
W35_PROJECTS = [
    ProjectWeek("project-a", "operating-efficiency", 100, 4.0),  # parked build lane
    ProjectWeek("project-b", "operating-efficiency", 100, 5.5),
    ProjectWeek("project-c", "cross-cutting",        100, 6.5),
    ProjectWeek("project-d", "operating-efficiency",  50, 2.0),
    ProjectWeek("project-e", "operating-efficiency", 100, 1.5),
    ProjectWeek("project-f", "operating-efficiency",   0, 1.0),  # silent outage fix
    ProjectWeek("project-g", "operating-efficiency", 100, 1.5),
]


def test_w35_total_project_hours_match_the_hand_built_close():
    totals = aggregate(W35_PROJECTS, [])
    assert totals.total_hours == pytest.approx(22.0)


def test_w35_parked_build_lane_lands_in_operating_efficiency():
    totals = aggregate(W35_PROJECTS, [])
    assert totals.by_quadrant["operating-efficiency"] >= 4.0


def test_w35_silent_outage_fix_is_pure_defense():
    outage = [p for p in W35_PROJECTS if p.project == "project-f"][0]
    assert outage.offense_pct == 0


def test_w35_reliability_reads_zero_and_the_flag_fires():
    totals = aggregate(W35_PROJECTS, [])
    assert totals.by_quadrant["reliability"] == 0.0
    prior = aggregate(W35_PROJECTS, [])   # W34 also had no reliability project
    flags = evaluate_flags(totals, [prior], driver_hours=11.0, held_hours=11.0)
    assert any("reliability" in f.lower() for f in flags)


def test_w35_unresolved_meeting_is_reported_not_absorbed():
    rows = [MeetingRow("Impromptu Zoom", Resolution(None, "unresolved"), 1.0)]
    totals = aggregate([], rows)
    assert totals.unresolved_hours == 1.0
    assert totals.total_hours == 1.0
```

- [ ] **Step 2: Run it and reconcile every failure against the hand-built close**

Run: `cd companion && pytest tests/test_portfolio_w35.py -v`
Expected: PASS. **Any mismatch is a real finding** — either the hand-built number was wrong or the pipeline is. Reconcile against `02-weekly/2026-W35.md` before adjusting either side. Do not edit the fixture to make a test green.

- [ ] **Step 3: Run one real close-week dry pass over W35**

Run `/close-week 2026-08-22` and stop at Step 2a's confirm gate without confirming. Compare the proposed table against `02-weekly/2026-W35.md`'s Stack Rank vs Reality.
Expected: total within ~1h of 52.6h; meetings ≈23.75h across ≈26. Note the ④-starvation flag fires on the PROJECT rows only — once the week's meetings are included, reliability carries meeting hours and the flag correctly does not fire; assert what is true of the full week rather than reshaping the fixture.

- [ ] **Step 4: Commit**

```bash
git add companion/tests/test_portfolio_w35.py
git commit -m "test(portfolio): W35 acceptance test — reproduce a known week"
```

---

## Self-Review

**Spec coverage.** §3.1 data model → Tasks 1, 2, 4. §3.2 role map → Task 1 + P3. §3.3 cascade → Task 3. §3.4 mode → Tasks 4, 6. §3.5 confirm gate → Tasks 6, 8. §3.6 flags → Task 5. §5 layout → Tasks 6, 7, 8. §6 migration → Prerequisites + task order. §7 acceptance → Task 9. **Gap found and closed:** the meeting cache from §3.5 had no task; it is now written into Task 8 Step 1 rather than given its own task, since it is a read/write inside the gate rather than an independently reviewable deliverable.

**Placeholder scan.** No TBDs. Every code step carries real code. Task 6 is prose, so it specifies seven required contents rather than a code block, and Step 2 gives a mechanical check that the vocabularies match.

**Type consistency.** `Resolution` is constructed identically in Tasks 3, 4, and 9. `ProjectWeek(project, quadrant, offense_pct, hours)` is positional and consistent across Tasks 4 and 9. `evaluate_flags(current, history, driver_hours, held_hours)` matches between Tasks 5 and 9. `_VALID` is defined in Task 1 and used in Tasks 2 and 3.

**One deviation from the spec, deliberate.** Spec §5 listed reference files only. This plan adds `companion/portfolio.py`, because the deterministic half is arithmetic that should not be re-derived by an LLM each Friday, and the repo has a 26-file pytest suite plus the `streak.py` precedent for exactly this split.
