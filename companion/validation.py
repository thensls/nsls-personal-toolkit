"""Input validation for routes that write to the vault."""

import re

HABIT_ID_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
SAFE_SHORT_RE = re.compile(r"^[^\n\r]{1,64}$")  # no newlines, 64 char cap
SAFE_LONG_RE = re.compile(r"^[\s\S]{0,4096}$")  # arbitrary text up to 4KB

ALLOWED_SAVE_SECTIONS = {
    "Insight Reflection", "Gratitude", "Brain Dump", "Carrying Over",
    # Command Center quick-capture insight. Kept distinct from the day-close
    # "Insight Reflection" so saving it doesn't flip the view to results mode.
    "Daily Insight",
}
ALLOWED_TOGGLE_SECTIONS = {"top_3", "bonus"}


def _derive_habit_id(name: str, existing_ids: set[str] | None = None) -> str:
    """Convert a habit name to a stable kebab-case id, deduping if needed.

    Examples: "Walk 30 min" -> "walk-30-min"; "Read" -> "read".
    Strips non-[a-z0-9-] characters. If the result collides with an existing
    id, appends -2, -3, etc.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = slug[:32] or "habit"
    existing = existing_ids or set()
    if slug not in existing:
        return slug
    i = 2
    while f"{slug[:30]}-{i}" in existing:
        i += 1
    return f"{slug[:30]}-{i}"


def validate_habit_fields(form, existing_ids: set[str] | None = None) -> dict:
    """Validate POST /habit form. Raises ValueError on failure.

    Form schema is intentionally minimal: just ``name``. The id is derived
    from the name (kebab-case, deduped against existing_ids). Emoji, target,
    and frequency default to empty/'daily' — callers can edit habits.md
    directly if they want richer metadata.
    """
    name = form.get("name", "").strip()
    if not SAFE_SHORT_RE.fullmatch(name):
        raise ValueError("name must be 1-64 chars, no newlines")
    return {
        "id": _derive_habit_id(name, existing_ids),
        "name": name,
        "emoji": form.get("emoji", "").strip()[:8],
        "target": form.get("target", "").strip()[:64] or "daily",
        "frequency": form.get("frequency", "").strip()[:64] or "daily",
    }


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
