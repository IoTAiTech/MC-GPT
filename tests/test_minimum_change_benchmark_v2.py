# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0
"""Deep deterministic contracts for the paired minimum-change benchmark."""
from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "minimum-change-v2"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("minimum_change_benchmark_v2", BENCH / "benchmark.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load benchmark module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MinimumChangeBenchmarkV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.protocol = json.loads((BENCH / "protocol.json").read_text(encoding="utf-8"))
        cls.corpus = json.loads((BENCH / "task-corpus.json").read_text(encoding="utf-8"))

    def test_protocol_and_corpus_are_strictly_valid(self) -> None:
        result = self.module.validate_protocol(self.protocol, self.corpus)
        self.assertEqual(result["decision"], "pass", result)
        self.assertEqual(result["task_count"], 24)
        self.assertEqual(result["enabled_arms"], ["baseline", "simple-yagni", "mcgpt-minimum-change"])
        self.assertFalse(result["production_claim"])

    def test_schedule_is_deterministic_balanced_and_unique(self) -> None:
        first = self.module.build_schedule(self.protocol, self.corpus, provider_ids=["openai-codex"])
        second = self.module.build_schedule(self.protocol, self.corpus, provider_ids=["openai-codex"])
        self.assertEqual(first, second)
        self.assertEqual(first["run_count"], 24 * 5 * 3)
        self.assertEqual(len({row["run_id"] for row in first["runs"]}), first["run_count"])
        grouped: dict[tuple[str, int], set[str]] = {}
        for row in first["runs"]:
            grouped.setdefault((row["task_id"], row["repetition"]), set()).add(row["arm_id"])
        self.assertTrue(all(value == set(first["enabled_arms"]) for value in grouped.values()))

    def test_synthetic_results_validate_but_cannot_authorize_public_savings_claim(self) -> None:
        schedule = self.module.build_schedule(self.protocol, self.corpus, provider_ids=["openai-codex"])
        results = self.module.synthetic_results(schedule)
        validation = self.module.validate_results(results, schedule)
        analysis = self.module.analyse_results(self.protocol, self.corpus, schedule, results)
        self.assertEqual(validation["decision"], "pass", validation)
        self.assertEqual(analysis["decision"], "pass", analysis)
        self.assertFalse(analysis["any_savings_claim_allowed"])
        self.assertEqual(analysis["public_claim_status"], "not-measured")
        self.assertTrue(all(not row["savings_claim_allowed"] for row in analysis["comparisons"].values()))

    def test_failed_hard_gate_blocks_claim_even_for_real_verified_data(self) -> None:
        schedule = self.module.build_schedule(self.protocol, self.corpus, provider_ids=["openai-codex"])
        results = self.module.synthetic_results(schedule)
        for row in results:
            row["data_classification"] = "real"
        target = next(row for row in results if row["arm_id"] == "mcgpt-minimum-change")
        target["terminal_state"] = "needs-work"
        target["hard_gates"]["security_privacy_controls_passed"] = False
        target["evidence"]["test_evidence_sha256"] = None
        validation = self.module.validate_results(results, schedule)
        analysis = self.module.analyse_results(self.protocol, self.corpus, schedule, results)
        self.assertEqual(validation["decision"], "pass", validation)
        self.assertFalse(analysis["comparisons"]["mcgpt-minimum-change"]["savings_claim_allowed"])
        self.assertTrue(analysis["comparisons"]["mcgpt-minimum-change"]["hard_gate_inferior"])

    def test_unverified_model_identity_blocks_claim(self) -> None:
        schedule = self.module.build_schedule(self.protocol, self.corpus, provider_ids=["openai-codex"])
        results = self.module.synthetic_results(schedule)
        for row in results:
            row["data_classification"] = "real"
        results[0]["model_identity_verified"] = False
        results[0]["model_served"] = None
        analysis = self.module.analyse_results(self.protocol, self.corpus, schedule, results)
        self.assertEqual(analysis["decision"], "pass")
        self.assertTrue(all(not row["savings_claim_allowed"] for row in analysis["comparisons"].values()))

    def test_result_tampering_and_metric_abuse_fail_closed(self) -> None:
        schedule = self.module.build_schedule(self.protocol, self.corpus, provider_ids=["openai-codex"])
        result = self.module.synthetic_results(schedule)[0]
        mutations = []
        wrong_run = dict(result)
        wrong_run["run_id"] = "run-" + "0" * 24
        mutations.append(wrong_run)
        negative = json.loads(json.dumps(result))
        negative["metrics"]["source_lines_added"] = -1
        mutations.append(negative)
        nan_value = json.loads(json.dumps(result))
        nan_value["metrics"]["wall_clock_seconds"] = float("nan")
        mutations.append(nan_value)
        false_complete = json.loads(json.dumps(result))
        false_complete["hard_gates"]["independent_review_passed"] = False
        mutations.append(false_complete)
        token_mismatch = json.loads(json.dumps(result))
        token_mismatch["metrics"]["tokens_total"] += 1
        mutations.append(token_mismatch)
        for candidate in mutations:
            with self.subTest(candidate=candidate):
                self.assertEqual(self.module.validate_result(candidate, schedule)["decision"], "block")

    def test_selftest_outputs_are_reproducible(self) -> None:
        schedule = self.module.build_schedule(self.protocol, self.corpus, provider_ids=["openai-codex"])
        results = self.module.synthetic_results(schedule)
        first = self.module.analyse_results(self.protocol, self.corpus, schedule, results)
        second = self.module.analyse_results(self.protocol, self.corpus, schedule, results)
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            self.module.write_json(output / "schedule.json", schedule)
            self.module.write_jsonl(output / "results.jsonl", results)
            self.assertEqual(self.module.read_jsonl(output / "results.jsonl"), results)

    def test_schedule_cli_exits_zero_without_a_decision_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "schedule.json"
            with redirect_stdout(io.StringIO()):
                rc = self.module.cli(
                    ["schedule", "--providers", "openai-codex", "--output", str(output)]
                )
            self.assertEqual(rc, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "pass")
            self.assertEqual(payload["run_count"], 24 * 5 * 3)


if __name__ == "__main__":
    unittest.main()
