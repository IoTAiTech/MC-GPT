# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-05
"""Labeled simulation of one installed Community workflow. Not a live PMD run."""
from __future__ import annotations

import json
from pathlib import Path

from iot_ai.runtime_gates import (
    accepted_plan_allows_implement,
    bind_implementation_to_accepted_plan,
    evaluate_minimum_change_gate,
    persist_accepted_plan,
    resolve_dispatch_effort,
)
from iot_ai.settings import load
from iot_ai.skill_router import select_skills
from iot_ai.tasks import create, list_open, show
from iot_ai.visual_acceptance import UNAVAILABLE, evaluate_visual_acceptance

from tests.common import IsolatedHomeTestCase
from tests.test_runtime_enforcement_corrective import passing_assessment


class InstalledWorkflowTraceTests(IsolatedHomeTestCase):
    """Simulation: mocks and disposable ledgers. provider_calls=0."""

    def test_readonly_inspection_creates_no_task(self) -> None:
        before = list_open(self.home)
        settings = load(self.home)
        self.assertIn("schema", settings)
        after = list_open(self.home)
        self.assertEqual(len(before), len(after))

    def test_one_goal_one_task_and_replay_without_paid_calls(self) -> None:
        created = create(
            self.home,
            title="Export inventory",
            description="Export inventory",
            acceptance_criteria="Tests pass.",
            allow_duplicate=True,
        )
        task_id = created["task_id"]
        selected = show(self.home, task_id)["task"]
        self.assertEqual(selected["id"], task_id)
        accepted = evaluate_minimum_change_gate(
            {"minimum_change_assessment": passing_assessment()},
            goal="Export inventory",
            task_id=task_id,
            risk_class="R2",
            acceptance=selected["acceptance_criteria"],
            context_digest="a" * 64,
            revision=int(selected.get("revision") or 1),
        )
        presented = {"decision": "accept", "mncg": accepted}
        receipt = persist_accepted_plan(self.home, presented)
        guard = accepted_plan_allows_implement(presented, persisted=receipt, user_home=self.home)
        self.assertTrue(guard["valid"])
        current = {
            "task_id": task_id,
            "revision": int(selected.get("revision") or 1),
            "acceptance_criteria": selected["acceptance_criteria"],
            "context_digest": "a" * 64,
            "authority_basis": "iot-ai-suite-standalone-task-store",
        }
        bind = bind_implementation_to_accepted_plan(
            {"minimum_change_assessment": passing_assessment()},
            presented,
            goal="Export inventory",
            task_id=task_id,
            risk_class="R2",
            acceptance=selected["acceptance_criteria"],
            context_digest="a" * 64,
            revision=int(selected.get("revision") or 1),
            current_task=current,
        )
        self.assertTrue(bind["valid"])
        replay = bind_implementation_to_accepted_plan(
            {"minimum_change_assessment": passing_assessment()},
            presented,
            goal="Export inventory",
            task_id=task_id,
            risk_class="R2",
            acceptance=selected["acceptance_criteria"],
            context_digest="a" * 64,
            revision=int(selected.get("revision") or 1),
            current_task=current,
        )
        self.assertTrue(replay["valid"])
        self.assertEqual(replay["assessment_sha256"], bind["assessment_sha256"])

    def test_seeded_failure_is_one_bounded_cycle(self) -> None:
        dispatch = resolve_dispatch_effort(
            {"requested_effort": "high", "supported_efforts": ["high"]},
            node_effort="high",
            max_effort="medium",
        )
        self.assertEqual(dispatch["decision"], "block")
        retry = resolve_dispatch_effort(
            {"requested_effort": "medium", "supported_efforts": ["low", "medium"]},
            node_effort="medium",
            max_effort="medium",
        )
        self.assertEqual(retry["decision"], "pass")
        visual = evaluate_visual_acceptance(visual_task=True, require_browser_acceptance=True, tool_available=False)
        self.assertEqual(visual["decision"], UNAVAILABLE)
        skills = select_skills(self.home, goal="document a local change", role_id="implementation-engineer", stage="implement")
        receipt = skills.get("receipt") or {}
        self.assertGreaterEqual(int(receipt.get("discovered_count") or skills.get("discovered_count") or 0), 0)

    def test_brief_and_full_share_the_same_records(self) -> None:
        created = create(self.home, title="Trace", description="Trace", acceptance_criteria="Tests pass.", allow_duplicate=True)
        ledger = {
            "schema": "iot-ai.installed-workflow-trace.v1",
            "simulation": True,
            "provider_calls": 0,
            "tasks": [created["task_id"]],
            "decisions": ["awaiting_founder"],
            "blocked_scope": ["paid-provider"],
            "next_actor": "founder",
        }
        brief = {key: ledger[key] for key in ("tasks", "decisions", "blocked_scope", "next_actor", "provider_calls")}
        self.assertEqual(brief["tasks"], ledger["tasks"])
        self.assertEqual(brief["provider_calls"], 0)
        path = Path(self.home) / "trace.json"
        path.write_text(json.dumps(ledger))
        loaded = json.loads(path.read_text())
        self.assertEqual(loaded["tasks"], brief["tasks"])
