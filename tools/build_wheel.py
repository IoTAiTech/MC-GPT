# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
"""Build the pure-Python Community wheel deterministically without network access."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import re
import runpy
import tomllib
import zipfile
from pathlib import Path

FIXED_TIME = (2026, 8, 8, 0, 0, 0)
DIST_NAME = "iot_ai_coder_suite"

def _version(root: Path) -> str:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){2}(?:(?:a|b|rc)[0-9]+)?", version):
        raise ValueError("unsupported-project-version")
    return version


def _digest(data: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")


def _metadata(root: Path, version: str) -> bytes:
    readme = (root / "README.md").read_text(encoding="utf-8").rstrip() + "\n"
    lines = [
        "Metadata-Version: 2.4",
        "Name: iot-ai-coder-suite",
        f"Version: {version}",
        "Summary: Governed multi-agent coding orchestration for Claude, Codex, Gemini, Grok and Ollama with task validation, meeting reports, deterministic testing and audit.",
        "Author: Dr.-Ing. Babak Sorkhpour",
        "License-Expression: LicenseRef-PolyForm-Noncommercial-1.0.0",
        "Keywords: ai-agents,multi-agent,multi-coder,agentic-coding,claude-code,openai-codex,gemini-cli,grok-cli,ollama,ai-governance,developer-tools,eu-ai-act",
        "Classifier: Development Status :: 3 - Alpha",
        "Classifier: Environment :: Console",
        "Classifier: Intended Audience :: Developers",
        "Classifier: Programming Language :: Python :: 3",
        "Classifier: Programming Language :: Python :: 3.11",
        "Classifier: Programming Language :: Python :: 3.12",
        "Classifier: Programming Language :: Python :: 3.13",
        "Classifier: Topic :: Software Development :: Build Tools",
        "Requires-Python: >=3.11",
        "Description-Content-Type: text/markdown",
        "Requires-Dist: openpyxl<4,>=3.1.5",
        "Provides-Extra: dev",
        'Requires-Dist: pytest<10,>=8; extra == "dev"',
        "Project-URL: Homepage, https://github.com/IoTAiTech/MC-GPT",
        "Project-URL: Documentation, https://github.com/IoTAiTech/MC-GPT#readme",
        "Project-URL: Repository, https://github.com/IoTAiTech/MC-GPT",
        "Project-URL: Issues, https://github.com/IoTAiTech/MC-GPT/issues",
        "Project-URL: Commercial, https://iot-ai.tech",
        "License-File: LICENSE",
        "License-File: LICENSE-COMMERCIAL.md",
        "License-File: LICENSE_POLICY.json",
        "License-File: NOTICE",
        "",
        readme,
    ]
    return "\n".join(lines).encode("utf-8")


def _entry_points() -> bytes:
    return (
        "[console_scripts]\n"
        "iot-ai = iot_ai.entrypoints:suite_main\n"
        "iot-ai-help = iot_ai.entrypoints:help_main\n"
        "iot-ai-settings = iot_ai.entrypoints:settings_main\n"
        "iot-ai-status = iot_ai.entrypoints:status_main\n"
        "iot-ai-update = iot_ai.entrypoints:update_main\n"
        "iot-ai-meeting = iot_ai.entrypoints:meeting_main\n"
        "iot-ai-tasks = iot_ai.entrypoints:tasks_main\n"
        "iot-ai-multi-coder = iot_ai.entrypoints:multicoder_main\n"
    ).encode("utf-8")


def _members(root: Path, dist_info: str, version: str) -> list[tuple[str, bytes, int]]:
    members: list[tuple[str, bytes, int]] = []
    package_root = root / "src" / "iot_ai"
    for path in sorted(package_root.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.suffix in {".pyc", ".pyo"} or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root / "src").as_posix()
        members.append((rel, path.read_bytes(), 0o644))
    members.extend(
        [
            (f"{dist_info}/METADATA", _metadata(root, version), 0o644),
            (
                f"{dist_info}/WHEEL",
                b"Wheel-Version: 1.0\nGenerator: iot-ai deterministic wheel builder 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
                0o644,
            ),
            (f"{dist_info}/entry_points.txt", _entry_points(), 0o644),
            (f"{dist_info}/top_level.txt", b"iot_ai\n", 0o644),
        ]
    )
    for name in ("LICENSE", "LICENSE-COMMERCIAL.md", "LICENSE_POLICY.json", "NOTICE"):
        members.append((f"{dist_info}/licenses/{name}", (root / name).read_bytes(), 0o644))
    collector = runpy.run_path(str(Path(__file__).with_name("package_assets.py")))
    members.extend((name, data, 0o644) for name, data in collector["collect_public_assets"](root))
    names = [name for name, _, _ in members]
    if len(names) != len(set(names)):
        raise ValueError("duplicate-wheel-member")
    return members


def build(root: Path, output_dir: Path) -> dict[str, object]:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    version = _version(root)
    dist_info = f"{DIST_NAME}-{version}.dist-info"
    output = output_dir / f"{DIST_NAME}-{version}-py3-none-any.whl"
    members = _members(root, dist_info, version)
    records: list[list[str]] = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data, mode in sorted(members):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (mode & 0xFFFF) << 16
            archive.writestr(info, data)
            records.append([name, _digest(data), str(len(data))])
        record_name = f"{dist_info}/RECORD"
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        for row in records:
            writer.writerow(row)
        writer.writerow([record_name, "", ""])
        data = stream.getvalue().encode("utf-8")
        info = zipfile.ZipInfo(record_name, FIXED_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (0o644 & 0xFFFF) << 16
        archive.writestr(info, data)
    return {
        "schema": "iot-ai.wheel-build.v1",
        "version": version,
        "decision": "pass",
        "path": str(output),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "members": len(members) + 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("output", nargs="?", default="dist")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.root), Path(args.output)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
