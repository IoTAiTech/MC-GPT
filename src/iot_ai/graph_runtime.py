# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
"""Dependency-aware and resource-aware execution graph compiler/runtime."""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .checkpoints import load_checkpoint, save_checkpoint
from .control_flow import ControlFlowState, continuation_decision
from .decision_receipts import build_turn_receipt, persist_turn_receipt
from .diagnostics import persist_graph_contract, persist_node_result, record_event
from .roles import ROLE_CATALOG, select_roles
from .util import utc_now
from .workspace import connect_write, new_id


@dataclass(slots=True)
class GraphNode:
    node_id: str
    role_id: str
    mission: str
    node_type: str = "agent"
    depends_on: tuple[str, ...] = ()
    required: bool = True
    output_schema: tuple[str, ...] = ()
    read_scope: tuple[str, ...] = ()
    write_scope: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()
    effort: str = "medium"
    provider_family: str | None = None
    model: str | None = None
    stage: str = "analysis"
    condition: dict[str, Any] | None = None


@dataclass(slots=True)
class GraphEdge:
    source: str
    target: str
    edge_type: str = "data"
    resource: str | None = None


@dataclass(slots=True)
class ExecutionGraph:
    graph_id: str
    correlation_id: str
    goal: str
    risk_class: str
    privacy_class: str
    max_parallel: int
    token_budget: int
    wall_clock_seconds: int
    max_model_calls: int
    goal_contract_digest: str = ""
    knowledge_mode: str = "full-analysis"
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
        }


class GraphValidationError(ValueError):
    """Raised when graph contracts cannot be scheduled safely."""


def _role_fields(role_id: str) -> tuple[str, ...]:
    return ROLE_CATALOG[role_id].output_fields


def compile_graph(
    goal: str,
    *,
    include_implementation: bool = False,
    risk_class: str = "R2",
    privacy_class: str = "D1",
    max_parallel: int = 6,
    token_budget: int = 250_000,
    wall_clock_seconds: int = 3600,
    max_model_calls: int = 32,
    knowledge_mode: str = "full-analysis",
    goal_contract_digest: str = "",
) -> ExecutionGraph:
    """Compile a goal into a typed DAG with explicit plan and execution gates."""
    roles = select_roles(goal, include_implementation=include_implementation)
    digest = hashlib.sha256(goal.encode("utf-8")).hexdigest()[:16]
    correlation_id = f"corr-{digest}-{int(time.time())}"
    graph = ExecutionGraph(
        graph_id=f"graph-{digest}-{int(time.time_ns()) % 1_000_000:06d}",
        correlation_id=correlation_id,
        goal=goal,
        risk_class=risk_class,
        privacy_class=privacy_class,
        max_parallel=max(1, min(max_parallel, 16)),
        token_budget=max(1_000, token_budget),
        wall_clock_seconds=max(30, wall_clock_seconds),
        max_model_calls=max(1, max_model_calls),
        goal_contract_digest=goal_contract_digest,
        knowledge_mode=knowledge_mode if knowledge_mode in {"full-analysis", "mini-review"} else "full-analysis",
    )

    graph.nodes.extend(
        [
            GraphNode(
                "intake",
                "requirements-analyst",
                "Normalize the original goal into 5W1H, constraints, risks, KPI and acceptance requirements.",
                "deterministic",
                output_schema=("goal", "5w1h", "constraints", "acceptance"),
                effort="low",
                stage="intake",
            ),
            GraphNode(
                "knowledge",
                "requirements-analyst",
                "Retrieve validated prior knowledge and identify only the missing questions.",
                "deterministic",
                depends_on=("intake",),
                output_schema=("coverage", "artifact_refs", "gap_questions", "mode", "knowledge_context"),
                effort="low",
                stage="knowledge",
            ),
        ]
    )

    excluded = {
        "requirements-analyst",
        "plan-synthesizer",
        "implementation-engineer",
        "quality-verifier",
        "independent-judge",
    }
    analysis_nodes: list[str] = []
    analysis_roles = [role for role in roles if role.role_id not in excluded]
    if graph.knowledge_mode == "mini-review":
        retained = [role for role in analysis_roles if role.role_id == "security-challenger"]
        analysis_roles = [ROLE_CATALOG["quality-verifier"], *retained]
    for role in analysis_roles:
        node_id = f"analysis-{role.role_id}"
        graph.nodes.append(
            GraphNode(
                node_id=node_id,
                role_id=role.role_id,
                mission=role.mission,
                depends_on=("knowledge",),
                required=role.required,
                output_schema=role.output_fields,
                resources=(f"provider-role:{role.role_id}",),
                effort=role.default_effort,
                stage="analysis",
            )
        )
        analysis_nodes.append(node_id)

    graph.nodes.append(
        GraphNode(
            "normalize",
            "requirements-analyst",
            "Normalize, deduplicate and group findings; preserve contradictions and evidence gaps.",
            "deterministic",
            depends_on=tuple(analysis_nodes) or ("knowledge",),
            output_schema=("domain_summaries", "contradictions", "evidence_matrix", "new_findings"),
            effort="low",
            stage="layered-fan-in",
        )
    )
    challenge_nodes: list[str] = []
    if graph.knowledge_mode == "full-analysis" and risk_class in {"R2", "R3", "R4"}:
        for role in analysis_roles:
            node_id = f"challenge-{role.role_id}"
            graph.nodes.append(
                GraphNode(
                    node_id=node_id,
                    role_id=role.role_id,
                    mission="Challenge the normalized findings from this specialist perspective; identify unsupported claims, contradictions and missing evidence.",
                    node_type="agent",
                    depends_on=("normalize",),
                    output_schema=("decision", "challenged_findings", "accepted_findings", "new_risks", "evidence_refs"),
                    resources=(f"challenge-role:{role.role_id}",),
                    effort=role.default_effort,
                    stage="cross-critique",
                )
            )
            challenge_nodes.append(node_id)

    graph.nodes.append(
        GraphNode(
            "plan-synthesis",
            "plan-synthesizer",
            "Create one evidence-bound plan with direct answer, architecture, KPI/SLA and 10/10/10 cases.",
            "agent",
            depends_on=("normalize", *challenge_nodes),
            output_schema=_role_fields("plan-synthesizer"),
            resources=("decision:plan-synthesis",),
            effort="xhigh",
            stage="plan-synthesis",
        )
    )

    review_role_ids = ["requirements-analyst", *[role.role_id for role in analysis_roles], "quality-verifier"]
    review_nodes: list[str] = []
    for role_id in dict.fromkeys(review_role_ids):
        contract = ROLE_CATALOG[role_id]
        node_id = f"plan-review-{role_id}"
        graph.nodes.append(
            GraphNode(
                node_id,
                role_id,
                "Blindly review only the frozen plan; accept its exact digest or return explicit evidence-bound dissent.",
                "agent",
                depends_on=("plan-synthesis",),
                output_schema=("decision", "plan_digest", "dissent", "evidence_refs"),
                resources=(f"review-role:{role_id}",),
                effort=contract.default_effort,
                stage="plan-digest-review",
            )
        )
        review_nodes.append(node_id)

    graph.nodes.append(
        GraphNode(
            "plan-acceptance",
            "independent-judge",
            "Verify all required roles accepted the same plan digest and all planning hard gates passed.",
            "deterministic",
            depends_on=("plan-synthesis", *review_nodes),
            output_schema=("decision", "plan_digest", "acceptance_matrix", "hard_gates", "dissent"),
            effort="low",
            stage="plan-acceptance",
        )
    )

    revision_condition = {"node": "plan-acceptance", "path": "output.decision", "equals": "needs-review"}
    graph.nodes.append(
        GraphNode(
            "plan-revision",
            "plan-synthesizer",
            "Revise only the frozen plan gaps and dissent; preserve accepted content and produce a new complete digest.",
            "agent",
            depends_on=("normalize", "plan-synthesis", "plan-acceptance"),
            required=False,
            output_schema=_role_fields("plan-synthesizer"),
            resources=("decision:plan-synthesis",),
            effort="xhigh",
            stage="plan-revision",
            condition=revision_condition,
        )
    )
    review_nodes_r2: list[str] = []
    for role_id in dict.fromkeys(review_role_ids):
        contract = ROLE_CATALOG[role_id]
        node_id = f"plan-review-r2-{role_id}"
        graph.nodes.append(
            GraphNode(
                node_id,
                role_id,
                "Blindly review the revised frozen plan; accept its exact digest or return explicit evidence-bound dissent.",
                "agent",
                depends_on=("plan-revision",),
                required=False,
                output_schema=("decision", "plan_digest", "dissent", "evidence_refs"),
                resources=(f"review-role:{role_id}",),
                effort=contract.default_effort,
                stage="plan-digest-review-r2",
                condition=revision_condition,
            )
        )
        review_nodes_r2.append(node_id)
    graph.nodes.append(
        GraphNode(
            "plan-acceptance-r2",
            "independent-judge",
            "Verify required roles accepted the revised plan digest and the planning hard gates passed.",
            "deterministic",
            depends_on=("plan-revision", *review_nodes_r2),
            required=False,
            output_schema=("decision", "plan_digest", "acceptance_matrix", "hard_gates", "dissent"),
            effort="low",
            stage="plan-acceptance-r2",
            condition=revision_condition,
        )
    )
    graph.nodes.append(
        GraphNode(
            "final-plan-gate",
            "independent-judge",
            "Choose the latest accepted plan without rewriting dissent; otherwise preserve needs-review.",
            "deterministic",
            depends_on=("plan-acceptance", "plan-acceptance-r2"),
            output_schema=("decision", "plan_digest", "acceptance_matrix", "hard_gates", "dissent", "selected_round"),
            effort="low",
            stage="final-plan-gate",
        )
    )

    if include_implementation:
        condition = {"node": "final-plan-gate", "path": "output.decision", "equals": "accept"}
        graph.nodes.extend(
            [
                GraphNode(
                    "implement",
                    "implementation-engineer",
                    "Implement only the accepted plan in the declared isolated write scope.",
                    "agent",
                    depends_on=("final-plan-gate",),
                    output_schema=_role_fields("implementation-engineer"),
                    write_scope=("task-authorized-worktree",),
                    resources=("write:task-worktree",),
                    effort="high",
                    stage="implementation",
                    condition=condition,
                ),
                GraphNode(
                    "deterministic-tests",
                    "quality-verifier",
                    "Run the configured unit, integration, smoke, A/B, stress, security, E2E and quality gates.",
                    "deterministic",
                    depends_on=("implement",),
                    output_schema=("test_results", "hard_gates", "evidence_refs"),
                    resources=("test:task-worktree",),
                    effort="low",
                    stage="test",
                ),
                GraphNode(
                    "final-verifier",
                    "quality-verifier",
                    "Independently verify the implementation, evidence and rollback against the accepted plan.",
                    "agent",
                    depends_on=("deterministic-tests",),
                    output_schema=_role_fields("quality-verifier"),
                    resources=("verification:final",),
                    effort="xhigh",
                    stage="final-verification",
                ),
                GraphNode(
                    "final-audit",
                    "independent-judge",
                    "Apply final hard gates without rewriting failed or dissenting evidence.",
                    "deterministic",
                    depends_on=("final-plan-gate", "final-verifier"),
                    output_schema=("decision", "plan_digest", "hard_gates", "findings", "evidence_refs"),
                    effort="low",
                    stage="audit",
                ),
            ]
        )
    else:
        graph.nodes.append(
            GraphNode(
                "final-audit",
                "independent-judge",
                "Record the planning verdict, dissent and unresolved evidence without authorizing implementation.",
                "deterministic",
                depends_on=("final-plan-gate",),
                output_schema=("decision", "plan_digest", "hard_gates", "findings", "evidence_refs"),
                effort="low",
                stage="audit",
            )
        )

    graph.nodes.append(
        GraphNode(
            "publish-knowledge",
            "requirements-analyst",
            "Publish a versioned knowledge artifact and diagnostics pointer after the audit.",
            "deterministic",
            depends_on=("final-audit",),
            output_schema=("artifact_id", "content_sha256", "diagnostics_bundle"),
            effort="low",
            stage="knowledge-write",
        )
    )

    edge_keys: set[tuple[str, str, str, str | None]] = set()
    for node in graph.nodes:
        for dependency in node.depends_on:
            if node.node_id in {"plan-acceptance", "plan-acceptance-r2", "final-plan-gate", "implement"}:
                edge_type = "approval"
            elif node.node_id in {"final-audit", "publish-knowledge"}:
                edge_type = "evidence"
            elif node.node_id in {"deterministic-tests", "final-verifier"}:
                edge_type = "control"
            else:
                edge_type = "data"
            key = (dependency, node.node_id, edge_type, None)
            if key not in edge_keys:
                graph.edges.append(GraphEdge(*key))
                edge_keys.add(key)
        for resource in node.resources:
            key = (node.node_id, node.node_id, "resource_lock", resource)
            if key not in edge_keys:
                graph.edges.append(GraphEdge(*key))
                edge_keys.add(key)

    validate_graph(graph)
    return graph


def validate_graph(graph: ExecutionGraph) -> dict[str, Any]:
    node_ids = [node.node_id for node in graph.nodes]
    if len(node_ids) != len(set(node_ids)):
        raise GraphValidationError("duplicate node id")
    known = set(node_ids)
    for node in graph.nodes:
        missing = set(node.depends_on) - known
        if missing:
            raise GraphValidationError(f"node {node.node_id} depends on unknown nodes: {sorted(missing)}")
        if node.node_type not in {"agent", "deterministic", "approval"}:
            raise GraphValidationError(f"invalid node type: {node.node_type}")
        if not node.output_schema:
            raise GraphValidationError(f"node {node.node_id} has no output schema")
        if set(node.read_scope) & set(node.write_scope):
            raise GraphValidationError(f"node {node.node_id} has overlapping read/write scope")
    dependencies = {node.node_id: set(node.depends_on) for node in graph.nodes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise GraphValidationError("cycle detected")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency in dependencies[node_id]:
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in node_ids:
        visit(node_id)
    return {"decision": "pass", "nodes": len(node_ids), "edges": len(graph.edges)}


def topological_layers(graph: ExecutionGraph) -> list[list[GraphNode]]:
    remaining = {node.node_id: node for node in graph.nodes}
    completed: set[str] = set()
    layers: list[list[GraphNode]] = []
    while remaining:
        ready = sorted(
            (node for node in remaining.values() if set(node.depends_on) <= completed),
            key=lambda node: node.node_id,
        )
        if not ready:
            raise GraphValidationError("graph cannot be scheduled")
        layers.append(ready)
        for node in ready:
            completed.add(node.node_id)
            remaining.pop(node.node_id)
    return layers


def resource_waves(nodes: list[GraphNode]) -> list[list[GraphNode]]:
    """Partition a topological layer so conflicting resources never run together."""
    waves: list[list[GraphNode]] = []
    for node in nodes:
        node_resources = set(node.resources)
        placed = False
        for wave in waves:
            held = {resource for candidate in wave for resource in candidate.resources}
            if node_resources.isdisjoint(held):
                wave.append(node)
                placed = True
                break
        if not placed:
            waves.append([node])
    return waves


NodeExecutor = Callable[[GraphNode, dict[str, Any], ExecutionGraph], dict[str, Any]]


def _get_path(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _condition_satisfied(node: GraphNode, results: dict[str, dict[str, Any]]) -> bool:
    if not node.condition:
        return True
    source = results.get(str(node.condition.get("node")), {})
    return _get_path(source, str(node.condition.get("path", ""))) == node.condition.get("equals")


def _validate_output(node: GraphNode, value: dict[str, Any]) -> dict[str, Any]:
    if value.get("status") not in {None, "pass"}:
        return value
    output = value.get("parsed") or value.get("output")
    if not isinstance(output, dict):
        value["status"] = "failed"
        value["failure_class"] = "invalid-output-contract"
        value["missing_output_fields"] = list(node.output_schema)
        return value
    missing = [field for field in node.output_schema if field not in output]
    if missing:
        value["status"] = "failed"
        value["failure_class"] = "missing-output-fields"
        value["missing_output_fields"] = missing
    return value


def _persist_graph_start(user_home: Path, graph: ExecutionGraph) -> None:
    connection = connect_write(user_home)
    try:
        now = utc_now()
        connection.execute(
            """INSERT OR REPLACE INTO graph_runs(
            id,correlation_id,goal,risk_class,privacy_class,status,token_budget,tokens_used,
            wall_clock_seconds,max_parallel,created_at,updated_at)
            VALUES(?,?,?,?,?,'running',?,0,?,?,?,?)""",
            (
                graph.graph_id,
                graph.correlation_id,
                graph.goal,
                graph.risk_class,
                graph.privacy_class,
                graph.token_budget,
                graph.wall_clock_seconds,
                graph.max_parallel,
                now,
                now,
            ),
        )
        for node in graph.nodes:
            contract = {
                "role_id": node.role_id,
                "mission": node.mission,
                "required": node.required,
                "read_scope": node.read_scope,
                "write_scope": node.write_scope,
                "output_schema": node.output_schema,
                "condition": node.condition,
            }
            contract_sha = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
            connection.execute(
                """INSERT OR REPLACE INTO role_bindings(
                id,graph_id,node_id,role_id,contract_sha256,provider_candidate_id,provider,model,
                authority_json,output_schema_json,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    new_id("rb"),
                    graph.graph_id,
                    node.node_id,
                    node.role_id,
                    contract_sha,
                    None,
                    None,
                    None,
                    json.dumps({"read_scope": node.read_scope, "write_scope": node.write_scope}, sort_keys=True),
                    json.dumps(node.output_schema),
                    now,
                ),
            )
        connection.commit()
    finally:
        connection.close()


def _persist_node(user_home: Path, graph: ExecutionGraph, node: GraphNode, value: dict[str, Any]) -> None:
    connection = connect_write(user_home)
    try:
        now = utc_now()
        output = value.get("parsed") or value.get("output") or {}
        output_sha = hashlib.sha256(
            json.dumps(output, sort_keys=True, ensure_ascii=False, default=str).encode()
        ).hexdigest()
        connection.execute(
            """INSERT OR REPLACE INTO graph_nodes(
            id,graph_id,role_id,node_type,stage,required,status,provider,model_requested,model_served,
            effort_requested,effort_effective,latency_ms,input_tokens,cached_tokens,output_tokens,
            reasoning_tokens,output_sha256,failure_class,evidence_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                node.node_id,
                graph.graph_id,
                node.role_id,
                node.node_type,
                node.stage,
                int(node.required),
                value.get("status", "unknown"),
                value.get("provider"),
                value.get("model_requested"),
                value.get("model_served"),
                value.get("effort_requested", node.effort),
                value.get("effort_effective", node.effort),
                value.get("latency_ms") or value.get("duration_ms"),
                value.get("input_tokens"),
                value.get("cached_tokens"),
                value.get("output_tokens"),
                value.get("reasoning_tokens"),
                output_sha,
                value.get("failure_class"),
                json.dumps(value.get("evidence_refs", [])),
                now,
                now,
            ),
        )
        candidate_id = value.get("candidate_id")
        if candidate_id:
            connection.execute(
                """UPDATE role_bindings SET provider_candidate_id=?,provider=?,model=?
                WHERE graph_id=? AND node_id=?""",
                (candidate_id, value.get("provider"), value.get("model_served") or value.get("model_requested"), graph.graph_id, node.node_id),
            )
        connection.commit()
    finally:
        connection.close()


def _persist_graph_finish(user_home: Path, graph: ExecutionGraph, payload: dict[str, Any]) -> None:
    connection = connect_write(user_home)
    try:
        acceptance = ((payload.get("results") or {}).get("plan-acceptance") or {}).get("output") or {}
        metrics = payload.get("metrics") or {}
        connection.execute(
            """UPDATE graph_runs SET status=?,plan_digest=?,tokens_used=?,elapsed_ms=?,parallel_efficiency=?,updated_at=? WHERE id=?""",
            (
                payload.get("decision"),
                acceptance.get("plan_digest"),
                metrics.get("tokens_used", 0),
                metrics.get("elapsed_ms"),
                metrics.get("parallel_efficiency"),
                utc_now(),
                graph.graph_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def execute_graph(
    user_home: Path,
    graph: ExecutionGraph,
    executor: NodeExecutor,
    *,
    resume: bool = False,
    pause_after_nodes: int | None = None,
) -> dict[str, Any]:
    """Execute a graph with owned control flow, checkpoints and turn receipts."""
    started = time.monotonic()
    graph_payload = graph.to_dict()
    checkpoint = load_checkpoint(user_home, graph.correlation_id, graph_payload) if resume else None
    if checkpoint is None:
        _persist_graph_start(user_home, graph)
    persist_graph_contract(user_home, graph.correlation_id, graph_payload)

    results: dict[str, dict[str, Any]] = dict((checkpoint or {}).get("results") or {})
    model_calls = int((checkpoint or {}).get("model_calls") or 0)
    tokens_used = int((checkpoint or {}).get("tokens_used") or 0)
    node_timings: dict[str, int] = {
        str(key): int(value) for key, value in ((checkpoint or {}).get("node_timings") or {}).items()
    }
    control_state = ControlFlowState(
        graph_id=graph.graph_id,
        completed_nodes=sorted(results),
        model_calls=model_calls,
        tokens_used=tokens_used,
    )
    completed_this_invocation = 0
    record_event(
        user_home,
        graph.correlation_id,
        {
            "event": "graph.resumed" if checkpoint else "graph.started",
            "graph_id": graph.graph_id,
            "status": "running",
            "checkpoint_loaded": bool(checkpoint),
        },
    )

    for layer in topological_layers(graph):
        pending = [node for node in layer if node.node_id not in results]
        if not pending:
            continue
        for wave in resource_waves(pending):
            elapsed_seconds = time.monotonic() - started
            if elapsed_seconds > graph.wall_clock_seconds:
                payload = _summary(graph, results, node_timings, tokens_used, model_calls, started, "blocked", "wall-clock-budget")
                save_checkpoint(
                    user_home,
                    graph.correlation_id,
                    graph=graph_payload,
                    results=results,
                    node_timings=node_timings,
                    model_calls=model_calls,
                    tokens_used=tokens_used,
                    status="blocked",
                )
                _persist_graph_finish(user_home, graph, payload)
                record_event(user_home, graph.correlation_id, {"event": "graph.finished", "status": "blocked", "failure_class": "wall-clock-budget", "metrics": payload["metrics"]})
                return payload

            def run_node(node: GraphNode) -> tuple[GraphNode, dict[str, Any], int]:
                if not _condition_satisfied(node, results):
                    status = "blocked" if node.required else "skipped"
                    return node, {"status": status, "failure_class": "condition-not-satisfied", "output": {}}, 0
                t0 = time.monotonic()
                try:
                    inputs = {dependency: results[dependency] for dependency in node.depends_on}
                    value = executor(node, inputs, graph)
                    if not isinstance(value, dict):
                        value = {"status": "failed", "failure_class": "executor-returned-non-object", "output": {}}
                except Exception as exc:  # defensive process boundary
                    value = {"status": "failed", "failure_class": type(exc).__name__, "error": str(exc), "output": {}}
                return node, _validate_output(node, value), int((time.monotonic() - t0) * 1000)

            completed: list[tuple[GraphNode, dict[str, Any], int]] = []
            with ThreadPoolExecutor(max_workers=max(1, min(graph.max_parallel, len(wave)))) as pool:
                futures = [pool.submit(run_node, node) for node in wave]
                for future in as_completed(futures):
                    completed.append(future.result())

            for node, value, duration in sorted(completed, key=lambda item: item[0].node_id):
                node_timings[node.node_id] = duration
                value.setdefault("status", "pass")
                value.setdefault("node_id", node.node_id)
                value.setdefault("role_id", node.role_id)
                value.setdefault("duration_ms", duration)
                if node.node_type == "agent":
                    model_calls += 1
                    tokens_used += sum(
                        int(value.get(key) or 0)
                        for key in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens")
                    )
                control_state.model_calls = model_calls
                control_state.tokens_used = tokens_used
                control_state.elapsed_ms = int((time.monotonic() - started) * 1000)
                control_state.completed_nodes.append(node.node_id)

                runtime_decisions = value.pop("_runtime_decisions", {}) if isinstance(value.get("_runtime_decisions"), dict) else {}
                context_decision = runtime_decisions.get("context_decision") or {
                    "decision": "pass",
                    "basis": "deterministic dependency map",
                    "dependencies": list(node.depends_on),
                }
                tool_decision = runtime_decisions.get("tool_decision") or {
                    "decision": "not-applicable",
                    "basis": "deterministic node" if node.node_type != "agent" else "external executor did not provide route receipt",
                }
                validation_decision = {
                    "decision": "pass" if value.get("status") == "pass" else "block",
                    "status": value.get("status"),
                    "failure_class": value.get("failure_class"),
                    "missing_output_fields": value.get("missing_output_fields", []),
                    **(runtime_decisions.get("validation_decision") or {}),
                }
                continuation = continuation_decision(
                    state=control_state,
                    node_id=node.node_id,
                    node_required=node.required,
                    result=value,
                    token_budget=graph.token_budget,
                    max_model_calls=graph.max_model_calls,
                    wall_clock_seconds=graph.wall_clock_seconds,
                )
                persistence_decision = runtime_decisions.get("persistence_decision") or {
                    "decision": "pass",
                    "stored": ["sanitized-node-result", "event", "checkpoint", "turn-receipt"],
                    "excluded": ["credentials", "raw-private-chain-of-thought"],
                }
                receipt = build_turn_receipt(
                    correlation_id=graph.correlation_id,
                    graph_id=graph.graph_id,
                    node_id=node.node_id,
                    role_id=node.role_id,
                    context_decision=context_decision,
                    tool_decision=tool_decision,
                    validation_decision=validation_decision,
                    continuation_decision=continuation,
                    persistence_decision=persistence_decision,
                )
                persist_turn_receipt(user_home, graph.correlation_id, receipt)
                value["turn_decision_receipt"] = {
                    "digest": receipt["digest"],
                    "decision_path": f"06_DECISIONS/{node.node_id}.json",
                }

                results[node.node_id] = value
                persist_node_result(user_home, graph.correlation_id, node.node_id, value)
                _persist_node(user_home, graph, node, value)
                record_event(
                    user_home,
                    graph.correlation_id,
                    {
                        "event": "node.completed",
                        "node_id": node.node_id,
                        "role_id": node.role_id,
                        "status": value.get("status"),
                        "failure_class": value.get("failure_class"),
                        "duration_ms": duration,
                        "turn_decision_digest": receipt["digest"],
                        "continuation_action": continuation["action"],
                    },
                )
                save_checkpoint(
                    user_home,
                    graph.correlation_id,
                    graph=graph_payload,
                    results=results,
                    node_timings=node_timings,
                    model_calls=model_calls,
                    tokens_used=tokens_used,
                    status="running",
                )
                completed_this_invocation += 1

                if node.required and value.get("status") != "pass":
                    payload = _summary(
                        graph,
                        results,
                        node_timings,
                        tokens_used,
                        model_calls,
                        started,
                        "blocked",
                        value.get("failure_class") or "required-node-failed",
                    )
                    save_checkpoint(user_home, graph.correlation_id, graph=graph_payload, results=results, node_timings=node_timings, model_calls=model_calls, tokens_used=tokens_used, status="blocked")
                    _persist_graph_finish(user_home, graph, payload)
                    record_event(user_home, graph.correlation_id, {"event": "graph.finished", "status": "blocked", "failure_class": payload.get("failure_class"), "metrics": payload["metrics"]})
                    return payload
                if continuation["action"] == "stop" and value.get("status") != "pass":
                    payload = _summary(graph, results, node_timings, tokens_used, model_calls, started, "blocked", continuation["reason"])
                    save_checkpoint(user_home, graph.correlation_id, graph=graph_payload, results=results, node_timings=node_timings, model_calls=model_calls, tokens_used=tokens_used, status="blocked")
                    _persist_graph_finish(user_home, graph, payload)
                    return payload
                if model_calls > graph.max_model_calls or tokens_used > graph.token_budget:
                    payload = _summary(graph, results, node_timings, tokens_used, model_calls, started, "blocked", "model-budget")
                    save_checkpoint(user_home, graph.correlation_id, graph=graph_payload, results=results, node_timings=node_timings, model_calls=model_calls, tokens_used=tokens_used, status="blocked")
                    _persist_graph_finish(user_home, graph, payload)
                    record_event(user_home, graph.correlation_id, {"event": "graph.finished", "status": "blocked", "failure_class": "model-budget", "metrics": payload["metrics"]})
                    return payload
                if pause_after_nodes is not None and completed_this_invocation >= max(1, pause_after_nodes):
                    payload = _summary(graph, results, node_timings, tokens_used, model_calls, started, "paused", "operator-or-test-pause")
                    save_checkpoint(user_home, graph.correlation_id, graph=graph_payload, results=results, node_timings=node_timings, model_calls=model_calls, tokens_used=tokens_used, status="paused")
                    record_event(user_home, graph.correlation_id, {"event": "graph.paused", "status": "paused", "metrics": payload["metrics"]})
                    return payload

    final_audit = results.get("final-audit", {}).get("output") or {}
    decision = "pass" if final_audit.get("decision") in {"accept", "pass", "approve"} else "needs-review"
    payload = _summary(graph, results, node_timings, tokens_used, model_calls, started, decision)
    save_checkpoint(user_home, graph.correlation_id, graph=graph_payload, results=results, node_timings=node_timings, model_calls=model_calls, tokens_used=tokens_used, status=decision)
    _persist_graph_finish(user_home, graph, payload)
    record_event(user_home, graph.correlation_id, {"event": "graph.finished", "status": decision, "metrics": payload["metrics"]})
    return payload

def _summary(
    graph: ExecutionGraph,
    results: dict[str, dict[str, Any]],
    timings: dict[str, int],
    tokens: int,
    calls: int,
    started: float,
    decision: str,
    failure_class: str | None = None,
) -> dict[str, Any]:
    elapsed = int((time.monotonic() - started) * 1000)
    critical = sum(
        sum(max((timings.get(node.node_id, 0) for node in wave), default=0) for wave in resource_waves(layer))
        for layer in topological_layers(graph)
    )
    total_node_ms = sum(timings.values())
    parallel_speedup = round(total_node_ms / critical, 3) if critical else 1.0
    parallel_efficiency = round(min(1.0, parallel_speedup / max(1, graph.max_parallel)), 3)
    runtime_utilization = round(min(1.0, total_node_ms / max(1, elapsed * graph.max_parallel)), 3)
    return {
        "schema": "iot-ai.execution-graph-result.v2",
        "decision": decision,
        "failure_class": failure_class,
        "graph": graph.to_dict(),
        "results": results,
        "metrics": {
            "elapsed_ms": elapsed,
            "critical_path_ms": critical,
            "parallel_efficiency": parallel_efficiency,
            "parallel_speedup": parallel_speedup,
            "runtime_utilization": runtime_utilization,
            "model_calls": calls,
            "tokens_used": tokens,
            "passed_nodes": sum(1 for result in results.values() if result.get("status") == "pass"),
            "failed_nodes": sum(1 for result in results.values() if result.get("status") == "failed"),
            "blocked_nodes": sum(1 for result in results.values() if result.get("status") == "blocked"),
            "skipped_nodes": sum(1 for result in results.values() if result.get("status") == "skipped"),
        },
    }
