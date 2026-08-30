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

The topic sections and their timestamps do **not** come from the daily note — its
`## Meetings` section preserves only time, title, attendees and 1-2 takeaways.
close-week Step 1a fetches them from Fathom for the whole week and carries them as
`meeting_topics`; without that fetch this rung can never fire and every meeting falls
through to project or unresolved. That matters most where the role rung is too broad
to be decisive (a leadership standing meeting) and the topic is the whole signal.

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

**Collapse on `(name, quadrant)`, never on name alone** — project rows on
`(project, quadrant)`, meeting rows on `(meeting name, quadrant)`. Quadrant is a
property of the activity, not of the project or the calendar invite: a project whose
week spanned two quadrants is two rows, and two occurrences of one standing meeting
that resolved differently stay two rows. Collapsing by name alone merges hours
confirmed in different quadrants into a single average and destroys the one dimension
this whole table exists to record.

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

**Run it with the companion's own interpreter, never a bare `python3`.** The module
needs Python ≥3.10. A stock Mac's `/usr/bin/python3` is 3.9, and a supported Windows
install has no `python3` on PATH at all — the launcher is `py`, and the toolkit may be
running from the private runtime `ensure-companion.sh` provisioned into
`companion/.python-runtime/`. Documenting `python3` meant Step 2a #1 could never parse
a project row on Windows. Resolve the interpreter the way every other skill resolves
the companion, then reuse `$PY` for both modes:

```bash
# Resolve once, at the top of Step 2a. ensure-companion.sh prints the BINARY path
# (see close-week Step 0.5 and open-day Step 8) — and that is all it promises.
TC="$(bash "$HOME/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh")"
# Ask the binary for its own interpreter. Never derive it from `dirname "$TC"`.
PY="$("$TC" python-path 2>/dev/null)"
[ -n "$PY" ] && [ -x "$PY" ] || PY=""    # no interpreter → skip Step 2a (see below)
```

**Why `$TC python-path` and not `$(dirname "$TC")/python`.** `ensure-companion.sh`
resolves the binary from three places, and only two of them are a venv: `<venv>/bin/`,
`<venv>/Scripts/`, and — unless `NSLS_COMPANION_LOCAL_ONLY` is set — whatever
`command -v toolkit-companion` finds on `PATH`. That third case is a supported
fallback, and the directory it returns can be a pipx bin dir, a `~/.local/bin`, or a
symlink farm with no interpreter in it at all; the sibling guess then produced a `$PY`
that does not exist and **both** module runs below failed on exactly the path the
guess was written to support. The binary is the only thing that knows its own
interpreter, because it *is* that interpreter — `python-path` prints `sys.executable`,
which by construction can import `companion`.

If `$TC` comes back empty the companion cannot be provisioned here. If `$PY` comes back
empty the binary resolved but would not name an interpreter (an older companion
predating `python-path`, or a broken install). Either way: say which, and skip Step 2a
rather than falling back to a bare `python3`, which on the machines that need this most
is either 3.9 or absent.

```bash
# 1. Parse ONE daily note's '## Projects Touched' section (Step 2a #1).
"$PY" -m companion.portfolio --parse-daily < daily-note.md

# 2. Aggregate the confirmed week (Step 2a #4).
"$PY" -m companion.portfolio < payload.json
```

Run mode 1 once per daily note. Never hand-roll a regex for the close-day line
format — verifying that format contract in one place is why the parser exists.

**`--parse-daily` result shape:**

| Key | Shape |
|---|---|
| `project_weeks` | list of `{project, quadrant, offense_pct, hours}` — feeds straight into mode 2's payload, after collapsing days per Step 2a #1. `quadrant` is `null` for a row rendered `· uncategorized ·` |
| `skipped_lines` | the raw text of every bullet under the heading the parser would not turn into a row — it did not match the format, **or** its quadrant slot held a word that is neither one of the five nor the literal `uncategorized` (e.g. the legacy `founder-transition`), **or** its `offense_pct` was outside 0-100, **or** its hours field was too large to be a finite number |
| `skipped_count` | how many. **Report this at the confirm gate, per day, even when it is 0.** A skipped line is a project's hours vanishing from the week with no other signal — the exact silent failure this feature exists to surface. Explanatory prose under the heading is not counted; only lines that were trying to be project rows |

**Payload shape** for mode 2 (top-level keys `summarize()` reads):

| Key | Shape | Notes |
|---|---|---|
| `project_weeks` | list of `{project, quadrant, offense_pct, hours}` | one row per project this week |
| `meeting_rows` | list of `{label, quadrant, resolved_by, hours, splits?}` | `splits`, when present, is a list of `[quadrant, share]` pairs; `quadrant` is `null` when `resolved_by` is `"topic"` (split) or `"unresolved"`. **Shares should sum to 1.0.** Over 1.0 they are normalised (the same rule `resolve_meeting()` applies), so `unresolved_hours` can never go negative and the table can never sum past 100% — and that normalisation runs over **all** the shares, out-of-vocabulary ones included, before any are dropped, so a bad quadrant's share really does reach `unresolved_hours` instead of being absorbed by its neighbours. Under 1.0 the missing share becomes unresolved hours — deliberately, because a share that went missing is time nobody attributed, not time to be absorbed into the quadrants that survived. A **negative** share is not normalised: the whole row goes to unresolved and lands in `rejected` |
| `history` | list of `{by_quadrant, by_mode, by_quadrant_mode?}` | most recent week first. **`by_quadrant` and `by_mode` are REQUIRED, and both must be complete**: `by_quadrant` names all five quadrants, `by_mode` names both modes, every value a non-negative finite number. A prior week that is absent, not an object, missing a quadrant, or only partly readable (`{"offense": 10, "defense": null}`) is **not** history — the module suppresses the ENTIRE list, reads it as `[]`, and reports the reason as a `payload` entry in `rejected`. **`by_quadrant_mode` is optional** (a note written before it was persisted has none) and costs only the assets-decaying flag when absent — that flag is scoped to ① and needs ①'s own mode split; present, it must be well formed or the entry fails like any other. An absent or empty `history` is ALSO reported, for the same reason a malformed one is. See "Absent history is never a zero" below |
| `driver_hours` | number | optional — but **omitting it does not mean `0.0`**, it means absent, and the held-vs-driver flag is then suppressed and the suppression reported. A value that is not a finite number reads as absent too, and is reported twice: once as an unreadable value, once as the flag it suppressed. Send `0.0` only when you counted and the answer was zero |
| `held_hours` | number | optional. Same rule |

**Result shape** (what the module prints):

| Key | Shape |
|---|---|
| `by_quadrant` | `{growth-driver, operating-efficiency, hygiene, reliability, cross-cutting}` → hours |
| `by_mode` | `{offense, defense}` → hours, week-wide, **project rows only** |
| `by_quadrant_mode` | same five quadrant keys → `{offense, defense}` hours, **project rows only**. This is what the per-quadrant Offense / Defense column renders from |
| `unresolved_hours` | number, never negative |
| `total_hours` | number |
| `project_hours` | number — the hours from **project rows only**, every one whose hours were usable, including a row whose `offense_pct` was rejected and therefore recorded no mode. This is `mode_percentages`' denominator, returned so the renderer can say what those shares are a share *of* |
| `percentages` | same five quadrant keys → share of `total_hours` |
| `mode_percentages` | `{offense, defense}` → share of the week's *project* hours, i.e. divided by `project_hours`. **These two need not sum to 100%**, and the gap is meaningful: it is project time whose mode nobody could read (an `offense_pct` the module rejected). Dividing instead by `offense + defense` forced them to 100% of a base that had quietly shrunk, hiding exactly that gap |
| `quadrant_mode_percentages` | same five quadrant keys → `{offense, defense}` shares **within that quadrant's project hours** |
| `unmoded_hours` | project hours that recorded no mode at all — `project_hours` minus (`by_mode.offense` + `by_mode.defense`). Exactly the slice `mode_percentages`' two shares are missing when they do not reach 100% |
| `unmoded_pct` | `unmoded_hours` as a share of `project_hours`. Returned so the renderer never has to subtract two percentages by hand to explain the gap |
| `unresolved_pct` | `unresolved_hours` as a share of `total_hours` |
| `rejected` | list of `{kind, row, reason}` — everything the module refused to trust, **plus every flag it could not evaluate**. `kind` is `"project"`, `"meeting"`, or `"payload"` (a week-level failure: a rows container that isn't a list, an unreadable `driver_hours` / `held_hours`, a payload that isn't an object) — and a `payload` entry whose reason ends `did not run this week` is a **flag suppression**, not a malformed row: an absent or empty `history`, a prior week with no growth-driver mode hours, an absent `driver_hours` / `held_hours`, or a payload carrying neither row container at all (an unmeasured week, which is not a week that measured 0h). Those fire on ordinary weeks, not just broken ones, and they are what stops an empty Flags block from reading as "nothing fired". `row` is the raw input row verbatim; `reason` names the field and value that failed. **Empty only when every row was trusted AND every flag could run; when it is not empty the caller must render every entry** — see the validation contract below |
| `flags` | list of strings, one per fired flag (reliability starvation, operating-efficiency ceiling, assets decaying on ①, held-out-earning-driver) |

### The validation contract

**Two boundaries, one `rejected` list, and they check different things.**
`aggregate()` owns every rule about a **value**. `summarize()` owns the one rule
`aggregate()` structurally cannot see — the JSON payload's **shape**, because
`aggregate()` takes dataclasses and never meets the payload's dicts. What
`summarize()` catches, each as a `rejected` entry rather than an exception:

- **a row missing a required key.** Project rows need `project`, `quadrant`,
  `offense_pct`, `hours`; meeting rows need `label`, `resolved_by`, `hours`
  (`quadrant` and `splits` stay optional — a split or unresolved meeting
  legitimately carries no quadrant). `null` is a legal *value* for `quadrant`;
  an absent *key* means nobody said. The reason names the missing key
- **a malformed `splits`** — not a list, or an entry that isn't a
  `[quadrant, share]` pair. `for q, s in splits` raises on both
- **a rows container that isn't a list**, and a payload that isn't an object.
  Reading either as empty would lose a whole week of work with no signal
- **a `driver_hours` / `held_hours` that is absent, or not a finite number.**
  These two feed *only* the held-vs-driver flag, so a bad one must not kill the
  week summary — that would be disproportionate to what they do. But neither
  case reads as `0.0`: `0.0` is a number that can *fire* that flag (`held >
  driver` is the firing condition), so an absent `driver_hours` beside a real
  `held_hours` manufactured `held projects out-earned drivers (5.0h vs 0.0h)`
  out of a field nobody supplied. Both cases read as **absent**, the flag is
  suppressed, and the suppression is reported beside it. A value that was
  present but unreadable is reported a second time as itself

No value check may be written in `summarize()`. A second copy of the value rules
there is exactly how these two halves came apart once already.

`aggregate()` is the single **value** boundary. Every caller funnels through
it — direct callers, `summarize()`'s JSON payload, and the CLI — so the checks
live there and nowhere else. Validating per entry point is what failed here
once: an out-of-vocabulary split quadrant was guarded in `summarize()` only and
stayed live in `aggregate()`, where it raised `KeyError` for anyone calling
directly. What is checked:

- **every numeric field is a real, finite number — checked *before* any
  comparison or arithmetic touches it.** `hours` and `offense_pct` on project
  rows, `hours` on meeting rows, and every split share. This is a type check, not
  a range check, and it comes first: a JSON payload can carry `"2"`, `null`, or a
  list where a number belongs, and `hours < 0` on any of those raises
  `TypeError` — one malformed row used to abort the **whole week summary**, so
  the CLI printed nothing and the confirm gate never saw the row that caused it.
  `NaN` and `Infinity` are the mirror image: they pass `hours < 0` cleanly and
  make `total_hours`, the quadrant totals and every percentage non-finite. A
  Python `bool` is an `int`, so `True` is rejected too rather than counted as one
  hour of work
- the quadrant, and every split quadrant, is in the five-value vocabulary
- `0 <= offense_pct <= 100`
- `hours >= 0`, on project rows and meeting rows alike
- every split share `>= 0`
- **the RESULT of the arithmetic is finite too, not just the inputs.** Finite
  numbers multiply and add their way out of the finite range: `1e308` hours at
  `50` offense overflowed a plain `hours * offense_pct` to `Infinity`, two
  `1e308`-hour rows overflow the running total, and two `1e308` split shares
  overflow their sum (where `1.0/inf` is `0.0`, which would silently scale every
  share to nothing and call it "normalised"). So the products are ordered to make
  overflow impossible — `hours * (pct / 100)`, a factor in `[0, 1]` — and the
  running total is checked *before* a row is added to it. A row that would push
  the week's total out of the finite range is **left out of the week entirely and
  reported**, exactly like unusable hours. Every other accumulator is bounded by
  that total (`sum(by_quadrant) + unresolved == total`, and the mode hours sum to
  the project hours inside it), so guarding the total guards all of them

**A failing row is reported, never silently corrected.** Its hours go to
`unresolved_hours` *and* the raw row comes back in `rejected` with the reason.
Nothing here raises: one malformed row costs its own row, never the week. The
one exception is unusable `hours` — negative, or not a finite number — which
cannot be routed anywhere without pushing `unresolved_hours` below zero or making
the week's total meaningless: such a row is left out of `total_hours`
entirely and reported. A non-finite or non-numeric split share is treated exactly
like a negative one: the *whole* row goes to unresolved, because a share nobody
can read cannot be apportioned in part. A negative split share sends the *whole* row to
unresolved rather than part of it — a negative share keeps the reconciliation
invariant true arithmetically while every rendered number is nonsense, which is
worse than an honest unresolved bucket. Either way
`sum(by_quadrant) + unresolved_hours == total_hours` still holds for any input,
and `unresolved_hours` is never negative.

**Shares are normalised *before* invalid quadrants are dropped, not after.** An
over-1.0 split is scaled by the sum of **all** its shares, including the ones
whose quadrant is about to be rejected; only then are those dropped, and only
then is the leftover routed to `unresolved_hours`. Dropping first and normalising
the survivors scales them *up* to fill the invalid share's place: on a 2h meeting
split `[["growth-driver", 0.7], ["hygiene", 0.6], ["typo", 0.1]]`, all 2h landed
in valid quadrants with `unresolved_hours` at `0.0` while the emitted `rejected`
entry said that share had been "routed to unresolved". The order is what makes
the reason string true.

A `quadrant` of `null` is **not** a rejection: it is the documented
`uncategorized` project row and the documented unresolved meeting, both of which
route to unresolved by design. Reporting those would cry wolf until nobody reads
the list.

The parser enforces the same `offense_pct` range one step earlier. Its regex
accepts `\d{1,3}`, so a line reading `· 150% offense` has the *shape* of a row;
`parse_daily_note()` returns it as a **skipped line** rather than a parsed one,
so it surfaces at the confirm gate instead of reaching `aggregate()` and
computing negative defense hours out of a number nobody ever read. It applies the
finiteness rule to the value it produces, too: the regex accepts unbounded
digits, so a 400-digit hours field `float()`s to `inf` — that line is skipped, not
parsed.

**In the parser, `uncategorized` is the only out-of-vocabulary quadrant token
that means `null`.** Any *other* word in that slot is drift and comes back as a
**skipped line**. Mapping every unrecognised token to `null` left `skipped_count`
at 0 while the hours routed to unresolved with no signal at all — and
`founder-transition`, a real legacy value still sitting in the vault, would have
vanished exactly that way.

**Absent history is never a zero — and the guard for that lives in the module,
not here.** "Unknown treated as zero" has been the bug three times in this one
feature: in the CLI contract, in `_totals_from_history_entry()`, and in the
rekeying close-week does before the payload is built. A rule written only in
prose is a rule the fourth caller does not have, so `summarize()` now validates
every `history` entry itself. It keeps coming back because **zero is not a
neutral value for either trend flag**:

- a prior week read as all-zero hours has `0h` of reliability, which *is* the
  reliability-starvation flag's firing condition — an unmeasured week thereby
  manufactures "0h for 2 consecutive weeks";
- a prior week of `{"offense": 10, "defense": null}` has a non-zero mode total
  and a 0% defense share, which *is* the assets-decaying flag's firing
  condition against any current week with defense in it.

So a prior week is either complete and finite — both keys present, all five
quadrants named, both modes named, every value a non-negative finite number — or
it is not history at all. **One bad entry suppresses the whole list**, not just
itself: `evaluate_flags` reads it positionally (`history[0]` *is* last week), so
dropping entry 0 and keeping entry 1 would promote a two-weeks-ago week into last
week's slot and compare against the wrong week — inventing a trend rather than
reading one. The suppression comes back as a `payload` entry in `rejected`,
because "no flags fired" and "the trend flags could not run" print identically
otherwise, and those two mean opposite things.

**And an ABSENT history is reported the same way a malformed one is.** That is
the common case, not the edge one — the first week on the pipeline, a gap week
(which Step 2a #5 signals by passing `[]`), an extended close, a prior week
whose Step 2a was rejected, any note predating this pipeline. Reporting only
the malformed case left the *artifact* — the weekly note, which is what anyone
reads a month later — identical in both cases, which is the exact failure the
malformed-case report was written to end. The same rule covers the two flag
inputs: an absent `driver_hours` / `held_hours` suppresses the held-vs-driver
flag and says so, and a prior week with no `by_quadrant_mode` suppresses the
assets-decaying flag and says so.

This is the module-side floor. close-week Step 2a #5's own `history: []` rules —
for skipped weeks and for an extended close — still apply on top of it: the module
can tell that an entry is unreadable, but it cannot tell that two readable entries
are not consecutive weeks.

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
   offense is exactly the silent-empty this feature exists to prevent. This
   hours test is the **only** reason a row prints `—`. `cross-cutting` is a
   quadrant like any other and carries project rows with real offense/defense
   splits; forcing its mode to `—` renders a 100%-defense cross-cutting week as
   no data at all. Only `Unresolved` has no mode by construction — it is not a
   quadrant and no mode hours are recorded against it.

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
     "by_mode": {"offense": 12.0, "defense": 8.5},
     "by_quadrant_mode": {"growth-driver": {"offense": 8.0, "defense": 6.0},
                          "operating-efficiency": {"offense": 4.0, "defense": 0.0},
                          "hygiene": {"offense": 0.0, "defense": 1.5},
                          "reliability": {"offense": 0.0, "defense": 0.0},
                          "cross-cutting": {"offense": 0.0, "defense": 0.0}}}
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
  "project_hours": 21.0,
  "percentages": {
    "growth-driver": 0.556,
    "operating-efficiency": 0.184,
    "hygiene": 0.12,
    "reliability": 0.12,
    "cross-cutting": 0.0
  },
  "mode_percentages": {"offense": 0.638, "defense": 0.362},
  "unmoded_hours": 0.0,
  "unmoded_pct": 0.0,
  "quadrant_mode_percentages": {
    "growth-driver": {"offense": 0.7, "defense": 0.3},
    "operating-efficiency": {"offense": 1.0, "defense": 0.0},
    "hygiene": {"offense": 0.5, "defense": 0.5},
    "reliability": {"offense": 0.0, "defense": 1.0},
    "cross-cutting": {"offense": 0.0, "defense": 0.0}
  },
  "unresolved_pct": 0.02,
  "rejected": [],
  "flags": []
}
```

(Floats are shown rounded here; the module prints full precision.)

No flags fire here, and nothing is suppressed either: reliability has hours this week
(only the history entry was at zero, and the flag needs two consecutive zero weeks);
operating-efficiency sits at 18.4%, under the 40% ceiling; growth-driver's own defense
share — 3.6h of 12.0h recorded mode hours, 30%, the same number the ① row's
Offense / Defense column prints — is lower than last week's 6.0h of 14.0h (43%), so
nothing is "decaying"; and held hours (4.0) don't out-earn driver hours (12.0).

**The flag reads ①, not the week.** Spec §3.6 scopes it to quadrant ① — "defense share
on ① rising week over week" — and its message names growth drivers by name, so
comparing the *week-wide* share fired it on a week where ① defense fell and hygiene's
rose, naming the wrong assets. It is also why the flag and the table can no longer
print two different numbers both called "the defense share": the flag quotes ①'s own
share (the ① row's column), while **Week Offense / Defense** divides by `project_hours`
and says so.

`unmoded_hours` is `0.0` here because every project row had a readable `offense_pct`.
Reject one — a `150` in that field — and `project_hours` still counts its hours while
`by_mode` does not, so the two mode shares stop reaching 100% and `unmoded_pct` is the
number that explains the gap. Note that `atlas` still carries 13.9h in `growth-driver` even though its
project-week row alone was 12.0h — the project-fallback meeting row (1.0h) and the
`growth-driver` share of the topic split (0.9h) both land in the same bucket, which is
exactly the point of running meetings through the same cascade as project time.

That same example shows why rule 2 above exists. `growth-driver` holds 13.9h but only
12.0h of it is project time, so its 70 / 30 split covers 12.0h, not 13.9h.
`cross-cutting` has no hours at all and reads `—`. Had a quadrant held *only* meeting
hours, it too would read `—`: unknown mode, not zero offense.

**A third case to expect: the week-level mode can describe hours that appear in no
quadrant row.** An `uncategorized` project row (`quadrant: null`) routes its hours to
**unresolved** but still contributes its offense/defense to `by_mode`, because the mode
was read even though the bucket was not. So 4h at 100% offense uncategorized plus 6h at
100% defense growth-driver renders **Week Offense / Defense: 40% / 60%** while no
quadrant row shows any offense at all — those offense hours are sitting in the
Unresolved row, which prints `—` by construction. That is arithmetically honest and
`uncategorized` is a routine close-day output, so it is documented rather than
"fixed" — but say it in the same line as the Hours-vs-mode note above, because nothing
else on the page prepares a reader for it.

Close-week is responsible for everything upstream of this call — attributing each
meeting to a rule, reading `portfolio-category` frontmatter, classifying Work Log
verbs into `offense_pct`. `summarize()` only aggregates and flags what it's handed.
