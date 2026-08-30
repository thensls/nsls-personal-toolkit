# Design: Signal as a first-class coaching source in Person Intelligence

**Date:** 2026-07-08
**Status:** Approved (design); pending implementation plan
**Author:** Marcus Vance + Claude Code

## Problem

Person Intelligence scores relationships and builds profiles primarily from Fathom
1:1 transcripts. Signal (Quick Notes) — where NSLS staff describe their own job
satisfaction, wins, and friction in their own words — is already ingested, but two
things are missing:

1. That self-reported signal is rendered descriptively (`## Signal Read`) but is
   **not turned into coaching action** — "how do I help this person succeed: remove
   which friction, celebrate which win, back which growth?"
2. Signal is **gated to direct reports only**, so it's absent for peers and other
   tracked relationships who also submit Quick Notes.

The relationship **health score must stay Signal-free** — it is derived only from
meeting evidence. Signal informs coaching and relationship *context*, not the number.

## Current state (verified 2026-07-08)

- `fetch_signal.py` pulls Quick Notes token-direct and normalizes sentiment, wins,
  friction themes, goal health, submission cadence. Raw notes stay cache-only; a
  mechanical filter drops HR/health/comp; the synthesizer applies the KB rubric.
- `synthesize_profile.py` renders a `## Signal Read` section and emits
  `<!-- DIGEST: Signal evidence for [goal] … -->` comments for the biweekly
  coaching-approval flow. It never auto-writes Coaching Goals.
- Signal is excluded from the health score (score = `assess_biweekly_period` /
  the sweep driver scoring Fathom summaries). This is correct and stays.
- Gating: `biweekly_sweep.py` sets `signal_ingest_planned` only when
  `tracking_reason == direct_report`; `fetch_signal.py --list-reports` filters the
  same way.

## Requirements

1. **Coaching action from Signal.** New advisory profile section
   `## How to Support [Name]` with three buckets: Remove Friction / Celebrate Wins /
   Support Growth. Generated from Signal + meeting evidence. Advisory only — never
   auto-writes the user-curated Coaching Goals.
2. **Broaden scope.** Attempt Signal for every tracked person with an NSLS email who
   is not board/external (excludes Dana Ashford, Joe Marsh, and no-email externals).
   No-match degrades to a silent skip (already handled by `fetch_signal.py`).
3. **Weave into relationship context.** Prompt change so job-satisfaction signal
   informs the broader narrative (What Energizes/Concerns Them, relational patterns),
   not only the Signal Read section.
4. **Score stays Signal-free.** Unchanged; add an explicit assertion in docs.
5. **Sensitivity + transparency.** Keep all existing safeguards. Add a provenance
   line to Signal Read noting Signal was included and the person's relation to the
   operating user (because we now read sentiment for people outside the reporting
   line).
6. **Pulse surfacing.** `generate_team_pulse.py` adds a per-person "How to support
   them this cycle" line (top friction to remove / win to celebrate).
7. **Shareable-tier boundary (privacy model).** Person Intelligence consumes ONLY
   the shareable Signal tier — sentiment analytics + the extracted `wins`,
   `challenges` (friction), and `growth` signals. It NEVER reads or caches the raw
   work-journal narrative (`narration_raw`, `entry_text`), which stays between the
   employee and their manager. This is the privacy line that makes the broadened
   scope acceptable: we see the signals that are shareable-by-design, not the
   private journal. Also: **add `growth` to the normalized signal** (currently
   only wins + friction are pulled) so growth can feed the Support-Growth bucket.

## Design

### Scope gating (Requirement 2)
- `list_relationships.py`: add a derived boolean `signal_eligible`, defined by ONE
  rule: `email` is a non-empty `@nsls.org` address AND `tracking_reason !=
  key_relationship_external` AND name not in `SIGNAL_EXCLUDE` (default set = known
  board members, currently `{"Dana Ashford"}`; overridable via env). Board members
  have an nsls.org email but no Quick Notes, so this is a defensive exclude — it
  avoids even attempting a fetch for people who structurally have no Signal data.
- `biweekly_sweep.py`: set `signal_ingest_planned = signal_eligible` (was
  direct-report-only). Populate `signal_slug` for all eligible.
- `fetch_signal.py`: `--list-reports` stays for back-compat; add `--list-signal`
  (or extend) to return all `signal_eligible` slugs for the cron path.
- Degradation: a person with no Quick Notes returns empty normalized signal; the
  synthesizer simply omits Signal Read / How-to-Support-from-Signal for them.

### `## How to Support [Name]` (Requirement 1)
- Emitted by `synthesize_profile.py`, placed immediately after `## Signal Read`
  (or after `## How to Work With` when no Signal Read exists).
- Three labeled buckets, each 1–3 concrete, observable actions the operating user
  can take. Sourced from Signal friction/wins/goals first, meeting evidence second.
- Explicitly advisory. A comment marker (`<!-- advisory: regenerated each sweep -->`)
  distinguishes it from curated content so future syntheses may replace it without
  touching Coaching Goals.
- If neither Signal nor meeting evidence exists, omit the section (no filler).

### Relationship-context weave (Requirement 3)
- Prompt-only change: instruct the synthesizer to let distilled Signal inform
  "What Energizes/Concerns Them" and "Relational Patterns" where it adds signal,
  still honoring the sensitivity rubric (no comp/health/personnel/family content).

### Score protection (Requirement 4)
- Documentation assertion in `SKILL.md` and `references/ingest-scoping.md`:
  "Signal never contributes to `health_score`; scoring reads Fathom-meeting
  evidence only." No code change (already true) — a guard against future drift.

### Sensitivity + provenance (Requirement 5)
- Existing filters unchanged.
- Signal Read gains a first line: `*Signal source: <relation> — Quick Notes through
  <most-recent-week>.*` where `<relation>` is direct report / SLT peer / key
  relationship. Makes ownership of the private words explicit.

### Pulse surfacing (Requirement 6)
- `generate_team_pulse.py`: for each scored person with Signal, add one line under
  their pulse entry: "Support: remove [top friction]; celebrate [top win]."

## Files touched
- `scripts/synthesize_profile.py` — new section, weave, provenance line
- `scripts/biweekly_sweep.py` — scope gating
- `scripts/list_relationships.py` — `signal_eligible` flag
- `scripts/fetch_signal.py` — broaden the eligible-slug listing
- `scripts/generate_team_pulse.py` — per-person support line
- `SKILL.md`, `references/ingest-scoping.md` — docs + score-free assertion

## Non-goals (YAGNI)
- No change to the scoring pipeline.
- No new MCP wiring (Signal is already reachable token-direct).
- No auto-writing of Coaching Goals; the accept/edit/reject flow stays.
- No UI/dashboard work.

## Testing
- `list_relationships.py` unit: eligible set excludes board/externals, includes
  staff peers.
- `fetch_signal.py` no-Quick-Notes person → empty normalized, no crash.
- `synthesize_profile.py` fixture with Signal → `## How to Support` present with 3
  buckets; fixture without Signal → section omitted; Coaching Goals untouched.
- Sensitivity: a Signal item matching the filter never appears in output.
- End-to-end: one direct report + one peer through the driver; confirm score
  unchanged by Signal presence (compare score with/without Signal input).
