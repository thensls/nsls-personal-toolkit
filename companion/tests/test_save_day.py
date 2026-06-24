"""Tests for the canonical SAVE_DAY save handler (Phase 3, build plan §3.2/3.3).

`apply_save_day` is the executable spec for the cowork artifact's save channel.
The cowork surface has no Python runtime — there, Claude follows the SKILL.md
prose that describes THIS algorithm. The CLI/web companion can call it for real.
One source of truth, exactly like streak.py is canonical for streak.js.

Contract (from docs/specs/2026-06-21-cowork-dashboard-2.1-design.md "Save protocol"):
  1. Validate the envelope. Malformed / schemaVersion-mismatch -> refuse, no write.
  2. Idempotency: a saveId already applied this session -> noop.
  3. Re-read the LATEST note (the caller passes it in); compute its hash.
  4. hash == baseHash -> apply `changes` as a field-level patch, whole-file write.
  5. hash != baseHash -> still patch onto the LATEST content (only the fields in
     `changes`), preserving every section the artifact didn't touch; flag drift.
  6. Whole-file replace, NEVER delete (cowork gates rm). Untouched sections survive.
"""

import copy

from companion.parsers import apply_save_day, compute_note_hash


# A realistic daily note mid-day: planned in the morning, has sections the
# artifact never sees (Calendar, Work Log, AI Suggested) that must survive.
BASE_NOTE = """\
---
status: active
---
# 2026-06-17 — Wednesday

## Morning Check-in
- Energy: high

### AI Suggested: Top 3 (from Tuesday's close)
1. **Finish the toolkit spec** — only you can do this.
2. **Q3 LOP draft** — strategic.
3. **Reply to vendor** — unblocks billing.

### My Top 3
1. [ ] Finish the toolkit spec
2. [ ] Q3 LOP draft
3. [ ] Reply to vendor

### Bonus
1. [ ] Review Red's PR

### Habits
- [ ] **Walk**
- [ ] **Read 15m**
- [ ] **Workout**

## Calendar
- **09:00-10:00** — Standup (team)
- **14:00-15:00** — Focus: toolkit spec <- *scheduled by /open-day*

## Work Log
-

## End of Day
- Energy:
"""


def _envelope(**changes):
    """Build a well-formed SAVE_DAY envelope against BASE_NOTE."""
    base = {
        "type": "SAVE_DAY",
        "schemaVersion": 1,
        "saveId": "2026-06-17-1",
        "date": "2026-06-17",
        "notePath": "01-daily/2026-06-17.md",
        "baseHash": compute_note_hash(BASE_NOTE),
        "changes": {
            "top3": [
                {"slot": 0, "text": "Finish the toolkit spec", "progress": 0, "disposition": "active"},
                {"slot": 1, "text": "Q3 LOP draft", "progress": 0, "disposition": "active"},
                {"slot": 2, "text": "Reply to vendor", "progress": 0, "disposition": "active"},
            ],
            "bonus": [{"text": "Review Red's PR", "progress": 0, "disposition": "active"}],
            "unplanned": [],
            "habits": [
                {"id": "walk", "percent": 0.0},
                {"id": "read15", "percent": 0.0},
                {"id": "workout", "percent": 0.0},
            ],
            "energy": {"morning": "high"},
            "gratitude": "",
            "dailyInsight": "",
            "insightReflection": "",
            "statusTransition": None,
        },
    }
    base["changes"].update(changes)
    return base


# ---------------------------------------------------------------------------
# compute_note_hash — the conflict-detection primitive
# ---------------------------------------------------------------------------

class TestComputeNoteHash:
    def test_stable(self):
        assert compute_note_hash(BASE_NOTE) == compute_note_hash(BASE_NOTE)

    def test_changes_with_content(self):
        assert compute_note_hash(BASE_NOTE) != compute_note_hash(BASE_NOTE + "x")

    def test_sixteen_hex_chars(self):
        h = compute_note_hash(BASE_NOTE)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# Step 1 — envelope validation (malformed -> refuse, never write)
# ---------------------------------------------------------------------------

class TestValidation:
    def test_wrong_type_refuses(self):
        env = _envelope()
        env["type"] = "SAVE_WEEK"
        r = apply_save_day(BASE_NOTE, env, set())
        assert r["action"] == "refuse"
        assert r["note_md"] == BASE_NOTE  # untouched

    def test_schema_version_mismatch_refuses(self):
        env = _envelope()
        env["schemaVersion"] = 2
        r = apply_save_day(BASE_NOTE, env, set())
        assert r["action"] == "refuse"
        assert r["note_md"] == BASE_NOTE

    def test_missing_changes_refuses(self):
        env = _envelope()
        del env["changes"]
        r = apply_save_day(BASE_NOTE, env, set())
        assert r["action"] == "refuse"
        assert r["note_md"] == BASE_NOTE

    def test_missing_save_id_refuses(self):
        env = _envelope()
        del env["saveId"]
        r = apply_save_day(BASE_NOTE, env, set())
        assert r["action"] == "refuse"

    def test_not_a_dict_refuses(self):
        r = apply_save_day(BASE_NOTE, "SAVE_DAY not-json", set())
        assert r["action"] == "refuse"
        assert r["note_md"] == BASE_NOTE

    def test_refuse_has_human_message(self):
        env = _envelope()
        env["schemaVersion"] = 99
        r = apply_save_day(BASE_NOTE, env, set())
        assert r["message"]  # non-empty explanation for the user


# ---------------------------------------------------------------------------
# Step 2 — idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_duplicate_save_id_is_noop(self):
        env = _envelope()
        r = apply_save_day(BASE_NOTE, env, {"2026-06-17-1"})
        assert r["action"] == "noop"
        assert r["note_md"] == BASE_NOTE

    def test_fresh_save_id_applies(self):
        env = _envelope(energy={"morning": "low"})
        r = apply_save_day(BASE_NOTE, env, {"2026-06-17-99"})
        assert r["action"] == "patched"

    def test_returns_save_id_for_caller_to_record(self):
        env = _envelope()
        r = apply_save_day(BASE_NOTE, env, set())
        assert r["save_id"] == "2026-06-17-1"


# ---------------------------------------------------------------------------
# Step 3-5 — conflict / drift detection
# ---------------------------------------------------------------------------

class TestConflict:
    def test_matching_hash_is_clean_patch(self):
        env = _envelope(energy={"morning": "low"})
        r = apply_save_day(BASE_NOTE, env, set())
        assert r["action"] == "patched"

    def test_stale_base_hash_patches_latest_with_drift_flag(self):
        # The note changed underneath us (close-day wrote Work Log). The
        # envelope's baseHash is now stale. We must STILL apply the field
        # patch onto the LATEST note, not refuse — and flag the drift.
        latest = BASE_NOTE.replace("## Work Log\n-", "## Work Log\n- Shipped the spec")
        env = _envelope(energy={"morning": "low"})  # baseHash is for BASE_NOTE, now stale
        r = apply_save_day(latest, env, set())
        assert r["action"] == "patched-with-drift"
        # The work that happened underneath us survives.
        assert "Shipped the spec" in r["note_md"]
        # And our edit landed.
        assert "- Energy: low" in r["note_md"]


# ---------------------------------------------------------------------------
# Step 4 — field-level patch: Top 3 (positional, progress markers, dispositions)
# ---------------------------------------------------------------------------

class TestTop3Patch:
    def test_progress_marker_written(self):
        env = _envelope(top3=[
            {"slot": 0, "text": "Finish the toolkit spec", "progress": 50, "disposition": "active"},
            {"slot": 1, "text": "Q3 LOP draft", "progress": 0, "disposition": "active"},
            {"slot": 2, "text": "Reply to vendor", "progress": 0, "disposition": "active"},
        ])
        r = apply_save_day(BASE_NOTE, env, set())
        assert "1. [ ] Finish the toolkit spec <!--p:50-->" in r["note_md"]

    def test_done_disposition_is_checked(self):
        env = _envelope(top3=[
            {"slot": 0, "text": "Finish the toolkit spec", "progress": 100, "disposition": "done"},
            {"slot": 1, "text": "Q3 LOP draft", "progress": 0, "disposition": "active"},
            {"slot": 2, "text": "Reply to vendor", "progress": 0, "disposition": "active"},
        ])
        r = apply_save_day(BASE_NOTE, env, set())
        assert "1. [x] Finish the toolkit spec" in r["note_md"]
        # no stray progress marker on a done item
        assert "Finish the toolkit spec <!--p:" not in r["note_md"]

    def test_positional_slots_never_compacted(self):
        # Slot 1 cleared (empty text) — the slot must remain, not collapse
        # slot 2 up into slot 1. (Build plan recent-learnings #1.)
        env = _envelope(top3=[
            {"slot": 0, "text": "Finish the toolkit spec", "progress": 0, "disposition": "active"},
            {"slot": 1, "text": "", "progress": 0, "disposition": "active"},
            {"slot": 2, "text": "Reply to vendor", "progress": 0, "disposition": "active"},
        ])
        r = apply_save_day(BASE_NOTE, env, set())
        lines = [ln for ln in r["note_md"].splitlines() if ln.strip().startswith(("1.", "2.", "3."))]
        top3_lines = [ln for ln in lines if "toolkit spec" in ln or "vendor" in ln or ln.strip() in ("2. [ ]", "2. [ ] ")]
        # Slot 2 (vendor) must still be the THIRD numbered row.
        my_top3 = r["note_md"].split("### My Top 3")[1].split("###")[0]
        rows = [ln.strip() for ln in my_top3.splitlines() if ln.strip() and ln.strip()[0].isdigit()]
        assert len(rows) == 3
        assert "Finish the toolkit spec" in rows[0]
        assert rows[1] in ("2. [ ]", "2. [ ]")  # empty slot kept
        assert "Reply to vendor" in rows[2]

    def test_deleted_disposition_keeps_row(self):
        # Delete is a reversible MARK, never a removal (cowork gates rm).
        env = _envelope(top3=[
            {"slot": 0, "text": "Finish the toolkit spec", "progress": 0, "disposition": "active"},
            {"slot": 1, "text": "Q3 LOP draft", "progress": 0, "disposition": "active"},
            {"slot": 2, "text": "Reply to vendor", "progress": 25, "disposition": "deleted"},
        ])
        r = apply_save_day(BASE_NOTE, env, set())
        # The deleted item's text still appears somewhere (row kept, not dropped).
        assert "Reply to vendor" in r["note_md"]

    def test_deleted_item_can_carry_progress(self):
        # An item can carry a % AND be marked deleted (CLI disposition semantics).
        env = _envelope(top3=[
            {"slot": 0, "text": "Finish the toolkit spec", "progress": 0, "disposition": "active"},
            {"slot": 1, "text": "Q3 LOP draft", "progress": 0, "disposition": "active"},
            {"slot": 2, "text": "Reply to vendor", "progress": 25, "disposition": "deleted"},
        ])
        r = apply_save_day(BASE_NOTE, env, set())
        assert "Reply to vendor" in r["note_md"]
        assert "<!--p:25-->" in r["note_md"]


# ---------------------------------------------------------------------------
# Step 4 — field-level patch: bonus / unplanned
# ---------------------------------------------------------------------------

class TestBonusUnplannedPatch:
    def test_unplanned_added(self):
        env = _envelope(unplanned=[
            {"text": "Unblocked the cowork build", "progress": 100, "disposition": "done"},
        ])
        r = apply_save_day(BASE_NOTE, env, set())
        assert "Unblocked the cowork build" in r["note_md"]
        assert "### Unplanned" in r["note_md"]

    def test_bonus_progress_updated(self):
        env = _envelope(bonus=[
            {"text": "Review Red's PR", "progress": 75, "disposition": "active"},
        ])
        r = apply_save_day(BASE_NOTE, env, set())
        assert "Review Red's PR <!--p:75-->" in r["note_md"]


# ---------------------------------------------------------------------------
# Step 4 — field-level patch: habits
# ---------------------------------------------------------------------------

class TestHabitsPatch:
    def test_habits_preserved_when_name_map_absent(self):
        # Codex [P2]: a SAVE_DAY that carries `habits` but no active_habits map
        # must NOT wipe the existing ### Habits checkboxes. (An energy-only save
        # from the artifact still includes the habits array.)
        env = _envelope(
            energy={"morning": "low"},
            habits=[{"id": "walk", "percent": 1.0}],
        )
        r = apply_save_day(BASE_NOTE, env, set())  # no active_habits passed
        # The original habit rows survive untouched (we couldn't safely rewrite them).
        assert "**Walk**" in r["note_md"]
        assert "**Read 15m**" in r["note_md"]
        assert "**Workout**" in r["note_md"]

    def test_completed_habit_checked(self):
        env = _envelope(habits=[
            {"id": "walk", "percent": 1.0},
            {"id": "read15", "percent": 0.0},
            {"id": "workout", "percent": 0.5},
        ])
        # apply_save_day needs the name<->id map to write the right bold label.
        r = apply_save_day(
            BASE_NOTE, env, set(),
            active_habits=[
                {"id": "walk", "name": "Walk"},
                {"id": "read15", "name": "Read 15m"},
                {"id": "workout", "name": "Workout"},
            ],
        )
        assert "- [x] **Walk**" in r["note_md"]
        assert "- [ ] **Read 15m**" in r["note_md"]
        assert "- [/] **Workout**" in r["note_md"]  # 0.5 partial


# ---------------------------------------------------------------------------
# Step 4 — field-level patch: energy (morning + evening, kept distinct)
# ---------------------------------------------------------------------------

class TestEnergyPatch:
    def test_morning_energy_in_morning_section(self):
        env = _envelope(energy={"morning": "low"})
        r = apply_save_day(BASE_NOTE, env, set())
        morning = r["note_md"].split("## Morning Check-in")[1].split("## Calendar")[0]
        assert "- Energy: low" in morning

    def test_evening_energy_in_end_of_day(self):
        env = _envelope(energy={"morning": "high", "evening": "medium"})
        r = apply_save_day(BASE_NOTE, env, set())
        eod = r["note_md"].split("## End of Day")[1]
        assert "- Energy: medium" in eod

    def test_evening_null_leaves_end_of_day_empty(self):
        env = _envelope(energy={"morning": "high", "evening": None})
        r = apply_save_day(BASE_NOTE, env, set())
        eod = r["note_md"].split("## End of Day")[1]
        assert "- Energy:" in eod
        assert "- Energy: high" not in eod  # morning didn't leak into evening


# ---------------------------------------------------------------------------
# Step 4 — gratitude / insight reflection
# ---------------------------------------------------------------------------

class TestReflectionPatch:
    def test_gratitude_written(self):
        env = _envelope(gratitude="Shipped the spec with Red's help.")
        r = apply_save_day(BASE_NOTE, env, set())
        assert "## Gratitude" in r["note_md"]
        assert "Shipped the spec with Red's help." in r["note_md"]

    def test_insight_reflection_written(self):
        env = _envelope(insightReflection="I do my best writing before 9am.")
        r = apply_save_day(BASE_NOTE, env, set())
        assert "## Insight Reflection" in r["note_md"]
        assert "I do my best writing before 9am." in r["note_md"]

    def test_empty_reflection_does_not_create_section(self):
        env = _envelope(gratitude="", insightReflection="")
        r = apply_save_day(BASE_NOTE, env, set())
        # Don't author empty sections.
        assert "## Insight Reflection" not in r["note_md"]

    def test_explicit_clear_removes_existing_gratitude(self):
        # Codex [P2]: a user who CLEARS an existing Gratitude field sends "".
        # That deletion must be persisted, not silently ignored. Key presence,
        # not truthiness, decides whether to apply the field.
        noted = BASE_NOTE + "\n## Gratitude\n\nGrateful for the team.\n"
        env = _envelope(gratitude="")
        env["baseHash"] = compute_note_hash(noted)
        r = apply_save_day(noted, env, set())
        assert "Grateful for the team." not in r["note_md"]

    def test_field_absent_from_changes_preserves_section(self):
        # The opposite case: if the artifact didn't send the field at all (key
        # absent), the existing section must be preserved — only sent fields patch.
        noted = BASE_NOTE + "\n## Gratitude\n\nGrateful for the team.\n"
        env = _envelope()
        del env["changes"]["gratitude"]
        env["baseHash"] = compute_note_hash(noted)
        r = apply_save_day(noted, env, set())
        assert "Grateful for the team." in r["note_md"]


# ---------------------------------------------------------------------------
# Step 4 — status transition
# ---------------------------------------------------------------------------

class TestStatusTransition:
    def test_lock_in_sets_active(self):
        note = BASE_NOTE.replace("status: active", "status: planning")
        env = _envelope(statusTransition="active")
        env["baseHash"] = compute_note_hash(note)
        r = apply_save_day(note, env, set())
        assert "status: active" in r["note_md"]

    def test_close_sets_closed(self):
        env = _envelope(statusTransition="closed")
        r = apply_save_day(BASE_NOTE, env, set())
        assert "status: closed" in r["note_md"]

    def test_no_transition_preserves_status(self):
        env = _envelope(statusTransition=None)
        r = apply_save_day(BASE_NOTE, env, set())
        assert "status: active" in r["note_md"]


# ---------------------------------------------------------------------------
# Step 6 — untouched sections survive byte-for-byte; never delete
# ---------------------------------------------------------------------------

class TestPreservation:
    def test_calendar_survives(self):
        env = _envelope(energy={"morning": "low"})
        r = apply_save_day(BASE_NOTE, env, set())
        assert "## Calendar" in r["note_md"]
        assert "Standup (team)" in r["note_md"]
        assert "scheduled by /open-day" in r["note_md"]

    def test_ai_suggestions_survive(self):
        env = _envelope(top3=[
            {"slot": 0, "text": "Something else entirely", "progress": 0, "disposition": "active"},
            {"slot": 1, "text": "Q3 LOP draft", "progress": 0, "disposition": "active"},
            {"slot": 2, "text": "Reply to vendor", "progress": 0, "disposition": "active"},
        ])
        r = apply_save_day(BASE_NOTE, env, set())
        # The AI Suggested block (close-day's overnight work) must not be clobbered.
        assert "### AI Suggested: Top 3" in r["note_md"]
        assert "only you can do this" in r["note_md"]

    def test_no_section_is_deleted(self):
        env = _envelope(energy={"morning": "low"})
        r = apply_save_day(BASE_NOTE, env, set())
        for heading in ("## Morning Check-in", "## Calendar", "## Work Log", "## End of Day"):
            assert heading in r["note_md"]

    def test_input_note_not_mutated(self):
        env = _envelope(energy={"morning": "low"})
        before = copy.copy(BASE_NOTE)
        apply_save_day(BASE_NOTE, env, set())
        assert BASE_NOTE == before  # pure function, no in-place mutation
