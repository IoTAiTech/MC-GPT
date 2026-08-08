# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
from __future__ import annotations

import unittest

from iot_ai.knowledge_plane import coverage, list_artifacts, root, write_artifact, write_canvas
from iot_ai.quality import score_response

from tests.common import IsolatedHomeTestCase


class KnowledgeQualityTests(IsolatedHomeTestCase):
    def test_separate_knowledge_roots(self) -> None:
        public = root(self.home, "public")
        private = root(self.home, "private")
        customer = root(self.home, "customer", "tenant-a")
        self.assertNotEqual(public, private)
        self.assertNotEqual(private, customer)

    def test_invalid_tenant_identifier_rejected(self) -> None:
        with self.assertRaises(ValueError):
            root(self.home, "customer", "../bad")

    def test_write_and_list_artifact(self) -> None:
        result = write_artifact(
            self.home,
            kind="decision",
            title="Evidence-bound decision",
            content="A validated decision with architecture, tests, risks and provenance.",
            visibility="public",
            source_ids={"task_id": "task-1"},
            privacy_class="D0",
            tags=["architecture"],
        )
        self.assertTrue(result["artifact_id"].startswith("ka-"))
        artifacts = list_artifacts(self.home, "public")
        self.assertEqual(len(artifacts), 1)

    def test_coverage_detects_reuse(self) -> None:
        artifacts = [{"content": "secure dashboard architecture evidence rollback tests"}]
        value = coverage("secure dashboard architecture tests", artifacts)
        self.assertGreater(value["score"], 0.5)

    def test_canvas_projection(self) -> None:
        first = write_artifact(self.home, kind="meeting", title="A", content="content a", visibility="public", source_ids={}, privacy_class="D0", tags=[])
        second = write_artifact(self.home, kind="decision", title="B", content="content b", visibility="public", source_ids={}, privacy_class="D0", tags=[])
        result = write_canvas(self.home, [first["artifact_id"], second["artifact_id"]], [(first["artifact_id"], second["artifact_id"])])
        self.assertEqual(result["decision"], "pass")

    def test_quality_is_heuristic_not_correctness_claim(self) -> None:
        result = score_response("secure design", "Evidence-backed secure design with tests, rollback and measurable outcomes.", [])
        self.assertIn("score", result)
        self.assertIn("basis", result)
        self.assertIn("heuristic", result["basis"])


if __name__ == "__main__":
    unittest.main()
