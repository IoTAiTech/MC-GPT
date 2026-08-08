# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Verify project-owned executable sources carry the release license notice."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXTENSIONS = {".py", ".ps1", ".sh"}
SKIP = {".git", ".venv", "venv", "build", "dist", "__pycache__", ".pytest_cache"}
MARKER = "SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    checked = 0
    missing: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        rel = path.relative_to(root)
        if any(part in SKIP or part.endswith(".egg-info") for part in rel.parts):
            continue
        checked += 1
        if MARKER not in path.read_text(encoding="utf-8", errors="replace")[:1000]:
            missing.append(rel.as_posix())
    payload = {"schema": "iot-ai.license-header-report.v1", "decision": "pass" if not missing else "block", "checked": checked, "missing": missing}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
