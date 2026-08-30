import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load():
    spec = importlib.util.spec_from_file_location("fetch_signal", SCRIPTS / "fetch_signal.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_list_signal_slugs_filters_eligible(monkeypatch):
    fs = _load()
    fake = {"relationships": [
        {"name": "Adam Ferris", "signal_eligible": True},
        {"name": "Dana Ashford", "signal_eligible": False},
        {"name": "Report A", "signal_eligible": True},
    ]}
    monkeypatch.setattr(fs, "_relationships_json", lambda: fake)
    slugs = fs.list_signal_slugs()
    names = {s["name"] for s in slugs}
    assert names == {"Adam Ferris", "Report A"}
    assert {"name": "Adam Ferris", "slug": "adam-stone"} in slugs


def test_list_signal_slugs_collision_still_lists_both_and_warns(monkeypatch, capsys):
    fs = _load()
    fake = {"relationships": [
        {"name": "Sam Lee", "signal_eligible": True},
        {"name": "Sam Lee", "signal_eligible": True, "tracking_reason": "key_relationship"},
    ]}
    monkeypatch.setattr(fs, "_relationships_json", lambda: fake)
    slugs = fs.list_signal_slugs()
    # Not silently overwritten — both entries still returned.
    assert len(slugs) == 2
    assert all(s["slug"] == "sam-lee" for s in slugs)
    # Collision is surfaced, not silent.
    captured = capsys.readouterr()
    assert "collision" in captured.err.lower() or "WARNING" in captured.err
