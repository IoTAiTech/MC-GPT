# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-05
"""Reconciled workflow contracts, also reusable for installed-package validation.

A checkout test is not an installation result. All providers here are synthetic;
this file proves actual runtime/ledger/report flow, not live PMD execution.
"""
from __future__ import annotations

import json
from unittest.mock import patch

from iot_ai.agentic import run_goal
from iot_ai.meeting_reporting import collect
from iot_ai.roles import ROLE_CATALOG
from iot_ai.runtime_gates import bind_implementation_to_accepted_plan, evaluate_minimum_change_gate, resolve_dispatch_effort
from iot_ai.settings import load
from iot_ai.tasks import create, list_open, show
from iot_ai.visual_acceptance import UNAVAILABLE, evaluate_visual_acceptance
from iot_ai.workspace import connect_read, one
from tests.common import IsolatedHomeTestCase
from tests.test_agentic import fake_node_executor
from tests.test_runtime_enforcement_corrective import passing_assessment


class InstalledWorkflowTraceTests(IsolatedHomeTestCase):
    def run_fixture(self):
        goal = "Export inventory with deterministic verification"
        created = create(self.home, title=goal, description=goal,
                         acceptance_criteria="All export checks pass.", allow_duplicate=True)
        calls = []
        def provider(node, prompt, context):
            calls.append(node.node_id)
            result = fake_node_executor(node, prompt, context)
            output = result["parsed"]
            if "kpis" in output:
                output["kpis"] = [{"name": "acceptance", "target": "pass"}]
            frozen = json.loads(prompt).get("node_contract", {}).get("frozen_plan_digest")
            if "plan_digest" in output and frozen:
                output["plan_digest"] = frozen
            return result
        candidates = {role: {"candidate_id": f"codex:fixture:{role}", "provider": "codex",
            "model": "fixture", "live_ready": True, "cloud": True,
            "fallback_candidates": []} for role in ROLE_CATALOG}
        with patch("iot_ai.agentic.select_candidates", return_value=candidates):
            result = run_goal(self.home, goal, execute=True, profile="balanced",
                              existing_task_id=created["task_id"], provider_executor=provider)
        return created["task_id"], result, calls

    def test_readonly_inspection_creates_no_task(self):
        before = list_open(self.home)
        self.assertIn("schema", load(self.home))
        self.assertEqual(len(list_open(self.home)), len(before))

    def test_one_goal_one_task_and_existing_ledger_proof(self):
        task_id, result, calls = self.run_fixture()
        self.assertEqual(result["decision"], "pass")
        self.assertIn("implement", calls)
        self.assertEqual(show(self.home, task_id)["task"]["status"], "awaiting_founder")
        connection = connect_read(self.home)
        try:
            self.assertEqual(one(connection, "SELECT count(*) AS n FROM tasks")["n"], 1)
            proof = one(connection, "SELECT status,output_sha256 FROM graph_nodes WHERE graph_id=? AND id=?",
                        (result["graph"]["graph_id"], "final-plan-gate"))
        finally:
            connection.close()
        self.assertEqual(proof["status"], "pass")
        self.assertEqual(len(proof["output_sha256"]), 64)
        self.assertFalse(list(self.home.rglob("accepted-plans")))

    def test_pure_binding_replay_does_not_dispatch_or_create_tasks(self):
        args = dict(goal="Export inventory", task_id="task-fixture", risk_class="R2",
                    acceptance="All tests pass.", context_digest="a" * 64, revision=3)
        payload = {"minimum_change_assessment": passing_assessment()}
        plan = {"decision": "accept", "mncg": evaluate_minimum_change_gate(payload, **args)}
        before = len(list_open(self.home))
        first = bind_implementation_to_accepted_plan(payload, plan, **args)
        second = bind_implementation_to_accepted_plan(payload, plan, **args)
        self.assertTrue(first["valid"])
        self.assertEqual(first, second)
        self.assertEqual(len(list_open(self.home)), before)
        missing_context = bind_implementation_to_accepted_plan(payload, plan, **(args | {"context_digest": None}))
        self.assertFalse(missing_context["valid"])

    def test_seeded_effort_failure_needs_changed_evidence_to_recover(self):
        row = {"requested_effort": "high", "supported_efforts": ["high"]}
        first = resolve_dispatch_effort(row, node_effort="high", max_effort="medium")
        repeat = resolve_dispatch_effort(row, node_effort="high", max_effort="medium")
        self.assertEqual(first, repeat)
        self.assertEqual(first["decision"], "block")
        corrected = resolve_dispatch_effort({"requested_effort": "medium", "supported_efforts": ["low", "medium"]},
                                            node_effort="medium", max_effort="medium")
        self.assertEqual(corrected["decision"], "pass")
        self.assertEqual(evaluate_visual_acceptance(visual_task=True,
            require_browser_acceptance=True, tool_available=False)["decision"], UNAVAILABLE)

    def test_brief_and_full_are_derived_from_the_actual_meeting_store(self):
        task_id, result, _ = self.run_fixture()
        brief = collect(self.home, view="brief", classification="restricted")
        full = collect(self.home, view="full", classification="restricted")
        self.assertEqual(brief["meeting_count"], 1)
        self.assertEqual(full["meeting_count"], 1)
        def identity(record):
            row = record.get("meeting") or record
            return row.get("id") or row.get("meeting_id"), row.get("task_id")
        self.assertEqual(identity(brief["meetings"][0]), identity(full["meetings"][0]))
        self.assertEqual(identity(full["meetings"][0])[1], task_id)
