# Signal MCP server

Read-only MCP server that exposes the NSLS Signal app's manager data to Claude Code. Same scoping as `/team`: manager sees their own reports, executive sees all.

## Install

1. **Generate a token.** Open https://employee-profiles-production.up.railway.app/team in your browser, scroll to the bottom, and click **Generate MCP token**. Copy the token — it's only shown once.

2. **Register with Claude Code:**
   ```bash
   claude mcp add signal \
     -e SIGNAL_API_TOKEN=signal_your_token_here \
     -- npx -y tsx /Users/$(whoami)/nsls-skills/nsls-personal-toolkit/mcp/signal/index.ts
   ```

   (If your toolkit lives somewhere else, adjust the path.)

3. **Restart Claude Code.** It'll pick up the new MCP server on next session.

## Tools

| Tool | Returns |
|---|---|
| `signal_team_summary(week?)` | Adoption, friction signals with streaks, win count. Same shape as the Monday Slack DM. |
| `signal_friction_signals(weeks?)` | Filtered + classifier-clarified actionable friction quotes over the window. |
| `signal_wins(weeks?)` | Public wins with bracketed-context clarifications. |
| `signal_person(slug)` | Per-person profile + last 12 weeks of sentiment quotes + work journal URL. |

## Usage examples

In a Claude Code session:

> Pull my team summary for last week and tell me what's worth surfacing in 1:1s.

> Who on my team has a friction streak of 3+ weeks right now?

> Get Stephanie's last 8 weeks of sentiment quotes and tell me if her tone has shifted.

> Summarize this quarter's wins on my team grouped by department.

## Rotating the token

If your token leaks or you want to rotate, just click **Generate MCP token** again on `/team`. The old token stops working immediately. Update `SIGNAL_API_TOKEN` in your Claude Code config:

```bash
claude mcp remove signal
claude mcp add signal -e SIGNAL_API_TOKEN=signal_new_token -- npx -y tsx /Users/$(whoami)/nsls-skills/nsls-personal-toolkit/mcp/signal/index.ts
```

## What's NOT here yet (Phase 2)

- Raw narration access (`signal_get_narration`)
- Extraction JSON access (`signal_get_extraction`)
- Work journal content read (`signal_person_journal`)
- The Signal Slack bot's proactive coaching loop

These come in Phase 2 once Phase 1 is in a few managers' hands and we've seen which queries they actually run.
