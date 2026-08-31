# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 2.0.0 | Date: 2026-08-31
from __future__ import annotations
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ID = "mcgpt-mncg-openwiki-2026-02"
EXPECTED_COMMIT = "51cb72e27d013d14ef2e3435ed84a3514b33c170"
EXPECTED_TREE = "81e3b88bb0005cad19b58e016ac3b50b5e8443cd"
EXPECTED_OPENWIKI = "58a1358e1f7d5b883db7405f56dcbdac3c4d7fe5"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContractTests(unittest.TestCase):
    def test_public_contract_validates(self) -> None:
        load(ROOT / "scripts" / "validate_benchmark.py", "validate_benchmark")
        status = json.loads((ROOT / "STATUS.json").read_text())
        self.assertEqual(status["provider_trials_executed"], 0)
        self.assertEqual(status["benchmark_id"], EXPECTED_ID)
        self.assertEqual(status["common_source_commit"], EXPECTED_COMMIT)
        self.assertEqual(status["common_source_tree"], EXPECTED_TREE)
        self.assertTrue((ROOT / "AMENDMENT_2026-08-31.json").is_file())

    def test_plan_is_deterministic_and_non_executable_without_qualified_models(self) -> None:
        planner = load(ROOT / "scripts" / "plan_trials.py", "plan_trials")
        matrix = json.loads((ROOT / "RUN_MATRIX.json").read_text())
        self.assertEqual(len(matrix["arms"]), 6)
        self.assertEqual(len(json.loads((ROOT / "TASK_SUITE.json").read_text())["tasks"]), 30)
        self.assertEqual(planner.order(["a", "b", "c"], "fixed"), planner.order(["a", "b", "c"], "fixed"))

    def test_all_contract_files_share_one_benchmark_identity(self) -> None:
        for name in ("STATUS.json", "RUN_MATRIX.json", "SCORING_SPEC.json", "PREREGISTRATION.json"):
            payload = json.loads((ROOT / name).read_text())
            self.assertEqual(payload["benchmark_id"], EXPECTED_ID, name)
            self.assertIs(payload.get("production_claim"), False, name)
        schema = json.loads((ROOT / "schemas" / "trial-receipt.schema.json").read_text())
        self.assertEqual(schema["properties"]["benchmark_id"]["const"], EXPECTED_ID)
        self.assertEqual(schema["properties"]["base_commit_sha"]["const"], EXPECTED_COMMIT)
        self.assertEqual(schema["properties"]["base_tree_sha"]["const"], EXPECTED_TREE)

    def test_source_and_openwiki_pins_are_consistent(self) -> None:
        matrix = json.loads((ROOT / "RUN_MATRIX.json").read_text())
        freeze = matrix["source_freeze"]
        self.assertEqual(freeze["mcgpt_common_source"], EXPECTED_COMMIT)
        self.assertEqual(freeze["mcgpt_common_tree"], EXPECTED_TREE)
        self.assertEqual(freeze["openwiki"], EXPECTED_OPENWIKI)
        self.assertNotIn("mcgpt_mncg_pr14_head", freeze)
        self.assertNotIn("mcgpt_public_main", freeze)

    def test_treatment_registry_matches_arms_and_has_stable_digests(self) -> None:
        planner = load(ROOT / "scripts" / "plan_trials.py", "plan_trials_for_treatments")
        matrix = json.loads((ROOT / "RUN_MATRIX.json").read_text())
        registry = json.loads((ROOT / "TREATMENTS.json").read_text())
        arm_ids = {row["arm_id"] for row in matrix["arms"]}
        self.assertEqual(set(registry["treatments"]), arm_ids)
        digests = {
            arm: planner.treatment_digest(value)
            for arm, value in registry["treatments"].items()
        }
        self.assertEqual(len(digests), 6)
        self.assertEqual(len(set(digests.values())), 6)
        self.assertTrue(all(len(value) == 64 for value in digests.values()))

    def test_claim_boundary(self) -> None:
        for name in ("STATUS.json", "RUN_MATRIX.json", "TASK_SUITE.json", "SCORING_SPEC.json", "PREREGISTRATION.json", "MODELS.example.json"):
            payload = json.loads((ROOT / name).read_text())
            self.assertIs(payload.get("production_claim"), False, name)


if __name__ == "__main__":
    unittest.main()
