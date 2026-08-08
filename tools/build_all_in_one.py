# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Build the deterministic Community ALL-IN-ONE installer package."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

FIXED_TIME = (2026, 8, 8, 0, 0, 0)
SUITE_VERSION = "6.7.0-beta.5"
MC_GPT_VERSION = "0.8.0-alpha.5"
ROOT_FILES = {
    "AGENTS.md", "CHANGELOG.md", "CITATION.cff", "CODE_OF_CONDUCT.md", "COMMERCIAL.md", "CONTACT.md", "CONTRIBUTING.md", "GOVERNANCE.md", "COMPONENT_REGISTRY.json", "EDITION_BOUNDARY.json",
    "FINAL_TEST_SUMMARY.json", "LEGACY_IDENTITY_ALLOWLIST.json", "LICENSE", "LICENSE-COMMERCIAL.md", "LICENSE_POLICY.json", "MODEL_POLICY.json",
    "NOTICE", "PACKAGE_LINEAGE.json", "PACKAGE_METADATA.json", "PUBLIC_REPOSITORY_NOTICE.md", "README.md",
    "RELEASE_NOTES.md", "RELEASE_STATUS.json", "REVIEW_SCOPE.md", "ROADMAP.md", "SBOM.cdx.json", "SECURITY.md",
    "SUPPORT.md", "THIRD_PARTY_NOTICES.md", "TRADEMARKS.md",
}
DIRECTORIES = ("docs", "skills", "installers", "examples", "schemas", "assets", "npm")


def _copy_tree(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        rel = path.relative_to(source)
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _zip(root: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(rel, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o755 if os.access(path, os.X_OK) else 0o644) & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())


def build(root: Path, wheel: Path, openpyxl: Path, et_xmlfile: Path, component: Path, output_dir: Path) -> dict[str, object]:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"IoT-AI-Tech-iot-ai-Coder-Suite-v{SUITE_VERSION}-ALL-IN-ONE.zip"
    with tempfile.TemporaryDirectory(prefix="iot-ai-all-in-one-") as temporary:
        stage = Path(temporary) / "stage"
        stage.mkdir()
        for name in sorted(ROOT_FILES):
            shutil.copy2(root / name, stage / name)
        for directory in DIRECTORIES:
            _copy_tree(root / directory, stage / directory)
        for wheel_dir in (stage / "wheels", stage / "installers" / "wheels"):
            wheel_dir.mkdir(parents=True, exist_ok=True)
            for source in (wheel, openpyxl, et_xmlfile):
                shutil.copy2(source, wheel_dir / source.name)
        component_dir = stage / "components" / "iot-ai-mc-gpt"
        component_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(component, component_dir / component.name)

        files = []
        sums = []
        for path in sorted(stage.rglob("*")):
            if not path.is_file() or path.name in {"MANIFEST.json", "SHA256SUMS.txt"}:
                continue
            rel = path.relative_to(stage).as_posix()
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            files.append({"path": rel, "sha256": digest, "size": len(data)})
            sums.append(f"{digest}  {rel}\n")
        registry_digest = hashlib.sha256((stage / "COMPONENT_REGISTRY.json").read_bytes()).hexdigest()
        manifest = {
            "schema": "iot-ai.suite-package-manifest.v2",
            "suite_version": SUITE_VERSION,
            "mc_gpt_version": MC_GPT_VERSION,
            "component_registry_sha256": registry_digest,
            "files": files,
        }
        (stage / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (stage / "SHA256SUMS.txt").write_text("".join(sums), encoding="utf-8")
        _zip(stage, output)
    return {
        "schema": "iot-ai.all-in-one-build.v2",
        "decision": "pass",
        "path": str(output),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "files": len(files) + 2,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--openpyxl", required=True)
    parser.add_argument("--et-xmlfile", required=True)
    parser.add_argument("--component", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build(Path(args.root), Path(args.wheel), Path(args.openpyxl), Path(args.et_xmlfile), Path(args.component), Path(args.output))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
