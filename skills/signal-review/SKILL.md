---
name: signal-review
description: >-
  Use weekly during /open-week (Monday) — or on demand — to review direct
  reports' Signal data (Quick Notes, wins, friction) and surface a ranked
  list of who needs a response this week and why. Trigger phrases: signal
  review, review my team's signal, who needs a check-in, weekly people
  review, /signal-review. For managers reviewing their reporting subtree.
  Read-only and triage-only — it does NOT draft or send replies.
---

# /signal-review — Who needs you this week

## SAFETY: PERMISSION TIERS
1. **Read-only** — every `signal_*` call is read-only. Reading the team's Quick Notes, wins, and friction is tier 1, no friction.
2. **Local write** — writes a "Signal Review" triage block into the current `/open-week` weekly note (or the daily note). Tier 2: say what's written and where.
3. **No sends — hard line.** This skill is **triage-only**. It NEVER drafts or sends DMs/replies on the manager's behalf. Surfacing what needs a response ≠ writing the response. (Turning on drafts/sends later is a deliberate scope change, not a default.)

## Purpose
Turn the weekly firehose of the team's Signal into a short, ranked **"who needs you, and why"** — so a struggling report, an unacknowledged win, or a quietly-stalling goal never slips, without drowning the manager in a dashboard. The intelligence is the triage plus the *human moment* behind each item — the report's actual words — not the metrics.

## Prerequisite
The `signal_*` tools must be connected (`signal_team_summary`, `signal_wins`, `signal_friction`, `signal_person`, `signal_person_history`, `signal_person_goals`). If they 403 or are missing → run **/signal-setup** (writes the personal token; managers only — builders with no direct reports 403 on every endpoint). Scope follows the token: you see your reporting subtree.

## When it runs
**Weekly, folded into /open-week (Monday).** Also on demand ("signal review"). One pass per week is the default cadence.

## Scope
- **Primary — your direct reports.** Review each one's week.
- **Escalate notable skip-levels** — surface someone deeper in the subtree *only* when their signal is notable (strong/new friction, a big win, a broken streak). Do not list the whole org.
- **Data-gap honesty:** Signal "my team" reflects the reporting structure in the `employee-profiles` base. If a report who *should* be yours isn't showing (e.g., a just-transitioned report whose manager field hasn't propagated), **flag the gap** — don't silently omit them.

## The flow
1. **Prereq check.** Tools available? If not → /signal-setup.
2. **Pull the week:**
   - `signal_team_summary` → subtree overview (participation %, sentiment trend).
   - `signal_friction` (actionable, last ~1–2 weeks) → what's hard.
   - `signal_wins` → what went well.
   - For flagged people: `signal_person` / `signal_person_history` (sentiment trend, reflection streak) / `signal_person_goals` (stalls).
3. **Triage — rank what needs *your* response this week:**
   - 🔴 **Check-in:** friction that's new or escalating, or a report sounding stuck/overloaded.
   - 🟢 **Acknowledge:** a notable win (cheap, high-trust — easy to miss).
   - ⚪ **Nudge:** a broken reflection streak (stopped submitting) — is something up?
   - 🎯 **Coach:** a stalled coaching goal (cross-ref /person-intelligence).
   - Skip-level escalations: only if notable.
4. **Output — a ranked `Signal Review` block** in the open-week note. Per item: **person · what (the actual quote/moment) · why it needs you · suggested response *type*** (acknowledge / check-in / coach / nudge). **No drafted message** — the manager writes the response.
5. **Cross-ref coaching:** pull active coaching goals from /person-intelligence so the triage reflects what's already being developed in each person.

## Macro / micro
- **Macro:** team participation %, sentiment trend (climbing/dipping), count in friction this week.
- **Micro:** the report's actual words, the specific friction quote, whose streak broke, which goal stalled.
Lead with the 2–3 micro moments that matter; back them with the macro. A dashboard alone is not the point.

## Diagnostic loop
**TRY → OBSERVE → DIAGNOSE → ADAPT.**
- `signal_*` 403 / missing → /signal-setup (token). Still 403 after setup → you have no direct reports registered → check the `employee-profiles` reporting data.
- Empty team, or a known report missing → reporting structure not reflected in `employee-profiles` yet (e.g., a just-transitioned report). Flag it; don't report "no data" as "all good."
- Friction empty/stale → widen the window, or sanity-check against `signal_team_summary` for the period.

## Output guidelines
- Ranked, short, human. **5–8 items max**; beyond that, top items + "+N more."
- Lead with people who need a **check-in** (friction) over wins.
- This is private people data — keep the triage in the manager's Obsidian note, never anywhere shared.
- **Triage only:** never include a drafted reply, never send anything.

## Service awareness
- **Setup:** /signal-setup (token).
- **Cadence host:** /open-week (this runs inside the Monday routine).
- **Coaching continuity:** /person-intelligence (goals + biweekly relationship health).
- **Cross-system intelligence:** /data-intel.

## Red flags — STOP
- About to draft a reply or send a DM → **STOP.** Triage-only; the manager responds.
- About to list the whole org → **STOP.** Direct reports + notable skip-levels only.
- About to drop a report because Signal shows no data → **STOP.** Flag the data gap (reporting structure may be stale).
- Tools missing and about to give up → **STOP.** Route to /signal-setup.

## Version
v1 (2026-06): triage-only · weekly via /open-week · direct reports + notable skip-levels. **Requires /signal-setup first** (managers only — no token, no data). Future scope changes (response drafts, twice-weekly cadence, auto-send) are deliberate opt-ins, not defaults.

To run weekly automatically, point your /open-week at it (a one-line step, or a note your assistant reads each Monday) — the host routine doesn't call it on its own.
