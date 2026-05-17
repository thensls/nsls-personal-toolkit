"""toolkit-companion CLI: serve, stop, status."""

import os
import signal
import socket
import sys
import webbrowser
from pathlib import Path

import click


PID_FILE = Path.home() / ".claude" / "local-plugins" / "nsls-personal-toolkit" / ".companion.pid"


def _find_free_port(start: int = 7777) -> int:
    for port in range(start, start + 100):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")


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
    port = port or _find_free_port()
    host = "127.0.0.1"

    from companion.server import create_app
    app = create_app(vault_path=vault)

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(f"{os.getpid()}\n{host}:{port}\n")
    PID_FILE.chmod(0o600)

    url = f"http://{host}:{port}"
    click.echo(f"Serving at {url}")
    if not no_open:
        webbrowser.open(url)

    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    finally:
        try:
            PID_FILE.unlink()
        except FileNotFoundError:
            pass


@main.command()
def stop():
    """Stop a running companion server."""
    if not PID_FILE.exists():
        click.echo("No running companion found.")
        return
    pid = int(PID_FILE.read_text().splitlines()[0])
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
        return
    lines = PID_FILE.read_text().splitlines()
    click.echo(f"Running: pid {lines[0]}, address {lines[1]}")
