# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Five-decision receipts for every material agent/runtime turn."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .diagnostics import run_root
from .util import atomic_json, utc_now

_REQUIRED = (
    "context_decision",
    "tool_decision",
    "validation_decision",
    "continuation_decision",
    "persistence_decision",
)


def build_turn_receipt(
    *,
    correlation_id: str,
    graph_id: str,
    node_id: str,
    role_id: str,
    context_decision: dict[str, Any],
    tool_decision: dict[str, Any],
    validation_decision: dict[str, Any],
    continuation_decision: dict[str, Any],
    persistence_decision: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema": "iot-ai.turn-decision-receipt.v1",
        "correlation_id": correlation_id,
        "graph_id": graph_id,
        "node_id": node_id,
        "role_id": role_id,
        "context_decision": context_decision,
        "tool_decision": tool_decision,
        "validation_decision": validation_decision,
        "continuation_decision": continuation_decision,
        "persistence_decision": persistence_decision,
        "created_at": utc_now(),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    payload["digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def validate_turn_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for key in _REQUIRED:
        value = receipt.get(key)
        if not isinstance(value, dict) or not value:
            errors.append(f"missing or empty {key}")
    body = {key: value for key, value in receipt.items() if key != "digest"}
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    if receipt.get("digest") != hashlib.sha256(canonical.encode("utf-8")).hexdigest():
        errors.append("decision receipt digest mismatch")
    return {"decision": "pass" if not errors else "block", "errors": errors, "node_id": receipt.get("node_id")}


def persist_turn_receipt(user_home: Path, correlation_id: str, receipt: dict[str, Any]) -> Path:
    validation = validate_turn_receipt(receipt)
    if validation["decision"] != "pass":
        raise ValueError("; ".join(validation["errors"]))
    path = run_root(user_home, correlation_id) / "06_DECISIONS" / f"{receipt['node_id']}.json"
    atomic_json(path, receipt)
    return path
