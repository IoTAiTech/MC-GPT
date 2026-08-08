# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
"""Verify a downloaded release artifact and optional checksum sidecar."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath


def safe(name: str) -> bool:
    value = PurePosixPath(name)
    return bool(name) and not value.is_absolute() and ".." not in value.parts and "\\" not in name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact")
    parser.add_argument("--sha256")
    args = parser.parse_args()
    artifact = Path(args.artifact).resolve()
    errors = []
    actual = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.is_file() else None
    if args.sha256 and actual != args.sha256:
        errors.append("sha256-mismatch")
    files = 0
    if artifact.suffix in {".zip", ".whl"}:
        try:
            with zipfile.ZipFile(artifact) as archive:
                names = archive.namelist()
                files = len(names)
                if len(names) != len(set(names)):
                    errors.append("duplicate-member")
                if any(not safe(name) for name in names):
                    errors.append("unsafe-member")
        except zipfile.BadZipFile:
            errors.append("invalid-zip")
    payload = {"decision": "pass" if not errors else "block", "artifact": str(artifact), "sha256": actual, "files": files, "errors": errors}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
