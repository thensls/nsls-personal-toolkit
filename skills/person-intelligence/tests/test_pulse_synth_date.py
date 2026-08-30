"""The team-pulse digest must read the last-synthesized date from the PROFILE.

Found 2026-08-24, the day after a completed 28-person sweep.

`biweekly_sweep` builds its manifest at PLAN time — before anything is written — so the
manifest's own `last_synthesized` is the *previous* cycle's value. `generate_team_pulse` read
staleness from there while reading health, health_score and health_last_assessed from the
profile. The result: a digest generated hours after synthesizing 28 people reported 25 of them
as 28–48 days stale, and the model then wrote its cadence commentary against those numbers.

Nothing errored. The digest was internally consistent and confidently wrong, and the only
reason it was caught is that a dry run happened to print both fields next to each other.

Run: python3 -m pytest skills/person-intelligence/tests/test_pulse_synth_date.py -q
"""

import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_team_pulse as gtp  # noqa: E402

TODAY = date.today().isoformat()
LAST_MONTH = (date.today() - timedelta(days=31)).isoformat()


def _rows(manifest, vault):
    """build_pulse_input returns {"operating_user", "manifest_date", "relationships"}."""
    return gtp.build_pulse_input(manifest, vault)["relationships"]


def _vault(tmp_path, name, fm_lines):
    people = tmp_path / "30-people"
    people.mkdir(parents=True, exist_ok=True)
    body = "\n".join(fm_lines)
    (people / f"{name}.md").write_text(
        f"---\n{body}\n---\n\n# {name}\n\n## Relationship Health\n", encoding="utf-8"
    )
    return tmp_path


def _manifest(name, manifest_date):
    return {
        "relationships": [
            {
                "name": name,
                "relationship_type": "direct_report",
                "last_synthesized": manifest_date,
                "fathom": {"count": 3},
                "has_obsidian_file": True,
            }
        ]
    }


def test_profile_date_wins_over_the_stale_manifest_date(tmp_path):
    """The regression. Manifest says a month ago; the profile says today."""
    vault = _vault(
        tmp_path,
        "Fresh Person",
        [f"last-synthesized: {TODAY}", "health: great", "health_score: 3.8"],
    )
    rows = _rows(_manifest("Fresh Person", LAST_MONTH), vault)
    assert rows[0]["last_synthesized"] == TODAY
    assert rows[0]["days_since_synth"] == 0
    assert rows[0]["synth_date_source"] == "profile"


def test_manifest_date_is_the_fallback_when_the_profile_has_none(tmp_path):
    """A profile predating the field, or one that never got stamped, must still report."""
    vault = _vault(tmp_path, "No Date", ["health: good", "health_score: 3.0"])
    rows = _rows(_manifest("No Date", LAST_MONTH), vault)
    assert rows[0]["last_synthesized"] == LAST_MONTH
    assert rows[0]["days_since_synth"] == 31
    assert rows[0]["synth_date_source"] == "manifest"


def test_no_profile_at_all_falls_back_without_raising(tmp_path):
    (tmp_path / "30-people").mkdir(parents=True, exist_ok=True)
    rows = _rows(_manifest("Ghost", LAST_MONTH), tmp_path)
    assert rows[0]["last_synthesized"] == LAST_MONTH
    assert rows[0]["synth_date_source"] == "manifest"


def test_both_missing_reports_never_rather_than_a_wrong_number(tmp_path):
    vault = _vault(tmp_path, "Unknown", ["health: unscored"])
    manifest = _manifest("Unknown", None)
    rows = _rows(manifest, vault)
    assert rows[0]["last_synthesized"] is None
    assert rows[0]["days_since_synth"] is None


def test_quoted_frontmatter_date_is_handled(tmp_path):
    """parse_frontmatter strips quotes; make sure the comparison doesn't reintroduce them."""
    vault = _vault(tmp_path, "Quoted", [f'last-synthesized: "{TODAY}"'])
    rows = _rows(_manifest("Quoted", LAST_MONTH), vault)
    assert rows[0]["last_synthesized"] == TODAY
    assert rows[0]["days_since_synth"] == 0


def test_health_fields_still_come_from_the_profile(tmp_path):
    """Guards against the fix disturbing the fields that were already correct."""
    vault = _vault(
        tmp_path,
        "Scored",
        [
            f"last-synthesized: {TODAY}",
            "health: great",
            "health_score: 3.83",
            f"health_last_assessed: {TODAY}",
        ],
    )
    row = _rows(_manifest("Scored", LAST_MONTH), vault)[0]
    assert row["health"] == "great"
    assert row["health_score"] == "3.83"
    assert row["health_last_assessed"] == TODAY
    assert row["fathom_new_meetings"] == 3, "roster-side data still comes from the manifest"


def test_the_rendered_prompt_shows_the_profile_date(tmp_path):
    """End-to-end through the text the model actually sees.

    The bug only mattered because it reached the prompt. Asserting on the dict alone would
    miss a formatting path that re-read the manifest, and the prompt is the artifact the
    digest's cadence commentary is written from.
    """
    vault = _vault(tmp_path, "Fresh Person", [f"last-synthesized: {TODAY}"])
    pulse_input = gtp.build_pulse_input(_manifest("Fresh Person", LAST_MONTH), vault)
    rendered = gtp.build_user_prompt(pulse_input, "TEMPLATE")
    assert f"Last synthesized: {TODAY} (0 days ago)" in rendered
    assert LAST_MONTH not in rendered, "the stale manifest date must not reach the model"

# ---------------------------------------------------------------------------------------
# malformed profile dates (Macroscope, 2026-08-24)
# ---------------------------------------------------------------------------------------


def test_malformed_profile_date_does_not_beat_a_valid_manifest_date(tmp_path, capsys):
    """A degradation the profile-preference fix itself introduced.

    Gating on truthiness meant `last-synthesized: TBD` won over a good manifest date,
    days_since() returned None, and the prompt rendered the person as NEVER synthesized —
    trading a stale number for no number, which is worse than the original bug.
    """
    for bad in ("TBD", "unknown", "2026-13-45", "yesterday", "2026/08/23"):
        vault = _vault(tmp_path / bad.replace("/", "-"), "Bad Date", [f"last-synthesized: {bad}"])
        rows = _rows(_manifest("Bad Date", LAST_MONTH), vault)
        assert rows[0]["last_synthesized"] == LAST_MONTH, f"{bad!r} should not win"
        assert rows[0]["days_since_synth"] == 31, f"{bad!r} lost the manifest date"
        assert rows[0]["synth_date_source"] == "manifest"


def test_both_unparseable_keeps_the_raw_value_visible_and_warns(tmp_path, capsys):
    """A malformed date must stay visible rather than silently becoming 'never'."""
    vault = _vault(tmp_path, "Bad Both", ["last-synthesized: TBD"])
    rows = _rows(_manifest("Bad Both", "also-garbage"), vault)
    assert rows[0]["last_synthesized"] == "TBD"
    assert rows[0]["days_since_synth"] is None
    assert rows[0]["synth_date_source"] == "unusable"
    assert "unparseable" in capsys.readouterr().err


def test_malformed_manifest_date_does_not_break_a_good_profile_date(tmp_path):
    vault = _vault(tmp_path, "Good Profile", [f"last-synthesized: {TODAY}"])
    rows = _rows(_manifest("Good Profile", "not-a-date"), vault)
    assert rows[0]["last_synthesized"] == TODAY
    assert rows[0]["synth_date_source"] == "profile"


def test_a_future_profile_date_does_not_win(tmp_path, capsys):
    """Macroscope, round 2 on this PR.

    A typo'd year parses perfectly and then renders as "-365 days ago", silently corrupting
    the cadence analysis the digest is written from. Unusable for the same reason `TBD` is,
    so it has to fail the same gate.
    """
    future = (date.today() + timedelta(days=365)).isoformat()
    vault = _vault(tmp_path, "Future", [f"last-synthesized: {future}"])
    rows = _rows(_manifest("Future", LAST_MONTH), vault)
    assert rows[0]["last_synthesized"] == LAST_MONTH
    assert rows[0]["days_since_synth"] == 31
    assert rows[0]["synth_date_source"] == "manifest"
    assert "in the future" in capsys.readouterr().err


def test_a_future_manifest_date_is_also_rejected(tmp_path):
    """The manifest side needs the same gate, or the fallback reintroduces the bug."""
    future = (date.today() + timedelta(days=10)).isoformat()
    vault = _vault(tmp_path, "Both Bad", ["last-synthesized: TBD"])
    rows = _rows(_manifest("Both Bad", future), vault)
    assert rows[0]["days_since_synth"] is None
    assert rows[0]["synth_date_source"] == "unusable"


def test_today_is_still_usable(tmp_path):
    """Age 0 must pass the non-negative gate — an off-by-one here breaks every fresh sweep."""
    vault = _vault(tmp_path, "Fresh", [f"last-synthesized: {TODAY}"])
    rows = _rows(_manifest("Fresh", LAST_MONTH), vault)
    assert rows[0]["days_since_synth"] == 0
    assert rows[0]["synth_date_source"] == "profile"
