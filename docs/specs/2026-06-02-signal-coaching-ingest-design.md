---
title: Signal Coaching Ingest — Design
type: feat
status: draft
date: 2026-06-02
plan_depth: deep
extends: 2026-05-16-manager-coaching-person-intelligence.md
---

# Signal Coaching Ingest — Design

## Purpose

Add the **Signal** platform (Quick Notes) as a person-intelligence ingest source so each
direct-report profile is informed by the team member's own weekly narration — their wins,
friction, sentiment trajectory, and goal health — and turn that signal into manager *behavior*
through a **Management lane** in `/open-day` and `/open-week`: celebrate, develop, remove friction.

This operationalizes the company strategy Kevin stated 2026-06-01: *"close the loop and show the
company it's worth doing Quick Notes — SLT does something with friction and manager meetings
reference info from quick notes."*

This extends the completed v2 manager-coaching system (Fathom + Slack + Gmail ingest, org-chart
direct-report scoping, open-day/week surfacing). Signal is the fourth ingest source.

## Data sources (Signal MCP — grounded)

| Tool | Returns | Role here |
|---|---|---|
| `signal_person_history(slug, weeks)` | **Raw weekly Quick Notes narration** + structured wins/friction/sentiment, live from Airtable | Primary coaching evidence — **cache-only**, never raw to vault |
| `signal_person(slug)` | role, manager, 12-wk sentiment trajectory + quotes, analytics | Sentiment reversals / novel lows → attention |
| `signal_person_goals(slug, weeks)` | L2/L3 goal health (R/Y/G), last update, flag-for-discussion, staleness | Align / unblock on goals |
| `signal_friction(weeks)` | actionable friction quotes + per-person **streak counts** | Remove-friction queue (streak = priority) |
| `signal_wins(weeks)` | public + clarified wins | Celebrate queue |
| `signal_team_summary(manager_slug, week)` | submissions, friction+streaks, wins, newly enrolled, analytics deltas | Weekly management digest |

Scope enforcement: Signal already scopes managers to their reporting subtree; Kevin's exec token
is broad, but **coaching focus is deliberately narrowed to direct reports** (`tracking_reason ==
"direct_report"` from `org-chart.json`). Org-wide `signal_wins`/`signal_friction` may color the
weekly digest but do not create or enrich non-report profiles.

## The sensitivity boundary (core safety design)

Quick Notes are employee-authored and can carry HR-sensitive, comp, or health content. The vault
syncs to iCloud and is the substrate for the KB harvest. Therefore:

1. **Raw narration → cache only.** `~/.cache/person-intelligence/signal/<slug>.json`, gitignored,
   short TTL (e.g. 30 days). Never written to `30-people/`.
2. **Distilled → vault.** `synthesize_profile.py` receives raw signal as input but emits only
   rubric-safe distillation, reusing the KB **Sensitive-Content Rubric** (never-write: individual
   comp, named personnel status, HR-sensitive, health, profit, security gaps, active legal,
   vendor-confidential, board-confidential). Sensitive friction becomes a *theme*, not a quote.
3. **Provenance.** Add `signal` to the profile `sources:` frontmatter array.
4. **Decision locked (Kevin, 2026-06-02): distilled-in-vault.** No private `_signal/` raw mirror in
   the vault. Raw lives only in cache.

### Distillation contract (what reaches the vault)

A new compact section on each direct-report profile:

```markdown
## Signal Read
*Last updated: YYYY-MM-DD · window: 12 wks · source: Quick Notes (distilled)*

- **Sentiment:** [trajectory direction — e.g. "steady green; dipped wk of 5/19, recovered"]
- **Recent wins:** [1–3 shareable wins, named, with the week]
- **Recurring friction (themes):** [theme — streak N wks]; [theme — streak N]
- **Goal health:** [N green / N yellow / N red; any flag-for-discussion]
- **Submission cadence:** [submitting weekly | gap of N wks ⚠]
```

Plus **evidence lines appended to `## Coaching Goals`** (existing AI-proposed / Kevin-approved
flow) sourced from Signal, dated, theme-level.

## Architecture

```
Signal API / MCP ──► fetch_signal.py ──► ~/.cache/.../signal/<slug>.json   (RAW, gitignored, TTL)
                                              │
                                              ▼
                          synthesize_profile.py  (raw in → rubric-filtered distillation out)
                                              │
                                              ▼
                          30-people/<Name>.md   (## Signal Read + Coaching-Goal evidence only)
                          sources: [fathom-1on1s, airtable-*, existing-profile, signal]
```

### `fetch_signal.py` (new script, mirrors `fetch_airtable_*.py`)

- Input: `--slug <kebab>` `--weeks <n>` (+ `--reports-only` reading org-chart).
- Output: JSON to stdout `{person, sentiment, wins[], friction[{theme,quote,streak,sensitive:bool}], goals[], history_raw[], submitted_weeks[]}`; status to stderr.
- **Two execution paths (see plan §Phasing):**
  - **MCP-in-orchestrator (Phase 1):** the interactive synthesis session calls `signal_*` MCP
    tools and writes the JSON; `fetch_signal.py` is a thin formatter over that.
  - **Token-direct (Phase 1.5):** `fetch_signal.py` calls the Signal/employee-profiles backend
    directly with the stored token (same posture as `fetch_airtable_*.py`) so the **cron sweep is
    self-sufficient**. Build-time unknown: confirm a REST read surface exists, or query the
    `obsfxvtflbmrfjcbmxoj` Supabase read replica with a scoped key.

### Integration into existing pipeline

- `biweekly_sweep.py` (manifest): add `signal_available: bool` per relationship (slug resolvable
  + is a direct report).
- `synthesize_profile.py`: accept a `signal` field in the combined JSON payload; apply the
  distillation contract + rubric; emit `## Signal Read` and Signal-sourced coaching evidence.
- `extract_coaching_actions.py`: already reads profiles → Signal-derived coaching actions flow to
  open-day automatically once they're in the profile. **No change needed** for the cached path.
- New live path for open-day freshness (see below).

## `/open-day` — Management surfacer

A new section keyed to **who is on today's calendar**, max 1–2 per bucket:

```
🧭 Management — today's people
  🎉 Celebrate  [Person]: "[win]" — say it in [#channel / DM] today
  🌱 Develop    [Person]: [coaching action] — from goal "[title]"
  🔧 Unblock    [Person]: "[friction theme]" (streak N) → own a fix + close the loop
```

- Two reads: cached coaching actions (existing) **+** a live `signal_wins/friction(weeks=1)` pull
  filtered to today's direct reports (freshness).
- **Priority pool:** a friction with **streak ≥ 3** on a direct report becomes a Top-3 Management
  candidate.
- **Cadence flag (N=2, locked):** any direct report not 1:1'd in **2 weeks** (Fathom gap + no
  calendar event) OR who stopped submitting Quick Notes for 2 weeks → surfaced as a check-in.

## `/open-week` — Management cadence lane

Run off `signal_team_summary(manager_slug=self)`:

1. **Week pulse** — submissions, wins, friction+streaks, sentiment deltas, newly enrolled,
   analytics reversals.
2. **Three management intentions** — exactly one celebrate / one develop / one unblock, each on a
   *different* report (never stack one person).
3. **Cadence audit** — 1:1 gaps ≥ 2 wks; stopped-submitting reports.
4. **Coaching-goal progress** — one evidence line per report's active goal; propose upgrades.
5. **Loop-closure review** — did last week's surfaced friction get fixed *and communicated*?
   Unclosed loops roll forward as P1.

## World-class-manager task catalog (data-triggered)

**Weekly (open-week):**
- Recognize 3 named people for specific wins (from `signal_wins`, unacknowledged).
- Remove top friction (streak N) — own a fix, tell the person what changed.
- Close the loop on last week's friction with [person].
- Check in: [report] no Quick Notes / no 1:1 in 2 wks.
- Advance [report]'s development goal — next stretch / visibility move.
- Unblock [report]'s red/flagged goal.

**Daily (open-day, only when triggered):**
- Pre-1:1 brief auto-surfaces for any report on today's calendar (wins, friction, goal health,
  open coaching action, last-met gap).
- Streak-≥3 friction → Management Top-3 candidate.

**Monthly / quarterly (open-week, low cadence):**
- Quarterly growth/career conversation per report (not status).
- Name a stretch assignment for a high-sentiment, green-goal report.
- Recognition audit — did anyone go a quarter without recognition?

## Management model (why these tasks)

Six repeatable manager jobs, each mapped to a signal and a behavior:

| Job | Signal | Behavior |
|---|---|---|
| Recognize | wins | 3 specific public recognitions/week |
| Remove friction | friction + streak | own recurring blockers; streak ≥3 = trust emergency |
| Close the loop | resolved friction | tell the person it was heard + what changed |
| Develop | sentiment + goal trajectory + growth edge | 1 active dev goal/report; create stretch/visibility |
| Cadence | Fathom gap + submissions | no report > 2 wks without a real 1:1 |
| Align | goal health | every report knows their top priority + L1/L2 ladder |

Under-weighted today (from Kevin's own data): **Recognize** and **Close the loop** — cheapest,
highest-trust levers, invisible to a task list. This engine exists to make them automatic.

## Non-goals
- Not org-wide per-person profiles (direct reports only).
- Not raw Quick Notes in the vault.
- Not auto-written coaching goals (stays AI-proposed / Kevin-approved).
- Not a new health dimension — Signal is evidence feeding the existing six.
