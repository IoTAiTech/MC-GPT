# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-30
from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_checker():
    path = ROOT / "tools" / "no_arabic_script_check.py"
    spec = importlib.util.spec_from_file_location("no_arabic_script_check", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load language checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicLanguageCheckTests(unittest.TestCase):
    def test_plain_english_and_german_text_passes(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text(
                "English documentation. Deutsche Dokumentation.", encoding="utf-8"
            )
            self.assertEqual(checker.scan(root), [])

    def test_arabic_script_character_blocks_without_literal_in_source(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "blocked.md").write_text("blocked-" + chr(0x0641), encoding="utf-8")
            findings = checker.scan(root)
            self.assertEqual(findings[0]["rule"], "arabic-script-character")

    def test_archive_member_is_scanned(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "artifact.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("docs/report.md", "blocked-" + chr(0x06CC))
            findings = checker.scan(root)
            self.assertEqual(len(findings), 1)
            self.assertIn("artifact.zip!docs/report.md", findings[0]["file"])


if __name__ == "__main__":
    unittest.main()
