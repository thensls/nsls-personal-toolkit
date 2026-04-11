---
name: update-personal-productivity
description: >-
  Pull the latest skills from the personal toolkit template repo. Use when you
  see an announcement about new skills, or when you want to check for updates.
  Trigger phrases: update personal productivity, update my skills, pull latest
  skills, grab new skills, check for skill updates.
---

# Update Personal Productivity Skills

Pull the latest skill updates from the upstream template repo into your personal fork.

## Step 1: Check upstream remote

```bash
git -C ~/nsls-skills/nsls-personal-toolkit remote -v
```

If `upstream` isn't configured:
```bash
git -C ~/nsls-skills/nsls-personal-toolkit remote add upstream https://github.com/thensls/nsls-personal-toolkit.git
```

## Step 2: Fetch upstream changes

```bash
git -C ~/nsls-skills/nsls-personal-toolkit fetch upstream
```

## Step 3: Show what changed

```bash
git -C ~/nsls-skills/nsls-personal-toolkit diff HEAD..upstream/main -- skills/ commands/
```

If no changes: "Your skills are up to date. No changes available."

If changes exist, summarize:
- Which skills were added or modified
- What changed in each (1 sentence per skill)

## Step 4: Let the builder choose

> "These updates are available:
> - **[skill name]**: [what changed]
> - **[skill name]**: [what changed]
>
> Pull all of them, or pick specific ones? (You can always revert with git.)"

Options:
- "All" → `git -C ~/nsls-skills/nsls-personal-toolkit checkout upstream/main -- skills/ commands/`
- Specific skills → `git -C ~/nsls-skills/nsls-personal-toolkit checkout upstream/main -- skills/[name]/`

## Step 5: Log the update

Call `POST https://web-production-6281e.up.railway.app/event`:
```json
{
  "builder_email": "<from .env or git config>",
  "event_type": "toolkit_update",
  "points": 0,
  "description": "Updated personal toolkit: [list of skills pulled]"
}
```

## Step 6: Confirm

> "Updated [N] skills. Changes are in your local fork — they'll be active in your next session."
