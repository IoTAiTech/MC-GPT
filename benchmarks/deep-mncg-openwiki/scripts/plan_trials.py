#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-31
"""Create a deterministic counterbalanced trial plan without provider calls."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path


def order(values, key):
    return sorted(values, key=lambda value: hashlib.sha256(f"{key}:{value}".encode()).hexdigest())


def treatment_digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--stage", choices=("smoke", "pilot", "confirmatory"), required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    matrix = json.loads((root / "RUN_MATRIX.json").read_text())
    tasks = json.loads((root / "TASK_SUITE.json").read_text())["tasks"]
    models = json.loads(Path(args.models).read_text())["models"]
    treatment_registry = json.loads((root / "TREATMENTS.json").read_text())
    treatments = treatment_registry["treatments"]
    stage = matrix["stages"][args.stage]
    selected = [row for row in tasks if args.stage in row["enabled_stages"]][: stage["tasks"]]
    enabled = [row for row in models if row.get("enabled") is True]
    common_commit = matrix["source_freeze"]["mcgpt_common_source"]
    common_tree = matrix["source_freeze"]["mcgpt_common_tree"]
    rows = []

    for task in selected:
        for model in enabled:
            for repetition in range(1, stage["repetitions"] + 1):
                block = f"{task['task_id']}:{model['slot_id']}:{repetition}"
                for position, arm in enumerate(order(stage["arms"], block), 1):
                    exact = (
                        model.get("model_requested") not in (None, "", "REQUIRED_AT_RUNTIME")
                        and model.get("model_requested") == model.get("model_served")
                        and isinstance(model.get("qualification_receipt_sha256"), str)
                        and len(model["qualification_receipt_sha256"]) == 64
                    )
                    trial_id = hashlib.sha256(
                        f"{matrix['benchmark_id']}:{block}:{arm}".encode()
                    ).hexdigest()[:24]
                    rows.append(
                        {
                            "trial_id": trial_id,
                            "task_id": task["task_id"],
                            "upstream_task_name": task["upstream_task_name"],
                            "arm_id": arm,
                            "provider_slot": model["slot_id"],
                            "model_requested": model.get("model_requested"),
                            "model_served": model.get("model_served"),
                            "repetition": repetition,
                            "order_in_block": position,
                            "base_commit_sha": common_commit,
                            "base_tree_sha": common_tree,
                            "treatment_bundle_sha256": treatment_digest(treatments[arm]),
                            "executable": exact,
                        }
                    )

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "iot-ai.deep-benchmark-trial-plan.v2",
        "benchmark_id": matrix["benchmark_id"],
        "stage": args.stage,
        "qualified_provider_slots": len(enabled),
        "trial_count": len(rows),
        "executable_trial_count": sum(bool(row["executable"]) for row in rows),
        "common_source_commit": common_commit,
        "common_source_tree": common_tree,
        "trials": rows,
        "production_claim": False,
    }
    (output / "trial-plan.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    fields = list(rows[0]) if rows else [
        "trial_id",
        "task_id",
        "upstream_task_name",
        "arm_id",
        "provider_slot",
        "model_requested",
        "model_served",
        "repetition",
        "order_in_block",
        "base_commit_sha",
        "base_tree_sha",
        "treatment_bundle_sha256",
        "executable",
    ]
    with (output / "trial-plan.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(
        json.dumps(
            {
                "decision": "pass",
                "stage": args.stage,
                "trial_count": len(rows),
                "executable_trial_count": sum(bool(row["executable"]) for row in rows),
                "common_source_commit": common_commit,
                "common_source_tree": common_tree,
                "output": str(output),
                "production_claim": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
