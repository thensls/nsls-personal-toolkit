"""JS <-> Python streak-rule parity (Phase 1.2, spec O3).

The canonical streak rule lives in Python (`companion/streak.py`) plus the
prose in close-day/SKILL.md. The cowork artifact embeds a JS display copy
(`cowork-artifact/streak.js`). This test guards against the two drifting:
it feeds the six canonical sequences (the same ones in test_streak.py) to
BOTH implementations and asserts they agree on `computeConcern`, `statusFor`,
and `streakDays`.

The JS side is exercised by shelling out to `node` with a tiny harness that
reads the sequences from stdin as JSON and prints the JS results as JSON. If
`node` isn't available the test is skipped (CI without Node still passes the
rest of the suite), but locally Node is present so drift is caught.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from companion.streak import DayResult, compute_concern, status_for, streak_days

STREAK_JS = Path(__file__).resolve().parents[2] / "cowork-artifact" / "streak.js"

# The six canonical sequences (a-f) from test_streak.py, plus the three extra
# edge cases that test_streak.py also asserts. Each is a list of percents in
# chronological order (oldest first), exactly how the Python log is ordered.
CANONICAL_SEQUENCES = {
    "a_five_hits": [1.0, 1.0, 1.0, 1.0, 1.0],
    "b_partial_middle_then_full": [1.0, 1.0, 0.5, 1.0, 1.0],
    "c_two_partials_one_miss": [1.0, 0.5, 0.5],
    "d_three_partials_at_risk": [0.5, 0.5, 0.5],
    "e_four_partials_reset": [0.5, 0.5, 0.5, 0.5],
    "f_two_misses_reset": [1.0, 0.0, 0.0],
    "mixed_miss_then_partial": [0.0, 0.5],
    "full_day_mid_chain_clears": [0.5, 0.5, 1.0, 0.5],
    "empty": [],
}


def _python_results(percents):
    log = [DayResult(date=f"2026-05-{10 + i:02d}", percent=p)
           for i, p in enumerate(percents)]
    concern = compute_concern(log)
    return {
        "concern": concern,
        "status": status_for(concern),
        "streak_days": streak_days(log),
    }


# A node harness that imports streak.js, runs each named sequence through the
# three functions, and prints {name: {concern, status, streak_days}} as JSON.
_NODE_HARNESS = r"""
// With `node -e SCRIPT ARG`, the eval script is not in argv; the first extra
// arg lands at argv[1].
const path = process.argv[1];
const mod = require(path);
const sequences = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const [name, percents] of Object.entries(sequences)) {
  const log = percents.map((p, i) => ({ date: `2026-05-${10 + i}`, percent: p }));
  const concern = mod.computeConcern(log);
  out[name] = {
    concern: concern,
    status: mod.statusFor(concern),
    streak_days: mod.streakDays(log),
  };
}
process.stdout.write(JSON.stringify(out));
"""


def _js_results():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available — JS parity check skipped")
    if not STREAK_JS.exists():
        pytest.fail(f"streak.js not found at {STREAK_JS}")
    proc = subprocess.run(
        [node, "-e", _NODE_HARNESS, str(STREAK_JS)],
        input=json.dumps(CANONICAL_SEQUENCES),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        pytest.fail(f"node harness failed:\n{proc.stderr}")
    return json.loads(proc.stdout)


def test_js_python_streak_parity():
    js = _js_results()
    for name, percents in CANONICAL_SEQUENCES.items():
        py = _python_results(percents)
        assert name in js, f"JS missing result for {name}"
        assert js[name]["concern"] == py["concern"], (
            f"concern mismatch on {name}: js={js[name]['concern']} py={py['concern']}"
        )
        assert js[name]["status"] == py["status"], (
            f"status mismatch on {name}: js={js[name]['status']} py={py['status']}"
        )
        assert js[name]["streak_days"] == py["streak_days"], (
            f"streak_days mismatch on {name}: "
            f"js={js[name]['streak_days']} py={py['streak_days']}"
        )
