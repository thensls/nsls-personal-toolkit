# Companion Quickstart

Here's how to use the companion. You don't need to install it first — `/open-day`
builds it on first use if it isn't there yet.

## Start it

`/open-day` starts it for you. To start it by hand, note the binary lives in a venv
and so is **not on your PATH** — resolve it first:

```bash
TC="$(bash ~/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh)"
"$TC" serve
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
"$TC" stop
```

Or auto-start at login (offered during install). Manage with `launchctl`.

## When something breaks

The CLI is the source of truth. Worst case: stop the companion and use the terminal — everything still works.
