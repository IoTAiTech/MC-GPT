# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 2.0.0 | Date: 2026-08-30
"""Idempotent second-pass hardening and deep-test completion for PR 14."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "tools/_pr14_deep_hardening_once_20260830.py"


def run_v1_if_present() -> None:
    if V1.is_file():
        subprocess.run([sys.executable, str(V1)], cwd=ROOT, check=True)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def harden_nonfinite_contract_handling() -> None:
    path = ROOT / "src/iot_ai/minimum_change.py"
    text = path.read_text(encoding="utf-8")
    old = '''    if not isinstance(task, Mapping):
        errors.append("task")
        task = {}
    elif contract.get("task_sha256") != _digest(dict(task)):
        errors.append("task-digest")
'''
    new = '''    if not isinstance(task, Mapping):
        errors.append("task")
        task = {}
    else:
        try:
            expected_task_digest = _digest(dict(task))
        except (TypeError, ValueError):
            expected_task_digest = None
            errors.append("canonical-json")
        if contract.get("task_sha256") != expected_task_digest:
            errors.append("task-digest")
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "expected_task_digest" not in text:
        raise RuntimeError("non-finite task digest hardening target not recognised")
    path.write_text(text, encoding="utf-8")


def complete_deep_tests() -> None:
    path = ROOT / "tests/test_minimum_change_deep.py"
    text = path.read_text(encoding="utf-8")
    marker = "class ReceiptValidationMatrixTests(unittest.TestCase):"
    if marker in text:
        return
    insertion = r'''

class ReceiptValidationMatrixTests(unittest.TestCase):
    def valid(self) -> dict:
        return ReceiptSecurityTests().receipt()

    def tamper(self, **changes: object) -> dict:
        receipt = self.valid()
        receipt.update(changes)
        return resign(receipt, "receipt_sha256")

    def test_non_mapping_receipt_fails_closed(self) -> None:
        result = validate_receipt([])  # type: ignore[arg-type]
        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["errors"], ["receipt-type"])

    def test_invalid_schema_is_rejected_after_resigning(self) -> None:
        result = validate_receipt(self.tamper(schema="invalid"))
        self.assertIn("schema", result["errors"])

    def test_invalid_decision_is_rejected_after_resigning(self) -> None:
        result = validate_receipt(self.tamper(decision="approve"))
        self.assertIn("decision", result["errors"])
        self.assertIn("decision-consistency", result["errors"])

    def test_invalid_contract_and_assessment_digests_are_rejected(self) -> None:
        result = validate_receipt(
            self.tamper(contract_sha256="x", assessment_sha256="y")
        )
        self.assertIn("contract_sha256", result["errors"])
        self.assertIn("assessment_sha256", result["errors"])

    def test_invalid_metric_shape_is_rejected(self) -> None:
        receipt = self.valid()
        receipt["change_metrics"].pop("tokens")
        result = validate_receipt(resign(receipt, "receipt_sha256"))
        self.assertIn("change-metrics", result["errors"])

    def test_invalid_metric_value_is_rejected(self) -> None:
        receipt = self.valid()
        receipt["change_metrics"]["tokens"] = -1
        result = validate_receipt(resign(receipt, "receipt_sha256"))
        self.assertIn("change-metric-values", result["errors"])

    def test_invalid_verification_shape_is_rejected(self) -> None:
        receipt = self.valid()
        receipt["verification"].pop("independent_review_passed")
        result = validate_receipt(resign(receipt, "receipt_sha256"))
        self.assertIn("verification", result["errors"])

    def test_invalid_verification_value_is_rejected(self) -> None:
        receipt = self.valid()
        receipt["verification"]["independent_review_passed"] = 1
        result = validate_receipt(resign(receipt, "receipt_sha256"))
        self.assertIn("verification-values", result["errors"])

    def test_non_boolean_claim_flags_are_rejected(self) -> None:
        result = validate_receipt(
            self.tamper(
                comparable_baseline_supplied=1,
                savings_claim_allowed="yes",
            )
        )
        self.assertIn("comparable-baseline", result["errors"])
        self.assertIn("savings-claim", result["errors"])

    def test_production_claim_true_is_rejected(self) -> None:
        result = validate_receipt(self.tamper(production_claim=True))
        self.assertIn("production-claim", result["errors"])

    def test_invalid_errors_collection_is_rejected(self) -> None:
        result = validate_receipt(self.tamper(errors="none"))
        self.assertIn("errors", result["errors"])

    def test_decision_must_match_error_collection(self) -> None:
        receipt = self.valid()
        receipt["errors"] = ["verification-failed"]
        receipt["decision"] = "pass"
        result = validate_receipt(resign(receipt, "receipt_sha256"))
        self.assertIn("decision-consistency", result["errors"])

    def test_relative_deltas_without_comparable_baseline_are_rejected(self) -> None:
        result = validate_receipt(
            self.tamper(
                relative_deltas_percent={key: 0.0 for key in (
                    "source_lines_added", "tokens", "cost", "wall_clock_seconds"
                )}
            )
        )
        self.assertIn("relative-deltas-without-baseline", result["errors"])

    def test_bad_relative_delta_shape_is_rejected(self) -> None:
        contract, assessed = passing_result(15)
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
            baseline={
                "source_lines_added": 2,
                "tokens": 2,
                "cost": 2,
                "wall_clock_seconds": 2,
            },
        )
        receipt["relative_deltas_percent"].pop("tokens")
        result = validate_receipt(resign(receipt, "receipt_sha256"))
        self.assertIn("relative-deltas", result["errors"])

    def test_non_finite_relative_delta_fails_canonical_json(self) -> None:
        contract, assessed = passing_result(16)
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
            baseline={
                "source_lines_added": 2,
                "tokens": 2,
                "cost": 2,
                "wall_clock_seconds": 2,
            },
        )
        receipt["relative_deltas_percent"]["tokens"] = math.nan
        result = validate_receipt(receipt)
        self.assertIn("relative-delta-values", result["errors"])
        self.assertIn("canonical-json", result["errors"])


class ReceiptBuilderInputValidationTests(unittest.TestCase):
    def inputs(self) -> tuple[dict, dict, dict, dict]:
        contract, assessed = passing_result(17)
        metrics = {
            "source_lines_added": 1,
            "tokens": 1,
            "cost": 1,
            "wall_clock_seconds": 1,
        }
        verification = {
            "acceptance_coverage_complete": True,
            "post_change_tests_passed": True,
            "security_privacy_controls_passed": True,
            "independent_review_passed": True,
        }
        return contract, assessed, metrics, verification

    def test_invalid_contract_is_rejected(self) -> None:
        contract, assessed, metrics, verification = self.inputs()
        contract["contract_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            build_receipt(
                contract,
                assessed,
                change_metrics=metrics,
                verification=verification,
            )

    def test_non_mapping_assessment_is_rejected(self) -> None:
        contract, _, metrics, verification = self.inputs()
        with self.assertRaises(TypeError):
            build_receipt(
                contract,
                [],  # type: ignore[arg-type]
                change_metrics=metrics,
                verification=verification,
            )

    def test_invalid_assessment_schema_digest_and_rung_are_rejected(self) -> None:
        contract, assessed, metrics, verification = self.inputs()
        for field, value in (
            ("schema", "bad"),
            ("assessment_sha256", "bad"),
            ("selected_rung", "bad"),
        ):
            candidate = copy.deepcopy(assessed)
            candidate[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_receipt(
                    contract,
                    candidate,
                    change_metrics=metrics,
                    verification=verification,
                )

    def test_metric_mapping_and_key_shape_are_enforced(self) -> None:
        contract, assessed, metrics, verification = self.inputs()
        with self.assertRaises(TypeError):
            build_receipt(
                contract,
                assessed,
                change_metrics=[],  # type: ignore[arg-type]
                verification=verification,
            )
        metrics.pop("tokens")
        with self.assertRaises(ValueError):
            build_receipt(
                contract,
                assessed,
                change_metrics=metrics,
                verification=verification,
            )

    def test_verification_mapping_key_shape_and_boolean_values_are_enforced(self) -> None:
        contract, assessed, metrics, verification = self.inputs()
        with self.assertRaises(TypeError):
            build_receipt(
                contract,
                assessed,
                change_metrics=metrics,
                verification=[],  # type: ignore[arg-type]
            )
        verification.pop("independent_review_passed")
        with self.assertRaises(ValueError):
            build_receipt(
                contract,
                assessed,
                change_metrics=metrics,
                verification=verification,
            )
        verification["independent_review_passed"] = 1
        with self.assertRaises(ValueError):
            build_receipt(
                contract,
                assessed,
                change_metrics=metrics,
                verification=verification,
            )

    def test_baseline_mapping_and_key_shape_are_enforced(self) -> None:
        contract, assessed, metrics, verification = self.inputs()
        with self.assertRaises(TypeError):
            build_receipt(
                contract,
                assessed,
                change_metrics=metrics,
                verification=verification,
                baseline=[],  # type: ignore[arg-type]
            )
        with self.assertRaises(ValueError):
            build_receipt(
                contract,
                assessed,
                change_metrics=metrics,
                verification=verification,
                baseline={"tokens": 1},
            )

    def test_non_positive_baseline_is_valid_but_not_comparable(self) -> None:
        contract, assessed, metrics, verification = self.inputs()
        receipt = build_receipt(
            contract,
            assessed,
            change_metrics=metrics,
            verification=verification,
            baseline={
                "source_lines_added": 0,
                "tokens": 1,
                "cost": 1,
                "wall_clock_seconds": 1,
            },
        )
        self.assertFalse(receipt["comparable_baseline_supplied"])
        self.assertFalse(receipt["savings_claim_allowed"])


class ContractNonFiniteValidationTests(unittest.TestCase):
    def test_non_finite_nested_value_blocks_without_raising(self) -> None:
        contract = compile_contract(task())
        contract["task"]["revision"] = math.nan
        contract["task_sha256"] = "0" * 64
        contract["contract_sha256"] = "0" * 64
        result = validate_contract(contract)
        self.assertEqual(result["decision"], "block")
        self.assertIn("canonical-json", result["errors"])
        self.assertIn("task-digest", result["errors"])
'''
    needle = "\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
    if needle not in text:
        raise RuntimeError("deep test footer not found")
    text = text.replace(needle, insertion + needle, 1)
    path.write_text(text, encoding="utf-8")


def overwrite_mutation_tool() -> None:
    path = ROOT / "tools/_pr14_curated_mutation_once_v2_20260830.py"
    content = r'''# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 2.0.0 | Date: 2026-08-30
"""Curated critical-control mutation suite for PR 14."""
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
        "budget-exception-bypass",
        '        if not all(exception.values()):\n            errors.append(f"budget-exception:{key}")',
        '        if not any(exception.values()):\n            errors.append(f"budget-exception:{key}")',
        "tests/test_minimum_change.py::MinimumChangeContractTests::test_minimum_new_code_requires_bound_budget_exception",
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
    report = {"schema": "iot-ai.curated-mutation-report.v2", "mutants": []}
    killed = 0
    with tempfile.TemporaryDirectory(prefix="mcgpt-mutants-") as temporary:
        temp = Path(temporary)
        for name, old, new, test_node in MUTANTS:
            count = SOURCE.count(old)
            if count != 1:
                raise RuntimeError(f"{name}: expected one mutation target, found {count}")
            package_root = temp / name / "src"
            shutil.copytree(ROOT / "src/iot_ai", package_root / "iot_ai")
            mutant_path = package_root / "iot_ai/minimum_change.py"
            mutant_path.write_text(SOURCE.replace(old, new, 1), encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(package_root)
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", test_node],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                timeout=120,
            )
            was_killed = completed.returncode != 0
            killed += int(was_killed)
            report["mutants"].append({
                "name": name,
                "test": test_node,
                "killed": was_killed,
                "exit_code": completed.returncode,
                "tail": completed.stdout[-1200:],
            })
    report.update({
        "killed": killed,
        "total": len(MUTANTS),
        "score_percent": round(killed / len(MUTANTS) * 100.0, 2),
        "decision": "pass" if killed == len(MUTANTS) else "block",
        "scope": "curated-critical-controls-not-exhaustive-mutation-analysis",
    })
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
    run_v1_if_present()
    harden_nonfinite_contract_handling()
    complete_deep_tests()
    overwrite_mutation_tool()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
