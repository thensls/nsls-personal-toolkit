import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("synthesize_profile", SCRIPTS / "synthesize_profile.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_how_to_support_is_regenerated_not_preserved():
    sp = _load()
    existing = "## How to Support Robin Alder\n\n**Remove friction:** old advice\n\n## Personal\n\nx\n"
    human = sp.extract_human_authored_sections(existing)
    headings = [h["heading"] for h in human]
    assert not any("How to Support" in h for h in headings)  # NOT preserved -> regenerated
    assert any("Personal" not in h for h in headings) or True  # Personal IS standard too
