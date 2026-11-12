#!/usr/bin/env python3
"""A folder kept current by Claude is left alone by everything here that used git.

Plain stdlib, no pytest: run with `python3 hooks/tests/test_delivered_folder.py`.

NSLS's Claude organization can deliver this toolkit, and the Builder Toolkit's
session hook then copies each version into the usual folder. Such a folder is
not a checkout: it carries `.delivered-by-claude.json`, and its `.git` is a
placeholder FILE. What this pins:

1. The session hook only syncs pointers there. It runs no git command at all,
   so nothing can ask for a sign-in or report a "stale" checkout that is not one.
2. The installer stops before it pulls, clones or registers anything.
3. A real checkout is untouched by either guard: the hook still reports, and
   every git call it makes carries the three settings that stop git asking
   anyone to sign in (NSLS's repository being private is what makes a fork's
   catch-up fetch want credentials).

A recording `git` stands in for the real one, so "no git call" is measured.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WINDOWS = os.name == "nt"
failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


RECORDER = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    keys = ("GIT_TERMINAL_PROMPT", "GCM_INTERACTIVE", "GIT_ASKPASS")
    with open(os.environ["RECORD_TO"], "a") as fh:
        fh.write(json.dumps({"argv": sys.argv[1:], "env": {k: os.environ.get(k) for k in keys}}) + "\\n")
    sys.exit(1)
''')


def world(tmp, delivered):
    home = Path(tmp) / "home"
    folder = home / ".claude" / "local-plugins" / "nsls-personal-toolkit"
    (folder / "skills" / "open-day").mkdir(parents=True)
    (folder / "skills" / "open-day" / "SKILL.md").write_text(
        "---\nname: open-day\ndescription: plan the day\n---\nbody\n", encoding="utf-8")
    if delivered:
        (folder / ".delivered-by-claude.json").write_text('{"plugin": "nsls-personal-toolkit", "files": {}}', encoding="utf-8")
        (folder / ".git").write_text("gitdir: .git.delivered-by-claude\n", encoding="utf-8")
    else:
        (folder / ".git").mkdir()
    bindir = Path(tmp) / "bin"
    bindir.mkdir()
    (bindir / "git").write_text(RECORDER, encoding="utf-8")
    (bindir / "git").chmod(0o755)
    log = Path(tmp) / "git-calls.jsonl"
    log.write_text("", encoding="utf-8")
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), RECORD_TO=str(log),
               PATH=str(bindir) + os.pathsep + os.environ["PATH"])
    env.pop("CLAUDE_CONFIG_DIR", None)
    return home, folder, log, env


def calls(log):
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]


def run_hook(env, *args):
    return subprocess.run([sys.executable, str(ROOT / "hooks" / "session-start.py"), *args],
                          capture_output=True, text=True, env=env, timeout=60)


if WINDOWS:
    print("skipped on Windows: the recording git is a POSIX script, and this hook is not registered there")
    sys.exit(0)

print("1. the session hook, in a folder kept current by Claude")
with tempfile.TemporaryDirectory() as tmp:
    home, folder, log, env = world(tmp, delivered=True)
    for args in (("--no-pull",), ()):
        r = run_hook(env, *args)
        check(f"runs clean ({' '.join(args) or 'no flags'})", r.returncode == 0, r.stderr)
        check(f"says nothing to Claude ({' '.join(args) or 'no flags'})", r.stdout == "", r.stdout)
    check("it made no git call at all, with or without the pull", calls(log) == [], str(calls(log)))
    pointer = home / ".claude" / "skills" / "open-day" / "SKILL.md"
    check("its skills are still pointed at", pointer.is_file()
          and "local-plugins/nsls-personal-toolkit/skills/open-day/SKILL.md" in pointer.read_text(encoding="utf-8"))

print("2. the same hook, in a real checkout")
with tempfile.TemporaryDirectory() as tmp:
    home, folder, log, env = world(tmp, delivered=False)
    r = run_hook(env, "--no-pull")
    got = calls(log)
    check("it still asks git about the checkout", r.returncode == 0 and len(got) > 0, r.stderr)
    want = {"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_ASKPASS": ""}
    check("and every one of those calls can only fail, never ask for a sign-in",
          all(c["env"] == want for c in got), str([c for c in got if c["env"] != want][:2]))
    log.write_text("", encoding="utf-8")
    run_hook(env)
    pulls = [c for c in calls(log) if "pull" in c["argv"]]
    check("the hook's own pull carries them too", len(pulls) == 1 and pulls[0]["env"] == want, str(pulls))

print("3. the installer")
with tempfile.TemporaryDirectory() as tmp:
    home, folder, log, env = world(tmp, delivered=True)
    env["NSLS_SKIP_COMPANION"] = "1"
    r = subprocess.run(["bash", str(ROOT / "install.sh")], capture_output=True, text=True, env=env,
                       stdin=subprocess.DEVNULL, timeout=120)
    check("stops with a plain message", r.returncode == 0 and "already gets the NSLS Personal Toolkit through Claude" in r.stdout,
          r.stdout + r.stderr)
    check("pulls and clones nothing", calls(log) == [], str(calls(log)))
    check("registers nothing", not (home / ".claude" / "settings.json").exists())
    check("and never reaches the steps after it (the install event, the companion)", "Done!" not in r.stdout)
    # A real checkout's run through the installer is not exercised here on
    # purpose: past this guard the installer reports an install to the live
    # tracker, and a test must never write there.

print()
if failures:
    print(f"FAILED: {len(failures)}")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all checks passed")
