# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-29
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MinimumChangeBenchmarkTests(unittest.TestCase):
    def test_deterministic_benchmark_passes_without_provider_calls(self) -> None:
        completed = subprocess.run(
            [sys.executable, "benchmarks/minimum-change/evaluate.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"], "pass")
        self.assertEqual(payload["positive_passed"], 12)
        self.assertEqual(payload["positive_total"], 12)
        self.assertEqual(payload["provider_calls"], 0)
        self.assertEqual(payload["savings_claim"], "not-measured")
        self.assertFalse(payload["production_claim"])


if __name__ == "__main__":
    unittest.main()
