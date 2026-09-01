#!/usr/bin/env python3
"""Tests for the role-coach cue pool in surface_actions_for_day.py.

The arbiter contract (role-coach plan, Phase 2):
  - Role-coach emits cue candidates to <role-cache>/cues.json
  - The surfacer admits AT MOST ONE role-coach cue per run
  - Totals stay within the hard caps (3 daily / 5 weekly):
    person-intelligence actions fill cap-1 slots when a role cue surfaces
  - Cue decay mirrors the action decay model (times_surfaced >= 3 -> stale)
  - Expired cues never surface
  - A role cue surfaces even when coaching_actions.json doesn't exist

Run: python3 -m pytest test_surface_actions_role_cues.py -q
"""

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "surface_actions_for_day.py"

TODAY = date.today().isoformat()
NEXT_WEEK = (date.today() + timedelta(days=7)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def make_actions_cache(cache_dir: Path, n_actions: int):
    """Person-intelligence cache with n pending actions across n people."""
    data = {
        f"Person {i}": {
            "relationship_type": "direct_report",
            "actions": [
                {
                    "text": f"action {i}",
                    "status": "pending",
                    "priority": 50,
                    "times_surfaced": 0,
                    "relationship_type": "direct_report",
                }
            ],
        }
        for i in range(n_actions)
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "coaching_actions.json").write_text(json.dumps(data))


def make_cues(role_dir: Path, cues):
    role_dir.mkdir(parents=True, exist_ok=True)
    (role_dir / "cues.json").write_text(json.dumps({"cues": cues}))


def cue(pattern_id="P001", text="🪑 Role: test cue", created=TODAY,
        expires=NEXT_WEEK, status="pending", times_surfaced=0):
    return {
        "id": f"{pattern_id}-{created}",
        "pattern_id": pattern_id,
        "text": text,
        "lens": "floor",
        "created": created,
        "expires": expires,
        "status": status,
        "times_surfaced": times_surfaced,
        "last_surfaced": None,
    }


def run(tmp_path: Path, *extra_args):
    cache_dir = tmp_path / "pi"
    role_dir = tmp_path / "rc"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--cache-dir", str(cache_dir),
         "--role-cache-dir", str(role_dir),
         "--people", "Person 0",
         *extra_args],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_no_cues_file_role_cue_null(tmp_path):
    make_actions_cache(tmp_path / "pi", 2)
    result = run(tmp_path)
    assert result["role_cue"] is None
    assert len(result["surfaced_actions"]) == 2


def test_role_cue_takes_one_slot_within_daily_cap(tmp_path):
    make_actions_cache(tmp_path / "pi", 5)  # more than enough to fill the cap
    make_cues(tmp_path / "rc", [cue()])
    result = run(tmp_path)
    assert result["role_cue"]["pattern_id"] == "P001"
    # total stays at the daily cap of 3: 1 role cue + 2 actions
    assert len(result["surfaced_actions"]) == 2


def test_weekly_cap_holds_with_role_cue(tmp_path):
    make_actions_cache(tmp_path / "pi", 8)
    make_cues(tmp_path / "rc", [cue()])
    result = run(tmp_path, "--weekly")
    assert result["role_cue"] is not None
    assert len(result["surfaced_actions"]) == 4  # 5 cap - 1 role slot


def test_at_most_one_role_cue(tmp_path):
    make_actions_cache(tmp_path / "pi", 1)
    make_cues(tmp_path / "rc", [cue("P001"), cue("P002"), cue("P003")])
    result = run(tmp_path)
    assert result["role_cue"] is not None  # exactly one, even with slots free
    assert len(result["surfaced_actions"]) == 1


def test_expired_and_stale_cues_skipped(tmp_path):
    make_actions_cache(tmp_path / "pi", 1)
    make_cues(tmp_path / "rc", [
        cue("P001", expires=YESTERDAY),            # expired
        cue("P002", times_surfaced=3),             # decayed
        cue("P003", status="done"),                # not pending
    ])
    result = run(tmp_path)
    assert result["role_cue"] is None


def test_surfacing_increments_and_persists(tmp_path):
    make_actions_cache(tmp_path / "pi", 1)
    make_cues(tmp_path / "rc", [cue("P001")])
    run(tmp_path)
    saved = json.loads((tmp_path / "rc" / "cues.json").read_text())
    c = saved["cues"][0]
    assert c["times_surfaced"] == 1
    assert c["last_surfaced"] == TODAY
    # third surfacing marks it stale (decay parity with actions)
    run(tmp_path)
    run(tmp_path)
    saved = json.loads((tmp_path / "rc" / "cues.json").read_text())
    assert saved["cues"][0]["times_surfaced"] == 3
    result = run(tmp_path)
    assert result["role_cue"] is None
    saved = json.loads((tmp_path / "rc" / "cues.json").read_text())
    assert saved["cues"][0]["status"] == "stale"


def test_role_cue_without_actions_cache(tmp_path):
    # No coaching_actions.json at all — role cue must still surface
    make_cues(tmp_path / "rc", [cue("P001")])
    result = run(tmp_path)
    assert result["role_cue"]["pattern_id"] == "P001"
    assert result["surfaced_actions"] == []


def test_no_cache_no_cues_keeps_hint(tmp_path):
    # Original empty-state behavior preserved
    result = run(tmp_path)
    assert result["role_cue"] is None
    assert result["surfaced_actions"] == []
    assert result.get("hint") == "no_cache"
