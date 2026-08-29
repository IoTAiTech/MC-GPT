# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 3.0.0 | Date: 2026-08-30
"""Third-pass mutation-complete and malformed-shape hardening for PR 14."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "tools/_pr14_deep_hardening_once_v2_20260830.py"


def bootstrap() -> None:
    if V2.is_file():
        subprocess.run([sys.executable, str(V2)], cwd=ROOT, check=True)


def add_shape_and_partial_exception_tests() -> None:
    path = ROOT / "tests/test_minimum_change_deep.py"
    text = path.read_text(encoding="utf-8")
    marker = "class AssessmentMalformedShapeMatrixTests(unittest.TestCase):"
    if marker in text:
        return
    insertion = r'''

class AssessmentMalformedShapeMatrixTests(unittest.TestCase):
    def evaluate(self, assessment: dict[str, object]) -> dict:
        return assess_strategy(compile_contract(task(31)), assessment)

    def test_partial_budget_exception_is_not_sufficient(self) -> None:
        contract = compile_contract(task(32))
        assessment = passing_assessment("minimum-new-code")
        assessment["dependency_service_schema_agent_delta"]["new_dependencies"] = [
            "new-package"
        ]
        assessment["budget_exceptions"] = {
            "new_dependencies": {
                "reason": "Only a reason is present.",
                "evidence_refs": [],
                "acceptance_refs": [],
            }
        }
        result = assess_strategy(contract, assessment)
        self.assertIn("budget-exception:new_dependencies", result["errors"])

    def test_non_mapping_rung_row_is_rejected(self) -> None:
        assessment = passing_assessment()
        assessment["rung_assessments"]["necessity"] = []
        result = self.evaluate(assessment)
        self.assertIn("earlier-rung-not-rejected:necessity", result["errors"])

    def test_non_mapping_delta_is_rejected(self) -> None:
        assessment = passing_assessment()
        assessment["dependency_service_schema_agent_delta"] = "invalid"
        result = self.evaluate(assessment)
        self.assertIn("delta-type", result["errors"])

    def test_non_mapping_budget_exceptions_are_rejected(self) -> None:
        assessment = passing_assessment()
        assessment["budget_exceptions"] = "invalid"
        result = self.evaluate(assessment)
        self.assertIn("budget-exceptions-type", result["errors"])

    def test_non_mapping_budget_exception_row_is_rejected(self) -> None:
        contract = compile_contract(task(33))
        assessment = passing_assessment("minimum-new-code")
        assessment["dependency_service_schema_agent_delta"]["new_dependencies"] = [
            "new-package"
        ]
        assessment["budget_exceptions"] = {"new_dependencies": "invalid"}
        result = assess_strategy(contract, assessment)
        self.assertIn("budget-exception:new_dependencies", result["errors"])

    def test_non_sequence_rejected_alternatives_is_rejected(self) -> None:
        assessment = passing_assessment()
        assessment["rejected_alternatives"] = "invalid"
        result = self.evaluate(assessment)
        self.assertIn("rejected-alternatives", result["errors"])

    def test_non_mapping_change_surface_is_rejected(self) -> None:
        assessment = passing_assessment()
        assessment["estimated_change_surface"] = "invalid"
        result = self.evaluate(assessment)
        self.assertIn("estimated-change-surface", result["errors"])

    def test_non_sequence_uncertainty_is_rejected(self) -> None:
        assessment = passing_assessment()
        assessment["remaining_uncertainty"] = "invalid"
        result = self.evaluate(assessment)
        self.assertIn("remaining-uncertainty", result["errors"])

    def test_string_tags_are_canonicalised(self) -> None:
        value = task(34)
        value["tags"] = "alpha,beta, alpha"
        contract = compile_contract(value)
        self.assertEqual(contract["task"]["tags"], ["alpha", "beta"])

    def test_missing_task_identity_is_rejected(self) -> None:
        value = task(35)
        value["id"] = ""
        with self.assertRaises(ValueError):
            compile_contract(value)
        value = task(36)
        value["title"] = ""
        with self.assertRaises(ValueError):
            compile_contract(value)

    def test_critical_and_low_risk_modes_are_deterministic(self) -> None:
        critical = task(37)
        critical["risk_class"] = "R3"
        self.assertEqual(
            compile_contract(critical)["mode"],
            "required-with-independent-review",
        )
        low = task(38)
        low["risk_class"] = "R1"
        low["priority"] = "normal"
        self.assertEqual(compile_contract(low)["mode"], "advisory-evidence")

    def test_needless_source_addition_is_recorded_in_receipt(self) -> None:
        contract, assessed = passing_result(39, "necessity")
        receipt = build_receipt(
            contract,
            assessed,
            change_metrics={
                "source_lines_added": 1,
                "tokens": 1,
                "cost": 1,
                "wall_clock_seconds": 1,
            },
            verification={
                "acceptance_coverage_complete": True,
                "post_change_tests_passed": True,
                "security_privacy_controls_passed": True,
                "independent_review_passed": True,
            },
        )
        self.assertEqual(receipt["decision"], "needs-work")
        self.assertIn("no-change-rung-has-source-additions", receipt["errors"])
        self.assertEqual(validate_receipt(receipt)["decision"], "pass")
'''
    needle = "\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
    if needle not in text:
        raise RuntimeError("deep test footer not found")
    path.write_text(text.replace(needle, insertion + needle, 1), encoding="utf-8")


def create_v3_mutation_tool() -> None:
    path = ROOT / "tools/_pr14_curated_mutation_once_v3_20260830.py"
    content = r'''# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 3.0.0 | Date: 2026-08-30
"""Curated critical-control mutation suite for PR 14 v3."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/iot_ai/minimum_change.py").read_text(encoding="utf-8")
MUTANTS = [
    (
        "canonical-contract-bypass",
        '            if unsigned != expected_unsigned:\n                errors.append("canonical-contract")',
        '            if False and unsigned != expected_unsigned:\n                errors.append("canonical-contract")',
        "tests/test_minimum_change_deep.py::CanonicalContractSecurityTests::test_resigned_contract_with_unknown_top_level_field_is_rejected",
    ),
    (
        "control-preservation-bypass",
        '    errors.extend(f"control:{item}" for item in NON_NEGOTIABLE_CONTROLS if item not in controls)',
        "    errors.extend(())",
        "tests/test_minimum_change.py::MinimumChangeContractTests::test_missing_control_or_verification_blocks_assessment",
    ),
    (
        "partial-budget-exception-bypass",
        '        if not all(exception.values()):\n            errors.append(f"budget-exception:{key}")',
        '        if not any(exception.values()):\n            errors.append(f"budget-exception:{key}")',
        "tests/test_minimum_change_deep.py::AssessmentMalformedShapeMatrixTests::test_partial_budget_exception_is_not_sufficient",
    ),
    (
        "necessity-mutation-bypass",
        '    if selected == "necessity" and change_surface.get("mutation_required") is not False:\n        errors.append("necessity-rung-must-be-no-mutation")',
        '    if False and selected == "necessity" and change_surface.get("mutation_required") is not False:\n        errors.append("necessity-rung-must-be-no-mutation")',
        "tests/test_minimum_change.py::MinimumChangeContractTests::test_necessity_rung_requires_explicit_no_mutation",
    ),
    (
        "receipt-field-bypass",
        '    if set(receipt) != set(_RECEIPT_FIELDS):\n        errors.append("receipt-fields")',
        '    if False and set(receipt) != set(_RECEIPT_FIELDS):\n        errors.append("receipt-fields")',
        "tests/test_minimum_change_deep.py::ReceiptSecurityTests::test_resigned_receipt_with_unknown_field_is_rejected",
    ),
    (
        "receipt-rung-bypass",
        '    if receipt.get("selected_rung") not in _RUNG_IDS:\n        errors.append("selected-rung")',
        '    if False and receipt.get("selected_rung") not in _RUNG_IDS:\n        errors.append("selected-rung")',
        "tests/test_minimum_change_deep.py::ReceiptSecurityTests::test_resigned_receipt_with_invalid_rung_is_rejected",
    ),
    (
        "savings-consistency-bypass",
        '    if savings is not expected_savings:\n        errors.append("savings-consistency")',
        '    if False and savings is not expected_savings:\n        errors.append("savings-consistency")',
        "tests/test_minimum_change_deep.py::ReceiptSecurityTests::test_resigned_receipt_with_false_savings_is_rejected",
    ),
]


def main() -> int:
    rows = []
    killed = 0
    with tempfile.TemporaryDirectory(prefix="mcgpt-mutants-v3-") as temporary:
        temp = Path(temporary)
        for name, old, new, test_node in MUTANTS:
            count = SOURCE.count(old)
            if count != 1:
                raise RuntimeError(f"{name}: expected one target, found {count}")
            package_root = temp / name / "src"
            shutil.copytree(ROOT / "src/iot_ai", package_root / "iot_ai")
            target = package_root / "iot_ai/minimum_change.py"
            target.write_text(SOURCE.replace(old, new, 1), encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(package_root)
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", test_node],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=120,
                check=False,
            )
            is_killed = completed.returncode != 0
            killed += int(is_killed)
            rows.append({
                "name": name,
                "test": test_node,
                "killed": is_killed,
                "exit_code": completed.returncode,
                "tail": completed.stdout[-1200:],
            })
    report = {
        "schema": "iot-ai.curated-mutation-report.v3",
        "scope": "curated-critical-controls-not-exhaustive-mutation-analysis",
        "mutants": rows,
        "killed": killed,
        "total": len(MUTANTS),
        "score_percent": round(killed / len(MUTANTS) * 100.0, 2),
        "decision": "pass" if killed == len(MUTANTS) else "block",
    }
    out = ROOT / "evidence/pr14-deep-validation/curated-mutation-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''
    path.write_text(content, encoding="utf-8")


def main() -> int:
    bootstrap()
    add_shape_and_partial_exception_tests()
    create_v3_mutation_tool()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
