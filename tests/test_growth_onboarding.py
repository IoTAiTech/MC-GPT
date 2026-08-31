# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-29
"""Public onboarding, fixture and metadata regression contracts."""

from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "quickstart-demo"


class PublicGrowthOnboardingTests(unittest.TestCase):
    def test_public_entry_points_use_supported_install_paths(self) -> None:
        texts = [
            (ROOT / "README.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "installation.md").read_text(encoding="utf-8"),
        ]
        joined = "\n".join(texts)
        self.assertNotIn("install-community-preview.sh", joined)
        self.assertNotIn("<ALL-IN-ONE-SHA256>", joined)
        self.assertIn("python3 -m pipx install", joined)
        self.assertNotIn("\npipx install", joined)
        self.assertIn(".mc-gpt-venv/bin/iot-ai", joined)
        self.assertFalse((ROOT / "installers" / "install-community-preview.sh").exists())

    def test_natural_language_plan_examples_do_not_use_unsupported_flag(self) -> None:
        for path in (
            ROOT / "README.md",
            ROOT / "docs" / "quickstart.md",
            DEMO / "README.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("\n  --plan", text, path.as_posix())
            self.assertIn("do not execute", text.lower(), path.as_posix())

    def test_fixture_declares_and_documents_all_nine_criteria(self) -> None:
        task = (DEMO / "TASK.md").read_text(encoding="utf-8")
        criteria = re.findall(r"(?m)^\d+\.\s", task)
        self.assertEqual(len(criteria), 9)
        demo_readme = (DEMO / "README.md").read_text(encoding="utf-8").lower()
        quickstart = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8").lower()
        self.assertIn("all nine acceptance criteria", demo_readme)
        self.assertIn("nine-criterion", quickstart)

    def test_fixture_is_detectable_by_post_change_test_inference(self) -> None:
        data = tomllib.loads((DEMO / "pyproject.toml").read_text(encoding="utf-8"))
        pytest_options = data["tool"]["pytest"]["ini_options"]
        self.assertEqual(pytest_options["testpaths"], ["tests"])
        self.assertTrue((DEMO / "tests").is_dir())

    def test_demo_python_sources_have_required_public_headers(self) -> None:
        for path in (DEMO / "auth_service.py", DEMO / "tests" / "test_auth_service.py"):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(
                text.startswith(
                    "# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0\n"
                    "# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour\n"
                ),
                path.as_posix(),
            )

    def test_metadata_script_consumes_the_canonical_json(self) -> None:
        metadata = json.loads(
            (ROOT / "GITHUB_REPOSITORY_METADATA.json").read_text(encoding="utf-8")
        )
        script = (ROOT / "scripts" / "apply-github-metadata.sh").read_text(
            encoding="utf-8"
        )
        self.assertEqual(metadata["repository"], "IoTAiTech/MC-GPT")
        self.assertLessEqual(len(metadata["topics"]), 20)
        self.assertIn("GITHUB_REPOSITORY_METADATA.json", script)
        self.assertIn('data["description"]', script)
        self.assertIn('data["homepage"]', script)
        self.assertIn('data["topics"]', script)

    def test_changed_public_material_contains_no_private_network_or_rtl_text(self) -> None:
        paths = [
            ROOT / "README.md",
            ROOT / "docs" / "quickstart.md",
            ROOT / "docs" / "installation.md",
            DEMO / "README.md",
            DEMO / "TASK.md",
            DEMO / "auth_service.py",
            DEMO / "tests" / "test_auth_service.py",
            DEMO / "pyproject.toml",
            ROOT / "scripts" / "apply-github-metadata.sh",
        ]
        private_ipv4 = re.compile(
            r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
        )
        rtl = re.compile(r"[\u0600-\u06ff]")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(private_ipv4.search(text), path.as_posix())
            self.assertIsNone(rtl.search(text), path.as_posix())


if __name__ == "__main__":
    unittest.main()
