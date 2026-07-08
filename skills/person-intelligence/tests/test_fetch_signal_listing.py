import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("fetch_signal", SCRIPTS / "fetch_signal.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_list_signal_slugs_filters_eligible(monkeypatch):
    fs = _load()
    fake = {"relationships": [
        {"name": "Adam Stone", "signal_eligible": True},
        {"name": "Cory Capoccia", "signal_eligible": False},
        {"name": "Report A", "signal_eligible": True},
    ]}
    monkeypatch.setattr(fs, "_relationships_json", lambda: fake)
    slugs = fs.list_signal_slugs()
    names = {s["name"] for s in slugs}
    assert names == {"Adam Stone", "Report A"}
    assert {"name": "Adam Stone", "slug": "adam-stone"} in slugs
