import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("generate_team_pulse", SCRIPTS / "generate_team_pulse.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_extract_support_section():
    gtp = _load()
    text = ("# X\n\n## Signal Read\n\nstuff\n\n## How to Support X\n"
            "**Remove friction:** give her a seat.\n**Celebrate wins:** name the ship.\n\n## Personal\n\nz\n")
    out = gtp.extract_support_section(text)
    assert out is not None
    assert "Remove friction" in out and "seat" in out
    assert "Personal" not in out

def test_extract_support_section_absent():
    gtp = _load()
    assert gtp.extract_support_section("# X\n\n## Personal\n\nz\n") is None
