# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
from __future__ import annotations

import json
import re
from unittest.mock import patch

from iot_ai.multicoder import run

from tests.common import IsolatedHomeTestCase


def _digest(prompt: str) -> str:
    match = re.search(r"PLAN_DIGEST:([0-9a-f]{64})", prompt)
    if not match:
        raise AssertionError("plan digest missing from review prompt")
    return match.group(1)


def successful_delegate(user_home, provider, prompt, stage="consultation", model="auto", **kwargs):
    del user_home, kwargs
    served = model if model not in {"auto", "auto:cloud"} else f"{provider}-served-model"
    if stage in {"plan-final-review", "final-review"}:
        output = json.dumps({"decision": "accept", "plan_digest": _digest(prompt), "findings": [], "dissent": []})
    elif stage == "plan-synthesis":
        output = (
            "Complete evidence-bound implementation plan with architecture, Article 5 and Article 50 controls, "
            "privacy boundaries, deterministic unit integration smoke security stress and rollback tests."
        )
    elif stage == "implementation":
        output = "Implemented only the frozen plan and preserved all public/private boundaries with rollback evidence."
    else:
        output = (
            f"{stage} independent analysis with scope, dependencies, security risks, privacy controls, "
            "test evidence, alternatives, rollback and unresolved assumptions."
        )
    return {
        "status": "pass",
        "output": output,
        "provider": provider,
        "route_id": f"route-{provider}",
        "request_id": f"req-{provider}-{stage}",
        "model_requested": served,
        "model_served": served,
        "input_tokens": 100,
        "cached_tokens": 10,
        "output_tokens": 40,
        "reasoning_tokens": 5,
        "latency_ms": 10,
        "fallback_used": False,
        "failure_class": None,
    }


class MultiCoderGovernanceTests(IsolatedHomeTestCase):
    @patch("iot_ai.multicoder.delegate", side_effect=successful_delegate)
    def test_happy_path_requires_digest_reviews_tests_and_marks_output(self, delegate_mock) -> None:
        result = run(
            self.home,
            task="Improve a developer tool without processing personal data",
            providers=["codex", "ollama@model-x:cloud"],
            quorum=2,
            test_argv=["python3", "-c", "print('1 passed')"],
            cwd=self.home,
        )
        self.assertEqual(result["decision"], "approve")
        self.assertTrue(result["execution_authorized"])
        self.assertTrue(result["plan_digest"])
        self.assertTrue(all(entry["review"]["accepted"] for entry in result["plan_reviews"]))
        self.assertTrue(all(entry["decision"] == "pass" for entry in result["tests"]))
        self.assertTrue(all(entry["review"]["accepted"] for entry in result["final_reviews"]))
        self.assertEqual(result["content_provenance"]["transparency_profile"], "eu-ai-act-article-50-v1")
        self.assertIn("ollama", result["content_provenance"]["model_providers"])
        self.assertTrue(result["article_50"]["disclosure"]["ai_interaction"])
        self.assertFalse(result["global_compliance_claim_allowed"])
        self.assertGreater(delegate_mock.call_count, 0)

    @patch("iot_ai.multicoder.delegate")
    def test_article_5_blocks_before_any_provider_call(self, delegate_mock) -> None:
        result = run(
            self.home,
            task="Build social scoring for citizens across unrelated contexts",
            providers=["codex", "ollama@model-x:cloud"],
            quorum=2,
            test_argv=["python3", "-c", "print('1 passed')"],
            cwd=self.home,
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["provider_calls"], 0)
        delegate_mock.assert_not_called()

    @patch("iot_ai.multicoder.delegate")
    def test_high_risk_candidate_blocks_before_any_provider_call(self, delegate_mock) -> None:
        result = run(
            self.home,
            task="Deploy an AI system to rank job applicants for employment selection",
            providers=["codex", "ollama@model-x:cloud"],
            quorum=2,
            test_argv=["python3", "-c", "print('1 passed')"],
            cwd=self.home,
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["reason"], "high-risk-deployment-classification-required")
        delegate_mock.assert_not_called()

    @patch("iot_ai.multicoder.delegate")
    def test_digest_rejection_prevents_implementation(self, delegate_mock) -> None:
        stages: list[str] = []

        def rejecting_delegate(user_home, provider, prompt, stage="consultation", model="auto", **kwargs):
            stages.append(stage)
            result = successful_delegate(user_home, provider, prompt, stage, model, **kwargs)
            if stage == "plan-final-review" and provider == "ollama":
                result["output"] = json.dumps({"decision": "needs-work", "plan_digest": _digest(prompt), "findings": ["gap"], "dissent": []})
            return result

        delegate_mock.side_effect = rejecting_delegate
        result = run(
            self.home,
            task="Improve a developer tool with deterministic tests",
            providers=["codex", "ollama@model-x:cloud"],
            quorum=2,
            test_argv=["python3", "-c", "print('1 passed')"],
            cwd=self.home,
        )
        self.assertEqual(result["decision"], "needs-work")
        self.assertFalse(result["execution_authorized"])
        self.assertNotIn("implementation", stages)


if __name__ == "__main__":
    import unittest
    unittest.main()
