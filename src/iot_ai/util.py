# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Shared utilities including fail-closed secure file open/hash helpers.

``sha256_file`` MUST only open paths that resolve inside an explicit
``allowed_roots`` set. Plain ``Path.resolve()`` alone is not sufficient.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import time
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

# Default max size for untrusted evidence/context hashes (64 MiB).
DEFAULT_MAX_HASH_BYTES = 64 * 1024 * 1024


class PathSecurityError(ValueError):
    """Raised when a path fails secure open/hash policy."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _as_path_list(roots: Sequence[Path | str] | Path | str) -> list[Path]:
    if isinstance(roots, (str, Path)):
        items: Sequence[Path | str] = [roots]
    else:
        items = roots
    if not items:
        raise PathSecurityError("allowed_roots must not be empty")
    out: list[Path] = []
    for root in items:
        candidate = Path(root).expanduser()
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise PathSecurityError(f"allowed root does not exist: {candidate}") from exc
        if not resolved.is_dir():
            raise PathSecurityError(f"allowed root is not a directory: {candidate}")
        out.append(_normcase(resolved))
    return out


def _normcase(path: Path) -> Path:
    if os.name == "nt":
        return Path(os.path.normcase(str(path)))
    return path


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _reject_windows_unc_and_drive_escape(path: Path) -> None:
    """Reject UNC / alternate-drive tricks when roots are local paths."""
    text = str(path)
    if os.name == "nt":
        if text.startswith("\\\\") or text.startswith("//"):
            # UNC is only allowed when an allowed root is also UNC (checked later via membership).
            return
        # Reject NT device paths
        if text.startswith("\\\\?\\") or text.startswith("\\\\.\\"):
            raise PathSecurityError("Windows device paths are not allowed")


def resolve_within_allowed_roots(
    path: Path | str,
    allowed_roots: Sequence[Path | str] | Path | str,
    *,
    must_exist: bool = True,
) -> Path:
    """Resolve ``path`` with ``strict=True`` and require membership in ``allowed_roots``.

    Symlinks on the final component are rejected. Intermediate symlink targets
    must still land inside an allowed root after resolution.
    """
    roots = _as_path_list(allowed_roots)
    raw = Path(path).expanduser()
    _reject_windows_unc_and_drive_escape(raw)

    if ".." in raw.parts:
        # Still resolve, but membership check is mandatory; keep explicit rejection for clarity on relative escapes.
        pass

    # Reject final-component symlink before following it.
    try:
        parent = raw.parent if raw.is_absolute() else (Path.cwd() / raw).parent
        parent_resolved = parent.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PathSecurityError(f"path parent does not exist: {raw}") from exc

    final = parent_resolved / raw.name
    if final.is_symlink():
        raise PathSecurityError(f"symlink rejected: {raw}")

    try:
        resolved = final.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise PathSecurityError(f"path does not exist: {raw}") from exc

    # If resolve followed intermediate links, re-check final is not a symlink and is under roots.
    if resolved.is_symlink():
        raise PathSecurityError(f"symlink rejected after resolve: {raw}")

    norm = _normcase(resolved)
    if not any(_is_within(norm, root) for root in roots):
        raise PathSecurityError(f"path escapes allowed_roots: {raw}")

    # Reject UNC unless at least one root is under the same UNC share / path.
    if os.name == "nt":
        text = str(norm)
        if text.startswith("\\\\") or text.startswith("//"):
            if not any(str(root).startswith("\\\\") or str(root).startswith("//") for root in roots):
                raise PathSecurityError("UNC paths require a UNC allowed root")
            if not any(_is_within(norm, root) for root in roots):
                raise PathSecurityError(f"UNC path escapes allowed_roots: {raw}")

    return resolved


def assert_secure_regular_file(
    path: Path | str,
    allowed_roots: Sequence[Path | str] | Path | str,
    *,
    max_bytes: int | None = DEFAULT_MAX_HASH_BYTES,
) -> Path:
    """Return a path that is a regular, non-symlink file under ``allowed_roots``."""
    resolved = resolve_within_allowed_roots(path, allowed_roots, must_exist=True)
    try:
        st = os.lstat(resolved)
    except OSError as exc:
        raise PathSecurityError(f"cannot stat path: {resolved}") from exc
    if stat.S_ISLNK(st.st_mode):
        raise PathSecurityError(f"symlink rejected: {resolved}")
    if not stat.S_ISREG(st.st_mode):
        raise PathSecurityError(f"not a regular file: {resolved}")
    if max_bytes is not None and st.st_size > max_bytes:
        raise PathSecurityError(f"file exceeds max_bytes ({max_bytes}): {resolved}")
    return resolved


def open_secure(
    path: Path | str,
    allowed_roots: Sequence[Path | str] | Path | str,
    *,
    max_bytes: int | None = DEFAULT_MAX_HASH_BYTES,
) -> BinaryIO:
    """Open a file for reading under fail-closed path policy (no symlink follow on final)."""
    resolved = assert_secure_regular_file(path, allowed_roots, max_bytes=max_bytes)
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(resolved, flags)
    except OSError as exc:
        raise PathSecurityError(f"secure open failed: {resolved}") from exc
    # Re-check after open (TOCTOU): fstat must still be a regular file.
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            os.close(fd)
            raise PathSecurityError(f"opened handle is not a regular file: {resolved}")
        if max_bytes is not None and st.st_size > max_bytes:
            os.close(fd)
            raise PathSecurityError(f"file exceeds max_bytes ({max_bytes}): {resolved}")
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    return os.fdopen(fd, "rb")


def sha256_file(
    path: Path | str,
    *,
    allowed_roots: Sequence[Path | str] | Path | str,
    max_bytes: int | None = DEFAULT_MAX_HASH_BYTES,
) -> str:
    """SHA-256 of a file opened only inside ``allowed_roots`` with no-follow protection.

    ``allowed_roots`` is required. Callers that omit it must not use this sink.
    Hash is computed from the opened file descriptor contents.
    """
    handle = open_secure(path, allowed_roots, max_bytes=max_bytes)
    try:
        digest = hashlib.sha256()
        # Bound total bytes even if file grows after open.
        remaining = max_bytes if max_bytes is not None else None
        while True:
            chunk_size = 1024 * 1024
            if remaining is not None:
                if remaining <= 0:
                    break
                chunk_size = min(chunk_size, remaining)
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
        if remaining is not None and handle.read(1):
            raise PathSecurityError(f"file exceeds max_bytes ({max_bytes}): {path}")
        return digest.hexdigest()
    finally:
        handle.close()


def ensure_under(path: Path, root: Path) -> Path:
    """Legacy helper: resolve path and require it to stay under ``root``."""
    return resolve_within_allowed_roots(path, root, must_exist=True)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_text(path: Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_bytes(path: Path, value: bytes, mode: int = 0o600) -> None:
    """Atomically replace a binary file and fsync its contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


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
        os.write(fd, payload)
        os.fsync(fd)
        yield
    finally:
        if fd is not None:
            os.close(fd)
        lock_path.unlink(missing_ok=True)
