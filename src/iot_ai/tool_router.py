# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Explicit provider/tool eligibility and selection receipts."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

from .model_policy import clamp_effort
from .util import utc_now


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    candidate_id: str
    provider: str
    route_id: str
    model: str
    eligible: bool
    reasons: tuple[str, ...]
    live_ready: bool
    authenticated: bool | None
    quota_state: str
    model_identity_verified: bool
    cloud: bool
    effort_supported: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "provider": self.provider,
            "route_id": self.route_id,
            "model": self.model,
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "live_ready": self.live_ready,
            "authenticated": self.authenticated,
            "quota_state": self.quota_state,
            "model_identity_verified": self.model_identity_verified,
            "cloud": self.cloud,
            "effort_supported": list(self.effort_supported),
        }


def evaluate_candidate(
    candidate: dict[str, Any],
    *,
    requested_effort: str,
    privacy_class: str,
    require_live: bool = True,
) -> CandidateEvaluation:
    receipt = candidate.get("receipt") or {}
    reasons: list[str] = []
    live_ready = bool(candidate.get("live_ready"))
    authenticated = receipt.get("authenticated")
    model = str(candidate.get("model") or "")
    model_identity_verified = bool(receipt.get("model_identity_verified", bool(receipt.get("model_served"))))
    quota_state = str(receipt.get("quota_state") or ("blocked" if receipt.get("failure_class") == "quota" else "available"))
    supported = tuple(receipt.get("effort_supported") or ("low", "medium", "high", "xhigh"))
    _, clamp_reason = clamp_effort(requested_effort, supported)

    if require_live and not live_ready:
        reasons.append("live-readiness-receipt-missing-or-stale")
    if authenticated is False:
        reasons.append("authentication-failed")
    if quota_state in {"blocked", "quota-blocked", "exhausted"}:
        reasons.append("provider-quota-blocked")
    if not model or model.startswith("auto"):
        reasons.append("exact-model-identity-unresolved")
    if require_live and not model_identity_verified:
        reasons.append("served-model-identity-unverified")
    if privacy_class == "D3" and candidate.get("cloud", True):
        reasons.append("D3-cloud-egress-forbidden")
    if clamp_reason and not supported:
        reasons.append("no-supported-effort-level")

    return CandidateEvaluation(
        candidate_id=str(candidate.get("candidate_id") or ""),
        provider=str(candidate.get("provider") or ""),
        route_id=str(candidate.get("route_id") or ""),
        model=model,
        eligible=not reasons,
        reasons=tuple(reasons),
        live_ready=live_ready,
        authenticated=authenticated,
        quota_state=quota_state,
        model_identity_verified=model_identity_verified,
        cloud=bool(candidate.get("cloud", True)),
        effort_supported=supported,
    )


def build_tool_decision(
    candidates: Iterable[dict[str, Any]],
    *,
    role_id: str,
    requested_effort: str,
    privacy_class: str,
    selected_candidate_id: str | None = None,
    require_live: bool = True,
) -> dict[str, Any]:
    evaluations = [
        evaluate_candidate(
            candidate,
            requested_effort=requested_effort,
            privacy_class=privacy_class,
            require_live=require_live,
        )
        for candidate in candidates
    ]
    selected = next(
        (evaluation for evaluation in evaluations if evaluation.candidate_id == selected_candidate_id),
        None,
    )
    if selected is None:
        selected = next((evaluation for evaluation in evaluations if evaluation.eligible), None)
    decision = {
        "schema": "iot-ai.tool-decision.v1",
        "role_id": role_id,
        "requested_effort": requested_effort,
        "effective_effort": requested_effort,
        "privacy_class": privacy_class,
        "selected_candidate_id": selected.candidate_id if selected else None,
        "selected_provider": selected.provider if selected else None,
        "selected_model": selected.model if selected else None,
        "selected_route": selected.route_id if selected else None,
        "decision": "pass" if selected and selected.eligible else "block",
        "evaluations": [evaluation.to_dict() for evaluation in evaluations],
        "selection_reason": "highest-ranked eligible candidate from explicit same-role ladder" if selected else "no eligible candidate",
        "created_at": utc_now(),
    }
    canonical = json.dumps(decision, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    decision["digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return decision


def validate_provider_binding(
    *,
    selected_provider: str,
    selected_model: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    served_provider = str(result.get("provider") or "")
    served_model = str(result.get("model_served") or "")
    if served_provider != selected_provider:
        errors.append(f"provider binding mismatch: selected={selected_provider}, served={served_provider or 'missing'}")
    if not served_model:
        errors.append("served model is missing")
    elif selected_model and not selected_model.startswith("auto") and served_model != selected_model:
        errors.append(f"model binding mismatch: requested={selected_model}, served={served_model}")
    return {"decision": "pass" if not errors else "block", "errors": errors}
