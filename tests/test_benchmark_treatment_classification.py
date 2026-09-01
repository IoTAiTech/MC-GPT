# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-01
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "deep-mncg-openwiki"
REQUIRED_FIELDS = ("kind", "runtime_component", "dependency_policy", "production_eligibility", "treatment_bundle")
KINDS = {
    "A_BASELINE": "benchmark_control",
    "B_SIMPLE_YAGNI": "benchmark_ablation",
    "C_PONYTAIL_PINNED": "external_comparator",
    "D_MNCG": "native_runtime_gate",
    "E_OPENWIKI": "optional_context_adapter_benchmark",
    "F_MNCG_OPENWIKI": "integration_benchmark_profile",
}


class BenchmarkTreatmentClassificationTests(unittest.TestCase):
    def test_one_user_facing_coder_runtime(self) -> None:
        runtime = json.loads((BENCH / "CODER_RUNTIME.json").read_text(encoding="utf-8"))
        self.assertEqual(runtime["user_facing_coder_runtime"], "iot-ai")
        self.assertEqual(runtime["user_facing_coder_runtime_count"], 1)
        self.assertIs(runtime["benchmark_treatments_are_not_products"], True)
        self.assertIs(runtime["native_mncg_authoritative"], True)
        self.assertIs(runtime["native_mncg_production_eligible"], True)
        self.assertIs(runtime["openwiki_default_off"], True)
        self.assertEqual(runtime["openwiki_production_eligible"], "conditional")
        self.assertIs(runtime["benchmark_runner_selects_treatments"], True)
        self.assertIs(runtime["production_claim"], False)
        self.assertEqual(
            runtime["pipeline"],
            [
                "intake_and_normalization",
                "reuse_first_precheck",
                "optional_knowledge_context_adapter",
                "native_mncg_decision",
                "plan_or_execute",
                "deterministic_verification_and_evidence",
            ],
        )

    def test_every_treatment_is_classified_and_not_a_product(self) -> None:
        registry = json.loads((BENCH / "TREATMENTS.json").read_text(encoding="utf-8"))
        treatments = registry["treatments"]
        self.assertEqual(set(treatments), set(KINDS))
        for arm_id, expected_kind in KINDS.items():
            row = treatments[arm_id]
            for field in REQUIRED_FIELDS:
                self.assertIn(field, row, arm_id)
            self.assertEqual(row["kind"], expected_kind, arm_id)
            self.assertNotIn("components", row, arm_id)
        self.assertIs(treatments["A_BASELINE"]["production_eligibility"], False)
        self.assertIs(treatments["B_SIMPLE_YAGNI"]["production_eligibility"], False)
        self.assertEqual(treatments["B_SIMPLE_YAGNI"]["folded_into"]["component"], "native_mncg")
        self.assertEqual(treatments["B_SIMPLE_YAGNI"]["folded_into"]["function"], "reuse_first_precheck")
        self.assertIs(treatments["C_PONYTAIL_PINNED"]["production_eligibility"], False)
        self.assertIs(treatments["C_PONYTAIL_PINNED"]["production_dependency"], False)
        self.assertIs(treatments["D_MNCG"]["production_eligibility"], True)
        self.assertEqual(treatments["E_OPENWIKI"]["production_eligibility"], "conditional")
        self.assertIs(treatments["F_MNCG_OPENWIKI"]["production_eligibility"], False)
        matrix = json.loads((BENCH / "RUN_MATRIX.json").read_text(encoding="utf-8"))
        for arm in matrix["arms"]:
            self.assertNotIn("components", arm, arm["arm_id"])
            self.assertEqual(arm["treatment_bundle"], treatments[arm["arm_id"]]["treatment_bundle"], arm["arm_id"])
        self.assertIs(treatments["D_MNCG"]["runtime_component"], True)
        self.assertIs(treatments["D_MNCG"]["authoritative"], True)
        self.assertIs(treatments["E_OPENWIKI"]["runtime_component"], False)
        self.assertIs(treatments["E_OPENWIKI"]["default_enabled"], False)
        self.assertIs(treatments["E_OPENWIKI"]["task_authority"], False)
        self.assertIs(treatments["E_OPENWIKI"]["direct_product_db_access"], False)
        self.assertIs(treatments["E_OPENWIKI"]["direct_golden_write"], False)
        self.assertEqual(treatments["F_MNCG_OPENWIKI"]["composition"], ["D_MNCG", "E_OPENWIKI"])
        self.assertIs(treatments["F_MNCG_OPENWIKI"]["runtime_component"], False)

    def test_all_treatments_classified(self) -> None:
        self.test_every_treatment_is_classified_and_not_a_product()

    def test_benchmark_arms_exposed_as_products_is_false(self) -> None:
        runtime = json.loads((BENCH / "CODER_RUNTIME.json").read_text(encoding="utf-8"))
        self.assertIs(runtime["benchmark_treatments_are_not_products"], True)

    def test_openwiki_default_enabled_is_false(self) -> None:
        runtime = json.loads((BENCH / "CODER_RUNTIME.json").read_text(encoding="utf-8"))
        self.assertIs(runtime["openwiki_default_off"], True)

    def test_docs_call_them_experimental_arms(self) -> None:
        readme = (BENCH / "README.md").read_text(encoding="utf-8")
        protocol = (BENCH / "BENCHMARK_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("Experimental arms", readme)
        self.assertIn("experimental treatment", protocol.lower() + protocol)
        self.assertIn("not architecture components", readme.lower())
        self.assertNotIn("six user-facing coder products", readme.lower())

    def test_public_docs_lock_runtime_pipeline_tokens(self) -> None:
        runtime = json.loads((BENCH / "CODER_RUNTIME.json").read_text(encoding="utf-8"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
        for token in runtime["pipeline"]:
            self.assertIn(token, readme, token)
            self.assertIn(token, architecture, token)


if __name__ == "__main__":
    unittest.main()
