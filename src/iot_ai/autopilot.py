# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Conversation-aware closed-loop Task -> Meeting -> Multi-Coder orchestration."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .audit import audit_task
from .autopilot_reporting import build_report, write_report_bundle
from .conversation_state import load_state, save_state
from .intent_router import compile_intent
from .meeting import approve as approve_meeting
from .meeting import start as start_meeting
from .multicoder import run as run_multicoder
from .readiness import provider_candidates
from .seat_selection import resolve_meeting_seats
from .task_backends import (
    EXECUTION_ELIGIBLE_STATES,
    TERMINAL_TECHNICAL_STATES,
    ExternalBackendUnavailable,
    SuiteTaskBackend,
    TaskBackend,
    TaskRecord,
    select_backend,
)
from .task_validation import approve as approve_validation
from .task_validation import review as review_validation
from .tasks import create as create_task
from .tasks import show as show_task
from .util import utc_now

AUTOPILOT_TERMINALS = {
    "COMPLETE",
    "TECHNICAL_COMPLETE_AWAITING_FOUNDER",
    "EXTERNALLY_BLOCKED",
    "AUTHORITY_BLOCKED",
    "SAFETY_BLOCKED",
    "BUDGET_EXHAUSTED",
    "FAILED_TERMINAL",
    "CANCELLED",
    "NEEDS_WORK",
}
PRIORITY_ORDER = {"critical": 4, "high": 3, "normal": 2, "medium": 2, "low": 1}
WIP_LIMITS = {"critical": 4, "high": 2, "normal": 1, "medium": 1, "low": 1}


@dataclass(slots=True)
class AutopilotHooks:
    backend_factory: Callable[[Path, dict[str, Any]], TaskBackend] = select_backend
    validation_review: Callable[..., dict[str, Any]] = review_validation
    validation_approve: Callable[..., dict[str, Any]] = approve_validation
    meeting_start: Callable[..., dict[str, Any]] = start_meeting
    meeting_approve: Callable[..., dict[str, Any]] = approve_meeting
    multicoder_run: Callable[..., dict[str, Any]] = run_multicoder
    task_audit: Callable[..., dict[str, Any]] = audit_task


def _failure_fingerprint(value: dict[str, Any]) -> str:
    body = {
        "decision": value.get("decision"),
        "reason": value.get("reason"),
        "tests": [
            {"tier": row.get("tier"), "exit_code": row.get("exit_code"), "sha256": row.get("sha256")}
            for row in value.get("tests", [])
            if isinstance(row, dict) and row.get("decision") != "pass"
        ],
        "plans": [
            {"seat": row.get("seat_id"), "status": row.get("status"), "failure": row.get("failure_class")}
            for row in value.get("plans", [])
            if isinstance(row, dict) and not row.get("substantive")
        ],
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _extract_providers(task_id: str, iteration: int, value: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups = ("plans", "critiques", "plan_reviews", "final_reviews")
    for group in groups:
        for item in value.get(group, []) or []:
            if not isinstance(item, dict):
                continue
            review = item.get("review") if isinstance(item.get("review"), dict) else {}
            rows.append({
                "task_id": task_id,
                "iteration": iteration,
                "seat": item.get("seat_id") or item.get("seat"),
                "provider": item.get("provider"),
                "model_requested": item.get("model_requested"),
                "model_served": item.get("model_served"),
                "status": item.get("status"),
                "substantive": bool(item.get("substantive")),
                "failure_class": item.get("failure_class"),
                "decision": review.get("decision") or group,
            })
    return rows


def _meeting_provider_rows(task_id: str, iteration: int, value: dict[str, Any]) -> list[dict[str, Any]]:
    meeting = value.get("meeting") if isinstance(value.get("meeting"), dict) else {}
    contributions = meeting.get("contributions") or []
    rows = []
    for item in contributions:
        if not isinstance(item, dict):
            continue
        rows.append({
            "task_id": task_id,
            "iteration": iteration,
            "seat": item.get("seat"),
            "provider": str(item.get("seat") or "").split("@", 1)[0],
            "model_requested": item.get("model_requested"),
            "model_served": item.get("model_served"),
            "status": item.get("status"),
            "substantive": bool(item.get("status") == "pass" and item.get("model_served") and len(str(item.get("text") or "")) >= 40),
            "failure_class": item.get("failure_class"),
            "decision": item.get("kind"),
        })
    return rows


def _infer_test_argv(cwd: Path) -> list[str] | None:
    if (cwd / "tests").is_dir() and ((cwd / "pyproject.toml").is_file() or (cwd / "pytest.ini").is_file()):
        return [sys.executable, "-m", "pytest", "-q"]
    if (cwd / "package.json").is_file():
        return ["npm", "test", "--", "--runInBand"]
    return None


def _schedule(records: list[TaskRecord], max_total: int) -> tuple[list[TaskRecord], list[TaskRecord]]:
    counters: dict[str, int] = {}
    selected: list[TaskRecord] = []
    deferred: list[TaskRecord] = []
    ordered = sorted(records, key=lambda row: (-PRIORITY_ORDER.get(row.priority, 2), row.task_id))
    for record in ordered:
        bucket = record.priority if record.priority in WIP_LIMITS else "normal"
        if len(selected) < max_total and counters.get(bucket, 0) < WIP_LIMITS[bucket]:
            selected.append(record)
            counters[bucket] = counters.get(bucket, 0) + 1
        else:
            deferred.append(record)
    return selected, deferred


def _schedule_waves(records: list[TaskRecord], max_parallel: int) -> list[list[TaskRecord]]:
    """Create bounded WIP waves while ensuring every selected task is eventually scheduled."""
    remaining = list(records)
    waves: list[list[TaskRecord]] = []
    while remaining:
        wave, deferred = _schedule(remaining, max(1, max_parallel))
        if not wave:
            # Defensive progress guarantee; priority limits must never create an endless scheduler loop.
            wave, deferred = [remaining[0]], remaining[1:]
        waves.append(wave)
        remaining = deferred
    return waves


def _task_acceptance(task_id: str, user_home: Path) -> dict[str, Any]:
    """Return evidence-bounded acceptance telemetry without inventing AC passes."""
    try:
        task = show_task(user_home, task_id)["task"]
    except Exception:
        return {"passed": 0, "total": 0, "declared_total": 0, "status": "unknown", "basis": "unavailable"}
    criteria_text = str(task.get("acceptance_criteria") or "").strip()
    declared_total = len([line for line in criteria_text.splitlines() if line.strip()]) if criteria_text else 0
    audits = task.get("audits") or []
    latest = audits[-1] if audits else {}
    gates = json.loads(latest.get("gates_json") or "{}") if isinstance(latest, dict) and latest.get("gates_json") else {}
    if gates:
        passed = sum(1 for value in gates.values() if value is True)
        return {
            "passed": passed,
            "total": len(gates),
            "declared_total": declared_total,
            "status": latest.get("decision") or "audited",
            "basis": "technical-audit-gates",
        }
    return {
        "passed": 0,
        "total": declared_total,
        "declared_total": declared_total,
        "status": "not-audited",
        "basis": "declared-criteria-not-machine-scored",
    }


def _meeting_ok(value: dict[str, Any]) -> bool:
    meeting = value.get("meeting") if isinstance(value.get("meeting"), dict) else {}
    explicit_pass = value.get("decision") == "pass"
    accepted_state = (
        meeting.get("status") in {"awaiting-user-decision", "approved"}
        and meeting.get("final_decision") == "accepted_by_required_seats"
    )
    hard_gates = value.get("hard_gates") or {}
    gates_ok = not hard_gates or all(bool(item) for item in hard_gates.values())
    return bool((explicit_pass or accepted_state) and gates_ok)


def _task_result_base(record: TaskRecord) -> dict[str, Any]:
    return {
        "task_id": record.task_id,
        "backend": record.backend,
        "authority_basis": record.authority_basis,
        "priority": record.priority,
        "title": record.title,
        "initial_state": record.status,
        "acceptance": {"passed": 0, "total": 0, "status": "not-evaluated"},
        "meeting": {"status": "not-run"},
        "multi_coder": {"status": "not-run"},
        "tests": {"decision": "not-run", "summary": "not-run"},
        "repairs": 0,
        "final_state": None,
        "blocker_next_actor": None,
        "evidence": [],
    }


def _process_suite_task(
    *,
    user_home: Path,
    record: TaskRecord,
    intent: dict[str, Any],
    hooks: AutopilotHooks,
    cwd: Path,
    test_argv: list[str] | None,
    providers: list[str],
    quorum: int,
    apply: bool,
    iterations: list[dict[str, Any]],
    provider_rows: list[dict[str, Any]],
    human_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    result = _task_result_base(record)
    if record.status in TERMINAL_TECHNICAL_STATES:
        result["acceptance"] = _task_acceptance(record.task_id, user_home)
        result["final_state"] = "COMPLETE" if record.status in {"completed", "closed"} else "TECHNICAL_COMPLETE_AWAITING_FOUNDER"
        result["blocker_next_actor"] = "founder" if record.status == "awaiting_founder" else None
        return result
    if record.status not in EXECUTION_ELIGIBLE_STATES:
        result["final_state"] = "AUTHORITY_BLOCKED"
        result["blocker_next_actor"] = f"task backend owner: unsupported state {record.status}"
        return result
    if not apply:
        result["final_state"] = "NEEDS_WORK"
        result["blocker_next_actor"] = "run the same natural-language request with an execution verb or --apply"
        return result

    seat_plan = resolve_meeting_seats(
        user_home,
        "all-coders+ollama-clouds",
        allow_missing_ollama=True,
        max_seats=None,
    )
    if seat_plan.decision != "pass" or not seat_plan.resolved_seats:
        result["meeting"] = {"decision": "blocked", "reason": seat_plan.reason, "seat_plan": seat_plan.to_dict()}
        result["final_state"] = "EXTERNALLY_BLOCKED"
        result["blocker_next_actor"] = "provider/route administrator"
        return result

    gate = hooks.backend_factory(user_home, intent).validation_gate(record.task_id, "run")
    if gate.get("decision") != "pass":
        if intent.get("human_gates"):
            result["final_state"] = "AUTHORITY_BLOCKED"
            result["blocker_next_actor"] = "user/founder confirmation for destructive or public action"
            human_decisions.append({"task_id": record.task_id, "decision": "pending", "gate": intent["human_gates"]})
            return result
        reviewed: dict[str, Any] = {}
        for validation_attempt in range(1, 3):
            reviewed = hooks.validation_review(
                user_home,
                record.task_id,
                context_files=[],
                privacy_class="D1",
                effort="xhigh",
                profile="ultracode",
                require_live=True,
            )
            iterations.append({
                "task_id": record.task_id, "iteration": 0, "stage": f"validate-and-optimise-{validation_attempt}",
                "decision": reviewed.get("decision"), "failure_fingerprint": _failure_fingerprint(reviewed),
                "new_evidence": reviewed.get("validation_id"), "meeting_id": reviewed.get("validation_meeting_id"),
                "run_id": reviewed.get("validation_task_id"), "started_at": reviewed.get("started_at"), "finished_at": utc_now(),
            })
            result["evidence"].append(reviewed.get("validation_id"))
            if reviewed.get("decision") == "pass" and reviewed.get("status") == "awaiting-user-approval":
                break
            if validation_attempt == 1:
                recovery = hooks.meeting_start(
                    user_home,
                    "Validation-recovery meeting. Diagnose why task validation did not converge, identify missing evidence, and return one bounded corrected validation plan for "
                    f"{record.task_id}: {record.title}",
                    list(seat_plan.resolved_seats),
                    min(max(2, quorum), len(seat_plan.resolved_seats)),
                    1,
                    True,
                    depth="deep",
                    effort="xhigh",
                    priority=record.priority if record.priority in {"low", "normal", "high", "critical"} else "normal",
                    risk_class=record.risk_class,
                    seat_plan=seat_plan.to_dict(),
                    existing_task_id=record.task_id,
                    correlation_id=intent["intent_id"],
                )
                recovery_id = recovery.get("meeting_id") or (recovery.get("meeting") or {}).get("id")
                provider_rows.extend(_meeting_provider_rows(record.task_id, 0, recovery))
                iterations.append({
                    "task_id": record.task_id, "iteration": 0, "stage": "validation-recovery-meeting",
                    "decision": recovery.get("decision"), "failure_fingerprint": _failure_fingerprint(recovery),
                    "new_evidence": recovery_id, "meeting_id": recovery_id, "run_id": None,
                    "started_at": None, "finished_at": utc_now(),
                })
                if recovery_id:
                    result["evidence"].append(recovery_id)
                if not _meeting_ok(recovery):
                    break
                if recovery_id:
                    hooks.meeting_approve(
                        user_home, str(recovery_id),
                        subject=f"natural-language:{intent['intent_id']}", intent_digest=intent["digest"],
                    )
        if reviewed.get("decision") != "pass" or reviewed.get("status") != "awaiting-user-approval":
            result["final_state"] = "EXTERNALLY_BLOCKED" if any(row.get("failure_class") for row in provider_rows if row.get("task_id") == record.task_id) else "NEEDS_WORK"
            result["blocker_next_actor"] = "provider administrator or task owner; validation and recovery meeting did not converge"
            return result
        approved = hooks.validation_approve(
            user_home,
            record.task_id,
            str(reviewed["validation_id"]),
            f"natural-language:{intent['intent_id']}",
            f"Explicit execution intent {intent['digest']} authorises the accepted optimisation; this is not founder final acceptance.",
        )
        human_decisions.append({
            "task_id": record.task_id,
            "decision": "approve-optimised-task",
            "subject": f"natural-language:{intent['intent_id']}",
            "intent_digest": intent["digest"],
            "validation_id": reviewed["validation_id"],
        })
        result["evidence"].extend([approved.get("validation_id")])

    meeting_value: dict[str, Any] = {}
    meeting_id: str | None = None
    meeting_attempts = 0
    previous_meeting_failure: dict[str, Any] = {}
    # A planning disagreement is recoverable: re-run one bounded, evidence-fed
    # meeting. Provider/auth/quota outages are external blockers and are not
    # hammered repeatedly with identical calls.
    for meeting_attempt in range(1, 3):
        meeting_attempts = meeting_attempt
        topic = f"Full hybrid planning and adversarial review for task {record.task_id}: {record.title}"
        if meeting_attempt > 1:
            topic = (
                "Bounded re-planning after an unsatisfied planning meeting. Resolve the exact hard gates, "
                "preserve dissent, and return one accepted evidence-bound plan. "
                + json.dumps(previous_meeting_failure, ensure_ascii=False, sort_keys=True)
                + f"\nTASK {record.task_id}: {record.title}"
            )
        meeting_value = hooks.meeting_start(
            user_home,
            topic,
            list(seat_plan.resolved_seats),
            min(max(2, quorum), len(seat_plan.resolved_seats)),
            2,
            True,
            depth="ultra" if record.priority == "critical" else "deep",
            effort="xhigh",
            priority=record.priority if record.priority in {"low", "normal", "high", "critical"} else "normal",
            risk_class=record.risk_class,
            seat_plan=seat_plan.to_dict(),
            max_parallel=min(len(seat_plan.resolved_seats), int(intent["execution"]["max_parallel_tasks"])),
            existing_task_id=record.task_id,
            correlation_id=intent["intent_id"],
        )
        current_meeting_id = meeting_value.get("meeting_id") or (meeting_value.get("meeting") or {}).get("id")
        if current_meeting_id:
            meeting_id = str(current_meeting_id)
            result["evidence"].append(meeting_id)
        current_provider_rows = _meeting_provider_rows(record.task_id, 0, meeting_value)
        provider_rows.extend(current_provider_rows)
        iterations.append({
            "task_id": record.task_id,
            "iteration": 0,
            "stage": f"planning-meeting-{meeting_attempt}",
            "decision": meeting_value.get("decision"),
            "failure_fingerprint": _failure_fingerprint(meeting_value),
            "new_evidence": meeting_id,
            "meeting_id": meeting_id,
            "run_id": intent["intent_id"],
            "started_at": None,
            "finished_at": utc_now(),
        })
        if _meeting_ok(meeting_value):
            if meeting_id:
                hooks.meeting_approve(
                    user_home,
                    meeting_id,
                    subject=f"natural-language:{intent['intent_id']}",
                    intent_digest=intent["digest"],
                )
                human_decisions.append({"task_id": record.task_id, "decision": "approve-meeting-plan", "meeting_id": meeting_id, "intent_digest": intent["digest"]})
            break
        previous_meeting_failure = {
            "decision": meeting_value.get("decision"),
            "status": meeting_value.get("status") or (meeting_value.get("meeting") or {}).get("status"),
            "hard_gates": meeting_value.get("hard_gates") or {},
            "seat_coverage": meeting_value.get("seat_coverage") or {},
        }
        if any(row.get("failure_class") for row in current_provider_rows):
            break

    result["meeting"] = {
        "meeting_id": meeting_id,
        "attempts": meeting_attempts,
        "status": meeting_value.get("status") or (meeting_value.get("meeting") or {}).get("status"),
        "decision": meeting_value.get("decision"),
        "hard_gates": meeting_value.get("hard_gates"),
    }
    if not _meeting_ok(meeting_value):
        result["final_state"] = "EXTERNALLY_BLOCKED" if any(row.get("failure_class") for row in provider_rows if row.get("task_id") == record.task_id) else "NEEDS_WORK"
        result["blocker_next_actor"] = "provider administrator or task owner; bounded planning/re-planning did not satisfy quorum and digest gates"
        return result

    max_iterations = int(intent["execution"]["max_iterations_per_task"])
    fingerprints: dict[str, int] = {}
    latest_multi: dict[str, Any] = {}
    for iteration in range(1, max_iterations + 1):
        started = utc_now()
        latest_multi = hooks.multicoder_run(
            user_home,
            task_id=record.task_id,
            providers=list(seat_plan.resolved_seats),
            quorum=min(max(2, quorum), len(seat_plan.resolved_seats)),
            test_argv=test_argv,
            cwd=cwd,
            risk_class=record.risk_class,
            effort="xhigh",
            max_repair_rounds=3 if record.priority == "critical" else 2,
        )
        fingerprint = _failure_fingerprint(latest_multi)
        fingerprints[fingerprint] = fingerprints.get(fingerprint, 0) + 1
        provider_rows.extend(_extract_providers(record.task_id, iteration, latest_multi))
        result["repairs"] += int(latest_multi.get("repair_rounds") or 0)
        result["multi_coder"] = {
            "run_id": latest_multi.get("run_id"),
            "decision": latest_multi.get("decision"),
            "reason": latest_multi.get("reason"),
            "plan_digest": latest_multi.get("plan_digest"),
        }
        test_rows = latest_multi.get("tests") or []
        tests_pass = bool(test_rows) and all(row.get("decision") == "pass" for row in test_rows if isinstance(row, dict))
        result["tests"] = {
            "decision": "pass" if tests_pass else "needs-work",
            "summary": ", ".join(f"{row.get('tier')}:{row.get('decision')}" for row in test_rows if isinstance(row, dict)) or "no deterministic tests",
        }
        iterations.append({
            "task_id": record.task_id,
            "iteration": iteration,
            "stage": "multi-coder-hybrid",
            "decision": latest_multi.get("decision"),
            "failure_fingerprint": fingerprint,
            "new_evidence": latest_multi.get("run_id"),
            "meeting_id": meeting_id,
            "run_id": latest_multi.get("run_id"),
            "started_at": started,
            "finished_at": utc_now(),
        })
        result["evidence"].append(latest_multi.get("run_id"))
        if latest_multi.get("decision") == "approve":
            break
        if fingerprints[fingerprint] >= int(intent["execution"]["max_identical_failures"]):
            result["blocker_next_actor"] = "task owner/provider administrator; identical failure repeated without new evidence"
            break

        failure_meeting = hooks.meeting_start(
            user_home,
            "Failure-analysis meeting. Diagnose the exact evidence below, choose one bounded repair, and preserve dissent. "
            + json.dumps({"task_id": record.task_id, "iteration": iteration, "multi_coder": result["multi_coder"], "tests": result["tests"]}, ensure_ascii=False),
            list(seat_plan.resolved_seats),
            min(max(2, quorum), len(seat_plan.resolved_seats)),
            1,
            True,
            depth="deep",
            effort="xhigh",
            priority=record.priority if record.priority in {"low", "normal", "high", "critical"} else "normal",
            risk_class=record.risk_class,
            seat_plan=seat_plan.to_dict(),
            existing_task_id=record.task_id,
            correlation_id=intent["intent_id"],
        )
        failure_meeting_id = failure_meeting.get("meeting_id") or (failure_meeting.get("meeting") or {}).get("id")
        provider_rows.extend(_meeting_provider_rows(record.task_id, iteration, failure_meeting))
        iterations.append({
            "task_id": record.task_id, "iteration": iteration, "stage": "failure-meeting",
            "decision": failure_meeting.get("decision"), "failure_fingerprint": fingerprint,
            "new_evidence": failure_meeting_id, "meeting_id": failure_meeting_id,
            "run_id": latest_multi.get("run_id"), "started_at": started, "finished_at": utc_now(),
        })
        if not _meeting_ok(failure_meeting):
            result["blocker_next_actor"] = "provider administrator; failure meeting did not reach quorum/digest acceptance"
            break
        if failure_meeting_id:
            hooks.meeting_approve(
                user_home,
                str(failure_meeting_id),
                subject=f"natural-language:{intent['intent_id']}",
                intent_digest=intent["digest"],
            )
            result["evidence"].append(failure_meeting_id)

    result["acceptance"] = _task_acceptance(record.task_id, user_home)
    try:
        snapshot = show_task(user_home, record.task_id)["task"]
        status = str(snapshot.get("status") or "unknown")
    except Exception:
        status = "unknown"
    if latest_multi.get("decision") == "approve" and status == "awaiting_founder":
        result["final_state"] = "TECHNICAL_COMPLETE_AWAITING_FOUNDER"
        result["blocker_next_actor"] = "founder: accept, reject, or rework"
    elif latest_multi.get("reason") in {"insufficient-substantive-quorum", "no-live-ready-provider"}:
        result["final_state"] = "EXTERNALLY_BLOCKED"
        result["blocker_next_actor"] = "provider/route administrator"
    else:
        result["final_state"] = "NEEDS_WORK"
        result["blocker_next_actor"] = result.get("blocker_next_actor") or "task owner; unresolved evidence or verification"
    return result


def run_autopilot(
    user_home: Path,
    raw_text: str,
    *,
    conversation_id: str = "default",
    apply: bool | None = None,
    cwd: Path | None = None,
    test_argv: list[str] | None = None,
    max_tasks: int | None = None,
    hooks: AutopilotHooks | None = None,
    report_output: Path | None = None,
) -> dict[str, Any]:
    hooks = hooks or AutopilotHooks()
    state = load_state(user_home, conversation_id)
    intent = compile_intent(raw_text, conversation_state=state, conversation_id=conversation_id, apply=apply)
    should_apply = bool(intent["execution"]["requested"])
    work_root = (cwd or Path.cwd()).resolve()
    tests = test_argv or _infer_test_argv(work_root)
    providers = list(dict.fromkeys(str(row.get("provider")) for row in provider_candidates(user_home, require_live=True) if row.get("provider")))
    if not providers:
        # Meeting seat resolution may still record honest route failures; Multi-Coder requires at least an explicit set.
        providers = ["claude", "codex", "gemini", "grok", "ollama@auto:cloud"]

    task_results: list[dict[str, Any]] = []
    provider_rows: list[dict[str, Any]] = []
    iterations: list[dict[str, Any]] = []
    human_decisions: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    backend_receipt: dict[str, Any] | None = None
    started = time.monotonic()

    try:
        backend = hooks.backend_factory(user_home, intent)
        backend_receipt = backend.adapter_receipt()
    except ExternalBackendUnavailable as exc:
        blockers.append({"code": "EXTERNAL_BACKEND_UNAVAILABLE", "summary": str(exc), "next_actor": "PMD/API administrator"})
        report = build_report(
            intent=intent, backend_receipt=None, tasks=[], providers=[], iterations=[], human_decisions=[],
            terminal_state="EXTERNALLY_BLOCKED", blockers=blockers,
        )
        bundle = write_report_bundle(user_home, report, report_output)
        save_state(user_home, {**state, "conversation_id": conversation_id, "active_goal_id": intent["intent_id"], "last_intent_id": intent["intent_id"], "active_product": (intent.get("scope") or {}).get("product"), "active_backend": (intent.get("scope") or {}).get("backend"), "external_blockers": blockers, "last_checkpoint": bundle["root"]})
        return {"decision": "blocked", "terminal_state": "EXTERNALLY_BLOCKED", "intent": intent, "blockers": blockers, "report": report, "report_bundle": bundle}

    records = backend.discover(intent)
    if (
        not records
        and isinstance(backend, SuiteTaskBackend)
        and should_apply
        and not (intent.get("scope") or {}).get("task_ids")
        and bool((intent.get("scope") or {}).get("create_if_none", True))
    ):
        created = create_task(
            user_home,
            raw_text[:180],
            raw_text,
            "critical" if "critical" in (intent.get("scope") or {}).get("priorities", []) else "high",
            source="cli-run",
            source_id=intent["intent_id"],
            risk_class="R2",
            task_type="autonomous-goal",
            tags=["natural-language", "autopilot", "meeting", "multi-coder"],
            acceptance_criteria=(
                "1. Scope and authority are explicit.\n"
                "2. All required coder families are attempted and outages are recorded.\n"
                "3. Meeting plan passes quorum and same-digest review.\n"
                "4. Implementation is limited to the approved scope.\n"
                "5. Deterministic tests pass.\n"
                "6. Independent final review passes.\n"
                "7. Audit and evidence bundle are complete.\n"
                "8. Final state and next human actor are explicit."
            ),
        )
        task_id = created.get("task_id") or created.get("duplicate_of")
        if task_id:
            records = [backend.snapshot(str(task_id))]

    ordered_records = sorted(records, key=lambda row: (-PRIORITY_ORDER.get(row.priority, 2), row.task_id))
    operator_deferred: list[TaskRecord] = []
    if max_tasks is not None and max_tasks >= 0 and len(ordered_records) > max_tasks:
        operator_deferred = ordered_records[max_tasks:]
        ordered_records = ordered_records[:max_tasks]
    waves = _schedule_waves(ordered_records, int(intent["execution"]["max_parallel_tasks"]))
    selected: list[TaskRecord] = []
    for wave_number, wave in enumerate(waves, start=1):
        iterations.append({
            "task_id": "*", "iteration": wave_number, "stage": "scheduler-wave",
            "decision": "scheduled", "failure_fingerprint": None,
            "new_evidence": ",".join(record.task_id for record in wave), "meeting_id": None,
            "run_id": intent["intent_id"], "started_at": utc_now(), "finished_at": utc_now(),
        })
        for record in wave:
            selected.append(record)
            if time.monotonic() - started > int(intent["execution"]["wall_clock_budget_seconds"]):
                task_results.append({**_task_result_base(record), "final_state": "BUDGET_EXHAUSTED", "blocker_next_actor": "operator: resume from checkpoint"})
                continue
            if not isinstance(backend, SuiteTaskBackend):
                run_task = getattr(backend, "run_task", None)
                if callable(run_task):
                    try:
                        external_result = dict(run_task(record.task_id, intent=intent, apply=should_apply))
                    except Exception as exc:
                        external_result = {"decision": "blocked", "failure_class": type(exc).__name__, "reason": str(exc)}
                    row = _task_result_base(record)
                    row["final_state"] = str(external_result.get("terminal_state") or "EXTERNALLY_BLOCKED")
                    row["blocker_next_actor"] = external_result.get("next_actor") or "Enterprise PMD/API owner"
                    row["evidence"] = list(external_result.get("evidence") or [])
                    if isinstance(external_result.get("acceptance"), dict): row["acceptance"] = dict(external_result["acceptance"])
                    if isinstance(external_result.get("meeting"), dict): row["meeting"] = dict(external_result["meeting"])
                    if isinstance(external_result.get("multi_coder"), dict): row["multi_coder"] = dict(external_result["multi_coder"])
                    if isinstance(external_result.get("tests"), dict): row["tests"] = dict(external_result["tests"])
                    row["repairs"] = int(external_result.get("repairs") or 0)
                    task_results.append(row)
                else:
                    task_results.append({
                        **_task_result_base(record),
                        "final_state": "EXTERNALLY_BLOCKED",
                        "blocker_next_actor": "Enterprise PMD adapter must implement its governed run_task contract",
                    })
                continue
            task_results.append(_process_suite_task(
                user_home=user_home,
                record=record,
                intent=intent,
                hooks=hooks,
                cwd=work_root,
                test_argv=tests,
                providers=providers,
                quorum=2,
                apply=should_apply,
                iterations=iterations,
                provider_rows=provider_rows,
                human_decisions=human_decisions,
            ))
    for record in operator_deferred:
        task_results.append({
            **_task_result_base(record),
            "final_state": "DEFERRED_BY_OPERATOR_LIMIT",
            "blocker_next_actor": "operator-configured max_tasks limit; resume from checkpoint",
        })
    deferred = operator_deferred

    states = {str(row.get("final_state")) for row in task_results}
    if not task_results:
        terminal = "COMPLETE" if not should_apply else "NEEDS_WORK"
    elif states <= {"COMPLETE", "TECHNICAL_COMPLETE_AWAITING_FOUNDER"}:
        terminal = "TECHNICAL_COMPLETE_AWAITING_FOUNDER" if "TECHNICAL_COMPLETE_AWAITING_FOUNDER" in states else "COMPLETE"
    elif "EXTERNALLY_BLOCKED" in states:
        terminal = "EXTERNALLY_BLOCKED"
    elif "AUTHORITY_BLOCKED" in states:
        terminal = "AUTHORITY_BLOCKED"
    elif "BUDGET_EXHAUSTED" in states:
        terminal = "BUDGET_EXHAUSTED"
    else:
        terminal = "NEEDS_WORK"

    for row in task_results:
        if row.get("final_state") in {"EXTERNALLY_BLOCKED", "AUTHORITY_BLOCKED", "NEEDS_WORK", "BUDGET_EXHAUSTED"}:
            blockers.append({
                "code": str(row.get("final_state")),
                "summary": f"{row.get('task_id')}: {row.get('blocker_next_actor')}",
                "next_actor": row.get("blocker_next_actor"),
            })
    report = build_report(
        intent=intent,
        backend_receipt=backend_receipt,
        tasks=task_results,
        providers=provider_rows,
        iterations=iterations,
        human_decisions=human_decisions,
        terminal_state=terminal,
        blockers=blockers,
    )
    bundle = write_report_bundle(user_home, report, report_output)
    selected_ids = [record.task_id for record in selected]
    save_state(user_home, {
        **state,
        "conversation_id": conversation_id,
        "active_goal_id": intent["intent_id"],
        "last_intent_id": intent["intent_id"],
        "active_product": (intent.get("scope") or {}).get("product"),
        "active_backend": (intent.get("scope") or {}).get("backend"),
        "selected_task_ids": selected_ids,
        "last_task_table_digest": report["digest"],
        "pending_human_decisions": [row for row in human_decisions if row.get("decision") == "pending"] + [
            {"task_id": row.get("task_id"), "decision": "founder-final", "state": row.get("final_state")}
            for row in task_results if row.get("final_state") == "TECHNICAL_COMPLETE_AWAITING_FOUNDER"
        ],
        "external_blockers": blockers,
        "last_checkpoint": bundle["root"],
    })
    decision = "pass" if terminal in {"COMPLETE", "TECHNICAL_COMPLETE_AWAITING_FOUNDER"} else "noop" if not selected and not should_apply else "needs-work"
    return {
        "schema": "iot-ai.autopilot-result.v1",
        "decision": decision,
        "terminal_state": terminal,
        "intent": intent,
        "backend_receipt": backend_receipt,
        "tasks": task_results,
        "deferred_count": len(deferred),
        "blockers": blockers,
        "report": report,
        "report_bundle": bundle,
        "production_claim": False,
    }
