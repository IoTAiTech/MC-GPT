# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-29
"""Public schema, role and runtime-presence contracts for the minimum-change gate."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from iot_ai.graph_runtime import GraphNode, _validate_output
from iot_ai.minimum_change import ASSESSMENT_SCHEMA, RUNG_DEFINITIONS
from iot_ai.roles import ROLE_CATALOG


ROOT = Path(__file__).resolve().parents[1]


class MinimumChangePublicContractTests(unittest.TestCase):
    def test_public_json_schema_matches_runtime_identity_and_rungs(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "minimum-change-assessment-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["properties"]["schema"]["const"], ASSESSMENT_SCHEMA)
        self.assertEqual(
            set(schema["properties"]["decision"]["enum"]),
            {"pass", "needs-work", "block"},
        )
        runtime_rungs = {str(item["id"]) for item in RUNG_DEFINITIONS}
        public_rungs = {
            value
            for value in schema["properties"]["selected_rung"]["enum"]
            if value is not None
        }
        normalized_rungs = set(
            schema["$defs"]["normalizedAssessment"]["properties"]["selected_rung"]["enum"]
        )
        self.assertEqual(public_rungs, runtime_rungs)
        self.assertEqual(normalized_rungs, runtime_rungs)
        self.assertFalse(schema["additionalProperties"])

    def test_planning_and_implementation_roles_require_the_assessment(self) -> None:
        for role_id in ("plan-synthesizer", "implementation-engineer"):
            with self.subTest(role=role_id):
                self.assertIn(
                    "minimum_change_assessment",
                    ROLE_CATALOG[role_id].output_fields,
                )

    def test_graph_runtime_rejects_missing_required_assessment_field(self) -> None:
        role = ROLE_CATALOG["plan-synthesizer"]
        node = GraphNode(
            node_id="plan-synthesis",
            role_id=role.role_id,
            stage="plan-synthesis",
            dependencies=(),
            required=True,
            read_scope=("normalized-evidence",),
            write_scope=("plan",),
            forbidden_actions=role.forbidden_actions,
            output_schema=role.output_fields,
            effort=role.default_effort,
        )
        payload = {
            "decision": "accept",
            "direct_answer": "Use the first sufficient evidence-bound solution rung.",
            "5w1h": {"defined": True},
            "minimum_change_assessment": {"selected_rung": "minimal-local-change"},
            "plan": [],
            "architecture": {"defined": True},
            "kpis": [],
            "sla": {"defined": True},
            "use_cases": [],
            "test_cases": [],
            "failure_cases": [],
            "risks": [],
            "disagreements": [],
            "missing_evidence": [],
        }
        payload.pop("minimum_change_assessment")
        with self.assertRaises(ValueError):
            _validate_output(node, payload)

    def test_public_docs_keep_upstream_claims_separate_from_mc_gpt_claims(self) -> None:
        research = (ROOT / "docs" / "research" / "ponytail-assessment.md").read_text(
            encoding="utf-8"
        )
        gate = (ROOT / "docs" / "minimum-necessary-change-gate.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("DietrichGebert/ponytail", research)
        self.assertIn("does not prove", research)
        self.assertIn("does not copy Ponytail source code", gate)
        self.assertIn("production_claim: false", gate)

    def test_skill_preserves_security_privacy_accessibility_and_recovery(self) -> None:
        skill = (
            ROOT / "skills" / "iot-ai-minimum-change" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for required in (
            "trust-boundary validation",
            "data-loss prevention",
            "security",
            "privacy",
            "accessibility",
            "rollback",
            "deterministic verification",
        ):
            self.assertIn(required, skill.casefold())


if __name__ == "__main__":
    unittest.main()
