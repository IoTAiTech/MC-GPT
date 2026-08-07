# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
from __future__ import annotations

import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from iot_ai.diagnostics import collect, compare, explain, record_event, validate
from iot_ai.meeting import approve, create_task_from_meeting, run, show, start

from tests.common import IsolatedHomeTestCase


def substantive_delegate(user_home, seat, prompt, stage, **kwargs):
    text = (
        f"Seat {seat} provides an evidence-aware analysis with risks, alternatives, measurable KPI, "
        "implementation plan, security controls, test cases and explicit unresolved evidence."
    )
    if stage == "meeting-synthesis":
        text = (
            "Direct answer and architecture plan. WHY, WHAT, HOW, WHEN, WHO. "
            "KPI SLA use cases test cases failure cases risks disagreements and missing evidence."
        )
    elif stage == "meeting-final-review":
        marker = "PLAN_DIGEST:"
        digest = prompt.split(marker, 1)[1].splitlines()[0].strip()
        text = json.dumps({"decision": "accept", "plan_digest": digest, "findings": [], "dissent": []})
    return {
        "status": "pass",
        "output": text,
        "model_requested": f"{seat}-requested",
        "model_served": f"{seat}-served",
        "request_id": f"request-{seat}-{stage}",
        "route_id": f"route-{seat}",
        "input_tokens": 100,
        "cached_tokens": 10,
        "output_tokens": 50,
        "reasoning_tokens": 5,
        "latency_ms": 25,
        "fallback_used": False,
        "failure_class": None,
    }


class MeetingDiagnosticsTests(IsolatedHomeTestCase):
    @patch("iot_ai.meeting.delegate", side_effect=substantive_delegate)
    def test_deep_meeting_persists_kpi_and_cases(self, delegate_mock) -> None:
        created = start(self.home, "Design a secure dashboard", ["claude", "codex", "ollama"], quorum=2, depth="deep")
        result = run(self.home, created["meeting_id"])
        details = show(self.home, created["meeting_id"])["meeting"]
        self.assertIn(result["decision"], {"pass", "needs-work"})
        self.assertEqual(len(details["kpis"]), 7)
        self.assertEqual(len([c for c in details["cases"] if c["case_type"] == "use"]), 10)
        self.assertEqual(len([c for c in details["cases"] if c["case_type"] == "test"]), 10)
        self.assertEqual(len([c for c in details["cases"] if c["case_type"] == "failure"]), 10)
        self.assertEqual(result["content_provenance"]["transparency_profile"], "eu-ai-act-article-50-v1")
        self.assertTrue(result["article_50"]["disclosure"]["ai_interaction"])

    @patch("iot_ai.meeting.delegate")
    def test_empty_seats_do_not_satisfy_quorum(self, delegate_mock) -> None:
        delegate_mock.return_value = {"status": "failed", "output": "", "failure_class": "quota"}
        created = start(self.home, "Review a plan", ["claude", "codex"], quorum=2)
        result = run(self.home, created["meeting_id"])
        self.assertEqual(result["meeting_status"], "needs-review")
        self.assertEqual(result["plan_acceptance"], "none")
        self.assertEqual(show(self.home, created["meeting_id"])["status"], "needs-review")

    @patch("iot_ai.meeting.delegate", side_effect=substantive_delegate)
    def test_meeting_approval_is_separate_from_task_creation(self, delegate_mock) -> None:
        created = start(self.home, "Review release", ["codex", "ollama"], quorum=2)
        run(self.home, created["meeting_id"])
        approved = approve(self.home, created["meeting_id"])
        self.assertTrue(approved["founder_approval"])
        self.assertEqual(approved["plan_acceptance"], "accepted")
        task = create_task_from_meeting(self.home, created["meeting_id"], "Implement approved result", self.home / "workspace")
        self.assertTrue(task["task_id"].startswith("task-"))

    def test_diagnostics_bundle_redacts_sensitive_classes(self) -> None:
        correlation = "corr-test-001"
        record_event(self.home, correlation, {
            "status": "failed",
            "failure_class": "auth",
            "message": "Bearer " + "S" * 40 + " on 192.168." + "7.8 under /home/" + "example/private",
        })
        output = self.home / "diagnostics.zip"
        result = collect(self.home, correlation, output)
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(validate(output)["decision"], "pass")
        with zipfile.ZipFile(output) as archive:
            joined = b"\n".join(archive.read(name) for name in archive.namelist() if not name.endswith("/"))
        self.assertNotIn(b"S" * 40, joined)
        self.assertNotIn(b"192.168.", joined)
        self.assertNotIn(b"/home/example", joined)

    def test_diagnostics_compare(self) -> None:
        for suffix in ("a", "b"):
            record_event(self.home, f"corr-{suffix}", {"status": "pass", "event": "done"})
            collect(self.home, f"corr-{suffix}", self.home / f"{suffix}.zip")
        result = compare(self.home / "a.zip", self.home / "b.zip")
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(result["failure_delta"], 0)

    def test_corrupt_diagnostics_are_blocked(self) -> None:
        bad = self.home / "bad.zip"
        bad.write_bytes(b"not-a-zip")
        self.assertEqual(validate(bad)["decision"], "block")


if __name__ == "__main__":
    unittest.main()
