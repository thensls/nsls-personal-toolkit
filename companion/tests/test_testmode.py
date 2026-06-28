"""Tests for `-t` test mode: vault-path resolution, the reset-day guard, and
the server's TEST marker."""

from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner

from companion import testmode
from companion.cli import main
from companion.server import create_app
from companion.testmode import (
    TEST_VAULT_NAME,
    assert_test_vault,
    default_test_vault,
    ensure_test_vault,
    is_test_vault,
)


# --- path resolution -------------------------------------------------------

def test_default_test_vault_is_named_correctly():
    assert default_test_vault().name == TEST_VAULT_NAME


def test_is_test_vault_true_for_test_named_dir(tmp_path):
    assert is_test_vault(tmp_path / TEST_VAULT_NAME) is True


def test_is_test_vault_false_for_real_vault(tmp_path):
    assert is_test_vault(tmp_path / "my-obsidian-vault") is False


def test_is_test_vault_false_for_empty():
    assert is_test_vault(None) is False
    assert is_test_vault("") is False


def test_is_test_vault_resolves_relative_trailing_slash(tmp_path):
    # A trailing slash or relative form must not defeat the name check.
    p = tmp_path / TEST_VAULT_NAME
    assert is_test_vault(str(p) + "/") is True


# --- reset-day guard -------------------------------------------------------

def test_assert_test_vault_passes_for_test_vault(tmp_path):
    p = tmp_path / TEST_VAULT_NAME
    p.mkdir()
    assert assert_test_vault(p) == p.resolve()


def test_assert_test_vault_raises_for_real_vault(tmp_path):
    real = tmp_path / "real-vault"
    real.mkdir()
    with pytest.raises(ValueError, match="non-test vault"):
        assert_test_vault(real)


def test_assert_test_vault_raises_for_empty():
    with pytest.raises(ValueError):
        assert_test_vault("")


# --- seeding ---------------------------------------------------------------

@pytest.fixture
def test_vault_at(tmp_path, monkeypatch):
    """Point the test-vault helpers at a tmp location so we never touch the
    real ~/.claude test vault during tests."""
    target = tmp_path / TEST_VAULT_NAME
    monkeypatch.setattr(testmode, "default_test_vault", lambda: target)
    return target


def test_ensure_test_vault_creates_structure_and_sample(test_vault_at):
    vault = ensure_test_vault()
    assert vault == test_vault_at
    assert (vault / "01-daily").is_dir()
    assert (vault / "30-habits").is_dir()
    today = vault / "01-daily" / f"{date.today().isoformat()}.md"
    assert today.exists()
    assert "status: active" in today.read_text(encoding="utf-8")
    # Sample habits seeded so there's something to tick.
    assert "- id:" in (vault / "30-habits" / "habits.md").read_text(encoding="utf-8")


def test_ensure_test_vault_does_not_overwrite_existing_today(test_vault_at):
    ensure_test_vault()
    today = test_vault_at / "01-daily" / f"{date.today().isoformat()}.md"
    today.write_text("MY EDITS", encoding="utf-8")
    ensure_test_vault()  # idempotent re-run
    assert today.read_text(encoding="utf-8") == "MY EDITS"


def test_ensure_test_vault_no_seed_skips_today(test_vault_at):
    vault = ensure_test_vault(seed_today=False)
    today = vault / "01-daily" / f"{date.today().isoformat()}.md"
    assert not today.exists()


# --- server TEST marker ----------------------------------------------------

def _seed_minimal(vault: Path):
    (vault / "01-daily").mkdir(parents=True)
    (vault / "30-habits").mkdir(parents=True)
    (vault / "30-habits" / "habits.md").write_text("# Daily Habits\n\n## Active\n", encoding="utf-8")
    (vault / "30-habits" / "log.md").write_text("# Log\n", encoding="utf-8")


def _client(vault: Path):
    app = create_app(vault_path=str(vault))
    app.config["TESTING"] = True
    return app


def test_server_marks_test_mode_for_test_vault(tmp_path):
    vault = tmp_path / TEST_VAULT_NAME
    _seed_minimal(vault)
    app = _client(vault)
    assert app.config["TEST_MODE"] is True
    try:
        resp = app.test_client().get("/")
        assert b"nsls-test-bar" in resp.data
        assert b"Test vault" in resp.data
    finally:
        app.config["WATCHER"].stop()


def test_server_no_test_mode_for_real_vault(tmp_path):
    vault = tmp_path / "real-vault"
    _seed_minimal(vault)
    app = _client(vault)
    assert app.config["TEST_MODE"] is False
    try:
        resp = app.test_client().get("/")
        assert b"nsls-test-bar" not in resp.data
    finally:
        app.config["WATCHER"].stop()


# --- CLI guard -------------------------------------------------------------

def test_cli_assert_test_vault_exit_zero_for_test_vault(tmp_path):
    p = tmp_path / TEST_VAULT_NAME
    p.mkdir()
    result = CliRunner().invoke(main, ["assert-test-vault", str(p)])
    assert result.exit_code == 0
    assert str(p.resolve()) in result.output


def test_cli_assert_test_vault_exit_nonzero_for_real_vault(tmp_path):
    real = tmp_path / "real-vault"
    real.mkdir()
    result = CliRunner().invoke(main, ["assert-test-vault", str(real)])
    assert result.exit_code == 1
    assert "non-test vault" in result.output


def test_cli_test_vault_seeds_and_prints_path(tmp_path, monkeypatch):
    target = tmp_path / TEST_VAULT_NAME
    monkeypatch.setattr(testmode, "default_test_vault", lambda: target)
    result = CliRunner().invoke(main, ["test-vault"])
    assert result.exit_code == 0
    assert str(target) in result.output
    assert (target / "01-daily" / f"{date.today().isoformat()}.md").exists()
