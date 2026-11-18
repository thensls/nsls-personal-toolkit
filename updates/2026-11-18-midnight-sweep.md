---
date: 2026-11-18
slug: midnight-sweep
skills_changed: [midnight-sweep, open-day, close-day]
files_changed: 11
cost_to_adopt: "1 min"
breaking: false
---

# A midnight sweep makes open-day faster and its suggestions current

## Why

Open-day can be quick or thorough, not both. Checking every suggestion against
every thread takes minutes, so in the morning it skimmed, and finished work and
already-handled asks came back as suggestions. Some builders stopped using
open-day because the wait was too long.

## What Changed

- **A new midnight sweep** runs after each workday while the Claude app is open.
  It checks every suggestion one by one against Slack, meetings, email, the
  calendar, your Claude threads, your own notes and GitHub, and writes the
  result to a file.
- **Open-day starts from that file** and only checks what happened since, so
  the morning is faster and the list is current.
- **Claude checks things for you** instead of suggesting you check them, and
  counts your own words in any thread ("I've recorded it") as done.
- **Coaching starts overnight.** The sweep works it out from the whole day;
  close-day only adds what changed after it.
- **If you didn't close your day,** the sweep estimates your progress on each
  task and shows it in very light blue in the Command Center. Click a level to
  set your own. Say "turn off Claude's estimates" if you'd rather not.

## Cost to Adopt

**1 min.** The next open-day in the Claude desktop app asks once: "Would you
like me to run a midnight sweep, so open-day happens faster?" Say yes or no.

## Safe Merge

New: `skills/midnight-sweep/SKILL.md`. Changed: `skills/open-day/SKILL.md`
(Step 1.5's prompt, new Step 2.0, Step 2n's checks, the coaching paragraph,
new Step 9) and `skills/close-day/SKILL.md` (Step 0.6, new Step 0.7). The
Command Center's light-blue estimates are in `companion/`.
