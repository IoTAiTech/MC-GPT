# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Explicit public export and privacy scanning."""
from __future__ import annotations
import hashlib
import re
import shutil
import zipfile
from pathlib import Path
from .util import sha256_file

PUBLIC_ROOT_FILES = {
    ".gitignore", "README.md", "CHANGELOG.md", "CITATION.cff", "CODE_OF_CONDUCT.md",
    "AGENTS.md", "COMMERCIAL.md", "CONTRIBUTING.md", "GOVERNANCE.md", "LICENSE", "LICENSE-COMMERCIAL.md", "NOTICE",
    "PUBLIC_REPOSITORY_NOTICE.md", "REVIEW_SCOPE.md", "SECURITY.md", "SUPPORT.md",
    "THIRD_PARTY_NOTICES.md", "TRADEMARKS.md", "MANIFEST.in", ".gitattributes", "pyproject.toml", "LICENSE_POLICY.json",
    "PACKAGE_LINEAGE.json", "PACKAGE_METADATA.json", "COMPONENT_REGISTRY.json", "MODEL_POLICY.json",
    "EDITION_BOUNDARY.json", "SBOM.cdx.json", "RELEASE_STATUS.json", "FINAL_TEST_SUMMARY.json",
    "RELEASE_NOTES.md", "ROADMAP.md",
}
PUBLIC_TOP_LEVEL_DIRS = {".github", "src", "skills", "installers", "tests", "tools", "docs", "examples", "schemas", "assets"}
_PRIVATE_MARKERS = [
    rb"(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})",
    rb"/(?:home|root)/[A-Za-z0-9._-]+/",
    rb"[A-Za-z]:\\Users\\[^\\\r\n]+",
    rb"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----",
    rb"\b(?:sk|xai)[-_][A-Za-z0-9_-]{16,}\b",
    rb"\bAIza[A-Za-z0-9_-]{20,}\b",
    rb"(?i)Authorization:\s*Bearer\s+[A-Za-z0-9._~+/=-]{16,}",
    rb"(?i)(?:password|secret)\s*[:=]\s*['\"][^'\"]{12,}['\"]",
]
PRIVATE_PATTERNS = [re.compile(value) for value in _PRIVATE_MARKERS]


def scan(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "build", "dist"} for part in path.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        rel = path.relative_to(root).as_posix()
        payloads: list[tuple[str, bytes]] = []
        if path.suffix == ".whl":
            try:
                with zipfile.ZipFile(path) as archive:
                    payloads.extend((f"{rel}!{name}", archive.read(name)) for name in sorted(archive.namelist()) if not name.endswith("/"))
            except zipfile.BadZipFile:
                findings.append({"file": rel, "rule": "invalid-wheel-archive"})
                continue
        else:
            payloads.append((rel, path.read_bytes()))
        for payload_name, data in payloads:
            for pattern in PRIVATE_PATTERNS:
                if pattern.search(data):
                    findings.append({"file": payload_name, "rule": pattern.pattern.decode("latin1")[:100]})
    return findings


def root_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256_file(path, allowed_roots=[root], max_bytes=None).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def export_public(source: Path, destination: Path) -> dict:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    copied: list[str] = []
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if not rel.parts:
            continue
        allowed = rel.parts[0] in PUBLIC_TOP_LEVEL_DIRS or (len(rel.parts) == 1 and rel.name in PUBLIC_ROOT_FILES)
        if not allowed:
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "build", "dist"} for part in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"symlink forbidden in public export: {rel}")
        target = destination / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied.append(rel.as_posix())
    findings = scan(destination)
    if findings:
        raise ValueError(f"public export privacy scan failed: {findings[:3]}")
    return {"decision": "pass", "files": len(copied), "root_digest": root_digest(destination)}
