"""Markdown parsers for weekly notes (02-weekly/*.md).

Parse YAML frontmatter, ## sections, the stack rank table, and weekly Top 3.
Write-back functions for reordering stack rank, setting frontmatter, and
updating Top 3 items. Tri-state checkbox support for close-week review.
"""

import re
from typing import Any


def parse_weekly_frontmatter(md: str) -> dict[str, str]:
    """Extract YAML frontmatter from a weekly note.

    Returns a flat dict of key-value pairs. Values are always strings.
    If no frontmatter block is present, returns {}.
    """
    if not md.startswith("---"):
        return {}
    end = md.find("\n---", 3)
    if end == -1:
        return {}
    block = md[3:end].strip()
    result: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            result[key] = value
    return result


def set_weekly_frontmatter(md: str, key: str, value: str) -> str:
    """Set a single frontmatter key. Creates the frontmatter block if missing."""
    if not md.startswith("---"):
        # No frontmatter — prepend one.
        return f"---\n{key}: {value}\n---\n\n{md}"
    end = md.find("\n---", 3)
    if end == -1:
        return f"---\n{key}: {value}\n---\n\n{md}"
    block = md[3:end]
    after = md[end + 4:]  # skip \n---
    # Check if key already exists in block
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*:\s*)(.*)$", re.MULTILINE)
    m = pattern.search(block)
    if m:
        block = block[:m.start()] + f"{key}: {value}" + block[m.end():]
    else:
        block = block.rstrip("\n") + f"\n{key}: {value}\n"
    return f"---{block}\n---{after}"


def parse_weekly_note_sections(md: str) -> dict[str, str]:
    """Parse a weekly note into {section_name: section_body}.

    Same convention as daily notes: level-2 headings (``## ``) delimit
    sections. Level-3 headings are kept inside their parent. Frontmatter
    is skipped.
    """
    # Strip frontmatter before parsing sections.
    body = md
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            body = md[end + 4:]

    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in body.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


_TABLE_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|$")


def parse_stack_rank_table(md: str) -> list[dict[str, str]]:
    """Parse the stack rank markdown table into a list of row dicts.

    Expects a table with columns: Rank | Project | LOP | Role | Impact | Effort | Status
    (or a subset). Handles wikilinks ``[[slug]]`` in cells. Skips the
    separator row (``|---|---|...``).

    Returns a list of dicts, one per data row, keyed by lowercase header name.
    """
    lines = md.splitlines()
    headers: list[str] = []
    rows: list[dict[str, str]] = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break  # end of table
            continue
        # Split cells — strip outer pipes then split on |
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not headers:
            headers = [h.lower() for h in cells]
            in_table = True
            continue
        # Skip separator row
        if all(re.fullmatch(r"-+|:?-+:?", c) for c in cells):
            continue
        # Skip placeholder rows like "| ... |"
        if len(cells) == 1 and cells[0].strip(".") == "":
            continue
        row: dict[str, str] = {}
        for i, h in enumerate(headers):
            row[h] = cells[i] if i < len(cells) else ""
        rows.append(row)
    return rows


def parse_week_top_3(md: str) -> list[dict[str, Any]]:
    """Extract weekly Top 3 items from ``## Focus This Week`` or ``### Recommended Top 3``.

    Returns list of dicts with keys:
      - ``text``: str
      - ``checked``: bool (backward compat: True if done)
      - ``status``: ``"done"`` | ``"partial"`` | ``"missed"``

    Checkbox mapping: ``[x]`` → done, ``[/]`` → partial, ``[ ]`` → missed.
    Items without a checkbox default to missed.
    """
    # Try multiple heading patterns that open-week / close-week use.
    target_headings = ["## Focus This Week", "### Recommended Top 3",
                       "### My Top 3", "## Top 3"]
    items: list[dict[str, Any]] = []
    in_section = False
    for line in md.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(h) for h in target_headings):
            in_section = True
            items = []  # reset in case we hit multiple; last wins
            continue
        if in_section and (stripped.startswith("## ") or
                          (stripped.startswith("### ") and
                           not any(stripped.startswith(h) for h in target_headings))):
            break
        if not in_section:
            continue
        if not stripped or not stripped[0].isdigit():
            continue
        # Parse "1. [x] text" or "1. [/] text" or "1. **text** — description" or "1. text"
        after_num = stripped.split(".", 1)[-1].strip()
        checked = False
        status = "missed"
        if after_num.startswith("[/]"):
            status = "partial"
            text = after_num[3:].strip()
        elif after_num.startswith("[ ]"):
            text = after_num[3:].strip()
        elif after_num[:3].lower() in ("[x]", "[X]"):
            checked = True
            status = "done"
            text = after_num[3:].strip()
        else:
            text = after_num
        # Strip bold markers for display
        text = re.sub(r"^\*\*(.+?)\*\*", r"\1", text)
        if text:
            items.append({"text": text, "checked": checked, "status": status})
    return items


def set_week_top_3_item(md: str, index: int, text: str) -> str:
    """Replace the text of the Nth (0-indexed) Top 3 item.

    Searches for the same headings as ``parse_week_top_3``. Preserves checkbox
    state. If fewer than ``index + 1`` items exist, appends new ones.
    """
    target_headings = ["## Focus This Week", "### Recommended Top 3",
                       "### My Top 3", "## Top 3"]
    lines = md.splitlines()
    section_start = None
    section_end = len(lines)
    item_re = re.compile(r"^(\s*\d+\.\s+)(.*)$")

    for i, line in enumerate(lines):
        stripped = line.strip()
        if section_start is None:
            if any(stripped.startswith(h) for h in target_headings):
                section_start = i
            continue
        if stripped.startswith("## ") or (stripped.startswith("### ") and
                                          not any(stripped.startswith(h) for h in target_headings)):
            section_end = i
            break

    if section_start is None:
        # No section — append one
        suffix = ["", "## Focus This Week", f"1. [ ] {text}", ""]
        return md.rstrip("\n") + "\n" + "\n".join(suffix) + "\n"

    # Find item lines in the section
    item_indices: list[int] = []
    for i in range(section_start + 1, section_end):
        if item_re.match(lines[i]):
            item_indices.append(i)

    if index < len(item_indices):
        m = item_re.match(lines[item_indices[index]])
        prefix = m.group(1)
        rest = m.group(2)
        # Preserve checkbox if present
        if rest.startswith("[ ]") or rest.startswith("[x]") or rest.startswith("[X]"):
            marker = rest[:3]
            lines[item_indices[index]] = f"{prefix}{marker} {text}".rstrip()
        else:
            lines[item_indices[index]] = f"{prefix}[ ] {text}".rstrip()
    else:
        # Append new items up to index
        insert_at = item_indices[-1] + 1 if item_indices else section_start + 1
        for n in range(len(item_indices), index + 1):
            body = text if n == index else ""
            lines.insert(insert_at + (n - len(item_indices)), f"{n + 1}. [ ] {body}".rstrip())

    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def toggle_week_top_3(md: str, index: int) -> str:
    """Toggle the checkbox on the Nth (0-indexed) weekly Top 3 item."""
    target_headings = ["## Focus This Week", "### Recommended Top 3",
                       "### My Top 3", "## Top 3"]
    lines = md.splitlines()
    in_section = False
    item_re = re.compile(r"^(\s*\d+\.\s+)(.*)$")
    seen = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not in_section:
            if any(stripped.startswith(h) for h in target_headings):
                in_section = True
            continue
        if stripped.startswith("## ") or (stripped.startswith("### ") and
                                          not any(stripped.startswith(h) for h in target_headings)):
            break
        m = item_re.match(line)
        if not m:
            continue
        if seen == index:
            prefix, rest = m.group(1), m.group(2)
            if rest.startswith("[ ]"):
                lines[i] = prefix + "[x]" + rest[3:]
            elif rest.startswith("[x]") or rest.startswith("[X]"):
                lines[i] = prefix + "[ ]" + rest[3:]
            else:
                lines[i] = prefix + "[x] " + rest
            break
        seen += 1

    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def reorder_stack_rank(md: str, ordered_projects: list[str]) -> str:
    """Rewrite the stack rank table rows to match ``ordered_projects``.

    ``ordered_projects`` is a list of project names (matching the Project
    column, with or without wikilink brackets). Rows not in the list are
    appended at the end in their original order. The Rank column is
    renumbered sequentially.
    """
    lines = md.splitlines()
    table_start = None
    table_end = len(lines)
    header_line = None
    separator_line = None
    data_rows: list[tuple[str, list[str]]] = []  # (project_key, raw_cells)
    headers: list[str] = []
    project_col = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            if table_start is not None and data_rows:
                table_end = i
                break
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if table_start is None:
            # First pipe-row = header
            table_start = i
            header_line = line
            headers = [h.lower() for h in cells]
            project_col = headers.index("project") if "project" in headers else 1
            continue
        if all(re.fullmatch(r"-+|:?-+:?", c) for c in cells):
            separator_line = line
            continue
        # Skip placeholder rows
        if len(cells) == 1 and cells[0].strip(".") == "":
            continue
        # Extract project key: strip wikilinks for matching
        proj = cells[project_col] if project_col < len(cells) else ""
        proj_key = proj.strip("[]").strip()
        data_rows.append((proj_key, cells))

    if table_start is None or not data_rows:
        return md  # no table found, return unchanged

    # Build lookup: project_key -> cells
    row_map: dict[str, list[str]] = {}
    row_order: list[str] = []
    for key, cells in data_rows:
        row_map[key] = cells
        row_order.append(key)

    # Normalize ordered_projects keys
    normalized_order = [p.strip("[]").strip() for p in ordered_projects]

    # Build new order: requested first, then remaining in original order
    new_order: list[str] = []
    for p in normalized_order:
        if p in row_map and p not in new_order:
            new_order.append(p)
    for p in row_order:
        if p not in new_order:
            new_order.append(p)

    # Rebuild table lines
    rank_col = headers.index("rank") if "rank" in headers else 0
    new_table_lines = [header_line]
    if separator_line:
        new_table_lines.append(separator_line)
    for rank, key in enumerate(new_order, 1):
        cells = list(row_map[key])
        if rank_col < len(cells):
            cells[rank_col] = str(rank)
        new_table_lines.append("| " + " | ".join(cells) + " |")

    result_lines = lines[:table_start] + new_table_lines + lines[table_end:]
    return "\n".join(result_lines) + ("\n" if md.endswith("\n") else "")


def set_week_top_3_status(md: str, index: int, status: str) -> str:
    """Set the Nth (0-indexed) weekly Top 3 item to a tri-state status.

    ``status`` must be ``"done"``, ``"partial"``, or ``"missed"``.
    Maps to ``[x]``, ``[/]``, ``[ ]`` respectively.
    """
    marker_map = {"done": "[x]", "partial": "[/]", "missed": "[ ]"}
    if status not in marker_map:
        return md
    new_marker = marker_map[status]

    target_headings = ["## Focus This Week", "### Recommended Top 3",
                       "### My Top 3", "## Top 3"]
    lines = md.splitlines()
    in_section = False
    item_re = re.compile(r"^(\s*\d+\.\s+)(.*)$")
    seen = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not in_section:
            if any(stripped.startswith(h) for h in target_headings):
                in_section = True
            continue
        if stripped.startswith("## ") or (stripped.startswith("### ") and
                                          not any(stripped.startswith(h) for h in target_headings)):
            break
        m = item_re.match(line)
        if not m:
            continue
        if seen == index:
            prefix, rest = m.group(1), m.group(2)
            if rest.startswith("[ ]") or rest.startswith("[x]") or rest.startswith("[X]") or rest.startswith("[/]"):
                lines[i] = prefix + new_marker + rest[3:]
            else:
                lines[i] = prefix + new_marker + " " + rest
            break
        seen += 1

    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def parse_quick_notes(md: str) -> str:
    """Extract the body of the ``### Quick Notes`` section.

    Returns the text below the heading up to the next heading of equal or
    higher level, or end of file. Returns empty string if not found.
    """
    lines = md.splitlines()
    in_section = False
    buf: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "### Quick Notes":
            in_section = True
            continue
        if in_section and (stripped.startswith("## ") or stripped.startswith("### ")):
            break
        if in_section:
            buf.append(line)
    return "\n".join(buf).strip()


def set_section_content(md: str, section: str, content: str) -> str:
    """Replace the body of ``### {section}`` with ``content``.

    Creates the section at the end of the note if it doesn't exist.
    Operates on level-3 (``### ``) headings.
    """
    heading = f"### {section}"
    lines = md.splitlines()
    section_start = None
    section_end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == heading:
            section_start = i
            continue
        if section_start is not None and (line.startswith("### ") or line.startswith("## ")):
            section_end = i
            break

    new_block = [heading, content.rstrip(), ""]
    if section_start is None:
        return md.rstrip("\n") + "\n\n" + "\n".join(new_block) + "\n"
    return "\n".join(lines[:section_start] + new_block + lines[section_end:]) + (
        "\n" if md.endswith("\n") else ""
    )


def set_project_status(md: str, project: str, status: str) -> str:
    """Set the Status column for ``project`` in the stack rank table.

    ``project`` is matched with wikilink brackets stripped for comparison.
    ``status`` should be ``"on-track"``, ``"needs-attention"``, or ``"stalled"``.
    """
    lines = md.splitlines()
    headers: list[str] = []
    project_col = -1
    status_col = -1
    in_table = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not headers:
            headers = [h.lower() for h in cells]
            project_col = headers.index("project") if "project" in headers else -1
            status_col = headers.index("status") if "status" in headers else -1
            in_table = True
            continue
        # Skip separator
        if all(re.fullmatch(r"-+|:?-+:?", c) for c in cells):
            continue
        if project_col < 0 or status_col < 0:
            continue
        proj = cells[project_col] if project_col < len(cells) else ""
        proj_key = proj.strip("[]").strip()
        target_key = project.strip("[]").strip()
        if proj_key == target_key:
            if status_col < len(cells):
                cells[status_col] = status
                lines[i] = "| " + " | ".join(cells) + " |"
            break

    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")
