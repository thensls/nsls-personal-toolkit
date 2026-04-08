---
name: self-insight
description: >-
  Generate a personal operating memo from behavioral evidence — calendar patterns,
  Fathom meeting transcripts, Familiar screen captures, and reflective conversation.
  Reveals how you actually spend time vs. how you think you spend it. Use when the
  user says "self insight", "personal insights", "operating memo", "how do I spend
  my time", "analyze my patterns", "what should I focus on", or during initial
  Obsidian strategy setup. Re-run quarterly to refresh the memo.
---

# Self-Insight

Analyze behavioral data to generate a personal operating memo — a strategic alignment doc that plan-week and plan-day use for coaching and trap detection.

## Philosophy

People are unreliable narrators of their own time. Calendar data, meeting transcripts, and screen captures reveal the truth. This skill synthesizes evidence from multiple sources, surfaces patterns the builder may not see, and facilitates a reflective conversation to turn data into a personal strategy document.

The output is honest, not flattering. If you spend 60% of your time on things you say you don't do, the memo says so.

## When to Run

- During initial Obsidian strategy setup (called by `/plan-week` opt-in flow)
- Quarterly refresh (plan-week nudges when `next-review` date passes)
- Manually when you want to reassess your focus

## Data Sources (in priority order)

| Source | What It Reveals | Access | Universal? |
|--------|----------------|--------|------------|
| **Google Calendar** | Where time goes: meeting load, partners, recurring commitments, deep work gaps | `gcal_list_events` MCP (90 days) | Yes — everyone has this |
| **Fathom transcripts** | How you think: what you advocate for, resist, where you lead vs. follow, coaching themes | Fathom API (90 days) | No — optional |
| **Familiar captures** | Where attention goes: apps, screen time, tool distribution | Bash: scan `$HOME/familiar/stills-markdown/` (7 days) | No — optional |
| **Reflective conversation** | Self-awareness: what you believe about your role, strengths, traps | Direct dialogue | Yes — always |

Use whatever sources are available. Calendar + conversation is the minimum viable input. Each additional source adds depth.

## Step-by-step Execution

### Step 1: Check available data sources

```bash
# Check Fathom — check FATHOM_API_KEY environment variable or .env file
echo "${FATHOM_API_KEY:+FATHOM: available}" || true
[ -z "$FATHOM_API_KEY" ] && grep -q FATHOM_API_KEY .env 2>/dev/null && echo "FATHOM: available (from .env)" || [ -z "$FATHOM_API_KEY" ] && echo "FATHOM: not available"

# Check Familiar
ls $HOME/familiar/stills-markdown/ 2>/dev/null | head -1 && echo "FAMILIAR: available" || echo "FAMILIAR: not available"
```

Google Calendar is always available via MCP.

Tell the user what data sources are available:
> "I can pull from: Google Calendar (90 days), [Fathom transcripts], [Familiar screen captures]. The more sources, the richer the insights. Ready to start?"

### Step 2: Gather evidence (run in parallel)

**2a. Calendar analysis (always)**

```
gcal_list_events(
  timeMin="90 days ago",
  timeMax="today",
  timeZone="America/Denver",
  condenseEventDetails=true,
  maxResults=250
)
```

Analyze:
- **Meeting load:** Total meetings per week (average + trend). Hours/week in meetings.
- **Recurring meetings:** List each recurring meeting, its cadence, and estimated hours/week. Rate each: essential / reduce cadence / candidate for async / drop.
- **Meeting partners:** Who appears most? Group by frequency tier (weekly, biweekly, monthly, one-off). This reveals who depends on you and where you might be a bottleneck.
- **Day-of-week patterns:** Which days are heaviest? Are there consistent deep work days?
- **Deep work windows:** Longest meeting-free blocks. Are they consistent or random?
- **Meeting-free days:** How many in 90 days? What percentage of workdays?
- **Red flags:**
  - Meetings > 50% of work hours = structural problem
  - Friday heavy with meetings = no end-of-week deep work
  - No recurring 1:1 with key reports = management gap
  - Back-to-back days with 5+ meetings = no recovery time

**2b. Fathom analysis (if available)**

```python
# Fetch 90 days of meetings with summaries
# (Use same pattern as close-day Fathom fetch but with 90-day range)
```

Analyze summaries and action items for:
- **Topic frequency:** What words/themes appear most across all meeting summaries? Track: delegate, hire, build, automate, strategy, revenue, support, product, coach, budget, etc.
- **Action item volume:** How many action items per meeting? How many assigned to you? This reveals commitment load.
- **Coaching themes** (if coaching sessions are available): What does the coach keep raising? What patterns get discussed repeatedly?
- **Decision patterns:** In meetings, do you mostly decide, mostly listen, or mostly build consensus? Look for language patterns.
- **The delegation gap:** Compare how often "delegate" appears vs. how often "I'll do it" or "build" appears. This is often the most revealing metric.

**2c. Familiar analysis (if available, last 7 days)**

```bash
# App distribution
grep -h "^app:" $HOME/familiar/stills-markdown/session-*/*.md 2>/dev/null \
  | sort | uniq -c | sort -rn

# Chrome breakdown
awk '/^app: Google Chrome/{f=1} f && /^window_title_raw:/{print; f=0}' \
  $HOME/familiar/stills-markdown/session-*/*.md 2>/dev/null \
  | sort | uniq -c | sort -rn | head -30
```

Analyze:
- **Tool time distribution:** What apps get the most screen time? Slack vs. terminal vs. docs vs. meetings.
- **Building vs. managing ratio:** Terminal/IDE time vs. Slack/email/meeting time.
- **Attention fragmentation:** How often do you switch between deep tools (IDE, docs) and interrupt tools (Slack, email)?
- **Personal time leakage:** Finance sites, news, social media during work hours — not judging, just measuring.

### Step 3: Synthesize insights

Combine all available data into a structured insight report. Present to the user BEFORE writing the operating memo — this is the "here's what the data says" moment.

```markdown
## Personal Insights Report

### How You Actually Spend Your Time

**Calendar says:**
- [X] meetings/week averaging [Y] hours
- Top recurring: [list top 5 with hours]
- Heaviest day: [day] ([N] meetings). Lightest: [day]
- Deep work windows: [description of consistent gaps, if any]
- Meeting partners (weekly+): [names]

**Fathom says:** (if available)
- Your meetings are mostly about: [top 5 topics]
- You generate [N] action items per meeting — [X] assigned to you
- The word "delegate" appeared [N] times in [M] meetings. "Build" appeared [X] times.
- Coaching themes: [top patterns from coaching sessions]

**Familiar says:** (if available)
- Screen time split: [X]% Slack, [Y]% terminal, [Z]% meetings, [W]% other
- Building vs. managing: [ratio]
- You context-switch approximately [N] times per hour

### The Story the Data Tells
[2-3 sentences synthesizing across all sources. Be direct.]
Example: "Your calendar says you're a manager (15h/week in meetings). Your Fathom transcripts say you want to be an architect (top topic: 'build'). Your screen time confirms you're stuck in the middle — 40% Slack, 20% terminal. The word 'delegate' appeared once in 90 days of meetings."

### Patterns to Watch
1. [Pattern] — [evidence] — [implication]
2. [Pattern] — [evidence] — [implication]
3. [Pattern] — [evidence] — [implication]

### Strengths the Data Confirms
1. [Strength] — [evidence]
2. [Strength] — [evidence]

### Meeting Health
- Target recommended: [X]h/week (based on role)
- Current: [Y]h/week
- Recurring meetings to challenge: [list with rationale]
- Meetings that consistently produce decisions: [list]
- Meetings that don't: [list]
```

### Step 4: Reflective conversation

After presenting the data, have a conversation. This is not 5 scripted questions — it's a dialogue guided by what the data revealed.

**Start with the headline:**
> "The data tells an interesting story. [1-2 sentence synthesis]. Does that ring true?"

**Then explore based on what the data showed:**
- If meeting load is high: "You're in [X] meetings/week. Which ones would you drop if you could?"
- If delegation is low: "The word 'delegate' appeared [N] times in 90 days. What's making it hard to hand things off?"
- If building time is high for a leader: "You spent [X]% on building. Is that intentional, or is it your comfort zone pulling you in?"
- If coaching themes repeat: "Your coach keeps raising [theme]. What would it take to actually change this pattern?"

**For users without rich data (no Fathom, no Familiar):**
Ask these questions directly, informed by whatever calendar data exists:
1. Looking at your calendar, what meetings give you energy vs. drain you?
2. What are the 3-5 things only you can do in your role?
3. What keeps pulling you in that someone else should own?
4. What do you measure yourself on this quarter?
5. What's the one thing that would make everything else easier?
6. What patterns do you fall into that you'd like to break?

### Step 5: Generate personal profile

From the deep Fathom analysis + calendar patterns + reflective conversation, generate a personal profile at `$OBSIDIAN_VAULT_PATH/10-strategy/personal-profile.md`. This is the "who you are" companion to the operating memo's "what you do."

**Structure (6 sections, each backed by evidence):**

```markdown
# Personal Profile — [Name]

## How I Work Best
Peak performance patterns: time of day, solo vs collaborative, optimal work structure,
energy rhythm. Sourced from calendar gaps analysis + Familiar screen data + meeting
transcript quality patterns.

## What Energizes Me / What Drains Me
Energy audit: what activities produce energy vs. consume it? Inferred from:
- Meeting topics where summaries are longest and most detailed (energy)
- Topics with vague action items that reappear across meetings (drain)
- What you volunteer for vs. what gets assigned to you
- Calendar patterns: what do you schedule yourself vs. get invited to

## My Top Strengths (with evidence)
3-4 observed strengths, each with:
- What it is (2-3 sentences)
- Specific meeting evidence (dates, what happened)
- "When this is at its best" — the ideal application
- "When this becomes a trap" — the strength overplayed

Inference methods:
- What topics pull you into meetings you weren't invited to
- What questions people bring to YOU specifically
- Moments where group energy shifts after you speak
- What you do in unstructured time (Familiar data)
- Reflected Best Self moments from transcripts

## My Top Traps (strengths overplayed)
2-3 derailers, each with:
- The pattern described plainly
- Specific evidence (meetings, dates, frequency)
- The cost of this pattern (what gets delayed or missed)

Look for: coaching themes that repeat, things you do even when it's not helping,
gaps between stated priorities and actual time allocation.

## What I Actually Value
Inferred from 90 days of meetings:
- What do you consistently push back on? What hills do you die on?
- What do you advocate for when it costs political capital?
- Repeated phrases and themes across meetings
- What you NEVER bring up (the dog that doesn't bark)

## Working Genius Profile (inferred)
Map observable meeting behavior to Lencioni's 6 types:
- Wonder: asks "why" and "what if," reframes problems at higher level
- Invention: generates novel solutions, connects disparate ideas
- Discernment: gut-checks proposals, says "that won't work because..."
- Galvanizing: rallies people, assigns next steps, sets vision
- Enablement: volunteers to help, asks "what do you need?"
- Tenacity: follows up on past items, tracks completion, handles details

Rank as primary / strong / moderate / weaker / weakest based on transcript evidence.
This is directional, not a formal assessment — label it as "inferred from meeting behavior."
```

**For users without Fathom:** The profile is lighter but still useful. Calendar patterns provide "How I Work Best" and partial "Energy" data. The reflective conversation fills "Strengths," "Traps," and "Values." Skip Working Genius without transcript data — it requires behavioral evidence.

### Step 6: Generate operating memo

From the data + conversation, generate the operating memo:

```markdown
---
title: "Operating Memo"
type: reference
updated: YYYY-MM-DD
next-review: [3 months from now]
quarter: [current quarter]
data-sources: [calendar, fathom, familiar, conversation]
---

# Operating Memo — [Quarter Year]

> Updated: YYYY-MM-DD | Next review: YYYY-MM-DD
> Generated by /self-insight from [list data sources used]

## I Do
- [3-5 things, grounded in evidence from Step 3]

## I Don't (aspiration — teach/delegate first, do as backup)
- [3-5 things, grounded in evidence]
- *Reality check: [honest note about current constraints]*

## I Measure
- [3-4 KPIs or outcomes]

## The One Thing
[Single highest-leverage focus for this quarter]

## My Traps
- [2-3 patterns, cited from data]
- [If coaching data exists, cite specific sessions]

## My Meeting Rules
- I attend meetings where I'm [deciding / unblocking / coaching / setting vision]
- My recurring meetings: [list with purpose and cadence]
- Meetings to challenge: [AI-suggested from calendar analysis]
- Target: <= [X] hours/week in meetings, >= [Y] hours/week in focus blocks

## Evidence Base
- Calendar: [X] meetings analyzed over [Y] days
- Fathom: [X] transcripts analyzed, [Y] action items tracked
- Familiar: [X] days of screen captures analyzed
- Key finding: [the single most surprising insight]
```

### Step 7: Write and confirm

Present both the personal profile and operating memo drafts to the user. Iterate until approved.

Write both documents:
- `$OBSIDIAN_VAULT_PATH/10-strategy/personal-profile.md` — who you are (strengths, energy, values, working genius, traps with evidence)
- `$OBSIDIAN_VAULT_PATH/10-strategy/operating-memo.md` — what you do (I Do, I Don't, I Measure, meeting rules, time targets)

The personal profile informs the operating memo. Strengths -> "I Do." Traps -> "My Traps." Energy drains -> "I Don't." The profile is the evidence; the memo is the action plan.

If either document already exists (quarterly refresh), show a diff: "Here's what changed since last quarter" — highlight shifts in strengths application, new traps, patterns that improved, and time allocation changes.

## Edge Cases

- **New employee, no data:** Calendar + conversation only. Memo is lighter but still useful. Will deepen on next quarterly refresh.
- **User disagrees with data:** That's fine and expected. The conversation in Step 4 is where you reconcile self-perception with evidence. The memo reflects your refined view, not raw data.
- **Sensitive findings:** If data shows significant personal time during work hours, high meeting cancellation rates, or patterns that could be embarrassing — present privately and let the user decide what goes in the memo. The memo is your document, not a performance review.
- **Quarterly refresh:** Show trend data. "Last quarter you were at 15h/week meetings, now 12h. Your 'delegate' mentions went from 1 to 7. Progress."
