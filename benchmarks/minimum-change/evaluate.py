#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-29
"""Deterministic semantic selftest for the Minimum Necessary Change Gate.

This benchmark measures gate correctness, not code/token/cost savings. Savings require
an independently comparable provider baseline and post-change hard-gate evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from iot_ai.minimum_change import (  # noqa: E402
    NON_NEGOTIABLE_CONTROLS,
    RUNG_DEFINITIONS,
    ZERO_DEFAULT_BUDGETS,
    assess_strategy,
    compile_contract,
)

RUNG_IDS = [item["id"] for item in RUNG_DEFINITIONS]


def task(case_id: str) -> dict[str, Any]:
    return {
        "id": f"task-{case_id}",
        "revision": 1,
        "title": f"Minimum-change benchmark {case_id}",
        "description": "Select the first evidence-sufficient engineering rung.",
        "acceptance_criteria": "The selected rung and all preserved controls are evidence-bound.",
        "risk_class": "R2",
        "priority": "high",
        "task_type": "benchmark",
        "source": "public-fixture",
        "source_id": case_id,
        "tags": ["minimum-change", "deterministic"],
    }


def assessment(selected: str) -> dict[str, Any]:
    selected_index = RUNG_IDS.index(selected)
    rows: dict[str, dict[str, Any]] = {}
    for index, rung_id in enumerate(RUNG_IDS):
        if index < selected_index:
            rows[rung_id] = {
                "decision": "rejected",
                "reason": "The fixture supplies evidence that this rung cannot satisfy acceptance.",
                "evidence_refs": [f"fixture:{rung_id}"],
            }
        elif index == selected_index:
            rows[rung_id] = {
                "decision": "selected",
                "reason": "The fixture supplies sufficient evidence for this first viable rung.",
                "evidence_refs": [f"fixture:selected:{rung_id}"],
            }
        else:
            rows[rung_id] = {"decision": "unassessed", "reason": "", "evidence_refs": []}
    return {
        "selected_rung": selected,
        "rung_assessments": rows,
        "acceptance_criteria_preserved": True,
        "controls_preserved": list(NON_NEGOTIABLE_CONTROLS),
        "rejected_alternatives": [],
        "estimated_change_surface": {
            "mutation_required": selected != "necessity",
            "files": 0 if selected == "necessity" else 1,
        },
        "dependency_service_schema_agent_delta": {key: [] for key in ZERO_DEFAULT_BUDGETS},
        "budget_exceptions": {},
        "verification_plan": ["python -m unittest"],
        "remaining_uncertainty": [],
    }


CASES: tuple[tuple[str, str], ...] = (
    ("already-fixed", "necessity"),
    ("duplicate-request", "necessity"),
    ("cmdb-existing-export", "existing-capability"),
    ("chatbot-existing-tool", "existing-capability"),
    ("csv-standard-library", "standard-library"),
    ("hash-standard-library", "standard-library"),
    ("keycloak-native-mfa", "native-platform"),
    ("postgres-native-constraint", "native-platform"),
    ("approved-openpyxl", "existing-dependency"),
    ("existing-broker-client", "existing-dependency"),
    ("single-policy-change", "minimal-local-change"),
    ("new-bounded-adapter", "minimum-new-code"),
)


def evaluate() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case_id, expected in CASES:
        contract = compile_contract(task(case_id))
        candidate = assessment(expected)
        if expected == "minimum-new-code":
            candidate["dependency_service_schema_agent_delta"]["new_abstraction_layers"] = [
                "bounded-provider-adapter"
            ]
            candidate["budget_exceptions"] = {
                "new_abstraction_layers": {
                    "reason": "All earlier rungs are evidence-rejected.",
                    "evidence_refs": ["fixture:architecture-review"],
                    "acceptance_refs": ["AC-1"],
                }
            }
        result = assess_strategy(contract, candidate)
        results.append(
            {
                "case_id": case_id,
                "expected_rung": expected,
                "selected_rung": result.get("selected_rung"),
                "decision": result["decision"],
                "errors": result["errors"],
            }
        )

    negative = assessment("standard-library")
    negative["rung_assessments"]["necessity"] = {
        "decision": "unassessed",
        "reason": "",
        "evidence_refs": [],
    }
    negative_result = assess_strategy(compile_contract(task("unknown-is-not-rejection")), negative)
    expected_negative = (
        negative_result["decision"] == "needs-work"
        and "earlier-rung-not-rejected:necessity" in negative_result["errors"]
    )
    passed = all(
        row["decision"] == "pass" and row["selected_rung"] == row["expected_rung"]
        for row in results
    ) and expected_negative
    return {
        "schema": "iot-ai.minimum-change-benchmark.v1",
        "decision": "pass" if passed else "block",
        "positive_cases": results,
        "positive_passed": sum(row["decision"] == "pass" for row in results),
        "positive_total": len(results),
        "negative_unknown_is_not_rejection": {
            "decision": negative_result["decision"],
            "errors": negative_result["errors"],
            "expected": expected_negative,
        },
        "provider_calls": 0,
        "savings_claim": "not-measured",
        "production_claim": False,
    }


if __name__ == "__main__":
    payload = evaluate()
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(0 if payload["decision"] == "pass" else 1)
