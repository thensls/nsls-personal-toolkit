"""Input validation for routes that write to the vault."""

import re

HABIT_ID_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
SAFE_SHORT_RE = re.compile(r"^[^\n\r]{1,64}$")  # no newlines, 64 char cap
SAFE_LONG_RE = re.compile(r"^[\s\S]{0,4096}$")  # arbitrary text up to 4KB

ALLOWED_SAVE_SECTIONS = {
    "Insight Reflection", "Gratitude", "Brain Dump", "Carrying Over",
}
ALLOWED_TOGGLE_SECTIONS = {"top_3", "bonus"}


def validate_habit_fields(form) -> dict:
    """Validate POST /habit form. Raises ValueError with message on failure."""
    out = {}
    out["id"] = form.get("id", "").strip()
    if not HABIT_ID_RE.fullmatch(out["id"]):
        raise ValueError("id must be 1-32 chars of [a-z0-9_-]")
    for field in ("name", "target", "frequency"):
        val = form.get(field, "").strip()
        if not SAFE_SHORT_RE.fullmatch(val):
            raise ValueError(f"{field} must be 1-64 chars, no newlines")
        out[field] = val
    emoji = form.get("emoji", "").strip()
    if len(emoji) > 8 or "\n" in emoji:
        raise ValueError("emoji too long or contains newline")
    out["emoji"] = emoji
    return out


def validate_save(form) -> tuple[str, str]:
    """Validate POST /save. Returns (section, content)."""
    section = form.get("section", "").strip()
    if section not in ALLOWED_SAVE_SECTIONS:
        raise ValueError(f"section must be one of {sorted(ALLOWED_SAVE_SECTIONS)}")
    content = form.get("content", "")
    if not SAFE_LONG_RE.fullmatch(content):
        raise ValueError("content exceeds 4KB or invalid")
    return section, content


def validate_toggle(form) -> tuple[str, int]:
    """Validate POST /toggle. Returns (section, index)."""
    section = form.get("section", "").strip()
    if section not in ALLOWED_TOGGLE_SECTIONS:
        raise ValueError(f"section must be one of {sorted(ALLOWED_TOGGLE_SECTIONS)}")
    try:
        index = int(form.get("index", ""))
    except (TypeError, ValueError):
        raise ValueError("index must be a non-negative integer")
    if index < 0 or index > 9:
        raise ValueError("index out of bounds (0-9)")
    return section, index
