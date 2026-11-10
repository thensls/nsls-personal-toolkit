"""The companion's own saved state: small UI facts that must outlive a browser.

Lives in the vault at ``.toolkit-companion/state.json`` (a dot folder, so
Obsidian never shows it). Keeping it beside the notes rather than in browser
storage means a choice survives restarts, a different browser and a different
machine syncing the same vault, and a test vault starts with a clean slate.

Today it holds one thing: which first-run tips (callouts) the builder has
dismissed. A missing or unreadable file reads as "nothing dismissed", so the
worst case is a tip showing again, never a broken page.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from companion.safe_write import safe_modify

STATE_DIR = ".toolkit-companion"
STATE_FILE = "state.json"
CALLOUT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
# Generous ceiling on stored ids: a bad client can't grow the file forever.
MAX_CALLOUTS = 100


def state_path(vault: Path) -> Path:
    return Path(vault) / STATE_DIR / STATE_FILE


def _parse(text: str) -> dict:
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _clean_ids(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: list[str] = []
    for item in raw:
        if isinstance(item, str) and CALLOUT_ID_RE.match(item) and item not in seen:
            seen.append(item)
    return seen[:MAX_CALLOUTS]


def dismissed_callouts(vault: Path) -> list[str]:
    try:
        text = state_path(vault).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return _clean_ids(_parse(text).get("callouts_dismissed"))


def _set_aside_if_unreadable(path: Path) -> None:
    """A state file that isn't UTF-8 would make every write fail (safe_modify
    decodes before it transforms). Move it aside so the next write starts
    clean; the bytes are kept beside it, never deleted."""
    try:
        path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        return
    except UnicodeDecodeError:
        path.replace(path.with_name(path.name + ".unreadable"))


def dismiss_callouts(vault: Path, ids: list[str]) -> list[str]:
    """Add ids to the dismissed list (deduplicated) and return the new list."""
    _set_aside_if_unreadable(state_path(vault))
    result: list[str] = []

    def _add(text: str) -> str:
        data = _parse(text)
        merged = _clean_ids(data.get("callouts_dismissed"))
        for cid in ids:
            if cid not in merged:
                merged.append(cid)
        merged = merged[:MAX_CALLOUTS]
        data["callouts_dismissed"] = merged
        result[:] = merged
        return json.dumps(data, indent=2) + "\n"

    safe_modify(state_path(vault), _add)
    return result
