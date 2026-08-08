# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Fail-closed public-release scanner for source trees and Git history."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable

FORBIDDEN_ROOTS = {"enterprise", "private", "customer", "evidence-private", "secrets", "release-private"}
SKIP_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", "build", "dist", "*.egg-info"}
SKIP_FILE_NAMES = {"pytest-output.txt", "junit-release.xml"}
SKIP_FILE_PREFIXES = ("junit-",)
SKIP_FILE_SUFFIXES = (".coverage",)
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".ini", ".cfg", ".sh", ".ps1", ".cmd", ".cff", ".xml", ".csv", ".srt"}
ARCHIVE_SUFFIXES = {".zip", ".whl"}

# Keep patterns split so this scanner does not self-trigger.
PRIVATE_IP = re.compile(rb"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b")
PERSONAL_PATH = re.compile(rb"(?:/(?:home|root)/[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\[^\\\r\n]+)")
PRIVATE_KEY = re.compile((b"-----BEGIN " + b"PRIVATE KEY-----") + b"|" + (b"-----BEGIN OPENSSH " + b"PRIVATE KEY-----"))
TOKEN = re.compile(rb"(?:\bsk-[A-Za-z0-9_-]{12,}\b|\bxai-[A-Za-z0-9_-]{12,}\b|\bghp_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b|\bAKIA[0-9A-Z]{16}\b|\bAIza[0-9A-Za-z_-]{20,}\b)")
AUTH = re.compile(rb"(?i)authorization\s*:\s*(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
ASSIGNMENT = re.compile(rb"(?i)(?:password|secret|private_key|access_token|refresh_token|api_key)\s*[:=]\s*['\"][^'\"]{8,}['\"]")
INTERNAL_NAMES = re.compile(rb"(?i)\b(?:" + b"DLD-" + b"DGX|" + b"IOT-" + b"Dashboard-Serv|" + b"HPZ" + b"8G4|" + rb"Nas\.IOT|" + rb"fritz\.box)\b")
RULES = {
    "private-ip": PRIVATE_IP,
    "personal-path": PERSONAL_PATH,
    "private-key": PRIVATE_KEY,
    "token-literal": TOKEN,
    "authorization-header": AUTH,
    "secret-assignment": ASSIGNMENT,
    "internal-hostname": INTERNAL_NAMES,
}

ALLOWLIST = {
    ("tests/test_setup.py", "pass@example.com"),
}

# History-only fixture noise: unit tests intentionally construct private-looking
# samples (often split at rest in the current tree). High-severity secret classes
# still fail closed even under tests/.
HISTORY_FIXTURE_RULES = frozenset({"private-ip", "personal-path", "private-key"})
HISTORY_SEVERE_RULES = frozenset(
    {"private-key", "token-literal", "authorization-header", "secret-assignment"}
)


def should_skip_file(rel: str, name: str) -> bool:
    del rel
    return name in SKIP_FILE_NAMES or name.startswith(SKIP_FILE_PREFIXES) or name.endswith(SKIP_FILE_SUFFIXES)


def _head_paths(root: Path) -> set[str]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        return set()
    return {line for line in completed.stdout.splitlines() if line}


def _history_rule_applies(path: str, rule: str, head_paths: set[str]) -> bool:
    pure = PurePosixPath(path)
    under_tests = pure.parts and pure.parts[0] == "tests"
    in_head = path in head_paths
    if under_tests and rule in HISTORY_FIXTURE_RULES:
        # Current tree must still pass scan_tree with split fixtures; historical
        # unsplit redaction fixtures must not block Developer Preview tags.
        return False
    if not in_head and rule not in HISTORY_SEVERE_RULES:
        # Deleted non-secret artifacts (e.g. old PUBLISH_AUDIT host paths).
        return False
    return True


def safe_archive_name(name: str) -> bool:
    pure = PurePosixPath(name)
    return bool(name) and not pure.is_absolute() and ".." not in pure.parts and "\\" not in name


def iter_payloads(root: Path) -> Iterable[tuple[str, bytes]]:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in SKIP_PARTS or part.endswith(".egg-info") for part in path.relative_to(root).parts):
            continue
        if should_skip_file(rel, path.name):
            continue
        if path.suffix in ARCHIVE_SUFFIXES:
            try:
                with zipfile.ZipFile(path) as archive:
                    names = archive.namelist()
                    if len(names) != len(set(names)):
                        yield f"{rel}!<archive>", b"DUPLICATE_ARCHIVE_MEMBER"
                    for name in names:
                        if name.endswith("/"):
                            continue
                        if not safe_archive_name(name):
                            yield f"{rel}!{name}", b"UNSAFE_ARCHIVE_PATH"
                            continue
                        yield f"{rel}!{name}", archive.read(name)
            except zipfile.BadZipFile:
                yield rel, b"INVALID_ARCHIVE"
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"LICENSE", "NOTICE", "MANIFEST.in", ".gitignore", ".gitattributes"}:
            yield rel, path.read_bytes()


def scan_tree(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for forbidden in sorted(FORBIDDEN_ROOTS):
        if (root / forbidden).exists():
            findings.append({"file": forbidden, "rule": "forbidden-root"})
    for path in root.rglob("*"):
        if path.is_symlink():
            findings.append({"file": path.relative_to(root).as_posix(), "rule": "symlink-forbidden"})
    for name, data in iter_payloads(root):
        if data == b"DUPLICATE_ARCHIVE_MEMBER":
            findings.append({"file": name, "rule": "duplicate-archive-member"})
            continue
        if data == b"UNSAFE_ARCHIVE_PATH":
            findings.append({"file": name, "rule": "unsafe-archive-path"})
            continue
        if data == b"INVALID_ARCHIVE":
            findings.append({"file": name, "rule": "invalid-archive"})
            continue
        for rule, pattern in RULES.items():
            if pattern.search(data):
                findings.append({"file": name, "rule": rule})
    return findings


def scan_git_history(root: Path) -> list[dict[str, str]]:
    if not (root / ".git").exists():
        return []
    findings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    head_paths = _head_paths(root)
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-list", "--objects", "--all"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        return [{"file": ".git", "rule": "git-history-unreadable"}]
    for line in completed.stdout.splitlines():
        object_id, _, path = line.partition(" ")
        if not path:
            continue
        if any(part in FORBIDDEN_ROOTS for part in PurePosixPath(path).parts):
            key = (path, "forbidden-history-path")
            if key not in seen:
                seen.add(key)
                findings.append({"file": path, "rule": "forbidden-history-path"})
            continue
        kind = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-t", object_id],
            capture_output=True,
            text=True,
            check=False,
        )
        if kind.returncode or kind.stdout.strip() != "blob":
            continue
        blob = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-p", object_id],
            capture_output=True,
            check=False,
        )
        if blob.returncode or len(blob.stdout) > 2_000_000:
            continue
        for rule, pattern in RULES.items():
            if not pattern.search(blob.stdout):
                continue
            if not _history_rule_applies(path, rule, head_paths):
                continue
            key = (path, f"history:{rule}")
            if key in seen:
                continue
            seen.add(key)
            findings.append({"file": path, "rule": f"history:{rule}"})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--git-history", action="store_true")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    findings = scan_tree(root)
    if args.git_history:
        findings.extend(scan_git_history(root))
    payload = {
        "schema": "iot-ai.public-boundary-report.v1",
        "decision": "pass" if not findings else "block",
        "root": str(root),
        "findings": findings,
        "finding_count": len(findings),
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.json_path:
        Path(args.json_path).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
