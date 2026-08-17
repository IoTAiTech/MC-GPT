# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.6 | Date: 2026-08-15
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LicenseUsagePagesTests(unittest.TestCase):
    def test_license_is_official_polyform_text(self) -> None:
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# PolyForm Noncommercial License 1.0.0\n"))
        self.assertIn("https://polyformproject.org/licenses/noncommercial/1.0.0", text)
        self.assertNotIn("Community use is noncommercial", text)
        self.assertNotIn("PolyForm Project Inc. publishes", text)

    def test_readme_has_usage_and_may_table(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Usage", text)
        self.assertIn("## Licence", text)
        self.assertIn("PolyForm-Noncommercial-1.0.0", text)
        self.assertIn("GitHub’s Fork button does not grant commercial rights", text)
        self.assertIn("USAGE.md", text)

    def test_usage_doc_exists(self) -> None:
        usage = (ROOT / "USAGE.md").read_text(encoding="utf-8")
        self.assertIn("iot-ai status", usage)
        self.assertIn("Allowed without a commercial licence", usage)
        pages = (ROOT / "docs/usage.md").read_text(encoding="utf-8")
        self.assertIn("iot-ai status", pages)

    def test_pages_index_has_usage_and_license(self) -> None:
        html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        self.assertIn('id="usage"', html)
        self.assertIn('id="license"', html)
        self.assertIn("PolyForm-Noncommercial-1.0.0", html)
        self.assertIn("usage.md", html)

    def test_pages_and_contact_have_company_linkedin(self) -> None:
        html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        contact = (ROOT / "CONTACT.md").read_text(encoding="utf-8")
        company = (ROOT / "docs/company.md").read_text(encoding="utf-8")
        self.assertIn('id="company"', html)
        self.assertIn("https://www.linkedin.com/company/iot-ai-tech", html)
        self.assertIn("https://www.linkedin.com/in/dr-babakskr", html)
        self.assertIn("https://iotaitech.github.io/", html)
        self.assertIn("Aschaffenburg", html)
        self.assertIn("https://www.linkedin.com/company/iot-ai-tech", contact)
        self.assertIn("Aschaffenburg", contact)
        self.assertIn("AI/IoT Product Portfolio Coordination", company)
        self.assertIn("production_claim: false", company)


if __name__ == "__main__":
    unittest.main()
