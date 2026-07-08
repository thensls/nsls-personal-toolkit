import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("fetch_signal", SCRIPTS / "fetch_signal.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_normalize_history_includes_growth():
    fs = _load()
    hist = {"history": [{"week_of": "2026-06-29", "extraction": {
        "wins": [{"description": "shipped X"}],
        "challenges": [],
        "growth": [{"description": "learning graph DBs"}],
    }}]}
    out = fs.normalize_history(hist)
    assert any(g["text"] == "learning graph DBs" for g in out["growth"])

def test_strip_work_journal_removes_narrative():
    fs = _load()
    bundle = {"history": {"history": [
        {"week_of": "2026-06-29", "narration_raw": "PRIVATE JOURNAL",
         "entry_text": "PRIVATE", "extraction": {"wins": [{"description": "shipped X"}]}}
    ]}}
    clean = fs.strip_work_journal(bundle)
    wk = clean["history"]["history"][0]
    assert "narration_raw" not in wk and "entry_text" not in wk
    assert wk["extraction"]["wins"][0]["description"] == "shipped X"  # signal kept
