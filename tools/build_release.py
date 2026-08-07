# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Build a reproducible source archive of the public repository."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path

EXCLUDED = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist"}
FIXED_TIME = (2026, 8, 4, 0, 0, 0)


def members(root: Path):
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in EXCLUDED or part.endswith(".egg-info") for part in rel.parts):
            continue
        if path.is_file() and not path.is_symlink() and path.suffix not in {".pyc", ".pyo"} and rel.as_posix() != "SOURCE_MANIFEST.json":
            yield path, rel.as_posix()


def build(root: Path, output_dir: Path) -> dict:
    from iot_ai.suite_version import SUITE_VERSION
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"IOT-AI-Coder-Suite-v{SUITE_VERSION}-SOURCE.zip"
    manifest = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, rel in members(root):
            data = path.read_bytes()
            info = zipfile.ZipInfo(f"iot-ai-coder-suite-{SUITE_VERSION}/{rel}", FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o755 if os.access(path, os.X_OK) else 0o644) & 0xFFFF) << 16
            archive.writestr(info, data)
            manifest.append({"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
        info = zipfile.ZipInfo(f"iot-ai-coder-suite-{SUITE_VERSION}/SOURCE_MANIFEST.json", FIXED_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, json.dumps({"schema": "iot-ai.source-manifest.v1", "files": manifest}, indent=2, sort_keys=True) + "\n")
    return {"path": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "files": len(manifest)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("output", nargs="?", default="dist")
    args = parser.parse_args()
    result = build(Path(args.root).resolve(), Path(args.output).resolve())
    print(json.dumps({"decision": "pass", **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
