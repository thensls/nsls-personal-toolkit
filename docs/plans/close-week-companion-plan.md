# Close Week — Companion Integration Plan

## Principle

Visual handles simple check-off and display, chat handles everything else.

Close-week is primarily a synthesis skill -- it reads a week of daily notes, Familiar data, Asana, and calendar to produce a roll-up. The companion's role is narrower than open-week: check off what was completed, display the results, and provide a copyable quick-notes block. All data collection, synthesis, coaching, and Asana sync stays in chat.

---

## What the companion view shows

### Mode: `week-review` (close-week is running, builder checks off completions)

This is the close-week equivalent of close-day's Step 0.5 -- a check-off surface before synthesis.

**Sections:**

- **This week's Top 3** with checkboxes (done / partial / missed)
  - Each item shows its current status; builder confirms or adjusts
  - "Partial" state matters here (unlike daily) -- a weekly priority may be half-done

- **Stack rank check-off** (if strategy layer active)
  - Each Top 5 project with a status dropdown: on-track / needs-attention / stalled
  - Shows estimated hours spent (from daily notes, if available from chat pre-processing)

- **Habits this week** (read-only summary)
  - 7-day row per habit showing daily completion (dot/check/miss)
  - Weekly completion rate percentage
  - Streak status

- **Brain dump** (optional)
  - Textarea for end-of-week thoughts that chat will route in Step 7e equivalent

### Mode: `week-results` (close-week has completed)

Read-only dashboard showing the final weekly note:

- **Insight Reflection** -- rendered as styled text (same as daily results)
- **Achievements** -- bulleted list
- **Priorities vs. Reality** -- table with done/partial/missed badges
- **Stack Rank vs. Reality** (if strategy layer active) -- table with planned focus vs. actual hours
- **Push/Protect** -- planned vs. actual mode
- **Time Allocation** -- category table with hours and percentages
- **Quick Notes** -- copyable block with a "Copy to clipboard" button
  - This is the primary companion value-add for close-week: the builder copies this directly into their Coach journal without switching to the terminal
- **AI Suggested: Next Week** -- Top 3, Delegate, Stop Doing (read-only, seeded for open-week)

---

## What stays in chat

- Data collection (Step 1): reading daily notes, Familiar time data, Asana completed/overdue
- Synthesis (Step 2): achievements, learnings, project progress, time allocation, insight reflection
- Knowledge graph consolidation (Step 2b)
- Writing the weekly note (Step 3 Output A)
- Generating quick notes format (Step 3 Output B)
- Generating AI suggestions for next week (Step 3 Output C)
- Asana sync (Step 6): creating tasks for stalled projects, bumping carry-forwards
- Presenting the draft and asking for edits (Step 4)

---

## Step 0.5 integration

Add a Step 0.5 to `close-week/SKILL.md`:

```
### Step 0.5: Check the visual companion

Same binary resolution and visual_mode check as close-day Step 0.5.

If visual_mode is on, companion is running, and this is a current-week close (not a backfill):

1. Check if the weekly note exists at `02-weekly/YYYY-WNN.md` and has
   open-week content (Top 3, stack rank). If no weekly note exists,
   skip this step -- there's nothing to check off.
2. Open the companion at /week and tell the builder:
   > "I opened the companion at <url>/week. Before we roll up the week,
   > go mark your Top 3 as done/partial/missed and update your stack rank
   > status. Say 'done' when you're ready."
3. Wait for "done" (same hook-notification guard as close-day).
4. Re-read the weekly note to pick up changes. Proceed to Step 1.
```

**After synthesis (post-Step 3):**

Chat writes the completed weekly note. The companion auto-refreshes via SSE and switches to `week-results` mode. The builder can:
- Read the insight reflection
- Copy the quick notes block
- Review AI suggestions for next week

No second hand-off prompt needed -- the SSE refresh handles it. Chat tells the builder: "Weekly note written. The companion has your quick notes ready to copy."

---

## SSE event flow

Same as open-week -- `02-weekly/` paths trigger main reload.

1. Chat writes `02-weekly/YYYY-WNN.md` (either draft or final)
2. VaultWatcher broadcasts
3. Companion detects mode change (plan-week -> week-command -> week-results) via `_detect_week_state`
4. View auto-updates

**Close-week specific SSE concern**: Chat writes the weekly note in Step 3 (possibly multiple times during draft review). Each write triggers an SSE broadcast. If the builder has the companion open during the draft phase, they'll see intermediate states. This is acceptable -- the content is progressing toward final, not bouncing between states. The existing debounce (800ms) and content-hash dedup prevent rapid flickering.

---

## Routes needed

| Route | Method | Purpose |
|-------|--------|---------|
| `/week` | GET | Already exists -- needs mode detection enhancement |
| `/week/set-priority-status` | POST | Set a weekly Top 3 item status (params: `index`, `status`: done/partial/missed) |
| `/week/set-project-status` | POST | Set a stack rank project status (params: `project`, `status`) |
| `/week/save-section` | POST | Save a text section like brain dump (params: `section`, `content`) |

Most routes from open-week-companion-plan are reused. Close-week adds:
- Priority status needs a 3-state toggle (done/partial/missed) instead of binary checkbox
- Project status dropdown (on-track/needs-attention/stalled)

The `/week/toggle` route from open-week can be extended to handle the 3-state priority status by accepting a `status` parameter alongside the binary toggle.

---

## Template structure

Close-week reuses the templates defined in the open-week plan:

```
templates/
  _components/
    week_review.html                 # Check-off surface for close-week Step 0.5
    week_results.html                # Read-only results (shared with open-week)
    week_quick_notes.html            # Copyable quick-notes block partial
```

The `week_review.html` is new -- it's the close-week equivalent of close-day's Step 0.5 check-off. It shows:
- Top 3 with tri-state toggles (done / partial / missed)
- Stack rank status dropdowns
- Habits week summary (read-only)

`week_results.html` from open-week gains:
- A "Copy quick notes" button that copies Output B to clipboard
- AI suggestions section at the bottom

---

## Mode detection (unified with open-week, R1)

Uses the same frontmatter-based `_detect_week_state` from the open-week plan. No separate function needed.

Close-week Step 0.5 forces `mode=week-review` via query param: `open <url>/week?mode=week-review`. The route handler respects this override UNLESS `status: closed` (meaning close-week already finished — auto-detect wins for finalized notes). This prevents the `?mode=` query param from persisting through SSE reloads after synthesis completes.

```python
# In the /week route handler:
mode_override = request.args.get("mode")
auto_mode = _detect_week_state(week_md)
if mode_override == "week-review" and auto_mode != "week-results":
    mode = "week-review"
else:
    mode = auto_mode
```

When SSE reloads the page (via `htmx.ajax("GET", window.location.href, ...)`), the query param persists. But once chat writes the final note with `status: closed`, the auto-detect returns `week-results` which overrides the query param. The transition is seamless.

---

## Quick Notes copy-to-clipboard

The primary UX win for close-week companion. The quick notes block in `week_results.html`:

```html
<section class="bg-white p-5 rounded shadow">
  <div class="flex justify-between items-center mb-2">
    <h3 class="text-sm uppercase text-stone-500">Quick Notes</h3>
    <button onclick="navigator.clipboard.writeText(document.getElementById('quick-notes').textContent)"
            class="text-xs px-2 py-1 bg-stone-100 rounded hover:bg-stone-200">
      Copy to clipboard
    </button>
  </div>
  <pre id="quick-notes" class="font-mono text-sm whitespace-pre-wrap text-stone-800 bg-stone-50 p-4 rounded">{{ quick_notes_text }}</pre>
</section>
```

Chat must write the quick notes output into a parseable section of the weekly note so the companion can extract it. Proposed: `### Quick Notes` section at the end of the weekly note, containing the plain-text Output B.

---

## Known risks (brittleness issues)

1. **SSE reload blows away Alpine/HTMX UI state after POSTs (#1)**: Less severe for close-week than open-week because the check-off surface (week-review) is simpler -- no step wizard, no drag-to-reorder. Still need to suppress SSE reloads during POST interactions. Guard: skip reload if `[x-data*='weekReview']` is present.

2. **Companion date hardcoded to today (#2)**: Close-week has explicit support for closing past weeks (`/close-week 2026-03-15`). The companion always shows the current week. If closing a past week, Step 0.5 should skip the companion entirely (same pattern as close-day skipping for past dates). The check: if the target Friday != this Friday, skip Step 0.5.

3. **Stale PID detection (#3)**: Same as open-week -- companion may not be running. Same mitigation.

5. **Hook notification treated as user input (#5)**: Close-week Step 0.5 waits for "done". Must use the same guard as close-day: only real user messages trigger continuation, not background hook notifications.

6. **Step 0.5 skips silently when weekly note doesn't exist (#6)**: If no open-week ran (no weekly note), Step 0.5 has nothing to show. Skip silently -- the builder goes straight to chat-based synthesis.

7. **Tri-state priority (R6)**: DECIDED. Use `[/]` for partial status. The habit parser (`parsers.py:124`) already handles `[/]` as 0.5. Extend `_extract_numbered_checkbox_list` to recognize `[/]` as a third state. Add `_set_nth_checkbox_status(md, heading, index, status)` for the explicit set-status route (`/week/set-priority-status`). The daily `/week/toggle` stays binary for `week-command` dashboard checkboxes.

10. **Habit reconciliation untested (#10)**: Close-week shows a 7-day habit summary. This reads from `30-habits/log.md` which is already reconciled daily by close-day. No new reconciliation needed -- just display. But if close-day didn't run some days, the log may have gaps. Display should show gaps as empty/unknown, not as misses.

---

## SKILL.md prerequisite (H5)

close-week/SKILL.md must be updated to write Output B (Quick Notes) into the weekly note as a `### Quick Notes` section at the end, after AI Suggested sections. Currently Output B is only presented in chat. Without this change, the companion has nothing to parse for the copy-to-clipboard feature.

---

## Week boundary decision (R5)

The toolkit week runs **Saturday-Friday** (per close-week SKILL.md). ISO weeks run Monday-Sunday. The habit log is date-keyed. The companion must query Sat-Fri dates for the weekly habit summary, not ISO week dates. Use the toolkit's Sat-Fri convention consistently — ISO `isocalendar()` is only used for the `YYYY-WNN` filename, not for date range queries.

---

## Route clarification (review feedback)

Drop the "extend `/week/toggle`" idea. Use only `/week/set-priority-status` for tri-state priority updates. The binary `/week/toggle` route from open-week stays for `week-command` dashboard checkboxes.

---

## Implementation order

0. **SKILL.md change**: Update close-week to write `### Quick Notes` into the weekly note (prerequisite)
1. Quick notes parser (extract `### Quick Notes` section)
2. `week_results.html` template with copy button (highest standalone value)
3. `week_review.html` template (check-off surface with tri-state toggles)
4. Tri-state priority route (`/week/set-priority-status`) + `_set_nth_checkbox_status` helper
5. Project status dropdown route (`/week/set-project-status`)
6. Step 0.5 addition to `close-week/SKILL.md`
7. Mode detection: `week-review` override respects `status: closed`

Estimated scope: Small-Medium. Most infrastructure (routes, parsers, SSE) is shared with open-week. The unique close-week work is the results template with copy-to-clipboard and the tri-state priority toggle. Coordination risk: the `_detect_week_state` merge with open-week needs design attention during open-week implementation.

---

## Dependency on open-week companion

Close-week companion depends on open-week companion being built first:
- Shared parsers (`parse_weekly_note_sections`, `parse_stack_rank_table`)
- Shared templates (`week_results.html` base)
- Shared routes (`/week` with mode detection)
- Shared SSE filter (`02-weekly/` path)

Build open-week companion first. Close-week companion is additive on top of it.
