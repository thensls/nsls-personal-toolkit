"""Node tests for cowork-logic.js (the artifact's framework-free logic).

Shells `node` to exercise the pure helpers, mirroring test_streak_parity.py.
Skips cleanly if node is unavailable.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

LOGIC_JS = Path(__file__).resolve().parents[2] / "cowork-artifact" / "cowork-logic.js"


def _run(fn_call_js, payload):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    if not LOGIC_JS.exists():
        pytest.fail(f"cowork-logic.js not found at {LOGIC_JS}")
    harness = (
        "const m=require(process.argv[1]);"
        "const input=JSON.parse(require('fs').readFileSync(0,'utf8'));"
        f"process.stdout.write(JSON.stringify({fn_call_js}));"
    )
    proc = subprocess.run([node, "-e", harness, str(LOGIC_JS)],
                          input=json.dumps(payload), capture_output=True, text=True)
    if proc.returncode != 0:
        pytest.fail(f"node failed:\n{proc.stderr}")
    return json.loads(proc.stdout)


SAMPLE_STATE = {
    "schemaVersion": 1, "date": "2026-06-17", "notePath": "01-daily/2026-06-17.md",
    "baseHash": "abc123", "mode": "command", "status": "active", "phase": "active",
    "top3": [
        {"slot": 0, "text": "Spec", "project": "Toolkit", "weekRank": 1, "progress": 75, "disposition": "active"},
        {"slot": 1, "text": "", "project": None, "weekRank": None, "progress": 0, "disposition": "active"},
        {"slot": 2, "text": "Vendor", "project": None, "weekRank": None, "progress": 100, "disposition": "done"},
    ],
    "bonus": [{"text": "PR", "progress": 0, "disposition": "active"}],
    "unplanned": [{"text": "Unblock", "progress": 100, "disposition": "done"}],
    "habits": [{"id": "walk", "name": "Walk", "emoji": "🚶", "percent": 1.0, "streakDays": 12, "status": "ok"}],
    "energy": {"morning": "High", "evening": None},
    "gratitude": "", "dailyInsight": "", "insightReflection": "",
}


def test_serialize_envelope_shape():
    env = _run("m.coworkLogic.serializeForSave(input, {saveId:'sid-1'})", SAMPLE_STATE)
    assert env["type"] == "SAVE_DAY"
    assert env["schemaVersion"] == 1
    assert env["saveId"] == "sid-1"
    assert env["date"] == "2026-06-17"
    assert env["notePath"] == "01-daily/2026-06-17.md"
    assert env["baseHash"] == "abc123"


def test_serialize_preserves_positional_empty_slots():
    env = _run("m.coworkLogic.serializeForSave(input, {saveId:'sid-1'})", SAMPLE_STATE)
    top3 = env["changes"]["top3"]
    assert len(top3) == 3                       # never compacted
    assert top3[1]["slot"] == 1
    assert top3[1]["text"] == ""                # empty slot survives
    assert top3[0]["progress"] == 75
    assert top3[2]["disposition"] == "done"


def test_serialize_reduces_habits():
    env = _run("m.coworkLogic.serializeForSave(input, {saveId:'sid-1'})", SAMPLE_STATE)
    assert env["changes"]["habits"] == [{"id": "walk", "percent": 1.0}]


def test_streak_label_active():
    out = _run("m.coworkLogic.streakLabel(input)", {"streakDays": 12, "status": "ok"})
    assert out == "🔥12"


def test_streak_label_zero_is_blank():
    out = _run("m.coworkLogic.streakLabel(input)", {"streakDays": 0, "status": "ok"})
    assert out == ""


def test_streak_label_reset_is_blank():
    out = _run("m.coworkLogic.streakLabel(input)", {"streakDays": 4, "status": "reset"})
    assert out == ""


def test_serialize_carries_status_transition():
    env = _run("m.coworkLogic.serializeForSave(input, {saveId:'s', statusTransition:'active'})", SAMPLE_STATE)
    assert env["changes"]["statusTransition"] == "active"
