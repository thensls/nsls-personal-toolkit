"""Tests for `_detect_day_state` mode detection.

Phase 1.3b: the daily note carries an explicit `status: planning|active|closed`
frontmatter that drives the mode, replacing the fragile section-presence
inference (the `## Insight Reflection` presence check that flipped Command
Center -> results mid-day). When `status` is present it is authoritative;
when absent we fall back to the legacy inference so old notes still open
correctly.

Status mapping (mirrors the spec's artifact-mode table):
  - closed   -> 'results'        (day fully closed)
  - active   -> 'command'        (Command Center) ...
               ... unless close-day has begun: an empty `## Insight
               Reflection` heading is present -> 'coach-evening'
  - planning -> 'coach-morning'  (plan-confirm pass)
  - absent   -> legacy inference (Insight Reflection body/heading, then Top 3)
"""

from companion.server import _detect_day_state


def _top3(n=3):
    return [{"text": f"task {i}", "checked": False} for i in range(n)]


# ---------------------------------------------------------------------------
# status frontmatter is authoritative when present
# ---------------------------------------------------------------------------

class TestStatusDriven:
    def test_closed_returns_results(self):
        md = "---\nstatus: closed\n---\n\n## Morning Check-in\n"
        assert _detect_day_state(md, _top3()) == "results"

    def test_active_returns_command(self):
        md = "---\nstatus: active\n---\n\n## Morning Check-in\n"
        assert _detect_day_state(md, _top3()) == "command"

    def test_planning_returns_coach_morning(self):
        md = "---\nstatus: planning\n---\n\n## Morning Check-in\n"
        assert _detect_day_state(md, _top3()) == "coach-morning"

    def test_active_with_empty_insight_heading_returns_coach_evening(self):
        # close-day injects an empty `## Insight Reflection` heading to signal
        # the evening pass has started but not finished. Still status:active.
        md = (
            "---\nstatus: active\n---\n\n## Morning Check-in\n\n"
            "## Insight Reflection\n\n## End of Day\n"
        )
        assert _detect_day_state(md, _top3()) == "coach-evening"

    def test_active_with_filled_insight_still_command_until_closed(self):
        # If status is still 'active' (close not committed), a non-empty
        # reflection means the user is mid-close -> coach-evening, not results.
        # Only `status: closed` yields results.
        md = (
            "---\nstatus: active\n---\n\n## Morning Check-in\n\n"
            "## Insight Reflection\nGreat day, shipped the thing.\n"
        )
        assert _detect_day_state(md, _top3()) == "coach-evening"

    def test_planning_ignores_top3_presence(self):
        # Even with a full Top 3, planning means we're still in the morning
        # confirm pass — status wins over the legacy Top-3 inference.
        md = "---\nstatus: planning\n---\n\n## Morning Check-in\n"
        assert _detect_day_state(md, _top3()) == "coach-morning"

    def test_closed_ignores_everything_else(self):
        md = "---\nstatus: closed\n---\n\n## Morning Check-in\n"
        assert _detect_day_state(md, []) == "results"


# ---------------------------------------------------------------------------
# backward compatibility: no status frontmatter -> legacy inference
# ---------------------------------------------------------------------------

class TestLegacyInference:
    def test_filled_insight_returns_results(self):
        md = "## Insight Reflection\nGreat day.\n"
        assert _detect_day_state(md, _top3()) == "results"

    def test_empty_insight_heading_returns_coach_evening(self):
        md = "## Morning Check-in\n\n## Insight Reflection\n\n## End of Day\n"
        assert _detect_day_state(md, _top3()) == "coach-evening"

    def test_top3_with_text_returns_command(self):
        md = "## Morning Check-in\n\n### My Top 3\n1. [ ] task\n"
        assert _detect_day_state(md, _top3()) == "command"

    def test_no_top3_returns_coach_morning(self):
        md = "## Morning Check-in\n"
        assert _detect_day_state(md, []) == "coach-morning"

    def test_empty_note_returns_coach_morning(self):
        assert _detect_day_state("", []) == "coach-morning"

    def test_unknown_status_falls_back_to_inference(self):
        # A status value we don't recognise shouldn't hijack detection; fall
        # back to the legacy inference so we never render a blank mode.
        md = "---\nstatus: bogus\n---\n\n## Insight Reflection\nGreat day.\n"
        assert _detect_day_state(md, _top3()) == "results"
