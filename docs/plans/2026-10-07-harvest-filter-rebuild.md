# Harvest filter rebuild — backlog plan

**Status:** backlog. Harvest is off by default in close-day / close-week (release
2026-10-07). This plan is the bar for turning it back on.

## Goal

Every harvest run sorts candidates into three buckets the builder can trust:

| Bucket | Meaning | Builder effort |
|---|---|---|
| **Safe** | Fine for an all-hands email | Skim, approve |
| **Not sharing** | Dropped, with a one-line reason | None — listed for transparency |
| **Unsure** | 3–4 items at most | Real decision |

The problem today is the opposite: the approval list is long, so private items get waved
through ("sure, sure, sure").

## Steps

1. **Baseline audit.** A model labels every edit harvest has already committed to the company
   KB as LEAK / BORDERLINE / CLEAN against the rubric plus wider classes (personal life,
   named-person performance or friction, 1:1-only material, financials beyond revenue,
   security, legal, PII). Everything already committed passed the current filter, so each LEAK
   is a measured miss. Any LEAK still in the KB goes to the KB owner to decide on removal.
2. **Scenario suite (~100 cases).** Synthetic meeting snippets, each with an expected bucket:
   rubric categories × meeting types (SLT, team sprint, 1:1, external), clean controls, reshape
   cases, and the audit's BORDERLINE items rewritten as synthetic. A human rules on every
   edge case before it becomes ground truth. Fixtures live in
   `skills/harvest-meeting/references/test-fixtures/`; no real meeting content in the repo.
3. **Filter changes** (candidates, to be chosen against the numbers):
   - Meeting-level gate before any transcript is read: 1:1s and private-titled meetings default
     to skipped (or local-KB only), overridable per meeting.
   - Separate classification pass that outputs the three buckets, rather than PASS / RESHAPE /
     DROP folded into extraction.
   - Rubric additions for whatever classes the audit shows leaking.
   - A cap on the Unsure bucket; overflow goes to Not sharing.
4. **Measure.** Run the new filter on the audit set and the suite. Report:
   LEAK catch rate (dropped or Unsure), CLEAN kept rate, average Unsure count per run.
5. **Turn back on** only when the bar below is met and the KB owner agrees. Coordinate
   with the BI team's knowledge base before re-enabling company-KB writes.

## Bar to re-enable (proposed)

- 100% of audit LEAKs and suite never-write cases land in Not sharing or Unsure.
- ≥ 90% of CLEAN items land in Safe.
- Median Unsure ≤ 4 per daily run.
