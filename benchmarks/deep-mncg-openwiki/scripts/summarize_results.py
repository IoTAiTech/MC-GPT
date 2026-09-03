#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-31
"""Summarize immutable trial receipts with paired descriptive statistics."""
from __future__ import annotations
import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

BENCHMARK_ID = "mcgpt-mncg-openwiki-2026-02"
METRICS = (
    "source_lines_added",
    "input_tokens",
    "output_tokens",
    "provider_cost_usd",
    "total_duration_seconds",
)


def median(values):
    return statistics.median(values) if values else None


def iqr(values):
    if len(values) < 4:
        return None
    quartiles = statistics.quantiles(sorted(values), n=4, method="inclusive")
    return quartiles[2] - quartiles[0]


def wilson(successes, total, z=1.959963984540054):
    if not total:
        return [None, None]
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    half = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total) / denominator
    return [max(0, center - half), min(1, center + half)]


def bootstrap(values, seed=20260831, iterations=10000):
    if not values:
        return [None, None]
    randomizer = random.Random(seed)
    samples = sorted(
        statistics.median([values[randomizer.randrange(len(values))] for _ in values])
        for _ in range(iterations)
    )
    return [samples[int(0.025 * iterations)], samples[int(0.975 * iterations)]]


def hard_gate_passed(row):
    gates = row.get("hard_gates") or {}
    required = (
        "security_privacy_passed",
        "data_loss_rollback_passed",
        "accessibility_passed",
        "model_identity_passed",
        "contamination_absent",
        "clean_patch_boundary_passed",
        "common_source_identity_passed",
        "treatment_bundle_identity_passed",
    )
    return row.get("status") == "pass" and all(gates.get(key) is True for key in required)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [json.loads(path.read_text()) for path in sorted(Path(args.results).glob("*.json"))]
    by_arm = defaultdict(list)
    for row in rows:
        if row.get("benchmark_id") != BENCHMARK_ID:
            raise ValueError(f"unexpected benchmark_id in {row.get('trial_id')}")
        by_arm[row["arm_id"]].append(row)

    arms = {}
    for arm, items in sorted(by_arm.items()):
        passed = [item for item in items if hard_gate_passed(item)]
        arms[arm] = {
            "attempted": len(items),
            "hard_gate_passed": len(passed),
            "success_rate": len(passed) / len(items) if items else None,
            "success_wilson_95": wilson(len(passed), len(items)),
            "metrics_on_success": {
                metric: {
                    "median": median([item["metrics"][metric] for item in passed if item["metrics"].get(metric) is not None]),
                    "iqr": iqr([item["metrics"][metric] for item in passed if item["metrics"].get(metric) is not None]),
                }
                for metric in METRICS
            },
        }

    blocks = defaultdict(dict)
    for row in rows:
        key = (
            row["task_id"],
            row["provider_slot"],
            row["model_served"],
            row["repetition"],
            row["seed"],
            row["base_commit_sha"],
            row["base_tree_sha"],
        )
        blocks[key][row["arm_id"]] = row

    comparisons = []
    for treatment in ("B_SIMPLE_YAGNI", "C_PONYTAIL_PINNED", "D_MNCG", "E_OPENWIKI", "F_MNCG_OPENWIKI"):
        pairs = [
            (block["A_BASELINE"], block[treatment])
            for block in blocks.values()
            if "A_BASELINE" in block
            and treatment in block
            and hard_gate_passed(block["A_BASELINE"])
            and hard_gate_passed(block[treatment])
        ]
        statistics_by_metric = {}
        for metric in METRICS:
            differences = [
                other["metrics"][metric] - baseline["metrics"][metric]
                for baseline, other in pairs
                if baseline["metrics"].get(metric) is not None
                and other["metrics"].get(metric) is not None
            ]
            statistics_by_metric[metric] = {
                "pairs": len(differences),
                "median_difference": median(differences),
                "iqr_difference": iqr(differences),
                "paired_bootstrap_95": bootstrap(differences),
            }
        comparisons.append(
            {
                "comparison": f"{treatment}-A_BASELINE",
                "successful_pairs": len(pairs),
                "metrics": statistics_by_metric,
            }
        )

    minimum_pairs = min(
        (metric["pairs"] for comparison in comparisons for metric in comparison["metrics"].values()),
        default=0,
    )
    output = {
        "schema": "iot-ai.deep-benchmark-summary.v2",
        "benchmark_id": BENCHMARK_ID,
        "trial_count": len(rows),
        "valid_trial_count": sum(isinstance(row.get("receipt_sha256"), str) for row in rows),
        "arms": arms,
        "comparisons": comparisons,
        "claim_decision": "eligible_for_internal_review" if minimum_pairs >= 10 else "insufficient_evidence",
        "production_claim": False,
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
