---
title: "feat: /role-coach — role-scoped coaching for every seat at NSLS"
type: feat
status: active
date: 2026-06-11
deepened: 2026-06-11
---

# ✨ /role-coach — role-scoped coaching for every seat at NSLS

## Enhancement Summary

**Deepened:** 2026-06-11 · **Agents:** coaching-science researcher, UX designer, memory-ledger designer, simplicity reviewer, security sentinel, architecture strategist

**Key changes from the deepening pass:**
1. **Phase 1 re-scoped to a one-day slice** — zero scripts, zero server changes, zero cadence edits. SKILL.md conventions only; scripts promoted later only if the convention proves unreliable.
2. **"Phase 0" renamed Phase 3a** — the self-scope server endpoint gates nothing until non-exec rollout; Marcus gets full value without it.
3. **Coaching budget made enforceable** — role-coach emits cues to `~/.cache/role-coach/cues.json`; the existing `surface_actions_for_day.py` arbiter grows a second input pool (≤1 role-coach cue, totals stay 3 daily / 5 weekly). The weekly cap (open-week Step 4.6) was missing from v1 entirely.
4. **`fetch_scoped_evidence.py` deleted from the design** — Python can't call MCP. Signal/Hex evidence follows the established orchestrator-calls-MCP-then-pipes-to-normalizer pattern; Airtable reuses existing per-source fetchers.
5. **Coaching pattern upgraded with behavior-change evidence** — if-then implementation intentions (d=.65), elicit-before-prescribe (MI), task-vs-self phrasing (Kluger & DeNisi), affirmation-first ordering, polymorphic delivery, an explicit go-silent rung, and "zero is a valid dose."
6. **Full ledger state machine specified** — 7 states, escalation keyed to `cycles-open`, contested mechanics with evidence-class re-open, 3-active-pattern cap, lapse detection (the silent-drop catcher Marcus's human-coach tracker lacked).
7. **Security hardening section added** — 2 critical (`?as=` trust model, unredacted interview answers), 4 high (cache/tmp lifecycle, tier-drop purge, manager-memo confidentiality, memo retention), 3 medium findings with mitigations.
8. **Write-ownership contract** — role-profile = the seat; operating-memo/personal-profile = the person (only /self-insight writes those); role-coach reads both, writes only `role-coaching/`.
9. **Floor + horizon (2026-06-11 revision):** coaching tracks both the role you have (`role-profile.md`) and the role you want (`role-trajectory.md`) — "here's how you get to the next milestone on the way to X." The trajectory is optional (mastery-in-seat is a valid answer), milestone-gated, and treated as sensitive content.

## Overview

A standalone coaching skill that any NSLS employee can run from the personal toolkit. It resolves who you are (title, role, accountabilities, role strategy), scopes its evidence to the size of your seat (IC → your own Quick Notes; manager → your team; exec/CEO → all of Signal + LOPs + SLT meeting intelligence + Hex business metrics), and coaches you on the best way to contribute from that seat — with a memory, so advice compounds instead of repeating.

**Two role files, one coaching stance.** The skill reads the seat you have (`role-profile.md` — the floor: accountabilities you're paid for today) and the seat you want (`role-trajectory.md` — the horizon: target role + the milestones between here and there). Coaching always comes from both: perform the floor, advance the horizon. "Here's how you get to the next milestone on your way to X" is the default frame, not a special case — Marcus's CEO-in-waiting situation (floor: title "Ignite"; horizon: CEO, gated on contracting) is just the first instance. A user with no target role runs in **mastery mode**: the horizon is depth in the current seat, and the trajectory file is simply absent.

The coaching pattern is the one proven in Marcus's 2026-06-11 leadership review session: evidence sweep → stated-priorities-vs-observed-behavior diff → blind spots at two altitudes → strengths/traps with a crowding-out test → concrete moves with forcing functions → follow-through tracking. This plan codifies that pattern so it works for a CS rep's seat as well as the CEO's.

**Not Marcus-specific.** Marcus is the first user (role: CEO-in-waiting, scope: everything), but the design premise is that the role file, not the skill, carries the role.

## Problem Statement

- The toolkit coaches *habits* (open-week traps, meeting load) and *relationships* (person-intelligence) but nothing coaches the *seat*: "given this role, this strategy, and this evidence, what's the highest-leverage way to contribute?"
- Coaching insight today is session-lucky — the 6/11 review found 6-week-old unclosed patterns precisely because nothing tracks whether named patterns get fixed.
- Everyone below SLT has no coaching loop at all, while the org's role infrastructure (ScoreCards, Role Masters, job leveling, LOPs, Signal) already contains everything needed to coach every seat.

## Proposed Solution

### Architecture

```
/role-coach [--week $WEEK | --date $TODAY | --deep]     # task-shaped flags, harvest style
  ├── Step 0  Identity + role resolution        (read role-profile.md; interview if missing)
  ├── Step 1  Scope detection (server-enforced) (probe Signal API; render what comes back)
  ├── Step 2  Evidence sweep (scoped)           (MCP-in-session + existing fetchers + vault reads)
  ├── Step 3  Coaching synthesis                (references/coaching-pattern.md)
  ├── Step 4  Output redaction pass             (rubric CHECKLIST the model executes — see Security)
  ├── Step 5  Memory update (proposed, not silent) (coaching-log.md conventions)
  └── Step 6  Render: memo / weekly block / daily cue + cache teardown
```

#### Role resolution (Step 0) — precedence order

1. **`10-strategy/role-coaching/role-profile.md`** (vault) — the seat you have, self-described framing included. Created on first run via interview (see UX Appendix §1); user-editable; re-read every run.
1b. **`10-strategy/role-coaching/role-trajectory.md`** (vault, optional) — the seat you want: target role, why, ordered milestones with gates ("contracting signed", "owns a P&L line", "has run a hiring loop end-to-end"), evidence of readiness so far. For Marcus: target = CEO, current milestone = contract executed. Where the target role maps to the NSLS job framework (Heather/Mara's leveling work), milestones reference the framework's next-level expectations rather than inventing parallel criteria. Absent file = mastery mode, stated in the heartbeat.
2. **People Ops Airtable** — Employees (`role_title`, `level`, `role_master_doc_url`, `scorecard_doc_url`) → ScoreCard → Accountabilities + Competencies. Canonical for *what the seat owns*. Pre-fills the interview so users confirm rather than type.
3. **org-chart.json** (builder toolkit `_shared/context/`) — canonical for *structure*: `manager`, `manages[]`, `department`. Freshness check (warn >7 days, reuse `resolve_user.py` pattern).

**Conflicts are surfaced, never silently resolved** — but disclosure is gated (security M7): surface title conflicts the user's own answers create; never reveal a not-yet-announced *manager* change through the conflict prompt. Contractors / people missing from org-chart (e.g., Lauren) get the interview path: self-described role, reduced-confidence coaching, never a fabricated ScoreCard. Role-tier change detected at resolve time → archive coaching log + **purge evidence cache rows above the new tier** (security H3), restart baseline.

**Phase 1 simplification:** for Marcus, role-profile.md is hand-seeded (10 lines). The interview flow, ScoreCard pre-fill, and conflict machinery ship in Phase 3 when non-Marcus users arrive.

#### Scope ladder (Step 1) — enforcement is server-side, always

| Tier | Who | Evidence in scope | Mechanism |
|------|-----|------------------|-----------|
| T1 Self | every employee | own Quick Notes + own goals + own ScoreCard + vault | **NEW** Signal "self scope" endpoint (Phase 3a); ScoreCard via People Ops |
| T2 Manager | `manages[]` non-empty | T1 + reporting subtree (team summary, person histories, sentiment) | existing `?as=<slack_id>` manager scope |
| T3 Exec | `app_role='executive'` (12 people, exists today) | T2 + org-wide Signal, all LOP goals, dept rollups | existing exec scope; LOP base `appAcnl4o8AQVZR1j` read |
| T4 CEO/SLT-deep | T3 + SLT membership | T3 + SLT meeting intelligence (participation/coaching scores, base `appHDEHQA4bvlWwQq`) + Hex threads for business metrics | SLT base read + Hex MCP |

The skill **never widens scope client-side**: it probes what the token returns and renders only that. A 403 produces a heartbeat line ("Signal: no access at this tier — coaching from ScoreCard + vault only"), not an error. `caller_role` from team-summary drives **copy only, never synthesis branching** (security M8) — synthesis iterates over returned records exclusively.

Scope-tier table lives inline in SKILL.md until T1/T2 ship (no separate references file yet).

#### Coaching engine (Step 3) — `references/coaching-pattern.md`

The codified pattern, scaled by tier. Steps 1–6 below are the v1 skeleton; the **Research Insights** that follow are now requirements of the reference doc, not suggestions.

1. **Evidence sweep** — scoped sources, every claim carries a citation (Quick Note date, meeting, goal record, vault file). **Uncitable claims are dropped** — the structural defense against hallucinated evidence.
2. **Stated vs. actual** — role accountabilities + stated priorities (stack rank, goals) diffed against observed behavior (Quick Notes, goal updates, meeting participation).
2b. **Trajectory readiness check** (when role-trajectory.md exists) — the current milestone's gate diffed against evidence: what this cycle produced that a promotion case could cite, what the gate still lacks. The floor is never sacrificed to the horizon: if floor accountabilities slipped while horizon work advanced, that *is* the week's gap (a next-role case built on a neglected current seat is self-defeating, and the coaching says so).
3. **Two-altitude blind spots** — cycle-level (this week) + horizon-level (quarter for ICs/managers; strategy for execs). With a trajectory on file, horizon-level explicitly includes milestone drift: a milestone untouched for 4+ cycles gets named.
4. **Strengths/traps with the crowding-out test** — a strength is named *with* the thing it displaces, evidenced, not moralized.
5. **Moves with forcing functions** — every recommendation names a date, an artifact, or a person. When a trajectory exists, weekly/deep output includes **at least one milestone move**: a this-cycle action that produces citable evidence toward the current gate (not "grow toward the role" — "run the Q3 budget review solo and have Devan countersign the output").
5b. **Trajectory honesty rules** — the coach never implies the org owes the user the target role; it coaches *evidence-building*, not entitlement ("your case for X will cite..."). If the milestones haven't moved in 2 consecutive quarters, deep mode asks the renegotiation question directly: is this still the role you want, or is mastery mode the honest answer? Aspiration drift left unexamined is the trajectory-file version of a zombie pattern.
6. **Memory check** — patterns from `coaching-log.md` (full state machine in Memory Appendix).

##### Research Insights — behavior-change evidence baked into the pattern

- **If-then implementation intentions, co-authored.** Upgrade step 5: every move is rendered in `when X, I will Y` form and the user restates/edits it before it's logged (rehearsal is the effect moderator; d=.65 Gollwitzer & Sheeran, confirmed in a 2024 meta-analysis of 642 tests).
- **Elicit before prescribing (motivational interviewing).** Weekly/deep modes present the diff, then ask "what would you change?" before offering moves; advice is offered with permission ("want a suggestion?"). MI-consistent AI coaching measurably raises user-generated change talk, which predicts behavior change.
- **Task-focused, never self-focused phrasing (Kluger & DeNisi: feedback hurts in 38% of cases, worse as it moves toward the self).** Diffs are artifact-vs-artifact ("the calendar shows X; the stack rank says Y"), never person-vs-claim ("you say X but you do Y").
- **Affirmation-first ordering (self-affirmation research).** Memo ordering rule: strengths-with-evidence (step 4) renders *before* the stated-vs-actual diff (step 2's output), connected to the user's own role-profile values. Cheap defensiveness insurance.
- **Polymorphic delivery.** A recurring pattern never reuses its sentence (habituation is measurable after 2–3 identical exposures): re-raises surface as new evidence, a question, or a metric delta.
- **Feedforward at staleness (Goldsmith).** From escalation rung 1 onward, raises switch tense — stop citing past misses, propose the next-cycle version.
- **Celebrate closure.** Weekly block and deep memo render closed patterns *first* ("2 patterns closed this quarter"). Gap-only coaching is the streak-break demotivator.
- **Zero is a valid dose (JITAI literature: excess prompts → abandonment).** No new evidence since the last cue → silent skip with heartbeat. Plus a user dial in role-profile.md: `coaching_intensity: low | default | high`.
- **Escalate the forcing function, never the frequency.** Same pattern: max 2 raises in original form → 3rd raise must be feedforward + structural proposal → then **go silent and park for the quarterly memo**. Escalation = bigger forcing function at lower frequency.

#### Privacy (Steps 2, 4, 5) — three layers, all reused or extended from shipped work

- **Input side (exists)**: raw Quick Notes cache-only with vault write-guard; `SENSITIVE_PATTERNS` mechanical pre-filter; third-party name stripping (person-intelligence `ingest-scoping.md`).
- **Output side**: the KB sensitive-content rubric ("could this appear in an all-hands email without HR/Finance/Legal flagging it?") runs as a **mandatory pre-write checklist step the model executes** (the rubric is a judgment; close-day Step 4c already runs it this way — no script needed). It gates **every** persistent write: memos, the log, **and role-profile.md interview answers** (security C2).
- **Names policy**: named-person observations appear only for people inside the user's scope; sentiment data is manager-facing only and **never** echoed back to the subject ("you sound overloaded" is forbidden output for T1). Team friction *about the user* is presented as a signal to explore, never anonymous-source accusation.
- **Coaching log stores labels + dates + status + evidence pointers — never quotes.**
- **Write trust ladder (exists)**: structured log rows auto-write; narrative coaching memos are always rendered for approval before vault write; declined memos are discarded with a one-line log entry.

#### Vault artifacts + write ownership

```
10-strategy/role-coaching/
  role-profile.md        # THE SEAT YOU HAVE: role, strategy, accountabilities, scope tier, coaching_intensity (user-editable)
  role-trajectory.md     # THE SEAT YOU WANT (optional): target role, why, milestones w/ gates + evidence checkboxes (user-editable, sensitive)
  coaching-log.md        # pattern ledger (schema in Memory Appendix); patterns may tag lens: floor|horizon
  memos/YYYY-MM-DD-<mode>.md  # approved coaching memos; retention rules in Security section
```

`role-trajectory.md` skeleton:

```markdown
---
target-role: CEO
declared: 2026-06-11
status: active          # active | parked | achieved (archives to memos/archive/, profile interview re-runs)
framework-ref: <job-framework level/role, when one maps>
---
## Why
One paragraph, the user's words.
## Milestones (ordered; current = first unchecked)
- [x] Permanent-CEO offer extended (2026-05-22)
- [ ] Contract executed — gate: signed agreement; evidence so far: Keith engaged 5/26, comp memo to Dana due 6/12
- [ ] First board cycle owned end-to-end as CEO — gate: Aug meeting run solo
## Readiness evidence ledger
Dated pointers a promotion/transition case could cite. Pointers, never quotes.
```

**Write-ownership contract (architecture review):** role-profile.md = *the seat you have*; role-trajectory.md = *the seat you want*; `operating-memo.md` + `personal-profile.md` = *the person*, written **only** by `/self-insight`. Role-coach reads all four and writes only `role-coaching/`. Within the trajectory file, milestones and the Why are the user's to write; role-coach *proposes* check-offs and readiness-evidence lines through the same approval flow as memos (trust ladder — never a silent edit to someone's ambitions). The crowding-out step *diffs observed behavior against the memo's existing "My Traps"* rather than re-deriving them; newly discovered person-level traps route to "run /self-insight," never to a memo edit.

**Cross-skill dedup:** before proposing a person-routed move ("delegate X to Chelsea"), check person-intelligence's `coaching_actions.json` — if a matching coaching goal exists, cite it ("already tracked as a Chelsea goal") instead of duplicating. Ownership rule: subject-of-change owns the artifact (self-directed pattern → coaching-log; person-directed goal → person-intelligence profile).

### Cadence integration — thin callers, one enforceable budget

**Budget mechanism (replaces v1's prose rule):** role-coach never writes to person-intelligence's `coaching_actions.json` (its extractor rewrites that file wholesale — rows would be clobbered). Instead role-coach emits cue candidates to `~/.cache/role-coach/cues.json` (`source: "role-coach"`), and `surface_actions_for_day.py` grows a second input pool with one arbitration rule: **≤1 role-coach cue; person-intelligence fills the remainder; totals stay 3 (daily) / 5 (weekly, open-week Step 4.6 — missing from v1)**. The surfacer's existing decay model (`times_surfaced >= 3` → auto-stale, snooze) doubles as the daily-cue fatigue rule — reused, not reimplemented.

| Caller | New step | Invocation | Output contract |
|--------|----------|------------|-----------------|
| close-day | Step 4d | `/role-coach --date $TODAY` | 1 cue max to cues.json; heartbeat even when 0 |
| open-day | Step 3 ("Role lens" — 3rd sibling section) | reads cues.json via arbiter | shares the 3-action cap; `🪑 Role:` glyph distinguishes from `🎯` |
| close-week | Step 2c | `/role-coach --week $WEEK` | "Role Coaching" block: said/did/gap + ledger deltas (UX §3) |
| open-week | Step 2.6 (beside 2.5 Signal lane) + Step 4.6 pool | reads `coaching-log.md` only — no fresh sweep | open patterns inform stack-rank coaching + trap check; weekly cap 5 holds |
| close-quarter (future) | core step | `/role-coach --deep` | full memo + propose role-profile refresh (pairs with /self-insight) |
| open-quarter (future) | core step | reads latest deep memo | quarter focus derived from memo's "moves" section |

Every caller: heartbeat echo first, fenced slash invocation, "after the skill returns" outcome lines (including the zero/declined cases) — exactly the harvest Step 4c/2b shape. Quarter skills are a separate future project; deep mode is simply designed to slot into them (one-sentence contract, nothing more in this plan).

## Security Hardening (from adversarial review)

**Critical**
- **C1 — `?as=` must be authorization-checked, not identity-trusted.** The server derives the caller from the auth token; `?as=` is only a request the token's role must authorize. Phase 3a acceptance tests must include: IC token + `?as=peer` → 403 (not just the self-read happy path).
- **C2 — Interview answers get the rubric too.** Free-text role-interview answers (comp disputes, struggling reports, health mentions) pass the output checklist before role-profile.md is written; structured fields preferred over free text.

**High**
- **H1b — Aspirations are sensitive content.** `role-trajectory.md` may encode "I want my manager's job" or a not-yet-announced succession. Rules: the file never leaves the vault; `/announce-update` and any shared example are hard-forbidden from referencing it; **daily cues reference the milestone, never the target role by name** (`🪑 Role: contract gate — Keith's redline reply is the blocker, chase today` not `🪑 Toward CEO: ...`) so a glanced-at screen reveals a task, not an ambition. Target-role naming appears only in weekly blocks and deep memos, which render in-session. Interview answers about aspiration pass the same rubric checklist as everything else (C2).
- **H2 — Scratch space lifecycle.** Evidence working set lives in one named dir (`~/.cache/role-coach/evidence/`), short TTL, explicit teardown in Step 6; the existing vault write-guard is asserted to cover the cache path.
- **H3 — Tier-stamped cache.** Cache keys are `(subject_slug, caller_tier, date)`; Step 0 purges rows whose tier exceeds the currently resolved tier (handles exec demotion / manager losing a report).
- **H4 — Manager memos are confidential artifacts.** Any memo containing named-report sentiment gets frontmatter `confidential: true`; `/announce-update` is hard-forbidden from sourcing examples from `memos/` (synthetic examples only).
- **H5 — Retention.** Deep memos auto-archive after one quarter (a prune step in deep mode); the log keeps labels+dates only; SKILL.md states these are personal coaching notes, not personnel records.

**Medium**
- **M6 — Self-scope endpoint returns identical 403/404 for any non-self read** regardless of slug existence (blocks employee enumeration).
- **M7 — Conflict disclosure gating** (see Step 0).
- **M8 — `caller_role` is copy-only** (see Step 1) — add as an acceptance test.

## Implementation Phases

### Phase 1 — The one-day slice: standalone `/role-coach`, T3/T4, Marcus (NO scripts, NO server work, NO cadence edits)
- `skills/role-coach/SKILL.md` — orchestrates everything as conventions: read hand-seeded role-profile.md → evidence sweep via existing `signal_*` MCP tools + existing Airtable fetchers + vault reads, heartbeat per source → coaching pattern per `references/coaching-pattern.md` → rubric checklist → render for approval (UX §4) → append to `coaching-log.md` per the Memory Appendix schema. (**No `disable-model-invocation`** in frontmatter.)
- `references/coaching-pattern.md` — the 6-step pattern + all Research Insights rules (they're prompt patterns; they cost nothing).
- Modes: `--week` and `--deep` only. Daily mode is deferred — it's the most nag-prone surface; weekly must prove out first.
- Hand-seeded `role-profile.md` (10 lines) **and `role-trajectory.md`** (target: CEO; milestone 1: contract executed — the gates already exist in the nsls-ceo-transition project doc, just transcribe them); empty `coaching-log.md` seeded from the 6/11 memo's crowd-out list.
- Success: Marcus runs `/role-coach --deep` and gets the 6/11-quality review reproducibly; `--week` lands the said/did/gap block + Horizon block.

### Phase 2 — Cadence integration + budget arbiter
- cues.json + the `surface_actions_for_day.py` second pool (the one genuine code change; small, in person-intelligence's surfacer)
- Thin callers: close-week Step 2c and open-week Step 2.6/4.6 first; close-day 4d + open-day "Role lens" only after two clean weekly cycles
- Success: one full week with no double-coaching, caps hold at 3/5, no silent skips

### Phase 3 — T1/T2 rollout (everyone at NSLS)
- **3a (server, parallel):** Signal self-scope endpoint in `thensls/nsls-coach`/`employee-profiles` — `scope='self'` on `/api/mcp/person/<slug>`, `/history`, `/goals`; acceptance: IC reads self → 200; IC reads peer (path or `?as=`) → uniform 403 (C1, M6)
- First-run interview flow with Airtable/org-chart pre-fill + conflict surfacing (UX §1); contractor path
- T2 manager mode: named-reports policy, `confidential: true` memos (H4), brand-new-team minimum-evidence rule ("insufficient evidence" beats inference); departed-employee filter on `manages[]`/histories
- `/personal-setup` wiring (`ROLE_COACH=1`, opt-in default for forks); rollout doc via `/announce-update` (synthetic examples only)
- Promote conventions to scripts **only where the convention failed in practice** (candidates: log parsing/validation, cache teardown)
- Success: one IC and one manager pilot outside SLT complete a weekly cycle

### Phase 4 — Quarter hook + Hex lens
- T4 Hex integration: business-metric evidence (e.g., the five-numbers card) via Hex MCP threads, cited like any other source
- Deep mode wired into `open-quarter`/`close-quarter` when those skills are built (separate plan)

### Phase 5 — Society coaching + goals into Signal context (tracked 2026-06-11)
Connect Society's member-platform coaching conversations and goals into Signal's context layer, exposed through the same scope-enforced MCP token (self/manager/exec tiers, employee-profiles #73 enforcement). Two consumers:
1. **Signal Slack bot coaching** — `nsls-coach` team-state/coaching payloads gain Society goal/coaching awareness
2. **role-coach** — evidence sweep gains a Society source row (own data at T1, team at T2+), same citation + redaction rules

Open design questions: employee↔member identity join (auth.nsls.org `sub`?); Society data is customer data — what crosses into the internal stack needs its own rubric pass; server-side stripping decisions (sentiment precedent) before any client sees it. Vault tracking: `20-projects/signal-app/signal-app.md` → Next Step.

## Acceptance Criteria

- [ ] Phase 1 loop works end-to-end for Marcus with zero new scripts: role → scoped evidence → coaching → approval → ledger
- [ ] Trajectory: weekly/deep output contains exactly one milestone move (if-then form) when role-trajectory.md exists; mastery mode (no file) renders no horizon content and no prompt to create one; milestone check-offs go through the approval flow; daily cues never name the target role (H1b)
- [ ] Floor-before-horizon: a test week where floor accountabilities slipped while horizon work advanced produces a gap line naming the slip, not a celebration of milestone progress
- [ ] Every coaching claim in a memo carries a citation; uncitable claims absent
- [ ] Memo ordering: closures → strengths-with-evidence → diff → moves (affirmation-first rule)
- [ ] Every move is if-then formatted and user-restated before logging
- [ ] Output rubric checklist: a planted comp detail in test evidence never reaches a memo, the log, or role-profile.md
- [ ] Ledger: cold start (2 baseline runs), contested suppression + evidence-class re-open, lapse detection at 6 idle cycles, 3-active cap with swap proposals
- [ ] Cadence: open-day total ≤3 with ≤1 role-coach cue; open-week total ≤5; zero-evidence days produce heartbeat skips
- [ ] Approval flow: section-by-section accept/edit/contest/decline; decline discards with one-line log
- [ ] Scope: T1 user cannot elicit teammate data through any prompt; 403s degrade with heartbeats; tier drop purges cache
- [ ] Marcus (T4), one manager (T2), one IC (T1) each complete a weekly cycle (Phases 1→3)

## Dependencies & Risks

| Risk | Mitigation |
|------|------------|
| Signal self-scope endpoint slips | T1 degraded mode ships anyway: ScoreCard + vault coaching with explicit "no Signal evidence" banner |
| CEO org-wide coaching perceived as surveillance | Dana's CPM framing — manager accountability, not monitoring; coaching output is about the *user's* contribution; evidence stays aggregate below T2 scope; rubric on output; H4/H5 confidentiality + retention |
| Advice fatigue / nagging | go-silent rung, polymorphic delivery, contested state, zero-is-valid-dose, surfacer decay reuse — and daily mode deferred until weekly proves out |
| Cadence-skill bloat | thin callers, one-line cues, single arbiter-enforced budget |
| org-chart/Airtable drift | freshness warnings; Airtable gotchas doc (field IDs, Python-side filtering) |
| Hex/Signal/Airtable outages | per-source heartbeat degradation; never block the cadence skill |
| Convention (no-script) Phase 1 proves flaky | promote exactly the failing convention to a script in Phase 3; schema designed to be machine-parseable from day one |

---

## UX Appendix (design pass, 2026-06-11)

### §1 First-run interview → role-profile.md
Max 5 questions; only Q3–Q5 require typing (Airtable/org-chart pre-fill makes Q1–Q2 confirmations):

```
🪑 Setting up your seat (one time, ~5 minutes)

Here's what the org systems say about you:
  Title:        Ignite (People Ops, level L4)
  Reports to:   Warren Aldrich
  You manage:   — (no direct reports in org-chart.json)
  Accountable for (ScoreCard, updated 2026-04-12): [3 items]

Q1. Is the structure right — manager, reports, department? (yes / correct it)
Q2. Are these still your accountabilities? (yes / what changed)
Q3. In one sentence, what does this seat exist to do? (your words, not the job description)
Q4. What's the one thing that would make this quarter a success?
Q5. Anything about your role the org chart doesn't capture?
Q6. Where do you want this seat to lead — is there a next role you're working toward?
    ("happy where I am" is a complete answer — I'll coach depth in this seat instead)
Q7. (if Q6 names a role) What's the very next gate between you and it — the thing that,
    once true, moves you visibly closer? (this becomes milestone #1 in role-trajectory.md)
```

Q6–Q7 answers write `role-trajectory.md` (after the rubric pass — aspirations are sensitive, H1b). The closing "here's your seat" render gains a Horizon line: `Horizon: CEO — current gate: contract executed`.

Conflict moment (fires on divergence, never silently resolved):
```
⚠️ Conflict: org-chart.json says "Ignite"; you described "CEO in waiting".
  [1] Coach the title  [2] Coach your framing  [3] Both — title is the floor,
      your framing is the horizon (recommended for succession seats)
```

Closes with a full "here's your seat as I understand it" render → approve → write (trust ladder). Contractor path: "You're not in org-chart.json — I'll coach from your own words at reduced confidence."

### §2 The daily cue (Phase 2+)
One line, `🪑 Role:` glyph (visually distinct from person-intelligence's `🎯`), consumes ≤1 of the 3-action budget, must cite + name a forcing function + carry the log tag:

```
GOOD: 🪑 Role: ScoreCard owns "cohort NPS" but no NPS data touched in 9 days —
      pull the Hex card before Thursday's review. [open: week 1]
BAD:  🪑 Role: Remember to stay strategic and prioritize what matters most today!
```
Zero case: `🪑 Role lens: log scanned, 0 open patterns relevant today.`

### §3 The weekly block
≤10 lines, no tables of shame — three labeled prose lines + ledger deltas. Numbers carry the judgment:

```
### Role Coaching — week of Jun 8
**Said:** #1 priority = ship L2 activation experiment (stack rank, Mon).
**Did:** 11h on retreat logistics, 1.5h on activation (calendar + Quick Notes, Jun 8–12).
**Gap:** Your #1 got 9% of the week. Logistics is delegable to Mara; the experiment is not.

**Pattern ledger:**
  ↗ "IC work crowds goal work" — week 3, escalating. Forcing function: book the Tue block before Monday standup.
  ✓ "No Hex data before reviews" — closed (pulled the card both reviews this week).
  ⏸ "Avoids Warren escalations" — contested 5/28, suppressed pending new evidence class.

**Horizon — CEO, gate: contract executed:**
  Evidence this week: comp memo sent to Dana 6/12 ✓. Still open: Keith's redline.
  Milestone move for next week: when Keith replies, I will turn it same-day and copy Dana.
```

(The Horizon block renders only when role-trajectory.md exists and only in weekly/deep modes; one milestone, one evidence line, one if-then move. Mastery mode renders nothing here — no nag to acquire an ambition.)
Status grammar: `↗ escalating / → steady / ↘ improving / ✓ closed / ⏸ contested`, always with `week N`.

### §4 Deep memo approval flow
Present full memo in-session, then **section-by-section** approval ("all" accepts the rest). Per section: **Accept / Edit / Contest a claim / Decline section**.
- Contest: claim stays, marked inline — `> ⏸ CONTESTED (Marcus, 2026-06-11): "<reason>" — suppressed until new evidence class.` Ledger row flips to contested. Contested ≠ deleted.
- Decline: section discarded entirely; one-line log entry; no ghost copies.
- Close: `Writing memos/2026-06-11-deep.md (5 accepted, 1 declined, 2 claims contested). Log: 3 patterns seeded, 1 closed.`

### §5 Tone spec
Buffett-letter register: declarative headline first, numbers over adjectives, every negative paired with its cost and a next move. **Name the cost, not the sin.** No corporate-speak.

Right: *"You said activation was #1. It got 1.5 of 40 hours. The retreat got 11. One of those two numbers is the real priority — which?"*
Wrong: *"You have a tendency to procrastinate on the hard things, which suggests an avoidance pattern."* (names the sin, diagnoses character, cites nothing)
Wrong: *"Great job this week! You're really crushing it!"* (adjectives doing the work numbers should)

---

## Memory Appendix — coaching-log.md design (2026-06-11)

**Prior-art findings:** Marcus's human-coach tracker (45 commitments) failed three ways a state machine fixes: silent drops surfaced only at audit (→ time-based `lapsed`), no aging on 12 open items (→ `cycles-open` counter), and rows were *moves* so the same pattern reappeared as 3 separate commitments (→ **rows are patterns; moves attach to patterns**). The shipped loop-closure ledger contributes ids, idempotent reconcile, and `surfaced` counts; person-intelligence contributes the section format. Format is **markdown sections** (not a table, not JSON) because contesting requires human editing in Obsidian; the file is validated on every run, malformed edits get a heartbeat warning.

### Schema (one `###` block per pattern)
```markdown
### P003 — Written closes lag verbal agreements
state: open | first-named: 2026-06-11 | last-evidence: 2026-06-11 | cycles-open: 0 | surfaced: 0 | escalation: 0
**Pattern**: Comp/role decisions reach verbal agreement; the written close lags weeks.
**Move (current)**: When a comp/role agreement happens verbally, I will send a written recap same-day.   # if-then form, user-restated
**Evidence**: (dated pointers, never quotes; cap 5)
- 2026-06-11: Warren comp framework verbally agreed ~5/06, no artifact by 6/11 (memos/2026-06-11-deep.md §4)
**History**: 2026-06-11 proposed (deep) → confirmed by Marcus
```
File frontmatter: `runs: N`, `tier: T4`, `active_count`. Role change archives the file to `memos/archive/coaching-log-<role>-<date>.md`.

### States & transitions
`proposed → open → progressing ⇄ open → closed`, plus `contested`, `lapsed`, `archived`.
- → proposed: skill, weekly/deep only, requires ≥2 dated citations from ≥2 distinct cycles
- open → contested: **user only** (inline at approval, `--contest P003 "<reason>"`, or direct file edit — file is truth)
- contested → open: skill *proposes* re-open on a **new evidence class** only (a source *type* absent at contest time); same-class recurrence never re-opens
- contested → closed: auto after 2 quarterly reviews with zero new-class evidence (the contest was right)
- open/progressing → lapsed: zero evidence either way for 6 weekly cycles — the silent-drop catcher; quarterly forces triage (recommit / close / contest)
- closed: user explicit, or skill proposes after 3 consecutive counter-evidence cycles

**Cadence draw rights:** daily → `open`/`progressing` only, max 1. Weekly → those + new proposals + transition announcements. Quarterly → everything, including contested (one line, no relitigation) and closed-since-last-quarter (celebrated first).

### Escalation ladder (keyed to cycles-open; `surfaced` enforces phrasing variety)
- **Rung 0 (1–2 cycles):** normal raise; at `surfaced ≥ 2`, verbatim repeat forbidden — reframe or stay silent.
- **Rung 1 (3 cycles):** age flag + feedforward tense + forcing function escalates to artifact-with-date; output shifts from advice to question.
- **Rung 2 (6 cycles):** forcing function adds a named person (role-profile's challenge team — Dana/Warren for Marcus); weekly block demands a state change: recommit with a *new* move, contest, or close-on-purpose. No decision after 2 more cycles → forced triage line that cannot be skipped.

### Cold start & cap
Run 1 = interview + inventory, zero patterns. Run 2 = proposals allowed, no escalation. **Cap: 3 active** (`open`+`progressing`) — maps to the 3-action budget; Marcus's own data argues the ceiling (the "max 5 projects" commitment failed at 14; ≤3 live commitments stuck). At cap, the skill proposes a **swap**, never a 4th.

### Trajectory interplay
Milestone *state* lives in role-trajectory.md (checkboxes + evidence ledger), not in the coaching log — milestones are goals, patterns are behaviors. The ledger participates two ways: (1) patterns may carry `lens: horizon` when the recurring behavior blocks a milestone specifically ("avoids the contract chase" is a pattern; "contract executed" stays a milestone); horizon patterns count against the same 3-active cap — the horizon doesn't get a separate nag budget. (2) Deep mode runs the **2-quarter renegotiation check**: no milestone movement across two quarterly memos → the memo's Trajectory section asks the keep/park/mastery question outright, and `status: parked` silences all horizon coaching without deleting the ambition.

---

## References

- Prior art: `docs/plans/2026-05-16-manager-coaching-person-intelligence.md` (trust ladder, activation, caps), `docs/plans/2026-06-02-signal-coaching-ingest.md` (distilled-in-vault, rubric, loop-closure ledger)
- Integration template: `skills/harvest-meeting/SKILL.md` + close-day Step 4c (`skills/close-day/SKILL.md:793`), close-week Step 2b (`skills/close-week/SKILL.md:292`)
- Hooks: `skills/open-week/SKILL.md` Steps 1.5–2.6 + 4.6, `skills/open-day/SKILL.md` Step 3 sections; arbiter: `person-intelligence/scripts/surface_actions_for_day.py`
- Scope enforcement: `nsls-coach/docs/superpowers/specs/2026-06-02-answer-questions-and-exec-scope-design.md`
- Role data: `people-ops/_shared/references/airtable-schema.md` (Employees, ScoreCards, Accountabilities, Competencies)
- Privacy: `skills/person-intelligence/references/ingest-scoping.md`, KB sensitive-content rubric
- Behavior-change evidence: Gollwitzer & Sheeran (implementation intentions); Kluger & DeNisi 1996 (feedback intervention theory); Sherman & Cohen (self-affirmation); Goldsmith (feedforward); CHI 2015 polymorphic warnings; JMIR 2024 JITAI dosing review
- Coaching pattern source: 2026-06-11 leadership review session (this plan codifies its method)
