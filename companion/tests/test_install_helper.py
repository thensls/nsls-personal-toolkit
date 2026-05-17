import os
import plistlib
import pytest
from pathlib import Path
from companion.install_helper import write_plist, resolve_vault


def test_write_plist_creates_valid_plist(tmp_path):
    dest = tmp_path / "test.plist"
    write_plist(vault="/tmp/test-vault", dest=str(dest), python_exe="/usr/bin/python3")
    assert dest.exists()
    assert dest.stat().st_mode & 0o777 == 0o600
    with open(dest, "rb") as f:
        plist = plistlib.load(f)
    assert plist["Label"] == "com.nsls.toolkit-companion"
    assert plist["EnvironmentVariables"]["OBSIDIAN_VAULT_PATH"] == "/tmp/test-vault"
    assert plist["ProgramArguments"][0] == "/usr/bin/python3"
    assert plist["ProgramArguments"][-2:] == ["serve", "--no-open"]
    assert plist["RunAtLoad"] is True


def test_write_plist_handles_special_chars_in_vault_path(tmp_path):
    """Paths with spaces, quotes, or shell metacharacters must serialize safely."""
    dest = tmp_path / "test.plist"
    weird_path = "/tmp/My Vault $with quotes' & symbols"
    write_plist(vault=weird_path, dest=str(dest))
    with open(dest, "rb") as f:
        plist = plistlib.load(f)
    assert plist["EnvironmentVariables"]["OBSIDIAN_VAULT_PATH"] == weird_path


def test_resolve_vault_uses_env_var_when_valid(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "01-daily").mkdir(parents=True)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    assert resolve_vault() == str(vault)


def test_resolve_vault_skips_env_var_without_01_daily(tmp_path, monkeypatch, capsys):
    # If env var is set but doesn't point at a real vault, falls through to
    # builder-profile or prompt. With no profile and no input, it would block
    # on input() — so we monkeypatch input.
    bad_vault = tmp_path / "novault"
    bad_vault.mkdir()  # no 01-daily/
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(bad_vault))
    # Also monkeypatch the PROFILE_PATH so it doesn't accidentally find one
    from companion import install_helper
    monkeypatch.setattr(install_helper, "PROFILE_PATH", tmp_path / "nonexistent")
    monkeypatch.setattr("builtins.input", lambda: "/from-prompt")
    assert resolve_vault() == "/from-prompt"
