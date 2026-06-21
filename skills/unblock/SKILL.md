---
name: unblock
description: >-
  Fix the "permission prompt on every edit" trap that hits builders editing the
  toolkit's own files in the VS Code extension. The extension forces a
  confirmation on every write under ~/.claude/ (where the plugin installs), so
  editing your own skills/companion code becomes a wall of prompts. This skill
  sets up a git worktree (or clone + symlink) outside ~/.claude/ so edits land
  on a non-protected path while the plugin still loads normally. Use when you
  see repeated "allow edit?" prompts editing toolkit files, or say "unblock",
  "/unblock", "why does every edit ask permission", "stop the permission
  prompts", "set up a worktree for the toolkit".
---

# Unblock

You're editing the personal toolkit's own files (a skill, the companion, a
template) and **every single edit pops a permission prompt** — even with
permissions set to allow edits. That's not your settings. It's a VS Code
extension guardrail.

## What's actually happening

The Claude Code **VS Code extension** force-confirms every write to any path
under `~/.claude/` — a built-in config-protection guardrail that sits *outside*
the normal permission-mode system, so even `bypassPermissions` / an allow-edit
rule won't silence it (GitHub issues #15921, #66525, #37253).

The toolkit installs to `~/.claude/local-plugins/nsls-personal-toolkit/`. So the
moment you try to edit your own toolkit *in the VS Code extension*, every edit is
under `~/.claude/` and every edit gets gated. The CLI doesn't have this problem;
it's specific to the VS Code extension surface.

**The fix:** do your editing on a copy of the repo that lives *outside*
`~/.claude/`, while the plugin keeps loading from inside `~/.claude/local-plugins/`
as usual. Git makes this clean — same history, same branch or a new one, no
duplication of the actual object store.

## Before you start — confirm the diagnosis

Only proceed if the symptom matches. Check:

1. **Surface is the VS Code extension** (not plain CLI). If they're in the CLI,
   this guardrail doesn't apply — the prompts are coming from something else
   (real permission rules, a hook). Don't set up a worktree they don't need.
2. **The files being edited are under `~/.claude/`.** Run:
   ```bash
   ls -d ~/.claude/local-plugins/nsls-personal-toolkit 2>/dev/null && echo "toolkit is under ~/.claude (the trap applies)"
   ```
3. **The prompts are edit/write confirmations on those files**, repeated, despite
   permissions allowing edits.

If any of those don't hold, stop and ask the user what they're seeing rather than
forcing a worktree.

## The fix: a git worktree outside ~/.claude/

A worktree is the cleanest option — it shares the existing git history (no second
clone, no remote round-trip) and you can put it on its own branch so toolkit
edits don't disturb whatever the installed plugin is checked out at.

```bash
# 1. Find the installed toolkit repo (the git root under ~/.claude).
TOOLKIT=~/.claude/local-plugins/nsls-personal-toolkit
git -C "$TOOLKIT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "Not a git repo at $TOOLKIT — use the clone+symlink fallback below."; exit 1; }

# 2. Pick a destination OUTSIDE ~/.claude (this is the whole point).
DEST=~/dev/nsls-personal-toolkit

# 3. Create a worktree on a new branch so edits are isolated from the
#    installed checkout. (Drop the branch args to track the current branch.)
git -C "$TOOLKIT" worktree add -b toolkit-edits "$DEST"

echo "Edit your toolkit at: $DEST"
echo "The plugin keeps loading from: $TOOLKIT (unchanged)"
```

Now open `~/dev/nsls-personal-toolkit` in the VS Code extension and edit there —
no path is under `~/.claude/`, so no forced prompts. Commit on the worktree's
branch. Because it's the same repo, the installed plugin sees your commits in its
git history; when you want the *running* plugin to pick up a change, either
checkout that commit/branch in the installed checkout or merge it there.

**Note the trade-off (be honest with the user):** a worktree shares history but
is a *separate working copy*. Edits in the worktree do **not** change the files
the plugin runs until you bring them into the installed checkout (merge/checkout
there, or use the symlink approach below if they want edits to be live
immediately). For most builders — who are developing/testing toolkit changes on a
branch before adopting them — the worktree is exactly right.

## Fallback: clone + symlink (edits are live immediately)

If the builder wants their edits to take effect in the running plugin *without* a
merge step, replace the installed directory with a symlink to a clone that lives
outside `~/.claude/`:

```bash
TOOLKIT=~/.claude/local-plugins/nsls-personal-toolkit
DEST=~/dev/nsls-personal-toolkit

# Clone (or move) the repo to a non-protected path.
git clone "$TOOLKIT" "$DEST"            # or: cp -R, or clone from the remote

# Back up the installed dir, then symlink it to the clone.
mv "$TOOLKIT" "$TOOLKIT.bak"
ln -s "$DEST" "$TOOLKIT"

echo "Edit at $DEST; the plugin loads it live via the symlink."
echo "If anything looks wrong, restore: rm $TOOLKIT && mv $TOOLKIT.bak $TOOLKIT"
```

This is the same shape as the recommended **structural install fix** (clone to
`~/dev/`, symlink into `~/.claude/local-plugins/`) so new installs never hit the
trap. Heads-up: the symlink target is still resolved by the editor — if the VS
Code extension follows the symlink and treats the resolved path as under
`~/.claude/`, prefer the worktree. Verify with the builder after setup that edits
in `$DEST` no longer prompt.

## After setup

- Tell the builder the exact path to edit (`$DEST`) and that the plugin still
  loads from `~/.claude/local-plugins/` unchanged.
- Remind them to **commit on the new branch/clone**, not on the installed
  checkout.
- **Don't push, share, or open a PR** — that's the builder's call, per their
  sharing rules.

## What this skill does NOT do

- It does **not** disable the VS Code guardrail (it can't — it's outside the
  permission system). It routes *around* it.
- It does **not** touch the user's vault, connected accounts, or any data.
- It does **not** move the installed plugin without backing it up first.
