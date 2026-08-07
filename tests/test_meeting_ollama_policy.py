# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
from __future__ import annotations

import unittest
from unittest.mock import patch

from iot_ai.cli import normalize_meeting_argv
from iot_ai.meeting import show, start
from iot_ai.seat_selection import resolve_meeting_seats

from tests.common import IsolatedHomeTestCase


CODERS = (
    ["claude", "codex", "gemini", "grok"],
    [
        {"seat": "claude", "provider": "claude", "installed": True, "live_ready": True},
        {"seat": "codex", "provider": "codex", "installed": True, "live_ready": True},
        {"seat": "gemini", "provider": "gemini", "installed": True, "live_ready": True},
        {"seat": "grok", "provider": "grok", "installed": True, "live_ready": True},
    ],
)
OLLAMA = (
    ["ollama@model-a:cloud", "ollama@model-b:cloud"],
    [
        {"seat": "ollama@model-a:cloud", "provider": "ollama", "model": "model-a:cloud", "installed": True, "live_ready": True, "cloud": True},
        {"seat": "ollama@model-b:cloud", "provider": "ollama", "model": "model-b:cloud", "installed": True, "live_ready": True, "cloud": True},
    ],
)


class MeetingOllamaPolicyTests(IsolatedHomeTestCase):
    def setUp(self) -> None:
        super().setUp()
        from iot_ai.settings import load, save

        value = load(self.home)
        value["cloud"]["enabled"] = True
        value["meeting"]["require_ollama_cloud_when_available"] = True
        save(self.home, value)

    @patch("iot_ai.seat_selection._ollama_cloud_seats", return_value=OLLAMA)
    @patch("iot_ai.seat_selection._coder_seats", return_value=CODERS)
    def test_all_coders_and_all_ollama_cloud_models_are_resolved(self, coder_mock, ollama_mock) -> None:
        plan = resolve_meeting_seats(self.home, "all-coders+ollama-clouds", max_seats=8)
        self.assertEqual(plan.decision, "pass")
        self.assertEqual(
            list(plan.resolved_seats),
            ["claude", "codex", "gemini", "grok", "ollama@model-a:cloud", "ollama@model-b:cloud"],
        )
        self.assertTrue(plan.ollama_cloud_included)

    @patch("iot_ai.seat_selection._ollama_cloud_seats", return_value=OLLAMA)
    @patch("iot_ai.seat_selection._coder_seats", return_value=CODERS)
    def test_four_coder_literal_cannot_silently_omit_ollama(self, coder_mock, ollama_mock) -> None:
        plan = resolve_meeting_seats(self.home, "claude,codex,gemini,grok", max_seats=8)
        self.assertEqual(plan.decision, "block")
        self.assertEqual(plan.reason, "OLLAMA_CLOUD_FIRST_CLASS_SEAT_OMITTED")
        self.assertFalse(plan.ollama_cloud_included)

    @patch("iot_ai.seat_selection._ollama_cloud_seats", return_value=OLLAMA)
    @patch("iot_ai.seat_selection._coder_seats", return_value=CODERS)
    def test_intentional_ollama_exclusion_is_explicit(self, coder_mock, ollama_mock) -> None:
        plan = resolve_meeting_seats(
            self.home,
            "claude,codex,gemini,grok",
            exclude_ollama=True,
            max_seats=8,
        )
        self.assertEqual(plan.decision, "pass")
        self.assertEqual(list(plan.resolved_seats), ["claude", "codex", "gemini", "grok"])

    @patch("iot_ai.seat_selection._ollama_cloud_seats", return_value=OLLAMA)
    @patch("iot_ai.seat_selection._coder_seats", return_value=CODERS)
    def test_auto_reserves_an_ollama_cloud_seat_under_community_cap(self, coder_mock, ollama_mock) -> None:
        plan = resolve_meeting_seats(self.home, "auto", max_seats=3)
        self.assertEqual(plan.decision, "pass")
        self.assertEqual(len(plan.resolved_seats), 3)
        self.assertTrue(any(seat.startswith("ollama@") for seat in plan.resolved_seats))

    def test_natural_language_alias_maps_to_all_coders_and_ollama_clouds(self) -> None:
        command = normalize_meeting_argv(
            [
                "--max-parallel",
                "ask",
                "all",
                "coder",
                "and",
                "ollama",
                "clouds",
                "only",
                "review",
                "the",
                "dashboard",
            ]
        )
        self.assertEqual(command[:2], ["meeting", "start"])
        self.assertIn("all-coders+ollama-clouds", command)
        topic = command[command.index("--topic") + 1]
        self.assertEqual(topic, "review the dashboard")

    def test_meeting_show_reports_ollama_coverage(self) -> None:
        seat_plan = {
            "schema": "iot-ai.meeting-seat-plan.v1",
            "selector": "all-coders+ollama-clouds",
            "requested_seats": ["codex", "ollama@model-a:cloud"],
            "resolved_seats": ["codex", "ollama@model-a:cloud"],
            "ollama_cloud_included": True,
            "decision": "pass",
        }
        created = start(
            self.home,
            "Review this plan",
            ["codex", "ollama@model-a:cloud"],
            quorum=2,
            seat_plan=seat_plan,
            max_parallel=2,
        )
        result = show(self.home, created["meeting_id"])
        self.assertEqual(result["seat_plan"]["selector"], "all-coders+ollama-clouds")
        self.assertEqual(result["seat_coverage"]["ollama_requested"], ["ollama@model-a:cloud"])
        self.assertFalse(result["seat_coverage"]["ollama_omitted"])


if __name__ == "__main__":
    unittest.main()
