"""Cross-platform safe_modify guarantees.

The concurrency test is the regression for the "checking one checkbox unchecks
another" bug: the threaded Flask dev server runs tick requests in parallel, and
without a working file lock the read-modify-write races and silently drops
updates. This must hold on both fcntl (Unix) and msvcrt (Windows) backends.
"""

import json
import sys
import threading

from companion import safe_write
from companion.safe_write import safe_modify


def test_lock_backend_present_for_platform():
    # Both backends expose the same _lock/_unlock interface.
    assert callable(safe_write._lock)
    assert callable(safe_write._unlock)


def test_concurrent_writers_lose_no_updates(tmp_path):
    """40 threads each add a distinct key via read-modify-write. With a correct
    exclusive lock all 40 survive; a broken/absent lock drops some."""
    f = tmp_path / "counts.json"
    f.write_text("{}", encoding="utf-8")
    n = 40

    def worker(i):
        def transform(existing):
            data = json.loads(existing or "{}")
            data[str(i)] = i
            return json.dumps(data)
        safe_modify(f, transform)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    data = json.loads(f.read_text(encoding="utf-8"))
    assert len(data) == n, f"lost updates: only {len(data)}/{n} survived"


def test_utf8_roundtrip(tmp_path):
    f = tmp_path / "note.md"
    payload = "emoji 🔥 café — résumé · 你好"
    safe_modify(f, lambda _: payload)
    assert f.read_text(encoding="utf-8") == payload


def test_crlf_normalized_to_lf(tmp_path):
    """A note created by a Windows editor (CRLF) is read with universal newlines
    and written back as LF, so we never accumulate CRLF in the vault."""
    f = tmp_path / "n.md"
    f.write_bytes(b"line1\r\nline2\r\n")
    seen = {}

    def transform(existing):
        seen["text"] = existing
        return existing + "line3\n"

    safe_modify(f, transform)
    assert "\r" not in seen["text"]          # transform sees normalized LF
    assert b"\r" not in f.read_bytes()       # file written as LF


def test_creates_missing_file(tmp_path):
    f = tmp_path / "new.md"
    safe_modify(f, lambda existing: existing + "created")
    assert f.read_text(encoding="utf-8") == "created"
