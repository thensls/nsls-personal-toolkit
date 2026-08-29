# Portfolio attribution — judgment reference

> This rule lives in exactly two places: this file, and `companion/portfolio.py` (for
> the deterministic half). The module owns the cascade mechanics — which rule fires
> first, how splits and unresolved hours are apportioned into the totals — the
> arithmetic, and the flag thresholds. This file owns the two judgment calls a module
> cannot make: inferring offense/defense from Work Log prose, and mapping a meeting's
> topics onto a quadrant. Changing one without the other is the failure this header
> exists to prevent — read `companion/portfolio.py` before editing either.

---

## 1. Quadrant vocabulary

Exactly five values. No synonyms, no substitutes.

- `growth-driver`
- `operating-efficiency`
- `hygiene`
- `reliability`
- `cross-cutting` — the passthrough, for founder/seat work outside the org portfolio

## 2. Mode vocabulary (offense / defense)

Per project-week, read the Work Log bullets for that project and classify by verb.

| Mode | Vocabulary |
|---|---|
| **Offense** | built, shipped, launched, scoped, designed, decided, drafted, prototyped, negotiated |
| **Defense** | fixed, migrated, rotated, restored, unblocked, renewed, patched, reconciled, recovered, verified |

Ambiguous bullets default to **offense** and are surfaced in the confirm gate, so the
bias is visible rather than silent. Mode is expressed as a percentage split of the
project's hours (`offense_pct`, defense is the remainder), never as a binary
either/or call.

## 3. Meeting → quadrant: the cascade and topic mapping

For each meeting, the first rule that resolves wins, and every result records which
rule produced it (`resolved_by`):

1. **Role** — an attendee appears in `~/.claude/portfolio-role-map.txt` → that
   quadrant, no matter what the meeting was about.
2. **Topic** — the Fathom summary's topic sections map to quadrants.
3. **Project** — the meeting maps to a project → inherit that project's
   `portfolio-category`.
4. **Unresolved** — none of the above resolves it (see §5).

Rules 1, 3, and 4's bookkeeping — matching, lookup, apportioning hours into totals —
is mechanical and lives in the module. Rule 2 is the judgment call this file owns:

**Topic mapping.** Read the Fathom summary's topic sections and map each one to a
quadrant using the same five-value vocabulary as everywhere else. A meeting that
genuinely spans two quadrants **splits** rather than forcing a single answer.

**The split rule.** Apportion hours by the elapsed span between consecutive topic
timestamps in the summary (Fathom stamps each section), with the final section
running to the recording end. When timestamps are missing, split evenly across the
resolved quadrants and mark the row `even-split (no timestamps)`, so the estimate is
visible as an estimate rather than passing as a timed measurement.

Topic mapping may use summaries, because identifying a topic is triage, not a factual
claim about what was agreed — contrast the alignment-capture rule (§4.2 of the design
spec), where summaries are forbidden and only transcripts count as evidence.

## 4. Confirm gate

One table per close. Roughly ten project rows, plus meetings collapsed into recurring
buckets. Recurring answers cache to `~/.claude/portfolio-meeting-cache.json`, so after
the first week most meeting rows arrive pre-filled.

```
PROPOSED — adjust any cell, then confirm

PROJECTS              quadrant  mode split     hours  why
<project>             ①         65% O / 35% D   3.3   bug fix = D
<project>             ④         100% D          1.0   silent-outage fix
<project>             ④         —               0.0   ranked, zero hours

MEETINGS              quadrant  resolved_by    hours
<recurring meeting>   ①         project         1.0
<standing meeting>    ①/②       topic (split)   1.5
<1:1>                 x-cut     role            1.0
<ad-hoc>              —         UNRESOLVED      1.0
```

Nothing is written before confirmation. Rejecting the whole table is a valid outcome
and leaves the weekly note without a Portfolio Allocation section rather than with a
guessed one.

## 5. The unresolved rule

A meeting that fails all three rules is **unresolved**. Unresolved is:

- **Reported as its own line**, with hours, in the confirm gate and in the output —
  never merged into any quadrant.
- **Always counted in the week total.** `total_hours` includes unresolved hours;
  `unresolved_hours` is reported alongside `by_quadrant`, not folded into it.
- **Never silently absorbed and never dropped.** A meeting the cascade can't place is
  evidence the role map or the topic read needs work, not a rounding error to smooth
  over.

## 6. Three worked examples

Generic shapes only — no real names, no real meeting titles. Each shows one rule in
the cascade resolving, with its expected `resolved_by`.

**(a) Role resolution.** A meeting is attended by someone whose role-map entry is
narrow enough to be decisive on its own — say, a person listed as
`→ hygiene  # security / governance`. That attendee appearing on the roster resolves
the meeting at Rule 1 regardless of what was discussed.
`resolved_by: role`, quadrant `hygiene`.

**(b) Topic split.** A standing leadership meeting opens with a growth-strategy
discussion and closes with an internal-process retro — two topic sections in one
Fathom summary, neither attendee narrow enough to trigger Rule 1. It resolves at
Rule 2 and splits: if the summary has timestamps, apportion by elapsed span between
them (e.g. 60% `growth-driver`, 40% `operating-efficiency`); if it doesn't, split the
hours evenly and mark the row `even-split (no timestamps)`.
`resolved_by: topic`, quadrant unresolved-to-a-single-value on purpose — the split
itself is the answer.

**(c) Project fallback.** A recurring team meeting has no role-map hit and no topic
section worth splitting on — it's a standing sync for one project. It resolves at
Rule 3 and inherits that project's `portfolio-category` frontmatter.
`resolved_by: project`, quadrant = the project's default quadrant.

An ad-hoc pull-aside that hits none of the three — no role, no clean topic, no
project mapping — falls through to unresolved per §5.
`resolved_by: unresolved`, quadrant `null`.

---

## 7. How close-week invokes this

`companion/portfolio.py` is not a library close-week imports and reads — it is a
program close-week **runs**. It has exactly two modes, both stdin → stdout JSON,
and close-week uses both:

```bash
# 1. Parse ONE daily note's '## Projects Touched' section (Step 2a #1).
python3 -m companion.portfolio --parse-daily < daily-note.md

# 2. Aggregate the confirmed week (Step 2a #4).
python3 -m companion.portfolio < payload.json
```

Run mode 1 once per daily note. Never hand-roll a regex for the close-day line
format — verifying that format contract in one place is why the parser exists.

**`--parse-daily` result shape:**

| Key | Shape |
|---|---|
| `project_weeks` | list of `{project, quadrant, offense_pct, hours}` — feeds straight into mode 2's payload, after collapsing days per Step 2a #1. `quadrant` is `null` for a row rendered `· uncategorized ·` |
| `skipped_lines` | the raw text of every bullet under the heading that did **not** match the format |
| `skipped_count` | how many. **Report this at the confirm gate, per day, even when it is 0.** A skipped line is a project's hours vanishing from the week with no other signal — the exact silent failure this feature exists to surface. Explanatory prose under the heading is not counted; only lines that were trying to be project rows |

**Payload shape** for mode 2 (top-level keys `summarize()` reads):

| Key | Shape | Notes |
|---|---|---|
| `project_weeks` | list of `{project, quadrant, offense_pct, hours}` | one row per project this week |
| `meeting_rows` | list of `{label, quadrant, resolved_by, hours, splits?}` | `splits`, when present, is a list of `[quadrant, share]` pairs; `quadrant` is `null` when `resolved_by` is `"topic"` (split) or `"unresolved"`. **Shares should sum to 1.0.** Over 1.0 they are normalised (the same rule `resolve_meeting()` applies), so `unresolved_hours` can never go negative and the table can never sum past 100%. Under 1.0 the missing share becomes unresolved hours — deliberately, because a share that went missing is time nobody attributed, not time to be absorbed into the quadrants that survived |
| `history` | list of `{by_quadrant, by_mode?}` | most recent week first; **each entry carries both `by_quadrant` and `by_mode`** — `by_mode` is optional and reads as zero offense/zero defense when omitted, which `evaluate_flags` treats as "no data," never as "recorded zero" |
| `driver_hours` | number | optional, defaults to `0.0` |
| `held_hours` | number | optional, defaults to `0.0` |

**Result shape** (what the module prints):

| Key | Shape |
|---|---|
| `by_quadrant` | `{growth-driver, operating-efficiency, hygiene, reliability, cross-cutting}` → hours |
| `by_mode` | `{offense, defense}` → hours, week-wide, **project rows only** |
| `by_quadrant_mode` | same five quadrant keys → `{offense, defense}` hours, **project rows only**. This is what the per-quadrant Offense / Defense column renders from |
| `unresolved_hours` | number, never negative |
| `total_hours` | number |
| `percentages` | same five quadrant keys → share of `total_hours` |
| `mode_percentages` | `{offense, defense}` → share of the week's *project* hours |
| `quadrant_mode_percentages` | same five quadrant keys → `{offense, defense}` shares **within that quadrant's project hours** |
| `unresolved_pct` | `unresolved_hours` as a share of `total_hours` |
| `flags` | list of strings, one per fired flag (reliability starvation, operating-efficiency ceiling, rising defense share, held-out-earning-driver) |

**Two rules for reading the mode keys, and both matter:**

1. **A quadrant's Hours and its Offense / Defense do not describe the same
   hours.** Hours include that quadrant's meeting time; mode covers only its
   project time, because a meeting carries a quadrant and deliberately no mode.
   Say so under the table rather than letting the reader assume the split
   partitions the row.
2. **Read `by_quadrant_mode`'s HOURS, not the percentages, to decide whether a
   quadrant has a mode at all.** When a quadrant's offense and defense hours are
   both `0.0`, no mode was recorded — print `—`, never `0% / 0%`. A quadrant
   whose hours are entirely meeting hours lands here, and rendering it as zero
   offense is exactly the silent-empty this feature exists to prevent.

Every percentage the `## Portfolio Allocation` table needs is in this result.
There is no cell in it that the step divides by hand.

**Worked payload:**

```json
{
  "project_weeks": [
    {"project": "atlas", "quadrant": "growth-driver", "offense_pct": 70, "hours": 12.0},
    {"project": "beacon", "quadrant": "operating-efficiency", "offense_pct": 100, "hours": 4.0},
    {"project": "cinder", "quadrant": "reliability", "offense_pct": 0, "hours": 3.0},
    {"project": "delta", "quadrant": "hygiene", "offense_pct": 50, "hours": 2.0}
  ],
  "meeting_rows": [
    {"label": "security review sync", "quadrant": "hygiene", "resolved_by": "role", "hours": 1.0},
    {"label": "leadership standing meeting", "quadrant": null, "resolved_by": "topic", "hours": 1.5,
     "splits": [["growth-driver", 0.6], ["operating-efficiency", 0.4]]},
    {"label": "atlas team sync", "quadrant": "growth-driver", "resolved_by": "project", "hours": 1.0},
    {"label": "ad-hoc pull-aside", "quadrant": null, "resolved_by": "unresolved", "hours": 0.5}
  ],
  "history": [
    {"by_quadrant": {"growth-driver": 14.0, "operating-efficiency": 5.0, "hygiene": 1.5,
                     "reliability": 0.0, "cross-cutting": 0.0},
     "by_mode": {"offense": 12.0, "defense": 8.5}}
  ],
  "driver_hours": 12.0,
  "held_hours": 4.0
}
```

**Resulting output:**

```json
{
  "by_quadrant": {
    "growth-driver": 13.9,
    "operating-efficiency": 4.6,
    "hygiene": 3.0,
    "reliability": 3.0,
    "cross-cutting": 0.0
  },
  "by_mode": {
    "offense": 13.4,
    "defense": 7.6
  },
  "by_quadrant_mode": {
    "growth-driver": {"offense": 8.4, "defense": 3.6},
    "operating-efficiency": {"offense": 4.0, "defense": 0.0},
    "hygiene": {"offense": 1.0, "defense": 1.0},
    "reliability": {"offense": 0.0, "defense": 3.0},
    "cross-cutting": {"offense": 0.0, "defense": 0.0}
  },
  "unresolved_hours": 0.5,
  "total_hours": 25.0,
  "percentages": {
    "growth-driver": 0.556,
    "operating-efficiency": 0.184,
    "hygiene": 0.12,
    "reliability": 0.12,
    "cross-cutting": 0.0
  },
  "mode_percentages": {"offense": 0.638, "defense": 0.362},
  "quadrant_mode_percentages": {
    "growth-driver": {"offense": 0.7, "defense": 0.3},
    "operating-efficiency": {"offense": 1.0, "defense": 0.0},
    "hygiene": {"offense": 0.5, "defense": 0.5},
    "reliability": {"offense": 0.0, "defense": 1.0},
    "cross-cutting": {"offense": 0.0, "defense": 0.0}
  },
  "unresolved_pct": 0.02,
  "flags": []
}
```

(Floats are shown rounded here; the module prints full precision.)

No flags fire here: reliability has hours this week (only the history entry was at
zero, and the flag needs two consecutive zero weeks); operating-efficiency sits at
18.4%, under the 40% ceiling; this week's defense share (36.2% — defense hours over
*project* hours, which is what the flag compares) is lower than last week's (41.5%),
so nothing is "rising"; and held hours (4.0) don't out-earn driver
hours (12.0). Note that `atlas` still carries 13.9h in `growth-driver` even though its
project-week row alone was 12.0h — the project-fallback meeting row (1.0h) and the
`growth-driver` share of the topic split (0.9h) both land in the same bucket, which is
exactly the point of running meetings through the same cascade as project time.

That same example shows why rule 2 above exists. `growth-driver` holds 13.9h but only
12.0h of it is project time, so its 70 / 30 split covers 12.0h, not 13.9h.
`cross-cutting` has no hours at all and reads `—`. Had a quadrant held *only* meeting
hours, it too would read `—`: unknown mode, not zero offense.

Close-week is responsible for everything upstream of this call — attributing each
meeting to a rule, reading `portfolio-category` frontmatter, classifying Work Log
verbs into `offense_pct`. `summarize()` only aggregates and flags what it's handed.
