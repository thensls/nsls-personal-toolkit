# Companion v1.0

A local web companion for the toolkit. Browser-based UI on localhost:7777.

## What's new

- Day / Week / Streaks tabs in a browser tab alongside your CLI
- Habits and Streaks engine with concern-counter rule
- Bonus list and Gratitude line additions to daily notes
- Real-time sync between CLI and browser via filesystem watcher + SSE
- Optional auto-start at login (macOS launchd)

## What's not changed

- All existing skills work exactly as before
- All existing hooks (`skill-event` etc.) continue to fire
- The Obsidian vault remains the single source of truth

## Install or upgrade

```bash
cd ~/.claude/local-plugins/nsls-personal-toolkit && git pull
./install.sh
```

When prompted, opt into the companion.
