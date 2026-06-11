---
name: role-coach
description: >-
  Role-scoped coaching from your seat at NSLS — reads the role you have
  (role-profile.md) and the role you want (role-trajectory.md), sweeps evidence
  scoped to your access tier, and coaches the gap with a pattern ledger that
  remembers across cycles. Use when the user says "role coach", "coach my role",
  "coach me on my role", "how am I doing in my role", "weekly role review",
  "role coaching", "/role-coach", "/role-coach --week", "/role-coach --deep",
  or asks for seat-specific contribution coaching. Future: invoked by
  close-week Step 2c and close-quarter.
---

# Role Coach

Coach the user on the best way to contribute from their seat — the role they have (the floor) and the role they want (the horizon) — using cited evidence and a pattern ledger so advice compounds instead of repeating.

Read `OBSIDIAN_VAULT_PATH` from `~/.claude/local-plugins/nsls-personal-toolkit/.env`.

**REQUIRED READING before Step 3:** `references/coaching-pattern.md` (the coaching engine — evidence rules, phrasing rules, escalation ladder, tone). Do not synthesize coaching without it.

## Modes

| Flag | Window | Output | Caller |
|------|--------|--------|--------|
| `--date [YYYY-MM-DD]` | that day | ≤1 daily cue (🪑 line) — or a heartbeat skip | manual; close-day Step 4d |
| `--week [YYYY-Www]` | the named week (default: current) | Role Coaching block (said/did/gap + ledger deltas + horizon) + one cue to cues.json | manual; close-week Step 2c |
| `--deep` | since last deep memo (or 90 days) | full memo, section-by-section approval | manual; close-quarter (future) |

Open-week reads the ledger directly (Step 2.6); open-day and open-week pick up the queued cue
through the person-intelligence surfacer (`role_cue` field — at most 1, inside the 3/5 caps).

**Daily mode is deliberately thin.** It does NOT run the full engine: it scans the day's evidence
(today's daily note, today's Quick Note if any) against `open`/`progressing` patterns only, and
renders at most ONE `🪑 Role:` line (UX rules: cite, name a forcing function, carry the `[state: week N]`
tag, never name the trajectory's target role). **Zero is a valid dose** — no new evidence today →
`Step 3: no pattern instance today — no cue (zero dose)`. No `cycles-open` ticks, no proposals,
no escalation changes, no memo. If today's evidence sharpened the queued cue, update `cues.json`
(replace); otherwise leave the weekly cue in place.

## Design rules (apply to every step)

- **Heartbeat every step**, including zero cases ("Step 2: Signal — no access at this tier, skipping"). Silent skips are indistinguishable from broken.
- **Scope is server-enforced.** Probe sources; render only what comes back. Never retry a 403 with widened parameters. `caller_role` (if returned) drives copy only — synthesis iterates over returned records exclusively.
- **Every claim carries a citation** (file, date, record, meeting). Uncitable claims are dropped before rendering.
- **Nothing persistent is written without the redaction checklist (Step 4) and, for narrative content, user approval (Step 5).**

## Step 0: Identity + role resolution

1. Read `$OBSIDIAN_VAULT_PATH/10-strategy/role-coaching/role-profile.md` (the seat you have) and `role-trajectory.md` (the seat you want — optional).
2. Heartbeat what was found:
   - `Step 0: seat = <seat name> (tier <T1-T4>), horizon = <target role> (gate: <current milestone>)` or
   - `Step 0: seat = <seat>, no trajectory file — mastery mode (no horizon coaching, no prompt to create one)`
3. **Missing role-profile.md** → run the first-run interview (see `references/coaching-pattern.md` §Interview). Phase 1 note: Kevin's files are hand-seeded; the interview is the fallback, not the norm.
4. If frontmatter `tier:` differs from the last run recorded in coaching-log.md frontmatter → archive `coaching-log.md` to `memos/archive/coaching-log-<old-seat>-<date>.md`, start a fresh ledger, and purge `~/.cache/role-coach/` entirely. Heartbeat it.
5. Read `10-strategy/operating-memo.md` and `personal-profile.md` if present (the *person* — written only by /self-insight; this skill never edits them). Read `coaching-log.md` and note `runs:` count.

## Step 1: Scope detection

Probe in order, heartbeat each source as available/unavailable:

| Source | How | Tier |
|--------|-----|------|
| Vault (daily/weekly notes, stack-rank, goals, lops-summary) | direct reads | all |
| Signal | `signal_*` MCP tools (load via ToolSearch if deferred); absent/403 → skip | T1+ (self scope: own slug only — person/history/goals; sentiment is server-stripped) |
| LOP goals | Airtable MCP, base `appAcnl4o8AQVZR1j`; absent → skip | T3+ |
| SLT meeting intelligence | Airtable MCP, base `appHDEHQA4bvlWwQq`; absent → skip | T4 |
| Hex business metrics | Phase 4 — heartbeat "not yet wired" | T4 |

`Step 1: scope = T4 seat; access this run: vault ✓, Signal ✓ (org-wide), LOP ✓, SLT ✓, Hex (Phase 4)`

Tier labels the seat; **access drives synthesis**. A T4 user with no MCP connections gets vault-only coaching with an honest heartbeat — never an error, never invented data.

## Step 2: Evidence sweep (scoped to mode window)

Gather, citing everything. For `--week`: the week's daily notes, the weekly note + stack-rank if present, Signal/goal activity in the window. For `--deep`: everything since the last memo in `memos/` (or 90 days), using parallel subagents per source group when volume warrants.

Collect specifically:
1. **Stated priorities** — stack-rank, weekly Top 3 / morning Top 3s, goals the seat DRIs.
2. **Observed behavior** — time/work evidence from daily notes, Quick Notes, goal updates, meeting participation.
3. **Floor evidence** — activity against each role-profile accountability (including "none found," which is itself evidence).
4. **Horizon evidence** (if trajectory exists) — anything that moved the current milestone's gate, and anything a readiness case could cite.
5. **Ledger evidence** — for each `open`/`progressing` pattern, scan the window for instances and counter-instances.

Working set goes to `~/.cache/role-coach/evidence/` only (never the vault); small in-session sweeps may skip the cache entirely — Step 6 heartbeats "nothing to delete". Heartbeat counts: `Step 2: swept 5 daily notes, 1 stack-rank, 12 Signal records, 3 goal updates; ledger: P001 2 instances, P002 0, P003 1 counter`.

## Step 3: Coaching synthesis

Follow `references/coaching-pattern.md` exactly — the 6-step engine, the phrasing rules (artifact-vs-artifact, if-then moves, affirmation-first ordering, polymorphic re-raises), the escalation ladder keyed to `cycles-open`, and the tone spec. Honor `coaching_intensity:` from role-profile frontmatter.

Mode shapes:
- `--week` → the ≤10-line Role Coaching block: **Said / Did / Gap** (3 prose lines, numbers carry the judgment) + **Pattern ledger** deltas (`↗ → ↘ ✓ ⏸` with `week N`, where **N = `cycles-open` after this run's tick**) + **Horizon** (only if trajectory exists: one milestone, one evidence line, one if-then milestone move).
- `--deep` → full memo: closures first, strengths-with-evidence, stated-vs-actual, two-altitude blind spots, trajectory readiness + 2-quarter renegotiation check, moves (each if-then, each with a forcing function), ledger proposals (new patterns need ≥2 dated citations from ≥2 distinct cycles).

Mode-shape edge rules (from skill testing, 2026-06-11):
- **Week in progress** (running `--week` for the current, uncompleted week): render counts with "(in progress)", note evidence-through date, and propose **no `cycles-open` ticks** — cycles tick only on completed weeks, so a later close-week run can't double-tick. A move that isn't testable yet (e.g., it fires at close-week) renders `→` with a "not yet testable" note.
- **Cold start** (`runs:` < 2): the ledger section still renders as counts; bookkeeping ticks apply; **`surfaced` does NOT increment** (a baseline run isn't a raise); no unfixed-pattern flags, no escalation language.
- **Dual-lens items** (a slipped floor item that is also the horizon gate artifact): may render in both Gap and Horizon with a cross-reference, but it counts as ONE raise — `surfaced` ticks once.

## Step 4: Redaction checklist (gates the RENDER, not just the write)

Run the checklist on everything the user will see, not only what gets persisted — what's rendered is what may later be copied, screenshotted, or persisted. Check the draft against the KB sensitive-content rubric — "could this appear in an all-hands email without HR/Finance/Legal/InfoSec flagging it?" Specifically strip or reshape:

1. Individual compensation (salaries, SARs grants, bonuses, comp asks) — pattern labels may say "comp decisions" but never amounts or terms
2. Named personnel decisions (hiring/firing/promotion of others) — role descriptors over names where the point survives
3. Health, leave, accommodations — anyone's
4. Profit numbers (revenue is OK)
5. Verbatim Quick Notes quotes from anyone but the user — pointers and paraphrase only
6. Sentiment about a named person echoed toward that person's possible view — the ledger and memos store labels + dates + pointers, never quotes
7. Board-confidential and not-yet-announced org changes
8. Security gaps

Heartbeat the pass: `Step 4: redaction checklist — 2 reshapes (comp amount → "the comp decision", named report → "a direct report"), 0 drops`.

Edge rules:
- **Source files that violate the rubric** (e.g., a role-file readiness line containing an amount or third-party name): flag to the user, never propagate into renders, memos, or the ledger. The skill doesn't silently edit source files.
- **The user's own comp/contract detail** may live in their own role files (private vault, H1b rules) — but it still never propagates into memos or ledger rows; renders reference "the contract gate," not terms.
- **Vault-embedded copies of Signal/Airtable data** (e.g., SLT-action snapshots inside daily notes) are legitimate vault evidence — cite the vault file, not the unavailable source. The scope rule governs live API calls, not the user's own notes.

## Step 5: Render, approve, remember

- `--week`: render the block in-session. Ledger state changes it implies (instance counts, `cycles-open` ticks, escalation rung changes, proposed transitions) are listed under the block as one-line items; apply them to `coaching-log.md` after the user acknowledges (a bare "ok"/"thanks" counts; objections are honored item-by-item). **Two ack classes:** bookkeeping (`runs:` increment, ticks, evidence pointers) = ok-class; pattern *proposals*, milestone *check-offs*, and any *move* (it must be restated or edited by the user per the pattern reference) = explicit-yes class. A milestone the user already hand-checked in role-trajectory.md is authoritative — reconcile silently with a heartbeat, don't re-propose it.
- `--deep`: section-by-section approval — **Accept / Edit / Contest a claim / Decline section** ("all" accepts the rest):
  - Contest → claim stays, marked inline `> ⏸ CONTESTED (<user>, <date>): "<reason>" — suppressed until new evidence class.` Ledger row → `contested`.
  - Decline → section discarded; one-line ledger note; no ghost copies.
  - Then write `memos/YYYY-MM-DD-deep.md` and apply approved ledger changes.
- Trajectory writes (milestone check-offs, readiness-evidence lines) are always proposals — the Why and the milestones are the user's to author.
- **Cue emission** (`--week`, after the move is restated/approved): write exactly ONE cue to `~/.cache/role-coach/cues.json`, **replacing** any prior pending cues (one live cue at a time). The cue is the week's single highest-leverage if-then — the milestone move when a trajectory exists, else the highest-rung open pattern's move. Cue text obeys H1b: reference the gate/artifact, never the target role by name. Format:

  ```json
  {"cues": [{"id": "P001-2026-06-12", "pattern_id": "P001", "text": "🪑 Role: <if-then, cited>",
             "lens": "floor", "created": "2026-06-12", "expires": "2026-06-19",
             "status": "pending", "times_surfaced": 0, "last_surfaced": null}]}
  ```

  `expires` = 7 days out (the cue dies when the next weekly run replaces it anyway). The person-intelligence surfacer (`surface_actions_for_day.py --weekly`) arbitrates: at most one role cue, inside the 3/5 caps, same decay model (3 surfacings → stale). Heartbeat the write: `Step 5: cue queued for open-week (P001, expires 6/19)` or `Step 5: no cue this week (move declined / zero dose)`.
- Close with the write summary: `Writing memos/2026-06-11-deep.md (5 accepted, 1 declined, 2 contested). Log: 3 seeded, 1 closed.`

## Step 6: Teardown + retention

- Delete `~/.cache/role-coach/evidence/` for this run. Heartbeat it.
- `--deep` only: archive memos older than one quarter to `memos/archive/` (the ledger keeps the durable labels). Heartbeat count.

## Ledger format (`coaching-log.md`)

File frontmatter: `runs: N`, `tier: T4`, `active_count: N` (cap 3 — see pattern reference for the swap rule).

One `###` block per pattern:

```markdown
### P001 — Written closes lag verbal agreements
state: open | lens: floor | first-named: 2026-06-11 | last-evidence: 2026-06-11 | cycles-open: 0 | surfaced: 0 | escalation: 0
**Pattern**: One-sentence behavioral description. No quotes, no amounts, no third-party names.
**Move (current)**: When <trigger>, I will <action>.   # if-then form, user-restated
**Evidence**: (dated pointers, never quotes; cap 5 — prune oldest to the citing memo)
- 2026-06-11: <pointer> (<source>)
**History**: 2026-06-11 proposed (deep) → confirmed
```

States: `proposed | open | progressing | contested | lapsed | closed | archived`.
Key transitions (full machine in the plan): user-only → `contested`; zero evidence either way for 6 weekly cycles → `lapsed` (quarterly forces triage); 3 consecutive counter-evidence cycles → skill *proposes* `closed`; contested re-opens only on a **new evidence class**, by proposal. Hand-edits to the file are legal — validate on read, heartbeat (never silently skip) malformed blocks.

## Tier rules (org-wide rollout)

**T1 — individual contributor (self scope):**
- Evidence = own Signal history + own goals (self-scope endpoints) + own vault/notes if present. A 403 elsewhere is normal, not an error.
- If Signal isn't connected at all, coach from ScoreCard accountabilities + vault with an explicit banner: `No Signal evidence this run — coaching from your role docs and notes only.`
- **Never quote or characterize teammates.** A teammate appears only as a role descriptor when the user's own evidence mentions them ("a teammate's review unblocked X").
- Sentiment is never part of T1 coaching — the server strips it, and the skill never infers it back ("you sound overloaded" is forbidden output).

**T2 — manager:**
- Named-person observations are allowed only for people in the caller's reporting subtree, and only as coaching input for the *user's* management behavior — never as a verdict on the report.
- **Memos containing named-report observations get frontmatter `confidential: true`** and are excluded from any sharing surface (announce-update, examples, screenshots).
- **Brand-new team rule:** if most reports have <4 weeks of history, render "insufficient evidence" for team-pattern claims — never infer a pattern from one or two weeks of someone's Quick Notes.
- **Departed-employee filter:** skip anyone no longer active in org-chart.json/Signal; never generate coaching about a departed person.

**T3/T4 — exec/CEO:** as Phase 1 (org-wide evidence, aggregate below-scope, rubric on render).

## Privacy boundaries (hard rules)

- Raw evidence (Quick Notes text, transcripts) lives in `~/.cache/role-coach/` only — never the vault.
- `role-trajectory.md` is sensitive: never referenced by `/announce-update` or any shared example; aspiration content passes Step 4 like everything else.
- Sentiment data is manager-facing only; never render "you sound X" toward the subject of the sentiment.
- Friction signals *about the user* render as a signal to explore, never as anonymous-source accusations.
- These are personal coaching notes, not personnel records.
