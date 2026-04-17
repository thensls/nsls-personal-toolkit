#!/usr/bin/env python3
"""
session-start.py — SessionStart hook for the NSLS Personal Productivity Toolkit.

Runs on every Claude Code session start. Does two things:
1. git pull the personal toolkit fork to get latest updates (fast-forward only)
2. Sync skill pointers from the plugin to ~/.claude/skills/ so each skill is
   discoverable by name (and invokable as a slash command).

Must be fast and fail silently. Mirrors the builder-toolkit hook but scoped
to the personal-toolkit — the builder-toolkit hook only syncs its own skills,
so without this hook, new personal-toolkit skills added via `git pull` never
get registered.
"""

import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
PLUGIN_DIR = HOME / ".claude" / "local-plugins" / "nsls-personal-toolkit"
SKILLS_DIR = HOME / ".claude" / "skills"
MARKER = "local-plugins/nsls-personal-toolkit"


def git_pull():
    try:
        subprocess.run(
            ["git", "-C", str(PLUGIN_DIR), "pull", "--ff-only", "--quiet"],
            capture_output=True, timeout=10
        )
    except Exception:
        pass


def sync_pointers():
    skills_src = PLUGIN_DIR / "skills"
    if not skills_src.is_dir():
        return

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    created = 0

    for skill_dir in sorted(skills_src.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill = skill_dir.name
        src = skill_dir / "SKILL.md"
        if not src.exists():
            continue

        dest = SKILLS_DIR / skill
        dest_skill = dest / "SKILL.md"

        # Skip if a user customization or builder-toolkit pointer already owns this slot.
        # Only overwrite our own pointers (identified by the personal-toolkit marker).
        if dest.is_dir() and dest_skill.exists():
            try:
                if MARKER not in dest_skill.read_text():
                    continue
            except Exception:
                continue

        try:
            content = src.read_text()
        except Exception:
            continue

        name_match = re.search(r"^name:\s*(.+)", content, re.MULTILINE)
        if not name_match:
            continue
        name = name_match.group(1).strip()

        desc = f"NSLS Personal Toolkit skill: {skill}"
        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            ml_match = re.search(r"description:\s*>-?\s*\n((?:\s+.+\n)*)", fm)
            if ml_match:
                desc = " ".join(l.strip() for l in ml_match.group(1).strip().split("\n"))
            else:
                sl_match = re.search(r"description:\s*(.+)", fm, re.MULTILINE)
                if sl_match:
                    desc = sl_match.group(1).strip()

        dest.mkdir(parents=True, exist_ok=True)
        dest_skill.write_text(
            f"---\nname: {name}\ndescription: >-\n  {desc}\n---\n\n"
            f"Read and follow the full skill at "
            f"`~/.claude/local-plugins/nsls-personal-toolkit/skills/{skill}/SKILL.md`.\n"
        )
        created += 1

    if created > 0:
        print(f"{created} personal-toolkit skill pointers synced", file=sys.stderr)


def main():
    git_pull()
    sync_pointers()


if __name__ == "__main__":
    main()
