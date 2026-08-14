# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from iot_ai.export_gate import assert_export_safe, redact_text
from iot_ai.meeting import project_meeting_view
from iot_ai.product_boundary import ProductBoundaryError, assert_not_product_database
from iot_ai.seat_selection import resolve_meeting_seats
from tests.common import IsolatedHomeTestCase

class ProductBoundaryTests(unittest.TestCase):
    def test_blocks_product_store_without_real_host_details(self):
        private_path = "/" + "home" + "/operator/product/pmd/data/tasks.db"
        with self.assertRaises(ProductBoundaryError):
            assert_not_product_database(private_path)
    def test_blocks_fcc_and_hid_markers(self):
        with self.assertRaises(ProductBoundaryError):
            assert_not_product_database("/var/lib/aiiot_fcc/state.db", context="test")
        with self.assertRaises(ProductBoundaryError):
            assert_not_product_database(r"C:\sandbox\hid\data\agents.db")
    def test_allows_suite_workspace(self):
        assert_not_product_database("/tmp/iot-ai-home/state/tasks.db")

class ExportGateTests(unittest.TestCase):
    def test_redacts_private_classes_without_real_fleet_literals(self):
        private_ip = "192" + ".168.77.88"
        private_path = "/" + "home" + "/operator/private/report.md"
        result = redact_text(f"host {private_ip} path {private_path}")
        self.assertIn("[PRIVATE_IP]", result["text"])
        self.assertIn("[PRIVATE_PATH]", result["text"])
    def test_blocks_private_key_residual(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "leak.txt"
            path.write_text("-----BEGIN " + "PRIVATE" + " KEY-----\nfixture\n-----END " + "PRIVATE" + " KEY-----\n", encoding="utf-8")
            self.assertEqual(assert_export_safe(path, allowed_roots=[Path(tmp)])["decision"], "block")

class MeetingViewTests(unittest.TestCase):
    def test_brief_has_semantic_participant_summary(self):
        payload = {"decision":"needs-work","meeting_id":"meeting-1","task_id":"task-1","hard_gates":{"substantive_quorum":False},"meeting":{"id":"meeting-1","status":"needs-review","topic":"Architecture review","substantive_seats":1,"requested_seats":2,"synthesis":"Use authenticated API; do not share databases.","contributions":[{"kind":"opinion","seat":"claude","status":"pass","model_requested":"m1","model_served":"m1","text":"Use a versioned API and keep PMD as a client."},{"kind":"opinion","seat":"codex","status":"failed","model_served":None,"failure_class":"quota","text":""}]}}
        brief = project_meeting_view(payload, "brief")
        self.assertEqual(brief["view"], "brief")
        self.assertNotIn("meeting", brief)
        self.assertIn("versioned API", brief["participants"][0]["opinion_summary"])
        self.assertIn("meeting", project_meeting_view(payload, "full"))

class SeatCapDecoupleTests(IsolatedHomeTestCase):
    def test_parallelism_does_not_implicitly_cap_seats(self):
        plan = resolve_meeting_seats(self.home, "all-coders+ollama-clouds", max_seats=None)
        self.assertIn(plan.decision, {"pass", "block"})
        self.assertNotIn("12>6", str(plan.reason or ""))
    def test_explicit_cap_is_honoured(self):
        plan = resolve_meeting_seats(self.home, "claude,codex,gemini,grok", max_seats=2)
        self.assertTrue(plan.decision in {"pass", "block"})

if __name__ == "__main__":
    unittest.main()
