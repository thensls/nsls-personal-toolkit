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

import os
import re
import signal
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
    """Run a git command in the plugin dir. Returns (ok, stdout) — never raises.

    git runs in its own session so a timeout kills the whole process TREE — a
    fetch's HTTPS remote helper is a child that killing git alone would leave
    running the network operation after we had released the lock."""
    try:
        proc = subprocess.Popen(
            ["git", "-C", str(PLUGIN_DIR), *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
            text=True, start_new_session=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except Exception:
        return False, ""
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode == 0, (out or "").strip()
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.communicate(timeout=2)
        except Exception:
            pass
        return False, ""
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
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
    # Judged by the remote the branch actually PULLS from (falling back to
    # origin): a canonical origin beside a branch that tracks a personal fork is
    # a fork in every way that matters, and a fork whose remote is not called
    # origin is still a fork.
    remote, url = _pull_source()
    is_fork = bool(url) and not _is_canonical_origin(url)
    if is_fork:
        _report_fork_drift(notice)
        # No return here: a fork with uncommitted edits still needs the notice
        # below, or Claude is told to merge over edits nobody mentioned.

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
    if is_fork or not url:
        return  # a fork's own main is not the NSLS line; no remote at all, nothing to say

    # No network here: the installer's pull entry runs before this one and has
    # already updated the remote-tracking ref, so a non-zero "behind" count means
    # the fast-forward itself was refused.
    # <remote>/main, not @{upstream}: the remote this branch pulls from is
    # verified as NSLS's own repo above, so its main IS the NSLS line. @{upstream}
    # follows whatever the BRANCH tracks — a feature branch, say — and would
    # label those commits "waiting from NSLS".
    counts_ok, counts = _git("rev-list", "--left-right", "--count", f"{remote}/main...HEAD")
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
# The stamp is a throttle, not a claim: two hooks can both read it as stale
# before either writes it. The lock is the claim — created exclusively, so
# exactly one of them fetches and speaks. The builder toolkit's own session hook
# runs this same check against this same checkout, keyed on these same files.
_UPSTREAM_LOCK = HOME / ".claude" / ".nsls-personal-upstream-check.lock"
_LOCK_STALE_S = 120  # a lock this old belongs to a hook that died
_UPSTREAM_URL = "https://github.com/thensls/nsls-personal-toolkit.git"
# Where the fetch lands: a private ref, not a remote. A fork may already have an
# `upstream` — or any other name — aimed at something else entirely; fetching
# that reported a stranger's commits as NSLS's, and re-pointing it was found to
# be its own small vandalism. Fetching NSLS by URL into a ref of our own touches
# neither, and gives the notice a stable name to merge. (FETCH_HEAD would do,
# but the installer's concurrent pull can overwrite it mid-check.) The refspec
# names refs/heads/main explicitly so a tag called main cannot stand in.
_UPSTREAM_REF = "refs/nsls/upstream-main"
_UPSTREAM_REFSPEC = f"+refs/heads/main:{_UPSTREAM_REF}"

# The NSLS repo itself, in any spelling git accepts. Compared as host + path,
# never as a substring: `mirror.example/thensls/nsls-personal-toolkit` and
# `github.com/thensls/nsls-personal-toolkit-experiments` both CONTAIN the
# canonical path, and a substring test classified either as NSLS's own repo —
# skipping the fork check, so that checkout stayed silently stale. Schemes are
# an allow-list: `file://github.com/...` need never touch GitHub.
_CANONICAL_HOST = "github.com"
_CANONICAL_PATH = "thensls/nsls-personal-toolkit"
_CANONICAL_SCHEMES = ("https", "http", "ssh", "git", "git+ssh", "ssh+git")
_URL_FORMS = (
    # scheme://[user[:secret]@]host[:port]/path
    re.compile(r"^([a-z][a-z0-9+.-]*)://(?:[^@/]*@)?([^/:]+)(?::\d+)?/(.*)$", re.IGNORECASE),
    # scp-like [user@]host:path — no scheme, and `host://...` is not this form
    re.compile(r"^(?:[^@/:]+@)?([^/:]+):(?!//)/?(.*)$"),
)


def _is_canonical_origin(url):
    """True only for NSLS's own repository on github.com.

    Accepts https, ssh://, and scp-like spellings, optional user info and port,
    `www.`, a trailing slash, `.git`, and any letter case (GitHub owner and repo
    names are case-insensitive). Anything else — another host, another owner,
    a longer repo name, a local path, an unexpected scheme — is not canonical.
    """
    u = (url or "").strip()
    m = _URL_FORMS[0].match(u)
    if m:
        if m.group(1).lower() not in _CANONICAL_SCHEMES:
            return False
        host, path = m.group(2).lower(), m.group(3)
    else:
        m = _URL_FORMS[1].match(u)
        if not m:
            return False
        host, path = m.group(1).lower(), m.group(2)
    if host.startswith("www."):
        host = host[4:]
    path = path.strip("/")
    if path.lower().endswith(".git"):
        path = path[:-4]
    return host == _CANONICAL_HOST and path.rstrip("/").lower() == _CANONICAL_PATH


def _safe_text(value, limit=200):
    """A path for the notice: printable ASCII only, bounded. Everything printed
    here is model context, and a path is text someone else can choose."""
    return re.sub(r"[^\x20-\x7e]", "?", str(value))[:limit]


def _pull_source():
    """(remote, url) this checkout's branch actually pulls from — the same
    source a bare `git pull` uses — falling back to origin. ("", "") when
    neither resolves."""
    # From config, not by splitting `@{u}` on "/": a remote may itself be
    # named with a slash (`personal/fork`), and the split kept only `personal`.
    remote = ""
    ok, branch = _git("symbolic-ref", "--short", "HEAD")  # fails when detached
    seen = set()
    while ok and branch and branch not in seen:
        seen.add(branch)  # stop only on a cycle, not at an arbitrary hop count
        ok, configured = _git("config", "--get", f"branch.{branch}.remote")
        if not ok or not configured:
            break
        if configured != ".":
            remote = configured
            break
        # "." means the branch pulls from a LOCAL branch, not a remote. Follow
        # that chain to the remote it ends at, rather than pretending it is
        # origin — but never give up on the checkout: its remote of record is
        # still the honest fallback, and silence on a fork is the failure here.
        ok, merge = _git("config", "--get", f"branch.{branch}.merge")
        if not ok or not merge.startswith("refs/heads/"):
            break
        branch = merge[len("refs/heads/"):]
    remote = remote or "origin"
    ok, url = _git("remote", "get-url", remote)
    if (not ok or not url) and remote != "origin":
        remote = "origin"
        ok, url = _git("remote", "get-url", remote)
    return (remote, url) if ok and url else ("", "")


def _stamp_is_fresh():
    """Bounded at BOTH ends: a stamp dated in the future (clock skew, a restored
    backup, a synced home directory) yields a negative age, which a bare `<`
    would read as freshly checked and could silence the check for days."""
    try:
        if _UPSTREAM_STAMP.exists():
            age_h = (time.time() - _UPSTREAM_STAMP.stat().st_mtime) / 3600
            return 0 <= age_h < _UPSTREAM_CHECK_EVERY_H
    except OSError:
        pass
    return False


def _claim_lock():
    """Create the lock exclusively and write a token into it; the token (truthy)
    when we hold the lock, None when another hook does.

    A lock whose age is outside 0.._LOCK_STALE_S was left by a hook that died
    (or is dated in the future) and is reclaimed ATOMICALLY: the stale inode is
    renamed away rather than deleted by name. Only one of two racing hooks can
    win that rename; the loser sees ENOENT and simply retries the exclusive
    create, which then fails on the winner's fresh lock. Deleting by name let
    the loser remove the winner's new lock and both proceed."""
    path = _UPSTREAM_LOCK
    token = f"{os.getpid()}-{time.time_ns()}-{os.urandom(4).hex()}"
    for attempt in (1, 2):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, token.encode("ascii"))
            finally:
                os.close(fd)
            return token
        except FileExistsError:
            if attempt != 1:
                return None
            try:
                st = path.stat()
            except FileNotFoundError:
                continue  # vanished under us: retry the create once
            except OSError:
                return None
            # Negative age counts as stale too: a lock dated in the FUTURE
            # (clock skew, a restored backup) would otherwise read as held
            # until that moment arrives, silencing every check until then.
            age_s = time.time() - st.st_mtime
            if 0 <= age_s <= _LOCK_STALE_S:
                return None  # live: someone is mid-check right now
            grave = path.with_name(f"{path.name}.stale-{token}")
            try:
                os.rename(path, grave)
            except FileNotFoundError:
                continue  # the other racer won the rename: retry the create once
            except OSError:
                return None
            try:
                same = grave.stat().st_ino == st.st_ino
            except OSError:
                same = True
            if not same:
                # We moved a LIVE lock created between our look and our rename.
                # Put it back if the name is still free (link is atomic and
                # refuses an existing path), and do not claim.
                try:
                    os.link(str(grave), str(path))
                except OSError:
                    pass
                try:
                    grave.unlink()
                except OSError:
                    pass
                return None
            try:
                grave.unlink()
            except OSError:
                pass
            continue
        except OSError:
            return None
    return None


def _release_lock(token):
    """Delete the lock only if it still carries OUR token. A hook paused past the
    stale threshold (a laptop asleep mid-check) would otherwise delete the lock
    a newer hook created after breaking ours, letting a third one in."""
    try:
        if _UPSTREAM_LOCK.read_text(encoding="ascii", errors="replace") == token:
            _UPSTREAM_LOCK.unlink()
    except OSError:
        pass


def _report_fork_drift(notice):
    """Tell the session when a fork has fallen behind NSLS.

    A fork's auto-update pulls the fork, so nothing NSLS ships ever arrives on
    its own — by design, to protect customizations. The failure was never
    telling anyone. Verified 2026-09-09: an active builder's fork sat 196
    commits behind with every check reporting healthy, because every check
    compared against her own fork.

    Reads and writes no remote: NSLS is fetched by URL into _UPSTREAM_REF. The
    update skill owns the named remote it needs for its longer walk.
    """
    if _stamp_is_fresh():
        return
    lock = _claim_lock()
    if lock is None:
        return  # another hook is mid-check this very second; it will speak
    try:
        if _stamp_is_fresh():
            return  # it finished between our two looks
        try:
            _UPSTREAM_STAMP.parent.mkdir(parents=True, exist_ok=True)
            _UPSTREAM_STAMP.touch()
        except OSError:
            pass

        # Bounded and best-effort: offline, blocked, or slow all mean "say nothing
        # this session" — never delay a session start over a nicety.
        # --no-tags: a plain fetch also auto-follows tags reachable from main,
        # writing NSLS's tags into the builder's checkout — or failing when one
        # collides with a tag of theirs. Only our ref should move.
        fetched, _ = _git("fetch", "--quiet", "--no-tags", _UPSTREAM_URL, _UPSTREAM_REFSPEC, timeout=6)
        if not fetched:
            return
        # A fork shares history with NSLS. A repository that does not — some
        # unrelated project sitting at this path — is not a fork, and telling
        # Claude to merge NSLS's main into it would be an instruction to merge
        # two unrelated histories. Nothing to say about such a checkout.
        related, _ = _git("merge-base", "HEAD", _UPSTREAM_REF)
        if not related:
            return
        ok, count = _git("rev-list", "--count", f"HEAD..{_UPSTREAM_REF}")
        if not ok or not count.isdigit():
            return
        behind = int(count)
        if behind == 0:
            return

        # Names the ref we just fetched and the checkout path, and points Claude
        # at the update skill's file: the merged checkout contains it, but the
        # slash command will not exist until the next restart, and without the
        # file the release walk is skipped.
        notice(
            f"This builder's toolkit is their OWN FORK and is {behind} commit(s) "
            f"behind NSLS — nothing shipped upstream has reached them, and their "
            f"auto-update never will, because it follows their fork. Tell them in "
            f"ONE plain sentence at the start of your first reply — e.g. \"Your "
            f"toolkit is your own copy, so NSLS updates haven't been reaching you "
            f"— want me to catch it up?\" — and if they agree: run "
            f"/update-personal-productivity if this machine has it; otherwise, in "
            f"{_safe_text(PLUGIN_DIR)}, merge {_UPSTREAM_REF} (NSLS's main, fetched "
            f"from {_UPSTREAM_URL} moments ago) yourself, preserving their own "
            f"commits and setting aside any uncommitted edits first, then read and "
            f"follow skills/update-personal-productivity/SKILL.md from the freshly "
            f"merged checkout to walk them through what's new (the slash command "
            f"itself appears after their next restart). NEVER hand them a git "
            f"command."
        )
    finally:
        _release_lock(lock)


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
