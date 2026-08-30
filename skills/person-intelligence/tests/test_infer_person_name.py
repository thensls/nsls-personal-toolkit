"""infer_person_name must know who the operator is, or refuse.

The operator's names used to be a hardcoded tuple, which published a real
identity in a PUBLIC repo and hardwired the skill to one installation. It now
reads OPERATING_USER_NAME, and an unset value disables title inference rather
than guessing which half of a 1:1 title is the subject.
"""
import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "summarize_meeting.py"


@contextlib.contextmanager
def _load(operating_user_name):
    """Yield a freshly imported module with OPERATING_USER_NAME set for the body.

    It must stay set for the DURATION of the test: this module reads the env
    inside infer_person_name(), not at import time. Restoring it before the
    assertions ran is what made the first version of this helper lie.
    """
    prior = os.environ.pop("OPERATING_USER_NAME", None)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        if operating_user_name is not None:
            os.environ["OPERATING_USER_NAME"] = operating_user_name
        spec = importlib.util.spec_from_file_location("summarize_meeting", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.path.pop(0)
        os.environ.pop("OPERATING_USER_NAME", None)
        if prior is not None:
            os.environ["OPERATING_USER_NAME"] = prior


def test_unset_refuses_and_warns():
    """No operator configured -> refuse every title, and say why. Once."""
    with _load(None) as mod:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            first = mod.infer_person_name("Ada Lovelace / Grace Hopper 1:1")
            second = mod.infer_person_name("Alan Turing / Grace Hopper 1:1")
        assert first == mod.UNKNOWN_SUBJECT, "must refuse, not guess a half"
        assert second == mod.UNKNOWN_SUBJECT
        out = err.getvalue()
        assert "OPERATING_USER_NAME is unset" in out
        assert out.count("OPERATING_USER_NAME is unset") == 1, "warn once, not per call"


def test_configured_returns_the_other_party():
    """With the operator known, the OTHER half is the subject."""
    with _load("Grace Hopper,Grace,GH") as mod:
        assert mod.infer_person_name("Ada Lovelace / Grace Hopper 1:1") == "Ada Lovelace"
        assert mod.infer_person_name("Grace Hopper / Ada Lovelace 1:1") == "Ada Lovelace"
        assert mod.infer_person_name("Ada Lovelace <> Grace") == "Ada Lovelace"


def test_aliases_are_case_insensitive():
    """Alias matching ignores case; the returned name keeps the title's casing."""
    with _load("grace hopper") as mod:
        assert mod.infer_person_name("Ada Lovelace / GRACE HOPPER") == "Ada Lovelace"


def test_group_titles_still_refuse():
    """The group-word guard is unaffected by the operator change."""
    with _load("Grace Hopper") as mod:
        assert mod.infer_person_name("Sprint Retro - Platform") == mod.UNKNOWN_SUBJECT
        assert mod.infer_person_name("") == mod.UNKNOWN_SUBJECT


def test_operator_only_title_refuses():
    """A title naming nobody but the operator yields no subject."""
    with _load("Grace Hopper,Grace") as mod:
        assert mod.infer_person_name("Grace Hopper / Grace") == mod.UNKNOWN_SUBJECT


def test_missing_alias_variant_returns_the_operator():
    """Documented sharp edge: list EVERY variant that appears in your titles.

    With only the full name configured, a title using the short form has no
    alias to match, so the operator's own short name is returned as the
    subject. That is why the docstring says comma-separated variants.
    """
    with _load("Grace Hopper") as mod:
        assert mod.infer_person_name("Grace Hopper / Grace") == "Grace"
