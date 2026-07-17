---
date: 2026-07-17
slug: harvest-verify-live-allowlist
last_commit: 432bfc2
commit_range: dfe40ab..432bfc2
skills_changed: [harvest-meeting]
files_changed: 4
cost_to_adopt: "2 min"
breaking: false
---

# Harvest: one-command setup check + live SLT allowlist

## Why

If you're on SLT, you can now confirm in one command that `/harvest-meeting` will actually land
in the **shared** company KB — instead of finding out weeks later that it was quietly writing to
a private local copy the whole time. Just say **"verify my harvest setup"** and it tells you the
route and, if something's off, exactly what to fix. And being added as an SLT writer is now
instant: it's a single commit to the KB repo, picked up on your next harvest — no toolkit update.

## What Changed

### `harvest-meeting` — self-serve setup verification + live allowlist

- **"verify my harvest setup"** (and `references/verify-setup.sh`) — a read-only check that runs
  no harvest and reports a clear verdict: `COMPANY KB ✓` (your harvest pushes to the shared repo)
  or `LOCAL KB ⚠` (it won't reach the shared KB), plus the exact fix. It checks the *real* write
  gate: your git identity vs the SLT allowlist, that the KB clone exists, and that you have push
  access. It deliberately does **not** check any `kb-gateway` URL or token — harvest writes via
  `git push`, not through the gateway (the gateway only powers the bot + kb.nsls.org read path).
- **One-command onboarding** (`references/setup.sh`, or say "set up my harvest") — for a new SLT
  writer: clones the KB repo into your vault, sets the clone's commit identity to your @nsls.org
  email (auto-detected), checks whether you're on the allowlist, and runs the verify check.
  Idempotent — existing writers can re-run it as a health check.
- **The SLT allowlist is now read live from the KB repo.** It lives at `_data/kb_authors.txt` in
  `thensls/nsls-knowledge`, and Step 0 reads it from `origin/main` (a fetch + `git show`, working
  tree untouched). Adding a writer is one commit there — everyone picks it up on their next
  harvest. The `kb_authors.txt` shipped in this toolkit is now only an offline / first-run
  fallback and may lag the KB-repo source.

## Cost to Adopt

**2 min** — pull the one skill. No manual steps, no vault changes. (If you're a *new* SLT writer,
ask Kevin to add your `@nsls.org` email to `_data/kb_authors.txt` in the KB repo — that's a
one-commit onboarding step on his side, not something you do to your fork.)

## Safe Merge

**If you haven't customized `harvest-meeting`:**
```bash
cd ~/nsls-skills/nsls-personal-toolkit
git fetch upstream
git checkout upstream/main -- skills/harvest-meeting/SKILL.md \
  skills/harvest-meeting/kb_authors.txt \
  skills/harvest-meeting/references/verify-setup.sh
git commit -m "pull upstream: harvest-verify-live-allowlist"
```

**If you have customized `harvest-meeting`:** see what changed upstream first, then merge by hand:
```bash
git diff HEAD upstream/main -- skills/harvest-meeting/SKILL.md
```
The change is confined to Step 0 (allowlist loading) and the new First-Time Setup / verify
section, plus a new `references/verify-setup.sh`. If you've edited other parts of the skill, they
won't conflict.

## Opt-Out Guide

- It's a single skill (`harvest-meeting`), so it's all-or-nothing within that skill — but the two
  pieces are independent in effect. The verify check is purely additive (a new script + a
  verify-only mode that runs and stops). The live-allowlist read falls back to the shipped copy
  when the KB repo can't be reached, so pulling it changes nothing for anyone who's offline or
  hasn't cloned the KB.
- Non-SLT forks are unaffected either way — you still write to your private local KB.

## Manual Steps

None for existing writers. After pulling:

- [ ] **New SLT writer?** Run `bash skills/harvest-meeting/references/setup.sh` (or say "set up my
      harvest") — it clones the KB repo, sets your identity, and verifies in one go.
- [ ] **Already set up?** Optional sanity check: `bash skills/harvest-meeting/references/verify-setup.sh`
      (or "verify my harvest setup") and confirm it prints `COMPANY KB ✓`.

## Commits Included
- `dfe40ab` — harvest-meeting: self-serve setup verification + live allowlist from KB repo
- `432bfc2` — harvest-meeting: one-command setup.sh for new SLT writers
