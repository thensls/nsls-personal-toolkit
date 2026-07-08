import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def test_gate_uses_eligibility_not_direct_report_only():
    bws = _load("biweekly_sweep")
    # a peer that is signal_eligible should be planned when signal is available
    rel = {"name": "Adam Stone", "email": "astone@nsls.org",
           "tracking_reason": "peer", "signal_eligible": True}
    planned = bws.plan_signal(rel, signal_available=True)
    assert planned["signal_ingest_planned"] is True
    assert planned["signal_slug"] == "adam-stone"
    # ineligible person never planned
    rel2 = {"name": "Cory Capoccia", "email": "ccapoccia@nsls.org",
            "tracking_reason": "key_relationship", "signal_eligible": False}
    assert bws.plan_signal(rel2, signal_available=True)["signal_ingest_planned"] is False


def test_plan_signal_computes_eligibility_when_untagged():
    bws = _load("biweekly_sweep")
    # sweep-path dict: no signal_eligible key set (build_manifest builds inline)
    rel = {"name": "Adam Stone", "email": "astone@nsls.org", "tracking_reason": "peer"}
    out = bws.plan_signal(rel, signal_available=True)
    assert out["signal_ingest_planned"] is True
    assert out["signal_slug"] == "adam-stone"
    assert out["signal_eligible"] is True
    # ineligible external, untagged
    rel2 = {"name": "Ext", "email": "", "tracking_reason": "key_relationship_external"}
    assert bws.plan_signal(rel2, signal_available=True)["signal_ingest_planned"] is False
