# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
from __future__ import annotations

import unittest
from unittest.mock import patch

from iot_ai.agentic import run_goal
from iot_ai.roles import ROLE_CATALOG

from tests.common import IsolatedHomeTestCase


def fake_node_executor(node, prompt, context):
    fields = node.output_schema
    output = {}
    for field in fields:
        if field in {"decision", "verdict"}:
            output[field] = "PASS" if field == "verdict" else "accept"
        elif field == "plan_digest":
            output[field] = "a" * 64
        elif field in {"direct_answer", "architecture", "plan", "migration", "rollback", "summary", "implementation_summary"}:
            output[field] = "Evidence-bound result with measurable acceptance and rollback."
        elif field in {"use_cases", "test_cases", "failure_cases"}:
            output[field] = [{"id": i, "decision": "pass", "expected": "pass"} for i in range(10)]
        elif field == "tests":
            output[field] = [{"name": "unit", "decision": "pass"}]
        elif field in {"kpis", "sla", "5w1h", "acceptance", "constraints"}:
            output[field] = {"defined": True}
        elif field in {"changed_files", "evidence_refs", "findings", "risks", "unknowns", "disagreements", "missing_evidence", "alternatives", "dependencies", "threats", "controls", "residual_risk", "benchmarks", "bottlenecks", "capacity", "recovery", "journeys", "ia", "widgets", "a11y", "explainability", "dissent", "challenged_findings", "accepted_findings", "new_risks"}:
            output[field] = []
        else:
            output[field] = "defined"
    return {
        "status": "pass",
        "output": output,
        "parsed": output,
        "provider": "ollama" if "security" in node.role_id else "codex",
        "model_requested": "demo:cloud",
        "model_served": "demo:cloud",
        "request_id": f"req-{node.node_id}",
        "input_tokens": 100,
        "cached_tokens": 10,
        "output_tokens": 50,
        "reasoning_tokens": 5,
        "latency_ms": 10,
    }


class AgenticTests(IsolatedHomeTestCase):
    @patch("iot_ai.agentic.select_candidates")
    def test_goal_compiles_and_executes_with_receipts(self, candidates) -> None:
        candidates.return_value = {
            role: {
                "candidate_id": f"codex:model:{role}",
                "provider": "codex",
                "model": "model",
                "route_id": "route",
                "live_ready": True,
                "cloud": True,
                "fallback_candidates": [],
            }
            for role in ROLE_CATALOG
        }
        result = run_goal(
            self.home,
            "Review security and architecture",
            execute=False,
            profile="balanced",
            provider_executor=fake_node_executor,
        )
        self.assertIn(result["decision"], {"pass", "needs-review"})
        self.assertIn("graph", result)
        self.assertIn("metrics", result)
        self.assertGreater(result["metrics"]["passed_nodes"], 0)
        self.assertEqual(result["content_provenance"]["transparency_profile"], "eu-ai-act-article-50-v1")
        self.assertTrue(result["article_50"]["disclosure"]["ai_interaction"])
        self.assertFalse(result["global_compliance_claim_allowed"])


if __name__ == "__main__":
    unittest.main()
