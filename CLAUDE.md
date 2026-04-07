# Personal Productivity Toolkit

These skills are your personal workflow — edit anything, delete what you don't use, add whatever you want.

This is a fork of Kevin's personal setup. It's one person's answer to "how do I manage my day, week, and notes?" — not a mandate. Take what works, ignore what doesn't.

## First Time?

If you installed this via the Builder Toolkit's `/setup`, your accounts are already connected.

To reconfigure later (change Slack ID, Airtable key, etc.), say `/personal-setup`.

## Skills

| Skill | What it does |
|-------|-------------|
| `/open-day` | Morning planning — calendar, tasks, priorities |
| `/close-day` | End-of-day summary — what happened, what's next |
| `/close-week` | Friday roll-up — weekly achievements and review |
| `/log` | Log session progress to project notes |
| `/familiar` | Recall past screen activity and work context |
| `/person-intelligence` | Build relationship profiles, track 1:1 context |
| `obsidian-setup` | Set up an Obsidian knowledge base |

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
