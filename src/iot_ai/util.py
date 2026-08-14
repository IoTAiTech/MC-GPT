# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
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

def resolve_within_allowed_roots(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str, *, must_exist: bool=True) -> Path:
    """Return a path only after realpath + commonpath + prefix confinement."""
    roots = _as_path_list(allowed_roots)
    raw = os.fspath(path)
    if os.name == "nt" and (raw.startswith("\\\\?\\") or raw.startswith("\\\\.\\")):
        raise PathSecurityError("Windows device paths are not allowed")
    expanded = os.path.expanduser(raw)
    absolute = os.path.abspath(expanded)
    parent = os.path.dirname(absolute)
    name = os.path.basename(absolute)
    if name in {"", ".", ".."}:
        raise PathSecurityError(f"path rejects empty or parent name: {path}")
    if not os.path.isdir(parent):
        raise PathSecurityError(f"path parent does not exist: {path}")
    parent_real = os.path.realpath(parent)
    candidate = os.path.join(parent_real, name)
    if os.path.islink(candidate):
        raise PathSecurityError(f"symlink rejected: {path}")
    if os.path.exists(candidate):
        final = _normcase_text(os.path.realpath(candidate))
    else:
        if must_exist:
            raise PathSecurityError(f"path does not exist: {path}")
        final = _normcase_text(candidate)
    allowed = False
    for root in roots:
        try:
            common = os.path.commonpath([root, final])
        except ValueError:
            continue
        if common == root and (final == root or final.startswith(root + os.sep)):
            allowed = True
            break
    if not allowed:
        raise PathSecurityError(f"path escapes allowed_roots: {path}")
    return Path(final)

def _assert_prefix_confined(final: str, roots: Sequence[str]) -> str:
    """Same-function CodeQL guard: realpath result must stay under a root prefix."""
    for root in roots:
        if (final == root or final.startswith(root + os.sep)) and os.path.commonpath([root, final]) == root:
            return final
    raise PathSecurityError("path escapes allowed_roots")

def confined_text_write(path: Path | str, text: str, allowed_roots: Sequence[Path | str] | Path | str, *, encoding: str="utf-8", newline: str|None=None) -> Path:
    resolved = resolve_within_allowed_roots(path, allowed_roots, must_exist=False)
    final = _assert_prefix_confined(os.fspath(resolved), _as_path_list(allowed_roots))
    kwargs: dict[str, Any] = {"encoding": encoding}
    if newline is not None:
        kwargs["newline"] = newline
    with open(final, "w", **kwargs) as handle:
        handle.write(text)
    return Path(final)

def confined_text_read(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str, *, encoding: str="utf-8") -> str:
    resolved = resolve_within_allowed_roots(path, allowed_roots, must_exist=True)
    final = _assert_prefix_confined(os.fspath(resolved), _as_path_list(allowed_roots))
    with open(final, "r", encoding=encoding) as handle:
        return handle.read()

def assert_secure_regular_file(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str, *, max_bytes: int | None=DEFAULT_MAX_HASH_BYTES) -> Path:
    resolved=resolve_within_allowed_roots(path,allowed_roots,must_exist=True)
    try: st=os.lstat(resolved)
    except OSError as exc: raise PathSecurityError(f"cannot stat path: {resolved}") from exc
    if stat.S_ISLNK(st.st_mode): raise PathSecurityError(f"symlink rejected: {resolved}")
    if not stat.S_ISREG(st.st_mode): raise PathSecurityError(f"not a regular file: {resolved}")
    if max_bytes is not None and st.st_size>max_bytes: raise PathSecurityError(f"file exceeds max_bytes ({max_bytes}): {resolved}")
    return resolved

def open_secure(path: Path | str, allowed_roots: Sequence[Path | str] | Path | str, *, max_bytes: int | None=DEFAULT_MAX_HASH_BYTES) -> BinaryIO:
    resolved=assert_secure_regular_file(path,allowed_roots,max_bytes=max_bytes)
    flags=os.O_RDONLY
    if hasattr(os,"O_CLOEXEC"): flags|=os.O_CLOEXEC
    if hasattr(os,"O_NOFOLLOW"): flags|=os.O_NOFOLLOW
    try: fd=os.open(resolved,flags)
    except OSError as exc: raise PathSecurityError(f"secure open failed: {resolved}") from exc
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode): raise PathSecurityError(f"opened handle is not a regular file: {resolved}")
        if max_bytes is not None and st.st_size>max_bytes: raise PathSecurityError(f"file exceeds max_bytes ({max_bytes}): {resolved}")
        return os.fdopen(fd,"rb")
    except Exception:
        try: os.close(fd)
        except OSError: pass
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
