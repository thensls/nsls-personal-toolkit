# NSLS Personal Productivity Toolkit

Personal productivity skills for [Claude Code](https://claude.ai/code). Daily planning, end-of-day summaries, weekly reviews, project logging, and relationship tracking.

**This is a starter template.** Fork it, make it yours.

## Install

**Easiest way:** Install the [NSLS Builder Toolkit](https://github.com/thensls/nsls-builder-toolkit) first, then say `/setup` in Claude Code — it offers to install this automatically.

**Standalone install:**

```bash
curl -fsSL https://raw.githubusercontent.com/thensls/nsls-personal-toolkit/main/install.sh | bash
```

Then say `/personal-setup` in Claude Code to connect your accounts.

**From your own fork:**

```bash
NSLS_PERSONAL_REPO=https://github.com/<your-github>/nsls-personal-toolkit.git \
  curl -fsSL https://raw.githubusercontent.com/<your-github>/nsls-personal-toolkit/main/install.sh | bash
```

## Skills

| Skill | Trigger | What it does |
|-------|---------|-------------|
| open-day | `/open-day`, "start my day" | Morning planning — calendar, tasks, priorities |
| close-day | `/close-day`, "close my day" | End-of-day summary — what happened, what's next |
| close-week | `/close-week`, "weekly review" | Friday roll-up — achievements, time allocation, priorities vs reality |
| log | `/log`, "log this session" | Log session progress to Obsidian project notes |
| familiar | "what did I work on" | Recall past screen activity and work context |
| person-intelligence | "person intel [name]" | Build relationship profiles, track 1:1 context |
| obsidian-setup | "set up Obsidian" | Set up an Obsidian knowledge base with templates |

## Customizing

Edit any `skills/<name>/SKILL.md` file. Or tell Claude what you want changed — it edits the file for you.

These skills default to [Obsidian](https://obsidian.md) for notes. Swap it for Google Docs, Notion, or plain files by changing the paths in the skill files.

Some skills optionally use [Familiar](https://familiar.app) for screen recording context. Everything works without it.

## Relationship to NSLS Builder Toolkit

This is separate from the [NSLS Builder Toolkit](https://github.com/thensls/nsls-builder-toolkit) (organization skills). The org toolkit auto-updates and shouldn't be edited. This personal toolkit is yours to change however you want.

## License

MIT
