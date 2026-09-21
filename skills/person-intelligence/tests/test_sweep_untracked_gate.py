"""The biweekly sweep must honour the vault's `tracked: false` markers.

`test_untracked_and_dedup.py` pins this gate for `list_relationships.main()`. That
was not enough: `biweekly_sweep.build_manifest()` composes its roster **inline**
(its own comment says it re-implements the logic "to avoid subprocess overhead")
and reuses only `find_by_name` / `find_peers` / `parse_key_relationships`. It never
called `build_untracked_set`, so the gate covered the reporting path and not the
path that actually spends API calls and writes profiles.

The 2026-09-13 headless sweep therefore processed 30 people against a roster of
28, re-synthesized profiles for a departed employee and an out-of-scope
contractor, and put "first assessment is overdue" for both into the team pulse.
The two earlier sweeps looked correct only because a human filtered the manifest
by hand afterwards — the `.unfiltered.bak` files beside them are the evidence.

One gate, two callers, tested on one: that is why this file exists. Every append
path in `build_manifest` gets a case below.

Run: python3 -m pytest skills/person-intelligence/tests/test_sweep_untracked_gate.py -q
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import biweekly_sweep  # noqa: E402
import resolve_user  # noqa: E402

FIXTURE = [
    {
        "name": "Test User",
        "email": "test@example.com",
        "manager": "Boss Person",
        "manages": ["Kept Report", "Archived Report"],
    },
    {"name": "Kept Report", "email": "kept@example.com", "manager": "Test User", "manages": []},
    {
        "name": "Archived Report",
        "email": "archived@example.com",
        "manager": "Test User",
        "manages": [],
    },
    {"name": "Boss Person", "email": "boss@example.com", "manager": "", "manages": ["Test User"]},
]

UNTRACKED_FM = "---\nstatus: departed\narchived: 2026-07-27\ntracked: false\n---\n\n# Archived\n"
TRACKED_FM = "---\ntype: person\n---\n\n# Live\n"


def _vault(tmp_path, files):
    people = tmp_path / "30-people"
    people.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        path = people / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _manifest(tmp_path, monkeypatch, employees, files, env=None):
    chart = tmp_path / "org-chart.json"
    chart.write_text(json.dumps(employees), encoding="utf-8")
    monkeypatch.setattr(resolve_user, "ORG_CHART_PATHS", [chart])

    for key in ("INCLUDE_MANAGEMENT_PEERS", "KEY_RELATIONSHIPS", "FATHOM_API_KEY",
                "SIGNAL_INGEST", "SKIP_SLACK_INGEST", "SKIP_GMAIL_INGEST"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPERATING_USER_EMAIL", "test@example.com")
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)

    vault = _vault(tmp_path / "vault", files)
    manifest, err = biweekly_sweep.build_manifest(vault, tmp_path / "cache")
    assert err is None, err
    return manifest


def _names(manifest):
    return {r["name"] for r in manifest["relationships"]}


def test_untracked_direct_report_is_excluded(tmp_path, monkeypatch):
    """The 2026-09-13 regression, reduced: an archived direct report came back."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM, "_archive/Archived Report.md": UNTRACKED_FM},
    )
    assert "Archived Report" not in _names(manifest)
    assert "Kept Report" in _names(manifest)


def test_excluded_people_are_announced_not_just_dropped(tmp_path, monkeypatch):
    """A silent exclusion reads exactly like a person who was never tracked."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM, "_archive/Archived Report.md": UNTRACKED_FM},
    )
    assert manifest["untracked_excluded_count"] == 1
    assert manifest["untracked_excluded"] == ["Archived Report"]


def test_relationship_count_matches_the_filtered_roster(tmp_path, monkeypatch):
    """`relationship_count` drives finalize() and the pulse header — it must not over-count."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM, "_archive/Archived Report.md": UNTRACKED_FM},
    )
    assert manifest["relationship_count"] == len(manifest["relationships"])
    assert "Archived Report" not in json.dumps(manifest["relationships"])


def test_untracked_manager_is_excluded(tmp_path, monkeypatch):
    """The manager append path bypasses add() entirely, so it needs its own gate."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM, "_archive/Boss Person.md": UNTRACKED_FM},
    )
    assert "Boss Person" not in _names(manifest)
    assert manifest["untracked_excluded"] == ["Boss Person"]


def test_untracked_external_key_relationship_is_excluded(tmp_path, monkeypatch):
    """Key relationships absent from the org chart append directly too."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM, "_archive/Former Advisor.md": UNTRACKED_FM},
        env={"KEY_RELATIONSHIPS": "Former Advisor"},
    )
    assert "Former Advisor" not in _names(manifest)


def test_untracked_matches_on_email_not_only_filename(tmp_path, monkeypatch):
    """An archive tombstone filed under a different spelling still has to bite."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {
            "Kept Report.md": TRACKED_FM,
            "_archive/Rippling Spelling.md":
                "---\nemail: archived@example.com\ntracked: false\n---\n\n# x\n",
        },
    )
    assert "Archived Report" not in _names(manifest)


def test_tracked_people_survive_an_empty_archive(tmp_path, monkeypatch):
    """The gate must not be so eager it empties the roster."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM, "Archived Report.md": TRACKED_FM},
    )
    assert {"Kept Report", "Archived Report", "Boss Person"} <= _names(manifest)
    assert manifest["untracked_excluded_count"] == 0


def test_body_prose_saying_tracked_false_does_not_drop_a_live_person(tmp_path, monkeypatch):
    """Only leading frontmatter counts — pinned for list_relationships, asserted here too."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {
            "Kept Report.md": TRACKED_FM,
            "Archived Report.md":
                "---\ntype: person\n---\n\nWe discussed whether tracked: false applied.\n",
        },
    )
    assert "Archived Report" in _names(manifest)


# --------------------------------------------------------------------------
# `tracking_reason:` overrides — the same one-gate-two-callers trap.
#
# Rippling models a contractor's point of contact as their manager, so a vendor
# lands in `manages` and reads as a direct report, which hands a supplier a
# health score and coaching goals. `tracked: false` was the only lever and it
# removes them outright. These pin the middle setting, in the SWEEP path.
# --------------------------------------------------------------------------

REASON_FM = "---\ntype: person\ntracking_reason: key_relationship\n---\n\n# x\n"


def _reason_of(manifest, name):
    r = next((x for x in manifest["relationships"] if x["name"] == name), None)
    return r and r["tracking_reason"]


def test_vault_can_demote_a_direct_report_to_key_relationship(tmp_path, monkeypatch):
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM, "Archived Report.md": REASON_FM},
    )
    assert _reason_of(manifest, "Archived Report") == "key_relationship"
    assert _reason_of(manifest, "Kept Report") == "direct_report"


def test_override_does_not_resurrect_an_untracked_person(tmp_path, monkeypatch):
    """`tracked: false` is the stronger statement; an override must not undo it."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {
            "Kept Report.md": TRACKED_FM,
            "_archive/Archived Report.md":
                "---\ntracked: false\ntracking_reason: key_relationship\n---\n\n# x\n",
        },
    )
    assert "Archived Report" not in _names(manifest)


def test_unknown_reason_value_is_ignored(tmp_path, monkeypatch):
    """A typo must not invent a category the coaching frames fail to match."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM,
         "Archived Report.md": "---\ntracking_reason: freind\n---\n\n# x\n"},
    )
    assert _reason_of(manifest, "Archived Report") == "direct_report"


def test_override_matches_on_email_too(tmp_path, monkeypatch):
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM,
         "Rippling Spelling.md":
             "---\nemail: archived@example.com\ntracking_reason: key_relationship\n---\n\n# x\n"},
    )
    assert _reason_of(manifest, "Archived Report") == "key_relationship"


def test_sweep_and_roster_agree_on_the_override(tmp_path, monkeypatch):
    """The regression that started all this: the two callers must not diverge."""
    import list_relationships as lr
    vault = _vault(tmp_path / "v2", {"Archived Report.md": REASON_FM})
    assert lr.build_reason_overrides(vault).get("archived report") == "key_relationship"
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM, "Archived Report.md": REASON_FM},
    )
    assert _reason_of(manifest, "Archived Report") == "key_relationship"


@pytest.mark.parametrize("who,fixture_files,env,expected", [
    # add() — the path that already worked.
    ("Archived Report", {"Archived Report.md": REASON_FM}, {}, "key_relationship"),
    # The manager path: appends directly, never touches add().
    ("Boss Person", {"Boss Person.md": REASON_FM}, {}, "key_relationship"),
    # The external KEY_RELATIONSHIPS path: same, for anyone absent from the org chart.
    ("Outside Coach", {"Outside Coach.md": REASON_FM},
     {"KEY_RELATIONSHIPS": "Outside Coach"}, "key_relationship"),
])
def test_override_applies_on_every_append_path(
    tmp_path, monkeypatch, who, fixture_files, env, expected
):
    """Macroscope caught this on PR #77: the untracked gate was fixed across all three
    append paths, then the NEW override gate was applied only in add() — the same
    partial-coverage bug the PR was about, one layer up. add() is the only path with a
    natural test; the other two append directly and are easy to forget twice."""
    files = {"Kept Report.md": TRACKED_FM}
    files.update(fixture_files)
    manifest = _manifest(tmp_path, monkeypatch, FIXTURE, files, env=env)
    assert _reason_of(manifest, who) == expected


def test_external_key_relationship_override_is_not_hardcoded(tmp_path, monkeypatch):
    """Without the fix this is always `key_relationship_external`, whatever the vault says."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE,
        {"Kept Report.md": TRACKED_FM, "Outside Coach.md": REASON_FM},
        env={"KEY_RELATIONSHIPS": "Outside Coach"},
    )
    assert _reason_of(manifest, "Outside Coach") == "key_relationship"
    assert _reason_of(manifest, "Outside Coach") != "key_relationship_external"


@pytest.mark.parametrize("reason_file,expected", [
    ("_archive/Archived Report.md", "Archived Report"),
    ("_archive/Boss Person.md", "Boss Person"),
])
def test_every_append_path_reports_through_one_counter(
    tmp_path, monkeypatch, reason_file, expected
):
    """Regression guard: a future append path added without the gate shows up here."""
    manifest = _manifest(
        tmp_path, monkeypatch, FIXTURE, {"Kept Report.md": TRACKED_FM, reason_file: UNTRACKED_FM},
    )
    assert expected in manifest["untracked_excluded"]
    assert expected not in _names(manifest)
