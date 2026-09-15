"""tenx.locking - cross-process safety for the shared `.tenx` harness.

A fleet of agents may run tenx concurrently against the same project. Without
coordination, two processes doing read-modify-write on the same markdown
artifact, or appending to the same `activity.jsonl`, can lose or corrupt
writes. This module provides two stdlib-only primitives:

  * `harness_lock(root)` - an exclusive advisory lock (`.tenx/.lock`) held for
    the whole of a mutating command, so read-modify-write cycles are atomic.
    It uses `fcntl.flock`, which the OS releases automatically when the process
    exits or the fd closes, so a crashed tenx never leaves a stale lock.

  * `atomic_write_text(path, text)` - write to a same-directory temp file then
    `os.replace`, so readers never observe a partially written file.

Platforms without `fcntl` (e.g. Windows) degrade to a documented no-op lock;
atomic replacement still applies everywhere.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import fcntl
    _HAVE_FCNTL = True
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None  # type: ignore[assignment]
    _HAVE_FCNTL = False

LOCK_NAME = ".lock"
DEFAULT_TIMEOUT = 60.0  # seconds to wait for the lock before giving up
_POLL = 0.05


def _default_timeout() -> float:
    """Env-overridable default (TENX_LOCK_TIMEOUT); used by tests/CI."""
    try:
        return float(os.environ.get("TENX_LOCK_TIMEOUT", DEFAULT_TIMEOUT))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT


class LockTimeout(RuntimeError):
    """Raised when the harness lock cannot be acquired within the timeout."""


def lock_path(project_root: Path) -> Path:
    return Path(project_root) / ".tenx" / LOCK_NAME


@contextmanager
def harness_lock(project_root: Path,
                 timeout: float | None = None) -> Iterator[None]:
    """Hold the per-project exclusive lock for the duration of a mutation.

    No-op when `fcntl` is unavailable or `.tenx` does not exist yet (e.g. the
    very first `tenx init`). Raises `LockTimeout` if another tenx process holds
    the lock past `timeout`.
    """
    if timeout is None:
        timeout = _default_timeout()
    tenx_dir = Path(project_root) / ".tenx"
    if not _HAVE_FCNTL or not tenx_dir.is_dir():
        yield
        return
    lp = lock_path(project_root)
    fd = os.open(str(lp), os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, PermissionError, OSError):
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire the tenx lock at {lp} within "
                        f"{timeout:.0f}s; another tenx process may be "
                        f"writing this project - retry shortly")
                time.sleep(_POLL)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write `text` to `path` atomically (temp file + os.replace).

    Guarantees a reader never sees a partially written file and a crash mid-write
    leaves the previous content intact. The temp file is created in the same
    directory so the replace is an atomic rename on the same filesystem.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise
