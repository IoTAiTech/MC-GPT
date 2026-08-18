# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-18
"""Pin subprocess executables and strip inherited secret environments."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

_SECRET_NAME = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIAL|AUTHORIZATION|BEARER|FOUNDER)",
    re.I,
)

_KEEP_ENV = (
    "HOME",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "TMPDIR",
    "TEMP",
    "TMP",
    "USER",
    "LOGNAME",
    "USERNAME",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "PYTHONUTF8",
    "PYTHONDONTWRITEBYTECODE",
)


def _existing(paths: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        if resolved.exists():
            found.append(resolved)
    return found


def allowed_executable_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        Path("/usr/bin"),
        Path("/bin"),
        Path("/usr/local/bin"),
        Path("/opt"),
        home / ".local" / "bin",
        Path("/Applications"),
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
        Path(r"C:\Windows\System32"),
        Path(sys.prefix),
        Path(sys.base_prefix),
        Path(sys.exec_prefix),
    ]
    return _existing(candidates)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def pin_executable(name: str, *, allowed_roots: Iterable[Path] | None = None) -> dict[str, str]:
    if not name or not str(name).strip():
        raise RuntimeError("missing-executable")
    raw = Path(str(name).strip())
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        found = shutil.which(str(raw))
        if not found:
            raise RuntimeError(f"unresolved-executable:{raw}")
        resolved = Path(found).resolve()
    if not resolved.is_file():
        raise RuntimeError(f"executable-not-a-file:{resolved}")
    roots = list(allowed_roots) if allowed_roots is not None else allowed_executable_roots()
    if not any(_is_relative_to(resolved, root) for root in roots):
        raise PermissionError(f"executable-not-in-allowlist:{resolved}")
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return {"path": str(resolved), "sha256": digest, "name": resolved.name}


def pin_command(command: list[str], *, allowed_roots: Iterable[Path] | None = None) -> list[str]:
    if not command:
        raise RuntimeError("empty-command")
    pinned = pin_executable(command[0], allowed_roots=allowed_roots)
    return [pinned["path"], *command[1:]]


def restricted_path(extra_dirs: Iterable[Path] | None = None) -> str:
    dirs = [root for root in allowed_executable_roots() if root.is_dir()]
    for item in extra_dirs or []:
        candidate = Path(item)
        if candidate.is_file():
            candidate = candidate.parent
        if candidate.is_dir():
            dirs.append(candidate.resolve())
    unique: list[str] = []
    for directory in dirs:
        text = str(directory)
        if text not in unique:
            unique.append(text)
    return os.pathsep.join(unique) or "/usr/bin"


def minimal_env(
    *,
    extra: Mapping[str, str] | None = None,
    allow_secret_names: Iterable[str] | None = None,
    extra_path_dirs: Iterable[Path] | None = None,
) -> dict[str, str]:
    env: dict[str, str] = {}
    for key in _KEEP_ENV:
        value = os.environ.get(key)
        if value:
            env[key] = value
    allowed_secrets = {str(name) for name in (allow_secret_names or []) if name}
    for name in allowed_secrets:
        value = os.environ.get(name)
        if value:
            env[name] = value
    env["PATH"] = restricted_path(extra_path_dirs)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["TERM"] = "dumb"
    if extra:
        for key, value in extra.items():
            if _SECRET_NAME.search(str(key)) and key not in allowed_secrets:
                continue
            env[str(key)] = str(value)
    return env


def test_env(*, extra_path_dirs: Iterable[Path] | None = None) -> dict[str, str]:
    """Untrusted tests inherit no provider or founder secrets."""
    return minimal_env(extra_path_dirs=extra_path_dirs)


def provider_env(secret_env: str | None = None, *, executable: str | None = None) -> dict[str, str]:
    extra_dirs = [Path(executable).resolve().parent] if executable else None
    allow = [secret_env] if secret_env else []
    return minimal_env(allow_secret_names=allow, extra_path_dirs=extra_dirs)


def looks_like_secret_name(name: str) -> bool:
    return bool(_SECRET_NAME.search(name))
