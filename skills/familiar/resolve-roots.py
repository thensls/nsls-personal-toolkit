#!/usr/bin/env python3
"""Resolve a builder's Familiar capture roots from their builder profile.

Familiar can capture on more than one machine, so the profile stores a LIST of
capture roots under `data_sources.familiar.paths`. This script reads that list
and prints one absolute path per line, so any close-day / close-week /
self-insight scan can loop over every machine and sum the results.

Usage:
    python3 resolve-roots.py <path-to-builder-profile.md>

Behavior:
- New form (`familiar:` block with `enabled:` + `paths:`) -> prints each path.
- Legacy boolean (`familiar: true`) or missing/unreadable profile
  -> prints the default `~/familiar/stills-markdown` (best effort).
- Disabled (`familiar: false`, or `enabled: false`) -> prints nothing.
- Unfilled template placeholders (e.g. `path: [absolute path]`) are ignored.
"""
import os
import re
import sys

DEFAULT = os.path.expanduser("~/familiar/stills-markdown")


def resolve(profile_path):
    try:
        txt = open(profile_path, encoding="utf-8").read()
    except Exception:
        return [DEFAULT]

    m = re.search(r"^([ \t]*)familiar:[ \t]*(.*)$", txt, re.MULTILINE)
    if not m:
        return [DEFAULT]

    indent, inline = m.group(1), m.group(2).strip()
    if inline.lower() == "true":       # legacy boolean form
        return [DEFAULT]
    if inline.lower() == "false":      # explicitly disabled
        return []

    # Block form: collect the lines indented under the `familiar:` key.
    block = []
    for line in txt[m.end():].splitlines():
        if line.strip() == "":
            block.append(line)
            continue
        if (len(line) - len(line.lstrip())) <= len(indent):
            break
        block.append(line)
    block = "\n".join(block)

    if re.search(r"enabled:\s*false", block, re.I):
        return []

    paths = [p.strip().strip("\"'") for p in re.findall(r"path:\s*(.+)", block)]
    paths = [
        os.path.expanduser(p)
        for p in paths
        if p and not p.lstrip().startswith("[")  # skip unfilled placeholders
    ]
    return paths or [DEFAULT]


if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else ""
    print("\n".join(resolve(profile)))
