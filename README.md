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

## Updates

Updates apply themselves: the installer registers a SessionStart hook in
`~/.claude/settings.json` that fast-forwards the toolkit every time you start
Claude Code.

**If you installed before that hook shipped**, catch up once — the hook can only
start working after it's on your machine. Re-running the installer registers it,
or just pull:

```bash
git -C ~/.claude/local-plugins/nsls-personal-toolkit pull --ff-only
```

If you've edited skills in place, commit those changes — a fast-forward can't run
over a dirty tree. The hook now tells you when that's blocking an update instead of
skipping quietly.

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

## Web Companion

A browser-based view onto your toolkit data, running locally at `http://localhost:7777`.

**You don't need to install this separately.** `install.sh` sets it up, and if you
skipped it — or installed the toolkit before the companion existed — the first
`/open-day` builds it for you (~10–30s, once) and opens it. That's the default;
`open day -v` stays in chat for a run, `open day visual off forever` disables it.

To set it up ahead of time, or to repair it:

```bash
bash ~/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh
```

That prints the path to the `toolkit-companion` binary (it lives in a venv, so it
isn't on your PATH). To start it by hand:

```bash
"$(bash ~/.claude/local-plugins/nsls-personal-toolkit/companion/ensure-companion.sh)" serve
```

The companion shows your Day, Week, and Streaks views with tappable checkboxes and a 30-day habit heatmap. It reads and writes the same Obsidian vault your CLI skills do, in real time. The CLI keeps working exactly as before — the companion is purely additive.

See `docs/companion-quickstart.md` for details.

## Customizing

Edit any `skills/<name>/SKILL.md` file. Or tell Claude what you want changed — it edits the file for you.

These skills default to [Obsidian](https://obsidian.md) for notes. Swap it for Google Docs, Notion, or plain files by changing the paths in the skill files.

Some skills optionally use [Familiar](https://familiar.app) for screen recording context. Everything works without it.

## Relationship to NSLS Builder Toolkit

This is separate from the [NSLS Builder Toolkit](https://github.com/thensls/nsls-builder-toolkit) (organization skills). The org toolkit auto-updates and shouldn't be edited. This personal toolkit is yours to change however you want.

## License

MIT
