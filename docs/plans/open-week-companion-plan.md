# Open Week — Companion Integration Plan

## Principle

Visual handles simple check-off and display, chat handles everything else.

The companion's week tab becomes the surface for reviewing and confirming the stack rank, setting the week mode, and locking in Top 3 priorities. Complex work stays in chat: coaching pattern detection, operating memo alignment, trap checks, Asana sync, learning goal triage, meeting analysis, and the vibes conversation.

---

## What the companion view shows

### Mode: `plan-week` (default when no weekly note exists or note has no confirmed Top 3)

A stepped wizard, similar to coach-morning but for weekly scope:

**Step 1 — Last week in review (read-only)**
- Priorities vs. Reality from last week's close-week (done/partial/missed)
- Key stats: hours worked, meeting hours, Top 3 completion rate
- AI Suggested: Next Week's Top 3 (seeded by close-week Output C)
- AI Suggested: Delegate Next Week
- AI Suggested: Stop Doing
- Source: parsed from `02-weekly/YYYY-[W]WW-1.md`

**Step 2 — Stack rank (interactive)**
- Table: Rank | Project | LOP | Role | Impact | Effort | drag handle
- Drag-to-reorder the Top 5 (or up/down buttons as fallback)
- "Parked this week" list below (read-only, collapsed)
- Each row shows the project name, LOP tag, and role badge
- No inline editing of project metadata -- that stays in Obsidian
- "Effort this week" dropdown per row: S / M / L

**Step 3 — Week mode (interactive)**
- Three cards: Push-to-build / Push-to-close / Protect
- Each shows its constraint text from the skill
- Chat proposes a mode with rationale (shown as a banner at top)
- Builder clicks to confirm or override
- Selected card gets a highlight ring

**Step 4 — Top 3 + Learning (interactive)**
- Same shape as the daily Plan Your Day: suggestion table + 3 input slots
- Suggestions sourced from: AI suggestions (close-week), stack rank Top 3, carry-forwards
- Learning plan summary: deep dive day + micro-learning commitment
- A "Confirm" textarea for any notes/adjustments

**Step 5 — Lock in**
- Summary card: mode, Top 3, stack rank, learning focus
- "Lock in" button transitions to `week-command` mode

### Mode: `week-command` (weekly note exists with confirmed priorities)

Read-only dashboard for the week:

- **Mode badge**: Push-to-build / Push-to-close / Protect with constraint reminder
- **Stack rank table**: read-only, with status column (on-track / needs-attention / stalled -- updated by close-day data)
- **This week's Top 3**: with checkbox toggles (same pattern as daily Top 3)
- **Learning plan**: deep dive day, micro-learning status
- **Meeting load**: total hours vs. target from operating memo
- **Habits this week**: 7-day mini-heatmap per habit (reuses streak data)

### Mode: `week-results` (close-week has run)

Read-only summary:

- Priorities vs. Reality table
- Stack Rank vs. Reality table
- Push/Protect planned vs. actual
- Time allocation table
- Weekly insight reflection (rendered text)
- Quick notes output (copyable block)

---

## What stays in chat

- Data collection (Steps 1a-1f): Asana, calendar, previous weekly notes, knowledge context scan
- Coaching insights (Step 2): pattern detection, cross-week signals, learning stagnation
- Strategy layer: operating memo checks, trap detection, meeting retrospective
- Vibes conversation (Step 1.6): body, family, mental, decisions -- requires real dialogue
- Automation portfolio check (Step 1.55)
- Relationship health check trigger (Step 4.5)
- Coaching goals portfolio display (Step 4.6)
- Asana sync (Step 6): task creation, due date updates
- Monday daily note seeding (Step 7)

---

## Step 0.5 integration

Add a Step 0.5 to `open-week/SKILL.md` matching the close-day pattern:

```
### Step 0.5: Check the visual companion

Same binary resolution as open-day Step 8. Same visual_mode check from builder-profile.md.

If visual_mode is on, companion is running, and this is a current-week plan (not a backfill):

1. Chat runs Steps 1-1.10 (data collection, coaching, strategy) as normal but condenses output.
2. Chat writes the proposed stack rank, mode, and suggestions to a staging area
   the companion can read (the weekly note itself, with a `status: draft` frontmatter flag).
3. Open the companion at /week and tell the builder:
   > "Continue in the browser at <url>/week. Review the stack rank, pick your mode,
   > and lock in your Top 3. Say 'done' when you're ready."
4. Wait for "done". Re-read the weekly note to pick up changes. Continue to Step 6 (Asana sync).
```

**Key difference from daily Step 0.5**: The weekly companion requires chat to do heavy lifting first (data collection, coaching, strategy checks) before handing off. The daily companion can launch immediately because the daily note already exists. For weekly, chat must produce the draft first.

---

## SSE event flow

1. Chat writes `02-weekly/YYYY-WNN.md` with draft content
2. VaultWatcher detects change, calls `broadcast("02-weekly/YYYY-WNN.md")`
3. `base.html` JS needs updating: currently only reloads on `01-daily/` and `30-habits/` paths. Add `02-weekly/` to the SSE reload filter.
4. Builder interacts with companion (reorder stack rank, pick mode, set Top 3)
5. Companion POSTs to new routes, writes back to `02-weekly/YYYY-WNN.md`
6. Broadcast fires, but SSE reload suppression (existing) prevents clobbering the UI the builder just changed

**SSE reload filter change in `base.html`:**
```javascript
// Current:
if (path.startsWith("01-daily/") || path.startsWith("30-habits/")) { reloadMain(); }
// New:
if (path.startsWith("01-daily/") || path.startsWith("30-habits/") || path.startsWith("02-weekly/")) { reloadMain(); }
```

---

## Routes needed

| Route | Method | Purpose |
|-------|--------|---------|
| `/week` | GET | Render week view (already exists -- needs mode detection) |
| `/week/set-rank` | POST | Reorder a project in the stack rank (params: `project`, `new_rank`) |
| `/week/set-effort` | POST | Set effort for a project (params: `project`, `effort`) |
| `/week/set-mode` | POST | Set the week mode (params: `mode`) |
| `/week/set-top-3` | POST | Set a weekly Top 3 item (params: `index`, `text`) |
| `/week/toggle` | POST | Toggle a weekly Top 3 checkbox (params: `index`) |
| `/week/lock-in` | POST | Transition from plan-week to week-command |

All POST routes write to `02-weekly/YYYY-WNN.md` and broadcast.

---

## Template structure

```
templates/
  week.html                          # Router: includes correct mode component
  _components/
    week_plan.html                   # Step wizard (plan-week mode)
    week_plan_stack_rank.html        # Stack rank table partial (for HTMX swaps)
    week_command.html                # Dashboard (week-command mode)
    week_results.html                # Read-only results (week-results mode)
```

`week.html` gets the same mode-switching pattern as `day.html`:
```jinja
{% if mode == 'plan-week' %}
  {% include "_components/week_plan.html" %}
{% elif mode == 'week-results' %}
  {% include "_components/week_results.html" %}
{% else %}
  {% include "_components/week_command.html" %}
{% endif %}
```

---

## Parsers needed

New functions in `companion/parsers.py` or a new `companion/week_parsers.py`:

- `parse_weekly_note_sections(md)` -- extract `##` sections from weekly note
- `parse_stack_rank_table(md)` -- extract the stack rank table into a list of dicts
- `parse_week_mode(md)` -- read the `mode:` frontmatter field
- `parse_week_top_3(md)` -- extract weekly Top 3 items (same shape as daily)

Markdown write-back functions:
- `reorder_stack_rank(md, project, new_rank)` -- move a row in the table
- `set_week_mode(md, mode)` -- update frontmatter
- `set_week_top_3_item(md, index, text)` -- same pattern as daily `_set_nth_item_text`

---

## Mode detection (R1: frontmatter-based)

Use `status` frontmatter as single source of truth, not section-presence heuristics.

```python
def _detect_week_state(weekly_md: str) -> str:
    """Unified mode detection for both open-week and close-week.

    Uses frontmatter `status:` field:
      - draft     → plan-week (chat wrote initial draft, builder reviewing)
      - editing   → plan-week (companion owns the file, chat must not write)
      - confirmed → week-command (open-week completed, locked in)
      - closed    → week-results (close-week completed)

    Query param `?mode=week-review` overrides to close-week check-off,
    UNLESS status is already 'closed' (auto-detect wins for finalized notes).
    """
    fm = parse_weekly_frontmatter(weekly_md)
    status = fm.get("status", "")
    if status == "closed":
        return "week-results"
    if status == "confirmed":
        return "week-command"
    return "plan-week"
```

---

## Write ownership protocol (R3)

Once chat writes `status: draft` and tells the builder to continue in the companion, chat enters a **read-only wait state**. Chat must not write to `02-weekly/YYYY-WNN.md` until the builder says "done" in chat.

1. Chat writes initial draft with `status: draft`
2. Companion's `/week/lock-in` sets `status: editing` (companion now owns the file)
3. Builder interacts (reorder, pick mode, set Top 3)
4. Builder clicks "Lock in" → companion sets `status: confirmed`
5. Chat re-reads the file and proceeds to Step 6 (Asana sync)

---

## Wizard step mechanism (R4)

Alpine-driven with `x-data="{ step: 1 }"` and `x-show="step === N"`. All 5 steps load at once; steps show/hide client-side. No server round-trips between steps. The `data-suppress-sse-reload` attribute (already implemented) prevents SSE from blowing away wizard state.

---

## Route shape change (review feedback)

`/week/set-rank` accepts a full ordered list instead of individual moves:

```
POST /week/set-rank
Body: { "order": ["proj-a", "proj-b", "proj-c", ...] }
```

This is idempotent, race-free, and works for both up/down buttons and future drag-to-reorder.

All POST routes include a `week` hidden form field (e.g., `2026-W22`) so the server knows which file to write to.

---

## Known risks (brittleness issues)

1. **SSE reload (#1)**: RESOLVED. `data-suppress-sse-reload` attribute implemented in base.html. Wizard template adds this attribute.

2. **Date hardcoding (#2)**: RESOLVED. `/week` route now accepts `?week=YYYY-WNN`, and `_target_date()` helper threads date through all routes.

3. **Stale PID detection (#3)**: Same as daily -- auto-start if not running.

4. **zsh glob errors (#4)**: Out of scope (chat-side issue, not companion).

5. **Hook notification (#5)**: Out of scope (chat-side issue, not companion).

6. **Step 0.5 skips silently (#6)**: Wizard shows "No data from last week" in Step 1. Not a blocker.

7. **Checkbox state (#7)**: Acceptable for weekly scope.

9. **Dismissed section (#9)**: Reuse same pattern under `## Week Plan`.

**Stack rank table parser**: Highest-risk component. Write test-first with edge cases: wikilinks in cells, empty cells, pipes in prose, single-row table, no-row table.

**"No weekly note" edge**: If builder navigates to `/week` without running `/open-week`, show current "no note" message. Wizard requires chat-produced draft.

---

## Implementation order

1. Weekly note parsers (frontmatter, sections, stack rank table) — **test-first**
2. `_detect_week_state` function (unified, frontmatter-based)
3. `/week` route enhancement (mode detection, context building)
4. `week_command.html` template (simplest -- read-only dashboard)
5. `week_results.html` template (read-only close-week output)
6. `week_plan.html` template + 5-step Alpine wizard with `data-suppress-sse-reload`
7. POST routes (`/week/set-rank` with full ordered list, `/week/set-mode`, `/week/set-top-3`, `/week/toggle`, `/week/lock-in`)
8. Step 0.5 addition to `open-week/SKILL.md`
9. Stack rank up/down buttons (drag-to-reorder deferred)

Estimated scope: Medium. Most complexity is in the stack rank table parser and reorder logic. The rest follows established patterns.
