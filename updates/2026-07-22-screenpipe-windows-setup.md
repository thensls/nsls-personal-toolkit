---
date: 2026-07-22
slug: screenpipe-windows-setup
last_commit: 3a9961b070db5a4ac1412a9a719f9a951c547b2f
commit_range: 6232d64..3a9961b
skills_changed: [screenpipe-windows-setup]
files_changed: 1
cost_to_adopt: "30+ min"
breaking: false
---

# Screenpipe on Windows — setup skill for the PC alternative to Familiar

## Why

The onboarding doc already points PC builders at Screenpipe as the Familiar
alternative, but nothing tells them how to configure it — and Screenpipe's
defaults are wrong on Windows in ways that are invisible.

That matters because three personal skills read screen data: `/familiar`,
the activity reconstruction in `/close-day`, and the screen inputs to
`/self-insight`. On a Mac, Familiar either works or it obviously doesn't. On
Windows, a misconfigured Screenpipe looks *identical to a working one* — the app
runs, the tray icon is green, `/health` returns OK — and the data quietly isn't
there. You find out weeks later, when you go to reconstruct a day or pull a
meeting transcript and there's nothing to pull.

Every failure in this skill was found that way. The defaults that need changing
aren't documented anywhere upstream, and each one costs a day or more to
rediscover:

- **Local Whisper needs an NVIDIA GPU.** On AMD or Intel graphics it appears to
  transcribe and produces nothing. No error, no warning.
- **Bluetooth headset output is never captured.** You record only your own voice
  and don't notice until you read a one-sided transcript.
- **`store.bin` edits silently revert** if the app is running when you edit it.

## What Changed

New skill: `skills/screenpipe-windows-setup/SKILL.md`. Nothing else in the
toolkit is touched — no existing skill changes behavior.

The skill is deliberately *not* an install walkthrough (the installer handles
that). It covers the part the installer doesn't:

### The six silent failures

Each with the diagnostic that catches it and the setting that fixes it —
config reverting on quit, Whisper/CUDA, Bluetooth audio, updates resetting
settings and breaking the Claude Desktop MCP shim, nanosecond timestamps and
cp1252 encoding when reading `db.sqlite` from a script, and retention deleting
history with no warning.

### A known-good settings block

The full working `store.bin` `settings` object, with the two hardware-specific
lines called out so they aren't pasted blind (`audioTranscriptionEngine` depends
on your GPU; `audioDevices` must match your device name exactly, including the
`(input)` suffix).

### A safety block, first section

Three tiers adapted to this domain. Tier 3 covers the three actions that are
irreversible or send data off the machine: choosing a cloud transcription engine,
lowering `localRetentionDays`, and `listenOnLan`.

### A diagnostic loop

Symptom → layer → check, across the five layers data moves through (capture →
write → transcription → retention → access). Written because "is the app
running?" resolves almost nothing here — it nearly always is.

## Cost to Adopt

**30+ min**, and nearly all of it is outside the repo. Pulling the skill is a
`git checkout`. The real cost is the Screenpipe license ($400 lifetime as of
July 2026 — check screenpi.pe for current pricing), the install, merging the
settings block, and a test call to verify audio. Builders who don't want screen
capture at all can ignore this entirely — like `/familiar`, it's fully optional.

## Safe Merge

New skill, no conflicts possible — nothing to merge against:

```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/screenpipe-windows-setup/
git commit -m "pull upstream: screenpipe-windows-setup"
```

## Manual Steps

Only if you actually want screen capture on Windows. Skip all of this otherwise.

- [ ] **Check your GPU before anything else** — `Get-CimInstance Win32_VideoController | Select-Object Name`. No NVIDIA means local Whisper will silently fail and you need a cloud transcription engine. Decide this first; it's the fork in the road.
- [ ] **Clear the data-governance question** if this machine sits in on calls or holds member data. Two separate questions: continuous screen capture at all, and (if you need a cloud engine) meeting audio leaving the machine.
- [ ] **Install Screenpipe** from screenpi.pe, then **quit it fully** before touching config.
- [ ] **Back up and merge the settings block** into `~/.screenpipe/store.bin`. Edits made while the app is running are silently discarded on quit.
- [ ] **Make a two-minute test call** through the audio path you actually use, and confirm the transcript exists *and* contains the other person. This is the only way to catch the two most expensive failures.
- [ ] **Verify frames are landing** with the query in the skill's Verify section before trusting `/close-day` with it.

Nothing degrades if you skip these — the skill is inert until you install
Screenpipe, and every other personal skill behaves exactly as it does today.

## Commits Included

- `3a9961b` — feat(screenpipe-windows-setup): Windows capture setup for the PC alternative to Familiar
