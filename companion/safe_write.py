"""Atomic, fcntl-locked read-modify-write for vault files."""

import fcntl
import os
import tempfile
from pathlib import Path
from typing import Callable


def safe_modify(path: Path, transform: Callable[[str], str]) -> None:
    """Read path under exclusive lock, transform, write back atomically.

    If path doesn't exist, transform receives "" and the file is created.

    Uses a separate .lock file so the lock survives the atomic rename of
    the data file (os.replace changes the inode, which would release an
    flock held on the data file itself).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lockfile = path.with_suffix(path.suffix + ".lock")
    with open(lockfile, "a+") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        # Read current content (may not exist yet).
        try:
            existing = path.read_text()
        except FileNotFoundError:
            existing = ""
        updated = transform(existing)
        # Atomic write: tempfile in same dir, fsync, rename.
        fd, tmp = tempfile.mkstemp(
            prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w") as tf:
                tf.write(updated)
                tf.flush()
                os.fsync(tf.fileno())
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise
        # flock released when 'lf' closes
