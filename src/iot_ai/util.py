# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.6 | Date: 2026-08-18
"""Shared utilities including fail-closed secure file open/hash helpers."""
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

DEFAULT_MAX_HASH_BYTES = 64 * 1024 * 1024

class PathSecurityError(ValueError):
    """Raised when a path fails secure open/hash policy."""

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def _normcase_text(path: str) -> str:
    return os.path.normcase(path) if os.name == "nt" else path

def _trusted_directory(root: Path | str) -> str:
    """Normalize an allow-list directory. The operator supplies the trust root."""
    text = os.path.expanduser(os.fspath(root))
    if os.name == "nt" and (text.startswith("\\\\?\\") or text.startswith("\\\\.\\")):
        raise PathSecurityError("Windows device paths are not allowed")
    if not os.path.isdir(text):
        raise PathSecurityError(f"allowed root does not exist: {root}")
    real = os.path.realpath(text)
    if not os.path.isdir(real):
        raise PathSecurityError(f"allowed root is not a directory: {root}")
    if os.path.dirname(real) == real:
        raise PathSecurityError("filesystem root is not an allowed trust boundary")
    return _normcase_text(real)

def _as_path_list(roots: Sequence[Path | str] | Path | str) -> list[str]:
    items = [roots] if isinstance(roots, (str, Path)) else roots
    if not items:
        raise PathSecurityError("allowed_roots must not be empty")
    result: list[str] = []
    for root in items:
        normalized = _trusted_directory(root)
        if normalized not in result:
            result.append(normalized)
    return result

def _confined_to_root(candidate: str, root: str) -> bool:
    try:
        if os.path.commonpath([root, candidate]) != root:
            return False
    except ValueError:
        return False
    return candidate == root or candidate.startswith(root + os.sep)

def _physical_join_preserving_final(path: str) -> str:
    """Resolve existing ancestor directories without following the final name.

    This maps OS prefix aliases (/var -> /private/var, Windows 8.3 names)
    while leaving a final symlink visible for later rejection.
    """
    norm = os.path.normpath(os.path.expanduser(path))
    if not os.path.isabs(norm):
        return norm
    parent, base = os.path.split(norm)
    suffix = [base] if base else []
    ancestor = parent
    while ancestor and not os.path.isdir(ancestor):
        ancestor, name = os.path.split(ancestor)
        if not name:
            break
        suffix.insert(0, name)
    if ancestor and os.path.isdir(ancestor):
        ancestor = os.path.realpath(ancestor)
    return os.path.join(ancestor, *suffix) if suffix else ancestor

def _reject_device_or_empty(path: Path | str) -> str:
    filename = os.fspath(path)
    if os.name == "nt" and (filename.startswith("\\\\?\\") or filename.startswith("\\\\.\\")):
        raise PathSecurityError("Windows device paths are not allowed")
    if os.path.basename(os.path.normpath(filename)) in {"", ".", ".."}:
        raise PathSecurityError(f"path rejects empty or parent name: {path}")
    return filename

def _is_reparse(st: os.stat_result) -> bool:
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT

def _relative_parts(path: Path | str, root: str) -> list[str]:
    filename = _reject_device_or_empty(path)
    if os.path.isabs(filename):
        norm = os.path.normpath(os.path.expanduser(filename))
        # Prefer the lexical path so in-root directory symlinks stay
        # visible to O_NOFOLLOW. Remap only OS aliases such as macOS
        # /var -> /private/var or Windows 8.3 short names.
        if _confined_to_root(_normcase_text(norm), root):
            rel = os.path.relpath(norm, root)
        else:
            remapped = _physical_join_preserving_final(filename)
            if not _confined_to_root(_normcase_text(remapped), root):
                raise PathSecurityError(f"path escapes allowed_roots: {path}")
            rel = os.path.relpath(remapped, root)
    else:
        rel = os.path.normpath(filename)
    if rel in {"", "."}:
        raise PathSecurityError(f"path rejects empty or parent name: {path}")
    if rel.startswith("..") or os.path.isabs(rel):
        raise PathSecurityError(f"path escapes allowed_roots: {path}")
    parts = [part for part in Path(rel).parts if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise PathSecurityError(f"path escapes allowed_roots: {path}")
    return parts

def _open_root_dir(root: str) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return os.open(root, flags)

def _component_dir_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags

def _walk_parent_fd(root: str, parts: list[str]) -> int:
    """Open every intermediate component with O_NOFOLLOW / reparse rejection."""
    intermediates = parts[:-1]
    parent_fd = _open_root_dir(root)
    try:
        for part in intermediates:
            nxt = os.open(part, _component_dir_flags(), dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = nxt
        return parent_fd
    except OSError:
        os.close(parent_fd)
        raise

def _windows_confined_fd(root: str, parts: list[str], *, write: bool) -> tuple[int, Path]:
    """Windows cannot os.open() directories; lstat every component, then open the file."""
    current = root
    for index, part in enumerate(parts):
        current = os.path.join(current, part)
        last = index == len(parts) - 1
        if last and write and not os.path.lexists(current):
            fd = os.open(current, _write_flags(), 0o600)
            return fd, Path(current)
        st = os.lstat(current)
        if _is_reparse(st):
            raise PathSecurityError(f"symlink rejected: {current}")
        if last:
            if not stat.S_ISREG(st.st_mode):
                raise PathSecurityError(f"not a regular file: {current}")
            flags = _write_flags() if write else _read_flags()
            return os.open(current, flags, 0o600), Path(current)
        if not stat.S_ISDIR(st.st_mode):
            raise PathSecurityError(f"not a directory: {current}")
    raise PathSecurityError(f"path rejects empty or parent name: {current}")

def resolve_within_allowed_roots(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str, *, must_exist: bool=True) -> Path:
    """Resolve a user path under a trusted root with component-level symlink rejection."""
    roots = _as_path_list(allowed_roots)
    last_error = "path escapes allowed_roots"
    for root in roots:
        try:
            parts = _relative_parts(path, root)
        except PathSecurityError as exc:
            last_error = str(exc)
            continue
        current = root
        try:
            for index, part in enumerate(parts):
                current = os.path.join(current, part)
                last = index == len(parts) - 1
                if last and not must_exist and not os.path.lexists(current):
                    return Path(current)
                st = os.lstat(current)
                if _is_reparse(st):
                    raise PathSecurityError(f"symlink rejected: {current}")
                if last:
                    if must_exist and not stat.S_ISREG(st.st_mode) and not stat.S_ISDIR(st.st_mode):
                        raise PathSecurityError(f"not a regular file: {current}")
                elif not stat.S_ISDIR(st.st_mode):
                    raise PathSecurityError(f"not a directory: {current}")
            return Path(current)
        except FileNotFoundError:
            last_error = "path does not exist"
            continue
        except PathSecurityError as exc:
            last_error = str(exc)
            continue
    raise PathSecurityError(f"{last_error}: {path}")

def _write_flags() -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags

def _read_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags

def _open_last_component(parent_fd: int, name: str, *, write: bool) -> int:
    flags = _write_flags() if write else _read_flags()
    if os.name != "nt":
        return os.open(name, flags, 0o600, dir_fd=parent_fd)
    raise PathSecurityError("secure component open requires POSIX dir_fd")

def _confined_fd(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str, *, write: bool) -> tuple[int, Path]:
    last_error = "path escapes allowed_roots"
    for root in _as_path_list(allowed_roots):
        try:
            parts = _relative_parts(path, root)
            if os.name == "nt":
                fd, resolved = _windows_confined_fd(root, parts, write=write)
            else:
                parent_fd = _walk_parent_fd(root, parts)
                try:
                    fd = _open_last_component(parent_fd, parts[-1], write=write)
                except OSError as exc:
                    os.close(parent_fd)
                    raise PathSecurityError(f"secure {'write' if write else 'read'} failed: {path}") from exc
                os.close(parent_fd)
                resolved = Path(root, *parts)
        except (OSError, PathSecurityError) as exc:
            last_error = str(exc)
            continue
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            os.close(fd)
            raise PathSecurityError(f"not a regular file: {path}")
        return fd, resolved
    raise PathSecurityError(f"{last_error}: {path}")

def confined_text_write(path: Path | str, text: str, allowed_roots: Sequence[Path | str] | Path | str, *, encoding: str="utf-8", newline: str|None=None) -> Path:
    fd, resolved = _confined_fd(path, allowed_roots, write=True)
    kwargs: dict[str, Any] = {"encoding": encoding}
    if newline is not None:
        kwargs["newline"] = newline
    with os.fdopen(fd, "w", **kwargs) as handle:
        handle.write(text)
    return resolved

def confined_text_read(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str, *, encoding: str="utf-8") -> str:
    fd, _resolved = _confined_fd(path, allowed_roots, write=False)
    with os.fdopen(fd, "r", encoding=encoding) as handle:
        return handle.read()

def confined_bytes_write(path: Path | str, data: bytes, allowed_roots: Sequence[Path | str] | Path | str) -> Path:
    fd, resolved = _confined_fd(path, allowed_roots, write=True)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    return resolved

def confined_makedirs(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str) -> Path:
    last_error = "path escapes allowed_roots"
    for root in _as_path_list(allowed_roots):
        try:
            parts = _relative_parts(path, root)
        except PathSecurityError as exc:
            last_error = str(exc)
            continue
        current = root
        for part in parts:
            current = os.path.join(current, part)
            if os.path.lexists(current):
                st = os.lstat(current)
                if _is_reparse(st):
                    raise PathSecurityError(f"symlink rejected: {path}")
                if not stat.S_ISDIR(st.st_mode):
                    raise PathSecurityError(f"not a directory: {path}")
                continue
            os.mkdir(current, 0o700)
        return Path(current)
    raise PathSecurityError(f"{last_error}: {path}")

def confined_unlink(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str) -> None:
    fd, resolved = _confined_fd(path, allowed_roots, write=False)
    os.close(fd)
    os.unlink(resolved)

def assert_secure_regular_file(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str, *, max_bytes: int | None=DEFAULT_MAX_HASH_BYTES) -> Path:
    resolved = resolve_within_allowed_roots(path, allowed_roots, must_exist=True)
    st = os.lstat(resolved)
    if _is_reparse(st):
        raise PathSecurityError(f"symlink rejected: {resolved}")
    if not stat.S_ISREG(st.st_mode):
        raise PathSecurityError(f"not a regular file: {resolved}")
    if max_bytes is not None and st.st_size > max_bytes:
        raise PathSecurityError(f"file exceeds max_bytes ({max_bytes}): {resolved}")
    return resolved

def open_secure(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str, *, max_bytes: int | None=DEFAULT_MAX_HASH_BYTES) -> BinaryIO:
    fd, resolved = _confined_fd(path, allowed_roots, write=False)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise PathSecurityError(f"opened handle is not a regular file: {resolved}")
        if max_bytes is not None and opened.st_size > max_bytes:
            raise PathSecurityError(f"file exceeds max_bytes ({max_bytes}): {resolved}")
        return os.fdopen(fd, "rb")
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise

def sha256_file(path: Path | str, *, allowed_roots: Sequence[Path | str] | Path | str, max_bytes: int | None=DEFAULT_MAX_HASH_BYTES) -> str:
    handle=open_secure(path,allowed_roots,max_bytes=max_bytes)
    try:
        digest=hashlib.sha256(); remaining=max_bytes
        while True:
            size=1024*1024 if remaining is None else min(1024*1024,max(0,remaining))
            if size==0: break
            chunk=handle.read(size)
            if not chunk: break
            digest.update(chunk)
            if remaining is not None: remaining-=len(chunk)
        if remaining is not None and handle.read(1): raise PathSecurityError(f"file exceeds max_bytes ({max_bytes}): {path}")
        return digest.hexdigest()
    finally: handle.close()

def trusted_operator_roots(user_home: Path | None=None) -> tuple[Path,...]:
    candidates=[Path.cwd(),Path.home()]
    if user_home is not None: candidates.append(Path(user_home))
    for value in (os.environ.get("IOT_AI_ALLOWED_READ_ROOTS") or "").split(os.pathsep):
        if value.strip(): candidates.append(Path(value).expanduser())
    roots=[]
    for candidate in candidates:
        try: resolved=candidate.resolve(strict=True)
        except (OSError,RuntimeError): continue
        if not resolved.is_dir() or resolved==Path(resolved.anchor): continue
        if resolved not in roots: roots.append(resolved)
    if not roots: raise PathSecurityError("no trusted operator file root is configured")
    return tuple(roots)

def ensure_under(path: Path, root: Path) -> Path:
    return resolve_within_allowed_roots(path,root,must_exist=True)

def load_json(path: Path, default: Any=None) -> Any:
    if not path.exists(): return default
    return json.loads(path.read_text(encoding="utf-8"))

def atomic_json(path: Path,value: Any,mode: int=0o600)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    try: path.parent.chmod(0o700)
    except OSError: pass
    fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            json.dump(value,handle,ensure_ascii=False,indent=2,sort_keys=True);handle.write("\n");handle.flush();os.fsync(handle.fileno())
        os.chmod(tmp,mode);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def atomic_text(path: Path,value: str,mode: int=0o600)->None:
    path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle: handle.write(value);handle.flush();os.fsync(handle.fileno())
        os.chmod(tmp,mode);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def atomic_bytes(path: Path,value: bytes,mode: int=0o600)->None:
    path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as handle: handle.write(value);handle.flush();os.fsync(handle.fileno())
        os.chmod(tmp,mode);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

@contextmanager
def exclusive_lock(lock_path: Path,*,timeout_seconds: float=5.0,stale_seconds: float=120.0):
    lock_path.parent.mkdir(parents=True,exist_ok=True);deadline=time.monotonic()+timeout_seconds;fd=None
    while fd is None:
        try: fd=os.open(lock_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError:
            try:
                if time.time()-lock_path.stat().st_mtime>stale_seconds: lock_path.unlink(missing_ok=True);continue
            except FileNotFoundError: continue
            if time.monotonic()>=deadline: raise TimeoutError(f"timed out acquiring lock: {lock_path}")
            time.sleep(0.02)
    try:
        os.write(fd,json.dumps({"pid":os.getpid(),"created_at":utc_now()},sort_keys=True).encode());os.fsync(fd);yield
    finally:
        if fd is not None: os.close(fd)
        lock_path.unlink(missing_ok=True)
