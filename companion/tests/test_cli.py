import socket
from companion.cli import _find_free_port, ensure_vault_structure, TEMPLATES_DIR


def test_find_free_port_returns_int():
    port = _find_free_port(start=15000)
    assert isinstance(port, int)
    assert 15000 <= port < 15100


def test_find_free_port_skips_occupied():
    # Occupy 15000
    s = socket.socket()
    s.bind(("127.0.0.1", 15000))
    try:
        port = _find_free_port(start=15000)
        assert port != 15000
        assert 15001 <= port < 15100
    finally:
        s.close()


def test_ensure_vault_structure_creates_missing_dirs_and_seeds_files(tmp_path):
    vault = tmp_path / "fresh-vault"
    vault.mkdir()
    created = ensure_vault_structure(vault)
    # All three expected subdirs exist
    assert (vault / "01-daily").is_dir()
    assert (vault / "02-weekly").is_dir()
    assert (vault / "30-habits").is_dir()
    # Templates copied
    assert (vault / "30-habits" / "habits.md").exists()
    assert (vault / "30-habits" / "log.md").exists()
    # habits.md starts empty — examples removed 2026-05-18 because seeding
    # Walk/Read as defaults confused users who hadn't added them themselves.
    # The morning Coach Card surfaces an onboarding banner instead.
    habits_text = (vault / "30-habits" / "habits.md").read_text()
    assert "Walk" not in habits_text
    assert "Read" not in habits_text
    assert "(none yet" in habits_text
    # Reported what it did
    assert any("01-daily" in line for line in created)
    assert any("habits.md" in line for line in created)


def test_ensure_vault_structure_idempotent(tmp_path):
    vault = tmp_path / "existing-vault"
    vault.mkdir()
    (vault / "01-daily").mkdir()
    (vault / "30-habits").mkdir()
    # Pre-existing habits.md with user customization — must NOT be overwritten
    (vault / "30-habits" / "habits.md").write_text("# My custom habits\n")
    ensure_vault_structure(vault)
    # User's content preserved
    assert (vault / "30-habits" / "habits.md").read_text() == "# My custom habits\n"
    # log.md was missing — should now be seeded
    assert (vault / "30-habits" / "log.md").exists()
    # 02-weekly was missing — created
    assert (vault / "02-weekly").is_dir()
    # Second call is a no-op (returns empty list)
    created = ensure_vault_structure(vault)
    assert created == []


def test_ensure_vault_structure_templates_dir_exists():
    """The shipped templates dir must actually contain the files we depend on."""
    assert TEMPLATES_DIR.is_dir(), f"Templates dir missing: {TEMPLATES_DIR}"
    assert (TEMPLATES_DIR / "habits.md.template").exists()
    assert (TEMPLATES_DIR / "log.md.template").exists()
