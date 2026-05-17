import time
from pathlib import Path

import pytest

from companion.watcher import VaultWatcher


def test_watcher_emits_on_file_change(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "01-daily").mkdir()

    events: list[str] = []
    watcher = VaultWatcher(str(vault), on_change=lambda relpath: events.append(relpath))
    watcher.start()

    try:
        (vault / "01-daily" / "2026-05-15.md").write_text("# test")
        time.sleep(0.5)
        assert any("01-daily/2026-05-15.md" in e for e in events)
    finally:
        watcher.stop()


def test_watcher_ignores_dotfiles(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    events: list[str] = []
    watcher = VaultWatcher(str(vault), on_change=lambda relpath: events.append(relpath))
    watcher.start()
    try:
        (vault / ".DS_Store").write_text("garbage")
        time.sleep(0.5)
        assert events == []
    finally:
        watcher.stop()
