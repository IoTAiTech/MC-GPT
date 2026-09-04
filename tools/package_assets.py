# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-04
"""Build-time public data collector shared by setuptools and offline wheels.

No downloads, scripts, model calls, user roots or Enterprise data are included.
The repository remains the sole source of skill files and the reviewed lock.
"""
from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 128_000
MAX_TOTAL_BYTES = 2_000_000
LOCK = "governance/garden-skills.lock.json"
NOTICE = "THIRD_PARTY_NOTICES.md"


def _read(root: Path, relative: str) -> bytes:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts or "\\" in relative:
        raise ValueError("invalid-package-data-path")
    path = root
    for part in rel.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("symlink-package-data")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
        raise ValueError("invalid-package-data-file")
    with path.open("rb") as stream:
        content = stream.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("oversized-package-data")
    content.decode("utf-8")
    return content


def collect_public_assets(root: Path) -> list[tuple[str, bytes]]:
    """Return deterministic installation paths and bytes after lock validation."""
    root = root.resolve()
    skills = root / "skills"
    if skills.is_symlink() or not skills.is_dir():
        raise ValueError("packaged-skills-root-invalid")
    selected: dict[str, bytes] = {}
    for path in sorted(skills.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlink-package-data")
        if path.is_dir():
            continue
        # Explicit data-only contract; unexpected assets require separate review.
        if path.name not in {"SKILL.md", "manifest.json"}:
            raise ValueError("unapproved-skill-package-member")
        relative = path.relative_to(root).as_posix()
        selected[relative] = _read(root, relative)
    if not any(name.endswith("/SKILL.md") for name in selected):
        raise ValueError("packaged-skills-empty")
    lock_bytes = _read(root, LOCK)
    lock = json.loads(lock_bytes)
    if (lock.get("schema") != "iot-ai.garden-skills.lock.v1"
            or lock.get("upstream_license") != "MIT"
            or lock.get("script_execution_policy") != "never"):
        raise ValueError("garden-package-policy-invalid")
    rows = lock.get("files")
    if not isinstance(rows, list):
        raise ValueError("garden-package-files-invalid")
    locked: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError("garden-package-row-invalid")
        name = row["path"]
        if name in locked or not name.startswith("skills/third-party/"):
            raise ValueError("garden-package-path-invalid")
        locked.add(name)
        if name not in selected or hashlib.sha256(selected[name]).hexdigest() != row.get("sha256"):
            raise ValueError("garden-package-digest-mismatch")
    third_party = {name for name in selected if name.startswith("skills/third-party/")}
    if third_party != locked or set(lock.get("included_skill_paths", [])) != locked:
        raise ValueError("garden-package-inventory-mismatch")
    selected[LOCK] = lock_bytes
    selected["governance/THIRD_PARTY_NOTICES.md"] = _read(root, NOTICE)
    if sum(len(data) for data in selected.values()) > MAX_TOTAL_BYTES:
        raise ValueError("package-data-budget-exceeded")
    return [("iot_ai/data/" + name, selected[name]) for name in sorted(selected)]
