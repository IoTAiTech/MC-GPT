# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-05
"""Non-vacuous red/green controls using the existing public runtime API."""
from unittest.mock import patch

from iot_ai.agentic import _finish_run, run_goal
from iot_ai.tasks import create, list_open, show
from tests.common import IsolatedHomeTestCase
from tests.test_agentic import fake_node_executor


class CompletionAuthorityRegressions(IsolatedHomeTestCase):
    def test_execute_without_host_test_runner_stops_before_provider_and_task(self):
        before = list_open(self.home)
        calls = []
        def provider(node, prompt, context):
            calls.append(node.node_id)
            return fake_node_executor(node, prompt, context)
        with patch("iot_ai.agentic.select_candidates", return_value={}):
            result = run_goal(self.home, "Export inventory with verified checks", execute=True,
                              provider_executor=provider)
        self.assertEqual(result.get("failure_class"), "host-test-runner-required")
        self.assertEqual(calls, [])
        self.assertEqual(list_open(self.home), before)

    def test_accepted_plan_does_not_complete_failed_execution(self):
        for decision in ("blocked", "failed", "needs-review", "pass"):
            task_id = create(self.home, title="Verify export " + decision, allow_duplicate=True)["task_id"]
            result = {"decision": decision, "results": {
                "final-plan-gate": {"output": {"decision": "accept"}},
                "final-audit": {"output": {"decision": "needs-review"}},
            }}
            _finish_run(self.home, task_id, "no-meeting-fixture", result, True)
            task = show(self.home, task_id)["task"]
            self.assertEqual(task["status"], "needs-work")
            self.assertLess(task["task_progress"], 100)
            self.assertNotEqual(result["decision"], "pass")
