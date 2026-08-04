"""toolkit-companion CLI: serve, stop, status."""

import os
import shutil
import signal
import socket
import sys
import time
import webbrowser
from pathlib import Path

import click


_PLUGIN_DIR = Path.home() / ".claude" / "local-plugins" / "nsls-personal-toolkit"
PID_FILE = _PLUGIN_DIR / ".companion.pid"
# Test mode runs as a fully separate instance: its own pidfile and its own
# default port, so `open day -t` can never displace, stop, or be confused with
# the real companion the regular `open day` runs on 7777.
TEST_PID_FILE = _PLUGIN_DIR / ".companion-test.pid"
DEFAULT_PORT = 7777
TEST_DEFAULT_PORT = 7788
# `status` won't reap a non-responding server whose pidfile is younger than
# this — Flask needs a beat to bind, and reaping inside that window kills
# healthy servers.
STARTUP_GRACE_SECONDS = 15
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _pid_alive(pid: int) -> bool:
    """Liveness probe that is safe on every OS.

    Never use ``os.kill(pid, 0)`` on Windows: there, any signal other than
    the CTRL events is routed to TerminateProcess — the "check" would kill
    the running server. Probe with OpenProcess instead.
    """
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but owned by another user
    return True


def _read_pidfile_addr(pid_file: Path):
    """Return the ``host:port`` recorded on the pidfile's 2nd line, or None.

    ``serve`` writes ``<pid>\\n<host>:<port>\\n``; wait-done reads line 2 to find
    the running companion so it can ping /listener-heartbeat. None whenever the
    file is missing or malformed — the caller then simply skips heartbeats.
    """
    try:
        lines = pid_file.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError):
        return None
    return lines[1] if len(lines) > 1 and lines[1].strip() else None


def _find_free_port(start: int = DEFAULT_PORT) -> int:
    for port in range(start, start + 100):
        with socket.socket() as s:
            # Match the server's own bind semantics (werkzeug binds with
            # SO_REUSEADDR): without it, TIME_WAIT sockets left by a
            # just-stopped instance make the default port look busy and a
            # stop→start restart silently drifts to the next port.
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")


def ensure_vault_structure(vault_path: Path, templates_dir: Path = TEMPLATES_DIR) -> list[str]:
    """Idempotently create the directories and seed files the companion expects.

    Returns a list of human-readable strings describing what was created (empty
    if nothing was missing). Safe to call on every startup — existing files are
    never overwritten.
    """
    created: list[str] = []
    for sub in ("01-daily", "02-weekly", "30-habits"):
        d = vault_path / sub
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(f"created {sub}/")
    for name in ("habits.md", "log.md"):
        dest = vault_path / "30-habits" / name
        if dest.exists():
            continue
        src = templates_dir / f"{name}.template"
        if not src.exists():
            continue
        shutil.copyfile(src, dest)
        created.append(f"seeded 30-habits/{name} from template")
    return created


@click.group()
def main():
    """NSLS toolkit web companion."""


@main.command()
@click.option("--vault", default=None, help="Override vault path (defaults to OBSIDIAN_VAULT_PATH env var)")
@click.option("--port", default=None, type=int, help="Port (default: 7777, or 7788 for a test vault)")
@click.option("--no-open", is_flag=True, help="Don't open the browser")
def serve(vault, port, no_open):
    """Start the local web companion."""
    vault = vault or os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        click.echo("Set OBSIDIAN_VAULT_PATH or pass --vault", err=True)
        sys.exit(1)
    vault_path = Path(vault)
    if not vault_path.is_dir():
        click.echo(f"Vault path is not a directory: {vault}", err=True)
        sys.exit(1)
    for line in ensure_vault_structure(vault_path):
        click.echo(f"  {line}")
    from companion.testmode import is_test_vault
    test_mode = is_test_vault(vault_path)
    # A test server is a separate instance: its own pidfile and its own default
    # port, so it can never collide with the real companion on 7777.
    pid_file = TEST_PID_FILE if test_mode else PID_FILE
    if test_mode:
        click.echo("  TEST vault — practice data; your real day is untouched.")
    port = port or _find_free_port(TEST_DEFAULT_PORT if test_mode else DEFAULT_PORT)
    host = "127.0.0.1"

    from companion.server import create_app
    app = create_app(vault_path=str(vault_path))

    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f"{os.getpid()}\n{host}:{port}\n", encoding="utf-8", newline="")
    pid_file.chmod(0o600)

    url = f"http://{host}:{port}"
    click.echo(f"Serving at {url}")
    if not no_open:
        if not webbrowser.open(url):
            click.echo(f"Couldn't open a browser automatically — visit {url}")

    try:
        # threaded=True is required, not optional: the SSE /events endpoint holds
        # a connection open indefinitely, so a single-threaded server would block
        # all other requests behind it. Concurrency is therefore real, which is
        # why every vault write goes through safe_modify's exclusive lock.
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    finally:
        try:
            pid_file.unlink()
        except FileNotFoundError:
            pass


@main.command("test-vault")
@click.option("--no-seed", is_flag=True, help="Create the vault structure but don't seed a sample day.")
def test_vault(no_seed):
    """Ensure the throwaway test vault exists (seeded) and print its path.

    Skills use this in `-t` mode: `export OBSIDIAN_VAULT_PATH=$(toolkit-companion
    test-vault)`. Idempotent — never overwrites an existing note.
    """
    from companion.testmode import ensure_test_vault
    vault = ensure_test_vault(seed_today=not no_seed)
    click.echo(str(vault))


@main.command("assert-test-vault")
@click.argument("path")
def assert_test_vault_cmd(path):
    """Exit 0 only if PATH is the test vault; non-zero otherwise.

    reset-day `-t` calls this before deleting, so a stray OBSIDIAN_VAULT_PATH
    pointing at real data can never be wiped under test mode.
    """
    from companion.testmode import assert_test_vault
    try:
        resolved = assert_test_vault(path)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    click.echo(str(resolved))


@main.command()
@click.option("--test", "test_mode", is_flag=True, help="Target the test companion (its own pidfile), not the real one.")
def stop(test_mode):
    """Stop a running companion server."""
    pid_file = TEST_PID_FILE if test_mode else PID_FILE
    if not pid_file.exists():
        click.echo("No running companion found.")
        return
    try:
        pid = int(pid_file.read_text(encoding="utf-8").splitlines()[0])
    except (IndexError, ValueError):
        click.echo("Malformed pidfile; cleaning up.")
        pid_file.unlink(missing_ok=True)
        return
    try:
        # On Windows SIGTERM maps to TerminateProcess — still a stop. A dead
        # pid raises OSError variants beyond ProcessLookupError there.
        os.kill(pid, signal.SIGTERM)
        click.echo(f"Sent SIGTERM to {pid}")
    except OSError:
        click.echo("Stale pidfile; cleaning up.")
    pid_file.unlink(missing_ok=True)


@main.command()
@click.option("--test", "test_mode", is_flag=True, help="Report on the test companion, not the real one.")
def status(test_mode):
    """Show companion status."""
    pid_file = TEST_PID_FILE if test_mode else PID_FILE
    default_addr = f"127.0.0.1:{TEST_DEFAULT_PORT if test_mode else DEFAULT_PORT}"
    if not pid_file.exists():
        click.echo("Not running.")
        sys.exit(1)
    lines = pid_file.read_text(encoding="utf-8").splitlines()
    try:
        pid = int(lines[0])
    except (IndexError, ValueError):
        click.echo("Not running (malformed pidfile cleaned up).")
        pid_file.unlink(missing_ok=True)
        sys.exit(1)
    addr = lines[1] if len(lines) > 1 else default_addr
    # Check if the process is actually alive (see _pid_alive — a bare
    # os.kill(pid, 0) here would TERMINATE the server on Windows).
    if not _pid_alive(pid):
        click.echo("Not running (stale pidfile cleaned up).")
        pid_file.unlink(missing_ok=True)
        sys.exit(1)
    # Verify the port actually responds — with a startup grace window. Flask
    # takes a moment to bind after the pidfile is written, and a `status`
    # probe racing that window used to conclude the server was dead and
    # SIGTERM a perfectly healthy process (bit twice in one onboarding run:
    # the server "died ~2s after start" with nothing in its own log). Retry
    # briefly; inside the grace window report "Starting" and never reap.
    host, _, port_str = addr.partition(":")
    try:
        port = int(port_str)
    except ValueError:
        port = None  # malformed address line — unprobeable, fall through to reap
    responded = False
    if port is not None:
        for attempt in range(3):
            try:
                with socket.create_connection((host, port), timeout=2):
                    responded = True
                    break
            except OSError:
                if attempt < 2:
                    time.sleep(1)
    if not responded:
        try:
            pidfile_age = time.time() - pid_file.stat().st_mtime
        except OSError:
            pidfile_age = float("inf")  # stat raced an unlink — out of grace
        # Inside the grace window an unparseable address line gets the same
        # benefit of the doubt as an unresponsive port: the pidfile write
        # isn't atomic, so a torn/partial address just means "mid-startup".
        # Past the window, unparseable falls through to the reap below.
        if pidfile_age < STARTUP_GRACE_SECONDS:
            click.echo(
                f"Starting: pid {pid}, address {addr} "
                "(port not up yet — re-run status in a few seconds)."
            )
            return
        click.echo("Not running (process alive but port not responding; cleaning up).")
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        pid_file.unlink(missing_ok=True)
        sys.exit(1)
    click.echo(f"Running: pid {pid}, address {addr}")


def wait_for_status(vault_path, date_str, target, timeout, poll=1.0, heartbeat=None):
    """Block until the daily note signals ``target``.

    ``heartbeat``, if given, is called once per poll (best-effort; exceptions
    are swallowed). ``wait_done`` passes a function that pings the companion's
    /listener-heartbeat endpoint so a Done/close click can tell a live listener
    is attached — the file poll below stays the source of truth regardless.

    Targets:
      - 'active' / 'closed' — the ``status:`` frontmatter reaches that value
        (morning Lock-in click / a fully closed day).
      - 'close-ready' — the closing banner's "I'm done" button was clicked
        (``close_ready: 1`` frontmatter), OR the day is already closed.
      - 'any' — any status change from the initial value, including the note
        first appearing.

    Returns the matched signal string on success, or None on timeout. Polls
    the FILE, not the server, so it keeps working across companion restarts
    and needs no network.

    **Fires only on a TRANSITION into the target, never a pre-existing
    signal.** A stale ``close_ready: 1`` left by an earlier incomplete close
    used to make this return instantly at arm time (misread as a "clock jump
    fires it early"). The timeout uses the monotonic clock, so a wall-clock
    jump can never trip it early.
    """
    import time as _time
    from companion.parsers import parse_frontmatter

    note = Path(vault_path) / "01-daily" / f"{date_str}.md"

    def signals() -> tuple[str, bool]:
        try:
            fm = parse_frontmatter(note.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError):
            return "", False
        return fm.get("status", ""), fm.get("close_ready") in ("1", "true", "yes")

    def matched(status: str, ready: bool):
        if target == "closed":
            return status if status == "closed" else None
        if target == "active":
            return status if status == "active" else None
        if target == "close-ready":
            if ready:
                return "close-ready"
            if status == "closed":
                return "closed"
            return None
        return None  # 'any' handled separately below

    status0, ready0 = signals()
    # If the target is ALREADY satisfied at arm time, don't fire — wait for
    # the next transition. (A genuinely already-closed day is the one
    # exception for 'closed', where there's nothing further to wait for.)
    baseline = matched(status0, ready0)
    already_closed = target in ("closed", "close-ready") and status0 == "closed"
    deadline = _time.monotonic() + timeout if timeout > 0 else None
    while True:
        if heartbeat is not None:
            try:
                heartbeat()
            except Exception:
                pass  # best-effort: the file transition is the durable signal
        status, ready = signals()
        if target == "any":
            if status != status0:
                return status
        elif already_closed:
            return "closed"
        else:
            hit = matched(status, ready)
            if hit is not None and matched(status0, ready0) is None:
                return hit
        if deadline is not None and _time.monotonic() >= deadline:
            return None
        _time.sleep(poll)


@main.command("wait-done")
@click.option("--date", "date_str", default=None,
              help="Note date YYYY-MM-DD (default: today)")
@click.option("--until", "target",
              type=click.Choice(["active", "closed", "close-ready", "any"]),
              default="close-ready",
              help="Signal to wait for: 'active' = morning Lock-in click, "
                   "'close-ready' = the closing banner's I'm-done click, "
                   "'closed' = day fully closed, 'any' = any status change.")
@click.option("--timeout", default=86400, type=int,
              help="Give up after N seconds (0 = wait forever). Default 24h. "
                   "NOTE: a live listener only lasts as long as the Claude "
                   "session; the durable path is the close_ready flag the "
                   "click persists, which open-day/close-day honor on their "
                   "next run — see the pending-close scan in those skills.")
@click.option("--vault", default=None,
              help="Override vault path (defaults to OBSIDIAN_VAULT_PATH)")
def wait_done(date_str, target, timeout, vault):
    """Block until the builder clicks Done/Lock-in in the browser companion.

    This is the same-machine 'webhook': the click flips the daily note's
    ``status:`` frontmatter, and this command exits the moment that happens.
    Skills run it as a BACKGROUND/Monitor task (never a blocking foreground
    Bash call) so the Claude session auto-resumes on the click instead of
    waiting for the builder to type "done" in chat.

    Prints exactly one line: ``STATUS <status> <date>`` on success (exit 0)
    or ``TIMEOUT <date>`` (exit 1).
    """
    vault = vault or os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        click.echo("Set OBSIDIAN_VAULT_PATH or pass --vault", err=True)
        sys.exit(1)
    if not date_str:
        from datetime import date as _date
        date_str = _date.today().isoformat()

    # While waiting, ping the companion's heartbeat endpoint so a Done/close
    # click can tell this listener is actually attached (the server otherwise
    # can't know — the wait below polls the file, not the server). Best-effort:
    # if the companion isn't running or the pidfile is unreadable we simply
    # don't ping; the file transition is still the durable signal.
    from companion.testmode import is_test_vault
    pid_file = TEST_PID_FILE if is_test_vault(Path(vault)) else PID_FILE
    addr = _read_pidfile_addr(pid_file)
    heartbeat = None
    if addr:
        import urllib.request
        hb_url = f"http://{addr}/listener-heartbeat"

        def heartbeat():
            req = urllib.request.Request(hb_url, data=b"", method="POST")
            urllib.request.urlopen(req, timeout=2).close()

    status = wait_for_status(Path(vault), date_str, target, timeout, heartbeat=heartbeat)
    if status is None:
        click.echo(f"TIMEOUT {date_str}")
        sys.exit(1)
    click.echo(f"STATUS {status} {date_str}")
