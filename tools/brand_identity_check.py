# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
"""Fail closed when superseded legal-brand strings are not classified."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SKIP = {".git", ".venv", "venv", "build", "dist", "__pycache__", ".pytest_cache"}
TEXT_NAMES = {"LICENSE", "NOTICE", "MANIFEST.in", ".gitignore", ".gitattributes"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".ini", ".cfg", ".sh", ".ps1", ".cmd", ".cff", ".xml", ".csv"}
# Split literals prevent the scanner from classifying itself accidentally.
LEGACY = ("AI" + "-IoT.Tech", "AI" + "-IoT-Tech", "ai" + "-iot-tech")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--allowlist", default="LEGACY_IDENTITY_ALLOWLIST.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    allowlist_path = (root / args.allowlist).resolve()
    payload = json.loads(allowlist_path.read_text(encoding="utf-8"))
    allowed = {str(row["path"]): row for row in payload.get("entries", [])}
    occurrences = []
    errors = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP or part.endswith(".egg-info") for part in rel.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = {literal: text.count(literal) for literal in LEGACY if literal in text}
        if not hits:
            continue
        key = rel.as_posix()
        classification = allowed.get(key)
        occurrences.append({"path": key, "hits": hits, "classification": classification})
        if classification is None:
            errors.append({"path": key, "reason": "unclassified-legacy-identity", "hits": hits})
    stale_allowlist = sorted(set(allowed) - {row["path"] for row in occurrences})
    if stale_allowlist:
        errors.extend({"path": value, "reason": "allowlist-entry-has-no-legacy-reference"} for value in stale_allowlist)
    result = {
        "schema": "iot-ai.brand-identity-check.v1",
        "decision": "pass" if not errors else "block",
        "canonical_company": "IoT-AI.Tech",
        "occurrences": occurrences,
        "errors": errors,
        "unclassified_count": len([row for row in errors if row["reason"] == "unclassified-legacy-identity"]),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
