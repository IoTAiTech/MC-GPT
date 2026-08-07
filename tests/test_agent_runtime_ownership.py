# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from iot_ai.agentic import run_goal
from iot_ai.checkpoints import load_checkpoint, save_checkpoint
from iot_ai.context_compiler import compile_context, validate_context_manifest
from iot_ai.decision_receipts import build_turn_receipt, validate_turn_receipt
from iot_ai.goal_contract import compile_goal_contract, validate_goal_contract
from iot_ai.graph_runtime import ExecutionGraph, GraphNode, execute_graph
from iot_ai.prompt_compiler import compile_prompt, validate_prompt
from iot_ai.owned_delegate import owned_delegate
from iot_ai.roles import ROLE_CATALOG
from iot_ai.status import unified_status
from iot_ai.tool_router import build_tool_decision, validate_provider_binding

from tests.common import IsolatedHomeTestCase


def _role() -> dict:
    return ROLE_CATALOG["security-challenger"].to_dict()


def _node() -> dict:
    return {
        "node_id": "security-review",
        "mission": "Review evidence for security and privacy defects.",
        "stage": "analysis",
        "required_output_fields": ["decision", "findings", "evidence_refs"],
    }


class GoalContractTests(unittest.TestCase):
    def test_goal_contract_is_goal_first_and_digest_stable(self) -> None:
        goal = "Improve the agent runtime because hidden context slows debugging. Do not expose private data. Done when tests pass and evidence is recorded."
        first = compile_goal_contract(goal)
        second = compile_goal_contract(goal)
        self.assertEqual(first.digest, second.digest)
        self.assertIn("Do not expose private data.", first.constraints)
        self.assertTrue(first.success_criteria)
        self.assertIn("outcome matters", first.autonomy_policy)
        self.assertEqual(validate_goal_contract(first)["decision"], "pass")

    def test_goal_contract_detects_tampering(self) -> None:
        payload = compile_goal_contract("Build and verify a bounded workflow with evidence.").to_dict()
        payload["outcome"] = "tampered"
        self.assertEqual(validate_goal_contract(payload)["decision"], "block")

    def test_goal_contract_rejects_unverifiable_short_goal(self) -> None:
        with self.assertRaises(ValueError):
            compile_goal_contract("fix")


class ContextCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.goal = compile_goal_contract("Review security evidence and return a bounded verified result.").to_dict()

    def test_context_is_budgeted_and_no_silent_truncation(self) -> None:
        manifest = compile_context(
            goal_contract=self.goal,
            role_contract=_role(),
            node_contract=_node(),
            inputs={"evidence": {"output": {"findings": ["x" * 50000]}, "status": "pass"}},
            privacy_class="D1",
            token_budget=5000,
            egress="cloud",
        )
        self.assertEqual(validate_context_manifest(manifest)["decision"], "pass")
        self.assertLessEqual(manifest.used_tokens + manifest.reserved_output_tokens, manifest.token_budget)
        self.assertTrue(manifest.no_silent_truncation)
        self.assertTrue(any(block.compacted or block.exclusion_reason for block in (*manifest.selected, *manifest.excluded)))

    def test_d2_cloud_context_becomes_hash_reference(self) -> None:
        manifest = compile_context(
            goal_contract=self.goal,
            role_contract=_role(),
            node_contract=_node(),
            inputs={"private-evidence": {"privacy_class": "D2", "output": {"host": "internal"}}},
            privacy_class="D2",
            token_budget=8000,
            egress="cloud",
        )
        reference = next(block for block in manifest.selected if block.source == "private-evidence")
        self.assertIn("content_sha256", reference.payload)
        self.assertNotIn("internal", json.dumps(reference.payload))
        self.assertEqual(reference.inclusion_reason, "privacy-preserving hash reference")

    def test_d2_local_context_may_remain_available(self) -> None:
        manifest = compile_context(
            goal_contract=self.goal,
            role_contract=_role(),
            node_contract=_node(),
            inputs={"private-evidence": {"privacy_class": "D2", "output": {"finding": "internal-only"}}},
            privacy_class="D2",
            token_budget=8000,
            egress="local",
        )
        block = next(block for block in manifest.selected if block.source == "private-evidence")
        self.assertIn("internal-only", json.dumps(block.payload))


    def test_d3_cloud_context_contains_only_protected_reference(self) -> None:
        manifest = compile_context(
            goal_contract=self.goal,
            role_contract=_role(),
            node_contract=_node(),
            inputs={"restricted": {"privacy_class": "D3", "output": {"customer": "confidential"}}},
            privacy_class="D3",
            token_budget=8000,
            egress="cloud",
        )
        self.assertEqual(validate_context_manifest(manifest)["decision"], "pass")
        row = next(block for block in manifest.selected if block.source == "restricted")
        self.assertEqual(row.payload.get("payload_available_in_protected_store"), True)
        self.assertNotIn("confidential", json.dumps(row.payload))

    def test_secret_input_never_enters_cloud_prompt(self) -> None:
        secret = "xai-" + "A" * 24
        manifest = compile_context(
            goal_contract=self.goal,
            role_contract=_role(),
            node_contract=_node(),
            inputs={"secret-evidence": {"output": {"api_key": secret}}},
            privacy_class="D1",
            token_budget=8000,
            egress="cloud",
        )
        serialized = json.dumps(manifest.to_dict(include_payloads=True))
        self.assertNotIn(secret, serialized)
        self.assertTrue(any(block.exclusion_reason == "secret-pattern-detected" for block in (*manifest.selected, *manifest.excluded)))


    def test_d2_goal_contract_blocks_cloud_egress(self) -> None:
        goal = compile_goal_contract(
            "Analyze confidential customer architecture without exposing it.",
            privacy_class="D2",
        )
        manifest = compile_context(
            goal_contract=goal.to_dict(),
            role_contract=_role(),
            node_contract=_node(),
            inputs={},
            privacy_class="D2",
            token_budget=8000,
            egress="cloud",
        )
        self.assertEqual(manifest.decision, "block")
        serialized = json.dumps(manifest.to_dict(include_payloads=True))
        self.assertNotIn("confidential customer architecture", serialized)
        self.assertIn("D2-confidential-payload-replaced-by-hash-reference", serialized)


class PromptCompilerTests(unittest.TestCase):
    def _manifest(self):
        goal = compile_goal_contract("Produce a verified security recommendation.")
        manifest = compile_context(
            goal_contract=goal.to_dict(),
            role_contract=_role(),
            node_contract=_node(),
            inputs={"evidence": {"status": "pass", "output": {"finding": "bounded"}}},
            privacy_class="D1",
            token_budget=8000,
        )
        return goal, manifest

    def test_prompt_is_owned_versioned_and_reproducible(self) -> None:
        goal, manifest = self._manifest()
        first = compile_prompt(
            goal_contract=goal.to_dict(),
            role_contract=_role(),
            node_contract=_node(),
            context_manifest=manifest,
            policy={"evidence_first": True},
        )
        second = compile_prompt(
            goal_contract=goal.to_dict(),
            role_contract=_role(),
            node_contract=_node(),
            context_manifest=manifest,
            policy={"evidence_first": True},
        )
        self.assertEqual(first.sha256, second.sha256)
        parsed = json.loads(first.text)
        self.assertFalse(parsed["ownership"]["framework_defaults_used"])
        dependency = next(block for block in parsed["context"]["selected_blocks"] if block["kind"] == "dependency-result")
        self.assertEqual(dependency["trust"], "untrusted-data")
        self.assertIn("cannot override", parsed["response_contract"]["untrusted_context_policy"])
        self.assertEqual(validate_prompt(first)["decision"], "pass")

    def test_prompt_tampering_fails_validation(self) -> None:
        goal, manifest = self._manifest()
        artifact = compile_prompt(
            goal_contract=goal.to_dict(),
            role_contract=_role(),
            node_contract=_node(),
            context_manifest=manifest,
            policy={"evidence_first": True},
        ).to_dict(include_text=True)
        artifact["text"] += " "
        self.assertEqual(validate_prompt(artifact)["decision"], "block")


class ToolRouterTests(unittest.TestCase):
    def test_static_candidate_is_not_eligible_as_live(self) -> None:
        decision = build_tool_decision(
            [{"candidate_id": "claude:auto:r", "provider": "claude", "route_id": "r", "model": "auto", "live_ready": False, "cloud": True, "receipt": {}}],
            role_id="domain-architect",
            requested_effort="xhigh",
            privacy_class="D1",
        )
        self.assertEqual(decision["decision"], "block")
        self.assertIn("live-readiness-receipt-missing-or-stale", decision["evaluations"][0]["reasons"])

    def test_live_exact_ollama_candidate_is_eligible(self) -> None:
        decision = build_tool_decision(
            [{
                "candidate_id": "ollama:model:route",
                "provider": "ollama",
                "route_id": "route",
                "model": "model:cloud",
                "live_ready": True,
                "cloud": True,
                "receipt": {"authenticated": True, "model_identity_verified": True, "model_served": "model:cloud", "effort_supported": ["medium", "high"]},
            }],
            role_id="security-challenger",
            requested_effort="high",
            privacy_class="D1",
        )
        self.assertEqual(decision["decision"], "pass")
        self.assertEqual(decision["selected_provider"], "ollama")

    def test_named_adapter_cannot_be_qualified_by_other_provider(self) -> None:
        result = validate_provider_binding(
            selected_provider="grok",
            selected_model="grok-4.5",
            result={"provider": "ollama", "model_served": "qwen:cloud"},
        )
        self.assertEqual(result["decision"], "block")


class DecisionAndCheckpointTests(IsolatedHomeTestCase):
    def test_five_decision_receipt_is_complete_and_tamper_evident(self) -> None:
        receipt = build_turn_receipt(
            correlation_id="corr-1",
            graph_id="graph-1",
            node_id="node-1",
            role_id="quality-verifier",
            context_decision={"decision": "pass"},
            tool_decision={"decision": "pass"},
            validation_decision={"decision": "pass"},
            continuation_decision={"action": "continue"},
            persistence_decision={"decision": "pass"},
        )
        self.assertEqual(validate_turn_receipt(receipt)["decision"], "pass")
        receipt["tool_decision"] = {"decision": "block"}
        self.assertEqual(validate_turn_receipt(receipt)["decision"], "block")

    def test_checkpoint_is_hash_bound(self) -> None:
        graph = {"graph_id": "g", "nodes": []}
        save_checkpoint(
            self.home,
            "corr-checkpoint",
            graph=graph,
            results={"a": {"status": "pass"}},
            node_timings={"a": 1},
            model_calls=0,
            tokens_used=0,
            status="running",
        )
        loaded = load_checkpoint(self.home, "corr-checkpoint", graph)
        self.assertEqual(loaded["results"]["a"]["status"], "pass")
        with self.assertRaises(ValueError):
            load_checkpoint(self.home, "corr-checkpoint", {"graph_id": "changed", "nodes": []})

    def test_graph_pauses_and_resumes_without_repeating_completed_node(self) -> None:
        graph = ExecutionGraph(
            graph_id="graph-resume",
            correlation_id="corr-resume",
            goal="resume test",
            risk_class="R1",
            privacy_class="D0",
            max_parallel=1,
            token_budget=10000,
            wall_clock_seconds=60,
            max_model_calls=1,
            nodes=[
                GraphNode("a", "requirements-analyst", "first", "deterministic", output_schema=("value",)),
                GraphNode("final-audit", "independent-judge", "final", "deterministic", depends_on=("a",), output_schema=("decision",)),
            ],
        )
        calls: list[str] = []

        def executor(node, inputs, active_graph):
            calls.append(node.node_id)
            return {"status": "pass", "output": {"value": 1} if node.node_id == "a" else {"decision": "accept"}}

        paused = execute_graph(self.home, graph, executor, pause_after_nodes=1)
        self.assertEqual(paused["decision"], "paused")
        resumed = execute_graph(self.home, graph, executor, resume=True)
        self.assertEqual(resumed["decision"], "pass")
        self.assertEqual(calls.count("a"), 1)


class OwnedDelegateTests(IsolatedHomeTestCase):
    @patch("iot_ai.owned_delegate.eligible_routes")
    def test_advanced_turn_persists_owned_runtime_artifacts(self, routes) -> None:
        routes.return_value = [{
            "route_id": "ollama-cloud",
            "provider": "ollama",
            "model": "model-x:cloud",
            "kind": "cli",
            "cloud": True,
        }]

        def fake_delegate(user_home, provider, prompt, stage, model="auto", **kwargs):
            self.assertIn("IOT-AI-PROMPT-ENVELOPE", prompt)
            return {
                "status": "pass",
                "output": "Evidence-bound specialist result with explicit risk, alternatives and verification evidence.",
                "provider": provider,
                "route_id": "ollama-cloud",
                "request_id": "req-owned-turn",
                "model_requested": model,
                "model_served": "model-x:cloud",
                "input_tokens": 100,
                "output_tokens": 25,
                "latency_ms": 7,
                "failure_class": None,
            }

        result = owned_delegate(
            self.home,
            "ollama@model-x:cloud",
            "Review the design and return evidence-bound risks and verification.",
            "meeting-opinion",
            run_id="meeting-owned-runtime",
            role="independent-opinion",
            delegate_fn=fake_delegate,
        )
        runtime = result["agent_runtime"]
        self.assertTrue(all(runtime[key] for key in ("prompt_owned", "context_owned", "tools_owned", "control_flow_owned")))
        self.assertTrue(Path(runtime["decision_receipt"]).is_file())
        self.assertTrue((Path(runtime["artifact_root"]) / "context-manifest.json").is_file())
        self.assertEqual(result["model_served"], "model-x:cloud")


class RuntimeIntegrationTests(IsolatedHomeTestCase):
    @patch("iot_ai.agentic.select_candidates")
    def test_run_persists_owned_prompt_context_tools_and_control_flow(self, candidates) -> None:
        candidates.return_value = {
            role: {
                "candidate_id": f"ollama:demo:cloud:{role}",
                "provider": "ollama",
                "model": "demo:cloud",
                "route_id": "ollama-cloud",
                "live_ready": True,
                "cloud": True,
                "receipt": {"authenticated": True, "model_identity_verified": True, "model_served": "demo:cloud"},
                "fallback_candidates": [],
            }
            for role in ROLE_CATALOG
        }

        def executor(node, prompt, context):
            parsed_prompt = json.loads(prompt)
            self.assertIn("goal_contract", parsed_prompt)
            self.assertIn("context", parsed_prompt)
            output = {}
            for field in node.output_schema:
                if field in {"decision", "verdict"}:
                    output[field] = "PASS" if field == "verdict" else "accept"
                elif field == "plan_digest":
                    output[field] = "a" * 64
                elif field in {"use_cases", "test_cases", "failure_cases"}:
                    output[field] = [{"id": i, "decision": "pass"} for i in range(10)]
                elif field == "tests":
                    output[field] = [{"decision": "pass"}]
                elif field in {"kpis", "sla", "5w1h", "constraints", "acceptance"}:
                    output[field] = {"defined": True}
                elif field in {"evidence_refs", "findings", "risks", "disagreements", "missing_evidence", "dissent", "challenged_findings", "accepted_findings", "new_risks", "alternatives", "dependencies", "threats", "controls", "residual_risk", "benchmarks", "bottlenecks", "capacity", "recovery", "journeys", "ia", "widgets", "a11y", "explainability", "changed_files", "unknowns"}:
                    output[field] = []
                else:
                    output[field] = "defined"
            return {
                "status": "pass",
                "output": output,
                "parsed": output,
                "provider": "ollama",
                "model_requested": "demo:cloud",
                "model_served": "demo:cloud",
                "request_id": f"req-{node.node_id}",
                "input_tokens": 100,
                "output_tokens": 20,
                "latency_ms": 5,
            }

        result = run_goal(
            self.home,
            "Review security, architecture and performance; do not expose private data; done when evidence-bound tests pass.",
            provider_executor=executor,
            require_live=True,
        )
        self.assertTrue(all(result["agent_runtime"][key] for key in ("prompt_owned", "context_owned", "tools_owned", "control_flow_owned")))
        status = unified_status(self.home)
        self.assertEqual(status["agent_runtime"]["status"], "pass")
        self.assertEqual(status["agent_runtime"]["decision_receipt_completeness"], 1.0)
        self.assertGreater(status["agent_runtime"]["prompt_artifacts"], 0)


if __name__ == "__main__":
    unittest.main()
