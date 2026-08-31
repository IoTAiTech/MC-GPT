# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0
"""Regression test for opaque, nonnumeric benchmark task identifiers."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "minimum-change-v2"


class BenchmarkOpaqueTaskIdTests(unittest.TestCase):
    def test_synthetic_selftest_accepts_opaque_task_ids(self) -> None:
        spec = importlib.util.spec_from_file_location("benchmark_v2_opaque_id", BENCH / "benchmark.py")
        if spec is None or spec.loader is None:
            self.fail("unable to load benchmark module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        protocol = json.loads((BENCH / "protocol.json").read_text(encoding="utf-8"))
        corpus = json.loads((BENCH / "task-corpus.json").read_text(encoding="utf-8"))
        corpus["tasks"][0]["id"] = "Tui"
        schedule = module.build_schedule(protocol, corpus, provider_ids=["openai-codex"])
        results = module.synthetic_results(schedule)
        self.assertEqual(len(results), schedule["run_count"])
        self.assertTrue(any(row["task_id"] == "Tui" for row in results))
        analysis = module.analyse_results(protocol, corpus, schedule, results)
        self.assertEqual(analysis["decision"], "pass")
        self.assertFalse(analysis["any_savings_claim_allowed"])


if __name__ == "__main__":
    unittest.main()
