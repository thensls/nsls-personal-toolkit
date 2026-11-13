---
date: 2026-11-12
slug: delivered-through-claude
last_commit: bf80089ae8317a1c769f237d3b590d48b8629855
skills_changed: [update-personal-productivity]
files_changed: 9
cost_to_adopt: "0 min"
breaking: false
---

# The toolkit can reach you through Claude, with no GitHub

## Why

NSLS's copy of this toolkit is becoming private. Until now every computer fetched its updates
from GitHub without signing in, and that stops working for a private copy: updates would
simply stop arriving, with nothing to say so. NSLS can now deliver the toolkit through Claude
instead.

## What Changed

- **If NSLS delivers the toolkit to you through Claude, your toolkit folder is kept current
  from that copy.** There is nothing to install and nothing to sign in to. Your own settings
  and files in the folder are left alone.
- **If you have edited or removed one of NSLS's files in that folder, updates pause and Claude
  asks** whether to keep yours or take NSLS's. If you take NSLS's, your version is moved to a
  `.set-aside` folder inside the toolkit folder. It is never deleted.
- **`/update-personal-productivity` knows the difference.** On a folder kept current by Claude
  it shows you what's new instead of fetching anything.
- **If you keep your own fork, one thing changes.** Once NSLS's copy is private, catching your
  fork up needs you signed in to GitHub on that computer. The skill now says so plainly
  instead of blaming the network, and offers to switch that computer to the delivered copy if
  you would rather stop keeping a fork there.

## Cost to Adopt

**0 min.** Arrives on its own.

## Safe Merge

The update skill gains a new first step and one new edge case. The session hook and both
installers gain a guard that only acts on a folder kept current by Claude. Your own edits to
these files are kept.

## Opt-Out Guide

- To keep a standard install on GitHub for good, put an empty file named `.keep-on-github` at
  the top of the toolkit folder.
