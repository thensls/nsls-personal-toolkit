import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("synthesize_profile", SCRIPTS / "synthesize_profile.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_how_to_support_instruction_present_with_signal():
    sp = _load()
    data = {"person_name": "Robin Alder", "relationship_type": "direct_report",
            "meeting_summaries": [{"date": "2026-07-01", "title": "1:1", "summary": "x"}],
            "signal": {"wins": [{"week": "2026-06-29", "text": "shipped auth gate"}],
                       "friction": [{"week": "2026-06-29", "text": "excluded from architecture", "category": "process"}],
                       "growth": [{"week": "2026-06-29", "text": "learning graph DBs"}],
                       "sentiment": {}, "goals": [], "submitted_weeks": ["2026-06-29"]}}
    prompt = sp.build_user_prompt(data)
    assert "## How to Support Robin Alder" in prompt
    assert "Remove friction" in prompt and "Celebrate wins" in prompt and "Support growth" in prompt
    assert "Signal source:" in prompt  # provenance-line instruction
    assert "learning graph DBs" in prompt  # growth signal rendered into the prompt

def test_how_to_support_present_from_meetings_without_signal():
    sp = _load()
    data = {"person_name": "Juan Salinas", "relationship_type": "direct_report",
            "meeting_summaries": [{"date": "2026-07-01", "title": "1:1", "summary": "x"}],
            "signal": None}
    prompt = sp.build_user_prompt(data)
    assert "## How to Support Juan Salinas" in prompt

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
    data = {"person_name": "Rhea Ward", "relationship_type": "direct_report",
            "meeting_summaries": meetings,
            "existing_profile": "## Marcus's Private Note\n\n" + ("keep " * 8000),
            "signal": {"wins": [{"week": "2026-06-29", "text": "shipped"}],
                       "friction": [], "growth": [{"week": "2026-06-29", "text": "learning"}],
                       "sentiment": {}, "goals": [], "submitted_weeks": ["2026-06-29"]}}
    prompt = sp.build_user_prompt(data)
    assert len(prompt) <= sp.MAX_PROMPT_CHARS, f"prompt {len(prompt)} exceeds cap"
    assert "## How to Support Rhea Ward" in prompt
    # older meetings trimmed, most-recent kept
    assert "of 15 meetings" in prompt


def test_meeting_budget_keeps_most_recent_prefix():
    """break (not continue): once a meeting overflows the budget we stop, keeping a
    most-recent contiguous prefix — we must not skip a newer meeting to fit an older."""
    sp = _load()
    meetings = [
        {"date": "2026-07-03", "title": "NEWEST", "summary": "a" * 20000},
        {"date": "2026-07-01", "title": "MIDDLE", "summary": "b" * 40000},
        {"date": "2026-06-01", "title": "OLDEST", "summary": "c" * 5000},
    ]
    data = {"person_name": "X", "relationship_type": "peer",
            "meeting_summaries": meetings, "signal": None}
    prompt = sp.build_user_prompt(data)
    assert "NEWEST" in prompt
    assert "OLDEST" not in prompt  # would only appear if we skipped MIDDLE (the bug)
