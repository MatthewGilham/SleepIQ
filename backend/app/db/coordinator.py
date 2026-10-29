"""Shared write gate for backups and future importer commits/raw-file changes."""

import msvcrt
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

_threads = RLock()


@contextmanager
def write_guard(data: Path, timeout: float = 5) -> Iterator[None]:
    """Windows process/thread lock; callers must not nest this guard."""
    lock = data / ".write.lock"
    if data.is_symlink() or data.is_junction() or lock.is_symlink() or lock.is_junction():
        raise ValueError("Data coordinator requires regular private paths")
    with _threads, lock.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Data writer is busy") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
