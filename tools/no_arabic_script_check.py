#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-30
"""Reject Arabic-script characters from public repository paths and text payloads."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable

TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".ini",
    ".cfg", ".sh", ".ps1", ".cmd", ".cff", ".xml", ".csv", ".srt",
    ".html", ".mjs", ".js", ".css", ".svg", ".in",
}
ARCHIVE_SUFFIXES = {".zip", ".whl"}
SKIP_PARTS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", "build", "dist",
}
ARABIC_SCRIPT_RANGES = (
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x0870, 0x089F),
    (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
)


def contains_arabic_script(value: str) -> bool:
    """Return whether text contains a code point from an Arabic-script block."""

    return any(
        lower <= ord(character) <= upper
        for character in value
        for lower, upper in ARABIC_SCRIPT_RANGES
    )


def safe_archive_name(name: str) -> bool:
    pure = PurePosixPath(name)
    return bool(name) and not pure.is_absolute() and ".." not in pure.parts


def iter_text_payloads(root: Path) -> Iterable[tuple[str, str]]:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative_path = path.relative_to(root)
        if any(
            part in SKIP_PARTS or part.endswith(".egg-info")
            for part in relative_path.parts
        ):
            continue
        relative = relative_path.as_posix()
        if contains_arabic_script(relative):
            yield relative, relative
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES or path.name in {"LICENSE", "NOTICE"}:
            try:
                yield relative, path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                yield relative, ""
            continue
        if suffix not in ARCHIVE_SUFFIXES:
            continue
        try:
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    if member.is_dir() or not safe_archive_name(member.filename):
                        continue
                    if contains_arabic_script(member.filename):
                        yield f"{relative}!{member.filename}", member.filename
                    if Path(member.filename).suffix.lower() not in TEXT_SUFFIXES:
                        continue
                    try:
                        text = archive.read(member).decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    yield f"{relative}!{member.filename}", text
        except zipfile.BadZipFile:
            continue


def scan(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for name, text in iter_text_payloads(root):
        if contains_arabic_script(text):
            findings.append({"file": name, "rule": "arabic-script-character"})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    findings = scan(root)
    payload = {
        "schema": "iot-ai.public-language-report.v1",
        "decision": "pass" if not findings else "block",
        "finding_count": len(findings),
        "findings": findings,
    }
    output = json.dumps(payload, indent=2, sort_keys=True)
    if args.json_path:
        Path(args.json_path).write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
