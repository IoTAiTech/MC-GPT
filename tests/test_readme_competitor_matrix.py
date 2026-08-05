# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
from __future__ import annotations

import unittest
from pathlib import Path


class ReadmeCompetitorMatrixTests(unittest.TestCase):
    def test_readme_has_quantitative_and_qualitative_comparison(self) -> None:
        text = Path("README.md").read_text(encoding="utf-8")
        for value in (
            "Competitive comparison",
            "Comparison methodology",
            "Claude Code Agent Teams",
            "GitHub Copilot Fleet",
            "AgentGem",
            "ServiceNow AI Control Tower",
            "Quantitative",
            "Qualitative",
            "not evidenced in reviewed public documentation",
        ):
            self.assertIn(value, text)
        self.assertNotIn("fully EU AI Act compliant", text.lower())
        self.assertNotIn("better than every competitor", text.lower())


if __name__ == "__main__":
    unittest.main()
