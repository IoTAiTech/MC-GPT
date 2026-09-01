# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-29
from __future__ import annotations

import copy
import unittest

from iot_ai.minimum_change import (
    NON_NEGOTIABLE_CONTROLS,
    REUSE_FIRST_RUNG_IDS,
    RUNG_DEFINITIONS,
    ZERO_DEFAULT_BUDGETS,
    assess_strategy,
    build_receipt,
    compile_contract,
    render_prompt,
    reuse_first_precheck,
    validate_contract,
)


def task(*, risk: str = "R2", acceptance: object = "Tests pass.") -> dict[str, object]:
    return {
        "id": "task-demo",
        "revision": 7,
        "title": "Add an export path",
        "description": "Export current inventory as CSV without changing ownership boundaries.",
        "acceptance_criteria": acceptance,
        "risk_class": risk,
        "priority": "high",
        "task_type": "implementation",
        "source": "pmd",
        "source_id": "req-1",
        "tags": ["cmdb", "export"],
    }


def passing_assessment(selected: str = "standard-library") -> dict[str, object]:
    rows: dict[str, dict[str, object]] = {}
    selected_index = [item["id"] for item in RUNG_DEFINITIONS].index(selected)
    for index, item in enumerate(RUNG_DEFINITIONS):
        rung_id = item["id"]
        if index < selected_index:
            rows[rung_id] = {
                "decision": "rejected",
                "reason": f"Current evidence rejects {rung_id}.",
                "evidence_refs": [f"evidence:{rung_id}"],
            }
        elif index == selected_index:
            rows[rung_id] = {
                "decision": "selected",
                "reason": "This is the first sufficient rung.",
                "evidence_refs": ["evidence:selected"],
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
            "files": 0 if selected == "necessity" else 1,
            "mutation_required": selected != "necessity",
        },
        "dependency_service_schema_agent_delta": {key: [] for key in ZERO_DEFAULT_BUDGETS},
        "budget_exceptions": {},
        "verification_plan": ["python -m unittest"],
        "remaining_uncertainty": [],
    }


class MinimumChangeContractTests(unittest.TestCase):
    def test_contract_is_deterministic_and_task_context_bound(self) -> None:
        context = {"sha256": "a" * 64}
        first = compile_contract(task(), context_manifest=context)
        second = compile_contract(task(), context_manifest=context)
        self.assertEqual(first, second)
        self.assertEqual(validate_contract(first)["decision"], "pass")
        changed = compile_contract({**task(), "revision": 8}, context_manifest=context)
        self.assertNotEqual(first["contract_sha256"], changed["contract_sha256"])
        self.assertEqual(first["context_manifest_sha256"], "a" * 64)

    def test_reuse_first_precheck_is_the_yagni_fold(self) -> None:
        contract = compile_contract(task(), context_manifest={"sha256": "a" * 64})
        self.assertEqual(validate_contract(contract)["decision"], "pass")
        precheck = reuse_first_precheck()
        self.assertEqual(precheck["function"], "reuse_first_precheck")
        self.assertEqual(precheck["component"], "native_mncg")
        self.assertEqual(tuple(precheck["rung_ids"]), REUSE_FIRST_RUNG_IDS)
        self.assertEqual(contract["reuse_first_precheck"], precheck)
        self.assertEqual(REUSE_FIRST_RUNG_IDS, tuple(item["id"] for item in RUNG_DEFINITIONS[:5]))
        self.assertIn("Reuse-first / YAGNI precheck", render_prompt(contract))

    def test_acceptance_list_is_preserved_as_text(self) -> None:
        contract = compile_contract(task(acceptance=["A passes", "B passes"]))
        self.assertEqual(contract["task"]["acceptance_criteria"], "A passes\nB passes")

    def test_contract_preserves_order_zero_budgets_and_safety_controls(self) -> None:
        contract = compile_contract(task())
        self.assertEqual(
            [item["id"] for item in contract["rungs"]],
            [item["id"] for item in RUNG_DEFINITIONS],
        )
        self.assertEqual(contract["default_budgets"], ZERO_DEFAULT_BUDGETS)
        self.assertEqual(tuple(contract["non_negotiable_controls"]), NON_NEGOTIABLE_CONTROLS)
        self.assertFalse(contract["claim_boundary"]["production_claim"])

    def test_missing_acceptance_fails_closed(self) -> None:
        contract = compile_contract(task(acceptance=""))
        self.assertEqual(validate_contract(contract)["decision"], "pass")
        self.assertFalse(contract["authority_precondition"]["acceptance_criteria_supplied"])
        self.assertEqual(
            contract["authority_precondition"]["missing_acceptance_decision"],
            "block-execution",
        )
        result = assess_strategy(contract, passing_assessment())
        self.assertEqual(result["decision"], "needs-work")
        self.assertIn("authoritative-acceptance-missing", result["errors"])

    def test_invalid_context_digest_is_rejected(self) -> None:
        contract = compile_contract(task(), context_manifest={"sha256": "invalid"})
        self.assertIn("context-digest", validate_contract(contract)["errors"])

    def test_tamper_is_detected_at_nested_and_outer_bindings(self) -> None:
        contract = compile_contract(task())
        tampered = copy.deepcopy(contract)
        tampered["task"]["revision"] = 9
        check = validate_contract(tampered)
        self.assertEqual(check["decision"], "block")
        self.assertIn("task-digest", check["errors"])
        self.assertIn("task-revision-binding", check["errors"])
        self.assertIn("digest", check["errors"])

    def test_prompt_is_compact_provider_neutral_and_claim_conservative(self) -> None:
        text = render_prompt(compile_contract(task()))
        self.assertIn("MINIMUM NECESSARY CHANGE CONTRACT", text)
        self.assertIn("Earlier rungs may be rejected only with evidence", text)
        self.assertIn("smaller is not proof of correctness", text)
        self.assertNotIn("Ponytail", text)

    def test_assessment_selects_first_evidenced_rung(self) -> None:
        contract = compile_contract(task())
        result = assess_strategy(contract, passing_assessment("standard-library"))
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(result["selected_rung"], "standard-library")
        self.assertRegex(result["assessment_sha256"], r"^[0-9a-f]{64}$")

    def test_necessity_rung_requires_explicit_no_mutation(self) -> None:
        contract = compile_contract(task())
        assessment = passing_assessment("necessity")
        assessment["estimated_change_surface"]["mutation_required"] = True
        result = assess_strategy(contract, assessment)
        self.assertIn("necessity-rung-must-be-no-mutation", result["errors"])

    def test_unknown_earlier_rung_is_not_treated_as_rejection(self) -> None:
        contract = compile_contract(task())
        assessment = passing_assessment("standard-library")
        assessment["rung_assessments"]["necessity"] = {
            "decision": "unassessed",
            "reason": "",
            "evidence_refs": [],
        }
        result = assess_strategy(contract, assessment)
        self.assertEqual(result["decision"], "needs-work")
        self.assertIn("earlier-rung-not-rejected:necessity", result["errors"])

    def test_non_code_rung_cannot_smuggle_a_new_dependency(self) -> None:
        contract = compile_contract(task())
        assessment = passing_assessment("standard-library")
        assessment["dependency_service_schema_agent_delta"]["new_dependencies"] = ["third-party-csv"]
        result = assess_strategy(contract, assessment)
        self.assertIn("unexpected-new_dependencies", result["errors"])
        self.assertIn("budget-exception:new_dependencies", result["errors"])

    def test_minimum_new_code_requires_bound_budget_exception(self) -> None:
        contract = compile_contract(task())
        assessment = passing_assessment("minimum-new-code")
        assessment["dependency_service_schema_agent_delta"]["new_dependencies"] = ["new-package"]
        blocked = assess_strategy(contract, assessment)
        self.assertIn("budget-exception:new_dependencies", blocked["errors"])
        assessment["budget_exceptions"] = {
            "new_dependencies": {
                "reason": "No approved capability meets the signed export criterion.",
                "evidence_refs": ["evidence:dependency-review"],
                "acceptance_refs": ["AC-2"],
            }
        }
        self.assertEqual(assess_strategy(contract, assessment)["decision"], "pass")

    def test_missing_control_or_verification_blocks_assessment(self) -> None:
        contract = compile_contract(task())
        assessment = passing_assessment("existing-capability")
        assessment["controls_preserved"].remove("security-privacy-and-secret-handling")
        assessment["verification_plan"] = []
        result = assess_strategy(contract, assessment)
        self.assertIn("control:security-privacy-and-secret-handling", result["errors"])
        self.assertIn("verification-plan", result["errors"])

    def test_receipt_forbids_savings_claim_without_comparable_baseline(self) -> None:
        contract = compile_contract(task())
        assessed = assess_strategy(contract, passing_assessment("standard-library"))
        receipt = build_receipt(
            contract,
            assessed,
            change_metrics={
                "source_lines_added": 12,
                "tokens": 1000,
                "cost": 0.02,
                "wall_clock_seconds": 7,
            },
            verification={
                "acceptance_coverage_complete": True,
                "post_change_tests_passed": True,
                "security_privacy_controls_passed": True,
                "independent_review_passed": True,
            },
        )
        self.assertEqual(receipt["decision"], "pass")
        self.assertFalse(receipt["savings_claim_allowed"])
        self.assertIsNone(receipt["relative_deltas_percent"])
        self.assertFalse(receipt["production_claim"])

    def test_receipt_computes_deltas_only_after_all_hard_gates_pass(self) -> None:
        contract = compile_contract(task())
        assessed = assess_strategy(contract, passing_assessment("standard-library"))
        metrics = {
            "source_lines_added": 50,
            "tokens": 800,
            "cost": 0.08,
            "wall_clock_seconds": 40,
        }
        baseline = {
            "source_lines_added": 100,
            "tokens": 1000,
            "cost": 0.10,
            "wall_clock_seconds": 50,
        }
        verification = {
            "acceptance_coverage_complete": True,
            "post_change_tests_passed": True,
            "security_privacy_controls_passed": True,
            "independent_review_passed": True,
        }
        receipt = build_receipt(
            contract,
            assessed,
            change_metrics=metrics,
            verification=verification,
            baseline=baseline,
        )
        self.assertTrue(receipt["savings_claim_allowed"])
        self.assertEqual(receipt["relative_deltas_percent"]["source_lines_added"], -50.0)
        blocked = build_receipt(
            contract,
            assessed,
            change_metrics=metrics,
            verification={**verification, "security_privacy_controls_passed": False},
            baseline=baseline,
        )
        self.assertFalse(blocked["savings_claim_allowed"])
        self.assertEqual(blocked["decision"], "needs-work")

    def test_receipt_rejects_assessment_from_another_contract(self) -> None:
        first = compile_contract(task())
        second = compile_contract({**task(), "revision": 8})
        assessed = assess_strategy(first, passing_assessment())
        receipt = build_receipt(
            second,
            assessed,
            change_metrics={key: 1 for key in ("source_lines_added", "tokens", "cost", "wall_clock_seconds")},
            verification={
                "acceptance_coverage_complete": True,
                "post_change_tests_passed": True,
                "security_privacy_controls_passed": True,
                "independent_review_passed": True,
            },
        )
        self.assertIn("assessment-contract-binding", receipt["errors"])


if __name__ == "__main__":
    unittest.main()
