# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
"""Primary natural-language workflow backed by immutable roles and a DAG."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .context_compiler import compile_context, validate_context_manifest
from .diagnostics import collect as collect_diagnostics, record_event, run_root
from .goal_contract import compile_goal_contract, validate_goal_contract
from .eu_ai_act import classify_risk, record_prohibited_practice_screen, screen_prohibited_practices
from .graph_runtime import ExecutionGraph, GraphNode, compile_graph, execute_graph
from .knowledge_plane import coverage, list_artifacts, write_artifact
from .licensing import current
from .mesh import delegate
from .model_policy import select_candidates
from .prompt_compiler import compile_prompt, validate_prompt
from .paths import data_root
from .roles import ROLE_CATALOG
from .runtime_gates import (
    bind_implementation_to_accepted_plan,
    build_effort_receipt,
    evaluate_minimum_change_gate,
    finalize_skill_state,
    resolve_dispatch_effort,
)
from .settings import effective_settings, load as load_settings
from .skill_router import context_blocks, is_visual_task, select_skills
from .tool_router import build_tool_decision, validate_provider_binding
from .visual_acceptance import evaluate_visual_acceptance
from .transparency import record_disclosure, runtime_output_provenance
from .util import atomic_json, utc_now
from .workspace import append_event, connect_write, new_id

ProviderExecutor = Callable[[GraphNode, str, dict[str, Any]], dict[str, Any]]


def _parse_model_output(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {"decision": "block", "summary": "empty output", "findings": [], "evidence_refs": []}
    candidates = [text]
    if "```json" in text:
        candidates.insert(0, text.split("```json", 1)[1].split("```", 1)[0])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue
    decision = "needs-work"
    lowered = text.casefold()
    if "decision: accept" in lowered or "decision: approve" in lowered or "decision: pass" in lowered:
        decision = "accept"
    elif "decision: block" in lowered:
        decision = "block"
    return {
        "decision": decision,
        "summary": text,
        "findings": [],
        "evidence_refs": [],
        "unstructured": True,
    }


def _five_w_one_h(goal: str) -> dict[str, str]:
    return {
        "why": "Resolve the stated goal with measurable evidence and minimum unnecessary coordination.",
        "what": goal.strip(),
        "how": "Knowledge-first dependency graph, immutable specialist roles, live-ready routing, deterministic gates and diagnostics.",
        "when": "Analysis starts now; writes occur only under the active task and authorization policy.",
        "who": "Perspective-diverse specialist roles, independent verifier, and user/founder for gated decisions.",
    }


def _dedupe_findings(values: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    seen: set[str] = set()
    findings: list[Any] = []
    contradictions: list[Any] = []
    decisions: dict[str, set[str]] = {}
    for value in values:
        parsed = value.get("parsed") or value.get("output") or {}
        if not isinstance(parsed, dict):
            continue
        role = str(value.get("role_id") or "unknown")
        decision = str(parsed.get("decision") or "unknown")
        decisions.setdefault(decision, set()).add(role)
        candidates = parsed.get("findings") or []
        if not candidates and parsed.get("summary"):
            candidates = [parsed["summary"]]
        for candidate in candidates:
            key = json.dumps(candidate, sort_keys=True, ensure_ascii=False) if not isinstance(candidate, str) else " ".join(candidate.casefold().split())
            if key and key not in seen:
                seen.add(key)
                findings.append(candidate)
    if len(decisions) > 1:
        contradictions.append({"type": "decision-disagreement", "decisions": {key: sorted(value) for key, value in decisions.items()}})
    return findings, contradictions


def _default_provider_executor(
    user_home: Path,
    candidate_map: dict[str, dict[str, Any]],
    graph: ExecutionGraph,
    *,
    task_id: str | None = None,
    meeting_id: str | None = None,
    max_effort: str = "xhigh",
) -> ProviderExecutor:
    """Create a role executor with explicit route decisions and binding checks."""
    recoverable = {
        "quota",
        "auth",
        "authentication",
        "timeout",
        "process",
        "empty-output",
        "model-drift",
        "URLError",
        "HTTPError",
        "TimeoutError",
        "JSONDecodeError",
        "no-live-role-candidate",
        "provider-binding-mismatch",
    }

    def execute(node: GraphNode, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        primary = candidate_map.get(node.role_id)
        if not primary:
            return {
                "status": "blocked",
                "failure_class": "no-live-role-candidate",
                "output": {},
                "role_id": node.role_id,
                "attempts": [],
                "_runtime_decisions": {
                    "tool_decision": {
                        "schema": "iot-ai.tool-decision.v1",
                        "decision": "block",
                        "role_id": node.role_id,
                        "selection_reason": "no live candidate assigned to required role",
                        "evaluations": [],
                    }
                },
            }
        ladder = [primary, *list(primary.get("fallback_candidates") or [])]
        primary_dispatch = resolve_dispatch_effort(
            primary,
            node_effort=node.effort,
            max_effort=max_effort,
            role_id=node.role_id,
        )
        tool_decision = build_tool_decision(
            ladder,
            role_id=node.role_id,
            requested_effort=str(primary_dispatch.get("effective_effort") or node.effort),
            privacy_class=graph.privacy_class,
            selected_candidate_id=str(primary.get("candidate_id") or ""),
            require_live=True,
        )
        evaluations = {
            str(row.get("candidate_id")): row for row in tool_decision.get("evaluations", [])
        }
        attempts: list[dict[str, Any]] = []
        last: dict[str, Any] | None = None
        for index, candidate in enumerate(ladder):
            evaluation = evaluations.get(str(candidate.get("candidate_id"))) or {}
            if not evaluation.get("eligible", False):
                attempts.append(
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "provider": candidate.get("provider"),
                        "model_requested": candidate.get("model"),
                        "status": "skipped",
                        "failure_class": "route-ineligible",
                        "reasons": evaluation.get("reasons", []),
                    }
                )
                continue
            dispatch = resolve_dispatch_effort(
                candidate,
                node_effort=node.effort,
                max_effort=max_effort,
                role_id=node.role_id,
            )
            if dispatch.get("decision") == "block":
                attempts.append(
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "provider": candidate.get("provider"),
                        "model_requested": candidate.get("model"),
                        "status": "blocked",
                        "failure_class": dispatch.get("block_reason") or "minimum-effort-unsatisfied",
                    }
                )
                continue
            effective = str(dispatch.get("effective_effort") or node.effort)
            reason = dispatch.get("clamp_reason")
            try:
                result = delegate(
                    user_home,
                    str(candidate["provider"]),
                    prompt,
                    node.stage,
                    model=str(candidate.get("model") or "auto"),
                    auth_mode=str(candidate.get("auth_mode") or "auto"),
                    allow_fallback=False,
                    run_id=graph.graph_id,
                    role=node.role_id,
                    task_id=task_id,
                    meeting_id=meeting_id,
                    timeout=max(60, min(graph.wall_clock_seconds, 1800)),
                    effort=effective,
                )
            except Exception as exc:
                message = str(exc)
                failure_class = "privacy-policy" if "privacy" in message.casefold() else type(exc).__name__
                result = {
                    "status": "blocked",
                    "failure_class": failure_class,
                    "error": message,
                    "provider": candidate.get("provider"),
                    "model_requested": candidate.get("model"),
                    "model_served": None,
                }
            effort_receipt = build_effort_receipt(
                settings_requested=candidate.get("requested_effort"),
                candidate=candidate,
                dispatch=dispatch,
                tool_decision=tool_decision,
                adapter_request_effort=effective,
                response={**result, "effort_effective": effective},
            )
            result = {
                **result,
                "effort_requested": dispatch.get("requested_effort") or candidate.get("requested_effort") or node.effort,
                "effort_effective": effective,
                "effort_source": dispatch.get("effort_source"),
                "effort_clamp_reason": reason,
                "effort_receipt": effort_receipt,
                "candidate_id": candidate.get("candidate_id"),
                "fallback_used": index > 0,
            }
            binding = validate_provider_binding(
                selected_provider=str(candidate.get("provider") or ""),
                selected_model=str(candidate.get("model") or ""),
                result=result,
            )
            if result.get("status") == "pass" and binding["decision"] != "pass":
                result["status"] = "blocked"
                result["failure_class"] = "provider-binding-mismatch"
                result["binding_errors"] = binding["errors"]
            attempts.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "provider": candidate.get("provider"),
                    "model_requested": candidate.get("model"),
                    "model_served": result.get("model_served"),
                    "status": result.get("status"),
                    "failure_class": result.get("failure_class"),
                    "request_id": result.get("request_id"),
                    "latency_ms": result.get("latency_ms"),
                    "binding_decision": binding["decision"],
                }
            )
            result["attempts"] = list(attempts)
            result["_runtime_decisions"] = {
                "tool_decision": {
                    **tool_decision,
                    "selected_candidate_id": candidate.get("candidate_id"),
                    "selected_provider": candidate.get("provider"),
                    "selected_model": candidate.get("model"),
                    "selected_route": candidate.get("route_id"),
                    "fallback_used": index > 0,
                    "binding_validation": binding,
                }
            }
            last = result
            if result.get("status") == "pass" and str(result.get("output") or "").strip() and result.get("model_served"):
                parsed = _parse_model_output(str(result.get("output") or ""))
                result["parsed"] = parsed
                return result
            failure = str(result.get("failure_class") or "")
            if failure not in recoverable or failure == "privacy-policy":
                break
        if last is None:
            last = {
                "status": "blocked",
                "failure_class": "no-eligible-role-candidate",
                "output": {},
                "provider": None,
                "model_requested": None,
                "model_served": None,
            }
        last["status"] = "blocked"
        last["attempts"] = attempts
        last.setdefault("_runtime_decisions", {})["tool_decision"] = tool_decision
        return last

    return execute

def _register_run(user_home: Path, graph: ExecutionGraph, goal: str, role_count: int, execute: bool, existing_task_id: str | None = None) -> tuple[str, str]:
    task_id = existing_task_id or new_id("task")
    meeting_id = new_id("meeting")
    now = utc_now()
    connection = connect_write(user_home)
    try:
        if existing_task_id:
            existing = one(connection, "SELECT id FROM tasks WHERE id=?", (existing_task_id,))
            if not existing:
                raise ValueError("Task not found")
            connection.execute(
                """UPDATE tasks SET status='meeting',source_id=?,engineering_stage='meeting',
                revision=revision+1,updated_at=? WHERE id=?""",
                (graph.graph_id, now, task_id),
            )
        else:
            connection.execute(
                """INSERT INTO tasks(
                id,title,description,status,priority,owner,source,source_id,risk_class,task_type,
                tags_json,acceptance_criteria,engineering_stage,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task_id,
                    goal.strip()[:180],
                    goal.strip(),
                    "meeting",
                    "high" if graph.risk_class in {"R2", "R3", "R4"} else "normal",
                    "iot-ai-orchestrator",
                    "iot-ai",
                    graph.graph_id,
                    graph.risk_class,
                    "agentic-execution" if execute else "agentic-decision",
                    json.dumps(["graph", "meeting", graph.privacy_class]),
                    "Required roles accept one plan digest; hard gates pass; evidence and diagnostics persist.",
                    "meeting",
                    now,
                    now,
                ),
            )
        connection.execute(
            """INSERT INTO meetings(
            id,task_id,topic,depth,effort,status,requested_seats,substantive_seats,quorum,rounds,
            created_at,updated_at)
            VALUES(?,?,?,?,?,'running',?,0,?,0,?,?)""",
            (
                meeting_id,
                task_id,
                goal,
                "deep",
                "ultracode" if graph.token_budget >= 500_000 else "adaptive",
                role_count,
                max(1, role_count),
                now,
                now,
            ),
        )
        append_event(connection, "task.meeting.started", {"meeting_id": meeting_id, "graph_id": graph.graph_id}, task_id=task_id)
        connection.commit()
    finally:
        connection.close()
    return task_id, meeting_id


def _finish_run(user_home: Path, task_id: str, meeting_id: str, result: dict[str, Any], execute: bool) -> None:
    plan_acceptance = ((result.get("results") or {}).get("final-plan-gate") or {}).get("output") or ((result.get("results") or {}).get("plan-acceptance") or {}).get("output") or {}
    accepted = plan_acceptance.get("decision") == "accept"
    final_audit = ((result.get("results") or {}).get("final-audit") or {}).get("output") or {}
    now = utc_now()
    connection = connect_write(user_home)
    try:
        connection.execute(
            """UPDATE meetings SET status=?,substantive_seats=?,rounds=?,synthesis=?,final_decision=?,
            consultation_sha256=?,updated_at=? WHERE id=?""",
            (
                "accepted" if accepted else "needs-review",
                sum(1 for node in (result.get("results") or {}).values() if node.get("status") == "pass" and node.get("provider")),
                int(plan_acceptance.get("selected_round") or 1),
                json.dumps(
                    (((result.get("results") or {}).get("plan-revision") or {}).get("parsed")
                     or ((result.get("results") or {}).get("plan-synthesis") or {}).get("parsed")
                     or {}),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                plan_acceptance.get("decision") or result.get("decision"),
                plan_acceptance.get("plan_digest"),
                now,
                meeting_id,
            ),
        )
        if execute and result.get("decision") == "pass" and final_audit.get("decision") in {"accept", "pass", "approve"}:
            task_status, progress, stage = "awaiting_founder", 100, "complete"
        elif accepted:
            task_status, progress, stage = "awaiting_founder", 50, "plan-accepted"
        else:
            task_status, progress, stage = "needs-work", 25, "meeting"
        connection.execute(
            """UPDATE tasks SET status=?,engineering_stage=?,engineering_progress=?,task_progress=?,
            result_summary=?,revision=revision+1,updated_at=? WHERE id=?""",
            (
                task_status,
                stage,
                progress,
                progress,
                f"Graph {result.get('decision')}; plan {plan_acceptance.get('decision', 'unknown')}",
                now,
                task_id,
            ),
        )
        append_event(
            connection,
            "task.meeting.finished",
            {
                "meeting_id": meeting_id,
                "graph_decision": result.get("decision"),
                "plan_decision": plan_acceptance.get("decision"),
                "plan_digest": plan_acceptance.get("plan_digest"),
            },
            task_id=task_id,
        )
        connection.commit()
    finally:
        connection.close()


def _valid_case_set(value: Any) -> bool:
    return isinstance(value, list) and len(value) >= 10 and all(isinstance(item, (str, dict)) for item in value[:10])


def run_goal(
    user_home: Path,
    goal: str,
    *,
    execute: bool = False,
    risk_class: str = "R2",
    privacy_class: str = "D1",
    max_parallel: int = 6,
    token_budget: int = 250_000,
    wall_clock_seconds: int = 3600,
    provider_executor: ProviderExecutor | None = None,
    require_live: bool = True,
    profile: str | None = None,
    existing_task_id: str | None = None,
    required_provider_families: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    article5 = screen_prohibited_practices(goal)
    record_prohibited_practice_screen(user_home, goal, context="agentic-run")
    disclosure = record_disclosure(user_home, surface="cli:run", language="en")
    if article5.decision == "block":
        return {
            "schema": "iot-ai.agentic-result.v2",
            "decision": "blocked",
            "failure_class": "eu-ai-act-article-5-prohibited-practice",
            "article_5": article5.to_dict(),
            "article_50": disclosure,
            "provider_calls": 0,
            "execution_authorized": False,
            "global_compliance_claim_allowed": False,
        }
    article6 = classify_risk(goal)
    goal_contract = compile_goal_contract(
        goal, risk_class=risk_class, privacy_class=privacy_class
    )
    goal_contract_validation = validate_goal_contract(goal_contract)
    if goal_contract_validation["decision"] != "pass":
        return {
            "schema": "iot-ai.agentic-result.v3",
            "decision": "blocked",
            "failure_class": "invalid-goal-contract",
            "goal_contract_validation": goal_contract_validation,
            "provider_calls": 0,
            "execution_authorized": False,
        }
    if execute and article6.get("decision") == "high-risk-candidate":
        return {
            "schema": "iot-ai.agentic-result.v2",
            "decision": "blocked",
            "failure_class": "eu-ai-act-high-risk-requires-deployment-classification",
            "article_5": article5.to_dict(),
            "article_6": article6,
            "article_50": disclosure,
            "provider_calls": 0,
            "execution_authorized": False,
            "global_compliance_claim_allowed": False,
        }

    settings = load_settings(user_home)
    active_profile = profile or str(settings.get("orchestration", {}).get("active_profile", "balanced"))
    profile_values = settings.get("orchestration", {}).get("profiles", {}).get(active_profile)
    if not isinstance(profile_values, dict):
        raise ValueError(f"unknown orchestration profile: {active_profile}")
    if max_parallel == 6:
        max_parallel = int(profile_values.get("max_parallel", max_parallel))
    if token_budget == 250_000:
        token_budget = int(profile_values.get("token_budget", token_budget))
    if wall_clock_seconds == 3600:
        wall_clock_seconds = int(profile_values.get("wall_clock_seconds", wall_clock_seconds))
    if require_live:
        require_live = bool(profile_values.get("require_live", True))

    prior = list_artifacts(user_home, "private")
    prior_coverage = coverage(goal, prior)
    knowledge_mode = (
        "mini-review"
        if prior_coverage["score"] >= float(settings.get("knowledge", {}).get("reuse_threshold", 0.85))
        else "full-analysis"
    )
    graph = compile_graph(
        goal,
        include_implementation=execute,
        risk_class=risk_class,
        privacy_class=privacy_class,
        max_parallel=max_parallel,
        token_budget=token_budget,
        wall_clock_seconds=wall_clock_seconds,
        knowledge_mode=knowledge_mode,
        goal_contract_digest=goal_contract.digest,
    )
    runtime_root = run_root(user_home, graph.correlation_id) / "08_AGENT_RUNTIME"
    atomic_json(runtime_root / "goal-contract.json", goal_contract.to_dict())
    role_ids = list(dict.fromkeys(node.role_id for node in graph.nodes if node.node_type == "agent"))
    entitlements = current()
    settings = load_settings(user_home)
    candidates = select_candidates(
        user_home,
        role_ids,
        require_live=require_live,
        allow_reuse=True,
        max_providers=entitlements.max_providers,
        required_provider_families=required_provider_families,
        settings=settings,
    )
    skill_selection = select_skills(
        user_home,
        goal=goal,
        role_id=role_ids[0] if role_ids else None,
        stage="agentic-execution",
        settings=settings,
    )
    effective = effective_settings(user_home, settings)
    task_id, meeting_id = _register_run(user_home, graph, goal, len(role_ids), execute, existing_task_id)
    provider_executor = provider_executor or _default_provider_executor(
        user_home,
        candidates,
        graph,
        task_id=task_id,
        meeting_id=meeting_id,
        max_effort=entitlements.max_effort,
    )

    def executor(node: GraphNode, inputs: dict[str, Any], active_graph: ExecutionGraph) -> dict[str, Any]:
        if node.node_id == "intake":
            return {
                "status": "pass",
                "output": {
                    "goal": goal,
                    "goal_contract": goal_contract.to_dict(),
                    "5w1h": _five_w_one_h(goal),
                    "constraints": {"risk_class": risk_class, "privacy_class": privacy_class},
                    "eu_ai_act": {"article_5": article5.to_dict(), "article_6": article6},
                    "article_50_disclosure": disclosure["disclosure"],
                    "acceptance": [
                        "required roles complete",
                        "hard gates pass",
                        "same plan digest",
                        "KPI/SLA and 10/10/10 cases exist",
                    ],
                },
            }
        if node.node_id == "knowledge":
            knowledge_context = [
                {
                    "artifact_id": artifact.get("artifact_id"),
                    "title": artifact.get("title"),
                    "kind": artifact.get("kind"),
                    "content_sha256": (artifact.get("integrity") or {}).get("content_sha256"),
                    "snippet": str(artifact.get("content") or "")[:1200],
                }
                for artifact in prior[:12]
            ]
            return {
                "status": "pass",
                "output": {
                    "coverage": prior_coverage["score"],
                    "artifact_refs": prior_coverage.get("artifact_refs", []),
                    "gap_questions": prior_coverage["missing"][:40],
                    "mode": knowledge_mode,
                    "knowledge_context": knowledge_context,
                },
            }
        if node.node_id == "normalize":
            findings, contradictions = _dedupe_findings([inputs[key] for key in sorted(inputs)])
            return {
                "status": "pass",
                "output": {
                    "domain_summaries": findings,
                    "contradictions": contradictions,
                    "evidence_matrix": [{"finding": finding, "evidence_refs": []} for finding in findings],
                    "new_findings": len(findings),
                },
            }
        if node.node_id in {"plan-acceptance", "plan-acceptance-r2"}:
            synthesis_key = "plan-revision" if node.node_id.endswith("r2") else "plan-synthesis"
            synthesis_result = inputs[synthesis_key]
            synthesis = synthesis_result.get("parsed") or synthesis_result.get("output") or {}
            if not isinstance(synthesis, dict):
                synthesis = {}
            plan_body = {key: value for key, value in synthesis.items() if key != "plan_digest"}
            plan_digest = synthesis.get("plan_digest") or hashlib.sha256(
                json.dumps(plan_body, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            acceptance_matrix: dict[str, Any] = {}
            dissent: list[Any] = []
            required_reviews_accept = True
            for dependency in node.depends_on:
                if dependency == synthesis_key:
                    continue
                review_result = inputs[dependency]
                parsed = review_result.get("parsed") or review_result.get("output") or {}
                if not isinstance(parsed, dict):
                    parsed = {}
                accepted = (
                    review_result.get("status") == "pass"
                    and parsed.get("decision") in {"accept", "approve", "pass"}
                    and parsed.get("plan_digest") == plan_digest
                )
                acceptance_matrix[dependency] = {
                    "accepted": accepted,
                    "decision": parsed.get("decision"),
                    "plan_digest": parsed.get("plan_digest"),
                    "status": review_result.get("status"),
                    "provider": review_result.get("provider"),
                    "model_served": review_result.get("model_served"),
                }
                required_reviews_accept = required_reviews_accept and accepted
                if parsed.get("dissent"):
                    dissent.append({"node": dependency, "dissent": parsed.get("dissent")})
            hard_gates = {
                "synthesis_complete": all(field in synthesis for field in ROLE_CATALOG["plan-synthesizer"].output_fields),
                "kpis_present": isinstance(synthesis.get("kpis"), list) and bool(synthesis.get("kpis")),
                "sla_present": isinstance(synthesis.get("sla"), (list, dict)) and bool(synthesis.get("sla")),
                "ten_use_cases": _valid_case_set(synthesis.get("use_cases")),
                "ten_test_cases": _valid_case_set(synthesis.get("test_cases")),
                "ten_failure_cases": _valid_case_set(synthesis.get("failure_cases")),
                "all_required_reviews_accept_same_digest": required_reviews_accept,
                "exact_model_receipts": all(
                    bool(result.get("model_served"))
                    for key, result in inputs.items()
                    if key.startswith("plan-review") or key in {"plan-synthesis", "plan-revision"}
                ),
            }
            acceptance = ""
            intake = inputs.get("intake", {}).get("output") or {}
            if isinstance(intake, dict):
                acceptance = str(intake.get("acceptance") or "")
            mncg = evaluate_minimum_change_gate(
                synthesis,
                goal=goal,
                task_id=task_id,
                risk_class=risk_class,
                acceptance=acceptance or goal,
                context_digest=plan_digest,
            )
            hard_gates["minimum_change_assessment_valid"] = bool(mncg.get("valid"))
            decision = "accept" if all(hard_gates.values()) else "needs-review"
            return {
                "status": "pass",
                "output": {
                    "decision": decision,
                    "plan_digest": plan_digest,
                    "acceptance_matrix": acceptance_matrix,
                    "hard_gates": hard_gates,
                    "dissent": dissent,
                    "mncg": mncg,
                },
            }
        if node.node_id == "final-plan-gate":
            first = inputs.get("plan-acceptance", {}).get("output") or {}
            second_result = inputs.get("plan-acceptance-r2", {})
            second = second_result.get("output") or {}
            if second_result.get("status") == "pass" and second.get("decision") == "accept":
                chosen = second
                selected_round = 2
            else:
                chosen = first
                selected_round = 1
            decision = "accept" if chosen.get("decision") == "accept" else "needs-review"
            return {
                "status": "pass",
                "output": {
                    "decision": decision,
                    "plan_digest": chosen.get("plan_digest"),
                    "acceptance_matrix": chosen.get("acceptance_matrix", {}),
                    "hard_gates": chosen.get("hard_gates", {}),
                    "dissent": chosen.get("dissent", []),
                    "selected_round": selected_round,
                    "mncg": chosen.get("mncg"),
                },
            }
        if node.node_id == "deterministic-tests":
            implementation = inputs.get("implement", {})
            parsed = implementation.get("parsed") or implementation.get("output") or {}
            tests = parsed.get("tests") if isinstance(parsed, dict) else None
            passed = isinstance(tests, list) and bool(tests) and all(
                isinstance(test, dict) and test.get("decision") in {"pass", "approve"} for test in tests
            )
            return {
                "status": "pass" if passed else "failed",
                "failure_class": None if passed else "deterministic-tests-missing-or-failed",
                "output": {
                    "test_results": tests or [],
                    "hard_gates": {"tests_present": bool(tests), "all_tests_pass": passed},
                    "evidence_refs": parsed.get("evidence_refs", []) if isinstance(parsed, dict) else [],
                },
            }
        if node.node_id == "final-audit":
            plan = inputs.get("final-plan-gate", {}).get("output") or {}
            if execute:
                verifier = inputs.get("final-verifier", {})
                verifier_output = verifier.get("parsed") or verifier.get("output") or {}
                verifier_pass = (
                    verifier.get("status") == "pass"
                    and isinstance(verifier_output, dict)
                    and verifier_output.get("verdict") in {"PASS", "pass", "approve", "accept"}
                )
                hard_gates = {
                    "plan_accepted": plan.get("decision") == "accept",
                    "final_verifier_pass": verifier_pass,
                    "no_active_failure": result_status(inputs) == "pass",
                }
            else:
                hard_gates = {
                    "plan_accepted": plan.get("decision") == "accept",
                    "no_active_failure": result_status(inputs) == "pass",
                }
            skills_cfg = settings.get("skills") or {}
            visual = evaluate_visual_acceptance(
                visual_task=is_visual_task(goal),
                require_browser_acceptance=bool(skills_cfg.get("require_browser_acceptance")),
                evidence=(inputs.get("implement", {}).get("parsed") or {}).get("visual_evidence")
                if isinstance(inputs.get("implement", {}).get("parsed"), dict)
                else None,
            )
            hard_gates["visual_acceptance"] = visual.get("decision") in {"pass", "not-applicable", "VISUAL_ACCEPTANCE_TOOL_UNAVAILABLE"}
            hard_gates["visual_acceptance_claim"] = bool(visual.get("visual_acceptance_claim"))
            if visual.get("decision") == "block":
                hard_gates["visual_acceptance"] = False
            decision = "accept" if all(value is True for key, value in hard_gates.items() if key != "visual_acceptance_claim") else "needs-review"
            return {
                "status": "pass",
                "output": {
                    "decision": decision,
                    "plan_digest": plan.get("plan_digest"),
                    "hard_gates": hard_gates,
                    "findings": plan.get("dissent", []),
                    "evidence_refs": [],
                    "visual_acceptance": visual,
                },
            }
        if node.node_id == "publish-knowledge":
            audit_output = inputs["final-audit"]["output"]
            content = json.dumps(
                {"goal": goal, "task_id": task_id, "meeting_id": meeting_id, "audit": audit_output},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            artifact = write_artifact(
                user_home,
                kind="decision",
                title=f"IOT-AI decision: {goal[:80]}",
                content=content,
                source_ids={
                    "graph_id": active_graph.graph_id,
                    "correlation_id": active_graph.correlation_id,
                    "task_id": task_id,
                    "meeting_id": meeting_id,
                },
                visibility="private",
                privacy_class=privacy_class,
                tags=["agentic", "graph", risk_class],
            )
            return {
                "status": "pass",
                "output": {
                    "artifact_id": artifact["artifact_id"],
                    "content_sha256": artifact["integrity"]["content_sha256"],
                    "diagnostics_bundle": None,
                },
            }

        contract = ROLE_CATALOG[node.role_id]
        plan_digest = None
        if node.stage in {"plan-digest-review", "plan-digest-review-r2"}:
            synthesis_key = "plan-revision" if node.stage.endswith("r2") else "plan-synthesis"
            synthesis = inputs.get(synthesis_key, {})
            parsed_synthesis = synthesis.get("parsed") or synthesis.get("output") or {}
            if isinstance(parsed_synthesis, dict):
                body = {key: value for key, value in parsed_synthesis.items() if key != "plan_digest"}
                plan_digest = parsed_synthesis.get("plan_digest") or hashlib.sha256(
                    json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest()
        node_contract = {
            "schema": "iot-ai.graph-node-contract.v1",
            "node_id": node.node_id,
            "mission": node.mission,
            "stage": node.stage,
            "node_type": node.node_type,
            "required": node.required,
            "depends_on": list(node.depends_on),
            "read_scope": list(node.read_scope),
            "write_scope": list(node.write_scope),
            "resources": list(node.resources),
            "required_output_fields": list(node.output_schema),
            "frozen_plan_digest": plan_digest,
            "effort": node.effort,
        }
        primary_candidate = candidates.get(node.role_id) or {}
        egress = "local" if primary_candidate.get("provider") == "ollama" and not primary_candidate.get("cloud", True) else "cloud"
        runtime_settings = settings.get("agent_runtime", {})
        context_budget = int(runtime_settings.get("context_token_budget", min(64000, max(12000, graph.token_budget // max(4, len(role_ids))))))
        node_skills = select_skills(
            user_home,
            goal=goal,
            role_id=node.role_id,
            stage=node.stage,
            artifact=node.mission,
            settings=settings,
        )
        context_manifest = compile_context(
            goal_contract=goal_contract.to_dict(),
            role_contract=contract.to_dict(),
            node_contract=node_contract,
            inputs=inputs,
            privacy_class=privacy_class,
            token_budget=context_budget,
            reserve_ratio=float(runtime_settings.get("output_reserve_ratio", 0.2)),
            egress=egress,
            extra_blocks=context_blocks(node_skills),
        )
        finalized_skills = finalize_skill_state(
            node_skills,
            context_manifest.to_dict(include_payloads=False),
            egress=egress,
        )
        node_skills = {**node_skills, **finalized_skills}
        context_validation = validate_context_manifest(context_manifest)
        node_runtime_root = runtime_root / node.node_id
        atomic_json(node_runtime_root / "context-manifest.json", context_manifest.to_dict(include_payloads=True))
        if context_validation["decision"] != "pass":
            return {
                "status": "blocked",
                "failure_class": "context-compilation-blocked",
                "output": {},
                "_runtime_decisions": {
                    "context_decision": {
                        "decision": "block",
                        "context_id": context_manifest.context_id,
                        "context_digest": context_manifest.digest,
                        "blockers": list(context_manifest.blockers),
                        "selected_blocks": len(context_manifest.selected),
                        "excluded_blocks": len(context_manifest.excluded),
                    },
                    "tool_decision": {
                        "decision": "not-run",
                        "reason": "context gate blocked provider dispatch",
                    },
                    "validation_decision": context_validation,
                    "persistence_decision": {
                        "decision": "pass",
                        "stored": ["goal-contract", "context-manifest", "context-blocker"],
                        "excluded": ["provider-call"],
                    },
                },
            }
        policy = {
            "evidence_first": True,
            "no_fabrication": True,
            "no_scope_expansion": True,
            "output_json_required": True,
            "do_not_echo_secrets": True,
            "article_5_screen": article5.to_dict(),
            "article_50_disclosure_required": True,
            "no_global_compliance_claim": True,
            "goal_first": True,
            "application_owns_control_flow": True,
            "do_not_reveal_private_chain_of_thought": True,
            "skill_selection": node_skills.get("receipt"),
        }
        prompt_artifact = compile_prompt(
            goal_contract=goal_contract.to_dict(),
            role_contract=contract.to_dict(),
            node_contract=node_contract,
            context_manifest=context_manifest,
            policy=policy,
        )
        prompt_validation = validate_prompt(prompt_artifact)
        prompt_record = prompt_artifact.to_dict(
            include_text=bool(settings.get("telemetry", {}).get("store_raw_prompts", False))
        )
        atomic_json(node_runtime_root / "prompt-artifact.json", prompt_record)
        if prompt_validation["decision"] != "pass":
            return {
                "status": "blocked",
                "failure_class": "prompt-compilation-blocked",
                "output": {},
                "_runtime_decisions": {
                    "context_decision": {
                        "decision": "pass",
                        "context_id": context_manifest.context_id,
                        "context_digest": context_manifest.digest,
                    },
                    "tool_decision": {"decision": "not-run", "reason": "prompt validation failed"},
                    "validation_decision": prompt_validation,
                    "persistence_decision": {
                        "decision": "pass",
                        "stored": ["prompt-metadata", "context-manifest"],
                        "excluded": ["provider-call"],
                    },
                },
            }
        provider_context = {
            "context_id": context_manifest.context_id,
            "context_digest": context_manifest.digest,
            "prompt_id": prompt_artifact.prompt_id,
            "prompt_sha256": prompt_artifact.sha256,
            "dependency_ids": list(inputs),
        }
        value = provider_executor(node, prompt_artifact.text, provider_context)
        if not isinstance(value, dict):
            value = {"status": "failed", "failure_class": "provider-executor-returned-non-object", "output": {}}
        runtime_decisions = value.setdefault("_runtime_decisions", {})
        runtime_decisions["context_decision"] = {
            "decision": "pass",
            "context_id": context_manifest.context_id,
            "context_digest": context_manifest.digest,
            "token_budget": context_manifest.token_budget,
            "used_tokens": context_manifest.used_tokens,
            "reserved_output_tokens": context_manifest.reserved_output_tokens,
            "selected_blocks": len(context_manifest.selected),
            "excluded_blocks": len(context_manifest.excluded),
            "no_silent_truncation": True,
            "egress": egress,
        }
        runtime_decisions.setdefault(
            "tool_decision",
            {
                "decision": "pass" if value.get("status") == "pass" else "block",
                "selection_reason": "explicit external/test executor",
                "provider": value.get("provider"),
                "model_served": value.get("model_served"),
            },
        )
        runtime_decisions["validation_decision"] = {
            "decision": "pass" if context_validation["decision"] == prompt_validation["decision"] == "pass" else "block",
            "context_validation": context_validation,
            "prompt_validation": prompt_validation,
        }
        runtime_decisions["persistence_decision"] = {
            "decision": "pass",
            "stored": ["goal-contract", "context-manifest", "prompt-metadata", "provider-receipt", "turn-receipt"],
            "raw_prompt_stored": bool(settings.get("telemetry", {}).get("store_raw_prompts", False)),
            "raw_output_stored": bool(settings.get("telemetry", {}).get("store_raw_outputs", False)),
            "excluded": ["credentials", "private-chain-of-thought"],
        }
        parsed = value.get("parsed") if isinstance(value, dict) else None
        if not isinstance(parsed, dict):
            parsed = _parse_model_output(str((value or {}).get("output") or "")) if isinstance(value, dict) else {"decision": "block"}
            if isinstance(value, dict):
                value["parsed"] = parsed
        if node.node_id in {"plan-synthesis", "plan-revision"}:
            body = {key: val for key, val in parsed.items() if key != "plan_digest"}
            parsed["plan_digest"] = hashlib.sha256(
                json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
        runtime_decisions["skill_state"] = (node_skills.get("skill_state") or (node_skills.get("receipt") or {}).get("skill_state"))
        if node.node_id == "implement":
            accepted = (inputs.get("final-plan-gate") or {}).get("output") or {}
            bind = bind_implementation_to_accepted_plan(
                parsed,
                accepted,
                goal=goal,
                task_id=task_id,
                risk_class=risk_class,
                acceptance=goal,
            )
            runtime_decisions["mncg_writer_bind"] = bind
            if not bind.get("valid"):
                value["status"] = "blocked"
                value["failure_class"] = "implementation-not-bound-to-accepted-mncg"
        return value

    def result_status(values: dict[str, Any]) -> str:
        return "pass" if all(value.get("status") == "pass" for value in values.values()) else "blocked"

    record_event(
        user_home,
        graph.correlation_id,
        {
            "event": "agentic.goal.accepted",
            "status": "running",
            "goal_sha256": hashlib.sha256(goal.encode()).hexdigest(),
            "task_id": task_id,
            "meeting_id": meeting_id,
            "candidate_roles": candidates,
        },
    )
    result = execute_graph(user_home, graph, executor)
    _finish_run(user_home, task_id, meeting_id, result, execute)
    diagnostics_path = data_root(user_home) / "diagnostics" / f"IOT-AI-DIAGNOSTICS-{graph.correlation_id}.zip"
    try:
        diagnostics = collect_diagnostics(user_home, graph.correlation_id, diagnostics_path)
    except Exception as exc:  # diagnostics failure must be explicit
        diagnostics = {"decision": "block", "error": str(exc)}
    generated_body = json.dumps(
        {key: value for key, value in result.items() if key in {"decision", "results", "failure_class", "metrics"}},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    served_models = sorted({
        str(value.get("model_served"))
        for value in (result.get("results") or {}).values()
        if isinstance(value, dict) and value.get("model_served")
    })
    served_providers = sorted({
        str(value.get("provider"))
        for value in (result.get("results") or {}).values()
        if isinstance(value, dict) and value.get("provider")
    })
    content_provenance = runtime_output_provenance(
        generated_body,
        content_type="application/json",
        model_providers=served_providers,
        model_ids=served_models,
    )
    result.update(
        {
            "diagnostics": diagnostics,
            "provider_selection": candidates,
            "profile": active_profile,
            "task_id": task_id,
            "meeting_id": meeting_id,
            "article_5": article5.to_dict(),
            "article_6": article6,
            "article_50": disclosure,
            "content_provenance": content_provenance,
            "goal_contract": goal_contract.to_dict(),
            "agent_runtime": {
                "prompt_owned": True,
                "context_owned": True,
                "tools_owned": True,
                "control_flow_owned": True,
                "five_decision_receipts": True,
                "checkpoint_path": str(run_root(user_home, graph.correlation_id) / "07_CHECKPOINT" / "checkpoint.json"),
            },
            "global_compliance_claim_allowed": False,
            "effective_settings_digest": effective.get("effective_settings_digest"),
            "skill_selection": skill_selection.get("receipt"),
        }
    )
    return result
