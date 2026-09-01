"""Project inference must not mis-attribute, and the frontmatter sync must converge.

Both defects here were found by the 2026-08-23 person-intelligence sweep and both were
silent — the wrong answer looked exactly like the right one.

1. `infer_projects.py` matched keywords as bare case-insensitive SUBSTRINGS. `HR` matched
   "Ant**hr**opic billing review" and tagged it `people-ops`; `board` matched "dash**board**
   redesign" and tagged it `board-intelligence`. The wrong project then appeared in a
   person's profile *with the sentence as its evidence*, which reads as a finding. The map
   also had no `society` entry at all, so every Society mention inferred nothing and had to
   be written by hand.

2. `sync_obsidian_frontmatter.py` visited every org-chart record in sequence, so two records
   resolving to the same profile each wrote `email` in turn. It oscillated between the two
   addresses forever — a diff that is never clean.

Run: python3 -m pytest skills/person-intelligence/tests/test_inference_and_collisions.py -q
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import infer_projects as ip  # noqa: E402
import sync_obsidian_frontmatter as sync  # noqa: E402


def _infer(*texts):
    out = subprocess.run(
        [sys.executable, str(SCRIPTS / "infer_projects.py")],
        input=json.dumps({"topics": list(texts), "goals": [], "actions": [], "person_name": "T"}),
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    d = json.loads(out.stdout)
    return {x["project"] for x in d["confirmed"] + d["suggested"]}


# ---------------------------------------------------------------------------------------
# infer_projects — word boundaries
# ---------------------------------------------------------------------------------------


def test_hr_inside_anthropic_does_not_tag_people_ops():
    """The reported case. `HR` is a substring of 'Anthropic'."""
    assert "people-ops" not in _infer("Anthropic billing review")


def test_board_inside_dashboard_does_not_tag_board_intelligence():
    """The reported case. `board` is a substring of 'dashboard'."""
    assert "board-intelligence" not in _infer("dashboard redesign for advisors")


def test_the_org_name_alone_matches_nothing():
    """'The National Society of Leadership and Success' is ordinary NSLS prose.

    It appears constantly, so any project keyed on the bare word `society` would fire on
    every document. `product-roadshow` used to carry that keyword and did exactly that.
    """
    assert _infer("the National Society of Leadership and Success") == set()


def test_real_mentions_still_match():
    """Guards against fixing the false positives by breaking every true positive."""
    for text, expected in [
        ("HR policy review", "people-ops"),
        ("improve our CAC", "marketing"),
        ("LTV modelling", "marketing"),
        ("reduce ARPM churn", "marketing"),
        ("the board intelligence deck", "board-intelligence"),
        ("JIRA ticket triage", "product-ops"),
        ("product roadshow planning", "product-roadshow"),
        ("Ignite demo for chapters", "product-roadshow"),
    ]:
        assert expected in _infer(text), f"{text!r} lost its {expected} match"


def test_society_project_exists_and_matches():
    """The map had no `society` key, so Society work inferred nothing."""
    for text in [
        "Society launch readiness",
        "SNT testing on Society",
        "Welcome track completion rate",
        "members on Society orientation",
    ]:
        assert "society" in _infer(text), f"{text!r} did not match society"
    assert "society-profiles" in _infer("member profile page work")


def test_acronyms_are_matched_case_sensitively():
    """An all-caps keyword <=5 chars is an initialism; lowercasing invites collisions."""
    m = ip._matcher("HR")
    assert m.search("HR policy")
    assert not m.search("the hr in Anthropic")
    # Non-acronyms stay case-insensitive.
    assert ip._matcher("board meeting").search("Board Meeting tomorrow")


def test_keyword_with_regex_metacharacters_is_escaped():
    """`make.com` contains a regex dot; unescaped it would match 'makeXcom'."""
    m = ip._matcher("make.com")
    assert m.search("we use make.com for that")
    assert not m.search("makeXcom")


# ---------------------------------------------------------------------------------------
# sync_obsidian_frontmatter — collision convergence
# ---------------------------------------------------------------------------------------


def _profile(tmp_path, name, email):
    p = tmp_path / f"{name}.md"
    p.write_text(f"---\ntype: person\nemail: {email}\n---\n\n# {name}\n", encoding="utf-8")
    return p


def test_single_record_wins_outright(tmp_path):
    p = _profile(tmp_path, "Solo Person", "solo@example.com")
    emp = {"name": "Solo Person", "email": "solo@example.com"}
    chosen, collisions = sync.resolve_collisions({p: [emp]})
    assert chosen[p] == (emp, False)
    assert collisions == []


def test_two_records_on_one_file_keep_the_files_existing_email(tmp_path):
    """The reported case, and the property that makes the sync idempotent.

    A person holding an agency address plus a work one appears as two org-chart records.
    The record carrying the address the file already uses must win every run, or `email`
    ping-pongs and the sync never reports a clean tree.
    """
    p = _profile(tmp_path, "Two Addr", "agency@example.com")
    a = {"name": "Two Addr", "email": "agency@example.com"}
    b = {"name": "Formal Name", "email": "work@example.org"}
    for order in ([a, b], [b, a]):  # order-independent
        chosen, collisions = sync.resolve_collisions({p: order})
        emp, drop_email = chosen[p]
        assert emp["email"] == "agency@example.com", order
        assert drop_email is False
        assert len(collisions) == 1
        assert collisions[0]["email_written"] is True


def test_when_no_record_matches_the_email_is_left_alone(tmp_path):
    """A curated address in neither record must not be overwritten by a coin flip."""
    p = _profile(tmp_path, "Curated", "chosen-by-hand@example.com")
    a = {"name": "Alpha", "email": "a@example.com"}
    b = {"name": "Beta", "email": "b@example.com"}
    chosen, collisions = sync.resolve_collisions({p: [a, b]})
    emp, drop_email = chosen[p]
    assert drop_email is True, "email must be dropped, not guessed"
    assert emp["name"] == "Alpha", "winner must be deterministic (sorted by name)"
    assert collisions[0]["email_written"] is False


def test_dropped_email_produces_no_email_change(tmp_path):
    """drop_email has to reach diff_employee, not just the collision report."""
    p = _profile(tmp_path, "Curated", "chosen-by-hand@example.com")
    emp = {"name": "Alpha", "email": "a@example.com", "title": "Engineer"}
    fields = [f for f, _, _ in sync.diff_employee(emp, p, {}, drop_email=True)]
    assert "email" not in fields
    assert "title" in fields, "other fields must still sync"
    fields_nodrop = [f for f, _, _ in sync.diff_employee(emp, p, {}, drop_email=False)]
    assert "email" in fields_nodrop, "the guard must be what suppressed it"


def test_existing_email_reads_missing_frontmatter_safely(tmp_path):
    p = tmp_path / "NoFrontmatter.md"
    p.write_text("# Just a heading\n", encoding="utf-8")
    assert sync.existing_email(p) == ""
    assert sync.existing_email(tmp_path / "does-not-exist.md") == ""
