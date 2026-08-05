#!/usr/bin/env python3
"""
session-start.py — SessionStart hook for the NSLS Personal Productivity Toolkit.

Registered in ~/.claude/settings.json by install.sh (see "How Updates Reach a
Builder" in CLAUDE.md for why that, and not a bundled hooks/hooks.json).
Runs on every Claude Code session start:
1. git pull the toolkit to get latest updates (fast-forward only) — skipped with
   --no-pull, which the installer passes because it registers the pull as its own
   bare `git` entry (keeping the update path free of any Python dependency).
2. Report when the toolkit could NOT update, instead of hiding it.
3. Sync skill pointers from the plugin to ~/.claude/skills/ so each skill is
   discoverable by name (and invokable as a slash command).

Must be fast and fail silently — with one deliberate exception: step 2 speaks up.
A silent no-op update is how a builder ends up running months-old skill text
while fixes ship upstream, which is exactly the failure that motivated the
visual-companion self-heal.

NOTE: this script sat in the repo unregistered for a long time — no installer or
manifest referenced it — so on macOS/Linux the toolkit never actually
auto-updated. install.sh's settings.json merge is what wires it in.

Mirrors the builder-toolkit hook. Note what that one does and doesn't cover: its
SYNC_PLUGINS lists both toolkits, so it syncs our pointers, but on macOS/Linux its
git_pull() pulls only its own directory (its PowerShell counterpart pulls both).
So on macOS/Linux nothing fetched this toolkit before this hook was registered.
"""

import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
PLUGIN_DIR = HOME / ".claude" / "local-plugins" / "nsls-personal-toolkit"
SKILLS_DIR = HOME / ".claude" / "skills"

# Sentinel identifying a pointer THIS script generated, used both to write one
# and to decide whether an existing file is ours to overwrite. It must be the
# exact generated sentence.
#
# It used to be a loose path match on "local-plugins/nsls-personal-toolkit",
# which is unsafe: a real skill's body legitimately mentions that path —
# open-day names the companion venv there several times — so a full,
# user-owned skill matched the check and would be replaced by a ~200-byte stub.
# That includes a cloud-synced custom skill, where the full text lives in
# ~/.claude/skills/ rather than being a pointer. Dormant while nothing ran this
# script; live the moment the installer registered it.
POINTER_SENTINEL = (
    "Read and follow the full skill at "
    "`~/.claude/local-plugins/nsls-personal-toolkit/skills/"
)


# A bare block-scalar indicator is not a description. If `description: >-` (or
# `|`) has no indented body, the value is empty — the indicator itself must
# never become the description text.
BLOCK_INDICATORS = (">", ">-", ">+", "|", "|-", "|+")

# One left-to-right pass over a double-quoted scalar's escapes. Single-pass
# matters: chained .replace() calls would decode the output of an earlier
# replacement (\\" would collapse to " and lose its backslash).
_DQ_ESCAPE = re.compile(r"\\x([0-9a-fA-F]{2})|\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})|\\(.)")
_DQ_SIMPLE = {"0": "\0", "a": "\a", "b": "\b", "t": "\t", "n": "\n",
              "v": "\v", "f": "\f", "r": "\r", "e": "\x1b",
              # The four named Unicode escapes YAML defines beyond the C set:
              # next-line, non-breaking space, line separator, paragraph
              # separator. Decoded faithfully; the collapse below folds all four
              # to spaces (\x85 via _CONTROL, the rest because str.split treats
              # them as whitespace), which is what a YAML value folded onto a
              # single line should become.
              "N": "\x85", "_": "\xa0", "L": "\u2028", "P": "\u2029"}

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


def _git(*args, timeout=10):
    """Run a git command in the plugin dir. Returns (ok, stdout) — never raises."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(PLUGIN_DIR), *args],
            capture_output=True, text=True, timeout=timeout
        )
        return proc.returncode == 0, (proc.stdout or "").strip()
    except Exception:
        return False, ""


def git_pull():
    try:
        subprocess.run(
            ["git", "-C", str(PLUGIN_DIR), "pull", "--ff-only", "--quiet"],
            capture_output=True, timeout=10
        )
    except Exception:
        pass


def report_if_stale():
    """Say so when the toolkit can't auto-update, instead of failing silently.

    `git pull --ff-only` refuses on a dirty tree or a diverged branch, and the
    README actively invites builders to edit skills in place — so this is a
    normal state to end up in, not an edge case. It used to be swallowed
    entirely, which meant a builder could sit on a months-old copy of a skill
    with no way to know: fixes shipped upstream and simply never arrived.
    One line on stderr is enough to make that visible and actionable.
    """
    if not (PLUGIN_DIR / ".git").exists():
        return

    dirty_ok, dirty = _git("status", "--porcelain", "--untracked-files=no")
    if dirty_ok and dirty:
        n = len(dirty.splitlines())
        print(
            f"personal-toolkit: auto-update skipped — {n} locally modified "
            f"file(s) in {PLUGIN_DIR}. Commit, stash, or revert them to resume "
            f"updates (git -C '{PLUGIN_DIR}' status).",
            file=sys.stderr,
        )
        return

    # No network here: the installer's pull entry runs before this one and has
    # already updated the remote-tracking ref, so a non-zero "behind" count means
    # the fast-forward itself was refused.
    counts_ok, counts = _git("rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    if not counts_ok or not counts:
        return
    try:
        behind, ahead = (int(x) for x in counts.split())
    except ValueError:
        return

    if behind and ahead:
        print(
            f"personal-toolkit: auto-update blocked — your copy has diverged "
            f"({ahead} local commit(s), {behind} upstream). Rebase or reset "
            f"{PLUGIN_DIR} to resume updates.",
            file=sys.stderr,
        )
    elif behind:
        print(
            f"personal-toolkit: {behind} update(s) available but not applied. "
            f"Run: git -C '{PLUGIN_DIR}' pull --ff-only",
            file=sys.stderr,
        )


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

        # Skip if anything else already owns this slot — a user customization, a
        # builder-toolkit pointer, or a full cloud-synced skill. Only overwrite
        # pointers we generated ourselves.
        if dest.is_dir() and dest_skill.exists():
            try:
                if POINTER_SENTINEL not in dest_skill.read_text():
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
        # Built from POINTER_SENTINEL so generation and detection can never drift.
        dest_skill.write_text(
            f"---\nname: {name}\ndescription: >-\n  {desc}\n---\n\n"
            f"{POINTER_SENTINEL}{skill}/SKILL.md`.\n"
        )
        created += 1

    if created > 0:
        print(f"{created} personal-toolkit skill pointers synced", file=sys.stderr)


def main():
    # The installer registers the pull as its own bare `git` entry (no
    # interpreter needed, so the update path can't be broken by a missing or
    # miswired python) and passes --no-pull here to avoid a second round trip.
    if "--no-pull" not in sys.argv:
        git_pull()
    report_if_stale()
    sync_pointers()


if __name__ == "__main__":
    main()
