# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
"""Runtime hard gates for MNCG, effort receipts, and skill-state truth."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import hashlib
import json
import re

from .minimum_change import assess_strategy, compile_contract  # PR #19 overlap: import only; do not edit that module.
from .model_policy import clamp_effort
from .settings_v2 import EFFORT_ORDER, resolve_effort

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
ACCEPTED_PLAN_SCHEMA = "iot-ai.accepted-plan-receipt.v1"
SKILL_STATE_SCHEMA = "iot-ai.skill-state.v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SYNTHETIC_DIGEST = re.compile(r"^([0-9a-f])\1{63}$")
PLAN_AUTHORITY_FIELDS = (
    "task_id",
    "task_revision",
    "acceptance_digest",
    "assessment_sha256",
    "contract_sha256",
    "context_digest",
    "policy_scope",
)
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
    policy_scope: str = "iot-ai-suite-standalone-task-store",
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
            "policy_scope": policy_scope,
        },
        "policy_scope": policy_scope,
    }


def _digest_ok(value: Any) -> bool:
    text = str(value or "")
    return bool(HEX64.fullmatch(text)) and not SYNTHETIC_DIGEST.fullmatch(text)


def _as_revision(value: Any, default: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _acceptance_digest(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _mncg_payload(accepted_plan: Mapping[str, Any] | None) -> dict[str, Any]:
    accepted = dict(accepted_plan or {})
    nested = accepted.get("mncg")
    if isinstance(nested, Mapping):
        return dict(nested)
    return accepted


def plan_authority_fields(accepted_plan: Mapping[str, Any] | None) -> dict[str, Any]:
    accepted = dict(accepted_plan or {})
    mncg = _mncg_payload(accepted)
    bind = dict(mncg.get("bind") or {}) if isinstance(mncg.get("bind"), Mapping) else {}
    source = {**mncg, **bind, **accepted}
    return {
        "task_id": str(source.get("task_id") or ""),
        "task_revision": _as_revision(source.get("task_revision") if source.get("task_revision") is not None else source.get("revision"), 0),
        "acceptance_digest": str(source.get("acceptance_digest") or _acceptance_digest(source.get("acceptance"))),
        "assessment_sha256": str(source.get("assessment_sha256") or ""),
        "contract_sha256": str(source.get("contract_sha256") or ""),
        "context_digest": str(source.get("context_digest") or ""),
        "policy_scope": str(source.get("policy_scope") or source.get("authority_basis") or "iot-ai-suite-standalone-task-store"),
        "selected_rung": source.get("selected_rung"),
        "decision": str(accepted.get("decision") or mncg.get("decision") or ""),
    }


def accepted_plan_receipt_path(user_home: Path, task_id: str, revision: int) -> Path:
    from .paths import data_root

    return data_root(user_home) / "accepted-plans" / f"{task_id}.r{revision}.json"


def persist_accepted_plan(
    user_home: Path,
    accepted_plan: Mapping[str, Any],
    *,
    policy_scope: str = "iot-ai-suite-standalone-task-store",
) -> dict[str, Any]:
    from .util import atomic_json

    fields = plan_authority_fields(accepted_plan)
    fields["policy_scope"] = fields["policy_scope"] or policy_scope
    receipt = {
        "schema": ACCEPTED_PLAN_SCHEMA,
        **{key: fields[key] for key in PLAN_AUTHORITY_FIELDS},
        "selected_rung": fields.get("selected_rung"),
        "decision": "accept",
    }
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    path = accepted_plan_receipt_path(user_home, str(receipt["task_id"]), int(receipt["task_revision"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, receipt)
    return receipt


def load_persisted_accepted_plan(user_home: Path, task_id: str, revision: int) -> dict[str, Any] | None:
    path = accepted_plan_receipt_path(user_home, task_id, revision)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema") != ACCEPTED_PLAN_SCHEMA:
        return None
    return payload


def accepted_plan_allows_implement(
    accepted_plan: Mapping[str, Any] | None,
    *,
    persisted: Mapping[str, Any] | None = None,
    user_home: Path | None = None,
) -> dict[str, Any]:
    """Pre-dispatch guard. Presented booleans are not execution authority."""

    accepted = dict(accepted_plan or {})
    accepted_mncg = _mncg_payload(accepted)
    errors: list[str] = []
    if accepted.get("decision") != "accept":
        errors.append("accepted-plan-not-accepted")
    fields = plan_authority_fields(accepted)
    if not accepted_mncg.get("valid"):
        errors.append("accepted-plan-mncg-missing")
    for name in PLAN_AUTHORITY_FIELDS:
        value = fields.get(name)
        if name in {"assessment_sha256", "contract_sha256"}:
            if not _digest_ok(value):
                errors.append(f"accepted-plan-evidence-missing:{name}")
        elif name in {"acceptance_digest", "context_digest"}:
            if not HEX64.fullmatch(str(value or "")):
                errors.append(f"accepted-plan-evidence-missing:{name}")
        elif name == "task_revision":
            if int(value or 0) < 1:
                errors.append("accepted-plan-evidence-missing:task_revision")
        elif not value:
            errors.append(f"accepted-plan-evidence-missing:{name}")
    stored = dict(persisted or {})
    if not stored and user_home is not None and fields.get("task_id"):
        loaded = load_persisted_accepted_plan(user_home, str(fields["task_id"]), int(fields["task_revision"] or 0))
        stored = dict(loaded or {})
    if not stored:
        errors.append("accepted-plan-not-persisted")
    else:
        stored_fields = plan_authority_fields(stored)
        for name in PLAN_AUTHORITY_FIELDS:
            if str(fields.get(name) or "") != str(stored_fields.get(name) or ""):
                errors.append(f"accepted-plan-persisted-mismatch:{name}")
        if stored.get("schema") not in {None, ACCEPTED_PLAN_SCHEMA} and stored.get("decision") not in {"accept", ""}:
            errors.append("accepted-plan-persisted-mismatch:decision")
    seen: set[str] = set()
    unique = []
    for item in errors:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    valid = not unique
    return {
        "valid": valid,
        "decision": "pass" if valid else "block",
        "errors": unique,
        "selected_rung": fields.get("selected_rung") or accepted_mncg.get("selected_rung"),
        "pre_dispatch": True,
        "persisted": bool(stored),
        "authority": fields if valid else None,
    }


def live_task_identity(
    current_task: Mapping[str, Any] | None,
    *,
    task_id: str = "",
    revision: int | None = None,
    acceptance: str | None = None,
    risk_class: str = "",
    context_digest: str | None = None,
    policy_scope: str | None = None,
) -> dict[str, Any]:
    """Current-task identity from a live snapshot only. Never copy accepted-plan fields."""

    row = dict(current_task or {})
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    identity = {
        "task_id": str(row.get("task_id") or row.get("id") or task_id or ""),
        "revision": _as_revision(row.get("revision") if row.get("revision") is not None else revision, 0),
        "acceptance_criteria": str(
            row["acceptance_criteria"] if "acceptance_criteria" in row else (acceptance or "")
        ),
        "risk_class": str(row.get("risk_class") or risk_class or ""),
        "policy_scope": str(row.get("policy_scope") or row.get("authority_basis") or policy_scope or ""),
    }
    if "context_digest" in row:
        identity["context_digest"] = row.get("context_digest")
    elif "context_digest" in raw:
        identity["context_digest"] = raw.get("context_digest")
    elif context_digest is not None:
        identity["context_digest"] = context_digest
    return identity


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
    current_task: Mapping[str, Any] | None = None,
    backend: Any = None,
    policy_scope: str | None = None,
) -> dict[str, Any]:
    """Hard-bind the writer to the accepted plan using current backend identity first."""

    accepted = dict(accepted_plan or {})
    accepted_mncg = _mncg_payload(accepted)
    if not accepted_mncg.get("valid"):
        return {
            "valid": False,
            "decision": "block",
            "errors": ["accepted-plan-mncg-missing"],
            "selected_rung": None,
        }
    current: dict[str, Any] = dict(current_task or {})
    if backend is not None:
        try:
            record = backend.snapshot(task_id)
            current = record.to_dict() if hasattr(record, "to_dict") else dict(record)
        except Exception:
            return {
                "valid": False,
                "decision": "block",
                "errors": ["minimum-change-current-task-unresolved"],
                "selected_rung": None,
            }
    current_id = str(current.get("task_id") or current.get("id") or task_id)
    current_revision = _as_revision(current.get("revision") if current.get("revision") is not None else revision)
    current_acceptance = str(current.get("acceptance_criteria") if "acceptance_criteria" in current else acceptance)
    if "context_digest" in current:
        current_context = current.get("context_digest")
    else:
        current_context = context_digest
    current_policy = str(current.get("policy_scope") or current.get("authority_basis") or policy_scope or "")
    accepted_id = str(accepted_mncg.get("task_id") or "")
    accepted_revision = _as_revision(accepted_mncg.get("task_revision"), 0)
    accepted_acceptance = str(accepted_mncg.get("acceptance") or "")
    accepted_acceptance_digest = str(accepted_mncg.get("acceptance_digest") or _acceptance_digest(accepted_acceptance))
    accepted_context = accepted_mncg.get("context_digest")
    accepted_policy = str(accepted_mncg.get("policy_scope") or accepted.get("policy_scope") or "")
    errors: list[str] = []
    if current_id != accepted_id:
        errors.append("minimum-change-task-id-mismatch")
        errors.append("minimum-change-authority-mismatch")
    if current_revision != accepted_revision:
        errors.append("minimum-change-task-revision-mismatch")
    if _acceptance_digest(current_acceptance) != accepted_acceptance_digest:
        errors.append("minimum-change-acceptance-mismatch")
        errors.append("minimum-change-authority-mismatch")
    if (accepted_context or current_context) and str(current_context or "") != str(accepted_context or ""):
        errors.append("minimum-change-context-mismatch")
    if accepted_policy and current_policy and accepted_policy != current_policy:
        errors.append("minimum-change-policy-scope-mismatch")
        errors.append("minimum-change-authority-mismatch")
    if errors:
        unique: list[str] = []
        seen: set[str] = set()
        for item in errors:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return {
            "valid": False,
            "decision": "block",
            "errors": unique,
            "selected_rung": None,
            "accepted_rung": accepted_mncg.get("selected_rung"),
            "current_task_id": current_id,
            "current_revision": current_revision,
        }
    impl = dict(implementation or {})
    recomputed = evaluate_minimum_change_gate(
        impl,
        goal=goal,
        task_id=current_id,
        risk_class=risk_class,
        acceptance=current_acceptance,
        context_digest=str(current_context) if current_context is not None else None,
        revision=current_revision,
    )
    errors = [item for item in list(recomputed.get("errors") or []) if item != "minimum-change-assessment-invalid" or not recomputed.get("valid")]
    if not recomputed.get("valid"):
        if "minimum-change-assessment-invalid" not in errors:
            errors.insert(0, "minimum-change-assessment-invalid")
    accepted_rung = accepted_mncg.get("selected_rung")
    if recomputed.get("selected_rung") != accepted_rung:
        errors.append("implementation-rung-diverges-from-accepted-plan")
        errors.append("minimum-change-assessment-drift")
    if accepted_mncg.get("contract_sha256") and recomputed.get("contract_sha256") != accepted_mncg.get("contract_sha256"):
        errors.append("implementation-contract-mismatch")
        errors.append("minimum-change-contract-mismatch")
    if accepted_mncg.get("assessment_sha256") and recomputed.get("assessment_sha256") != accepted_mncg.get("assessment_sha256"):
        errors.append("minimum-change-assessment-drift")
    accepted_norm = dict(accepted_mncg.get("normalized") or {})
    recomputed_norm = dict(recomputed.get("normalized") or {})
    for field in MNCG_BIND_FIELDS:
        if json.dumps(accepted_norm.get(field), sort_keys=True, default=str) != json.dumps(
            recomputed_norm.get(field), sort_keys=True, default=str
        ):
            errors.append("minimum-change-assessment-drift")
            errors.append(f"implementation-{field}-diverges")
    seen = set()
    unique_errors = []
    for item in errors:
        if item not in seen:
            seen.add(item)
            unique_errors.append(item)
    valid = not unique_errors and recomputed.get("valid") is True
    return {
        "valid": valid,
        "decision": "pass" if valid else "block",
        "errors": unique_errors,
        "selected_rung": recomputed.get("selected_rung"),
        "accepted_rung": accepted_rung,
        "assessment_sha256": recomputed.get("assessment_sha256"),
        "contract_sha256": recomputed.get("contract_sha256"),
        "context_digest": recomputed.get("context_digest"),
        "task_revision": recomputed.get("task_revision"),
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
    """Intersect provider, entitlement, role, risk, user and route effort. Empty set is unsatisfied."""

    row = dict(candidate or {})
    requested = str(row.get("requested_effort") or row.get("effective_effort") or node_effort or "medium")
    source = str(row.get("effort_source") or "candidate")
    supported = row.get("supported_efforts")
    resolved = resolve_effort(
        role_id=role_id or str(row.get("role_id") or ""),
        provider=str(row.get("provider") or ""),
        model=str(row.get("canonical_target_model") or row.get("model") or ""),
        routing=dict(routing or {}),
        requested=requested,
        supported=list(supported) if isinstance(supported, (list, tuple)) else None,
    )
    source = str(resolved.get("source_layer") or source)
    clamp_reason = resolved.get("clamp_reason") or row.get("effort_clamp_reason")
    ceiling = max_effort if max_effort in EFFORT_ORDER else "medium"
    entitlement_ceiling = str(resolved.get("entitlement_limit") or ceiling)
    if entitlement_ceiling in EFFORT_ORDER and EFFORT_ORDER.index(entitlement_ceiling) < EFFORT_ORDER.index(ceiling):
        ceiling = entitlement_ceiling
    ceiling_set = {item for item in EFFORT_ORDER if EFFORT_ORDER.index(item) <= EFFORT_ORDER.index(ceiling)}
    if isinstance(supported, (list, tuple)):
        supported_set = {item for item in supported if item in EFFORT_ORDER}
    else:
        supported_set = set(EFFORT_ORDER)
    route_caps = row.get("route_efforts") or row.get("capability_efforts")
    if isinstance(route_caps, (list, tuple)):
        supported_set &= {item for item in route_caps if item in EFFORT_ORDER}
    allowed = [item for item in EFFORT_ORDER if item in ceiling_set and item in supported_set]
    if resolved.get("decision") == "block":
        return {
            "decision": "block",
            "block_reason": resolved.get("block_reason") or "minimum-effort-unsatisfied",
            "requested_effort": requested,
            "configured_effort": resolved.get("configured_value") or requested,
            "effective_effort": None,
            "effort_source": source,
            "clamp_reason": clamp_reason,
            "entitlement_ceiling": ceiling,
            "allowed_efforts": allowed,
        }
    if not allowed:
        return {
            "decision": "block",
            "block_reason": "effort-policy-unsatisfied",
            "requested_effort": requested,
            "configured_effort": resolved.get("configured_value") or requested,
            "effective_effort": None,
            "effort_source": source,
            "clamp_reason": "empty effort-policy intersection",
            "entitlement_ceiling": ceiling,
            "allowed_efforts": [],
        }
    effective = str(resolved.get("effective_value") or requested)
    if effective not in allowed:
        capped, cap_reason = clamp_effort(effective, allowed)
        if capped not in allowed:
            return {
                "decision": "block",
                "block_reason": "effort-policy-unsatisfied",
                "requested_effort": requested,
                "configured_effort": resolved.get("configured_value") or requested,
                "effective_effort": None,
                "effort_source": source,
                "clamp_reason": cap_reason or "empty effort-policy intersection",
                "entitlement_ceiling": ceiling,
                "allowed_efforts": allowed,
            }
        clamp_reason = f"{clamp_reason}; {cap_reason}" if clamp_reason and cap_reason else (cap_reason or clamp_reason)
        effective = capped
    block_reason = row.get("effort_block_reason") or row.get("block_reason")
    if block_reason == "minimum-effort-unsatisfied":
        return {
            "decision": "block",
            "block_reason": "minimum-effort-unsatisfied",
            "requested_effort": requested,
            "configured_effort": resolved.get("configured_value") or requested,
            "effective_effort": effective,
            "effort_source": source,
            "clamp_reason": clamp_reason,
            "entitlement_ceiling": ceiling,
            "allowed_efforts": allowed,
        }
    return {
        "decision": "pass",
        "block_reason": None,
        "requested_effort": requested,
        "configured_effort": resolved.get("configured_value") or requested,
        "effective_effort": effective,
        "effort_source": source,
        "clamp_reason": clamp_reason,
        "entitlement_ceiling": ceiling,
        "allowed_efforts": allowed,
    }


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
    missing = [name for name in required_stages if stages.get(name) in {None, ""}]
    mismatches = [
        name
        for name, value in stages.items()
        if value not in {None, ""} and str(value) != effective
    ]
    consistent = not mismatches and not missing
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
        "model_served": row.get("model_served"),
        "configured_effort": settings_requested,
        "requested_effort": dispatch.get("requested_effort"),
        "effective_effort": effective,
        "source_layer": dispatch.get("effort_source"),
        "provider_supported_efforts": list(row.get("supported_efforts") or []),
        "entitlement_ceiling": dispatch.get("entitlement_ceiling"),
        "risk_policy_floor": dispatch.get("risk_policy_floor"),
        "clamp_reason": dispatch.get("clamp_reason"),
        "effort_source": dispatch.get("effort_source"),
        "stages": stages,
        "missing_stages": missing,
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
