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
    # ActionBar replaced the 2.1 SaveBar (Save progress + Close Day).
    for comp in ("Disc", "TaskRow", "Panel", "HabitChip", "Header", "ActionBar"):
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


def test_command_center_has_both_action_buttons():
    src = JSX.read_text()
    assert "Save progress" in src
    assert "Close Day" in src


def test_active_command_center_has_no_closing_copy():
    # The "type done to close" instruction must not appear in the active banner.
    src = JSX.read_text()
    assert "mark progress any time" in src
    before = src.split("mark progress any time")[0][-200:]
    assert "Type" not in before and "type done" not in before.lower()


def test_close_day_transitions_via_logic():
    src = JSX.read_text()
    assert "onCloseDay" in src
    assert "transition" in src and "close-day" in src


def test_morning_has_done_button_and_energy():
    src = JSX.read_text()
    assert "MorningCoachCards" in src
    assert "onLockIn" in src
    assert "Done" in src               # plain "Done" CTA (Davo: prefer "Done")
    assert "energy" in src.lower()
    assert "Morning Coach Cards — stub" not in src   # no longer a stub
    assert "EnergyPicker" in src                     # real energy control


def test_evening_has_close_flow():
    src = JSX.read_text()
    assert "EveningCoachCards" in src
    assert "Evening Coach Cards — stub" not in src   # no longer a stub
    assert "onFinishClose" in src
    assert "dayStats" in src                          # stats recap
    assert "gratitude" in src.lower()
    assert "reflection" in src.lower()
    # the closing instruction lives HERE (evening), not in the active CC
    assert "Closing the day" in src


def test_results_is_readonly_summary():
    src = JSX.read_text()
    assert 'data-mode="results"' in src
    assert "Results — stub" not in src   # no longer a stub
    # both energies surfaced in results
    assert "evening" in src and "morning" in src


def test_taskrow_has_disposition_controls():
    src = JSX.read_text()
    assert "toggleDisposition" in src
    assert "onItemChange" in src
