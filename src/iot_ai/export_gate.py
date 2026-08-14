# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Fail-closed redaction and classification gate for exported text artifacts."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from .privacy import sanitize
from .util import confined_text_read, confined_text_write, resolve_within_allowed_roots, trusted_operator_roots

PRIVATE_IP = re.compile(r"\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|\b192\.168\.\d{1,3}\.\d{1,3}\b|\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b")
PRIVATE_PATH = re.compile(r"(?:/(?:home|root)/[A-Za-z0-9._-]+(?:/[^\s\"']+)?|[A-Za-z]:\\Users\\[^\r\n\"']+)")
SECRET_RESIDUAL = re.compile(r"(?i)(begin\s+(?:rsa\s+|ec\s+|openssh\s+)?private\s+key|akia[0-9a-z]{16}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-)")

def redact_text(text: str) -> dict:
    findings: list[str] = []
    privacy = sanitize(text, mode="strict")
    out = privacy.text
    findings.extend(list(privacy.findings or ()))
    if PRIVATE_IP.search(out):
        findings.append("private_ip")
        out = PRIVATE_IP.sub("[PRIVATE_IP]", out)
    if PRIVATE_PATH.search(out):
        findings.append("private_path")
        out = PRIVATE_PATH.sub("[PRIVATE_PATH]", out)
    return {
        "text": out,
        "findings": sorted(set(findings)),
        "sha256": hashlib.sha256(out.encode("utf-8")).hexdigest(),
    }

def inspect_export_file(path: Path, *, allowed_roots: list[Path] | None = None) -> dict:
    roots = allowed_roots or list(trusted_operator_roots())
    safe = resolve_within_allowed_roots(path, roots, must_exist=True)
    try:
        text = confined_text_read(safe, roots)
    except UnicodeDecodeError:
        return {"decision": "pass", "kind": "binary", "path": str(safe), "findings": []}
    result = redact_text(text)
    findings = list(result["findings"])
    if SECRET_RESIDUAL.search(text) or SECRET_RESIDUAL.search(result["text"]):
        findings.append("secret_residual")
    return {
        "decision": "pass" if not findings else "redact-required",
        "path": str(safe),
        "findings": sorted(set(findings)),
        "redacted_sha256": result["sha256"],
        "redacted_text": result["text"],
    }

def assert_export_safe(path: Path, *, public: bool = True, allowed_roots: list[Path] | None = None) -> dict:
    result = inspect_export_file(path, allowed_roots=allowed_roots)
    if public and result["decision"] != "pass":
        return {**result, "decision": "block"}
    return result

def rewrite_public_export(path: Path, *, allowed_roots: list[Path] | None = None) -> dict:
    roots = allowed_roots or list(trusted_operator_roots())
    safe = resolve_within_allowed_roots(path, roots, must_exist=True)
    result = inspect_export_file(safe, allowed_roots=roots)
    if "secret_residual" in result.get("findings", []):
        return {**result, "decision": "block"}
    if result.get("kind") != "binary" and result.get("decision") == "redact-required":
        confined_text_write(safe, str(result["redacted_text"]), roots)
    return {k: v for k, v in {**result, "decision": "pass"}.items() if k != "redacted_text"}
