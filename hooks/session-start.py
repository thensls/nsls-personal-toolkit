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

import codecs
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
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


# git reads these ahead of `-C`: with GIT_DIR or GIT_WORK_TREE set, `git -C <toolkit>`
# still works on the repository they name. Claude launched from inside a git hook
# inherits them (git exports GIT_DIR and GIT_INDEX_FILE to its hooks), so every git
# call here would read, fetch into, or fast-forward that repository instead of the
# toolkit. This is git's own list (`git rev-parse --local-env-vars`), the set it
# clears itself when it moves into another repository.
_GIT_REPO_ENV = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT", "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
    "GIT_INTERNAL_SUPER_PREFIX", "GIT_SHALLOW_FILE", "GIT_COMMON_DIR",
)


def _git_env():
    """The environment for every git call aimed at the toolkit checkout."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_REPO_ENV}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _git(*args, timeout=10):
    """Run a git command in the plugin dir. Returns (ok, stdout) — never raises.

    git runs in its own session so a timeout kills the whole process TREE — a
    fetch's HTTPS remote helper is a child that killing git alone would leave
    running the network operation after we had released the lock."""
    timeout = min(timeout, _HOOK_STARTED + _GIT_DONE_BY_S - time.monotonic())
    if timeout <= 0:
        return False, ""   # past this hook's budget: spawn nothing
    try:
        proc = subprocess.Popen(
            ["git", "-C", str(PLUGIN_DIR), *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
            text=True, start_new_session=True,
            env=_git_env(),
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
            capture_output=True, timeout=10, env=_git_env(),
        )
    except Exception:
        pass


# The settings.json pull entry the installers wrote before it cleared the
# variables above, matched whole: `git -C "<toolkit>" pull --ff-only --quiet`.
# Either path spelling (C:\... from install.ps1, /c/... from Git Bash). Anything
# a builder has edited by hand no longer matches and is left alone.
_LEGACY_PULL = re.compile(r'git -C "[^"]*[/\\]nsls-personal-toolkit" pull --ff-only --quiet')
_PULL_UNSET = "unset " + " ".join(_GIT_REPO_ENV) + "; "


def upgrade_pull_hook():
    """Give an existing install the git-variable-proof pull entry.

    The installers now write the pull as `unset <_GIT_REPO_ENV>; git -C ...`,
    but nobody re-runs an installer, so an existing machine keeps the bare
    entry and its hazard until something rewrites it. This hook already runs
    every session, so it does: once, only that exact command, by replacing its
    JSON string in place so every other byte of settings.json stays as it was,
    and only when re-parsing proves nothing else changed. Never raises."""
    path = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (HOME / ".claude")) / "settings.json"
    try:
        real = Path(os.path.realpath(path))   # a dotfiles symlink stays a symlink
        data = real.read_bytes()
        if b"pull --ff-only --quiet" not in data:
            return
        bom = codecs.BOM_UTF8 if data.startswith(codecs.BOM_UTF8) else b""
        raw = data[len(bom):].decode("utf-8")
        cfg = json.loads(raw)
        legacy = set()
        for entry in (cfg.get("hooks") or {}).get("SessionStart") or []:
            for h in (entry.get("hooks") or [] if isinstance(entry, dict) else []):
                cmd = h.get("command") if isinstance(h, dict) else None
                if isinstance(cmd, str) and _LEGACY_PULL.fullmatch(cmd):
                    h["command"] = _PULL_UNSET + cmd
                    legacy.add(cmd)
        if not legacy:
            return
        text = raw
        for cmd in legacy:
            new = json.dumps(_PULL_UNSET + cmd, ensure_ascii=False)
            for old in (json.dumps(cmd), json.dumps(cmd, ensure_ascii=False)):
                text = text.replace(old, new)
        if json.loads(text) != cfg:
            return   # spelled some other way: leave it to the installer
        fd, tmp = tempfile.mkstemp(prefix=".settings.json.", dir=str(real.parent))
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(bom + text.encode("utf-8"))
            os.chmod(tmp, stat.S_IMODE(real.stat().st_mode))
            # Anything that wrote settings.json since we read it (Claude Code,
            # an installer, an editor) wins: drop ours and try next session.
            if real.read_bytes() != data:
                raise OSError("settings.json changed while upgrading")
            os.replace(tmp, str(real))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return
        print("personal-toolkit update hook now ignores git variables from the "
              "calling repository", file=sys.stderr)
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
# before either writes it. The lock is the claim — an OS-level exclusive lock
# on a file that is never deleted, so exactly one of them fetches and speaks.
# The builder toolkit's own session hook runs this same check against this
# same checkout, keyed on these same files.
_UPSTREAM_LOCK = HOME / ".claude" / ".nsls-personal-upstream-check.flock"
# The lock file of the protocol this one replaced (created exclusively, a token
# inside, treated as stale after 120 s). A machine may briefly run one old copy
# of this check beside one new — the builder plugin cache and this checkout
# update on different schedules — so while the OS lock is held this copy ALSO
# claims under that protocol: it creates the old file exclusively and leaves it
# empty (see _shadow_legacy_claim); a fresh, non-empty token there means an old
# hook is mid-check and this one yields. Two files, so
# nothing the old protocol renames or deletes can ever be the inode locked here.
_UPSTREAM_LEGACY_LOCK = HOME / ".claude" / ".nsls-personal-upstream-check.lock"
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


def _lock_exclusive(fd):
    """Non-blocking exclusive lock on an open descriptor: flock where the
    platform has it, the C runtime's byte-range lock on Windows. Raises
    OSError when another process holds it."""
    try:
        import fcntl
    except ImportError:
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _claim_lock():
    """Take an exclusive OS lock on the lock file; the open descriptor when we
    hold it, None when another hook does.

    An OS lock, not create-exclusively/rename/unlink: the kernel owns the
    claim and drops it the instant the holder exits, so a hook that dies
    mid-check leaves nothing to reclaim — no stale threshold, no token, no
    grave — and there is no step at which a third hook can be handed a lock
    that is still in use. The file is never deleted: every hook locks the same
    inode. On a PC the builder toolkit's PowerShell hook opens this same file
    with sharing denied, so whichever of the two opens first holds it and the
    other's open simply fails."""
    path = _UPSTREAM_LOCK
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0), 0o644)
    except OSError:
        return None  # includes a Windows sharing violation: the PowerShell hook holds it
    try:
        _lock_exclusive(fd)
    except (OSError, ImportError):
        _release_lock(fd)
        return None
    if not _shadow_legacy_claim(_UPSTREAM_LEGACY_LOCK):
        _release_lock(fd)
        return None  # an old copy of this check is mid-check right now; it will speak
    return fd


def _legacy_lock_is_live(path):
    """True while a hook still on the previous lock protocol is mid-check: its
    token file exists, is NON-EMPTY, and is under 120 s old (its own stale
    threshold). Older or future-dated means a dead hook left it. Empty means a
    hook on THIS protocol left its shadow claim (below) — never a live old hook,
    whose token is always written."""
    try:
        st = path.stat()
    except OSError:
        return False
    return st.st_size > 0 and 0 <= time.time() - st.st_mtime <= 120


def _shadow_legacy_claim(path):
    """Also claim under the previous protocol while the OS lock is held, so a
    hook still on the old code sees a live lock and yields — the one atomic
    handshake the two protocols share is the old one's own exclusive create.
    Only ever called while holding the OS lock, so no two hooks on this protocol
    touch the file at once; the only other actor is an old hook, and the old
    rules apply to it: a file under 120 s old is someone mid-check.

    False when an old hook is mid-check right now (yield). True when the shadow
    is ours, or the file cannot be written at all (then the stamp, re-checked
    under the lock, is what arbitrates). The shadow is left EMPTY and never
    deleted by us: old tokens are never empty, so a later hook on this protocol
    does not mistake our own leftover for a live old hook, and an old hook's
    own release only ever deletes a file that still carries its token."""
    for attempt in (1, 2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            if _legacy_lock_is_live(path):
                return False
            if attempt == 2:
                return True
            try:
                path.unlink()  # a dead old hook's token, or our own empty shadow from last time
            except OSError:
                return True
            continue
        except OSError:
            return True
        os.close(fd)
        return True
    return True


def _release_lock(fd):
    """Closing the descriptor drops the lock; the file itself stays."""
    try:
        os.close(fd)
    except OSError:
        pass


# The catch-up for a fork with nothing of its own is a local write. It is only
# begun early, and it is never killed: git stopped half-way through a checkout
# leaves a half-updated folder and a stale index.lock. Both limits are measured
# from the start of this hook, which the installer gives 20 seconds in all with
# sync_pointers still to run after this check: the write is not begun after
# _FF_LATEST_START_S, and session start stops waiting for it at _FF_DONE_BY_S.
# One still running then is left to finish on its own and reported as such. And
# every git call in this hook ends by _GIT_DONE_BY_S, whatever timeout it asked
# for, so a wedged checkout cannot run the hook past its 20 seconds. Same rules as
# the builder toolkit's copy.
_HOOK_STARTED = time.monotonic()
_FF_LATEST_START_S = 8
_FF_DONE_BY_S = 12
_GIT_DONE_BY_S = 16
# git's markers for an operation in progress: mid-bisect, -rebase, -am or -revert a
# checkout can look clean and sit on main, and moving main changes that operation.
_OP_STATE = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_START",
             "BISECT_LOG", "rebase-merge", "rebase-apply", "sequencer")
# The status that counts everything: untracked files even where
# status.showUntrackedFiles=no hides them, and submodules even where configured away.
_STATUS_ARGS = ("status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none")


def _git_path_exists(rel):
    # rev-parse --git-path answers relative to the checkout, or absolute.
    return bool(rel) and (PLUGIN_DIR / rel).exists()


def _clean_to_fast_forward():
    """Every condition under which a fast-forward can only add NSLS's commits.

    On the branch `main`; no operation in progress; no submodules and no sparse
    checkout, neither proven here; no commits NSLS lacks; nothing unsaved,
    untracked, or in a submodule.
    """
    ok, branch = _git("symbolic-ref", "--short", "-q", "HEAD")
    if not ok or branch != "main":
        return False
    ok, paths = _git("rev-parse", *[a for name in _OP_STATE for a in ("--git-path", name)])
    if not ok or any(_git_path_exists(rel) for rel in paths.splitlines()):
        return False
    if (PLUGIN_DIR / ".gitmodules").exists():
        return False
    _, sparse = _git("config", "--bool", "--get", "core.sparseCheckout")
    if sparse == "true":
        return False
    ok, ahead = _git("rev-list", "--count", f"{_UPSTREAM_REF}..HEAD")
    if not ok or ahead != "0":
        return False
    ok, dirty = _git(*_STATUS_ARGS)
    return ok and not dirty


def _ff_merge(wait):
    """The fast-forward itself: its exit code, or None if still running. Never killed.

    Runs in its own session with its output discarded, so it can outlive this
    hook. Switched off for this one call: branch.main.mergeOptions (with
    --no-squash and --no-autostash stated outright), hooks (via a hooks directory
    that does not exist; a post-merge hook runs after the branch has moved and
    can hang), background maintenance and auto-gc, and overwriting an ignored file.
    """
    no_hooks = PLUGIN_DIR / ".git" / "nsls-no-hooks"   # deliberately never created
    try:
        proc = subprocess.Popen(
            ["git", "-C", str(PLUGIN_DIR),
             "-c", f"core.hooksPath={no_hooks.as_posix()}", "-c", "maintenance.auto=false",
             "-c", "gc.auto=0", "-c", "branch.main.mergeOptions=",
             "merge", "--ff-only", "--no-squash", "--no-autostash",
             "--no-overwrite-ignore", "--quiet", _UPSTREAM_REF],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, env=_git_env(),
        )
    except Exception:
        return -1
    try:
        return proc.wait(timeout=wait)
    except subprocess.TimeoutExpired:
        return None


def _checkout_state(head_before, target):
    """'caught_up', 'untouched' or 'broken', read fresh after the attempt."""
    ok_h, head = _git("rev-parse", "HEAD", timeout=5)
    ok_s, dirty = _git(*_STATUS_ARGS, timeout=10)
    ok_l, lock = _git("rev-parse", "--git-path", "index.lock", timeout=5)
    # Still on main: a checkout moved to another branch between the checks and the
    # merge would have had THAT branch moved. Reported for a look, never caught up.
    ok_b, branch = _git("symbolic-ref", "-q", "HEAD", timeout=5)
    if not (ok_h and ok_s and ok_l) or dirty or _git_path_exists(lock):
        return "broken"
    if not ok_b or branch != "refs/heads/main":
        return "broken"
    if head == target:
        return "caught_up"
    if head == head_before:
        return "untouched"
    return "broken"


def _fast_forward_clean_fork():
    """'caught_up'; 'untouched' (conditions not met, too late, or git refused
    cleanly: the builder gets the offer); 'unfinished'; or 'broken'."""
    if not _clean_to_fast_forward():
        return "untouched"
    ok_b, before = _git("rev-parse", "HEAD")
    ok_t, target = _git("rev-parse", _UPSTREAM_REF)
    if not (ok_b and ok_t):
        return "untouched"
    elapsed = time.monotonic() - _HOOK_STARTED
    if elapsed > _FF_LATEST_START_S:
        return "untouched"   # a write we might abandon is a write we do not begin
    if _ff_merge(_FF_DONE_BY_S - elapsed) is None:
        return "unfinished"
    return _checkout_state(before, target)


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

        # Nothing of theirs in the way: catch it up and say so once. Anything of
        # theirs in the way keeps the offer below, because only they can decide
        # what happens to it.
        outcome = _fast_forward_clean_fork()
        if outcome in ("unfinished", "broken"):
            notice(
                f"An automatic catch-up of this builder's toolkit (their own fork, "
                f"{behind} commit(s) behind NSLS) did not finish cleanly, so the folder "
                f"at {_safe_text(PLUGIN_DIR)} may be part-way through an update. Nothing "
                f"of theirs was at risk: it only starts on a clean checkout with no "
                f"commits of their own. Tell them in ONE plain sentence at the start of "
                f"your first reply that their toolkit needs a quick look, and offer to "
                f"sort it out. If they agree, inspect before changing anything — whether "
                f"a git process is still running, whether .git/index.lock exists, git "
                f"status, and where HEAD sits relative to {_UPSTREAM_REF} — then finish "
                f"the fast-forward or put it back. NEVER hand them a git command."
            )
            return
        if outcome == "caught_up":
            notice(
                f"This builder's toolkit was their OWN FORK, {behind} commit(s) behind "
                f"NSLS, with no commits or unsaved edits of their own, so it has just "
                f"been caught up with NSLS automatically. Tell them in ONE plain "
                f"sentence at the start of your first reply — e.g. \"Your toolkit was "
                f"your own copy, so NSLS updates hadn't been reaching you; I've caught "
                f"it up.\" — then offer to show them what's new: read and follow "
                f"skills/update-personal-productivity/SKILL.md in {_safe_text(PLUGIN_DIR)} "
                f"(the slash command itself appears after their next restart). NEVER "
                f"hand them a git command."
            )
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
    # First: it is quick and contained, and a slow or failing step below must
    # not keep a machine on the unsafe pull entry.
    upgrade_pull_hook()
    if "--no-pull" not in sys.argv:
        git_pull()
    report_if_stale()
    sync_pointers()


if __name__ == "__main__":
    main()
