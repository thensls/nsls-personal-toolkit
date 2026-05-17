"""Watchdog-based vault observer.

Calls on_change(relative_path) whenever any markdown file in the vault
changes. Ignores dotfiles and non-markdown files.
"""

from pathlib import Path
from typing import Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class _Handler(FileSystemEventHandler):
    def __init__(self, vault: Path, on_change: Callable[[str], None]):
        self.vault = vault
        self.on_change = on_change

    def _maybe_emit(self, path: str) -> None:
        try:
            rel = Path(path).resolve().relative_to(self.vault.resolve())
        except ValueError:
            return
        name = rel.name
        if name.startswith("."):
            return
        if not name.endswith(".md"):
            return
        self.on_change(str(rel))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._maybe_emit(event.src_path)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._maybe_emit(event.src_path)


class VaultWatcher:
    def __init__(self, vault_path: str, on_change: Callable[[str], None]):
        self.vault = Path(vault_path)
        self._observer = Observer()
        self._handler = _Handler(self.vault, on_change)

    def start(self) -> None:
        self._observer.schedule(self._handler, str(self.vault), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=2)
