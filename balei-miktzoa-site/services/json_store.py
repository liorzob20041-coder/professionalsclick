"""Thread-safe helpers for atomic JSON persistence."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, TypeVar

try:
    import fcntl
except ImportError:  # pragma: no cover - non-posix fallback
    fcntl = None

T = TypeVar("T")

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _get_lock(path: Path) -> threading.Lock:
    with _LOCKS_GUARD:
        key = str(path.resolve())
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _ensure_parent_dir(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


@contextmanager
def atomic_write_json(path: Path, default_factory: Callable[[], T] | None = None):
    """Read-modify-write JSON atomically with in-process + cross-process locks."""

    if default_factory is None:
        default_factory = dict  # type: ignore[assignment]

    path = Path(path)
    _ensure_parent_dir(path)
    sample = default_factory()
    lock = _get_lock(path)
    lock_file = path.with_suffix(path.suffix + ".lock")
    lock_handle = None
    lock.acquire()
    try:
        lock_handle = lock_file.open("a+", encoding="utf-8")
        if fcntl is not None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)

        data: T
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, type(sample)):
                    data = loaded  # type: ignore[assignment]
                else:
                    data = sample
            except (json.JSONDecodeError, OSError):
                data = sample
        else:
            data = sample

        yield data

        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=path.name + ".",
            suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
                json.dump(data, tmp, ensure_ascii=False, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, path)
        finally:
            try:
                if os.path.exists(tmp_name):
                    os.remove(tmp_name)
            except OSError:
                pass
    finally:
        if lock_handle is not None:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()
        lock.release()
