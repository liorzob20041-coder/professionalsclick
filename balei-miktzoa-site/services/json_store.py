"""Thread-safe helpers for atomic JSON persistence."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, TypeVar

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
    """Read-modify-write JSON atomically with an in-process lock."""

    if default_factory is None:
        default_factory = dict  # type: ignore[assignment]

    path = Path(path)
    _ensure_parent_dir(path)
    sample = default_factory()
    lock = _get_lock(path)
    lock.acquire()
    try:
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
        lock.release()