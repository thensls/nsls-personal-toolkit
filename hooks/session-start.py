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
import time
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

    # stdout, not stderr: SessionStart stdout is what reaches the model's
    # context on every surface. The builder toolkit learned this the hard way
    # and prefixes its notices for the same reason — a warning on stderr can be
    # swallowed by the desktop app, which is how a stale toolkit stays silent.
    def notice(text):
        print(f"[NSLS Personal Toolkit] {text}")

    # --- forks: measured against NSLS, not against their own copy -----------
    # This is the defect that hid a 196-commit gap on a real builder's machine.
    # @{upstream} for a fork is the fork's own main, which they are usually
    # perfectly in sync with — so the checks below reported "healthy" while
    # nothing NSLS shipped had reached them for months. A fork's own remote
    # never receives NSLS changes, so the only honest reference is upstream.
    origin_ok, origin = _git("remote", "get-url", "origin")
    is_canonical = origin_ok and _is_canonical_origin(origin)
    if origin_ok and not is_canonical:
        _report_fork_drift(notice)
        return

    dirty_ok, dirty = _git("status", "--porcelain", "--untracked-files=no")
    if dirty_ok and dirty:
        n = len(dirty.splitlines())
        notice(
            f"Auto-update is paused — this builder has {n} locally modified "
            f"file(s) in the toolkit folder, so updates cannot be applied. "
            f"Mention it in one plain sentence at a natural moment and offer to "
            f"sort it out (save their edits on a side branch, then catch the "
            f"toolkit up). Do NOT hand them a git command — do it for them."
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
        notice(
            f"Auto-update is blocked — this builder's toolkit has diverged "
            f"({ahead} local commit(s), {behind} waiting from NSLS). Say so in "
            f"one plain sentence and offer to catch it up for them (preserve "
            f"their commits on a side branch first). Never hand them a git "
            f"command."
        )
    elif behind:
        notice(
            f"{behind} NSLS update(s) are waiting and were not applied "
            f"automatically. Offer to apply them now — run "
            f"/update-personal-productivity, or bring the checkout current "
            f"yourself if that skill is not present. Do it for them; do not "
            f"hand over a git command."
        )


# How often to ask NSLS whether a fork has fallen behind. The check costs one
# network fetch, so it is throttled rather than run every session, and the stamp
# lives OUTSIDE the repo — a stamp inside it would dirty the tree and trip the
# "locally modified" branch above.
_UPSTREAM_CHECK_EVERY_H = 12
_UPSTREAM_STAMP = HOME / ".claude" / ".nsls-personal-upstream-check"
_UPSTREAM_URL = "https://github.com/thensls/nsls-personal-toolkit.git"
# A remote name WE own, deliberately not "upstream". A fork may already have an
# `upstream` pointing at something else entirely — fetching that and reporting
# its commits as "behind NSLS" would tell Claude to merge a foreign project into
# the builder's toolkit. Clobbering their remote to prevent that would be its own
# small act of vandalism, so we use our own name and leave theirs alone.
_UPSTREAM_REMOTE = "nsls-upstream"

# The NSLS repo itself, in any spelling git accepts. Compared as host + path,
# never as a substring: `mirror.example/thensls/nsls-personal-toolkit` and
# `github.com/thensls/nsls-personal-toolkit-experiments` both CONTAIN the
# canonical path, and a substring test classified either as NSLS's own repo —
# skipping the fork check, so that checkout stayed silently stale.
_CANONICAL_HOST = "github.com"
_CANONICAL_PATH = "thensls/nsls-personal-toolkit"
_URL_FORMS = (
    # scheme://[user[:secret]@]host[:port]/path
    re.compile(r"^[a-z][a-z0-9+.-]*://(?:[^@/]*@)?([^/:]+)(?::\d+)?/(.*)$", re.IGNORECASE),
    # scp-like [user@]host:path — no scheme, and `host://...` is not this form
    re.compile(r"^(?:[^@/:]+@)?([^/:]+):(?!//)/?(.*)$"),
)


def _is_canonical_origin(url):
    """True only for NSLS's own repository on github.com.

    Accepts https, ssh://, and scp-like spellings, optional user info and port,
    `www.`, a trailing slash, `.git`, and any letter case (GitHub owner and repo
    names are case-insensitive). Anything else — another host, another owner,
    a longer repo name, a local path — is not canonical and gets the fork check.
    """
    for form in _URL_FORMS:
        m = form.match((url or "").strip())
        if m:
            host, path = m.group(1).lower(), m.group(2)
            break
    else:
        return False
    if host.startswith("www."):
        host = host[4:]
    path = path.strip("/")
    if path.lower().endswith(".git"):
        path = path[:-4]
    return host == _CANONICAL_HOST and path.rstrip("/").lower() == _CANONICAL_PATH


def _report_fork_drift(notice):
    """Tell the session when a fork has fallen behind NSLS.

    A fork's auto-update pulls the fork, so nothing NSLS ships ever arrives on
    its own — by design, to protect customizations. The failure was never
    telling anyone. Verified 2026-09-09: an active builder's fork sat 196
    commits behind with every check reporting healthy, because every check
    compared against her own fork.
    """
    try:
        if _UPSTREAM_STAMP.exists():
            age_h = (time.time() - _UPSTREAM_STAMP.stat().st_mtime) / 3600
            # 0 <= age: a stamp dated in the FUTURE (clock skew, a restored
            # backup, a synced home directory) yields a negative age, which a
            # bare `<` would read as freshly-checked and could suppress the
            # check for far longer than 12 hours.
            if 0 <= age_h < _UPSTREAM_CHECK_EVERY_H:
                return
    except Exception:
        pass

    remotes_ok, remotes = _git("remote")
    if not remotes_ok:
        return
    if _UPSTREAM_REMOTE in remotes.split():
        # We own this name, so we may enforce its URL — that also repairs a
        # checkout left pointing at a moved or mistyped repo.
        _git("remote", "set-url", _UPSTREAM_REMOTE, _UPSTREAM_URL)
    else:
        _git("remote", "add", _UPSTREAM_REMOTE, _UPSTREAM_URL)

    # Claim the slot BEFORE fetching. The builder toolkit's own session hook
    # runs this same check against this same checkout, keyed on this same stamp,
    # and Claude Code starts SessionStart hooks concurrently — stamping after
    # the fetch left a seconds-wide window in which both would fetch and both
    # would speak. Stamping first shrinks that to the file write itself.
    try:
        _UPSTREAM_STAMP.parent.mkdir(parents=True, exist_ok=True)
        _UPSTREAM_STAMP.touch()
    except Exception:
        pass

    # Bounded and best-effort: offline, blocked, or slow all mean "say nothing
    # this session" — never delay a session start over a nicety.
    fetched, _ = _git("fetch", _UPSTREAM_REMOTE, "main", "--quiet", timeout=6)
    if not fetched:
        return

    ok, count = _git("rev-list", "--count", f"HEAD..{_UPSTREAM_REMOTE}/main")
    if not ok or not count.isdigit():
        return
    behind = int(count)
    if behind == 0:
        return

    # Names OUR remote, never a bare "upstream": on a fork that already has an
    # `upstream` of its own, "merge upstream/main" would be an instruction to
    # merge a stranger's project. And the merged checkout contains the update
    # skill even though the slash command will not exist until the next
    # restart — so point Claude at the file, or the release walk is skipped.
    notice(
        f"This builder's toolkit is their OWN FORK and is {behind} commit(s) "
        f"behind NSLS — nothing shipped upstream has reached them, and their "
        f"auto-update never will, because it follows their fork. Tell them in "
        f"ONE plain sentence at the start of your first reply — e.g. \"Your "
        f"toolkit is your own copy, so NSLS updates haven't been reaching you "
        f"— want me to catch it up?\" — and if they agree: run "
        f"/update-personal-productivity if this machine has it; otherwise merge "
        f"{_UPSTREAM_REMOTE}/main into the checkout at {PLUGIN_DIR} yourself, "
        f"preserving their own commits, then read and follow "
        f"skills/update-personal-productivity/SKILL.md from the freshly merged "
        f"checkout to walk them through what's new (the slash command itself "
        f"appears after their next restart). NEVER hand them a git command."
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
