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


# --- wait-done: the same-machine "webhook" for the Done/Lock-in click ---

def _write_note(vault, day, status):
    (vault / "01-daily").mkdir(parents=True, exist_ok=True)
    (vault / "01-daily" / f"{day}.md").write_text(
        f"---\nstatus: {status}\n---\n# Daily Note\n\n## Morning Check-in\n",
        encoding="utf-8",
    )


def test_wait_for_status_returns_immediately_when_already_there(tmp_path):
    from companion.cli import wait_for_status
    _write_note(tmp_path, "2026-07-11", "closed")
    assert wait_for_status(tmp_path, "2026-07-11", "closed", timeout=2, poll=0.05) == "closed"


def test_wait_for_status_wakes_on_flip(tmp_path):
    import threading, time
    from companion.cli import wait_for_status
    _write_note(tmp_path, "2026-07-11", "planning")

    def flip():
        time.sleep(0.2)
        _write_note(tmp_path, "2026-07-11", "active")

    t = threading.Thread(target=flip)
    t.start()
    got = wait_for_status(tmp_path, "2026-07-11", "active", timeout=5, poll=0.05)
    t.join()
    assert got == "active"


def test_wait_for_status_any_fires_on_note_appearing(tmp_path):
    import threading, time
    from companion.cli import wait_for_status

    def create():
        time.sleep(0.2)
        _write_note(tmp_path, "2026-07-11", "planning")

    t = threading.Thread(target=create)
    t.start()
    got = wait_for_status(tmp_path, "2026-07-11", "any", timeout=5, poll=0.05)
    t.join()
    assert got == "planning"


def test_wait_for_status_times_out(tmp_path):
    from companion.cli import wait_for_status
    _write_note(tmp_path, "2026-07-11", "planning")
    assert wait_for_status(tmp_path, "2026-07-11", "closed", timeout=0.3, poll=0.05) is None


def test_wait_for_status_close_ready_fires_on_button_flag(tmp_path):
    import threading, time
    from companion.cli import wait_for_status
    _write_note(tmp_path, "2026-07-11", "active")

    def click():
        time.sleep(0.2)
        note = tmp_path / "01-daily" / "2026-07-11.md"
        note.write_text(note.read_text().replace(
            "status: active", "status: active\nclose_ready: 1"), encoding="utf-8")

    t = threading.Thread(target=click)
    t.start()
    got = wait_for_status(tmp_path, "2026-07-11", "close-ready", timeout=5, poll=0.05)
    t.join()
    assert got == "close-ready"


def test_wait_for_status_close_ready_also_fires_on_closed(tmp_path):
    from companion.cli import wait_for_status
    _write_note(tmp_path, "2026-07-11", "closed")
    assert wait_for_status(tmp_path, "2026-07-11", "close-ready", timeout=2, poll=0.05) == "closed"


def test_wait_close_ready_does_not_fire_on_stale_flag(tmp_path):
    """A close_ready:1 already present at arm time must NOT fire instantly —
    that stale-flag instant-return was misread as a 'clock jump' (2026-07-13,
    Davo). It should wait for the next real transition."""
    from companion.cli import wait_for_status
    (tmp_path / "01-daily").mkdir(parents=True)
    (tmp_path / "01-daily" / "2026-07-11.md").write_text(
        "---\nstatus: active\nclose_ready: 1\n---\n# n\n", encoding="utf-8")
    # target already satisfied at arm → should time out, not fire
    assert wait_for_status(tmp_path, "2026-07-11", "close-ready", timeout=0.3, poll=0.05) is None


def test_wait_close_ready_fires_on_fresh_transition(tmp_path):
    import threading, time
    from companion.cli import wait_for_status
    (tmp_path / "01-daily").mkdir(parents=True)
    note = tmp_path / "01-daily" / "2026-07-11.md"
    note.write_text("---\nstatus: active\n---\n# n\n", encoding="utf-8")

    def click():
        time.sleep(0.2)
        note.write_text("---\nstatus: active\nclose_ready: 1\n---\n# n\n", encoding="utf-8")

    t = threading.Thread(target=click); t.start()
    got = wait_for_status(tmp_path, "2026-07-11", "close-ready", timeout=5, poll=0.05)
    t.join()
    assert got == "close-ready"


def test_wait_close_ready_already_closed_returns_immediately(tmp_path):
    """A genuinely already-closed day has nothing left to wait for."""
    from companion.cli import wait_for_status
    (tmp_path / "01-daily").mkdir(parents=True)
    (tmp_path / "01-daily" / "2026-07-11.md").write_text(
        "---\nstatus: closed\n---\n# n\n", encoding="utf-8")
    assert wait_for_status(tmp_path, "2026-07-11", "close-ready", timeout=2, poll=0.05) == "closed"


def test_wait_active_fires_on_planning_to_active(tmp_path):
    import threading, time
    from companion.cli import wait_for_status
    (tmp_path / "01-daily").mkdir(parents=True)
    note = tmp_path / "01-daily" / "2026-07-11.md"
    note.write_text("---\nstatus: planning\n---\n# n\n", encoding="utf-8")

    def lock():
        time.sleep(0.2)
        note.write_text("---\nstatus: active\n---\n# n\n", encoding="utf-8")

    t = threading.Thread(target=lock); t.start()
    got = wait_for_status(tmp_path, "2026-07-11", "active", timeout=5, poll=0.05)
    t.join()
    assert got == "active"
