# Ingest Scoping — Slack, Gmail, Fathom

This document spells out exactly what the biweekly person-intelligence sweep
reads when it pulls signal from your communication tools. The privacy posture
is **self-applied surveillance, narrowly scoped**: you're reading your own
messages, you decide what gets used, third parties don't appear in the
synthesized output.

If anything here feels too broad for your comfort, the opt-out switches at the
bottom let you turn off any source independently.

## What gets pulled

For each person the sweep tracks, three sources fire in parallel.

### Fathom — 1:1 transcripts (always on if `FATHOM_API_KEY` is set)

- Meetings since the profile's `last-synthesized` date
- Filtered to 1:1s with this specific person (uses Fathom's
  `calendar_invitees_domains_type=all` + per-person email filter)
- Excludes meeting titles matching common multi-party patterns (all-staff, SLT,
  board, etc.) per `references/meeting-exclusions.json`

### Slack — DMs and shared threads (last 14 days)

- **`mcp__claude_ai_Slack__slack_read_dm`** with the target person's Slack ID
  (looked up from `org-chart.json`)
- **`mcp__claude_ai_Slack__slack_search_public_and_private`** restricted to
  threads where both the operating user and the target are participants
- 14-day rolling window — no historical backfill
- **No keyword searches across the workspace.** The sweep never runs queries
  like "find every message mentioning Adam" — that's noise and it crosses the
  line from coaching context to surveillance.

### Gmail — direct threads (last 14 days)

- **`mcp__claude_ai_Gmail__search_threads`** with `from:{email} OR to:{email}`
  scoped to the last 14 days
- Threads where you're a direct participant (sender or recipient)
- **No keyword sweeps on the person's name** across your full mailbox.

## Three filters applied before content reaches the synthesizer

These run on every Slack message and every Gmail thread, regardless of source:

### 1. Third-party name stripping

If a DM thread between you and Adam mentions Cory by name, **Cory's name is
replaced** with a role descriptor ("another SLT member", "a board member")
before the content reaches the synthesizer. Adam's profile never surfaces
named third parties from your private conversations.

Implementation note: the orchestrator builds a name-replacement map from
`org-chart.json` (other employees' names → role) and applies it to the
ingested content before synthesis.

### 2. Per-user `INGEST_EXCLUDE_THREADS` list

Patterns in your `.env` skip matching content entirely.

**Format** (comma-separated):
- Gmail: subject keyword regexes — e.g., `legal`, `payroll`, `severance`
- Slack: channel ID or name prefixes — e.g., `#hr-`, `#legal-`, `#dms-private`

**Default value** (shipped in `.env.example`):
```
INGEST_EXCLUDE_THREADS=legal,payroll,severance,hr-,#hr-,#legal-
```

Add your own patterns as you encounter content you don't want pulled. The
filter runs before any data reaches the synthesizer — matched threads/channels
are dropped server-side from the MCP response handling, never logged.

### 3. Low-signal filter

These messages don't carry coaching information and just add noise:
- Messages shorter than 20 characters
- Pure emoji or sticker replies
- Routine logistics matching `running late|brb|👍|got it|on my way` patterns

Filter rules live in the script alongside the MCP orchestration. You can
extend them by editing `references/low-signal-patterns.json` (created lazily
the first time you customize).

## Opt-out switches

If you want to disable a source entirely — even when its MCP is connected —
set the env var in `.env`:

| Switch | Effect |
|---|---|
| `SKIP_SLACK_INGEST=1` | No Slack MCP calls. Synthesis runs from Fathom + Gmail only. |
| `SKIP_GMAIL_INGEST=1` | No Gmail MCP calls. Synthesis runs from Fathom + Slack only. |

There's no equivalent `SKIP_FATHOM_INGEST` — Fathom is the foundational source
that the existing skill has always used. To disable Fathom for a specific
person, blank out their email in the Known People Registry; the script
short-circuits when no email is provided.

## What the synthesizer sees per person

Each person's synthesis input gets a `signals` block with the structure:

```json
{
  "fathom_summaries": [{"date": "...", "title": "...", "summary": "..."}],
  "slack_signals": {
    "dm_message_count_14d": 12,
    "thread_count_14d": 3,
    "summary": "Brief AI summary of topics, with third-party names stripped."
  },
  "gmail_signals": {
    "thread_count_14d": 5,
    "summary": "Brief AI summary of topics, with third-party names stripped."
  },
  "sources_unavailable": ["slack"]  // present only when MCPs aren't connected
}
```

The Slack and Gmail blocks **summarize**, not raw-dump. The synthesizer never
sees verbatim DM threads — it sees AI-generated summaries that have already
been third-party-stripped. This is intentional: raw thread text is too
specific and would over-anchor the synthesis on individual exchanges.

## Audit trail

After each sweep, `~/.cache/person-intelligence/last-sweep-status.json`
records which sources were pulled per person, how many items came back, and
how many were filtered. You can grep this file to see exactly what the
system touched without re-running.

```json
{
  "timestamp": "2026-05-17T07:03:12Z",
  "exit_code": 0,
  "per_person": {
    "Adam Stone": {
      "fathom_meetings_pulled": 2,
      "slack_dms_pulled": 14,
      "slack_dms_filtered_low_signal": 6,
      "gmail_threads_pulled": 3,
      "gmail_threads_excluded_by_pattern": 0
    }
  }
}
```

## What this scoping does not protect against

Honest call-out:

- **You see your own messages anyway.** This is not a privacy gate for the
  user — it's a scoping gate for what reaches the synthesizer.
- **Anything you write to Slack or Gmail is already on company infrastructure.**
  This skill doesn't change that surface area.
- **If you share your Obsidian vault**, the synthesized profile content (which
  includes summaries of these signals) goes with it. Treat profiles as
  private intelligence and don't sync them to shared drives.
