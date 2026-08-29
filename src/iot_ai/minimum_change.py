# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-29
"""Deterministic Minimum Necessary Change Gate for governed engineering.

The gate compiles a task-bound, evidence-first contract before provider dispatch.
It does not add a model call, dependency, service, schema, or filesystem write.
Acceptance, safety, product ownership, and evidence always outrank diff size.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

CONTRACT_SCHEMA = "iot-ai.minimum-necessary-change-contract.v1"
ASSESSMENT_SCHEMA = "iot-ai.minimum-necessary-change-assessment.v1"
RECEIPT_SCHEMA = "iot-ai.minimum-necessary-change-receipt.v1"
_DECISIONS = {"selected", "rejected", "not-applicable", "unassessed"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_METRIC_KEYS = ("source_lines_added", "tokens", "cost", "wall_clock_seconds")

RUNG_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "necessity",
        "order": 1,
        "question": "Is any product or system change required to satisfy the authoritative task?",
        "preferred_outcome": "no-change-or-clarification",
        "evidence_required": (
            "current acceptance criteria",
            "current runtime or repository evidence",
            "proof that the issue is not resolved, obsolete, duplicate, or out of scope",
        ),
    },
    {
        "id": "existing-capability",
        "order": 2,
        "question": "Can an existing product capability, helper, contract, query, or service satisfy it?",
        "preferred_outcome": "reuse-existing-capability",
        "evidence_required": (
            "repository and capability search",
            "caller and ownership trace",
            "compatibility and rollback impact",
        ),
    },
    {
        "id": "standard-library",
        "order": 3,
        "question": "Can the language or runtime standard library satisfy it safely?",
        "preferred_outcome": "standard-library",
        "evidence_required": (
            "runtime version",
            "standard-library API and platform support",
            "security and compatibility constraints",
        ),
    },
    {
        "id": "native-platform",
        "order": 4,
        "question": "Can the OS, browser, database, Git, IdP, or approved platform do it natively?",
        "preferred_outcome": "native-platform",
        "evidence_required": (
            "platform capability and version",
            "deployment portability",
            "data-sovereignty, tenancy, and rollback implications",
        ),
    },
    {
        "id": "existing-dependency",
        "order": 5,
        "question": "Can an approved dependency or managed service satisfy it without widening trust?",
        "preferred_outcome": "reuse-approved-dependency",
        "evidence_required": (
            "dependency or service inventory",
            "licence and supply-chain status",
            "supported-version and security evidence",
        ),
    },
    {
        "id": "minimal-local-change",
        "order": 6,
        "question": "Can one bounded configuration, data, policy, prompt, query, or local code change satisfy it?",
        "preferred_outcome": "minimal-local-change",
        "evidence_required": (
            "exact file, setting, query, or contract",
            "caller impact",
            "deterministic verification command",
        ),
    },
    {
        "id": "minimum-new-code",
        "order": 7,
        "question": "After earlier rungs fail with evidence, what is the smallest coherent new implementation?",
        "preferred_outcome": "minimum-new-code",
        "evidence_required": (
            "rejections for rungs 1 through 6",
            "bounded write scope and architecture",
            "tests, rollback, and independent review",
        ),
    },
)

NON_NEGOTIABLE_CONTROLS: tuple[str, ...] = (
    "authoritative-task-and-explicit-acceptance",
    "trust-boundary-input-validation",
    "authentication-authorization-and-tenant-isolation",
    "data-loss-prevention-backup-restore-and-rollback",
    "security-privacy-and-secret-handling",
    "accessibility-and-operator-explainability",
    "observability-audit-and-evidence-binding",
    "hardware-calibration-and-real-world-safety-when-applicable",
    "licence-supply-chain-and-commercial-boundaries",
    "product-ownership-and-no-cross-product-database-coupling",
    "independent-review-and-founder-decision-separation",
)

ZERO_DEFAULT_BUDGETS: dict[str, int] = {
    "new_dependencies": 0,
    "new_external_services": 0,
    "new_databases_or_schemas": 0,
    "new_agents_or_provider_routes": 0,
    "new_abstraction_layers": 0,
}

_REQUIRED_ASSESSMENT_FIELDS: tuple[str, ...] = (
    "selected_rung",
    "rung_assessments",
    "acceptance_criteria_preserved",
    "controls_preserved",
    "rejected_alternatives",
    "estimated_change_surface",
    "dependency_service_schema_agent_delta",
    "budget_exceptions",
    "verification_plan",
    "remaining_uncertainty",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values: Sequence[Any] = [value]
    elif isinstance(value, Sequence):
        values = value
    else:
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _acceptance_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return "\n".join(_string_list(value))


def _task_projection(task: Mapping[str, Any]) -> dict[str, Any]:
    tags = task.get("tags") or []
    if isinstance(tags, str):
        tags = [item.strip() for item in tags.split(",") if item.strip()]
    return {
        "id": str(task.get("id") or "").strip(),
        "revision": int(task.get("revision") or 0),
        "title": str(task.get("title") or "").strip(),
        "description": str(task.get("description") or "").strip(),
        "acceptance_criteria": _acceptance_text(task.get("acceptance_criteria")),
        "risk_class": str(task.get("risk_class") or "R1").upper(),
        "priority": str(task.get("priority") or "normal").casefold(),
        "task_type": str(task.get("task_type") or "").strip(),
        "source": str(task.get("source") or "").strip(),
        "source_id": str(task.get("source_id") or "").strip(),
        "tags": sorted({str(item).strip() for item in tags if str(item).strip()}),
    }


def _mode(task: Mapping[str, Any]) -> str:
    risk = str(task.get("risk_class") or "R1").upper()
    priority = str(task.get("priority") or "normal").casefold()
    if risk in {"R3", "R4"} or priority == "critical":
        return "required-with-independent-review"
    if risk == "R2" or priority == "high":
        return "required-plan-evidence"
    return "advisory-evidence"


def compile_contract(
    task: Mapping[str, Any],
    *,
    context_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile one immutable pre-code economy contract without external work."""

    projection = _task_projection(task)
    if not projection["id"]:
        raise ValueError("minimum-change contract requires task id")
    if not projection["title"]:
        raise ValueError("minimum-change contract requires task title")
    context_sha = str(
        (context_manifest or {}).get("sha256")
        or (context_manifest or {}).get("digest")
        or ""
    ).strip() or None
    acceptance_supplied = bool(projection["acceptance_criteria"])
    contract: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "version": "1.0.0",
        "decision": "requires-evidence",
        "mode": _mode(projection),
        "task": projection,
        "task_sha256": _digest(projection),
        "context_manifest_sha256": context_sha,
        "authority_precondition": {
            "task_authority_must_remain_single": True,
            "task_revision_must_match": projection["revision"],
            "acceptance_criteria_supplied": acceptance_supplied,
            "missing_acceptance_decision": "block-execution" if not acceptance_supplied else "not-applicable",
            "explicit_requirements_may_not_be_removed_for_size": True,
        },
        "rungs": [
            {**item, "evidence_required": list(item["evidence_required"]), "status": "unassessed"}
            for item in RUNG_DEFINITIONS
        ],
        "default_budgets": dict(ZERO_DEFAULT_BUDGETS),
        "budget_rule": (
            "A zero budget may be raised only by a bound exception proving that every earlier rung "
            "failed and an authoritative acceptance criterion requires the addition."
        ),
        "non_negotiable_controls": list(NON_NEGOTIABLE_CONTROLS),
        "required_assessment_fields": list(_REQUIRED_ASSESSMENT_FIELDS),
        "metrics": [
            "files_added_modified_deleted",
            "source_lines_added_deleted",
            "dependency_service_schema_agent_delta",
            "provider_input_output_reasoning_tokens",
            "cost_and_wall_clock_time",
            "acceptance_coverage",
            "post_change_tests",
            "security_privacy_accessibility_results",
            "rollback_result",
        ],
        "claim_boundary": {
            "no_savings_claim_without_comparable_baseline": True,
            "smaller_diff_is_not_correctness": True,
            "provider_opinion_is_not_deterministic_evidence": True,
            "production_claim": False,
        },
        "implementation_origin": (
            "Independent IoT-AI.Tech implementation. No third-party runtime, hook, source file, "
            "or prompt package is embedded by this contract."
        ),
    }
    contract["contract_sha256"] = _digest(contract)
    return contract


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate schema, authority binding, rung order, budgets, controls, and digest."""

    errors: list[str] = []
    if contract.get("schema") != CONTRACT_SCHEMA:
        errors.append("schema")
    if contract.get("version") != "1.0.0":
        errors.append("version")
    task = contract.get("task") or {}
    if not isinstance(task, Mapping):
        errors.append("task")
        task = {}
    elif contract.get("task_sha256") != _digest(dict(task)):
        errors.append("task-digest")
    context_sha = contract.get("context_manifest_sha256")
    if context_sha is not None and not _SHA256.fullmatch(str(context_sha)):
        errors.append("context-digest")
    authority = contract.get("authority_precondition") or {}
    acceptance = bool(str(task.get("acceptance_criteria") or "").strip())
    if authority.get("acceptance_criteria_supplied") is not acceptance:
        errors.append("acceptance-precondition")
    expected_missing = "not-applicable" if acceptance else "block-execution"
    if authority.get("missing_acceptance_decision") != expected_missing:
        errors.append("missing-acceptance-decision")
    if authority.get("task_revision_must_match") != task.get("revision"):
        errors.append("task-revision-binding")
    rungs = list(contract.get("rungs") or [])
    expected_rungs = [
        {**item, "evidence_required": list(item["evidence_required"]), "status": "unassessed"}
        for item in RUNG_DEFINITIONS
    ]
    if rungs != expected_rungs:
        errors.append("rungs")
    if dict(contract.get("default_budgets") or {}) != ZERO_DEFAULT_BUDGETS:
        errors.append("default-budgets")
    if tuple(contract.get("non_negotiable_controls") or ()) != NON_NEGOTIABLE_CONTROLS:
        errors.append("non-negotiable-controls")
    if tuple(contract.get("required_assessment_fields") or ()) != _REQUIRED_ASSESSMENT_FIELDS:
        errors.append("assessment-fields")
    claim = contract.get("claim_boundary") or {}
    if claim.get("production_claim") is not False:
        errors.append("production-claim")
    supplied = str(contract.get("contract_sha256") or "")
    unsigned = {key: value for key, value in contract.items() if key != "contract_sha256"}
    if supplied != _digest(unsigned):
        errors.append("digest")
    return {
        "decision": "pass" if not errors else "block",
        "schema": CONTRACT_SCHEMA,
        "contract_sha256": supplied or None,
        "errors": sorted(set(errors)),
    }


def render_prompt(contract: Mapping[str, Any]) -> str:
    """Render a compact, provider-neutral form of the owned contract."""

    validation = validate_contract(contract)
    if validation["decision"] != "pass":
        raise ValueError(f"invalid minimum-change contract: {','.join(validation['errors'])}")
    rungs = "\n".join(f"{item['order']}. {item['id']}: {item['question']}" for item in contract["rungs"])
    controls = ", ".join(contract["non_negotiable_controls"])
    budgets = ", ".join(f"{key}=0" for key in contract["default_budgets"])
    return f"""MINIMUM NECESSARY CHANGE CONTRACT
CONTRACT_SHA256: {contract['contract_sha256']}
MODE: {contract['mode']}

Evaluate these rungs in order and stop at the first one supported by current evidence:
{rungs}

Rules:
- Acceptance criteria and task authority outrank code reduction.
- Earlier rungs may be rejected only with evidence; unknown is not rejection.
- Default budgets are {budgets}.
- Preserve these controls: {controls}.
- Bind any budget exception to evidence and an authoritative acceptance criterion.
- Return `minimum_change_assessment` with every required assessment field.
- Do not claim savings without a comparable baseline; smaller is not proof of correctness.
""".strip()


def assess_strategy(contract: Mapping[str, Any], assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a specialist-produced rung assessment deterministically."""

    contract_check = validate_contract(contract)
    if contract_check["decision"] != "pass":
        return {
            "schema": ASSESSMENT_SCHEMA,
            "decision": "block",
            "errors": [f"contract:{item}" for item in contract_check["errors"]],
        }
    errors: list[str] = []
    if not contract["authority_precondition"]["acceptance_criteria_supplied"]:
        errors.append("authoritative-acceptance-missing")
    for field in _REQUIRED_ASSESSMENT_FIELDS:
        if field not in assessment:
            errors.append(f"field:{field}")

    selected = str(assessment.get("selected_rung") or "")
    rung_ids = [item["id"] for item in contract["rungs"]]
    selected_index = rung_ids.index(selected) if selected in rung_ids else -1
    if selected_index < 0:
        errors.append("selected-rung")

    raw_rows = assessment.get("rung_assessments") or {}
    if not isinstance(raw_rows, Mapping):
        errors.append("rung-assessments-type")
        raw_rows = {}
    normalized_rows: dict[str, dict[str, Any]] = {}
    for rung_id in rung_ids:
        raw = raw_rows.get(rung_id) or {}
        if not isinstance(raw, Mapping):
            raw = {}
        decision = str(raw.get("decision") or "unassessed")
        reason = str(raw.get("reason") or "").strip()
        refs = _string_list(raw.get("evidence_refs"))
        normalized_rows[rung_id] = {"decision": decision, "reason": reason, "evidence_refs": refs}
        if decision not in _DECISIONS:
            errors.append(f"decision:{rung_id}")

    if selected_index >= 0:
        for index, rung_id in enumerate(rung_ids):
            row = normalized_rows[rung_id]
            if index < selected_index:
                if row["decision"] not in {"rejected", "not-applicable"}:
                    errors.append(f"earlier-rung-not-rejected:{rung_id}")
                if not row["reason"] or not row["evidence_refs"]:
                    errors.append(f"earlier-rung-evidence:{rung_id}")
            elif index == selected_index:
                if row["decision"] != "selected":
                    errors.append(f"selected-rung-decision:{rung_id}")
                if not row["reason"] or not row["evidence_refs"]:
                    errors.append(f"selected-rung-evidence:{rung_id}")
            elif row["decision"] == "selected":
                errors.append(f"multiple-selected:{rung_id}")

    if assessment.get("acceptance_criteria_preserved") is not True:
        errors.append("acceptance-criteria-not-preserved")
    controls = set(_string_list(assessment.get("controls_preserved")))
    errors.extend(f"control:{item}" for item in NON_NEGOTIABLE_CONTROLS if item not in controls)

    rejected_alternatives = assessment.get("rejected_alternatives")
    if not isinstance(rejected_alternatives, Sequence) or isinstance(rejected_alternatives, str):
        errors.append("rejected-alternatives")
        rejected_alternatives = []
    change_surface = assessment.get("estimated_change_surface")
    if not isinstance(change_surface, Mapping):
        errors.append("estimated-change-surface")
        change_surface = {}
    uncertainties = assessment.get("remaining_uncertainty")
    if not isinstance(uncertainties, Sequence) or isinstance(uncertainties, str):
        errors.append("remaining-uncertainty")
        uncertainties = []

    raw_delta = assessment.get("dependency_service_schema_agent_delta") or {}
    if not isinstance(raw_delta, Mapping):
        errors.append("delta-type")
        raw_delta = {}
    delta = {key: _string_list(raw_delta.get(key)) for key in ZERO_DEFAULT_BUDGETS}
    raw_exceptions = assessment.get("budget_exceptions") or {}
    if not isinstance(raw_exceptions, Mapping):
        errors.append("budget-exceptions-type")
        raw_exceptions = {}
    exceptions: dict[str, dict[str, Any]] = {}
    for key, values in delta.items():
        raw = raw_exceptions.get(key) or {}
        if not isinstance(raw, Mapping):
            raw = {}
        exception = {
            "reason": str(raw.get("reason") or "").strip(),
            "evidence_refs": _string_list(raw.get("evidence_refs")),
            "acceptance_refs": _string_list(raw.get("acceptance_refs")),
        }
        exceptions[key] = exception
        if not values:
            continue
        if selected != "minimum-new-code":
            errors.append(f"unexpected-{key}")
        if not all(exception.values()):
            errors.append(f"budget-exception:{key}")

    verification_plan = _string_list(assessment.get("verification_plan"))
    if not verification_plan:
        errors.append("verification-plan")
    if selected == "necessity" and change_surface.get("mutation_required") is not False:
        errors.append("necessity-rung-must-be-no-mutation")

    normalized = {
        "selected_rung": selected or None,
        "rung_assessments": normalized_rows,
        "acceptance_criteria_preserved": assessment.get("acceptance_criteria_preserved") is True,
        "controls_preserved": sorted(controls),
        "rejected_alternatives": list(rejected_alternatives),
        "estimated_change_surface": dict(change_surface),
        "dependency_service_schema_agent_delta": delta,
        "budget_exceptions": exceptions,
        "verification_plan": verification_plan,
        "remaining_uncertainty": list(uncertainties),
    }
    return {
        "schema": ASSESSMENT_SCHEMA,
        "decision": "pass" if not errors else "needs-work",
        "contract_sha256": contract["contract_sha256"],
        "assessment_sha256": _digest(normalized),
        "selected_rung": selected or None,
        "errors": sorted(set(errors)),
        "normalized": normalized,
    }


def _positive_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def build_receipt(
    contract: Mapping[str, Any],
    assessment_result: Mapping[str, Any],
    *,
    change_metrics: Mapping[str, Any],
    verification: Mapping[str, Any],
    baseline: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a post-change receipt without overstating savings or readiness."""

    errors: list[str] = []
    if validate_contract(contract)["decision"] != "pass":
        errors.append("contract-not-pass")
    if assessment_result.get("decision") != "pass":
        errors.append("assessment-not-pass")
    if assessment_result.get("contract_sha256") != contract.get("contract_sha256"):
        errors.append("assessment-contract-binding")
    required_verification = (
        "acceptance_coverage_complete",
        "post_change_tests_passed",
        "security_privacy_controls_passed",
        "independent_review_passed",
    )
    errors.extend(key for key in required_verification if verification.get(key) is not True)
    if (
        assessment_result.get("selected_rung") == "necessity"
        and float(change_metrics.get("source_lines_added") or 0) > 0
    ):
        errors.append("no-change-rung-has-source-additions")

    comparable = bool(baseline) and all(
        key in change_metrics
        and key in (baseline or {})
        and _positive_number((baseline or {})[key])
        and math.isfinite(float(change_metrics[key]))
        for key in _METRIC_KEYS
    )
    deltas: dict[str, float] | None = None
    if comparable:
        deltas = {
            key: round(
                (float(change_metrics[key]) - float((baseline or {})[key]))
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
        "assessment_sha256": assessment_result.get("assessment_sha256"),
        "selected_rung": assessment_result.get("selected_rung"),
        "change_metrics": dict(change_metrics),
        "verification": dict(verification),
        "comparable_baseline_supplied": comparable,
        "relative_deltas_percent": deltas,
        "savings_claim_allowed": comparable and not errors,
        "errors": sorted(set(errors)),
        "production_claim": False,
    }
    receipt["receipt_sha256"] = _digest(receipt)
    return receipt
