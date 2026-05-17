# Companion Quickstart

You've installed the companion. Here's how to use it.

## Start it

```bash
toolkit-companion serve
```

This starts the server on `http://localhost:7777` (or the next free port if 7777 is taken) and opens your browser.

## Your first day with both surfaces

1. **Morning:** Open your terminal, run `claude /open-day`. The skill pulls calendar, Asana, etc., and writes today's daily note.
2. Within ~1 second, the companion's browser tab auto-refreshes: you see Top 3, Bonus, Schedule, Habits.
3. Tap checkboxes as you work. Each tap saves immediately to the daily note.
4. Use the CLI for narrative work ("what should I push to tomorrow?", "summarize my morning").
5. **Evening:** `claude /close-day`. The companion's Day tab shows your stats, prompts for Insight Reflection and Gratitude. Type into the textarea or speak via CLI — either saves.

## Streaks

Click the Streaks tab. You see all active habits with a 30-day heatmap each. Add or archive habits with the buttons.

## Stop it

```bash
toolkit-companion stop
```

Or auto-start at login (offered during install). Manage with `launchctl`.

## When something breaks

The CLI is the source of truth. Worst case: stop the companion and use the terminal — everything still works.
