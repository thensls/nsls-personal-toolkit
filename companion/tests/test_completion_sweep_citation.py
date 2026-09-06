"""The citation contract behind open-day step 2n (completed-work sweep).

2n tells the skill to pre-check already-shipped work AND to cite the evidence
inline so the builder can audit the call. Those two requirements are coupled
through `_clean_ai_item`, and the coupling is not obvious: a dash-led citation
is truncated out of the stored text, so it vanishes from the rendered row as
well as the matching key, leaving exactly the unauditable "likely done" row the
rule exists to prevent.

These tests pin the behaviour the doc documents, so the doc cannot rot against
the code silently.
"""

import pathlib

from companion.server import _build_plan_context, _extract_ai_suggestions

CITED = 'Ship the reporting skill (quicknote 2026-08-15: "shipped")'
DASHED = 'Ship the reporting skill — quicknote 2026-08-15: "shipped"'


def _note(candidate: str, done_line: str) -> str:
    return (
        "## Morning Check-in\n\n"
        "### AI Suggested: Likely already done\n"
        f"1. {candidate}\n\n"
        "### Done\n"
        f"- {done_line}\n"
    )


def _vault(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "01-daily").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_dash_led_citation_is_stripped_from_the_rendered_row():
    """Why 2n mandates parentheses: the dash form loses the evidence."""
    got = _extract_ai_suggestions(_note(DASHED, "irrelevant"))
    assert got[0]["text"] == "Ship the reporting skill"
    assert "quicknote" not in got[0]["text"]


def test_parenthetical_citation_survives_into_the_rendered_row():
    got = _extract_ai_suggestions(_note(CITED, "irrelevant"))
    assert got[0]["text"] == CITED


def test_cited_candidate_pre_checks_when_done_line_matches_in_full(tmp_path):
    ctx = _build_plan_context(_note(CITED, CITED), _vault(tmp_path),
                              "2026-09-05", [], [])
    assert ctx["suggestions"][0]["taken"] == "done"


def test_done_line_trimmed_to_bare_text_does_not_match(tmp_path):
    """The comparison is exact — no normalisation on this path."""
    ctx = _build_plan_context(_note(CITED, "Ship the reporting skill"),
                              _vault(tmp_path), "2026-09-05", [], [])
    assert ctx["suggestions"][0]["taken"] is None
