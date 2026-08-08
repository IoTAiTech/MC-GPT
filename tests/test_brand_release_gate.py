# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


class BrandReleaseGateTests(unittest.TestCase):
    def test_legacy_brand_references_are_fully_classified(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, str(root / "tools" / "brand_identity_check.py"), str(root)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        value = json.loads(completed.stdout)
        self.assertEqual(value["canonical_company"], "IoT-AI.Tech")
        self.assertEqual(value["unclassified_count"], 0)
        self.assertTrue(value["occurrences"])

    def test_article_50_operator_uses_canonical_identity(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "src" / "iot_ai" / "transparency.py").read_text(encoding="utf-8")
        self.assertIn("IoT-AI.Tech", text)
        self.assertNotIn("AI" + "-IoT.Tech", text)


if __name__ == "__main__":
    unittest.main()
