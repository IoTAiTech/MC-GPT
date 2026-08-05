# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-06
"""Legal brand identity constants and residual AI-IoT classification."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CANONICAL_LEGAL_NAME = "IoT-AI.Tech"
WRONG_LEGAL_NAME = "AI-IoT.Tech"  # classified legacy constant only
CANONICAL_PACKAGE_PREFIX = "IoT-AI-Tech"
LEGACY_PACKAGE_PREFIX = "AI-IoT-Tech"

TECHNICAL_KEEP = (
    "iot-ai",
    "iot_ai",
    "IOT-AI Coder Suite",
    "IOT-AI Suite",
    "MC-GPT",
)

EXCEPTION_LEGACY_PACKAGE = "approved-legacy-package-identifier"
EXCEPTION_EXTERNAL_HISTORICAL_URL = "external-historical-url"
EXCEPTION_MIGRATION_FIXTURE = "migration-fixture"
EXCEPTION_TECHNICAL_PRODUCT_ID = "technical-product-id"
EXCEPTION_LEGACY_NAMESPACE = "approved-legacy-filesystem-namespace"
EXCEPTION_LEGACY_LICENSE_REF = "approved-legacy-license-identifier"

_LEGACY_PACKAGE_RE = re.compile(
    r"AI-IoT-Tech-iot-ai-Coder-Suite-v(?P<version>[0-9A-Za-z.+-]+)-ALL-IN-ONE\.zip"
)
_TECHNICAL_PRODUCT_ID_RE = re.compile(r"\bai-iot-tech\.iot-ai[-\w.]*")
_LEGACY_MARKER_RE = re.compile(
    r"WINDOWS_VENDOR_LEGACY|WRONG_LEGAL_NAME|LEGACY_PACKAGE|LEGACY_SUITE_NAMESPACE|"
    r"LEGACY_STATE_NAMESPACE|legacy_windows_vendor|legacy_linux_state|approved-legacy|"
    r"LEGACY_PACKAGE_FILENAME_PREFIX|_LEGACY_PACKAGE",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s\"')]+", re.IGNORECASE)


def classify_ai_iot_occurrence(text: str, *, path: str = "") -> list[dict[str, Any]]:
    """Classify every AI-IoT occurrence in *text*; unclassified items are blockers."""
    findings: list[dict[str, Any]] = []
    path_l = path.replace("\\", "/").lower()
    identity_module = (
        path_l.endswith("brand_identity.py")
        or path_l.endswith("paths.py")
        or path_l.endswith("brand_exceptions.json")
        or "brand_exceptions" in path_l
    )
    for match in re.finditer(r"AI-IoT", text):
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 100)
        window = text[start:end]
        line_no = text.count("\n", 0, match.start()) + 1
        classification: str | None = None
        if identity_module:
            classification = EXCEPTION_LEGACY_NAMESPACE
        elif "LicenseRef-AI-IoT-Tech" in window:
            classification = EXCEPTION_LEGACY_LICENSE_REF
        elif _LEGACY_PACKAGE_RE.search(window):
            classification = EXCEPTION_LEGACY_PACKAGE
        elif _TECHNICAL_PRODUCT_ID_RE.search(window):
            classification = EXCEPTION_TECHNICAL_PRODUCT_ID
        elif _LEGACY_MARKER_RE.search(window):
            classification = EXCEPTION_LEGACY_NAMESPACE
        elif "github.com/AI-IoT-Tech" in window or any(u for u in _URL_RE.findall(window) if "AI-IoT" in u or "ai-iot" in u.lower()):
            classification = EXCEPTION_EXTERNAL_HISTORICAL_URL
        elif (
            "fixture" in path_l
            or path_l.startswith("tests/")
            or "/tests/" in path_l
            or path_l.startswith("test_")
            or "/test_" in path_l
        ):
            classification = EXCEPTION_MIGRATION_FIXTURE
        elif "migration" in path_l:
            classification = EXCEPTION_MIGRATION_FIXTURE
        elif 'assertNotIn("AI-IoT.Tech"' in window or "assertNotIn('AI-IoT.Tech'" in window:
            classification = EXCEPTION_MIGRATION_FIXTURE
        elif "must only appear" in window or "wrong legal brand" in window.lower():
            classification = EXCEPTION_MIGRATION_FIXTURE
        findings.append(
            {
                "path": path,
                "line": line_no,
                "snippet": window.replace("\n", " ")[:160],
                "classification": classification,
                "decision": "pass" if classification else "block",
            }
        )
    return findings


def scan_tree(root: Path) -> dict[str, Any]:
    """Scan a source tree for residual AI-IoT strings and classify them."""
    text_suffixes = {
        ".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".cff",
        ".html", ".in", ".cfg", ".ini", ".sh",
    }
    all_findings: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        if any(part in {"__pycache__", ".git", ".venv"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "AI-IoT" not in text:
            continue
        rel = str(path.relative_to(root))
        all_findings.extend(classify_ai_iot_occurrence(text, path=rel))
    blockers = [f for f in all_findings if f["decision"] == "block"]
    return {
        "schema": "iot-ai.brand-identity-scan.v1",
        "canonical_legal_name": CANONICAL_LEGAL_NAME,
        "findings": all_findings,
        "blocker_count": len(blockers),
        "decision": "pass" if not blockers else "block",
        "blockers": blockers,
    }
