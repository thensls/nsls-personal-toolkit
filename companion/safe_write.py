"""Atomic, exclusively-locked read-modify-write for vault files.

Cross-platform: uses fcntl.flock on Unix/macOS and msvcrt.locking on Windows.
A broken or absent lock lets concurrent writers race (the threaded Flask dev
server runs requests in parallel), and last-write-wins silently drops data —
e.g. ticking two habits quickly would lose one. The lock below serializes them
on every platform.

All reads/writes are UTF-8 with LF newlines so vault notes containing emoji or
accented characters work regardless of the OS locale (Windows defaults to
cp1252, which raises UnicodeDecodeError on such notes).
"""

import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

if sys.platform == "win32":
    import msvcrt

    def _lock(fileobj) -> None:
        """Acquire an exclusive lock on 1 byte of the lock file, retrying until
        it's free. msvcrt.locking(LK_LOCK) blocks ~10s then raises; loop so we
        wait as long as needed instead of failing under contention."""
        fileobj.seek(0)
        while True:
            try:
                msvcrt.locking(fileobj.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:
                time.sleep(0.05)

    def _unlock(fileobj) -> None:
        fileobj.seek(0)
        try:
            msvcrt.locking(fileobj.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _lock(fileobj) -> None:
        fcntl.flock(fileobj.fileno(), fcntl.LOCK_EX)

    def _unlock(fileobj) -> None:
        fcntl.flock(fileobj.fileno(), fcntl.LOCK_UN)


def _atomic_replace(tmp: str, path: Path, retries: int = 10, delay: float = 0.1) -> None:
    """os.replace, retried on PermissionError. On Windows the destination can be
    transiently locked by Obsidian sync, antivirus, or a file indexer; a short
    backoff lets the rename succeed instead of crashing the write."""
    for attempt in range(retries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def safe_modify(path: Path, transform: Callable[[str], str]) -> None:
    """Read path under exclusive lock, transform, write back atomically.

    If path doesn't exist, transform receives "" and the file is created.

    Uses a separate .lock file so the lock survives the atomic rename of
    the data file (os.replace changes the inode, which would release a lock
    held on the data file itself).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lockfile = path.with_suffix(path.suffix + ".lock")
    with open(lockfile, "a+") as lf:
        _lock(lf)
        try:
            # Read current content (may not exist yet). UTF-8 + universal
            # newlines normalizes any CRLF a Windows editor introduced.
            try:
                existing = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                existing = ""
            updated = transform(existing)
            # Atomic write: tempfile in same dir, fsync, rename. newline=""
            # writes the string verbatim (LF), so we never emit CRLF.
            fd, tmp = tempfile.mkstemp(
                prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as tf:
                    tf.write(updated)
                    tf.flush()
                    os.fsync(tf.fileno())
                _atomic_replace(tmp, path)
            except Exception:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
                raise
        finally:
            _unlock(lf)
