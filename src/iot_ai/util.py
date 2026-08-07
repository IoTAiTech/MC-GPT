# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07

from __future__ import annotations
import hashlib, json, os, tempfile, time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try: path.parent.chmod(0o700)
    except OSError: pass
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def atomic_text(path: Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value); handle.flush(); os.fsync(handle.fileno())
        os.chmod(tmp, mode); os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)



def atomic_bytes(path: Path, value: bytes, mode: int = 0o600) -> None:
    """Atomically replace a binary file and fsync its contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(value); handle.flush(); os.fsync(handle.fileno())
        os.chmod(tmp, mode); os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


@contextmanager
def exclusive_lock(lock_path: Path, *, timeout_seconds: float = 5.0, stale_seconds: float = 120.0):
    """Acquire a small cross-platform lock file with bounded stale recovery.

    The lock protects short local metadata transactions.  It is intentionally
    not a distributed lease and must not be used as one.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > stale_seconds:
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out acquiring lock: {lock_path}")
            time.sleep(0.02)
    try:
        payload = json.dumps({"pid": os.getpid(), "created_at": utc_now()}, sort_keys=True).encode("utf-8")
        os.write(fd, payload); os.fsync(fd)
        yield
    finally:
        if fd is not None:
            os.close(fd)
        lock_path.unlink(missing_ok=True)

def ensure_under(path: Path, root: Path) -> Path:
    resolved, base = path.expanduser().resolve(), root.expanduser().resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"path escapes allowed root: {path}")
    return resolved
