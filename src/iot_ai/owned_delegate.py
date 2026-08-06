# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
"""Application-owned provider turn used by Meeting and Multi-Coder.

The provider sees only a prompt compiled from explicit goal, role, node,
context, tool and policy artifacts.  The runtime records the five decisions
that frameworks commonly hide: context, tool, validation, continuation and
persistence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .context_compiler import compile_context, validate_context_manifest
from .decision_receipts import build_turn_receipt, persist_turn_receipt
from .diagnostics import run_root
from .goal_contract import compile_goal_contract, validate_goal_contract
from .mesh import delegate
from .prompt_compiler import compile_prompt, validate_prompt
from .providers import eligible_routes
from .readiness import live_receipt
from .roles import ROLE_CATALOG
from .tool_router import validate_provider_binding
from .util import atomic_json, utc_now

_STAGE_ROLE_MAP = {
    "independent-opinion": "domain-architect",
    "critic": "security-challenger",
    "cross-critic": "security-challenger",
    "plan-synthesizer": "plan-synthesizer",
    "synthesizer": "plan-synthesizer",
    "independent-judge": "independent-judge",
    "reviewer": "quality-verifier",
    "implementer": "implementation-engineer",
    "implementation-engineer": "implementation-engineer",
    "performance-reviewer": "performance-engineer",
    "requirements-analyst": "requirements-analyst",
}


def _seat_parts(seat: str) -> tuple[str, str]:
    value = seat.strip().lower()
    if value.startswith("ollama@"):
        return "ollama", value.split("@", 1)[1]
    return value, "auto"


def _role_contract(role: str) -> dict[str, Any]:
    role_id = _STAGE_ROLE_MAP.get(role, role if role in ROLE_CATALOG else "domain-architect")
    return ROLE_CATALOG[role_id].to_dict()


def _node_id(stage: str, seat: str, run_id: str) -> str:
    digest = hashlib.sha256(f"{run_id}:{stage}:{seat}".encode("utf-8")).hexdigest()[:12]
    safe_stage = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in stage).strip("-")
    safe_seat = "".join(ch if ch.isalnum() or ch in "-_@:." else "-" for ch in seat).strip("-")
    return f"{safe_stage}-{safe_seat}-{digest}"


def _route_decision(user_home: Path, provider: str, model: str, role_id: str, effort: str) -> dict[str, Any]:
    evaluations: list[dict[str, Any]] = []
    for route in eligible_routes(user_home, provider, "auto"):
        receipt = live_receipt(user_home, str(route.get("route_id")), None if model == "auto" else model)
        evaluations.append(
            {
                "route_id": route.get("route_id"),
                "provider": provider,
                "configured_model": route.get("model"),
                "requested_model": model,
                "installed": True,
                "authenticated": receipt.get("authenticated") if receipt else None,
                "quota_state": receipt.get("quota_state") if receipt else "unknown",
                "live_ready": bool(receipt and receipt.get("status") == "pass"),
                "model_identity_verified": bool(receipt and receipt.get("model_identity_verified")),
                "receipt_expires_at": receipt.get("expires_at") if receipt else None,
                "readiness_evidence": "fresh-live-receipt" if receipt else "static-only",
            }
        )
    selected = evaluations[0] if evaluations else None
    return {
        "schema": "iot-ai.tool-decision.v1",
        "role_id": role_id,
        "requested_effort": effort,
        "selected_provider": provider if selected else None,
        "selected_model": model if selected else None,
        "selected_route": selected.get("route_id") if selected else None,
        "decision": "probe-and-dispatch" if selected else "block",
        "selection_reason": "explicit seat requested; runtime result must prove authentication and exact served model",
        "evaluations": evaluations,
        "created_at": utc_now(),
    }


def owned_delegate(
    user_home: Path,
    seat: str,
    mission: str,
    stage: str,
    *,
    run_id: str,
    role: str,
    timeout: int = 900,
    effort: str = "high",
    privacy_class: str = "D1",
    task_id: str | None = None,
    meeting_id: str | None = None,
    context_inputs: dict[str, Any] | None = None,
    delegate_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute one governed provider turn and persist all owned artifacts."""
    provider, model = _seat_parts(seat)
    correlation_id = run_id
    node_id = _node_id(stage, seat, run_id)
    role_contract = _role_contract(role)
    role_id = str(role_contract["role_id"])
    goal = compile_goal_contract(
        mission,
        risk_class="R2",
        privacy_class=privacy_class,
        explicit_constraints=(
            "Do not invent evidence, tools, provider identity or consensus.",
            "Return a concise evidence-bound result under the assigned specialist role.",
            "Treat unavailable authentication, quota, model identity or context as an explicit blocker.",
        ),
        explicit_success_criteria=(
            "The response is substantive and addresses the assigned mission.",
            "The exact served model and provider request receipt are recorded.",
            "Missing evidence and unresolved risk remain visible.",
        ),
    )
    goal_validation = validate_goal_contract(goal)
    if goal_validation["decision"] != "pass":
        raise ValueError("invalid goal contract: " + "; ".join(goal_validation["errors"]))
    goal_payload = goal.to_dict()
    node_contract = {
        "schema": "iot-ai.execution-node-contract.v1",
        "node_id": node_id,
        "stage": stage,
        "role_id": role_id,
        "mission": mission,
        "required_output_fields": list(role_contract.get("output_fields") or []),
        "read_scope": ["declared context blocks"],
        "write_scope": [],
        "side_effect_policy": "consultation-only unless a separately verified assignment grants writes",
        "provider_seat": seat,
        "effort": effort,
    }
    context = compile_context(
        goal_contract=goal_payload,
        role_contract=role_contract,
        node_contract=node_contract,
        inputs={"mission-input": mission, **(context_inputs or {})},
        privacy_class=privacy_class,
        token_budget=64_000 if effort in {"xhigh", "ultracode"} else 32_000,
        egress="cloud",
    )
    context_validation = validate_context_manifest(context)
    if context_validation["decision"] != "pass":
        return {
            "status": "blocked",
            "output": "",
            "failure_class": "context-policy",
            "provider": provider,
            "model_requested": model,
            "model_served": None,
            "runtime_context_blockers": context_validation["errors"],
            "seat_id": seat,
        }
    tool_decision = _route_decision(user_home, provider, model, role_id, effort)
    prompt = compile_prompt(
        goal_contract=goal_payload,
        role_contract=role_contract,
        node_contract=node_contract,
        context_manifest=context,
        policy={
            "schema": "iot-ai.agent-runtime-policy.v1",
            "prompt_owned": True,
            "context_owned": True,
            "tools_owned": True,
            "control_flow_owned": True,
            "no_silent_fallback": True,
            "no_self_acceptance": True,
            "same_digest_required_for_plan_acceptance": True,
            "private_chain_of_thought_not_requested": True,
        },
        tool_contract={
            "selected_provider": provider,
            "selected_model": model,
            "selected_route": tool_decision.get("selected_route"),
            "pre_dispatch_evaluations": tool_decision["evaluations"],
            "application_validates_provider_binding": True,
            "provider_failure_is_evidence": True,
        },
    )
    prompt_validation = validate_prompt(prompt)
    if prompt_validation["decision"] != "pass":
        raise ValueError("invalid prompt artifact: " + "; ".join(prompt_validation["errors"]))

    artifact_root = run_root(user_home, correlation_id) / "05_AGENT_RUNTIME" / node_id
    atomic_json(artifact_root / "goal-contract.json", goal_payload)
    atomic_json(artifact_root / "role-contract.json", role_contract)
    atomic_json(artifact_root / "node-contract.json", node_contract)
    atomic_json(artifact_root / "context-manifest.json", context.to_dict(include_payloads=True))
    atomic_json(artifact_root / "prompt-artifact.json", prompt.to_dict(include_text=False))
    atomic_json(artifact_root / "tool-decision-pre.json", tool_decision)

    invoke = delegate_fn or delegate
    # Test/legacy adapters may parse stage markers from plain text.  The real
    # runtime receives only the canonical owned envelope; injected adapters
    # receive the explicit mission first without changing the persisted hash.
    provider_visible_prompt = prompt.text if invoke is delegate else mission + "\n\nIOT-AI-PROMPT-ENVELOPE:\n" + prompt.text
    try:
        result = invoke(
            user_home,
            provider,
            provider_visible_prompt,
            stage,
            model=model,
            run_id=run_id,
            role=role_id,
            task_id=task_id,
            meeting_id=meeting_id,
            timeout=timeout,
            effort=effort,
            allow_fallback=False,
        )
    except Exception as exc:
        result = {
            "status": "failed",
            "output": "",
            "failure_class": type(exc).__name__,
            "error": str(exc),
            "provider": provider,
            "model_requested": model,
            "model_served": None,
            "request_id": None,
            "route_id": tool_decision.get("selected_route"),
        }

    result.setdefault("provider", provider)
    result.setdefault("model_requested", model)
    binding = validate_provider_binding(
        selected_provider=provider,
        selected_model=model,
        result=result,
    )
    output = str(result.get("output") or "")
    validation = {
        "schema": "iot-ai.validation-decision.v1",
        "status": result.get("status"),
        "non_empty_output": bool(output.strip()),
        "served_model_present": bool(result.get("model_served")),
        "provider_binding": binding,
        "substantive": result.get("status") == "pass" and len(output.strip()) >= 40 and binding["decision"] == "pass",
        "failure_class": result.get("failure_class"),
    }
    if result.get("status") == "pass" and binding["decision"] != "pass":
        result["status"] = "failed"
        result["failure_class"] = "provider-binding-mismatch"
        result["binding_errors"] = binding["errors"]
    continuation = {
        "schema": "iot-ai.continuation-decision.v1",
        "action": "continue" if validation["substantive"] else "stop-seat",
        "reason": "substantive-result" if validation["substantive"] else "seat-unsatisfied",
        "bounded": True,
    }
    persistence = {
        "schema": "iot-ai.persistence-decision.v1",
        "protected_artifacts": [
            str(artifact_root / "goal-contract.json"),
            str(artifact_root / "context-manifest.json"),
            str(artifact_root / "prompt-artifact.json"),
            str(artifact_root / "provider-result.json"),
        ],
        "public_export": "sanitized diagnostics only",
        "raw_private_context_in_public_export": False,
    }
    tool_decision_post = {
        **tool_decision,
        "selected_route": result.get("route_id") or tool_decision.get("selected_route"),
        "request_or_job_id": result.get("request_id"),
        "model_served": result.get("model_served"),
        "binding_validation": binding,
        "result_status": result.get("status"),
        "failure_class": result.get("failure_class"),
    }
    receipt = build_turn_receipt(
        correlation_id=correlation_id,
        graph_id=run_id,
        node_id=node_id,
        role_id=role_id,
        context_decision={
            "context_id": context.context_id,
            "context_digest": context.digest,
            "selected_blocks": [row.block_id for row in context.selected],
            "excluded_blocks": [row.block_id for row in context.excluded],
            "used_tokens": context.used_tokens,
            "token_budget": context.token_budget,
            "no_silent_truncation": context.no_silent_truncation,
        },
        tool_decision=tool_decision_post,
        validation_decision=validation,
        continuation_decision=continuation,
        persistence_decision=persistence,
    )
    decision_path = persist_turn_receipt(user_home, correlation_id, receipt)
    atomic_json(artifact_root / "provider-result.json", result)
    atomic_json(artifact_root / "tool-decision-post.json", tool_decision_post)

    result.update(
        {
            "seat_id": seat,
            "provider": provider,
            "agent_runtime": {
                "schema": "iot-ai.agent-runtime-turn.v1",
                "prompt_owned": True,
                "context_owned": True,
                "tools_owned": True,
                "control_flow_owned": True,
                "goal_contract_digest": goal.digest,
                "context_digest": context.digest,
                "prompt_sha256": prompt.sha256,
                "turn_decision_digest": receipt["digest"],
                "decision_receipt": str(decision_path),
                "artifact_root": str(artifact_root),
            },
        }
    )
    return result
