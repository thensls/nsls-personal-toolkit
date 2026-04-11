# Personal Productivity Toolkit

These skills are your personal workflow — edit anything, delete what you don't use, add whatever you want.

This is a fork of Kevin's personal setup. It's one person's answer to "how do I manage my day, week, and notes?" — not a mandate. Take what works, ignore what doesn't.

## First Time?

If you installed this via the Builder Toolkit's `/setup`, your accounts are already connected.

To reconfigure later (change Slack ID, Airtable key, etc.), say `/personal-setup`.

## Skills

| Skill | What it does |
|-------|-------------|
| `/open-day` | Morning planning — calendar, tasks, priorities, schedule focus blocks + vitality time |
| `/plan-week` | Weekly planning — project stack ranking, push/protect mode, strategy alignment |
| `/close-day` | End-of-day summary — what happened, what's next |
| `/close-week` | Friday roll-up — weekly achievements, stack rank review, alignment scoring |
| `/self-insight` | Personal insight — analyzes your calendar, meetings, and behavior to build a personal profile + operating memo |
| `/log` | Log session progress to project notes |
| `/familiar` | Recall past screen activity and work context |
| `/person-intelligence` | Build relationship profiles, track 1:1 context |
| `obsidian-setup` | Set up an Obsidian knowledge base |

## Strategy Layer (Optional)

Your first `/plan-week` will offer to set up a **strategy layer** — a system that connects your daily/weekly planning to company goals and personal strategy:

- **Operating memo** — "I Do / I Don't / My Traps" generated from your behavioral data
- **Personal profile** — your strengths, energy patterns, values, and working genius
- **Project stack ranking** — weekly priority ordering connected to LOPs
- **Push/protect modes** — are you advancing strategy or stabilizing?
- **Meeting coaching** — are you in too many meetings? Which ones should you challenge?

Run `/self-insight` to generate your operating memo and personal profile. Once created, all the daily/weekly skills read from them to provide personalized coaching.

**This is opt-in.** Everything works without it — just less smart.

## Customizing

Edit any `skills/<name>/SKILL.md` file — or just tell Claude what you want changed ("make close-day skip the Slack section") and it will edit the file for you.

Common modifications:
- **Don't use Obsidian?** Change the vault path in `log` and `close-day` to write wherever you keep notes (Google Docs, Notion, plain files)
- **Want a simpler daily close?** Strip out the Familiar and Slack sections from `close-day`
- **Different time tracking?** Modify `close-week` to output your team's format
- **Don't want any of this?** Delete the whole plugin. The org toolkit works independently.

## Keeping Your Fork Updated

If Kevin adds improvements to the template, you can pull them selectively:
```bash
git remote add upstream https://github.com/thensls/nsls-personal-toolkit.git
git fetch upstream
git diff upstream/main -- skills/<skill-name>/SKILL.md  # see what changed
git checkout upstream/main -- skills/<skill-name>/SKILL.md  # pull one skill
```

Or don't. Your fork is yours.
