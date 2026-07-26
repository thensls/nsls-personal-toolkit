"""Tests for the generic daily-note frontmatter helpers.

`parse_frontmatter` / `set_frontmatter` are the daily-note analogues of
`parse_weekly_frontmatter` / `set_weekly_frontmatter` in week_parsers.py.
They drive the `status: planning | active | closed` contract that both the
CLI/web companion and the cowork artifact use to pick a mode (replacing the
fragile section-presence inference). Behavior must match the weekly versions
so the two surfaces never disagree on frontmatter.
"""

from companion.parsers import parse_frontmatter, set_frontmatter


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        md = "---\ndate: 2026-06-17\nstatus: active\n---\n\n## Morning Check-in\n"
        fm = parse_frontmatter(md)
        assert fm["date"] == "2026-06-17"
        assert fm["status"] == "active"

    def test_missing_frontmatter(self):
        md = "## Morning Check-in\n\nSome content here.\n"
        assert parse_frontmatter(md) == {}

    def test_partial_frontmatter(self):
        md = "---\nstatus: planning\n---\n\n## Morning Check-in\n"
        fm = parse_frontmatter(md)
        assert fm["status"] == "planning"
        assert "date" not in fm

    def test_quoted_values(self):
        md = '---\ntitle: "My Tuesday"\n---\n'
        fm = parse_frontmatter(md)
        assert fm["title"] == "My Tuesday"

    def test_single_quoted_values(self):
        md = "---\ntitle: 'My Tuesday'\n---\n"
        fm = parse_frontmatter(md)
        assert fm["title"] == "My Tuesday"

    def test_empty_string(self):
        assert parse_frontmatter("") == {}

    def test_no_closing_delimiter(self):
        # Opening --- but no closing --- is not valid frontmatter.
        md = "---\nstatus: active\n\n## Morning Check-in\n"
        assert parse_frontmatter(md) == {}

    def test_lines_without_colon_ignored(self):
        md = "---\nstatus: closed\njust a stray line\n---\n"
        fm = parse_frontmatter(md)
        assert fm["status"] == "closed"
        assert len(fm) == 1

    def test_value_with_colon(self):
        # A value containing a colon (e.g. a time) should keep everything
        # after the first colon.
        md = "---\nclosed-at: 17:42\n---\n"
        fm = parse_frontmatter(md)
        assert fm["closed-at"] == "17:42"


# ---------------------------------------------------------------------------
# set_frontmatter
# ---------------------------------------------------------------------------

class TestSetFrontmatter:
    def test_set_existing_key(self):
        md = "---\nstatus: planning\n---\n\n## Morning Check-in\n"
        result = set_frontmatter(md, "status", "active")
        fm = parse_frontmatter(result)
        assert fm["status"] == "active"
        assert "## Morning Check-in" in result

    def test_add_new_key(self):
        md = "---\nstatus: planning\n---\n\n## Morning Check-in\n"
        result = set_frontmatter(md, "date", "2026-06-17")
        fm = parse_frontmatter(result)
        assert fm["date"] == "2026-06-17"
        assert fm["status"] == "planning"

    def test_create_frontmatter_when_missing(self):
        md = "## Morning Check-in\n\nContent.\n"
        result = set_frontmatter(md, "status", "planning")
        fm = parse_frontmatter(result)
        assert fm["status"] == "planning"
        assert "## Morning Check-in" in result

    def test_create_frontmatter_on_empty(self):
        result = set_frontmatter("", "status", "planning")
        fm = parse_frontmatter(result)
        assert fm["status"] == "planning"

    def test_status_lifecycle_roundtrip(self):
        # planning -> active -> closed, the daily-note lifecycle.
        md = "## Morning Check-in\n\nContent.\n"
        md = set_frontmatter(md, "status", "planning")
        assert parse_frontmatter(md)["status"] == "planning"
        md = set_frontmatter(md, "status", "active")
        assert parse_frontmatter(md)["status"] == "active"
        md = set_frontmatter(md, "status", "closed")
        assert parse_frontmatter(md)["status"] == "closed"
        # Body survives the whole lifecycle.
        assert "## Morning Check-in" in md

    def test_preserves_other_keys_when_updating(self):
        md = "---\ndate: 2026-06-17\nstatus: planning\n---\n\n## Morning Check-in\n"
        result = set_frontmatter(md, "status", "closed")
        fm = parse_frontmatter(result)
        assert fm["date"] == "2026-06-17"
        assert fm["status"] == "closed"


def test_set_frontmatter_first_key_keeps_opening_delimiter_on_own_line():
    """Regression (2026-07-11): replacing the FIRST key of the block glued it
    onto the opening --- ('---status: active'), breaking frontmatter for
    every parser including Obsidian. The old pattern's leading \\s* swallowed
    the newline before the key."""
    from companion.parsers import set_frontmatter, parse_frontmatter
    md = "---\nstatus: planning\n---\n# Note\n"
    out = set_frontmatter(md, "status", "active")
    assert out.startswith("---\nstatus: active\n---\n"), repr(out[:40])
    assert parse_frontmatter(out).get("status") == "active"
    # idempotent on a second write
    out2 = set_frontmatter(out, "status", "closed")
    assert out2.startswith("---\nstatus: closed\n---\n"), repr(out2[:40])


def test_set_weekly_frontmatter_first_key_same_regression():
    from companion.week_parsers import set_weekly_frontmatter
    md = "---\nmode: plan\n---\n# Week\n"
    out = set_weekly_frontmatter(md, "mode", "review")
    assert out.startswith("---\nmode: review\n---\n"), repr(out[:40])


def test_test_vault_seed_top3_rows_are_real_slots(tmp_path, monkeypatch):
    """Seeded '1.' bare rows didn't match _LIST_ITEM_RE, so plan writes
    inserted above them and left junk rows in the note."""
    import companion.testmode as tm
    monkeypatch.setattr(tm, "_TOOLKIT_ROOT", tmp_path)
    vault = tm.ensure_test_vault(seed_today=True)
    from datetime import date
    from companion.parsers import parse_daily_note_sections
    from companion.server import _extract_numbered_checkbox_list_raw
    md = (vault / "01-daily" / f"{date.today().isoformat()}.md").read_text()
    morning = parse_daily_note_sections(md).get("Morning Check-in", "")
    raw = _extract_numbered_checkbox_list_raw(morning, "### My Top 3")
    assert len(raw) == 3 and all(not r["text"] for r in raw)
