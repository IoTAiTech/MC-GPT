# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Deterministic control-flow and convergence decisions around model calls."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ControlFlowState:
    graph_id: str
    status: str = "running"
    completed_nodes: list[str] = field(default_factory=list)
    failure_fingerprints: dict[str, int] = field(default_factory=dict)
    finding_digests: list[str] = field(default_factory=list)
    no_new_finding_rounds: int = 0
    model_calls: int = 0
    tokens_used: int = 0
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "iot-ai.control-flow-state.v1", **asdict(self)}


def result_fingerprint(value: dict[str, Any]) -> str:
    body = {
        "status": value.get("status"),
        "failure_class": value.get("failure_class"),
        "missing_output_fields": value.get("missing_output_fields"),
        "provider": value.get("provider"),
        "model_served": value.get("model_served"),
        "output": value.get("parsed") or value.get("output"),
    }
    return hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def finding_digest(value: dict[str, Any]) -> str | None:
    output = value.get("parsed") or value.get("output") or {}
    if not isinstance(output, dict):
        return None
    findings = output.get("findings") or output.get("new_risks") or output.get("dissent")
    if not findings:
        return None
    return hashlib.sha256(
        json.dumps(findings, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def continuation_decision(
    *,
    state: ControlFlowState,
    node_id: str,
    node_required: bool,
    result: dict[str, Any],
    token_budget: int,
    max_model_calls: int,
    wall_clock_seconds: int,
    max_identical_failures: int = 2,
    max_no_new_finding_rounds: int = 2,
) -> dict[str, Any]:
    """Choose continue/stop/pause using application-owned rules."""
    fingerprint = result_fingerprint(result)
    state.failure_fingerprints[fingerprint] = state.failure_fingerprints.get(fingerprint, 0) + 1
    digest = finding_digest(result)
    if digest and digest not in state.finding_digests:
        state.finding_digests.append(digest)
        state.no_new_finding_rounds = 0
    elif result.get("status") == "pass":
        state.no_new_finding_rounds += 1

    action = "continue"
    reason = "node-completed"
    if node_required and result.get("status") != "pass":
        action, reason = "stop", "required-node-failed"
    elif state.failure_fingerprints[fingerprint] >= max_identical_failures and result.get("status") != "pass":
        action, reason = "stop", "repeated-identical-failure"
    elif state.tokens_used > token_budget or state.model_calls > max_model_calls:
        action, reason = "stop", "model-budget"
    elif state.elapsed_ms > wall_clock_seconds * 1000:
        action, reason = "stop", "wall-clock-budget"
    elif state.no_new_finding_rounds >= max_no_new_finding_rounds and "review" in node_id:
        action, reason = "stop-revision", "no-new-material-findings"

    return {
        "schema": "iot-ai.continuation-decision.v1",
        "action": action,
        "reason": reason,
        "failure_fingerprint": fingerprint,
        "identical_failure_count": state.failure_fingerprints[fingerprint],
        "no_new_finding_rounds": state.no_new_finding_rounds,
        "tokens_used": state.tokens_used,
        "model_calls": state.model_calls,
        "elapsed_ms": state.elapsed_ms,
    }
