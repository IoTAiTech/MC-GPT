# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Deterministic micro-benchmark for the owned agent-runtime compilation path."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from iot_ai.context_compiler import compile_context  # noqa: E402
from iot_ai.goal_contract import compile_goal_contract  # noqa: E402
from iot_ai.prompt_compiler import compile_prompt  # noqa: E402
from iot_ai.roles import ROLE_CATALOG  # noqa: E402
from iot_ai.tool_router import build_tool_decision  # noqa: E402


def percentile(values: list[float], value: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * value))))
    return ordered[index]


def run(iterations: int) -> dict[str, object]:
    samples: list[float] = []
    role = ROLE_CATALOG["security-challenger"].to_dict()
    node = {
        "node_id": "security-review",
        "mission": "Audit an agent-runtime change and preserve privacy boundaries.",
        "stage": "review",
        "required_output_fields": ["decision", "findings", "evidence_refs"],
    }
    candidate = {
        "candidate_id": "ollama:benchmark:cloud:security",
        "provider": "ollama",
        "route_id": "ollama-cloud",
        "model": "benchmark:cloud",
        "live_ready": True,
        "cloud": True,
        "receipt": {
            "authenticated": True,
            "model_identity_verified": True,
            "model_served": "benchmark:cloud",
            "effort_supported": ["medium", "high", "xhigh"],
        },
    }
    for index in range(iterations):
        started = time.perf_counter_ns()
        goal = compile_goal_contract(
            f"Review runtime iteration {index}; do not expose private data; done when evidence-bound tests pass.",
            explicit_success_criteria=("All hard gates pass.",),
        )
        context = compile_context(
            goal_contract=goal.to_dict(),
            role_contract=role,
            node_contract=node,
            inputs={"evidence": {"status": "pass", "findings": ["bounded"], "iteration": index}},
            privacy_class="D1",
            token_budget=16_000,
        )
        prompt = compile_prompt(
            goal_contract=goal.to_dict(),
            role_contract=role,
            node_contract=node,
            context_manifest=context,
            policy={"evidence_first": True, "bounded": True},
        )
        decision = build_tool_decision(
            [candidate],
            role_id="security-challenger",
            requested_effort="xhigh",
            privacy_class="D1",
        )
        if not prompt.sha256 or decision["decision"] != "pass":
            raise RuntimeError("benchmark correctness gate failed")
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    result = {
        "schema": "iot-ai.agent-runtime-benchmark.v1",
        "decision": "pass",
        "iterations": iterations,
        "mean_ms": round(statistics.fmean(samples), 4),
        "median_ms": round(statistics.median(samples), 4),
        "p95_ms": round(percentile(samples, 0.95), 4),
        "p99_ms": round(percentile(samples, 0.99), 4),
        "max_ms": round(max(samples), 4),
        "target_p95_ms": 10.0,
        "target_met": percentile(samples, 0.95) <= 10.0,
        "scope": "goal+context+prompt+tool-decision compilation only; excludes provider network latency",
    }
    result["decision"] = "pass" if result["target_met"] else "needs-work"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.iterations < 10:
        parser.error("iterations must be at least 10")
    result = run(args.iterations)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
