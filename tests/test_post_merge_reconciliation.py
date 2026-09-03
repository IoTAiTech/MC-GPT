# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-31
"""Post-merge truth and benchmark-trigger contracts."""
from __future__ import annotations
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_SHA = "51cb72e27d013d14ef2e3435ed84a3514b33c170"
TREE_SHA = "81e3b88bb0005cad19b58e016ac3b50b5e8443cd"
OPENWIKI_SHA = "58a1358e1f7d5b883db7405f56dcbdac3c4d7fe5"


class PostMergeReconciliationTests(unittest.TestCase):
    def test_release_status_matches_integrated_source_and_claim_boundary(self) -> None:
        status = json.loads((ROOT / "RELEASE_STATUS.json").read_text())
        self.assertEqual(status["suite_version"], "6.8.0-beta.1")
        self.assertEqual(status["mc_gpt_version"], "0.8.0-alpha.7")
        publication = status["publication"]
        self.assertEqual(publication["integration_snapshot_sha"], MAIN_SHA)
        self.assertEqual(publication["integration_tree_sha"], TREE_SHA)
        self.assertEqual(publication["branch_cleanup"], "only-protected-main-remains")
        self.assertFalse(publication["new_6_8_0_beta_1_release_performed"])
        self.assertFalse(status["production_ready"])
        self.assertFalse(status["production_or_fleet_install_authorized"])

    def test_benchmark_workflows_target_main_not_deleted_feature_branches(self) -> None:
        paths = [
            ROOT / ".github" / "workflows" / "benchmark-minimum-change-openwiki.yml",
            ROOT / ".github" / "workflows" / "deep-benchmark-contract.yml",
        ]
        joined = "\n".join(path.read_text() for path in paths)
        self.assertIn("- main", joined)
        self.assertNotIn("benchmark/minimum-change-openwiki-v1", joined)
        self.assertNotIn("benchmark/mncg-openwiki-v1", joined)
        self.assertNotIn("feature/minimum-necessary-change-gate-v1", joined)
        self.assertFalse((ROOT / ".github" / "workflows" / "openwiki-upstream-audit-20260830.yml").exists())

    def test_openwiki_pin_is_consistent(self) -> None:
        matrix = json.loads((ROOT / "benchmarks" / "deep-mncg-openwiki" / "RUN_MATRIX.json").read_text())
        workflow = (ROOT / ".github" / "workflows" / "benchmark-minimum-change-openwiki.yml").read_text()
        self.assertEqual(matrix["source_freeze"]["openwiki"], OPENWIKI_SHA)
        self.assertIn(f"OPENWIKI_COMMIT: {OPENWIKI_SHA}", workflow)

    def test_public_reconciliation_files_contain_no_arabic_script(self) -> None:
        pattern = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u0870-\u089f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")
        paths = [
            ROOT / "RELEASE_STATUS.json",
            ROOT / "docs" / "local-cli-seats.md",
            ROOT / "benchmarks" / "deep-mncg-openwiki" / "README.md",
            ROOT / "benchmarks" / "deep-mncg-openwiki" / "BENCHMARK_PROTOCOL.md",
            ROOT / "benchmarks" / "deep-mncg-openwiki" / "AMENDMENT_2026-08-31.json",
            ROOT / ".github" / "workflows" / "benchmark-minimum-change-openwiki.yml",
            ROOT / ".github" / "workflows" / "deep-benchmark-contract.yml",
        ]
        for path in paths:
            self.assertIsNone(pattern.search(path.read_text()), path)


if __name__ == "__main__":
    unittest.main()
