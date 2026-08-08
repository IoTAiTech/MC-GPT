# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Unified health, version, coder, model, effort and workflow status."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .conversation_state import load_state
from .diagnostics import run_root
from .eu_ai_act import runtime_compliance_status
from .european_compliance import BASELINES as EU_REGULATORY_BASELINES
from .installer import HOSTS, status as package_status
from .logging_config import log_locations
from .model_policy import EFFORT_ORDER
from .providers import load as load_routes, static_status
from .readiness import live_receipt, probe_routes
from .report import data as report_data
from .settings import load as load_settings
from .suite_version import MC_GPT_VERSION, SUITE_VERSION
from .workspace import connect_read, one, rows
from .worktrees import list_runs as worktree_runs
from .identity_migration import status as identity_migration_status


def _status_from_score(score: float | None, *, pass_at: float = 90.0) -> str:
    if score is None:
        return "no-data"
    if score >= pass_at:
        return "pass"
    if score >= 60:
        return "degraded"
    return "blocked"


def _workflow_scores(user_home: Path) -> dict[str, Any]:
    connection = connect_read(user_home)
    if connection is None:
        return {
            name: {"score": None, "status": "no-data", "basis": [], "hard_gate": None}
            for name in ("meeting", "mesh", "multi-coder", "task-execution", "graph")
        }
    meeting = one(connection, "SELECT * FROM meetings ORDER BY updated_at DESC LIMIT 1")
    audit = one(connection, "SELECT * FROM audits ORDER BY created_at DESC LIMIT 1")
    task = one(connection, "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT 1")
    graph = one(connection, "SELECT * FROM graph_runs ORDER BY updated_at DESC LIMIT 1")
    contributions = rows(connection, "SELECT * FROM contributions ORDER BY created_at DESC LIMIT 100")
    graph_nodes = rows(
        connection,
        "SELECT * FROM graph_nodes WHERE graph_id=? ORDER BY created_at" if graph else "SELECT * FROM graph_nodes WHERE 1=0",
        (graph["id"],) if graph else (),
    )
    connection.close()

    meeting_score: float | None = None
    meeting_basis: list[str] = []
    meeting_hard_gate = None
    if meeting:
        substantive = int(meeting.get("substantive_seats") or 0)
        quorum = max(1, int(meeting.get("quorum") or 1))
        participation = min(1.0, substantive / quorum)
        accepted = meeting.get("status") == "accepted" and meeting.get("final_decision") == "accept"
        meeting_score = round(55 * participation + 20 * bool(meeting.get("synthesis")) + 25 * accepted, 1)
        meeting_hard_gate = "pass" if accepted else "plan-not-accepted"
        meeting_basis = [
            f"substantive={substantive}/{quorum}",
            f"status={meeting.get('status')}",
            f"decision={meeting.get('final_decision')}",
        ]

    total = len(contributions)
    successful = sum(1 for row in contributions if row.get("status") in {"pass", "completed"})
    exact_models = sum(1 for row in contributions if row.get("model_served"))
    failures = sum(1 for row in contributions if row.get("failure_class"))
    mesh_score = (
        round(50 * successful / total + 35 * exact_models / total + 15 * (1 - failures / total), 1)
        if total
        else None
    )

    multi_score = float(audit.get("gate_score")) if audit else None
    task_score = float(task.get("task_progress") or 0) if task else None
    task_hard_gate = None
    if task:
        task_hard_gate = "pass" if task.get("status") in {"awaiting_founder", "completed", "closed"} else "open"

    graph_score: float | None = None
    graph_basis: list[str] = []
    graph_hard_gate = None
    if graph:
        total_nodes = len(graph_nodes)
        passed_nodes = sum(1 for row in graph_nodes if row.get("status") == "pass")
        required_failures = sum(1 for row in graph_nodes if row.get("required") and row.get("status") != "pass")
        graph_score = round(100 * passed_nodes / total_nodes, 1) if total_nodes else 0.0
        graph_hard_gate = "pass" if graph.get("status") == "pass" and required_failures == 0 else "required-node-failure"
        graph_basis = [
            f"nodes={passed_nodes}/{total_nodes}",
            f"required_failures={required_failures}",
            f"parallel_efficiency={graph.get('parallel_efficiency')}",
        ]

    return {
        "meeting": {
            "score": meeting_score,
            "status": "pass" if meeting_hard_gate == "pass" else _status_from_score(meeting_score),
            "basis": meeting_basis,
            "hard_gate": meeting_hard_gate,
        },
        "mesh": {
            "score": mesh_score,
            "status": _status_from_score(mesh_score, pass_at=85),
            "basis": [f"successful={successful}/{total}", f"exact-model={exact_models}/{total}", f"failures={failures}/{total}"],
            "hard_gate": "pass" if total and exact_models == successful and successful > 0 else "incomplete-model-evidence",
        },
        "multi-coder": {
            "score": multi_score,
            "status": str(audit.get("decision")) if audit else "no-data",
            "basis": [f"audit={audit.get('id')}" if audit else "no audit"],
            "hard_gate": "pass" if audit and audit.get("decision") == "approve_technical" else "audit-not-approved" if audit else None,
        },
        "task-execution": {
            "score": task_score,
            "status": str(task.get("status")) if task else "no-data",
            "basis": [f"status={task.get('status')}", f"progress={task_score}", f"decision={task.get('final_decision')}"] if task else [],
            "hard_gate": task_hard_gate,
        },
        "graph": {
            "score": graph_score,
            "status": "pass" if graph_hard_gate == "pass" else _status_from_score(graph_score),
            "basis": graph_basis,
            "hard_gate": graph_hard_gate,
        },
    }



def _agent_runtime_status(user_home: Path) -> dict[str, Any]:
    connection = connect_read(user_home)
    if connection is None:
        return {
            "status": "no-data",
            "prompt_owned": None,
            "context_owned": None,
            "tools_owned": None,
            "control_flow_owned": None,
            "decision_receipt_completeness": None,
        }
    graph = one(connection, "SELECT * FROM graph_runs ORDER BY updated_at DESC LIMIT 1")
    if not graph:
        connection.close()
        return {
            "status": "no-data",
            "prompt_owned": None,
            "context_owned": None,
            "tools_owned": None,
            "control_flow_owned": None,
            "decision_receipt_completeness": None,
        }
    nodes = rows(connection, "SELECT * FROM graph_nodes WHERE graph_id=? ORDER BY created_at", (graph["id"],))
    connection.close()
    root = run_root(user_home, str(graph["correlation_id"]))
    agent_nodes = [row for row in nodes if row.get("node_type") == "agent"]
    prompt_files = list((root / "08_AGENT_RUNTIME").glob("*/prompt-artifact.json")) if root.exists() else []
    context_files = list((root / "08_AGENT_RUNTIME").glob("*/context-manifest.json")) if root.exists() else []
    decision_files = list((root / "06_DECISIONS").glob("*.json")) if root.exists() else []
    tool_decisions = 0
    context_tokens = 0
    excluded_blocks = 0
    for file in decision_files:
        try:
            receipt = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(receipt.get("tool_decision"), dict) and receipt["tool_decision"]:
            tool_decisions += 1
    for file in context_files:
        try:
            context = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        context_tokens += int(context.get("used_tokens") or 0)
        excluded_blocks += len(context.get("excluded") or [])
    checkpoint = {}
    checkpoint_file = root / "07_CHECKPOINT" / "checkpoint.json"
    if checkpoint_file.exists():
        try:
            checkpoint = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            checkpoint = {"status": "invalid"}
    total_nodes = len(nodes)
    agent_count = len(agent_nodes)
    prompt_owned = len(prompt_files) == agent_count if agent_count else True
    context_owned = len(context_files) == agent_count if agent_count else True
    control_flow_owned = len(decision_files) == total_nodes if total_nodes else False
    tools_owned = tool_decisions == total_nodes if total_nodes else False
    completeness = round(len(decision_files) / total_nodes, 4) if total_nodes else None
    status = "pass" if all((prompt_owned, context_owned, tools_owned, control_flow_owned)) else "degraded"
    return {
        "status": status,
        "graph_id": graph.get("id"),
        "correlation_id": graph.get("correlation_id"),
        "prompt_owned": prompt_owned,
        "context_owned": context_owned,
        "tools_owned": tools_owned,
        "control_flow_owned": control_flow_owned,
        "agent_nodes": agent_count,
        "all_nodes": total_nodes,
        "prompt_artifacts": len(prompt_files),
        "context_manifests": len(context_files),
        "turn_decision_receipts": len(decision_files),
        "decision_receipt_completeness": completeness,
        "context_tokens_selected": context_tokens,
        "context_blocks_excluded_explicitly": excluded_blocks,
        "checkpoint_status": checkpoint.get("status"),
        "checkpoint_digest": checkpoint.get("checkpoint_digest"),
    }

def unified_status(user_home: Path, *, live: bool = False, window: str = "24h") -> dict[str, Any]:
    normalized_window = "1d" if window in {"24h", "1day"} else window
    live_results = probe_routes(user_home) if live else []
    routes: list[dict[str, Any]] = []
    for route in load_routes(user_home).get("routes", []):
        static = static_status(route)
        receipt = live_receipt(user_home, str(route.get("route_id")))
        routes.append(
            {
                "route_id": route.get("route_id"),
                "provider": route.get("provider"),
                "kind": route.get("kind"),
                "auth_mode": route.get("auth_mode"),
                "installed": static.get("installed"),
                "authenticated": receipt.get("authenticated") if receipt else None,
                "live_ready": bool(receipt and receipt.get("status") == "pass" and receipt.get("model_identity_verified")),
                "model_requested": receipt.get("model_requested") if receipt else route.get("model"),
                "model_served": receipt.get("model_served") if receipt else None,
                "effort_supported": receipt.get("effort_supported", list(EFFORT_ORDER)) if receipt else list(EFFORT_ORDER),
                "latency_ms": receipt.get("latency_ms") if receipt else None,
                "failure_class": receipt.get("failure_class") if receipt else None,
                "receipt_expires_at": receipt.get("expires_at") if receipt else None,
                "status_basis": "live-receipt" if receipt else "static-only",
            }
        )
    package = package_status(user_home)
    active_settings = load_settings(user_home)
    effective_profile = str(active_settings.get("orchestration", {}).get("active_profile", "balanced"))
    profile_values = active_settings.get("orchestration", {}).get("profiles", {}).get(effective_profile, {})
    coders = [
        {
            "coder": host,
            "executable": shutil.which(host),
            "available": bool(shutil.which(host)),
            "suite_state": package.get("hosts", {}).get(host) if isinstance(package.get("hosts"), dict) else None,
        }
        for host in HOSTS
    ]
    return {
        "schema": "iot-ai.status.v4",
        "suite": {"version": SUITE_VERSION, "mc_gpt_version": MC_GPT_VERSION, "package": package},
        "coders": coders,
        "providers": routes,
        "effective_profile": {"name": effective_profile, "settings": profile_values},
        "workflow_scores": _workflow_scores(user_home),
        "agent_runtime": _agent_runtime_status(user_home),
        "autopilot": {
            "settings": active_settings.get("autopilot", {}),
            "conversation": load_state(user_home, "default"),
            "notice": "Conversation state contains operator-visible identifiers and checkpoint paths only; no private chain-of-thought is stored.",
        },
        "eu_ai_act": runtime_compliance_status(user_home),
        "eu_regulatory_baselines": EU_REGULATORY_BASELINES,
        "logs": log_locations(user_home),
        "activity": report_data(user_home, normalized_window),
        "worktrees": worktree_runs(user_home),
        "brand_identity_migration": identity_migration_status(user_home),
        "live_probe_performed": live,
        "live_probe_results": live_results,
        "window": normalized_window,
        "score_notice": (
            "Workflow scores are evidence-derived indicators; hard gates override numeric scores. "
            "EU AI Act controls are reported control-by-control and never as a compliance percentage or certification."
        ),
    }
