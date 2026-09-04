# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
"""Runtime hard gates for MNCG, effort receipts, and skill-state truth."""
from __future__ import annotations

from typing import Any, Mapping

from .minimum_change import assess_strategy, compile_contract  # PR #19 overlap: import only; do not edit that module.
from .model_policy import clamp_effort
from .settings_v2 import EFFORT_ORDER, resolve_effort

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

    payload = dict(synthesis or {})
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
    contract = compile_runtime_mncg_contract(
        goal=goal,
        task_id=task_id,
        risk_class=risk_class,
        acceptance=acceptance,
        context_digest=context_digest,
        revision=revision,
    )
    result = assess_strategy(contract, assessment)
    return {
        "valid": result.get("decision") == "pass",
        "decision": result.get("decision"),
        "errors": list(result.get("errors") or []),
        "selected_rung": result.get("selected_rung"),
        "assessment_sha256": result.get("assessment_sha256"),
        "contract_sha256": result.get("contract_sha256"),
        "context_digest": context_digest,
        "acceptance": acceptance,
        "normalized": result.get("normalized"),
    }


def accepted_plan_allows_implement(accepted_plan: Mapping[str, Any] | None) -> dict[str, Any]:
    accepted = dict(accepted_plan or {})
    accepted_mncg = accepted.get("mncg") if isinstance(accepted.get("mncg"), Mapping) else accepted
    if accepted.get("decision") == "accept" and accepted_mncg.get("valid"):
        return {"valid": True, "decision": "pass", "errors": [], "selected_rung": accepted_mncg.get("selected_rung")}
    return {
        "valid": False,
        "decision": "block",
        "errors": ["accepted-plan-mncg-missing"],
        "selected_rung": accepted_mncg.get("selected_rung") if isinstance(accepted_mncg, Mapping) else None,
        "pre_dispatch": True,
    }


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
    """Hard-bind the writer to the accepted plan MNCG assessment."""

    accepted = dict(accepted_plan or {})
    accepted_mncg = accepted.get("mncg") if isinstance(accepted.get("mncg"), Mapping) else accepted
    if not accepted_mncg.get("valid"):
        return {
            "valid": False,
            "decision": "block",
            "errors": ["accepted-plan-mncg-missing"],
            "selected_rung": None,
        }
    impl = dict(implementation or {})
    frozen_digest = accepted_mncg.get("context_digest") or context_digest
    frozen_acceptance = str(accepted_mncg.get("acceptance") or acceptance)
    recomputed = evaluate_minimum_change_gate(
        impl,
        goal=goal,
        task_id=task_id,
        risk_class=risk_class,
        acceptance=frozen_acceptance,
        context_digest=frozen_digest,
        revision=revision,
    )
    errors = list(recomputed.get("errors") or [])
    accepted_rung = accepted_mncg.get("selected_rung")
    if recomputed.get("selected_rung") != accepted_rung:
        errors.append("implementation-rung-diverges-from-accepted-plan")
    if accepted_mncg.get("contract_sha256") and recomputed.get("contract_sha256") != accepted_mncg.get("contract_sha256"):
        errors.append("implementation-contract-mismatch")
    valid = not errors and recomputed.get("valid") is True
    return {
        "valid": valid,
        "decision": "pass" if valid else "block",
        "errors": errors,
        "selected_rung": recomputed.get("selected_rung"),
        "accepted_rung": accepted_rung,
        "assessment_sha256": recomputed.get("assessment_sha256"),
        "contract_sha256": recomputed.get("contract_sha256"),
        "normalized": recomputed.get("normalized"),
    }


def resolve_dispatch_effort(
    candidate: Mapping[str, Any] | None,
    *,
    node_effort: str,
    max_effort: str,
    role_id: str | None = None,
    routing: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Candidate effective_effort is the only dispatch source."""

    row = dict(candidate or {})
    requested = str(row.get("requested_effort") or row.get("effective_effort") or node_effort or "medium")
    source = str(row.get("effort_source") or "candidate")
    resolved = resolve_effort(
        role_id=role_id or str(row.get("role_id") or ""),
        provider=str(row.get("provider") or ""),
        model=str(row.get("model") or ""),
        routing=dict(routing or {}),
        requested=requested,
    )
    effective = str(resolved["effective_value"] or row.get("effective_effort") or requested)
    clamp_reason = resolved.get("clamp_reason") or row.get("effort_clamp_reason")
    source = str(resolved.get("source_layer") or source)
    if resolved.get("decision") == "block":
        return {
            "decision": "block",
            "block_reason": resolved.get("block_reason") or "minimum-effort-unsatisfied",
            "requested_effort": requested,
            "effective_effort": effective,
            "effort_source": source,
            "clamp_reason": clamp_reason,
        }
    capped, cap_reason = clamp_effort(effective, [item for item in EFFORT_ORDER if EFFORT_ORDER.index(item) <= EFFORT_ORDER.index(max_effort if max_effort in EFFORT_ORDER else "medium")])
    if cap_reason:
        clamp_reason = f"{clamp_reason}; {cap_reason}" if clamp_reason else cap_reason
        effective = capped
    block_reason = row.get("effort_block_reason") or row.get("block_reason")
    if block_reason == "minimum-effort-unsatisfied":
        return {
            "decision": "block",
            "block_reason": "minimum-effort-unsatisfied",
            "requested_effort": requested,
            "effective_effort": effective,
            "effort_source": source,
            "clamp_reason": clamp_reason,
        }
    return {
        "decision": "pass",
        "block_reason": None,
        "requested_effort": requested,
        "effective_effort": effective,
        "effort_source": source,
        "clamp_reason": clamp_reason,
    }


def build_effort_receipt(
    *,
    settings_requested: str | None,
    candidate: Mapping[str, Any],
    dispatch: Mapping[str, Any],
    tool_decision: Mapping[str, Any] | None,
    adapter_request_effort: str | None,
    response: Mapping[str, Any] | None,
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
    mismatches = [
        name
        for name, value in stages.items()
        if value not in {None, ""} and str(value) != effective
    ]
    return {
        "schema": EFFORT_RECEIPT_SCHEMA,
        "requested_effort": dispatch.get("requested_effort"),
        "effective_effort": effective,
        "effort_source": dispatch.get("effort_source"),
        "clamp_reason": dispatch.get("clamp_reason"),
        "stages": stages,
        "consistent": not mismatches,
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
