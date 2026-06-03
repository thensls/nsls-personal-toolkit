I'm working on the visual companion for the NSLS personal productivity toolkit. Branch: pp-cli-visual in ~/.claude/local-plugins/nsls-personal-toolkit. The companion is a Flask web app at companion/ that provides a browser UI for open-day/close-day/streaks/habits.

Current state:
- open-day visual companion: working but brittle (SSE reload races, date assumptions, Step 0.5 companion check has edge cases)
- close-day visual companion: Step 0.5 added but not thoroughly tested. Fathom switched to MCP tools. Familiar zsh glob errors fixed.
- open-week / close-week: NOT yet wired to the visual companion
- Draft PR for builder toolkit: thensls/nsls-builder-toolkit#43 (mute skill-event hook, SKILL_EVENT_VERBOSE env var)
- Reset testing skills created: /reset-close-day, /reset-open-day
- 68/68 companion tests passing

Known brittleness issues to feed to reviewers:
1. SSE reload blows away Alpine/HTMX UI state after POSTs (partially fixed with suppression window, but fragile)
2. Companion date hardcoded to today — breaks Step 0.5 for closing past dates
3. Stale PID detection works but the skill can still fail to start the companion
4. zsh glob errors on empty Familiar data (fixed with find, but Claude sessions sometimes improvise alternate paths)
5. Hook notification ("Record skill usage event") treated as user input, causing auto-answer
6. Step 0.5 skips silently when daily note doesn't exist — user doesn't know why companion wasn't offered
7. Checkbox/progress state only persists done/not-done (no intermediate progress in markdown)
8. Add Habit form SSE interaction — adding habits triggers reload that can clobber the form
9. Done/Delete dismissal uses ### Dismissed section which accumulates permanently
10. Habit reconciliation (Step 3.5) untested in real close-day runs

What I need you to do (in order):

**Phase 1 — Plans (sub-agent):**
Write companion integration plans for open-week and close-week. Read the existing open-day/close-day SKILL.md files and the companion code at companion/server.py to understand the pattern. The principle: visual handles simple check-off and display, chat handles everything else. Save plans to docs/plans/.

**Phase 2 — Reviews (4 parallel sub-agents via ce-code-review):**
Run ce-code-review on:
1. open-day SKILL.md + companion code (the implementation)
2. close-day SKILL.md + companion code (the implementation)
3. open-week companion plan (from Phase 1)
4. close-week companion plan (from Phase 1)
Feed each reviewer the 10 known brittleness issues above.

**Phase 3 — Synthesis:**
Merge all review findings. Present a single prioritized action list: what to fix before shipping, what to defer, what to rethink.

Don't implement anything until I've reviewed the plans and the review synthesis. Plan first, review, then implement.
