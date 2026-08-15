---
name: meet-with
description: Find a meeting time that genuinely works for you and 1–3 colleagues, then book it — checking THEIR real calendars, not guessing. Use when the user says "find a time with X", "book 30 min with X and Y", "put a block on the calendar for me and X", "when are X and Y both free", or "/meet-with". The Calendar connector's suggest_time CANNOT see other people's calendars — this skill exists because of that trap.
---

# meet-with — group scheduling that checks everyone's real calendar

Finds slots that clear **every** attendee's actual busy times, presents numbered options,
and books the winner — with an explicit approval gate before any invite goes out.

## The trap this skill exists to avoid

Verified 2026-08-15 on a machine with the standard claude.ai Google Calendar connector:

- `suggest_time` with colleague attendees **silently treats calendars it cannot read as
  100% free**. It reported a colleague "free 9–5" on a day the Calendar web UI showed
  three meetings. No error, no warning — just a confident wrong answer.
- `list_events` on a colleague's address returns "not found" — **even after subscribing
  to their calendar in the web UI**. The connector's calendar list only carries calendars
  the user owns/writes, not org-shared colleague calendars.
- Google Workspace orgs (NSLS included) DO share availability internally — the web UI's
  **"Meet with… → Search for people"** proves it instantly. The data exists; the
  connector just can't reach it.

**Hard rules:** never present `suggest_time` output as another person's availability.
Never infer "free" from an error or an empty result — an unreadable calendar is
UNKNOWN, not free. Free times come only from a source that demonstrably returned that
person's busy data.

## Step 0: Engine check

Resolve the Calendar connector tools **by suffix** (`list_events`, `create_event`,
`list_calendars`) from this session's live tools — connector UUID prefixes differ per
machine; never hardcode them.

Probe the availability engines, in order of preference:

**Engine A — gws freebusy (preferred: fast, silent, any colleague, no per-person setup).**
```bash
gws auth status 2>/dev/null | grep -q 'googleapis.com/auth/calendar' && echo "ENGINE A: ready" || echo "ENGINE A: gws missing calendar scope"
```
If gws is installed but lacks the scope, tell the user the one-time fix (a browser
consent, ~30 seconds) and fall through to Engine B for this run:

> One-time upgrade for the fast path: run `gws auth login --services docs,drive,calendar`
> and click Allow. (Scope list must be the UNION of what `gws auth status` already shows
> plus `calendar` — per the gws skill, a narrower re-login silently strips scopes other
> skills need. Adjust the `--services` list to include everything already granted.)

**Engine B — browser (works with zero setup when Chrome tools are connected).** Read the
user's own Google Calendar web UI, which renders any org colleague via "Meet with".

**Engine C — manual.** No gws scope, no browser: print the 10-second human recipe
(Google Calendar → left sidebar → "Meet with… → Search for people" → type the name) and
ask the user to read out the busy blocks or pick from slots that clear the calendars you
CAN see. Say plainly whose calendars were actually checked and whose weren't.

Heartbeat: `Step 0: engines — gws:✓|✗ browser:✓|✗ → using A|B|C`

## Step 1: Parse the ask

- **Attendees → emails.** Resolve real addresses (Slack profile search, past calendar
  events, or ask). **Never guess an address from a name pattern** — a typo'd guest gets
  a bounced invite or, worse, a stranger gets invited. If not 100% sure, confirm with
  the user before Step 5. First names alone ("Brandon") are fine only when context makes
  the person unambiguous.
- **Duration** — default 30 minutes.
- **Window** — default: the next 5 business days, 09:00–17:00 in the user's primary
  calendar timezone. Honor anything the user said ("this week", "Monday", "mornings").
- **Extra busy calendars** — if `~/.config/nsls/meet-with-extra-calendars.txt` exists,
  every non-comment line is a calendar id whose busy times count against the USER's
  availability (e.g. a personal/second-business calendar). Include them silently — never
  name these calendars' events in output aimed at other people.

Heartbeat: `Step 1: N attendees (<emails>), M min, window <start>→<end> <tz>, +K extra calendars`

## Step 2: Collect busy intervals

**Engine A (gws):** one freebusy call covers everyone — attendees, the user, and extra
calendars:

```bash
set -o pipefail
gws calendar freebusy query --json '{
  "timeMin": "<window start, ISO with offset>",
  "timeMax": "<window end, ISO with offset>",
  "timeZone": "<tz>",
  "items": [{"id": "<attendee1>"}, {"id": "<attendee2>"}, {"id": "<user>"}, {"id": "<extra1>"}]
}' | grep -v -i keyring
```

> ⚠️ **Per-calendar errors arrive INSIDE the response**, at `calendars.<id>.errors`,
> alongside an empty `busy` list. A naive reader sees `busy: []` and calls that person
> free — recreating the exact suggest_time bug. For every requested id, require either
> a `busy` array **with no `errors` key** or treat that person as UNKNOWN and fall to
> Engine B/C for them. Also check gws's own failure modes (non-zero exit; JSON error
> payload on stdout) per the gws skill.

**Engine B (browser):** open `calendar.google.com/calendar/r/day/<yyyy>/<m>/<d>` in the
user's browser, use "Meet with… → Search for people" to add each attendee, and read
their column per day in the window (zoom on cramped regions; full-detail calendars show
titles, free/busy-only calendars show "busy" blocks — both give exact boundaries).
Record intervals; never screenshot-guess ambiguous edges — zoom until the boundary is
legible. Colleague event details seen this way are for scheduling math only — don't echo
titles into the conversation unless the user asks.

**The user's own busy (all engines):** connector `list_events` on their primary calendar
and each extra calendar. Skip events that don't block: `transparency: transparent`
(marked Free), `status: cancelled`, events the user has RSVP'd **declined**. All-day
out-of-office events DO block.

Heartbeat per person: `Step 2: <email> — N busy blocks (source: gws|browser|user-said)`.
**If any attendee's data came from nowhere** (all engines failed), STOP and say so —
do not proceed on a partial picture while implying it's complete.

## Step 3: Compute the intersection

Deterministic math, not vibes. Write the collected data to
`/tmp/meet-with-ctx/busy.json`:

```json
{"window": {"start": "2026-08-17T00:00:00-04:00", "end": "2026-08-21T23:59:00-04:00",
            "tz": "America/New_York", "duration_min": 30,
            "day_start": "09:00", "day_end": "17:00"},
 "busy": {"dadams@nsls.org": [["2026-08-17T12:00:00-04:00", "2026-08-17T13:00:00-04:00"]],
          "davowood@nsls.org": []}}
```

```bash
python3 - <<'PYEOF'
import json, pathlib
from datetime import datetime, timedelta

cfg = json.loads(pathlib.Path('/tmp/meet-with-ctx/busy.json').read_text())
w = cfg['window']
dur = timedelta(minutes=w['duration_min'])
iso = datetime.fromisoformat

# Merge everyone's busy into one sorted interval list
blocks = sorted((iso(a), iso(b)) for ivs in cfg['busy'].values() for a, b in ivs)
merged = []
for a, b in blocks:
    if merged and a <= merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], b)
    else:
        merged.append([a, b])

def free(s, e):
    return all(e <= a or s >= b for a, b in merged)

start, end = iso(w['start']), iso(w['end'])
dsh, dsm = map(int, w['day_start'].split(':'))
deh, dem = map(int, w['day_end'].split(':'))
slots, day = [], start
while day.date() <= end.date() and len(slots) < 12:
    if day.weekday() < 5:  # business days only
        t = day.replace(hour=dsh, minute=dsm, second=0, microsecond=0)
        day_end = day.replace(hour=deh, minute=dem, second=0, microsecond=0)
        while t + dur <= day_end:
            if t >= start and t + dur <= end and free(t, t + dur):
                tight = any(b == t or a == t + dur for a, b in merged)
                slots.append((t, t + dur, tight))
            t += timedelta(minutes=30)  # candidate starts on :00 / :30
    day += timedelta(days=1)

for i, (s, e, tight) in enumerate(slots[:5], 1):
    flag = "  (tight — back-to-back for someone)" if tight else ""
    print(f"[{i}] {s:%a %b %-d, %-I:%M}–{e:%-I:%M %p}{flag}")
print(f"({len(slots)} viable slots in window)" if slots else
      "NO slot clears everyone — widen the window or drop an attendee.")
PYEOF
```

Heartbeat: `Step 3: N viable slots, presenting top 5`

## Step 4: Present and pick

Numbered list, user picks a number (or asks for a different window — loop back to
Step 2 with the new window). If zero slots, say which attendee is the bottleneck
(most busy-hours in window) and offer the two least-blocked near-misses.

## Step 5: Approval gate, create, verify

Creating a calendar event with guests **emails real invitations to real people**. So:

1. Show the exact manifest first — title, date/time with timezone, duration, every
   guest address, Meet link yes/no, description. Nothing vague.
2. Require an explicit yes **to that manifest** in this run. Content edits reset
   approval. Never add, swap, or "helpfully" include a guest that wasn't approved.
3. Create via the connector's `create_event` (suffix-resolved) with attendees + Google
   Meet. Default description one-liner: `Scheduled via /meet-with.`
4. **Verify by reading it back** — `list_events` over that window must show the new
   event with the right guests. An exit code is not proof. Echo the `htmlLink`.

Heartbeat: `Step 5: created "<title>" <when> — guests <n>, Meet ✓, verified ✓`

## Teach-the-human corner (include when the user seems new to this)

- **See a colleague's day anytime:** Google Calendar → left sidebar → "Meet with… →
  Search for people". Their day renders next to yours. Permanent version: Settings →
  Add calendar → Subscribe to calendar → their email.
- **"Find a time" tab** inside event creation shows all guests side-by-side.
- **A booking page is not a group tool** — it checks only its owner's calendars.
- **Slots only block on events that are "created or accepted" AND marked Busy** —
  invitations nobody accepted, and events marked Free, don't protect a slot.

## Config

`~/.config/nsls/meet-with-extra-calendars.txt` — one calendar id per line, `#` comments.
Each is treated as additional busy time for the user. Absent file = primary calendar only.
