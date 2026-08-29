# Portfolio Quadrant Allocation + Org Alignment Capture — Design

**Date:** 2026-08-29
**Status:** approved in brainstorming, not yet implemented
**Skills touched:** `close-week` (primary), `close-day`, `open-week`

> **Scope.** Part A (quadrant allocation) and Part B (alignment capture) are two
> sub-projects. They share one design doc because they share an output surface and an
> identical confirm-gate pattern, but they get **separate implementation plans**, and
> the §7 acceptance test is a hard gate between them. Part B does not start until Part A
> reproduces a week whose answer is already known.

> **Naming note.** This repo is public. This spec describes procedure only. Every
> person→quadrant mapping, every named relationship, and every alignment score lives
> outside the repo (`~/.claude/` and the private Obsidian vault). Where an example needs
> a person, it names a *role* ("a security-governance role"), never an individual.

---

## 1. Problem

Two gaps, one shared output.

**Gap A — the portfolio frame is declared but never measured.** Projects have carried
`portfolio-category` frontmatter since 2026-07-11, and the frame note at
`10-strategy/portfolio/2x2-portfolio.md` is the shared language with the founder's
dashboard. But no weekly output reports *time* against those four quadrants, so the
frame's central claim — that reliability silently loses to growth until something
breaks — is unfalsifiable in practice. The 2026-07-11 memory already asked close-week
and close-day to group Project Progress by quadrant; they do not.

**Gap B — weekly reporting is factual only.** Quick Notes captures what moved. It does
not capture whether the builder and the org are pointing the same way, which is the
signal that predicts whether next week's work will land at all.

**A modelling error sits underneath Gap A.** Active-project category distribution is
~49 operating-efficiency / 13 growth-driver / 4 hygiene / 1 reliability. Quadrant ④
reads near zero not because reliability work is absent but because **reliability is a
mode of work, not a type of project** — keeping a growth asset from decaying is ④ work
on a ① project. An open Asana task proposes creating reliability *projects* to fix the
zero; under this design that would model the wrong thing and should be re-scoped.

---

## 2. Goals / Non-goals

**Goals**
- Report weekly time by portfolio quadrant **and** by offense/defense mode.
- Attribute meeting time (≈45% of a recent week) rather than excluding it.
- Produce a per-relationship org-alignment read from meeting transcripts, with a score,
  a direction, and named out-of-alignment subjects.
- Cross-reference the builder's own sentiment against org-wide friction signals.
- Land both in the weekly note and, appropriately reshaped, in Quick Notes.
- Gate every write behind line-level human confirmation.

**Non-goals**
- No new Airtable fields; no writes to Signal.
- No automated quadrant tagging of Google Calendar events.
- No historical backfill beyond one acceptance-test week.
- No composite alignment score. Org alignment only — personal conviction and
  energy/drain were considered and deliberately excluded.
- No second denylist: meeting exclusions reuse the existing `harvest-exclude.txt`.

---

## 3. Part A — quadrant × mode allocation

### 3.1 Data model

Quadrant is a property of the **activity**, not of the project. The project's
`portfolio-category` is the *default*; the week's actual work may override it. Mode
(offense/defense) is always derived from the activity and never stored on the project.

| Input | Source | Exists today |
|---|---|---|
| Project hours per week | Familiar window titles → project | yes (close-day) |
| Project default quadrant | `portfolio-category` frontmatter | yes, 68/84 projects |
| Driver vs. held | `portfolio-role` frontmatter | yes |
| Mode (offense/defense) | inferred per project-week from Work Log bullets | **new** |
| Meeting → quadrant | role → topic → project cascade | **new** |
| Role map | `~/.claude/portfolio-role-map.txt` | **new** |

Quadrant values are exactly the four from the frame note, plus one passthrough:
`growth-driver` (①), `operating-efficiency` (②), `hygiene` (③), `reliability` (④),
and `cross-cutting` (founder/seat work, outside the org portfolio).

### 3.2 The role map

Lives at `~/.claude/portfolio-role-map.txt`, **outside both toolkit repos**, for the
same reason and by the same precedent as `~/.claude/close-day-title-overrides.txt`: it
names people and their functions, and both toolkits are public. Absent file means the
cascade skips rule 1 and starts at topic. Format:

```
# person → quadrant. One per line. '#' comments. Case-insensitive substring match
# on attendee name or email local-part.
#
# ONLY list roles narrow enough to be decisive on their own. A broad role belongs
# here NOT AT ALL — leaving it out is what makes the topic rule fire.
<name>  → hygiene         # security / governance
<name>  → hygiene         # security-first engineering
#
# Deliberately absent (role too broad — topic decides):
#   the founder/CEO, the board chair, the SLT as a body, finance, product, ops
```

### 3.3 The cascade

For each meeting, the **first rule that resolves wins**. Every result records
`resolved_by`, so any number traces back to the rule that produced it.

1. **Role** — an attendee appears in the role map → that quadrant.
2. **Topic** — the Fathom summary's topic sections map to quadrants. A meeting that
   genuinely spans two quadrants **splits**. Hours are apportioned by the elapsed span
   between consecutive topic timestamps in the summary (Fathom stamps each section), with
   the final section running to the recording end. When timestamps are missing, split
   evenly across the resolved quadrants and mark the row `even-split (no timestamps)` so
   the estimate is visible as an estimate.
3. **Project** — the meeting maps to a project → inherit its `portfolio-category`,
   unless the activity says otherwise (§3.4).
4. **Unresolved** — reported as its own line with hours. Never silently absorbed into a
   quadrant, and never dropped from the total.

Rule 2 may use summaries, because topic identification is triage, not a factual claim
about what was agreed. Contrast §4.2, where summaries are forbidden.

### 3.4 Mode inference

Per project-week, from Work Log bullets:

| Mode | Vocabulary |
|---|---|
| **Offense** | built, shipped, launched, scoped, designed, decided, drafted, prototyped, negotiated |
| **Defense** | fixed, migrated, rotated, restored, unblocked, renewed, patched, reconciled, recovered, verified |

Ambiguous bullets default to offense and are surfaced in the confirm gate, so the bias
is visible rather than silent. Mode is expressed as a percentage split of the project's
hours, not a binary.

### 3.5 Confirm gate

One table per close. Roughly ten project rows, plus meetings collapsed into recurring
buckets. **Recurring answers cache** to `~/.claude/portfolio-meeting-cache.json`, so
after the first week most meeting rows arrive pre-filled and only new or changed
meetings need attention.

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

### 3.6 Flags

Each is tied to a decision. A flag with no decision attached does not ship.

| Flag | Condition | Decision it forces |
|---|---|---|
| Reliability starving | ④ at 0h for **2** consecutive weeks | Fund it, or say out loud you are not |
| Assets decaying | defense share on ① rising week over week | Your best assets are rotting under you |
| Machine eating output | ② above ~40% of the week | The system is consuming the value it exists to produce |
| Vital few unprotected | `portfolio-role: held` out-earns `driver` | The ranking is not what you are actually doing |

Thresholds are starting values, tuned after the acceptance test and the first live weeks.

---

## 4. Part B — org alignment capture

### 4.1 Scope

**Alignment is measured against the org**, per relationship and per topic: where the
builder and a counterpart actually diverge, and whether that gap is widening or closing.
Alignment against the stack rank and against the operating memo are already computed
weekly and are out of scope here.

### 4.2 The evidence rule

> **Summaries triage. Transcripts evidence.**

Summaries are used only to shortlist which of a week's recordings plausibly carry
alignment signal — typically the 4–6 that are 1:1s or strategy conversations out of
~17 recordings. **Every score and every quote comes from the transcript, first-hand.**

Two prior findings force this and must not be re-litigated in implementation:

- A summary bullet phrased as a conclusion is not evidence that anyone agreed to it.
- A quote relayed by a third party is not evidence of what the original speaker said.

A claim that cannot cite a transcript timestamp is dropped, not softened.

### 4.3 Exclusions

Reuse `harvest-exclude.txt` — one denylist for meeting content across this toolkit, not
two. Absent or empty means everything is read, which is the current default, and the
confirm gate is what protects the write.

### 4.4 Alignment scoring

| Score | Anchor |
|---|---|
| 5 | Explicit agreement on both the decision and the reasoning |
| 4 | Agreement on the decision, divergence on why |
| 3 | No disagreement surfaced — **absence of evidence, flagged as such** |
| 2 | Open disagreement, named by at least one party |
| 1 | Disagreement plus an unresolved decision that is blocking work |

Direction (widening / stable / improving) is computed against the prior week's stored
score. **Week one produces no direction** and says so, rather than inventing one. Every
score carries the transcript timestamp that produced it.

### 4.5 Sentiment

Mapped onto the existing Signal Work-Journal enum so the builder is readable in the same
instrument as staff: `energized`, `pressured_deadline`, `overloaded`,
`frustrated_blocked`, `confused_uncertain`, `neutral`. Primary plus optional secondary,
plus 1–3 verbatim quotes.

**Read from the builder's own lines only**, never the room's. Attributing a sentiment to
someone else from their speech in a meeting is out of scope and would be a different,
more invasive system.

### 4.6 Corroboration against Signal

After sentiment topics are extracted, cross-reference `signal_friction` (executive
scope, org-wide, 4-week window, per-person streak counts). A builder frustration topic
that matches a live team friction topic is marked **corroborated** and promoted.

```
CORROBORATED
  Builder: frustrated_blocked — <topic>
  Team:    N people, friction on <topic>, M-week streak
  → structural, not a mood. Belongs in a decision, not a journal.

UNCORROBORATED
  Builder: overloaded — <meeting>
  Team:    no matching signal
  → the builder's to manage; no org action implied.
```

Corroboration is the strongest output this system produces: two instruments that share
no inputs landing on the same problem.

### 4.7 Destination and the visibility hazard

**Quick Notes is not private.** The Work Journal writer sets visibility to `Shared` as a
hardcoded literal on every write; the journal Doc is shared so the employee *and their
manager* can read it; an HR-viewer list applies on top. For this builder the manager is
the counterpart most likely to appear in an alignment score.

Therefore:

| Output | Destination | Contents |
|---|---|---|
| Named alignment scores + directions + subjects | Obsidian weekly note + alignment ledger (private) | Full, with names and timestamps |
| De-identified structural alignment | Quick Notes (Shared) | Shape without the person |
| Signal-enum sentiment + approved quotes | Quick Notes (Shared) | No names, no scores |

**Accepted risk, decided by the builder 2026-08-29:** a de-identified line such as "one
senior relationship is misaligned on timeline" is not reliably anonymous inside a small
leadership team when the surrounding note supplies context. The mitigation is mechanical,
not advisory — see §4.8. The decision to publish a flagged line remains the builder's.

### 4.8 Confirm gate and re-identification check

Line-level confirm/reject/edit before anything is written anywhere. Every de-identified
Quick Notes line is scored for re-identification risk, and the risk is **shown, not
enforced**:

- **HIGH** — the hiding population is small; or a role is named; or other content in the
  same note narrows the candidate set.
- **LOW** — structural, with no re-identification path.

A HIGH line can still ship. It cannot ship unseen.

### 4.9 Alignment ledger

`10-strategy/alignment/ledger.md` in the vault, mirroring the role-coaching log rather
than scattering named judgments across weekly-note frontmatter. One file to audit, one
file to delete. Stores per-relationship score history, subjects, and timestamps; supplies
the prior-week score that direction is computed from.

### 4.10 Zero case

A week with no recorded qualifying meetings produces "no alignment signal this week."
It never produces a fabricated score, and the zero is reported rather than skipped.

---

## 5. Implementation layout

| File | Purpose | Repo? |
|---|---|---|
| `skills/close-week/references/portfolio-attribution.md` | Cascade, mode vocabulary, flag thresholds, worked examples | yes |
| `skills/close-week/references/alignment-capture.md` | Scoring anchors, evidence rule, corroboration, re-identification check | yes |
| `~/.claude/portfolio-role-map.txt` | person → quadrant | **no** |
| `~/.claude/portfolio-meeting-cache.json` | recurring meeting → quadrant cache | **no** |
| `10-strategy/alignment/ledger.md` | alignment history | vault (private) |

Cross-skill reference is the established pattern in this toolkit (close-day already
treats another skill's file as its source of truth for project mappings), so close-day
and open-week point at the attribution engine rather than duplicating it.

**Skill changes**

- **`close-day`** — emit per-project hours plus a *provisional* quadrant and mode in
  `## Projects Touched`. Without this, close-week re-derives seven days of Familiar
  attribution every Friday; with it, close-week aggregates seven small tables it already
  reads.
- **`close-week`** — Step 1b gains per-project hours; **new Step 2a** (portfolio
  attribution + confirm) runs before Achievements, since the grouping drives them; **new
  Step 2d** (alignment capture + confirm) runs after Step 2c role-coaching so
  corroboration can reuse that evidence sweep; Output A gains `## Portfolio Allocation`
  and `## Alignment`; Output B restructures Project Progress to group by quadrant and
  carries the de-identified alignment plus enum sentiment.
- **`open-week`** — read-only. Last week's quadrant split and any open out-of-alignment
  items enter the stack-rank candidate pool.

---

## 6. Migration order

1. **Categorize the 5 uncategorized active projects.** Proposed by the assistant,
   confirmed by the builder. Blocks everything downstream.
2. **Re-scope the open "promote reliability items to tracked project files" task** — under
   quadrant × mode it models the wrong thing.
3. **Seed the role map.** Drafted from the org chart, corrected by the builder.
   Deliberately short; broad roles stay out.
4. **Part A** — reference file, close-day emit, close-week Step 2a, Output A section.
5. **Acceptance test** (§7) before Part B starts.
6. **Part B** — reference file, close-week Step 2d, ledger, Quick Notes restructure.
7. **open-week** read.

Steps 1–3 are prerequisites, not implementation steps. Step 5 is a gate.

---

## 7. Acceptance test

The week of **2026-08-22 → 2026-08-28** is the test case, because it is already closed by
hand and the answers are known. Running the new pipeline over it must reproduce:

- total active work ≈ 52.6h, within rounding of the hand-built figure;
- a parked build lane appearing in ② at ≈4h;
- a 30-day silent-outage fix classified ④ / defense;
- a growth-driver project showing a mixed offense/defense split rather than 100% offense;
- the ④-starvation flag firing;
- meeting hours ≈23.75h across 26 meetings, with unresolved meetings reported rather
  than absorbed.

Failure to reproduce a week whose answer is known blocks Part B.

For Part B, the same week supplies at least one relationship expected to score low with
a widening direction, and at least one corroborated sentiment/friction pair. Because
these are judgment outputs rather than arithmetic, the bar is *the builder agrees with
the reads at the confirm gate*, not exact reproduction.

---

## 8. Open questions

None blocking. Two to settle during implementation:

- Flag thresholds in §3.6 are starting values and want tuning after the first live weeks.
- Whether coaching sessions belong in `harvest-exclude.txt`. They carry the richest
  alignment signal and the most sensitive content. Default remains "read, gate at the
  write"; the builder may narrow it.
