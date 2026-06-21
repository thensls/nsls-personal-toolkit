"""Structural tests for the cowork-dashboard artifact source.

The .jsx is verified visually in a real cowork session; here we only assert the
machine-checkable invariants: the inlined logic matches cowork-logic.js (drift
guard), the four modes are wired, and the brand tokens / constraints are present.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "cowork-artifact"
JSX = ROOT / "cowork-dashboard.jsx"
LOGIC = ROOT / "cowork-logic.js"


def _sentinel_block(text):
    m = re.search(r"// === COWORK-LOGIC:BEGIN ===\n(.*?)\n// === COWORK-LOGIC:END ===",
                  text, re.DOTALL)
    return m.group(1) if m else None


def test_jsx_exists():
    assert JSX.exists()


def test_inlined_logic_matches_source():
    jsx_block = _sentinel_block(JSX.read_text())
    logic_block = _sentinel_block(LOGIC.read_text())
    assert jsx_block is not None, "no COWORK-LOGIC sentinel block in the .jsx"
    assert logic_block is not None, "no COWORK-LOGIC sentinel block in cowork-logic.js"
    assert jsx_block == logic_block, "inlined logic has drifted from cowork-logic.js"


def test_routes_all_four_modes():
    src = JSX.read_text()
    for mode in ("coach-morning", "command", "coach-evening", "results"):
        assert mode in src, f"mode {mode} not referenced"
    for comp in ("MorningCoachCards", "CommandCenter", "EveningCoachCards", "Results"):
        assert comp in src, f"component {comp} not defined"


def test_sample_state_has_contract_fields():
    src = JSX.read_text()
    for field in ("schemaVersion", "mode", "status", "phase", "top3", "habits", "baseHash"):
        assert field in src, f"SAMPLE missing {field}"


def test_brand_tokens_present():
    src = JSX.read_text()
    for hexv in ("#18315A", "#0091AE", "#EEB117"):  # navy, teal, gold
        assert hexv in src, f"brand color {hexv} missing"


def test_font_stack_has_no_cdn_import():
    src = JSX.read_text()
    assert "Lexend Deca" in src
    assert "fonts.googleapis" not in src and "@import" not in src


def test_primitives_defined():
    src = JSX.read_text()
    for comp in ("Disc", "TaskRow", "Panel", "HabitChip", "Header", "SaveBar"):
        assert comp in src, f"primitive {comp} not defined"


def test_save_uses_sendprompt_envelope():
    src = JSX.read_text()
    assert "serializeForSave" in src
    assert "sendPrompt(" in src
    assert "SAVE_DAY " in src  # the chat-message prefix Claude parses


def test_draft_persistence_with_fallback():
    src = JSX.read_text()
    assert "localStorage" in src              # local draft (no chat turn)
    # graceful fallback when localStorage is unavailable in the runtime
    assert "typeof localStorage" in src or "try" in src


def test_dirty_indicator_wired():
    src = JSX.read_text()
    assert "dirty" in src
