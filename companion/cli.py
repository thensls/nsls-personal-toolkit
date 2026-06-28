"""toolkit-companion CLI: serve, stop, status."""

import os
import shutil
import signal
import socket
import sys
import webbrowser
from pathlib import Path

import click


PID_FILE = Path.home() / ".claude" / "local-plugins" / "nsls-personal-toolkit" / ".companion.pid"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _find_free_port(start: int = 7777) -> int:
    for port in range(start, start + 100):
        with socket.socket() as s:
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
@click.option("--port", default=None, type=int, help="Port (default: first free starting at 7777)")
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
    if is_test_vault(vault_path):
        click.echo("  TEST vault — practice data; your real day is untouched.")
    port = port or _find_free_port()
    host = "127.0.0.1"

    from companion.server import create_app
    app = create_app(vault_path=str(vault_path))

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(f"{os.getpid()}\n{host}:{port}\n", encoding="utf-8", newline="")
    PID_FILE.chmod(0o600)

    url = f"http://{host}:{port}"
    click.echo(f"Serving at {url}")
    if not no_open:
        webbrowser.open(url)

    try:
        # threaded=True is required, not optional: the SSE /events endpoint holds
        # a connection open indefinitely, so a single-threaded server would block
        # all other requests behind it. Concurrency is therefore real, which is
        # why every vault write goes through safe_modify's exclusive lock.
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    finally:
        try:
            PID_FILE.unlink()
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
def stop():
    """Stop a running companion server."""
    if not PID_FILE.exists():
        click.echo("No running companion found.")
        return
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").splitlines()[0])
    except (IndexError, ValueError):
        click.echo("Malformed pidfile; cleaning up.")
        PID_FILE.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"Sent SIGTERM to {pid}")
    except ProcessLookupError:
        click.echo("Stale pidfile; cleaning up.")
    PID_FILE.unlink(missing_ok=True)


@main.command()
def status():
    """Show companion status."""
    if not PID_FILE.exists():
        click.echo("Not running.")
        sys.exit(1)
    lines = PID_FILE.read_text(encoding="utf-8").splitlines()
    try:
        pid = int(lines[0])
    except (IndexError, ValueError):
        click.echo("Not running (malformed pidfile cleaned up).")
        PID_FILE.unlink(missing_ok=True)
        sys.exit(1)
    addr = lines[1] if len(lines) > 1 else "127.0.0.1:7777"
    # Check if the process is actually alive
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        click.echo("Not running (stale pidfile cleaned up).")
        PID_FILE.unlink(missing_ok=True)
        sys.exit(1)
    except PermissionError:
        pass  # process exists but owned by another user — treat as alive
    # Verify the port actually responds
    host, _, port_str = addr.partition(":")
    try:
        with socket.create_connection((host, int(port_str)), timeout=2):
            pass
    except (OSError, ValueError):
        click.echo("Not running (process alive but port not responding; cleaning up).")
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        PID_FILE.unlink(missing_ok=True)
        sys.exit(1)
    click.echo(f"Running: pid {pid}, address {addr}")
