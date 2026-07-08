"""Regression tests for _set_nth_item_text (Macroscope review on #30).

Two distinct bugs this covers:
  - Renaming an existing item must NOT drop trailing progress/estimate markers
    (<!--p:..-->/<!--e:..-->) — editing a title silently reset saved progress
    and the remaining-time estimate.
  - When the target heading is missing, `index` must be honored (blank rows for
    slots 0..index-1) instead of always writing to slot 0.
"""

from companion.server import _set_nth_item_text


def test_rename_preserves_progress_and_estimate_markers():
    md = "## Morning Check-in\n\n### My Top 3\n1. [ ] old title <!--p:50--> <!--e:1.5-->\n"
    out = _set_nth_item_text(md, "### My Top 3", 0, "new title")
    assert "new title" in out and "old title" not in out
    assert "<!--p:50-->" in out  # progress preserved
    assert "<!--e:1.5-->" in out  # estimate preserved


def test_rename_preserves_checkbox_state():
    md = "## Morning Check-in\n\n### My Top 3\n1. [x] done task <!--p:100-->\n"
    out = _set_nth_item_text(md, "### My Top 3", 0, "renamed")
    assert "1. [x] renamed" in out
    assert "<!--p:100-->" in out


def test_missing_heading_honors_index():
    md = "## Morning Check-in\n\n### My Top 3\n1. [ ] existing\n"
    out = _set_nth_item_text(md, "### Unplanned", 2, "foo")
    assert "### Unplanned" in out
    # foo lands at slot index=2 (item 3), with blank rows 1 and 2 created
    assert "3. [ ] foo" in out
    lines = out.splitlines()
    assert "1. [ ] " in lines and "2. [ ] " in lines


def test_missing_heading_index_zero_unchanged():
    md = "## Morning Check-in\n\n### My Top 3\n1. [ ] x\n"
    out = _set_nth_item_text(md, "### Unplanned", 0, "bar")
    assert "1. [ ] bar" in out
