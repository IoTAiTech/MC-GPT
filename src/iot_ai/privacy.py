# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07

from __future__ import annotations
import re
from dataclasses import dataclass

SECRET_PATTERNS = [
    re.compile(r"(?i)(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-=]{12,}"),
    re.compile(r"(?i)\bauthorization\s*:\s*(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\b(?:cookie|set-cookie)\s*:\s*[^\r\n]+"),
    re.compile(r"(?i)\b(?:oauth|access|refresh)[_-]?token\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\boauth-[A-Za-z0-9._~-]{12,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|xai|AIza)[-_A-Za-z0-9]{16,}\b"),
]
PRIVATE_IP = re.compile(r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b")
UNIX_PATH = re.compile(r"(?<![A-Za-z0-9])/(?:home|root|srv|opt|etc|var|mnt)/[^\s'\"<>]+")
WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\(?:Users|ProgramData|Windows|Program Files)[^\r\n<>]*")
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)

@dataclass(frozen=True)
class PrivacyResult:
    decision: str
    text: str
    findings: tuple[str, ...]


def sanitize(text: str, mode: str = "strict") -> PrivacyResult:
    findings=[]
    for pat in SECRET_PATTERNS:
        if pat.search(text): findings.append("secret")
    if findings:
        return PrivacyResult("block", "", tuple(sorted(set(findings))))
    out=text
    if PRIVATE_IP.search(out): findings.append("private_ip"); out=PRIVATE_IP.sub("[PRIVATE_IP]", out)
    if UNIX_PATH.search(out): findings.append("private_path"); out=UNIX_PATH.sub("[PRIVATE_PATH]", out)
    if WINDOWS_PATH.search(out): findings.append("private_path"); out=WINDOWS_PATH.sub("[PRIVATE_PATH]", out)
    if EMAIL.search(out): findings.append("email"); out=EMAIL.sub("[EMAIL]", out)
    decision = "redact" if findings else "pass"
    if mode == "block-private" and findings: return PrivacyResult("block", "", tuple(sorted(set(findings))))
    return PrivacyResult(decision, out, tuple(sorted(set(findings))))
