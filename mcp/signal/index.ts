#!/usr/bin/env -S npx -y tsx
// Signal MCP server — exposes the read-only NSLS Signal API to Claude Code.
//
// Required env:
//   SIGNAL_API_TOKEN  — bearer token minted from /team on the Signal app
//   SIGNAL_API_URL    — base URL (default https://employee-profiles-production.up.railway.app)
//
// Wire into Claude Code:
//   claude mcp add signal \
//     -e SIGNAL_API_TOKEN=signal_xxx \
//     -- npx -y tsx /Users/k/nsls-skills/nsls-personal-toolkit/mcp/signal/index.ts
//
// All tools are read-only and scoped to the token owner's team
// (or all teams if the token belongs to an executive).

import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js'

const API_URL = (process.env.SIGNAL_API_URL ?? 'https://employee-profiles-production.up.railway.app').replace(/\/$/, '')
const TOKEN = process.env.SIGNAL_API_TOKEN
if (!TOKEN) {
  console.error('SIGNAL_API_TOKEN not set — generate one from /team in the Signal app')
  process.exit(1)
}

async function apiGet(path: string): Promise<unknown> {
  const res = await fetch(API_URL + path, {
    headers: { Authorization: `Bearer ${TOKEN}` },
  })
  const text = await res.text()
  if (!res.ok) {
    throw new Error(`Signal API ${res.status} on ${path}: ${text.slice(0, 300)}`)
  }
  return JSON.parse(text)
}

const server = new Server(
  { name: 'signal', version: '0.1.0' },
  { capabilities: { tools: {} } },
)

const TOOLS = [
  {
    name: 'signal_team_summary',
    description:
      'Get the team\'s weekly state: adoption (who submitted vs. not), filtered friction signals with streak counts, and public wins. ' +
      'Same shape as the Monday manager Slack DM. Use for "how is my team doing this week" questions.',
    inputSchema: {
      type: 'object',
      properties: {
        week: {
          type: 'string',
          description: 'Optional YYYY-MM-DD Friday anchor. Default: most recent week with submissions from the team.',
        },
      },
    },
  },
  {
    name: 'signal_friction_signals',
    description:
      'List the team\'s actionable friction quotes (filtered + classifier-clarified) over the last N weeks. ' +
      'Each quote includes the person, sentiment, week, streak count (consecutive weeks of friction), and bracketed clarification if the original quote was orphaned out of context. ' +
      'Use for 1:1 prep, identifying chronic narrators, surfacing patterns.',
    inputSchema: {
      type: 'object',
      properties: {
        weeks: { type: 'number', description: 'Window in weeks (1-12). Default 4.' },
      },
    },
  },
  {
    name: 'signal_wins',
    description:
      'List the team\'s public wins over the last N weeks, including classifier-clarified bracketed context where the win was orphaned. Use for recognition, weekly recap, board-prep.',
    inputSchema: {
      type: 'object',
      properties: {
        weeks: { type: 'number', description: 'Window in weeks (1-12). Default 4.' },
      },
    },
  },
  {
    name: 'signal_person',
    description:
      'Full profile for one person on the team: identity, role, manager link, Work Journal URL, and the last 12 weeks of sentiment + quote history. ' +
      'Manager scope: returns 403 unless the slug is one of your direct reports (or yourself).',
    inputSchema: {
      type: 'object',
      properties: {
        slug: { type: 'string', description: 'The person\'s slug (e.g. "stephanie-repaci").' },
      },
      required: ['slug'],
    },
  },
  {
    name: 'signal_person_history',
    description:
      'Per-week Quick Notes history for one person — raw narration verbatim, structured extraction (wins, work, challenges, growth, sentiment_quotes, quality_score), entry_text rendered for the journal. ' +
      'Use when you need depth: "what did Stephanie actually say in week X?", "how has her language shifted over the quarter?", "are there recurring themes in her challenges?". ' +
      'Manager scope: 403 unless the slug is your direct report or yourself. Window: 1-52 weeks, default 12.',
    inputSchema: {
      type: 'object',
      properties: {
        slug: { type: 'string', description: 'The person\'s slug.' },
        weeks: { type: 'number', description: 'Window in weeks (1-52). Default 12.' },
      },
      required: ['slug'],
    },
  },
  {
    name: 'signal_person_goals',
    description:
      'L2/L3 goal updates for one person over the last N weeks, grouped per goal. Each goal returns goal_name, level (L2/L3), latest_health (GREEN/YELLOW/RED), latest_update_at, latest_update_body, update_count. ' +
      'Use for OKR/goal questions: "how is Trina trending on her Q2 OKR?", "any of my reports off track?", "which goals haven\'t been updated in 2 weeks?". ' +
      'Manager scope: 403 unless the slug is your direct report or yourself. Window: 1-52 weeks, default 12.',
    inputSchema: {
      type: 'object',
      properties: {
        slug: { type: 'string', description: 'The person\'s slug.' },
        weeks: { type: 'number', description: 'Window in weeks (1-52). Default 12.' },
      },
      required: ['slug'],
    },
  },
]

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }))

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params
  const a = (args ?? {}) as Record<string, unknown>
  try {
    let data: unknown
    switch (name) {
      case 'signal_team_summary': {
        const qs = a.week ? `?week=${encodeURIComponent(String(a.week))}` : ''
        data = await apiGet(`/api/mcp/team-summary${qs}`)
        break
      }
      case 'signal_friction_signals': {
        const weeks = typeof a.weeks === 'number' ? a.weeks : 4
        data = await apiGet(`/api/mcp/friction?weeks=${weeks}`)
        break
      }
      case 'signal_wins': {
        const weeks = typeof a.weeks === 'number' ? a.weeks : 4
        data = await apiGet(`/api/mcp/wins?weeks=${weeks}`)
        break
      }
      case 'signal_person': {
        const slug = String(a.slug ?? '').trim()
        if (!slug) throw new Error('slug is required')
        data = await apiGet(`/api/mcp/person/${encodeURIComponent(slug)}`)
        break
      }
      case 'signal_person_history': {
        const slug = String(a.slug ?? '').trim()
        if (!slug) throw new Error('slug is required')
        const weeks = typeof a.weeks === 'number' ? a.weeks : 12
        data = await apiGet(`/api/mcp/person/${encodeURIComponent(slug)}/history?weeks=${weeks}`)
        break
      }
      case 'signal_person_goals': {
        const slug = String(a.slug ?? '').trim()
        if (!slug) throw new Error('slug is required')
        const weeks = typeof a.weeks === 'number' ? a.weeks : 12
        data = await apiGet(`/api/mcp/person/${encodeURIComponent(slug)}/goals?weeks=${weeks}`)
        break
      }
      default:
        throw new Error(`unknown tool: ${name}`)
    }
    return { content: [{ type: 'text', text: JSON.stringify(data, null, 2) }] }
  } catch (e) {
    return {
      content: [{ type: 'text', text: `Error: ${e instanceof Error ? e.message : String(e)}` }],
      isError: true,
    }
  }
})

const transport = new StdioServerTransport()
await server.connect(transport)
