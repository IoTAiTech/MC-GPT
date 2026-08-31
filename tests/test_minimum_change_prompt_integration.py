# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-29
from __future__ import annotations

import hashlib
import json
import unittest

from iot_ai.context_compiler import compile_context
from iot_ai.goal_contract import compile_goal_contract
from iot_ai.minimum_change import validate_contract
from iot_ai.prompt_compiler import compile_prompt, validate_prompt
from iot_ai.roles import ROLE_CATALOG


def _node(stage: str, role_id: str) -> dict[str, object]:
    return {
        "node_id": stage,
        "stage": stage,
        "required_output_fields": list(ROLE_CATALOG[role_id].output_fields),
    }


def _artifacts(stage: str = "plan-synthesis", role_id: str = "plan-synthesizer"):
    goal = compile_goal_contract(
        "Provide a safe bounded CSV export. Done when output is correct and ownership boundaries remain unchanged."
    )
    role = ROLE_CATALOG[role_id].to_dict()
    node = _node(stage, role_id)
    manifest = compile_context(
        goal_contract=goal.to_dict(),
        role_contract=role,
        node_contract=node,
        inputs={"evidence": {"status": "pass", "output": {"finding": "bounded"}}},
        privacy_class="D1",
        token_budget=8000,
    )
    return goal, role, node, manifest


class MinimumChangePromptIntegrationTests(unittest.TestCase):
    def test_prompt_embeds_owned_digest_bound_contract(self) -> None:
        goal, role, node, manifest = _artifacts()
        first = compile_prompt(
            goal_contract=goal.to_dict(),
            role_contract=role,
            node_contract=node,
            context_manifest=manifest,
            policy={"evidence_first": True},
        )
        second = compile_prompt(
            goal_contract=goal.to_dict(),
            role_contract=role,
            node_contract=node,
            context_manifest=manifest,
            policy={"evidence_first": True},
        )
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(first.version, "2.1.0")
        parsed = json.loads(first.text)
        contract = parsed["minimum_necessary_change"]
        self.assertEqual(validate_contract(contract)["decision"], "pass")
        self.assertEqual(contract["context_manifest_sha256"], manifest.digest)
        self.assertEqual(contract["task"]["source_id"], goal.digest)
        self.assertTrue(parsed["response_contract"]["minimum_change_assessment"]["required"])
        self.assertEqual(validate_prompt(first)["decision"], "pass")

    def test_non_planning_role_receives_contract_without_forced_assessment(self) -> None:
        goal, role, node, manifest = _artifacts("analysis", "security-challenger")
        artifact = compile_prompt(
            goal_contract=goal.to_dict(),
            role_contract=role,
            node_contract=node,
            context_manifest=manifest,
            policy={"evidence_first": True},
        )
        parsed = json.loads(artifact.text)
        self.assertFalse(parsed["response_contract"]["minimum_change_assessment"]["required"])

    def test_nested_contract_tampering_is_detected_with_rebound_outer_hash(self) -> None:
        goal, role, node, manifest = _artifacts()
        artifact = compile_prompt(
            goal_contract=goal.to_dict(),
            role_contract=role,
            node_contract=node,
            context_manifest=manifest,
            policy={"evidence_first": True},
        ).to_dict(include_text=True)
        parsed = json.loads(artifact["text"])
        parsed["minimum_necessary_change"]["default_budgets"]["new_dependencies"] = 1
        artifact["text"] = json.dumps(
            parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        artifact["sha256"] = hashlib.sha256(artifact["text"].encode()).hexdigest()
        check = validate_prompt(artifact)
        self.assertEqual(check["decision"], "block")
        self.assertIn("minimum-change:default-budgets", check["errors"])
        self.assertIn("minimum-change:digest", check["errors"])


if __name__ == "__main__":
    unittest.main()
