# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
"""Mandatory redaction gate before any non-private report export."""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from .privacy import sanitize

PRIVATE_IP = re.compile(r"\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|\b192\.168\.\d{1,3}\.\d{1,3}\b|\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b")
UNIX_PATH = re.compile(r"/home/[A-Za-z0-9._-]+(?:/[^\s\"']+)?")

def redact_text(text: str) -> dict:
    findings = []
    out = text
    pr = sanitize(out, mode="strict")
    out = pr.text
    findings.extend(list(pr.findings or ()))
    if PRIVATE_IP.search(out):
        findings.append("private_ip"); out = PRIVATE_IP.sub("[PRIVATE_IP]", out)
    if UNIX_PATH.search(out):
        findings.append("private_path"); out = UNIX_PATH.sub("[PRIVATE_PATH]", out)
    return {"text": out, "findings": sorted(set(findings)), "sha256": hashlib.sha256(out.encode()).hexdigest()}

_SECRET_RESIDUAL = re.compile(
    r"(?i)(begin\s+(?:rsa\s+|ec\s+|openssh\s+)?private\s+key|akia[0-9a-z]{16}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-)"
)


def assert_export_safe(path: Path) -> dict:
    """Scan a file; return decision pass/block for non-binary text.

    Blocks when original content still contains secret-like material that must
    never leave a private workspace, even if a redactor attempts to rewrite it.
    """
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"decision": "pass", "kind": "binary", "path": str(path)}
    result = redact_text(text)
    findings = list(result["findings"])
    if _SECRET_RESIDUAL.search(text) or _SECRET_RESIDUAL.search(result["text"]):
        findings.append("secret_residual")
        return {"decision": "block", "findings": sorted(set(findings)), "path": str(path)}
    return {
        "decision": "pass",
        "findings": findings,
        "path": str(path),
        "redacted_sha256": result["sha256"],
    }
