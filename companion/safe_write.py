"""Atomic, fcntl-locked read-modify-write for vault files."""

import fcntl
import os
import tempfile
from pathlib import Path
from typing import Callable


def safe_modify(path: Path, transform: Callable[[str], str]) -> None:
    """Read path under exclusive lock, transform, write back atomically.

    If path doesn't exist, transform receives "" and the file is created.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Open or create — exclusive lock held for the whole read-modify-write.
    with open(path, "a+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.seek(0)
        existing = f.read()
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
        # flock released when 'f' closes
