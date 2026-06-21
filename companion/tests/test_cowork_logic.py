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


def test_cycle_progress_steps():
    assert _run("m.coworkLogic.cycleProgress(input)", 0) == 25
    assert _run("m.coworkLogic.cycleProgress(input)", 25) == 50
    assert _run("m.coworkLogic.cycleProgress(input)", 75) == 100
    assert _run("m.coworkLogic.cycleProgress(input)", 100) == 0


def test_toggle_disposition_sets_and_clears():
    item = {"text": "x", "progress": 50, "disposition": "active"}
    done = _run("m.coworkLogic.toggleDisposition(input, 'done')", item)
    assert done["disposition"] == "done"
    assert done["progress"] == 50            # progress preserved
    cleared = _run("m.coworkLogic.toggleDisposition(input, 'done')",
                   {"text": "x", "progress": 50, "disposition": "done"})
    assert cleared["disposition"] == "active"  # tapping the same target clears it


def test_toggle_disposition_is_mutually_exclusive():
    item = {"text": "x", "progress": 0, "disposition": "done"}
    deleted = _run("m.coworkLogic.toggleDisposition(input, 'deleted')", item)
    assert deleted["disposition"] == "deleted"  # replaces done, not additive


STATE_FOR_STATS = {
    "top3": [
        {"text": "a", "progress": 100, "disposition": "done"},
        {"text": "b", "progress": 50,  "disposition": "active"},
        {"text": "",  "progress": 0,   "disposition": "active"},   # empty slot — not counted
    ],
    "habits": [{"id": "w", "percent": 1.0}, {"id": "r", "percent": 0.0}],
    "status": "active", "phase": "active", "mode": "command",
}


def test_day_stats():
    s = _run("m.coworkLogic.dayStats(input)", STATE_FOR_STATS)
    assert s["top3Total"] == 2          # empty slot excluded
    assert s["top3Done"] == 1
    assert s["habitsDone"] == 1
    assert s["habitsTotal"] == 2


def test_transition_lock_in():
    s = _run("m.coworkLogic.transition(input, 'lock-in')",
             {"status": "planning", "phase": "planning", "mode": "coach-morning"})
    assert s["status"] == "active" and s["phase"] == "active" and s["mode"] == "command"


def test_transition_close_day():
    s = _run("m.coworkLogic.transition(input, 'close-day')",
             {"status": "active", "phase": "active", "mode": "command"})
    assert s["phase"] == "closing" and s["mode"] == "coach-evening"
    assert s["status"] == "active"      # not closed until finish


def test_transition_finish_close():
    s = _run("m.coworkLogic.transition(input, 'finish-close')",
             {"status": "active", "phase": "closing", "mode": "coach-evening"})
    assert s["status"] == "closed" and s["mode"] == "results"
