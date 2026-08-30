import os
import socket
import time as _time

from click.testing import CliRunner

from companion import cli
from companion.cli import _find_free_port, ensure_vault_structure, TEMPLATES_DIR


def _write_pidfile(path, pid, addr="127.0.0.1:1"):
    # Port 1 is never listening — a live pid with an unresponsive port.
    path.write_text(f"{pid}\n{addr}\n", encoding="utf-8")


def test_status_grace_window_reports_starting_and_never_reaps(tmp_path, monkeypatch):
    """P2: a fresh pidfile + live pid + port not yet bound is a BOOTING server.

    `status` used to SIGTERM it (killing a healthy companion ~2s after start).
    Inside STARTUP_GRACE_SECONDS it must report Starting and touch nothing.
    """
    pidfile = tmp_path / "companion.pid"
    _write_pidfile(pidfile, os.getpid())
    monkeypatch.setattr(cli, "PID_FILE", pidfile)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)  # keep the retry loop instant
    terminated = []
    real_kill = os.kill

    def guarded_kill(pid, sig):
        if sig == cli.signal.SIGTERM:
            terminated.append(pid)
            return
        return real_kill(pid, sig)  # liveness probes (sig 0) stay real

    monkeypatch.setattr(cli.os, "kill", guarded_kill)
    result = CliRunner().invoke(cli.main, ["status"])
    assert "Starting:" in result.output
    assert result.exit_code == 0
    assert terminated == []
    assert pidfile.exists()


def test_status_reaps_after_grace_window(tmp_path, monkeypatch):
    """Past the grace window, a live pid with a dead port is still cleaned up."""
    pidfile = tmp_path / "companion.pid"
    _write_pidfile(pidfile, os.getpid())
    old = _time.time() - (cli.STARTUP_GRACE_SECONDS + 60)
    os.utime(pidfile, (old, old))
    monkeypatch.setattr(cli, "PID_FILE", pidfile)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    terminated = []
    real_kill = os.kill

    def guarded_kill(pid, sig):
        if sig == cli.signal.SIGTERM:
            terminated.append(pid)
            return
        return real_kill(pid, sig)

    monkeypatch.setattr(cli.os, "kill", guarded_kill)
    result = CliRunner().invoke(cli.main, ["status"])
    assert "Not running (process alive but port not responding" in result.output
    assert result.exit_code == 1
    assert terminated == [os.getpid()]
    assert not pidfile.exists()


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
    a builder). It should wait for the next real transition."""
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


# --- §3.7: wait_for_status pings the listener heartbeat while it waits --------

def test_wait_for_status_pings_heartbeat_each_poll(tmp_path):
    """The heartbeat hook fires while waiting so a Done/close click can tell a
    listener is attached. (§3.7)"""
    from companion.cli import wait_for_status
    _write_note(tmp_path, "2026-07-11", "planning")
    calls = []
    # Target never reached → times out after a couple polls; heartbeat fires.
    wait_for_status(tmp_path, "2026-07-11", "closed", timeout=0.25, poll=0.05,
                    heartbeat=lambda: calls.append(1))
    assert len(calls) >= 1


def test_wait_for_status_swallows_heartbeat_errors(tmp_path):
    """A raising heartbeat (companion down) must not break the wait — the file
    transition is the durable signal. (§3.7)"""
    from companion.cli import wait_for_status
    _write_note(tmp_path, "2026-07-11", "planning")

    def boom():
        raise RuntimeError("server down")

    assert wait_for_status(tmp_path, "2026-07-11", "closed", timeout=0.2,
                           poll=0.05, heartbeat=boom) is None


def test_read_pidfile_addr(tmp_path):
    """_read_pidfile_addr returns the address line, or None when missing/malformed."""
    from companion.cli import _read_pidfile_addr
    pf = tmp_path / ".companion.pid"
    pf.write_text("12345\n127.0.0.1:7777\n", encoding="utf-8")
    assert _read_pidfile_addr(pf) == "127.0.0.1:7777"
    # No 2nd line → None
    pf.write_text("12345\n", encoding="utf-8")
    assert _read_pidfile_addr(pf) is None
    # Missing file → None
    assert _read_pidfile_addr(tmp_path / "nope.pid") is None


def test_python_path_prints_a_runnable_interpreter_that_can_import_companion():
    """close-week Step 2a runs `"$PY" -m companion.portfolio`, so it needs the
    INTERPRETER, not this console script. `$(dirname "$TC")/python` guessed it
    from the binary's directory, which is empty of Python on ensure-companion's
    PATH-fallback resolution -- the one case that derivation existed for. The
    binary answering for itself cannot be wrong: it is the interpreter.
    """
    import subprocess
    import sys
    from pathlib import Path

    result = CliRunner().invoke(cli.main, ["python-path"])
    assert result.exit_code == 0
    printed = result.output.strip()
    assert printed == sys.executable
    assert os.path.exists(printed)

    # And it really can run the module the skill runs -- including the
    # >=3.10 syntax (`str | None`) that a stock Mac's /usr/bin/python3 3.9
    # cannot even import.
    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [printed, "-m", "companion.portfolio", "--parse-daily"],
        input="", capture_output=True, text=True, cwd=repo_root,
    )
    assert proc.returncode == 0, proc.stderr

    # THE PROPERTY THAT ACTUALLY MATTERS: the INTERPRETER supplies
    # `companion`, not the current directory. close-week Step 2a runs
    # `"$PY" -m companion.portfolio` from the session's cwd -- the vault, or
    # $HOME -- never from this repo. Run with cwd=repo_root only, the
    # assertion above proves the cwd can supply the package, which is true of
    # any interpreter on earth and so proves nothing about this one.
    import pytest
    import tempfile
    neutral = tempfile.mkdtemp()
    proc = subprocess.run(
        [printed, "-m", "companion.portfolio", "--parse-daily"],
        input="", capture_output=True, text=True, cwd=neutral,
    )
    if proc.returncode != 0 and "No module named 'companion'" in proc.stderr:
        # An uninstalled source checkout: pytest puts the rootdir on sys.path,
        # a bare subprocess does not. SKIPPED WITH THE REASON NAMED rather
        # than quietly passing -- the installed companion venv that
        # ensure-companion.sh builds does satisfy this, and that is the one
        # the skill runs.
        pytest.skip("`companion` is not installed into this interpreter "
                    "(uninstalled source checkout); the cwd-independence "
                    "property cannot be proven here")
    assert proc.returncode == 0, proc.stderr
