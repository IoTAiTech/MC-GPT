# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-01
"""Fail-closed public-release scanner for source trees and Git history."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

FORBIDDEN_ROOTS = {"enterprise", "private", "customer", "evidence-private", "secrets", "release-private"}
SKIP_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", "build", "dist", "*.egg-info"}
SKIP_FILE_NAMES = {"pytest-output.txt", "junit-release.xml"}
SKIP_FILE_PREFIXES = ("junit-",)
SKIP_FILE_SUFFIXES = (".coverage",)
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".ini", ".cfg", ".sh", ".ps1", ".cmd", ".cff", ".xml", ".csv", ".srt", ".html", ".mjs", ".js", ".css", ".svg", ".in"}
ARCHIVE_SUFFIXES = {".zip", ".whl"}
CLASSIFIED_BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".xlsx"}
KNOWN_EMPTY_SUFFIX_NAMES = {
    "LICENSE", "NOTICE", "MANIFEST.in", ".gitignore", ".gitattributes",
    ".editorconfig", ".nojekyll", "CODEOWNERS",
    "Dockerfile", ".dockerignore",
}
FORBIDDEN_BASENAMES = {".env", ".netrc", "id_rsa", "id_ed25519", "credentials"}
FORBIDDEN_SUFFIXES = {".env", ".pem", ".key"}

# Keep patterns assembled from Names so AST bytes-fold does not self-trigger.
PRIVATE_IP = re.compile(rb"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b")
PERSONAL_PATH = re.compile(rb"(?:/(?:home|root)/[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\[^\\\r\n]+)")
_PEM_BEGIN = b"-----BEGIN "
_PEM_PRIV = b"PRIVATE"
_PEM_KEY = b" KEY-----"
_PEM_OPENSSH = b"-----BEGIN OPENSSH "
PRIVATE_KEY = re.compile(_PEM_BEGIN + _PEM_PRIV + _PEM_KEY + b"|" + _PEM_OPENSSH + _PEM_PRIV + _PEM_KEY)
TOKEN = re.compile(rb"(?:\bsk-[A-Za-z0-9_-]{12,}\b|\bxai-[A-Za-z0-9_-]{12,}\b|\bghp_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b|\bAKIA[0-9A-Z]{16}\b|\bAIza[0-9A-Za-z_-]{20,}\b)")
AUTH = re.compile(rb"(?i)authorization\s*:\s*(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
ASSIGNMENT = re.compile(rb"(?i)(?:password|secret|private_key|access_token|refresh_token|api_key)\s*[:=]\s*['\"][^'\"]{8,}['\"]")
GENERIC_INTERNAL = re.compile(rb"(?i)\bfritz\.box\b")
_HOST_TOKEN = re.compile(rb"[A-Za-z0-9][A-Za-z0-9._-]{2,64}")
# Unique fleet hostnames are digest-bound. Mapping stays in private evidence.
FORBIDDEN_NAME_DIGESTS = frozenset(
    {
        "d03c663474f34a0f8d78e8306855d96d3a445b450e8b51e29dd3ee857b90397e",
        "4f2547c9b9690cc6a4a409c8129b467415cb7fd60df21682399206f05c7bfcc5",
        "53237a0c8c9dc2ef16203d165c6ec3fcfc09177491521ce859e317a11857e097",
        "4bd9bc54910bac918cf6281ae4afdc7de9d4bcc094422c537dac6c9ad0fba764",
    }
)
RULES = {
    "private-ip": PRIVATE_IP,
    "personal-path": PERSONAL_PATH,
    "private-key": PRIVATE_KEY,
    "token-literal": TOKEN,
    "authorization-header": AUTH,
    "secret-assignment": ASSIGNMENT,
}

# Digest-bound synthetic fixtures only. Empty by default: current-tree tests must
# not store reconstructable private literals. Historical RFC1918/path matches are
# inventoried, not allowlisted.
SYNTHETIC_FIXTURE_ALLOWLIST: dict[tuple[str, str], str] = {}
HISTORY_SEVERE_RULES = frozenset(
    {"private-key", "token-literal", "authorization-header", "secret-assignment"}
)
HISTORY_INVENTORY_ONLY_RULES = frozenset({"private-ip", "personal-path", "internal-hostname"})


def _static_int(node: ast.AST) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    return None


def _static_payload(node: ast.AST) -> str | bytes | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
                continue
            if isinstance(value, ast.FormattedValue):
                inner_node = value.value
                if (
                    isinstance(inner_node, ast.Constant)
                    and isinstance(inner_node.value, (str, int, float))
                    and not isinstance(inner_node.value, bool)
                ):
                    parts.append(str(inner_node.value))
                    continue
                inner = _static_payload(inner_node)
                if not isinstance(inner, str):
                    return None
                parts.append(inner)
                continue
            return None
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_payload(node.left)
        right = _static_payload(node.right)
        if left is None or right is None or type(left) is not type(right):
            return None
        return left + right
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        seq = _static_payload(node.left)
        count = _static_int(node.right)
        if seq is None or count is None:
            seq = _static_payload(node.right)
            count = _static_int(node.left)
        if seq is None or count is None or count < 0 or count > 4096:
            return None
        return seq * count
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "join":
        sep = _static_payload(node.func.value)
        if sep is None or len(node.args) != 1:
            return None
        seq = node.args[0]
        if not isinstance(seq, (ast.List, ast.Tuple)):
            return None
        parts = [_static_payload(item) for item in seq.elts]
        if any(item is None or type(item) is not type(sep) for item in parts):
            return None
        return sep.join(parts)  # type: ignore[arg-type]
    return None


def reconstructed_python_payloads(data: bytes) -> list[bytes]:
    try:
        tree = ast.parse(data.decode("utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    found: list[bytes] = []
    for node in ast.walk(tree):
        value = _static_payload(node)
        if isinstance(value, str) and value:
            found.append(value.encode("utf-8", errors="replace"))
        elif isinstance(value, bytes) and value:
            found.append(value)
    return found


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
    in_head = path in head_paths
    if not in_head and rule not in HISTORY_SEVERE_RULES and rule not in HISTORY_INVENTORY_ONLY_RULES:
        return False
    return True


def _file_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _allowlisted(rel: str, data: bytes) -> bool:
    digest = SYNTHETIC_FIXTURE_ALLOWLIST.get((rel, _file_digest(data)))
    return digest is not None


def internal_hostname_hit(data: bytes) -> bool:
    if GENERIC_INTERNAL.search(data):
        return True
    for token in _HOST_TOKEN.findall(data):
        if hashlib.sha256(token.lower()).hexdigest() in FORBIDDEN_NAME_DIGESTS:
            return True
    return False


def rule_hit(rule: str, data: bytes) -> bool:
    if rule == "internal-hostname":
        return internal_hostname_hit(data)
    pattern = RULES.get(rule)
    return bool(pattern is not None and pattern.search(data))


SCAN_RULES = tuple(list(RULES) + ["internal-hostname"])


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
        name = path.name
        if name in FORBIDDEN_BASENAMES or name.startswith(".env.") or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            yield rel, b"FORBIDDEN_ENV_OR_KEY"
            continue
        classified = (
            path.suffix.lower() in TEXT_SUFFIXES
            or path.suffix.lower() in ARCHIVE_SUFFIXES
            or path.suffix.lower() in CLASSIFIED_BINARY_SUFFIXES
            or name in KNOWN_EMPTY_SUFFIX_NAMES
        )
        if not classified:
            yield rel, b"UNCLASSIFIED_FILE"
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
        if path.suffix.lower() in CLASSIFIED_BINARY_SUFFIXES:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in KNOWN_EMPTY_SUFFIX_NAMES:
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
        if data == b"FORBIDDEN_ENV_OR_KEY":
            findings.append({"file": name, "rule": "forbidden-env-or-key"})
            continue
        if data == b"UNCLASSIFIED_FILE":
            findings.append({"file": name, "rule": "unclassified-file"})
            continue
        if _allowlisted(name, data):
            continue
        for rule in SCAN_RULES:
            if rule_hit(rule, data):
                findings.append({"file": name, "rule": rule})
        if name.endswith(".py"):
            for payload in reconstructed_python_payloads(data):
                for rule in SCAN_RULES:
                    if rule_hit(rule, payload) and not rule_hit(rule, data):
                        findings.append({"file": name, "rule": f"reconstructed:{rule}"})
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
        if blob.returncode:
            key = (path, "history:blob-unreadable")
            if key not in seen:
                seen.add(key)
                findings.append({"file": path, "rule": "history:blob-unreadable"})
            continue
        if len(blob.stdout) > 2_000_000:
            key = (path, "history:blob-too-large")
            if key not in seen:
                seen.add(key)
                findings.append({"file": path, "rule": "history:blob-too-large"})
            continue
        matched_rules: set[str] = set()
        for rule in SCAN_RULES:
            if not rule_hit(rule, blob.stdout):
                continue
            if not _history_rule_applies(path, rule, head_paths):
                continue
            matched_rules.add(rule)
            key = (path, f"history:{rule}")
            if key in seen:
                continue
            seen.add(key)
            findings.append({"file": path, "rule": f"history:{rule}"})
        if path.endswith(".py"):
            for payload in reconstructed_python_payloads(blob.stdout):
                for rule in SCAN_RULES:
                    if rule in matched_rules:
                        continue
                    if not rule_hit(rule, payload):
                        continue
                    if not _history_rule_applies(path, rule, head_paths):
                        continue
                    key = (path, f"history:reconstructed:{rule}")
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append({"file": path, "rule": f"history:reconstructed:{rule}"})
    return findings


def _history_inner_rule(rule: str) -> str:
    inner = rule[len("history:"):] if rule.startswith("history:") else rule
    if inner.startswith("reconstructed:"):
        return inner.split(":", 1)[1]
    return inner


def _is_blocking(finding: dict[str, str]) -> bool:
    rule = finding.get("rule") or ""
    path = finding.get("file") or ""
    if not rule.startswith("history:"):
        return True
    inner = _history_inner_rule(rule)
    if inner in HISTORY_INVENTORY_ONLY_RULES:
        return False
    if inner in HISTORY_SEVERE_RULES:
        # Reconstructed historical markers are inventoried. Rewriting git
        # history is forbidden; current-tree reconstructed matches still block.
        if ":reconstructed:" in f":{rule}:":
            return False
        return True
    return inner in {"blob-too-large", "blob-unreadable", "git-history-unreadable"}


def list_tags(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(root), "tag", "--list"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--git-history", action="store_true")
    parser.add_argument("--inventory", dest="inventory_path")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    tree_findings = scan_tree(root)
    history_findings = scan_git_history(root) if args.git_history else []
    findings = [*tree_findings, *history_findings]
    blocking = [item for item in findings if _is_blocking(item)]
    inventory_only = [item for item in findings if not _is_blocking(item)]
    payload = {
        "schema": "iot-ai.public-boundary-report.v2",
        "decision": "pass" if not blocking else "block",
        "root": str(root),
        "findings": blocking,
        "finding_count": len(blocking),
        "historical_inventory": inventory_only,
        "historical_inventory_count": len(inventory_only),
        "history_rewrite_performed": False,
        "tags": list_tags(root) if args.git_history or args.inventory_path else [],
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.json_path:
        Path(args.json_path).write_text(text + "\n", encoding="utf-8")
    if args.inventory_path:
        Path(args.inventory_path).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not blocking else 1


if __name__ == "__main__":
    raise SystemExit(main())
