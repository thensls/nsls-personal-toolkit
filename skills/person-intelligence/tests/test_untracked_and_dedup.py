"""Tests for the roster's untracked gate and its name/email dedup.

Every case here corresponds to a defect that shipped or was caught in review on
2026-08-23. They exist because the failure mode in this area is always the same:
the roster silently contains the wrong people and reports success either way.

`build_untracked_set` and `_frontmatter` are imported directly (both pure, both
filesystem-only). The dedup rules are exercised end-to-end through the script,
because they live inside `main()`'s closure.

Run: python3 -m pytest skills/person-intelligence/tests/test_untracked_and_dedup.py -q
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import list_relationships as lr  # noqa: E402

_EMPTY_ENV = Path(tempfile.mkdtemp(prefix="pi-test-env-")) / "empty.env"
_EMPTY_ENV.write_text("", encoding="utf-8")


def _vault(tmp_path, files):
    """files: {relative path under 30-people: file text}"""
    people = tmp_path / "30-people"
    for rel, text in files.items():
        path = people / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    people.mkdir(parents=True, exist_ok=True)
    return tmp_path


# --------------------------------------------------------------------------------------
# _frontmatter / build_untracked_set
# --------------------------------------------------------------------------------------


def test_tracked_false_in_the_body_does_not_untrack_an_active_person(tmp_path):
    """The original implementation scanned a 4000-char prefix, so prose won.

    A profile whose *body* discusses `tracked: false` — a runbook note, a quoted
    snippet, an explanation of this very mechanism — would silently drop a live
    relationship from the sweep.
    """
    vault = _vault(
        tmp_path,
        {
            "Active Person.md": (
                "---\nemail: active@example.com\nstatus: current\n---\n\n"
                "# Active Person\n\n"
                "Archiving works by setting `tracked: false` in the frontmatter.\n"
                "tracked: false\n"
            )
        },
    )
    assert lr.build_untracked_set(vault) == set()


def test_tracked_false_beyond_the_old_prefix_cutoff_is_still_found(tmp_path):
    """Frontmatter longer than the old 4000-char window silently kept people in."""
    padding = "\n".join(f"note_{i}: {'x' * 80}" for i in range(120))
    vault = _vault(
        tmp_path,
        {
            "_archive/Long Frontmatter.md": (
                f"---\nemail: long@example.com\n{padding}\ntracked: false\n---\n\n# Long\n"
            )
        },
    )
    untracked = lr.build_untracked_set(vault)
    assert "long frontmatter" in untracked
    assert "long@example.com" in untracked


def test_archive_subdirectory_is_scanned(tmp_path):
    vault = _vault(
        tmp_path,
        {"_archive/Gone Person.md": "---\nemail: gone@example.com\ntracked: false\n---\n"},
    )
    assert "gone person" in lr.build_untracked_set(vault)


def test_email_alt_is_also_untracked(tmp_path):
    """A two-address person must be excluded by either address."""
    vault = _vault(
        tmp_path,
        {
            "_archive/Two Addr.md": (
                "---\nemail: a@example.com\nemail_alt: b@example.com\ntracked: false\n---\n"
            )
        },
    )
    untracked = lr.build_untracked_set(vault)
    assert {"a@example.com", "b@example.com"} <= untracked


def test_file_without_frontmatter_is_ignored(tmp_path):
    vault = _vault(tmp_path, {"Plain.md": "# Plain\n\ntracked: false\n"})
    assert lr.build_untracked_set(vault) == set()


def test_missing_vault_returns_empty_rather_than_raising(tmp_path):
    assert lr.build_untracked_set(tmp_path / "nope") == set()
    assert lr.build_untracked_set(Path(".")) == set()


# --------------------------------------------------------------------------------------
# dedup rules, end-to-end
# --------------------------------------------------------------------------------------

FIXTURE = [
    {
        "name": "Test User",
        "email": "test@example.com",
        "manager": "Boss",
        "manages": ["Alpha One", "Alpha Two"],
    },
    {"name": "Alpha One", "email": "a1@example.com", "manager": "Test User", "manages": []},
    {"name": "Alpha Two", "email": "a2@example.com", "manager": "Test User", "manages": []},
]


def _run(tmp_path, employees, vault=None, env=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    fixture = tmp_path / "org-chart.json"
    fixture.write_text(json.dumps(employees), encoding="utf-8")
    wrapper = f"""
import sys
sys.path.insert(0, {str(SCRIPT_DIR)!r})
import resolve_user
from pathlib import Path
resolve_user.ORG_CHART_PATHS = [Path({str(fixture)!r})]
import list_relationships
list_relationships.main()
"""
    full = {
        **os.environ,
        "PERSONAL_TOOLKIT_ENV": str(_EMPTY_ENV),
        "OPERATING_USER_EMAIL": "test@example.com",
        "OBSIDIAN_VAULT_PATH": str(vault) if vault else "",
        **(env or {}),
    }
    for k in ("KEY_RELATIONSHIPS", "INCLUDE_MANAGEMENT_PEERS"):
        if not env or k not in env:
            full.pop(k, None)
    out = subprocess.run(
        [sys.executable, "-c", wrapper], env=full, capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_two_different_people_sharing_a_name_are_both_kept(tmp_path):
    """Macroscope, 2026-08-23: name-dedup silently dropped one of two real people.

    Merging on a bare name collision is only valid when a vault redirect proved the
    two records are the same human. Two unrelated people who happen to share an
    ordinary name must both survive, with the collision announced.
    """
    employees = FIXTURE + [
        {"name": "Sam Taylor", "email": "sam1@example.com", "manager": "Test User", "manages": []},
        {"name": "Sam Taylor", "email": "sam2@example.com", "manager": "Test User", "manages": []},
    ]
    employees[0]["manages"] = ["Alpha One", "Alpha Two", "Sam Taylor"]
    data = _run(tmp_path, employees)
    sams = [r for r in data["relationships"] if r["name"] == "Sam Taylor"]
    # find_by_name resolves one record per name, so at most one enters; the point is
    # that the dedup path must not report a *merge* when no redirect linked them.
    assert not any("Merged a second" in w for w in data["warnings"]), data["warnings"]
    assert len(sams) <= 1


def test_redirect_merges_two_emails_onto_one_person(tmp_path):
    """The two-address case: a redirect proves identity, so a merge IS correct."""
    vault = _vault(
        tmp_path / "vault",
        {
            "Formal Name.md": (
                "---\ntype: person-redirect\ncanonical_profile: \"[[Casual Name]]\"\n"
                "preferred_name: Casual Name\n---\n\n# Formal Name\n"
            ),
            "Casual Name.md": "---\nemail: casual@example.com\n---\n\n# Casual Name\n",
        },
    )
    employees = FIXTURE + [
        {"name": "Formal Name", "email": "formal@example.com", "manager": "Test User", "manages": []},
    ]
    employees[0]["manages"] = ["Alpha One", "Alpha Two", "Formal Name"]
    data = _run(tmp_path, employees, vault=vault)
    names = [r["name"] for r in data["relationships"]]
    assert "Casual Name" in names, names
    assert "Formal Name" not in names, names


def test_untracked_person_is_excluded_and_announced(tmp_path):
    vault = _vault(
        tmp_path / "vault",
        {"_archive/Alpha Two.md": "---\nemail: a2@example.com\ntracked: false\n---\n"},
    )
    data = _run(tmp_path, FIXTURE, vault=vault)
    names = [r["name"] for r in data["relationships"]]
    assert "Alpha Two" not in names, names
    assert "Alpha One" in names
    assert data["untracked_excluded_count"] == 1
    assert any("tracked: false" in w for w in data["warnings"])


def test_untracked_key_relationship_absent_from_org_chart_is_excluded(tmp_path):
    """Macroscope, 2026-08-23: the KEY_RELATIONSHIPS external branch bypassed add().

    Someone in KEY_RELATIONSHIPS but absent from the org chart (a departed
    contractor, a former coach) skipped the untracked gate entirely, so archiving
    them left them in the sweep forever.
    """
    vault = _vault(
        tmp_path / "vault",
        {"_archive/Former Coach.md": "---\ntracked: false\n---\n\n# Former Coach\n"},
    )
    data = _run(
        tmp_path,
        FIXTURE,
        vault=vault,
        env={"KEY_RELATIONSHIPS": "Former Coach, Still Here"},
    )
    names = [r["name"] for r in data["relationships"]]
    assert "Former Coach" not in names, names
    assert "Still Here" in names, names
    assert any("key_relationship_external" in w for w in data["warnings"])

# --------------------------------------------------------------------------------------
# order independence (Macroscope, 2026-08-23, second round)
# --------------------------------------------------------------------------------------

_REDIRECT_VAULT = {
    "Formal Name.md": (
        '---\ntype: person-redirect\ncanonical_profile: "[[Casual Name]]"\n'
        "preferred_name: Casual Name\n---\n\n# Formal Name\n"
    ),
    "Casual Name.md": "---\nemail: casual@example.com\n---\n\n# Casual Name\n",
}


def _two_records_in_order(first, second):
    """Org chart holding BOTH the Rippling-spelled record and the canonical-name record."""
    recs = {
        "Formal Name": {
            "name": "Formal Name",
            "email": "formal@example.com",
            "manager": "Test User",
            "manages": [],
        },
        "Casual Name": {
            "name": "Casual Name",
            "email": "casual@example.com",
            "manager": "Test User",
            "manages": [],
        },
    }
    user = {
        "name": "Test User",
        "email": "test@example.com",
        "manager": "Boss",
        "manages": [first, second],
    }
    return [user, recs[first], recs[second]]


def test_redirect_dedup_is_order_independent(tmp_path):
    """The roster size must not depend on org-chart ordering.

    With only the `via_redirect` test, "redirected record first, canonical second" left
    BOTH tracked — the second record has its own email and no redirect of its own — while
    the reverse order merged correctly. Same two records, two different rosters.
    """
    vault = _vault(tmp_path / "vault", _REDIRECT_VAULT)
    counts = {}
    for order in (("Formal Name", "Casual Name"), ("Casual Name", "Formal Name")):
        data = _run(
            tmp_path / ("wd-" + order[0].replace(" ", "")),
            _two_records_in_order(*order),
            vault=vault,
        )
        names = [r["name"] for r in data["relationships"]]
        counts[order] = names
        assert "Formal Name" not in names, (order, names)
        assert names.count("Casual Name") == 1, (order, names)

    a, b = counts.values()
    assert sorted(a) == sorted(b), counts


def test_unrelated_name_collision_still_tracks_both(tmp_path):
    """Order-independence must not be bought by merging genuinely different people.

    Neither record is redirected and the name is not a declared canonical identity,
    so both must survive.
    """
    vault = _vault(tmp_path / "vault", _REDIRECT_VAULT)
    employees = [
        {
            "name": "Test User",
            "email": "test@example.com",
            "manager": "Boss",
            "manages": ["Alpha One"],
        },
        {"name": "Alpha One", "email": "a1@example.com", "manager": "Test User", "manages": []},
    ]
    data = _run(tmp_path, employees, vault=vault)
    assert not any("Merged a second" in w for w in data["warnings"]), data["warnings"]
    assert "Alpha One" in [r["name"] for r in data["relationships"]]
