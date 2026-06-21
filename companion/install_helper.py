"""Resolve vault path and generate the launchd plist safely.

Invoked from install.sh as a python subprocess so we avoid sed quoting issues.
"""

import os
import plistlib
import socket
import sys
from pathlib import Path

PROFILE_PATH = Path.home() / ".claude" / "local-plugins" / "nsls-personal-toolkit" / "50-reference" / "builder-profile.md"


def resolve_vault() -> str:
    # 1) env var
    env = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env and (Path(env) / "01-daily").is_dir():
        return env
    # 2) builder-profile (simple YAML-in-markdown — find data_sources.familiar.paths)
    if PROFILE_PATH.exists():
        text = PROFILE_PATH.read_text(encoding="utf-8")
        host = socket.gethostname()
        in_paths = False
        current: dict = {}
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "paths:":
                in_paths = True; continue
            if in_paths and stripped.startswith("- host:"):
                if current.get("host") == host and current.get("path"):
                    return current["path"]
                current = {"host": stripped.split(":", 1)[1].strip()}
            elif in_paths and stripped.startswith("path:"):
                current["path"] = stripped.split(":", 1)[1].strip()
            elif in_paths and stripped == "":
                if current.get("host") == host and current.get("path"):
                    return current["path"]
                current = {}
        if current.get("host") == host and current.get("path"):
            return current["path"]
    # 3) prompt fallback
    sys.stderr.write("Vault path not found. Enter path to your Obsidian vault: ")
    sys.stderr.flush()
    return input().strip()


def write_plist(vault: str, dest: str, python_exe: str | None = None) -> None:
    python_exe = python_exe or sys.executable
    plist = {
        "Label": "com.nsls.toolkit-companion",
        "ProgramArguments": [python_exe, "-m", "companion.cli", "serve", "--no-open"],
        "EnvironmentVariables": {"OBSIDIAN_VAULT_PATH": vault},
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(Path.home() / "Library" / "Logs" / "nsls-toolkit-companion.log"),
        "StandardErrorPath": str(Path.home() / "Library" / "Logs" / "nsls-toolkit-companion.log"),
    }
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        plistlib.dump(plist, f)
    os.chmod(dest, 0o600)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "resolve-vault":
        print(resolve_vault())
    elif cmd == "write-plist":
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--vault", required=True)
        ap.add_argument("--dest", required=True)
        args = ap.parse_args(sys.argv[2:])
        write_plist(args.vault, args.dest)
    else:
        sys.exit("usage: install_helper.py {resolve-vault|write-plist}")
