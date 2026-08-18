# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.6 | Date: 2026-08-18
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicBoundaryEnvTests(unittest.TestCase):
    def test_env_file_is_classified_and_blocked(self) -> None:
        tools = Path(__file__).resolve().parents[1] / "tools"
        boundary = _load("iot_ai_public_boundary", tools / "public_boundary_check.py")
        with tempfile.TemporaryDirectory(prefix="iot-ai-boundary-env-") as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "docs" / ".env").write_text("OPENAI_API_KEY=" + "sk-" + "AUDITFIXTUREONLY1234567890\n", encoding="utf-8")
            (root / "README.md").write_text("Public documentation\n", encoding="utf-8")
            findings = boundary.scan_tree(root)
        self.assertTrue(any(item["rule"] == "forbidden-env-or-key" for item in findings))


if __name__ == "__main__":
    unittest.main()
