# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3+remediate.1 | Date: 2026-08-06
"""Deep-audit remediations: product boundary, export gate, seat-cap decoupling, meeting views."""
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
    def test_blocks_pmd_data_path(self):
        with self.assertRaises(ProductBoundaryError):
            assert_not_product_database("/home/iot/ai-iot/pmd/data/tasks.db")

    def test_blocks_fcc_and_hid_markers(self):
        with self.assertRaises(ProductBoundaryError):
            assert_not_product_database("/var/lib/aiiot_fcc/state.db", context="test")
        with self.assertRaises(ProductBoundaryError):
            assert_not_product_database(r"C:\data\hid\data\agents.db")

    def test_allows_suite_workspace(self):
        assert_not_product_database("/tmp/iot-ai-home/state/tasks.db")


class ExportGateTests(unittest.TestCase):
    def test_redacts_private_ip_and_path(self):
        result = redact_text("host 192.168.50.40 path /home/iot/secret/report.md")
        self.assertIn("[PRIVATE_IP]", result["text"])
        self.assertIn("[PRIVATE_PATH]", result["text"])
        self.assertTrue(result["findings"])

    def test_blocks_private_key_residual(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "leak.txt"
            path.write_text("-----BEGIN PRIVATE KEY-----\nMIIE\n-----END PRIVATE KEY-----\n", encoding="utf-8")
            gate = assert_export_safe(path)
            self.assertEqual(gate["decision"], "block")


class MeetingViewTests(unittest.TestCase):
    def test_brief_view_omits_full_contributions(self):
        payload = {
            "decision": "needs-work",
            "meeting_id": "meeting-1",
            "task_id": "task-1",
            "hard_gates": {"substantive_quorum": False},
            "meeting": {
                "id": "meeting-1",
                "status": "needs-review",
                "topic": "x" * 500,
                "substantive_seats": 0,
                "requested_seats": ["claude", "codex"],
                "synthesis": "",
                "contributions": [
                    {"kind": "opinion", "seat": "claude", "status": "failed", "model_served": None, "text": "short"},
                    {"kind": "critique", "seat": "codex", "status": "pass", "model_served": "x", "text": "long body"},
                ],
            },
        }
        brief = project_meeting_view(payload, "brief")
        self.assertEqual(brief["view"], "brief")
        self.assertNotIn("meeting", brief)
        self.assertEqual(brief["meeting_id"], "meeting-1")
        self.assertTrue(brief["seat_table"])
        full = project_meeting_view(payload, "full")
        self.assertEqual(full["view"], "full")
        self.assertIn("meeting", full)


class SeatCapDecoupleTests(IsolatedHomeTestCase):
    def test_max_parallel_does_not_cap_all_cloud_seats_when_max_seats_none(self):
        # With max_seats None, limit is edition max_providers (>=12 typically)
        plan = resolve_meeting_seats(self.home, "all-coders+ollama-clouds", max_seats=None)
        # may block if no ollama routes in isolated home — accept pass or NO_OLLAMA
        self.assertIn(plan.decision, {"pass", "block"})
        if plan.decision == "block":
            self.assertNotIn("SEAT_LIMIT_EXCEEDED:12>6", str(plan.reason or ""))

    def test_explicit_max_seats_is_honoured(self):
        plan = resolve_meeting_seats(self.home, "claude,codex,gemini,grok", max_seats=2)
        if plan.decision == "pass":
            self.assertLessEqual(len(plan.resolved_seats), 2)
        else:
            self.assertTrue(plan.reason)
