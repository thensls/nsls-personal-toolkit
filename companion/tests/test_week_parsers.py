"""Tests for weekly note parsers and write-back functions."""

import pytest

from companion.week_parsers import (
    parse_quick_notes,
    parse_stack_rank_table,
    parse_week_top_3,
    parse_weekly_frontmatter,
    parse_weekly_note_sections,
    reorder_stack_rank,
    set_project_status,
    set_section_content,
    set_week_top_3_item,
    set_week_top_3_status,
    set_weekly_frontmatter,
    toggle_week_top_3,
)


# ---------------------------------------------------------------------------
# parse_weekly_frontmatter
# ---------------------------------------------------------------------------

class TestParseWeeklyFrontmatter:
    def test_valid_frontmatter(self):
        md = "---\nweek: 2026-W22\nstatus: confirmed\nmode: push-to-build\n---\n\n# Week\n"
        fm = parse_weekly_frontmatter(md)
        assert fm["week"] == "2026-W22"
        assert fm["status"] == "confirmed"
        assert fm["mode"] == "push-to-build"

    def test_missing_frontmatter(self):
        md = "# Week\n\nSome content here.\n"
        assert parse_weekly_frontmatter(md) == {}

    def test_partial_frontmatter(self):
        md = "---\nstatus: draft\n---\n\n# Week\n"
        fm = parse_weekly_frontmatter(md)
        assert fm["status"] == "draft"
        assert "mode" not in fm

    def test_quoted_values(self):
        md = '---\nmode-rationale: "lots of signals"\n---\n'
        fm = parse_weekly_frontmatter(md)
        assert fm["mode-rationale"] == "lots of signals"

    def test_empty_string(self):
        assert parse_weekly_frontmatter("") == {}


# ---------------------------------------------------------------------------
# set_weekly_frontmatter
# ---------------------------------------------------------------------------

class TestSetWeeklyFrontmatter:
    def test_set_existing_key(self):
        md = "---\nstatus: draft\n---\n\n# Week\n"
        result = set_weekly_frontmatter(md, "status", "confirmed")
        fm = parse_weekly_frontmatter(result)
        assert fm["status"] == "confirmed"
        assert "# Week" in result

    def test_add_new_key(self):
        md = "---\nstatus: draft\n---\n\n# Week\n"
        result = set_weekly_frontmatter(md, "mode", "protect")
        fm = parse_weekly_frontmatter(result)
        assert fm["mode"] == "protect"
        assert fm["status"] == "draft"

    def test_create_frontmatter_when_missing(self):
        md = "# Week\n\nContent.\n"
        result = set_weekly_frontmatter(md, "status", "draft")
        fm = parse_weekly_frontmatter(result)
        assert fm["status"] == "draft"
        assert "# Week" in result


# ---------------------------------------------------------------------------
# parse_weekly_note_sections
# ---------------------------------------------------------------------------

class TestParseWeeklyNoteSections:
    def test_basic_sections(self):
        md = "---\nstatus: draft\n---\n\n## Week Plan\n\nSome plan.\n\n## Focus This Week\n1. Ship it\n"
        sections = parse_weekly_note_sections(md)
        assert "Week Plan" in sections
        assert "Focus This Week" in sections
        assert "Ship it" in sections["Focus This Week"]

    def test_sections_without_frontmatter(self):
        md = "# Week\n\n## Section A\n\nContent A\n\n## Section B\n\nContent B\n"
        sections = parse_weekly_note_sections(md)
        assert "Section A" in sections
        assert "Section B" in sections


# ---------------------------------------------------------------------------
# parse_stack_rank_table
# ---------------------------------------------------------------------------

class TestParseStackRankTable:
    NORMAL_TABLE = """\
---
week: 2026-W22
---

# W22 Project Stack Rank

| Rank | Project | LOP | Role | Impact | Effort | Status |
|------|---------|-----|------|--------|--------|--------|
| 1 | [[proj-alpha]] | Growth | architect | L | M | on-track |
| 2 | [[proj-beta]] | Ops | sponsor | M | S | needs-attention |
| 3 | plain-project | Tech | IC | S | L | stalled |

## Focus This Week
"""

    def test_normal_table(self):
        rows = parse_stack_rank_table(self.NORMAL_TABLE)
        assert len(rows) == 3
        assert rows[0]["rank"] == "1"
        assert rows[0]["project"] == "[[proj-alpha]]"
        assert rows[0]["lop"] == "Growth"
        assert rows[2]["project"] == "plain-project"

    def test_wikilinks_in_cells(self):
        rows = parse_stack_rank_table(self.NORMAL_TABLE)
        assert "[[" in rows[0]["project"]
        assert "[[" not in rows[2]["project"]

    def test_empty_cells(self):
        md = """\
| Rank | Project | LOP | Role | Impact | Effort | Status |
|------|---------|-----|------|--------|--------|--------|
| 1 | [[proj-a]] |  |  |  |  |  |
"""
        rows = parse_stack_rank_table(md)
        assert len(rows) == 1
        assert rows[0]["lop"] == ""
        assert rows[0]["status"] == ""

    def test_single_row(self):
        md = """\
| Rank | Project | LOP |
|------|---------|-----|
| 1 | [[solo]] | Core |
"""
        rows = parse_stack_rank_table(md)
        assert len(rows) == 1
        assert rows[0]["project"] == "[[solo]]"

    def test_no_rows(self):
        md = """\
| Rank | Project | LOP |
|------|---------|-----|
"""
        rows = parse_stack_rank_table(md)
        assert rows == []

    def test_no_table(self):
        md = "# Week\n\nNo table here.\n"
        rows = parse_stack_rank_table(md)
        assert rows == []

    def test_placeholder_row_skipped(self):
        md = """\
| Rank | Project | LOP |
|------|---------|-----|
| 1 | [[proj-a]] | Core |
| ... |
"""
        rows = parse_stack_rank_table(md)
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# parse_week_top_3
# ---------------------------------------------------------------------------

class TestParseWeekTop3:
    def test_focus_this_week(self):
        md = """\
## Focus This Week
1. [ ] Ship the toolkit
2. [x] Review PRs
3. [ ] Write docs
"""
        items = parse_week_top_3(md)
        assert len(items) == 3
        assert items[0]["text"] == "Ship the toolkit"
        assert items[0]["checked"] is False
        assert items[0]["status"] == "missed"
        assert items[1]["text"] == "Review PRs"
        assert items[1]["checked"] is True
        assert items[1]["status"] == "done"

    def test_tri_state_partial(self):
        md = """\
## Focus This Week
1. [x] Done item
2. [/] Partial item
3. [ ] Missed item
"""
        items = parse_week_top_3(md)
        assert len(items) == 3
        assert items[0]["status"] == "done"
        assert items[0]["checked"] is True
        assert items[1]["status"] == "partial"
        assert items[1]["checked"] is False
        assert items[2]["status"] == "missed"
        assert items[2]["checked"] is False

    def test_bold_items(self):
        md = """\
### Recommended Top 3
1. **Ship toolkit** — high priority
2. **Review PRs** — blocking others
"""
        items = parse_week_top_3(md)
        assert len(items) == 2
        assert items[0]["text"].startswith("Ship toolkit")

    def test_no_checkboxes(self):
        md = "## Focus This Week\n1. Ship it\n2. Review\n"
        items = parse_week_top_3(md)
        assert len(items) == 2
        assert all(not i["checked"] for i in items)
        assert all(i["status"] == "missed" for i in items)


# ---------------------------------------------------------------------------
# reorder_stack_rank
# ---------------------------------------------------------------------------

class TestReorderStackRank:
    TABLE_MD = """\
---
week: 2026-W22
---

| Rank | Project | LOP |
|------|---------|-----|
| 1 | [[alpha]] | Growth |
| 2 | [[beta]] | Ops |
| 3 | [[gamma]] | Tech |
"""

    def test_normal_reorder(self):
        result = reorder_stack_rank(self.TABLE_MD, ["gamma", "alpha", "beta"])
        rows = parse_stack_rank_table(result)
        assert rows[0]["project"] == "[[gamma]]"
        assert rows[0]["rank"] == "1"
        assert rows[1]["project"] == "[[alpha]]"
        assert rows[1]["rank"] == "2"
        assert rows[2]["project"] == "[[beta]]"
        assert rows[2]["rank"] == "3"

    def test_same_order(self):
        result = reorder_stack_rank(self.TABLE_MD, ["alpha", "beta", "gamma"])
        rows = parse_stack_rank_table(result)
        assert rows[0]["project"] == "[[alpha]]"
        assert rows[1]["project"] == "[[beta]]"
        assert rows[2]["project"] == "[[gamma]]"

    def test_single_item(self):
        md = """\
| Rank | Project | LOP |
|------|---------|-----|
| 1 | [[solo]] | Core |
"""
        result = reorder_stack_rank(md, ["solo"])
        rows = parse_stack_rank_table(result)
        assert len(rows) == 1
        assert rows[0]["project"] == "[[solo]]"

    def test_partial_order_appends_remaining(self):
        result = reorder_stack_rank(self.TABLE_MD, ["gamma"])
        rows = parse_stack_rank_table(result)
        assert rows[0]["project"] == "[[gamma]]"
        assert len(rows) == 3

    def test_wikilink_brackets_in_order(self):
        result = reorder_stack_rank(self.TABLE_MD, ["[[beta]]", "[[gamma]]", "[[alpha]]"])
        rows = parse_stack_rank_table(result)
        assert rows[0]["project"] == "[[beta]]"


# ---------------------------------------------------------------------------
# _detect_week_state (imported from server)
# ---------------------------------------------------------------------------

class TestDetectWeekState:
    """Test the mode detection function. Imported from server at test time."""

    def test_closed_returns_results(self):
        from companion.server import _detect_week_state
        assert _detect_week_state("---\nstatus: closed\n---\n# Week\n") == "week-results"

    def test_confirmed_returns_command(self):
        from companion.server import _detect_week_state
        assert _detect_week_state("---\nstatus: confirmed\n---\n# Week\n") == "week-command"

    def test_draft_returns_plan(self):
        from companion.server import _detect_week_state
        assert _detect_week_state("---\nstatus: draft\n---\n# Week\n") == "plan-week"

    def test_editing_returns_plan(self):
        from companion.server import _detect_week_state
        assert _detect_week_state("---\nstatus: editing\n---\n# Week\n") == "plan-week"

    def test_no_frontmatter_returns_plan(self):
        from companion.server import _detect_week_state
        assert _detect_week_state("# Week\nSome content.\n") == "plan-week"

    def test_empty_returns_plan(self):
        from companion.server import _detect_week_state
        assert _detect_week_state("") == "plan-week"


# ---------------------------------------------------------------------------
# set_week_top_3_status (tri-state write-back)
# ---------------------------------------------------------------------------

class TestSetWeekTop3Status:
    BASE_MD = """\
---
status: confirmed
---

## Focus This Week
1. [ ] Ship the toolkit
2. [x] Review PRs
3. [ ] Write docs
"""

    def test_set_to_done(self):
        result = set_week_top_3_status(self.BASE_MD, 0, "done")
        items = parse_week_top_3(result)
        assert items[0]["status"] == "done"
        assert items[0]["checked"] is True

    def test_set_to_partial(self):
        result = set_week_top_3_status(self.BASE_MD, 0, "partial")
        items = parse_week_top_3(result)
        assert items[0]["status"] == "partial"

    def test_set_to_missed(self):
        result = set_week_top_3_status(self.BASE_MD, 1, "missed")
        items = parse_week_top_3(result)
        assert items[1]["status"] == "missed"
        assert items[1]["checked"] is False

    def test_roundtrip_all_states(self):
        md = self.BASE_MD
        md = set_week_top_3_status(md, 0, "done")
        md = set_week_top_3_status(md, 1, "partial")
        md = set_week_top_3_status(md, 2, "missed")
        items = parse_week_top_3(md)
        assert items[0]["status"] == "done"
        assert items[1]["status"] == "partial"
        assert items[2]["status"] == "missed"

    def test_set_on_item_without_checkbox(self):
        md = "## Focus This Week\n1. Ship it\n2. Review\n"
        result = set_week_top_3_status(md, 0, "partial")
        items = parse_week_top_3(result)
        assert items[0]["status"] == "partial"
        assert items[0]["text"] == "Ship it"

    def test_invalid_status_returns_unchanged(self):
        result = set_week_top_3_status(self.BASE_MD, 0, "invalid")
        assert result == self.BASE_MD


# ---------------------------------------------------------------------------
# parse_quick_notes
# ---------------------------------------------------------------------------

class TestParseQuickNotes:
    def test_basic_extraction(self):
        md = """\
## Insight Reflection
Some insight text.

### Quick Notes
Week of May 18:
- Shipped the toolkit
- Fixed 3 bugs

### AI Suggested: Next Week
1. Plan launch
"""
        result = parse_quick_notes(md)
        assert "Shipped the toolkit" in result
        assert "Fixed 3 bugs" in result
        assert "AI Suggested" not in result

    def test_no_quick_notes(self):
        md = "## Insight Reflection\nSome text.\n"
        assert parse_quick_notes(md) == ""

    def test_quick_notes_at_end(self):
        md = """\
## Results

### Quick Notes
Final notes here.
Second line.
"""
        result = parse_quick_notes(md)
        assert "Final notes here." in result
        assert "Second line." in result

    def test_empty_quick_notes(self):
        md = "### Quick Notes\n\n### Next Section\n"
        assert parse_quick_notes(md) == ""


# ---------------------------------------------------------------------------
# set_section_content
# ---------------------------------------------------------------------------

class TestSetSectionContent:
    def test_replace_existing_section(self):
        md = "## Results\n\n### Brain Dump\nOld thoughts.\n\n### Next\nStuff.\n"
        result = set_section_content(md, "Brain Dump", "New thoughts here.")
        assert "New thoughts here." in result
        assert "Old thoughts" not in result
        assert "Stuff." in result

    def test_create_new_section(self):
        md = "## Results\nSome content.\n"
        result = set_section_content(md, "Brain Dump", "My thoughts.")
        assert "### Brain Dump" in result
        assert "My thoughts." in result

    def test_empty_content(self):
        md = "### Brain Dump\nOld.\n"
        result = set_section_content(md, "Brain Dump", "")
        assert "### Brain Dump" in result


# ---------------------------------------------------------------------------
# set_project_status
# ---------------------------------------------------------------------------

class TestSetProjectStatus:
    TABLE_MD = """\
| Rank | Project | LOP | Role | Impact | Effort | Status |
|------|---------|-----|------|--------|--------|--------|
| 1 | [[proj-alpha]] | Growth | architect | L | M | on-track |
| 2 | [[proj-beta]] | Ops | sponsor | M | S | needs-attention |
"""

    def test_set_status(self):
        result = set_project_status(self.TABLE_MD, "proj-alpha", "stalled")
        rows = parse_stack_rank_table(result)
        assert rows[0]["status"] == "stalled"

    def test_set_status_with_brackets(self):
        result = set_project_status(self.TABLE_MD, "[[proj-beta]]", "on-track")
        rows = parse_stack_rank_table(result)
        assert rows[1]["status"] == "on-track"

    def test_nonexistent_project_unchanged(self):
        result = set_project_status(self.TABLE_MD, "nonexistent", "stalled")
        assert result == self.TABLE_MD
