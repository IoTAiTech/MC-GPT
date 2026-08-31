# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.2 | Date: 2026-08-19
"""Official Task closed loop: iot-ai meeting, then iot-ai multi-coder."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .meeting import start as meeting_start
from .multicoder import run as multicoder_run
from .seat_selection import resolve_meeting_seats
from .task_validation import gate as validation_gate
from .task_validation import skip as validation_skip
from .tasks import add_work_unit


def meeting_id_of(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("meeting_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    meeting = payload.get("meeting")
    if isinstance(meeting, dict):
        for key in ("id", "meeting_id"):
            inner = meeting.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return None


def provider_call_count(payload: dict[str, Any] | None) -> int:
    if not isinstance(payload, dict):
        return 0
    value = payload.get("provider_calls")
    if isinstance(value, int) and value >= 0:
        return value
    total = 0
    for key in ("plans", "critiques", "plan_reviews", "final_reviews"):
        rows = payload.get(key)
        if isinstance(rows, list):
            total += len(rows)
    if payload.get("synthesis"):
        total += 1
    if total:
        return total
    providers = payload.get("providers")
    if isinstance(providers, list):
        return len(providers)
    return 0


def _seat_models(rows: list[Any]) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        seat = row.get("seat") or row.get("seat_id") or row.get("provider")
        requested = row.get("model_requested")
        served = row.get("model_served")
        if not seat and requested is None and served is None:
            continue
        models.append({
            "seat": seat,
            "model_requested": requested,
            "model_served": served,
            "status": row.get("status"),
        })
    return models


def run_meeting_then_multicoder(
    user_home: Path,
    task: dict[str, Any],
    *,
    providers: list[str],
    quorum: int = 2,
    implementer: str | None = None,
    test_profile: Path | None = None,
    test_argv: list[str] | None = None,
    cwd: Path | None = None,
    effort: str = "high",
    risk_class: str = "R1",
) -> dict[str, Any]:
    """Start the official meeting service, then run official multi-coder.

    Community stays on the standalone Suite store. This function never opens
    a ProductX PRCS SQLite file.
    """
    task_id = str(task.get("id") or task.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("task id is required")
    title = str(task.get("title") or task_id)
    seats = list(dict.fromkeys(str(item).strip() for item in providers if str(item).strip()))
    plan = resolve_meeting_seats(user_home, "auto", allow_missing_ollama=True)
    if plan.decision == "pass" and plan.resolved_seats:
        seats = list(plan.resolved_seats)
    if not seats:
        return {
            "schema": "iot-ai.task-meeting-multicoder.v1",
            "task_id": task_id,
            "decision": "needs-work",
            "reason": "no-meeting-or-multi-coder-seats",
            "meeting_id": None,
            "run_id": None,
            "provider_calls": 0,
            "executed": False,
            "canonical_pmd_prcs": False,
            "authority_basis": "iot-ai-suite-standalone-task-store",
        }
    meeting_quorum = min(max(1, quorum), len(seats))
    meeting = meeting_start(
        user_home,
        f"Full hybrid planning and adversarial review for Suite task {task_id}: {title}",
        seats,
        meeting_quorum,
        1,
        True,
        depth="deep",
        effort=effort,
        existing_task_id=task_id,
        risk_class=str(task.get("risk_class") or risk_class),
    )
    meeting_id = meeting_id_of(meeting)
    meeting_rows = []
    inner = meeting.get("meeting") if isinstance(meeting.get("meeting"), dict) else {}
    if isinstance(inner, dict):
        meeting_rows = list(inner.get("contributions") or [])
    elif isinstance(meeting.get("contributions"), list):
        meeting_rows = list(meeting["contributions"])

    gate = validation_gate(user_home, task_id, "execute")
    if gate.get("decision") != "pass":
        if str(gate.get("policy") or "optional") == "required":
            return {
                "schema": "iot-ai.task-meeting-multicoder.v1",
                "task_id": task_id,
                "decision": "needs-work",
                "reason": "task-validation-required",
                "meeting_id": meeting_id,
                "run_id": None,
                "meeting": meeting,
                "task_validation": gate,
                "provider_calls": 0,
                "executed": False,
                "canonical_pmd_prcs": False,
                "authority_basis": "iot-ai-suite-standalone-task-store",
            }
        add_work_unit(
            user_home,
            task_id,
            f"Implementation: {title}",
            "implementation",
            read_scope=[str(cwd or Path.cwd())],
            write_scope=[str(cwd or Path.cwd())],
        )
        validation_skip(
            user_home,
            task_id,
            subject="iot-ai-closed-loop",
            reason="Official meeting already executed; optional or recommended validation is advisory before multi-coder.",
            trigger_action="execute",
        )

    multi = multicoder_run(
        user_home,
        task_id=task_id,
        providers=list(dict.fromkeys(str(item).split("@", 1)[0] for item in seats)),
        quorum=min(max(1, quorum), len(seats)),
        implementer=implementer,
        test_profile=test_profile,
        test_argv=test_argv,
        cwd=cwd or Path.cwd(),
        effort=effort,
        risk_class=str(task.get("risk_class") or risk_class),
    )
    calls = provider_call_count(multi)
    return {
        "schema": "iot-ai.task-meeting-multicoder.v1",
        "task_id": task_id,
        "decision": multi.get("decision") if calls > 0 else "needs-work",
        "reason": None if calls > 0 else (multi.get("reason") or "zero-provider-calls"),
        "meeting_id": meeting_id,
        "run_id": multi.get("run_id"),
        "meeting": meeting,
        "multi_coder": multi,
        "meeting_seats": _seat_models(meeting_rows),
        "multi_coder_seats": _seat_models(list(multi.get("plans") or [])),
        "provider_calls": calls,
        "executed": calls > 0,
        "canonical_pmd_prcs": False,
        "authority_basis": "iot-ai-suite-standalone-task-store",
    }
