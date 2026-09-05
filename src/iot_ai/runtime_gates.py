# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
"""Runtime hard gates for MNCG, effort receipts, and skill-state truth."""
from __future__ import annotations

from typing import Any, Mapping

import hashlib
import json
import re

from .minimum_change import assess_strategy, compile_contract  # PR #19 overlap: import only; do not edit that module.
from .settings_v2 import EFFORT_ORDER, normalize_routing, resolve_effort

MNCG_BIND_FIELDS = (
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

MNCG_GATE = "minimum_change_assessment_valid"
EFFORT_RECEIPT_SCHEMA = "iot-ai.effort-receipt.v1"
SKILL_STATE_SCHEMA = "iot-ai.skill-state.v1"
SOURCE_PRIVACY = {
    "packaged": "D0",
    "user": "D1",
    "project": "D2",
    "configured": "D2",
}


def compile_runtime_mncg_contract(
    *,
    goal: str,
    task_id: str,
    risk_class: str,
    acceptance: str,
    context_digest: str | None = None,
    revision: int = 1,
) -> dict[str, Any]:
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("minimum-change-task-id-invalid")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise ValueError("minimum-change-task-revision-invalid")
    if not isinstance(goal, str) or not goal.strip() or not isinstance(acceptance, str):
        raise ValueError("minimum-change-authority-invalid")
    if risk_class not in {"R1", "R2", "R3", "R4"}:
        raise ValueError("minimum-change-risk-class-invalid")
    if context_digest is not None and not re.fullmatch(r"[a-f0-9]{64}", str(context_digest)):
        raise ValueError("minimum-change-context-invalid")
    task = {
        "id": task_id or "task-runtime",
        "revision": revision,
        "title": (goal or "Untitled goal")[:180],
        "description": goal or "",
        "acceptance_criteria": acceptance or "",
        "risk_class": risk_class or "R2",
        "priority": "high",
        "task_type": "implementation",
        "source": "iot-ai",
        "source_id": task_id or "task-runtime",
        "tags": ["agentic", "mncg"],
    }
    manifest = {"digest": context_digest} if context_digest else None
    return compile_contract(task, context_manifest=manifest)


def evaluate_minimum_change_gate(
    synthesis: Mapping[str, Any] | None,
    *,
    goal: str,
    task_id: str,
    risk_class: str,
    acceptance: str,
    context_digest: str | None = None,
    revision: int = 1,
) -> dict[str, Any]:
    """Recompute MNCG semantically. Field presence is not validity."""

    payload = dict(synthesis) if isinstance(synthesis, Mapping) else {}
    assessment = payload.get("minimum_change_assessment")
    if not isinstance(assessment, Mapping):
        return {
            "valid": False,
            "decision": "needs-work",
            "errors": ["field:minimum_change_assessment"],
            "selected_rung": None,
            "assessment_sha256": None,
            "contract_sha256": None,
            "normalized": None,
        }
    try:
        contract = compile_runtime_mncg_contract(
            goal=goal, task_id=task_id, risk_class=risk_class,
            acceptance=acceptance, context_digest=context_digest, revision=revision,
        )
        result = assess_strategy(contract, assessment)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return {"valid": False, "decision": "block", "errors": ["minimum-change-authority-invalid"]}
    errors = list(result.get("errors") or [])
    if result.get("decision") != "pass":
        errors = ["minimum-change-assessment-invalid", *errors]
    acceptance_digest = hashlib.sha256(str(acceptance or "").encode("utf-8")).hexdigest()
    return {
        "valid": result.get("decision") == "pass",
        "decision": result.get("decision"),
        "errors": errors,
        "selected_rung": result.get("selected_rung"),
        "assessment_sha256": result.get("assessment_sha256"),
        "contract_sha256": result.get("contract_sha256"),
        "goal": goal,
        "risk_class": risk_class,
        "context_digest": context_digest,
        "acceptance": acceptance,
        "acceptance_digest": acceptance_digest,
        "task_id": task_id,
        "task_revision": revision,
        "normalized": result.get("normalized"),
        "bind": {
            "task_id": task_id,
            "task_revision": revision,
            "context_digest": context_digest,
            "acceptance_digest": acceptance_digest,
            "assessment_sha256": result.get("assessment_sha256"),
            "contract_sha256": result.get("contract_sha256"),
            "selected_rung": result.get("selected_rung"),
        },
    }


def plan_output_digest(plan: Mapping[str, Any]) -> str:
    """Match the existing graph_nodes output digest; a digest is not a signature."""
    return hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def accepted_plan_allows_implement(
    accepted_plan: Mapping[str, Any] | None,
    *,
    persisted_output_sha256: str | None = None,
    require_persistence: bool = False,
) -> dict[str, Any]:
    """Recompute the accepted assessment. Runtime additionally verifies its ledger hash.

    This pure checker grants no lease or Founder authority. The caller must obtain
    the expected digest from the existing graph ledger, never from model output.
    """
    accepted = dict(accepted_plan) if isinstance(accepted_plan, Mapping) else {}
    mncg = accepted.get("mncg")
    errors: list[str] = []
    if accepted.get("decision") != "accept" or not isinstance(mncg, Mapping):
        return {"valid": False, "decision": "block", "errors": ["accepted-plan-mncg-missing"], "pre_dispatch": True}
    required = {"goal", "risk_class", "task_id", "task_revision", "context_digest", "acceptance",
                "acceptance_digest", "assessment_sha256", "contract_sha256", "selected_rung", "normalized", "bind"}
    if not required.issubset(mncg) or mncg.get("valid") is not True or mncg.get("decision") != "pass":
        errors.append("accepted-plan-mncg-incomplete")
    else:
        recomputed = evaluate_minimum_change_gate(
            {"minimum_change_assessment": mncg.get("normalized")},
            goal=mncg["goal"], task_id=mncg["task_id"], risk_class=mncg["risk_class"],
            acceptance=mncg["acceptance"], context_digest=mncg["context_digest"], revision=mncg["task_revision"],
        )
        if recomputed.get("valid") is not True:
            errors.append("accepted-plan-mncg-invalid")
        for key in ("assessment_sha256", "contract_sha256", "acceptance_digest", "selected_rung", "normalized", "bind"):
            if recomputed.get(key) != mncg.get(key):
                errors.append("accepted-plan-mncg-integrity-mismatch")
    if require_persistence and not persisted_output_sha256:
        errors.append("accepted-plan-persisted-evidence-missing")
    if persisted_output_sha256 is not None:
        try:
            if plan_output_digest(accepted) != persisted_output_sha256:
                errors.append("accepted-plan-persisted-evidence-mismatch")
        except (TypeError, ValueError, RecursionError):
            errors.append("accepted-plan-persisted-evidence-invalid")
    return {"valid": not errors, "decision": "block" if errors else "pass", "errors": sorted(set(errors)),
            "selected_rung": mncg.get("selected_rung"), "pre_dispatch": True}


def bind_implementation_to_accepted_plan(
    implementation: Mapping[str, Any] | None,
    accepted_plan: Mapping[str, Any] | None,
    *,
    goal: str,
    task_id: str,
    risk_class: str,
    acceptance: str,
    context_digest: str | None = None,
    revision: int = 1,
) -> dict[str, Any]:
    """Compare current authority before canonicalization; never replace it with a plan.

    context_digest is the independently retrieved planning context, not the new
    implementation prompt context (which legitimately differs per node).
    """
    checked = accepted_plan_allows_implement(accepted_plan)
    if not checked["valid"]:
        return checked
    accepted = dict(accepted_plan or {})
    frozen = accepted["mncg"]
    errors: list[str] = []
    comparisons = (
        (task_id, frozen.get("task_id"), "minimum-change-task-id-mismatch"),
        (revision, frozen.get("task_revision"), "minimum-change-task-revision-mismatch"),
        (acceptance, frozen.get("acceptance"), "minimum-change-acceptance-mismatch"),
        (context_digest, frozen.get("context_digest"), "minimum-change-context-mismatch"),
        (goal, frozen.get("goal"), "minimum-change-goal-mismatch"),
        (risk_class, frozen.get("risk_class"), "minimum-change-risk-class-mismatch"),
    )
    for current, expected, error in comparisons:
        if type(current) is not type(expected) or current != expected:
            errors.append(error)
    recomputed = evaluate_minimum_change_gate(
        implementation, goal=goal, task_id=task_id, risk_class=risk_class,
        acceptance=acceptance, context_digest=context_digest, revision=revision,
    )
    if recomputed.get("valid") is not True:
        errors.extend(recomputed.get("errors") or ["minimum-change-assessment-invalid"])
    if recomputed.get("selected_rung") != frozen.get("selected_rung"):
        errors.append("implementation-rung-diverges-from-accepted-plan")
    for key, error in (("contract_sha256", "minimum-change-contract-mismatch"),
                       ("assessment_sha256", "minimum-change-assessment-drift"),
                       ("normalized", "minimum-change-assessment-drift")):
        if recomputed.get(key) != frozen.get(key):
            errors.append(error)
    return {**recomputed, "valid": not errors, "decision": "block" if errors else "pass", "errors": sorted(set(errors))}


def resolve_dispatch_effort(
    candidate: Mapping[str, Any] | None,
    *,
    node_effort: str,
    max_effort: str,
    role_id: str | None = None,
    routing: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Intersect every active ceiling and floor; never choose one instead of another.

    The settings resolver's current entitlement is part of the final allowed set.
    A later runtime clamp may narrow that set but must never broaden it.
    """
    row = dict(candidate or {})
    requested = next((value for value in (
        row.get("requested_effort"), row.get("effective_effort"), node_effort
    ) if value is not None), "medium")
    source = str(row.get("effort_source") or "candidate")
    metadata: dict[str, Any] = {}

    def blocked(reason: str) -> dict[str, Any]:
        return {"decision": "block", "block_reason": reason,
                "requested_effort": requested if isinstance(requested, str) else None,
                "effective_effort": None, "effort_source": source,
                "clamp_reason": "No effort satisfies all active policy constraints.",
                **metadata}

    supported = row.get("supported_efforts")
    if type(requested) is not str or requested not in EFFORT_ORDER:
        return blocked("invalid-requested-effort")
    if type(max_effort) is not str or max_effort not in EFFORT_ORDER:
        return blocked("invalid-effort-ceiling")
    if supported is not None and (
        not isinstance(supported, (list, tuple))
        or any(type(item) is not str or item not in EFFORT_ORDER for item in supported)
    ):
        return blocked("invalid-provider-effort-capabilities")
    try:
        normalized_routing = normalize_routing(dict(routing or {}))
        role = role_id or str(row.get("role_id") or "")
        resolved = resolve_effort(
            role_id=role, provider=str(row.get("provider") or ""),
            model=str(row.get("canonical_target_model") or row.get("model") or ""),
            routing=normalized_routing, requested=requested, supported=supported,
        )
    except (TypeError, ValueError, OverflowError):
        return blocked("invalid-effort-policy")
    source = str(resolved.get("source_layer") or source)
    actual_ceiling = resolved.get("entitlement_limit")
    role_floor = normalized_routing["role_bindings"].get(role, {}).get("minimum_effort")
    floors = (role_floor, row.get("minimum_effort"), row.get("risk_policy_floor"))
    metadata = {"entitlement_ceiling": actual_ceiling, "runtime_effort_ceiling": max_effort,
                "role_minimum_effort": role_floor,
                "candidate_minimum_effort": row.get("minimum_effort"),
                "risk_policy_floor": row.get("risk_policy_floor")}
    if any(value is not None and (type(value) is not str or value not in EFFORT_ORDER) for value in floors):
        # Do not echo malformed provider-controlled objects in diagnostic metadata.
        metadata = {key: value for key, value in metadata.items() if value is None or type(value) is str}
        return blocked("invalid-effort-floor")
    if type(actual_ceiling) is not str or actual_ceiling not in EFFORT_ORDER:
        return blocked("invalid-entitlement-effort-ceiling")
    if resolved.get("decision") != "pass":
        return blocked(str(resolved.get("block_reason") or "effort-policy-intersection-empty"))
    policy_limit = resolved.get("policy_limit")
    if not isinstance(policy_limit, list) or any(type(item) is not str or item not in EFFORT_ORDER for item in policy_limit):
        return blocked("invalid-resolved-effort-policy")
    allowed = [item for item in EFFORT_ORDER
               if item in policy_limit
               and EFFORT_ORDER.index(item) <= EFFORT_ORDER.index(max_effort)
               and EFFORT_ORDER.index(item) <= EFFORT_ORDER.index(actual_ceiling)
               and (supported is None or item in supported)
               and all(value is None or EFFORT_ORDER.index(item) >= EFFORT_ORDER.index(value) for value in floors)]
    metadata["allowed_efforts"] = allowed
    if not allowed:
        return blocked("effort-policy-intersection-empty")
    if (row.get("effort_block_reason") or row.get("block_reason")) == "minimum-effort-unsatisfied":
        return blocked("minimum-effort-unsatisfied")
    lower = [item for item in allowed if EFFORT_ORDER.index(item) <= EFFORT_ORDER.index(requested)]
    effective = lower[-1] if lower else allowed[0]
    clamp_reason = resolved.get("clamp_reason") or row.get("effort_clamp_reason")
    if effective != resolved.get("effective_value"):
        extra = "Combined runtime, role, candidate and risk policy adjusted effort."
        clamp_reason = f"{clamp_reason}; {extra}" if clamp_reason else extra
    return {"decision": "pass", "block_reason": None, "requested_effort": requested,
            "effective_effort": effective, "effort_source": source,
            "clamp_reason": clamp_reason, **metadata}


def build_effort_receipt(
    *,
    settings_requested: str | None,
    candidate: Mapping[str, Any],
    dispatch: Mapping[str, Any],
    tool_decision: Mapping[str, Any] | None,
    adapter_request_effort: str | None,
    response: Mapping[str, Any] | None,
    required_stages: tuple[str, ...] = ("settings", "candidate", "tool_decision", "adapter_request", "response", "final_report"),
) -> dict[str, Any]:
    effective = str(dispatch.get("effective_effort") or "")
    stages = {
        "settings": settings_requested,
        "candidate": candidate.get("effective_effort") or candidate.get("requested_effort"),
        "tool_decision": (tool_decision or {}).get("effective_effort") or (tool_decision or {}).get("requested_effort"),
        "adapter_request": adapter_request_effort,
        "response": (response or {}).get("effort_effective"),
        "final_report": effective,
    }
    missing = [name for name in required_stages
               if stages.get(name) is None or (type(stages.get(name)) is str and not stages[name])]
    invalid = [name for name, value in stages.items()
               if name not in missing and (type(value) is not str or value not in EFFORT_ORDER)]
    mismatches = [name for name, value in stages.items()
                  if name != "settings" and name not in missing and name not in invalid and value != effective]
    consistent = effective in EFFORT_ORDER and not mismatches and not missing and not invalid
    # Preserve the discrepancy class without echoing malformed response objects.
    stages = {name: (None if name in invalid else value) for name, value in stages.items()}
    row = dict(candidate or {})
    return {
        "schema": EFFORT_RECEIPT_SCHEMA,
        "role_id": row.get("role_id"),
        "candidate_id": row.get("candidate_id"),
        "provider": row.get("provider"),
        "provider_family": row.get("provider_family"),
        "client_product": row.get("client_product") or (row.get("catalog") or {}).get("client_product"),
        "route_id": row.get("route_id"),
        "model_requested": row.get("model_requested") or row.get("model"),
        "canonical_target_model": row.get("canonical_target_model"),
        "model_served": (response or {}).get("model_served"),
        "configured_effort": settings_requested,
        "requested_effort": dispatch.get("requested_effort"),
        "effective_effort": effective,
        "source_layer": dispatch.get("effort_source"),
        "provider_supported_efforts": list(row.get("supported_efforts") or []),
        "entitlement_ceiling": dispatch.get("entitlement_ceiling"),
        "risk_policy_floor": dispatch.get("risk_policy_floor"),
        "runtime_effort_ceiling": dispatch.get("runtime_effort_ceiling"),
        "role_minimum_effort": dispatch.get("role_minimum_effort"),
        "candidate_minimum_effort": dispatch.get("candidate_minimum_effort"),
        "allowed_efforts": list(dispatch.get("allowed_efforts") or []),
        "evidence_scope": "adapter-request-and-response-metadata-not-internal-model-compute",
        "clamp_reason": dispatch.get("clamp_reason"),
        "effort_source": dispatch.get("effort_source"),
        "stages": stages,
        "missing_stages": missing,
        "invalid_stages": invalid,
        "consistent": consistent,
        "mismatches": mismatches,
    }


def inherit_skill_privacy(source: str, declared: str | None = None) -> str:
    from .privacy_class import max_privacy_class, normalize_privacy_class

    inherited = SOURCE_PRIVACY.get(source, "D2")
    if not declared:
        return inherited
    return max_privacy_class(inherited, normalize_privacy_class(declared, default=inherited))


def coerce_max_selected(value: Any, default: int = 4) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("skills.max_selected must be an integer, not a boolean")
    return int(value)


def finalize_skill_state(
    selection: Mapping[str, Any],
    context_manifest: Mapping[str, Any] | None = None,
    *,
    egress: str = "cloud",
) -> dict[str, Any]:
    selected_rows = list(selection.get("selected") or [])
    receipt = dict(selection.get("receipt") or {})
    selected_ids = [str(row.get("id")) for row in selected_rows]
    included: list[str] = []
    truncated: list[str] = []
    rejected = list(receipt.get("rejected") or [])
    manifest = dict(context_manifest or {})
    selected_blocks = manifest.get("selected") or []
    excluded_blocks = manifest.get("excluded") or []
    included_sources = {
        str(block.get("source"))
        for block in selected_blocks
        if isinstance(block, Mapping) and block.get("kind") == "skill-guidance"
    }
    truncated_sources = {
        str(block.get("source"))
        for block in excluded_blocks
        if isinstance(block, Mapping) and block.get("kind") == "skill-guidance"
    }
    for skill_id in selected_ids:
        if skill_id in included_sources:
            included.append(skill_id)
        elif skill_id in truncated_sources:
            truncated.append(skill_id)
        elif context_manifest is None:
            included.append(skill_id)
        else:
            truncated.append(skill_id)
    actually_used = list(included)
    cloud_checked = True
    privacy_errors: list[str] = []
    for row in selected_rows:
        privacy = str(row.get("privacy_class") or inherit_skill_privacy(str(row.get("source") or "packaged"), row.get("declared_privacy_class")))
        if privacy in {"D2", "D3"} and egress == "cloud" and row.get("id") in included:
            privacy_errors.append(f"cloud-egress-blocked:{row.get('id')}:{privacy}")
            cloud_checked = False
            if row.get("id") in actually_used:
                actually_used = [item for item in actually_used if item != row.get("id")]
    state = {
        "schema": SKILL_STATE_SCHEMA,
        "discovered": int(selection.get("discovered_count") or receipt.get("discovered_count") or 0),
        "eligible": selected_ids,
        "selected": selected_ids,
        "included_in_context": included,
        "truncated": truncated,
        "actually_used": actually_used,
        "rejected": rejected,
        "privacy": {
            "inherited_from_source": True,
            "cloud_egress_checked": cloud_checked and not privacy_errors,
            "errors": privacy_errors,
        },
    }
    receipt["skill_state"] = state
    receipt["selected"] = [row for row in (receipt.get("selected") or []) if row.get("id") in actually_used]
    return {"receipt": receipt, "skill_state": state, "selected": [row for row in selected_rows if row.get("id") in actually_used]}
