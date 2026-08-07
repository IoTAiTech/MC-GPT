# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Hash-bound checkpoints for pause/resume and deterministic replay."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .diagnostics import run_root
from .util import atomic_json, load_json, utc_now


def graph_digest(graph: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(graph, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def checkpoint_path(user_home: Path, correlation_id: str) -> Path:
    return run_root(user_home, correlation_id) / "07_CHECKPOINT" / "checkpoint.json"


def save_checkpoint(
    user_home: Path,
    correlation_id: str,
    *,
    graph: dict[str, Any],
    results: dict[str, Any],
    node_timings: dict[str, int],
    model_calls: int,
    tokens_used: int,
    status: str,
) -> Path:
    payload = {
        "schema": "iot-ai.execution-checkpoint.v1",
        "correlation_id": correlation_id,
        "graph_digest": graph_digest(graph),
        "results": results,
        "node_timings": node_timings,
        "model_calls": model_calls,
        "tokens_used": tokens_used,
        "status": status,
        "updated_at": utc_now(),
    }
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    payload["checkpoint_digest"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    path = checkpoint_path(user_home, correlation_id)
    atomic_json(path, payload)
    return path


def load_checkpoint(user_home: Path, correlation_id: str, graph: dict[str, Any]) -> dict[str, Any] | None:
    payload = load_json(checkpoint_path(user_home, correlation_id))
    if not isinstance(payload, dict):
        return None
    if payload.get("graph_digest") != graph_digest(graph):
        raise ValueError("checkpoint graph digest mismatch")
    body = {key: value for key, value in payload.items() if key != "checkpoint_digest"}
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    if payload.get("checkpoint_digest") != hashlib.sha256(canonical.encode("utf-8")).hexdigest():
        raise ValueError("checkpoint digest mismatch")
    return payload
