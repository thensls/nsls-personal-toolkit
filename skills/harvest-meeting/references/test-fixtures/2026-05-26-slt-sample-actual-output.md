# Task 11 — End-to-End Verification: Actual Output

Run date: 2026-05-30. Driver: Kevin (`kprentiss@nsls.org`). Mode: `--fathom-url` against the
staged synthetic fixture (`2026-05-26-slt-sample.md`). Approval response: `cancel` (no KB write).

## Result vs. expectation

| Step | Expected | Actual | Verdict |
|---|---|---|---|
| 0 SLT gate | confirmed | confirmed (`kprentiss@nsls.org` via `kb-repo` scope) | ✅ (after fix — see Finding 1) |
| 1 context | ~60 topics + rubric | 66 topics, rubric 2878 chars | ✅ |
| 2 load meeting | 1 meeting | 1 (staged fixture) | ✅ |
| 3 extract | 4 candidates | 4 (1 decision, 1 project, 2 state-change) | ✅ |
| 6 rubric | 1 DROP_UNSAFE (margin) | 1 DROP_UNSAFE (Q1 margin → profit/margin) | ✅ |
| 7 approval list | 3 candidates + 1 dropped | 3 candidates + 1 dropped | ✅ |

Headline expectation met: **3 KB-eligible candidates, 1 rubric-dropped.**

## Actual approval list rendered

```
Harvest candidates from 2026-05-26 (1 meeting, 3 candidates after rubric):

[1] b2b-conversion.md → Key Decisions
    + 2026-05-26: Pausing B2B campaign through July to focus on chapter renewals;
      Adam owns partner communication ([▶](https://fathom.video/share/SYNTHETIC?timestamp=74))

[2] chapter-health.md → Key Decisions
    + 2026-05-26: Chapter health framework expanded from 3 tiers to 4 —
      added 'orange' early-warning band ([▶](…?timestamp=922))

[3] 🆕 NEW: ninety-day-check-in-program.md (parent: people-hr, type: l3)
    + Key Decision: 2026-05-26: 90-day check-in program — Red owns instrumentation,
      Heather owns HR side, Q3 2026 launch ([▶](…?timestamp=1800))

⚠ 1 candidate dropped by rubric:
  - "Q1 net margin 14.2% (up from 11.8% in Q4)" (confidential financials — profit/margin)
```

Responded `cancel` → no commit. KB unchanged.

## Findings (the value of running the test before backfill)

### Finding 1 — SLT gate silently skipped harvest for everyone (FIXED)
Step 0 resolved identity via a bare `git config user.email`, which reads the config for the
**current working directory**. close-day runs from `~` (not a git repo), so it fell back to the
**global** config — Kevin's personal gmail, which is not in `kb_authors.txt`. Result:
`slt_writer: False` → the entire harvest was silently skipped, regardless of Step 4c being wired.
This is the "silent skip = indistinguishable from broken" failure mode.

**Fix:** Step 0 now resolves candidate identities from all stable, cwd-independent scopes
(`kb-repo`, `--global`, `toolkit-repo`, `$GIT_AUTHOR_EMAIL`) and treats the user as an SLT writer
if any matches the allowlist. It heartbeats every scope checked. Also set the KB clone's local
identity to `kprentiss@nsls.org` so harvest commits are correctly attributed to the org (they
were previously authored as gmail) and the gate matches via the `kb-repo` scope.

### Finding 2 — `state_change → current_state REPLACE` can clobber unrelated content (NEEDS DECISION)
The fixture assumed `chapter-health.md`'s `current_state` literally read "3 tiers
(green/yellow/red)", making a clean swap safe. The **real** `chapter-health.md` `current_state`
is a multi-fact narrative about the L2-target replacement and advisor/e-board tracking — it says
nothing about a tier list. Step 8's mechanical implementation regex-replaces the **entire**
Current State block with the candidate's **one-sentence** summary, which would destroy the
existing narrative. For this run I mapped the tier change to `key_decisions` (append) instead.

The approval diff does surface the before/after, so a careful human catches it — but the default
`all` would clobber. Recommend resolving before backfill (see plan Task addendum).

### Finding 3 — entries were stamped with harvest date, not meeting date (FIXED)
Step 8 used `datetime.date.today()` for the `- <date>:` entry prefix. Existing KB entries use the
**meeting/decision date**. Backfilling the 2026-05-26 meeting today (2026-05-30) would have
mislabeled every decision as 2026-05-30 — corrupting the historical record, the core purpose of
the KB. **Fix:** Step 8 now stamps `entry_date = cand['meeting_date'] or today`.

## Pipeline verdict
Core pipeline (extract → map → dedup → rubric → approval render) works and matches expectations.
Two correctness bugs found and fixed (gate, date). One write-safety design issue (current_state
clobber) flagged for a decision before Task 17 backfill.
