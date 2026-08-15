# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.6 | Date: 2026-08-15
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from iot_ai.cli import main
from iot_ai.github_analysis import analyze_records, classify, parse_repo_ref


class GitHubAnalysisTests(unittest.TestCase):
    def test_parse_url_and_slug(self) -> None:
        self.assertEqual(parse_repo_ref("https://github.com/affaan-m/ECC"), "affaan-m/ECC")
        self.assertEqual(parse_repo_ref("owner/name.git"), "owner/name")

    def test_missing_license_is_block(self) -> None:
        row = classify(repo="angelos-p/llm-from-scratch", spdx=None, description="tutorial")
        self.assertEqual(row["use"], "NO")
        self.assertFalse(row["adds_dependency"])
        self.assertFalse(row["relicense_us"])

    def test_copyleft_is_not_vendored(self) -> None:
        row = classify(repo="halfgaar/FlashMQ", spdx="OSL-3.0", description="MQTT broker")
        self.assertEqual(row["use"], "NO_VENDOR")
        self.assertFalse(row["adds_dependency"])

    def test_mark_stripper_contradicts_product(self) -> None:
        row = classify(
            repo="guillaumemeyer/watermarks-remover",
            spdx="MIT",
            description="Strip C2PA and SynthID marks",
        )
        self.assertEqual(row["use"], "NO")
        self.assertEqual(row["relevance"], "contradicts_product")

    def test_permissive_is_ideas_only(self) -> None:
        row = classify(repo="paperclipai/paperclip", spdx="MIT", description="agent org app")
        self.assertEqual(row["use"], "PATTERNS_ONLY")
        self.assertFalse(row["adds_dependency"])

    def test_batch_never_recommends_dependency(self) -> None:
        result = analyze_records(
            [
                {"repo": "vernemq/vernemq", "spdx": "Apache-2.0", "description": "MQTT broker"},
                {"url": "https://github.com/opensandbox-group/OpenSandbox", "spdx": "Apache-2.0"},
            ]
        )
        self.assertFalse(result["adds_dependency"])
        self.assertFalse(result["relicense_us"])
        self.assertEqual(len(result["repos"]), 2)

    def test_cli_offline_json(self) -> None:
        payload = [
            {"repo": "example/tool", "spdx": "MIT", "description": "sample"},
            {"repo": "example/secret-sauce", "spdx": None, "description": "no grant"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "in.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            code = main(["github-analyze", "--offline-json", str(path), "--no-network"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
