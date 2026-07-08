"""Regression tests for _set_nth_item_text (Macroscope review on #30).

Marker semantics (progress <!--p:..--> / estimate <!--e:..-->):
  - Rewriting an item with the SAME title (e.g. a checkbox toggle) preserves
    its markers.
  - A genuine rename — or a cleared slot reused by a NEW task — must DROP the
    markers, so the new task doesn't inherit the old one's progress/estimate.
And when the target heading is missing, `index` must be honored (blank rows for
slots 0..index-1) instead of always writing to slot 0.
"""

from companion.server import _set_nth_item_text


def test_same_title_preserves_markers():
    md = "## Morning Check-in\n\n### My Top 3\n1. [ ] ship the thing <!--p:50--> <!--e:1.5-->\n"
    out = _set_nth_item_text(md, "### My Top 3", 0, "ship the thing")
    assert "<!--p:50-->" in out   # unchanged title → progress kept
    assert "<!--e:1.5-->" in out  # estimate kept


def test_rename_drops_markers():
    md = "## Morning Check-in\n\n### My Top 3\n1. [ ] old title <!--p:50--> <!--e:1.5-->\n"
    out = _set_nth_item_text(md, "### My Top 3", 0, "a different task")
    assert "a different task" in out and "old title" not in out
    # Different title → do NOT inherit the previous task's progress/estimate.
    assert "<!--p:50-->" not in out
    assert "<!--e:1.5-->" not in out


def test_rename_keeps_checkbox_state_but_drops_progress():
    md = "## Morning Check-in\n\n### My Top 3\n1. [x] done task <!--p:100-->\n"
    out = _set_nth_item_text(md, "### My Top 3", 0, "renamed task")
    assert "1. [x] renamed task" in out  # checkbox state preserved
    assert "<!--p:100-->" not in out      # but stale progress dropped


def test_missing_heading_honors_index():
    md = "## Morning Check-in\n\n### My Top 3\n1. [ ] existing\n"
    out = _set_nth_item_text(md, "### Unplanned", 2, "foo")
    assert "### Unplanned" in out
    assert "3. [ ] foo" in out
    lines = out.splitlines()
    assert "1. [ ] " in lines and "2. [ ] " in lines


def test_missing_heading_index_zero_unchanged():
    md = "## Morning Check-in\n\n### My Top 3\n1. [ ] x\n"
    out = _set_nth_item_text(md, "### Unplanned", 0, "bar")
    assert "1. [ ] bar" in out
