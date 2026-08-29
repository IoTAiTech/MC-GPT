# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-30
"""One-time, fail-closed hardening script for PR 14.

This file is removed by the validation workflow after all deep gates pass.
It never merges, releases, deploys, or mutates PMD/runtime state.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def fix_public_contract_test() -> None:
    path = "tests/test_minimum_change_contract.py"
    text = read(path)
    text = text.replace("dependencies=(),", "depends_on=(),")
    text = text.replace("            forbidden_actions=role.forbidden_actions,\n", "")
    old = """        with self.assertRaises(ValueError):
            _validate_output(node, payload)
"""
    new = """        result = _validate_output(node, {\"status\": \"pass\", \"output\": payload})
        self.assertEqual(result[\"status\"], \"failed\")
        self.assertEqual(result[\"failure_class\"], \"missing-output-fields\")
        self.assertIn(\"minimum_change_assessment\", result[\"missing_output_fields\"])
"""
    if old in text:
        text = text.replace(old, new, 1)
    elif "result = _validate_output(node" not in text:
        raise RuntimeError("public contract test: output-validation assertion shape not recognised")
    text = text.replace(
        'self.assertIn("does not copy Ponytail source code", gate)',
        'self.assertIn("No Ponytail source code is copied into MC-GPT", gate)',
    )
    write(path, text)


def fix_brand_identity() -> None:
    path = "docs/research/ponytail-assessment.md"
    text = read(path)
    text = text.replace("AI-IoT.Tech", "IoT-AI.Tech")
    write(path, text)


def harden_minimum_change() -> None:
    path = "src/iot_ai/minimum_change.py"
    text = read(path)
    text = text.replace(
        "# Version: 1.0.0 | Date: 2026-08-29",
        "# Version: 1.1.0 | Date: 2026-08-30",
        1,
    )
    text = replace_once(
        text,
        'return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)',
        'return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)',
        label="canonical-json",
    )
    text = replace_once(
        text,
        "    elif isinstance(value, Sequence):\n        values = value\n",
        "    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):\n        values = value\n",
        label="byte-sequence-rejection",
    )
    marker = ")\n\nNON_NEGOTIABLE_CONTROLS: tuple[str, ...] = ("
    insertion = ")\n\n_RUNG_IDS: tuple[str, ...] = tuple(str(item[\"id\"]) for item in RUNG_DEFINITIONS)\n_RECEIPT_FIELDS: frozenset[str] = frozenset({\n    \"schema\",\n    \"decision\",\n    \"contract_sha256\",\n    \"assessment_sha256\",\n    \"selected_rung\",\n    \"change_metrics\",\n    \"verification\",\n    \"comparable_baseline_supplied\",\n    \"relative_deltas_percent\",\n    \"savings_claim_allowed\",\n    \"errors\",\n    \"production_claim\",\n    \"receipt_sha256\",\n})\n_VERIFICATION_KEYS: tuple[str, ...] = (\n    \"acceptance_coverage_complete\",\n    \"post_change_tests_passed\",\n    \"security_privacy_controls_passed\",\n    \"independent_review_passed\",\n)\n\nNON_NEGOTIABLE_CONTROLS: tuple[str, ...] = ("
    if "_RECEIPT_FIELDS" not in text:
        text = replace_once(text, marker, insertion, label="receipt-constants")

    old_start = '''def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate schema, authority binding, rung order, budgets, controls, and digest."""

    errors: list[str] = []
'''
    new_start = '''def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate schema, authority binding, canonical shape, and digest."""

    if not isinstance(contract, Mapping):
        return {
            "decision": "block",
            "schema": CONTRACT_SCHEMA,
            "contract_sha256": None,
            "errors": ["contract-type"],
        }
    errors: list[str] = []
'''
    if old_start in text:
        text = text.replace(old_start, new_start, 1)
    elif "canonical shape" not in text:
        raise RuntimeError("validate_contract start not recognised")

    old_end = '''    supplied = str(contract.get("contract_sha256") or "")
    unsigned = {key: value for key, value in contract.items() if key != "contract_sha256"}
    if supplied != _digest(unsigned):
        errors.append("digest")
    return {
'''
    new_end = '''    supplied = str(contract.get("contract_sha256") or "")
    unsigned = {key: value for key, value in contract.items() if key != "contract_sha256"}
    try:
        expected_digest = _digest(unsigned)
    except (TypeError, ValueError):
        expected_digest = None
        errors.append("canonical-json")
    if supplied != expected_digest:
        errors.append("digest")

    if isinstance(task, Mapping):
        context_manifest = (
            {"sha256": str(context_sha)} if context_sha is not None else None
        )
        try:
            expected_contract = compile_contract(
                dict(task), context_manifest=context_manifest
            )
        except (TypeError, ValueError):
            errors.append("canonical-contract")
        else:
            expected_unsigned = {
                key: value
                for key, value in expected_contract.items()
                if key != "contract_sha256"
            }
            if unsigned != expected_unsigned:
                errors.append("canonical-contract")
    return {
'''
    if old_end in text:
        text = text.replace(old_end, new_end, 1)
    elif "expected_unsigned" not in text:
        raise RuntimeError("validate_contract end not recognised")

    old_assessment_start = '''    errors: list[str] = []
    if not contract["authority_precondition"]["acceptance_criteria_supplied"]:
'''
    new_assessment_start = '''    if not isinstance(assessment, Mapping):
        return {
            "schema": ASSESSMENT_SCHEMA,
            "decision": "needs-work",
            "contract_sha256": contract.get("contract_sha256"),
            "assessment_sha256": None,
            "selected_rung": None,
            "errors": ["assessment-type"],
            "normalized": {},
        }
    errors: list[str] = []
    if set(assessment) != set(_REQUIRED_ASSESSMENT_FIELDS):
        errors.append("assessment-fields")
    if not contract["authority_precondition"]["acceptance_criteria_supplied"]:
'''
    # Restrict replacement to assess_strategy by searching after its definition.
    assess_at = text.index("def assess_strategy(")
    prefix, suffix = text[:assess_at], text[assess_at:]
    if old_assessment_start in suffix:
        suffix = suffix.replace(old_assessment_start, new_assessment_start, 1)
    elif "assessment-type" not in suffix:
        raise RuntimeError("assess_strategy start not recognised")
    text = prefix + suffix

    row_old = '''        if not isinstance(raw, Mapping):
            raw = {}
        decision = str(raw.get("decision") or "unassessed")
'''
    row_new = '''        if not isinstance(raw, Mapping):
            raw = {}
        elif set(raw) != {"decision", "reason", "evidence_refs"}:
            errors.append(f"rung-fields:{rung_id}")
        decision = str(raw.get("decision") or "unassessed")
'''
    if row_old in text:
        text = text.replace(row_old, row_new, 1)
    elif "rung-fields:" not in text:
        raise RuntimeError("rung row validation insertion not recognised")

    delta_old = '''    if not isinstance(raw_delta, Mapping):
        errors.append("delta-type")
        raw_delta = {}
    delta = {key: _string_list(raw_delta.get(key)) for key in ZERO_DEFAULT_BUDGETS}
'''
    delta_new = '''    if not isinstance(raw_delta, Mapping):
        errors.append("delta-type")
        raw_delta = {}
    elif set(raw_delta) != set(ZERO_DEFAULT_BUDGETS):
        errors.append("delta-fields")
    delta = {key: _string_list(raw_delta.get(key)) for key in ZERO_DEFAULT_BUDGETS}
'''
    if delta_old in text:
        text = text.replace(delta_old, delta_new, 1)
    elif "delta-fields" not in text:
        raise RuntimeError("delta validation insertion not recognised")

    exceptions_old = '''    if not isinstance(raw_exceptions, Mapping):
        errors.append("budget-exceptions-type")
        raw_exceptions = {}
    exceptions: dict[str, dict[str, Any]] = {}
'''
    exceptions_new = '''    if not isinstance(raw_exceptions, Mapping):
        errors.append("budget-exceptions-type")
        raw_exceptions = {}
    elif set(raw_exceptions) - set(ZERO_DEFAULT_BUDGETS):
        errors.append("budget-exception-fields")
    exceptions: dict[str, dict[str, Any]] = {}
'''
    if exceptions_old in text:
        text = text.replace(exceptions_old, exceptions_new, 1)
    elif "budget-exception-fields" not in text:
        raise RuntimeError("budget exception validation insertion not recognised")

    exception_row_old = '''        if not isinstance(raw, Mapping):
            raw = {}
        exception = {
            "reason": str(raw.get("reason") or "").strip(),
'''
    exception_row_new = '''        if not isinstance(raw, Mapping):
            raw = {}
        elif set(raw) - {"reason", "evidence_refs", "acceptance_refs"}:
            errors.append(f"budget-exception-row-fields:{key}")
        exception = {
            "reason": str(raw.get("reason") or "").strip(),
'''
    # This pattern occurs only in the exceptions loop after the row loop was already changed.
    if exception_row_old in text:
        text = text.replace(exception_row_old, exception_row_new, 1)
    elif "budget-exception-row-fields" not in text:
        raise RuntimeError("budget exception row insertion not recognised")

    positive_old = '''def _positive_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0
'''
    positive_new = '''def _positive_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def _finite_nonnegative(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0
'''
    if positive_old in text:
        text = text.replace(positive_old, positive_new, 1)
    elif "def _finite_nonnegative" not in text:
        raise RuntimeError("numeric helper replacement not recognised")

    build_at = text.index("def build_receipt(")
    text = text[:build_at] + '''def build_receipt(
    contract: Mapping[str, Any],
    assessment_result: Mapping[str, Any],
    *,
    change_metrics: Mapping[str, Any],
    verification: Mapping[str, Any],
    baseline: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a strictly shaped post-change receipt without overstating savings."""

    contract_check = validate_contract(contract)
    if contract_check["decision"] != "pass":
        raise ValueError("receipt requires a valid minimum-change contract")
    if not isinstance(assessment_result, Mapping):
        raise TypeError("assessment_result must be a mapping")
    if assessment_result.get("schema") != ASSESSMENT_SCHEMA:
        raise ValueError("assessment_result schema is invalid")
    assessment_sha = str(assessment_result.get("assessment_sha256") or "")
    if not _SHA256.fullmatch(assessment_sha):
        raise ValueError("assessment_result digest is invalid")
    selected_rung = assessment_result.get("selected_rung")
    if selected_rung not in _RUNG_IDS:
        raise ValueError("assessment_result selected rung is invalid")
    if not isinstance(change_metrics, Mapping):
        raise TypeError("change_metrics must be a mapping")
    if set(change_metrics) != set(_METRIC_KEYS):
        raise ValueError("change_metrics must contain exactly the v1 metric keys")
    metrics = dict(change_metrics)
    invalid_metrics = [
        key for key in _METRIC_KEYS if not _finite_nonnegative(metrics.get(key))
    ]
    if invalid_metrics:
        raise ValueError(f"invalid non-negative finite metrics: {invalid_metrics}")
    if not isinstance(verification, Mapping):
        raise TypeError("verification must be a mapping")
    if set(verification) != set(_VERIFICATION_KEYS):
        raise ValueError("verification must contain exactly the v1 hard gates")
    verification_payload = dict(verification)
    if any(not isinstance(verification_payload[key], bool) for key in _VERIFICATION_KEYS):
        raise ValueError("verification hard gates must be booleans")
    if baseline is not None:
        if not isinstance(baseline, Mapping):
            raise TypeError("baseline must be a mapping when supplied")
        if set(baseline) != set(_METRIC_KEYS):
            raise ValueError("baseline must contain exactly the v1 metric keys")

    errors: list[str] = []
    if assessment_result.get("decision") != "pass":
        errors.append("assessment-not-pass")
    if assessment_result.get("contract_sha256") != contract.get("contract_sha256"):
        errors.append("assessment-contract-binding")
    errors.extend(
        key for key in _VERIFICATION_KEYS if verification_payload.get(key) is not True
    )
    if selected_rung == "necessity" and float(metrics["source_lines_added"]) > 0:
        errors.append("no-change-rung-has-source-additions")

    comparable = bool(baseline) and all(
        _positive_number((baseline or {}).get(key))
        and _finite_nonnegative(metrics.get(key))
        for key in _METRIC_KEYS
    )
    deltas: dict[str, float] | None = None
    if comparable:
        deltas = {
            key: round(
                (float(metrics[key]) - float((baseline or {})[key]))
                / float((baseline or {})[key])
                * 100.0,
                4,
            )
            for key in _METRIC_KEYS
        }

    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "decision": "pass" if not errors else "needs-work",
        "contract_sha256": contract.get("contract_sha256"),
        "assessment_sha256": assessment_sha,
        "selected_rung": selected_rung,
        "change_metrics": metrics,
        "verification": verification_payload,
        "comparable_baseline_supplied": comparable,
        "relative_deltas_percent": deltas,
        "savings_claim_allowed": comparable and not errors,
        "errors": sorted(set(errors)),
        "production_claim": False,
    }
    receipt["receipt_sha256"] = _digest(receipt)
    structural = validate_receipt(receipt)
    if structural["decision"] != "pass":
        raise RuntimeError(
            "internal receipt validation failed: " + ",".join(structural["errors"])
        )
    return receipt


def validate_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an externally supplied or persisted v1 receipt fail-closed."""

    if not isinstance(receipt, Mapping):
        return {"decision": "block", "errors": ["receipt-type"], "receipt_sha256": None}
    errors: list[str] = []
    if set(receipt) != set(_RECEIPT_FIELDS):
        errors.append("receipt-fields")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        errors.append("schema")
    receipt_decision = receipt.get("decision")
    if receipt_decision not in {"pass", "needs-work"}:
        errors.append("decision")
    for field in ("contract_sha256", "assessment_sha256"):
        if not _SHA256.fullmatch(str(receipt.get(field) or "")):
            errors.append(field)
    if receipt.get("selected_rung") not in _RUNG_IDS:
        errors.append("selected-rung")

    metrics = receipt.get("change_metrics")
    if not isinstance(metrics, Mapping) or set(metrics) != set(_METRIC_KEYS):
        errors.append("change-metrics")
    elif any(not _finite_nonnegative(metrics.get(key)) for key in _METRIC_KEYS):
        errors.append("change-metric-values")

    verification = receipt.get("verification")
    if not isinstance(verification, Mapping) or set(verification) != set(_VERIFICATION_KEYS):
        errors.append("verification")
    elif any(not isinstance(verification.get(key), bool) for key in _VERIFICATION_KEYS):
        errors.append("verification-values")

    comparable = receipt.get("comparable_baseline_supplied")
    savings = receipt.get("savings_claim_allowed")
    if not isinstance(comparable, bool):
        errors.append("comparable-baseline")
    if not isinstance(savings, bool):
        errors.append("savings-claim")
    if receipt.get("production_claim") is not False:
        errors.append("production-claim")

    receipt_errors = receipt.get("errors")
    if not isinstance(receipt_errors, list) or any(
        not isinstance(item, str) for item in (receipt_errors or [])
    ):
        errors.append("errors")
        receipt_errors = []
    expected_decision = "pass" if not receipt_errors else "needs-work"
    if receipt_decision != expected_decision:
        errors.append("decision-consistency")
    expected_savings = comparable is True and not receipt_errors
    if savings is not expected_savings:
        errors.append("savings-consistency")

    deltas = receipt.get("relative_deltas_percent")
    if comparable is True:
        if not isinstance(deltas, Mapping) or set(deltas) != set(_METRIC_KEYS):
            errors.append("relative-deltas")
        elif any(
            isinstance(deltas.get(key), bool)
            or not isinstance(deltas.get(key), (int, float))
            or not math.isfinite(float(deltas[key]))
            for key in _METRIC_KEYS
        ):
            errors.append("relative-delta-values")
    elif deltas is not None:
        errors.append("relative-deltas-without-baseline")

    supplied = str(receipt.get("receipt_sha256") or "")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    try:
        expected_digest = _digest(unsigned)
    except (TypeError, ValueError):
        expected_digest = None
        errors.append("canonical-json")
    if supplied != expected_digest:
        errors.append("digest")
    return {
        "decision": "pass" if not errors else "block",
        "errors": sorted(set(errors)),
        "receipt_sha256": supplied or None,
    }
'''
    write(path, text)


def add_deep_tests() -> None:
    path = ROOT / "tests/test_minimum_change_deep.py"
    content = '''# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-30
"""Adversarial, fuzz, concurrency, and receipt tests for the minimum-change gate."""
from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import json
import math
import random
import string
import unittest
from collections.abc import Mapping

from iot_ai.minimum_change import (
    ASSESSMENT_SCHEMA,
    NON_NEGOTIABLE_CONTROLS,
    RUNG_DEFINITIONS,
    ZERO_DEFAULT_BUDGETS,
    assess_strategy,
    build_receipt,
    compile_contract,
    validate_contract,
    validate_receipt,
)


def canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )


def resign(payload: dict, digest_field: str) -> dict:
    result = copy.deepcopy(payload)
    unsigned = {key: value for key, value in result.items() if key != digest_field}
    result[digest_field] = hashlib.sha256(canonical(unsigned).encode("utf-8")).hexdigest()
    return result


def task(seed: int = 1) -> dict[str, object]:
    return {
        "id": f"task-deep-{seed}",
        "revision": seed,
        "title": "Verify the minimum necessary governed change",
        "description": "Prefer existing capability and preserve every hard control.",
        "acceptance_criteria": "All deterministic and adversarial tests pass.",
        "risk_class": "R2",
        "priority": "high",
        "task_type": "implementation",
        "source": "deep-validation",
        "source_id": f"source-{seed}",
        "tags": ["deep", "minimum-change"],
    }


def passing_assessment(selected: str = "minimal-local-change") -> dict[str, object]:
    ids = [str(item["id"]) for item in RUNG_DEFINITIONS]
    index = ids.index(selected)
    rows: dict[str, dict[str, object]] = {}
    for position, rung_id in enumerate(ids):
        if position < index:
            rows[rung_id] = {
                "decision": "rejected",
                "reason": f"Objective evidence rejects {rung_id}.",
                "evidence_refs": [f"evidence:{rung_id}"],
            }
        elif position == index:
            rows[rung_id] = {
                "decision": "selected",
                "reason": "This is the first complete and safe solution rung.",
                "evidence_refs": ["evidence:selected"],
            }
        else:
            rows[rung_id] = {
                "decision": "unassessed",
                "reason": "",
                "evidence_refs": [],
            }
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
        "dependency_service_schema_agent_delta": {
            key: [] for key in ZERO_DEFAULT_BUDGETS
        },
        "budget_exceptions": {},
        "verification_plan": ["python -m pytest"],
        "remaining_uncertainty": [],
    }


def passing_result(seed: int = 1, selected: str = "minimal-local-change") -> tuple[dict, dict]:
    contract = compile_contract(task(seed), context_manifest={"sha256": "a" * 64})
    result = assess_strategy(contract, passing_assessment(selected))
    assert result["decision"] == "pass", result
    return contract, result


class CanonicalContractSecurityTests(unittest.TestCase):
    def test_resigned_contract_with_unknown_top_level_field_is_rejected(self) -> None:
        contract = compile_contract(task())
        contract["hidden_override"] = {"allow": True}
        tampered = resign(contract, "contract_sha256")
        result = validate_contract(tampered)
        self.assertEqual(result["decision"], "block")
        self.assertIn("canonical-contract", result["errors"])

    def test_resigned_contract_with_unknown_nested_task_field_is_rejected(self) -> None:
        contract = compile_contract(task())
        contract["task"]["hidden_tenant"] = "other"
        contract["task_sha256"] = hashlib.sha256(
            canonical(contract["task"]).encode("utf-8")
        ).hexdigest()
        tampered = resign(contract, "contract_sha256")
        result = validate_contract(tampered)
        self.assertEqual(result["decision"], "block")
        self.assertIn("canonical-contract", result["errors"])

    def test_resigned_claim_boundary_relaxation_is_rejected(self) -> None:
        contract = compile_contract(task())
        contract["claim_boundary"]["production_claim"] = True
        tampered = resign(contract, "contract_sha256")
        result = validate_contract(tampered)
        self.assertIn("production-claim", result["errors"])
        self.assertIn("canonical-contract", result["errors"])

    def test_non_mapping_contract_fails_closed(self) -> None:
        result = validate_contract([])  # type: ignore[arg-type]
        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["errors"], ["contract-type"])

    def test_non_finite_contract_value_cannot_be_resigned(self) -> None:
        contract = compile_contract(task())
        contract["task"]["revision"] = math.nan
        with self.assertRaises(ValueError):
            resign(contract, "contract_sha256")


class AssessmentBypassTests(unittest.TestCase):
    def test_unknown_assessment_field_is_rejected(self) -> None:
        contract = compile_contract(task())
        assessment = passing_assessment()
        assessment["hidden_override"] = True
        result = assess_strategy(contract, assessment)
        self.assertIn("assessment-fields", result["errors"])

    def test_unknown_rung_row_field_is_rejected(self) -> None:
        contract = compile_contract(task())
        assessment = passing_assessment()
        assessment["rung_assessments"]["necessity"]["hidden"] = True
        result = assess_strategy(contract, assessment)
        self.assertIn("rung-fields:necessity", result["errors"])

    def test_unknown_delta_field_is_rejected(self) -> None:
        contract = compile_contract(task())
        assessment = passing_assessment()
        assessment["dependency_service_schema_agent_delta"]["new_shadow_store"] = []
        result = assess_strategy(contract, assessment)
        self.assertIn("delta-fields", result["errors"])

    def test_unknown_budget_exception_field_is_rejected(self) -> None:
        contract = compile_contract(task())
        assessment = passing_assessment()
        assessment["budget_exceptions"]["shadow"] = {
            "reason": "not authorised",
            "evidence_refs": [],
            "acceptance_refs": [],
        }
        result = assess_strategy(contract, assessment)
        self.assertIn("budget-exception-fields", result["errors"])

    def test_bytes_cannot_satisfy_control_list(self) -> None:
        contract = compile_contract(task())
        assessment = passing_assessment()
        assessment["controls_preserved"] = b"security"
        result = assess_strategy(contract, assessment)
        self.assertEqual(result["decision"], "needs-work")
        self.assertTrue(any(item.startswith("control:") for item in result["errors"]))

    def test_non_mapping_assessment_fails_closed(self) -> None:
        contract = compile_contract(task())
        result = assess_strategy(contract, [])  # type: ignore[arg-type]
        self.assertEqual(result["decision"], "needs-work")
        self.assertEqual(result["errors"], ["assessment-type"])


class ReceiptSecurityTests(unittest.TestCase):
    def receipt(self) -> dict:
        contract, result = passing_result()
        return build_receipt(
            contract,
            result,
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

    def test_valid_receipt_is_structurally_accepted(self) -> None:
        result = validate_receipt(self.receipt())
        self.assertEqual(result["decision"], "pass")

    def test_resigned_receipt_with_unknown_field_is_rejected(self) -> None:
        receipt = self.receipt()
        receipt["hidden_override"] = True
        tampered = resign(receipt, "receipt_sha256")
        result = validate_receipt(tampered)
        self.assertIn("receipt-fields", result["errors"])

    def test_resigned_receipt_with_invalid_rung_is_rejected(self) -> None:
        receipt = self.receipt()
        receipt["selected_rung"] = "skip-all-controls"
        tampered = resign(receipt, "receipt_sha256")
        result = validate_receipt(tampered)
        self.assertIn("selected-rung", result["errors"])

    def test_resigned_receipt_with_false_savings_is_rejected(self) -> None:
        receipt = self.receipt()
        receipt["savings_claim_allowed"] = True
        tampered = resign(receipt, "receipt_sha256")
        result = validate_receipt(tampered)
        self.assertIn("savings-consistency", result["errors"])

    def test_receipt_digest_tampering_is_rejected(self) -> None:
        receipt = self.receipt()
        receipt["change_metrics"]["tokens"] = 999
        result = validate_receipt(receipt)
        self.assertIn("digest", result["errors"])

    def test_build_receipt_rejects_non_finite_metrics(self) -> None:
        contract, result = passing_result()
        with self.assertRaises(ValueError):
            build_receipt(
                contract,
                result,
                change_metrics={
                    "source_lines_added": 1,
                    "tokens": math.nan,
                    "cost": 0.1,
                    "wall_clock_seconds": 1,
                },
                verification={key: True for key in (
                    "acceptance_coverage_complete",
                    "post_change_tests_passed",
                    "security_privacy_controls_passed",
                    "independent_review_passed",
                )},
            )

    def test_build_receipt_rejects_boolean_metric(self) -> None:
        contract, result = passing_result()
        with self.assertRaises(ValueError):
            build_receipt(
                contract,
                result,
                change_metrics={
                    "source_lines_added": True,
                    "tokens": 1,
                    "cost": 0.1,
                    "wall_clock_seconds": 1,
                },
                verification={key: True for key in (
                    "acceptance_coverage_complete",
                    "post_change_tests_passed",
                    "security_privacy_controls_passed",
                    "independent_review_passed",
                )},
            )


class DeterminismConcurrencyAndFuzzTests(unittest.TestCase):
    def test_contract_compilation_is_thread_deterministic(self) -> None:
        source = task(77)
        context = {"sha256": "7" * 64}
        expected = compile_contract(source, context_manifest=context)
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            results = list(
                pool.map(
                    lambda _: compile_contract(source, context_manifest=context),
                    range(512),
                )
            )
        self.assertTrue(all(item == expected for item in results))

    def test_unicode_and_key_order_are_digest_stable_for_identical_semantics(self) -> None:
        first = task(9)
        first["description"] = "Sicher prüfen — بررسی دقیق"
        second = dict(reversed(list(first.items())))
        self.assertEqual(
            compile_contract(first)["contract_sha256"],
            compile_contract(second)["contract_sha256"],
        )

    def test_seeded_malformed_assessments_never_raise(self) -> None:
        rng = random.Random(20260830)
        contract = compile_contract(task())
        alphabet = string.ascii_letters + string.digits
        for _ in range(1000):
            assessment = passing_assessment(
                rng.choice(["necessity", "existing-capability", "minimal-local-change"])
            )
            operation = rng.randrange(8)
            if operation == 0:
                assessment.pop(rng.choice(list(assessment)))
            elif operation == 1:
                assessment["selected_rung"] = "".join(rng.choice(alphabet) for _ in range(12))
            elif operation == 2:
                assessment["controls_preserved"] = rng.choice([None, 7, b"x", []])
            elif operation == 3:
                assessment["rung_assessments"] = rng.choice([None, [], "bad"])
            elif operation == 4:
                assessment["verification_plan"] = rng.choice([None, [], 3])
            elif operation == 5:
                assessment["dependency_service_schema_agent_delta"] = {"unknown": ["x"]}
            elif operation == 6:
                assessment["budget_exceptions"] = {"unknown": {"reason": "x"}}
            else:
                assessment["hidden_" + str(rng.randrange(100))] = True
            result = assess_strategy(contract, assessment)
            self.assertIn(result["decision"], {"pass", "needs-work", "block"})
            self.assertIsInstance(result["errors"], list)


if __name__ == "__main__":
    unittest.main()
'''
    path.write_text(content, encoding="utf-8")


def add_curated_mutation_tool() -> None:
    path = ROOT / "tools/_pr14_curated_mutation_once_20260830.py"
    content = '''# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-30
"""Curated critical-control mutation suite; removed after the PR hardening run."""
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
        "            if unsigned != expected_unsigned:\n                errors.append(\"canonical-contract\")",
        "            if False and unsigned != expected_unsigned:\n                errors.append(\"canonical-contract\")",
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
        "        if not all(exception.values()):\n            errors.append(f\"budget-exception:{key}\")",
        "        if not any(exception.values()):\n            errors.append(f\"budget-exception:{key}\")",
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
        "receipt-digest-bypass",
        '    if supplied != expected_digest:\n        errors.append("digest")\n    return {\n        "decision": "pass" if not errors else "block",',
        '    if False and supplied != expected_digest:\n        errors.append("digest")\n    return {\n        "decision": "pass" if not errors else "block",',
        "tests/test_minimum_change_deep.py::ReceiptSecurityTests::test_receipt_digest_tampering_is_rejected",
    ),
    (
        "savings-consistency-bypass",
        '    if savings is not expected_savings:\n        errors.append("savings-consistency")',
        '    if False and savings is not expected_savings:\n        errors.append("savings-consistency")',
        "tests/test_minimum_change_deep.py::ReceiptSecurityTests::test_resigned_receipt_with_false_savings_is_rejected",
    ),
]


def main() -> int:
    report = {"schema": "iot-ai.curated-mutation-report.v1", "mutants": []}
    killed = 0
    with tempfile.TemporaryDirectory(prefix="mcgpt-mutants-") as temporary:
        temp = Path(temporary)
        for name, old, new, test_node in MUTANTS:
            if SOURCE.count(old) != 1:
                raise RuntimeError(f"{name}: expected one mutation target, found {SOURCE.count(old)}")
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
                "tail": completed.stdout[-1000:],
            })
    report["killed"] = killed
    report["total"] = len(MUTANTS)
    report["score_percent"] = round(killed / len(MUTANTS) * 100.0, 2)
    report["decision"] = "pass" if killed == len(MUTANTS) else "block"
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
    fix_public_contract_test()
    fix_brand_identity()
    harden_minimum_change()
    add_deep_tests()
    add_curated_mutation_tool()
    manifest = {
        "schema": "iot-ai.pr14-deep-hardening-manifest.v1",
        "production_claim": False,
        "merge_performed": False,
        "release_performed": False,
        "pmd_runtime_mutated": False,
        "persistent_files": [
            "src/iot_ai/minimum_change.py",
            "tests/test_minimum_change_contract.py",
            "tests/test_minimum_change_deep.py",
            "docs/research/ponytail-assessment.md",
        ],
    }
    evidence = ROOT / "evidence/pr14-deep-validation"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "hardening-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
