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


# A bare block-scalar indicator is not a description. If `description: >-` (or
# `|`) has no indented body, the value is empty — the indicator itself must
# never become the description text.
BLOCK_INDICATORS = (">", ">-", ">+", "|", "|-", "|+")

# One left-to-right pass over a double-quoted scalar's escapes. Single-pass
# matters: chained .replace() calls would decode the output of an earlier
# replacement (\\" would collapse to " and lose its backslash).
_DQ_ESCAPE = re.compile(r"\\x([0-9a-fA-F]{2})|\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})|\\(.)")
_DQ_SIMPLE = {"0": "\0", "a": "\a", "b": "\b", "t": "\t", "n": "\n",
              "v": "\v", "f": "\f", "r": "\r", "e": "\x1b"}

# Decoded control characters (NUL, BEL, ESC…) would make the generated pointer's
# frontmatter unparseable, so they're mapped to spaces and folded away by the
# whitespace collapse. \t \n \r are deliberately absent — they're whitespace and
# the collapse already handles them.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _dq_unescape(match):
    for group in (1, 2, 3):
        if match.group(group):
            return chr(int(match.group(group), 16))
    ch = match.group(4)
    # Anything else (\" \\ \/ \space) stands for itself.
    return _DQ_SIMPLE.get(ch, ch)


def unquote_scalar(value):
    """Turn a single-line YAML scalar into the string a YAML parser would give.

    The folded-block branch never sees quotes, but a description written as
    `description: "Brain dump…"` reaches the single-line fallback with its
    delimiters attached, and they end up verbatim in the generated pointer.
    We can't just call a YAML parser here — pyyaml isn't guaranteed on a fresh
    machine, which is why this extraction is hand-rolled in the first place.

    Whitespace is collapsed at the end because the caller embeds the result as
    a single indented line under `description: >-`. A decoded `\\n` left as a
    real newline would break the generated frontmatter, so folding it to a
    space is both safe and what the folded-block branch already does.
    """
    v = value.strip()
    if v in BLOCK_INDICATORS:
        return ""
    quote = v[:1]
    if len(v) >= 2 and v[-1:] == quote and quote in ('"', "'"):
        inner = v[1:-1]
        if quote == '"':
            inner = _DQ_ESCAPE.sub(_dq_unescape, inner)
        else:
            # Single-quoted YAML has exactly one escape: '' is a literal quote.
            inner = inner.replace("''", "'")
        v = inner
    return " ".join(_CONTROL.sub(" ", v).split())


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
            # `*` not `+`: an empty folded block still belongs to the folded
            # branch. With `+` it fell through to the fallback, which then
            # captured the literal `>-` as the description.
            ml_match = re.search(r"description:\s*>-?\s*\n((?:[ \t]+.+\n?)*)", fm)
            if ml_match:
                extracted = " ".join(l.strip() for l in ml_match.group(1).strip().split("\n"))
            else:
                sl_match = re.search(r"description:[ \t]*(.+)", fm, re.MULTILINE)
                extracted = unquote_scalar(sl_match.group(1)) if sl_match else ""
            # Only override the default when we actually recovered text —
            # a blank or `""` description must not produce a blank pointer.
            if extracted.strip():
                desc = extracted

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
