# Original CLI Flow — /open-day and /close-day

This is the step-by-step sequence the agent runs in **chat-only mode** — i.e. when the visual companion is off (`open day visual off`, or `visual_mode: off` in `builder-profile.md`). It's the baseline we compare the visual flow against.

When the visual companion is **on**, the same data-collection happens in chat (Steps 1-2), but Steps 3-7 either become silent reads (the agent doesn't print suggestions in chat) or are skipped (the builder makes those decisions in the browser). The agent only re-engages chat at the end with a one-line summary.

---

## /open-day — chat-only flow

| Step | Name | What the agent does |
|------|------|---------------------|
| 1 | Determine today's date | `date +%Y-%m-%d` |
| 1.5 | Auto-close yesterday | If yesterday's daily note has an open Morning Check-in and no Insight Reflection, run /close-day for yesterday first |
| 2 | Collect data (parallel) | Pulls in parallel: Google Calendar events, Asana open tasks (Mine + assigned), overdue Asana, yesterday's carry-over Top 3, learning goals from `40-learning/`, project stack-rank (if exists), open GitHub PRs (yours + waiting on you), and — only if `slt_member: true` — SLT Meeting Actions from Airtable |
| 3 | Draft Morning Check-in | Builds the proposed daily note: AI-suggested Top 3 + Delegate from /close-day (if present), today's meetings, relationship context, Top 3 candidates, overdue, SLT items, PRs, also-on-the-plate, vitality |
| 4 | Builder reviews + adjusts | Agent presents the draft in chat; builder modifies/approves Top 3, Bonus, and schedule |
| 4a | SLT → Asana shadow | If SLT actions were pulled, optionally create shadow Asana tasks with `SLT record: recXXX` lines for /close-day round-trip |
| 5 | Schedule the day | Propose a calendar layout (focus blocks, vitality, meetings); after approval, write events to Google Calendar |
| 6 | Write daily note | Save the approved Morning Check-in to `01-daily/YYYY-MM-DD.md`, with skeleton sections (Work Log, Projects Touched, Carrying Over, End of Day) left empty for /close-day to fill |
| 7 | Track priority alignment | If close-day suggestions existed, classify each user-chosen priority as Adopted / Modified / Replaced and append a row to `03-meta/priority-alignment.md` |
| 8 | Open visual companion | **SKIPPED in CLI-only mode.** Otherwise opens browser. |

End state: today's daily note exists with Morning Check-in populated; calendar events written; agent's chat has presented the day and ended.

---

## /close-day — chat-only flow

| Step | Name | What the agent does |
|------|------|---------------------|
| 0 | Determine the date | Today by default, or accept an explicit date argument |
| 1 | Collect data (parallel) | Pulls: Fathom meeting summaries (today), Asana tasks completed today, Slack messages today, Familiar capture data, GitHub commits/PRs, calendar (what was on it), learning progress signals, SLT actions touched (if applicable) |
| 2 | Identify projects touched | Cluster the day's activity into project buckets using `02-projects/` directory + tag-matching |
| 3 | Draft the daily note | Compose Work Log, Projects Touched, Carrying Over, End of Day sections; surface task-evidence detection (which Top 3 / Asana items are done based on signals) |
| 4 | Present draft | Show the draft in chat with proposed Asana writes (complete / comment / advance status / create) clearly labelled — no writes happen yet |
| 4b | Coaching Check-in | Brief reflection prompt about the day's shape (where energy went, what hit the wall) |
| 4c | Knowledge graph insights | Propose updates to `04-knowledge/` based on what was learned/discussed |
| 5 | Write daily note | Save the approved sections back to today's note |
| 6 | Update project session logs | Append a session summary to each touched project's `_log.md` |
| 7 | Sync Asana | Execute the approved completes / comments / status advances / creates |
| 7d | SLT Meeting Actions sync | If `slt_member: true`, PATCH the SLT base for any actions that closed |
| 8 | Seed tomorrow's daily note | Write `01-daily/{tomorrow}.md` with `### Last Night's AI Suggestions` (Top 3 + Delegate) so /open-day next morning has a head start |
| 9 | Confirm | Brief chat acknowledgement: tasks closed, projects touched, suggestions seeded |

End state: today's note fully written; tomorrow's note seeded with suggestions; Asana / SLT in sync; project logs updated.

---

## Where the visual companion changes things

| Surface | CLI-only mode | Visual companion mode |
|---|---|---|
| Top 3 selection | Agent suggests in chat, builder approves in chat | Daily note's `### My Top 3` rendered as the morning Coach Card's Plan-Your-Day screen; builder checks suggestions or types into the slots; auto-saves on each keystroke |
| Bonus list | Same as above, in chat | Same screen as Top 3, dynamic input field, auto-saves |
| Habit intentions | Agent doesn't ask — habits are daily by default. (Was a separate step pre-2026-05-18; removed.) | Same — no "what habits will you do today?" prompt. Onboarding banner appears in Command Center only when `habits.md` is empty. |
| Vitality intentions | Inline in chat draft | Two disabled inputs in Coach Card (Phase 2 — not yet wired through) |
| Lock-in | None; agent exits after Step 7 | Builder clicks **Lock in** at Step 5 of Coach Card → view transitions to Command Center → builder says "done" in chat → agent prints summary |
| Suggestions surfacing | Agent reads close-day suggestions + carry-overs and prints them in chat with rationale | Coach Card reads them from today's note and renders a 3-column checkbox table (Top 3 / Bonus / Done) |
| Habit ticking during day | Builder edits the daily note manually | Command Center shows habit checkboxes; tap to advance state; writes to `30-habits/log.md` |

The split is meant to keep the *thinking* parts in chat (where the agent's coaching shines) and put the *clicking/typing* parts in the browser (where direct manipulation beats text).
