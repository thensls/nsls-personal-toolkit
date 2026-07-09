import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("synthesize_profile", SCRIPTS / "synthesize_profile.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_how_to_support_instruction_present_with_signal():
    sp = _load()
    data = {"person_name": "Red Akasha", "relationship_type": "direct_report",
            "meeting_summaries": [{"date": "2026-07-01", "title": "1:1", "summary": "x"}],
            "signal": {"wins": [{"week": "2026-06-29", "text": "shipped auth gate"}],
                       "friction": [{"week": "2026-06-29", "text": "excluded from architecture", "category": "process"}],
                       "growth": [{"week": "2026-06-29", "text": "learning graph DBs"}],
                       "sentiment": {}, "goals": [], "submitted_weeks": ["2026-06-29"]}}
    prompt = sp.build_user_prompt(data)
    assert "## How to Support Red Akasha" in prompt
    assert "Remove friction" in prompt and "Celebrate wins" in prompt and "Support growth" in prompt
    assert "Signal source:" in prompt  # provenance-line instruction
    assert "learning graph DBs" in prompt  # growth signal rendered into the prompt

def test_how_to_support_present_from_meetings_without_signal():
    sp = _load()
    data = {"person_name": "Juan Maggi", "relationship_type": "direct_report",
            "meeting_summaries": [{"date": "2026-07-01", "title": "1:1", "summary": "x"}],
            "signal": None}
    prompt = sp.build_user_prompt(data)
    assert "## How to Support Juan Maggi" in prompt

def test_no_support_section_without_any_evidence():
    sp = _load()
    data = {"person_name": "Ghost", "relationship_type": "peer",
            "meeting_summaries": [], "signal": None}
    prompt = sp.build_user_prompt(data)
    assert "## How to Support" not in prompt


def test_how_to_support_survives_many_large_meetings():
    """Regression: with a big meeting set + large existing profile, the prompt
    must stay within MAX_PROMPT_CHARS AND keep the ## How to Support directive
    (previously it fell off the truncated tail)."""
    sp = _load()
    big_summary = "word " * 3000  # ~15k chars each
    meetings = [{"date": f"2026-06-{d:02d}", "title": f"SLT Huddle {d}", "summary": big_summary}
                for d in range(1, 16)]  # 15 meetings, ~225k chars unbounded
    data = {"person_name": "Chelsea Byers", "relationship_type": "direct_report",
            "meeting_summaries": meetings,
            "existing_profile": "## Kevin's Private Note\n\n" + ("keep " * 8000),
            "signal": {"wins": [{"week": "2026-06-29", "text": "shipped"}],
                       "friction": [], "growth": [{"week": "2026-06-29", "text": "learning"}],
                       "sentiment": {}, "goals": [], "submitted_weeks": ["2026-06-29"]}}
    prompt = sp.build_user_prompt(data)
    assert len(prompt) <= sp.MAX_PROMPT_CHARS, f"prompt {len(prompt)} exceeds cap"
    assert "## How to Support Chelsea Byers" in prompt
    # older meetings trimmed, most-recent kept
    assert "of 15 meetings" in prompt
