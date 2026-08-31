# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.2 | Date: 2026-08-21
"""Local Claude/Codex/Grok CLI seats must bind and fail closed."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from iot_ai.cli import _result_exit_code
from iot_ai.exec_pin import pin_executable
from iot_ai.mesh import _extract_text, _extract_usage, _with_cli_identity_flags, delegate

from tests.common import IsolatedHomeTestCase


class LocalCliSeatTests(IsolatedHomeTestCase):
    def test_pin_prefers_user_local_grok_over_vibe_kit(self) -> None:
        user_bin = self.home / ".local" / "bin"
        user_bin.mkdir(parents=True)
        local = user_bin / "grok"
        local.write_text("#!/bin/sh\necho local-build\n", encoding="utf-8")
        local.chmod(0o755)
        system = self.home / "usr" / "local" / "bin"
        system.mkdir(parents=True)
        vibe = system / "grok"
        vibe.write_text("#!/bin/sh\necho vibe-kit\n", encoding="utf-8")
        vibe.chmod(0o755)
        pinned = pin_executable("grok", allowed_roots=[user_bin, system], user_home=self.home)
        self.assertEqual(Path(pinned["path"]), local.resolve())

    def test_grok_json_binds_text_and_model_usage_key(self) -> None:
        payload = {
            "text": "Independent plan with evidence, tests, and rollback.",
            "requestId": "req-grok-1",
            "modelUsage": {
                "grok-4.6-build": {
                    "inputTokens": 12,
                    "outputTokens": 9,
                }
            },
        }
        usage = _extract_usage(payload)
        self.assertEqual(_extract_text(payload), "Independent plan with evidence, tests, and rollback.")
        self.assertEqual(usage["model_served"], "grok-4.6-build")
        self.assertEqual(usage["request_id"], "req-grok-1")

    def test_claude_json_binds_canonical_model(self) -> None:
        payload = {
            "result": "Independent plan with evidence and rollback.",
            "session_id": "sess-1",
            "modelUsage": {
                "claude-opus-5[1m]": {
                    "canonicalModel": "claude-opus-5",
                    "outputTokens": 9,
                }
            },
        }
        usage = _extract_usage(payload)
        self.assertEqual(_extract_text(payload), "Independent plan with evidence and rollback.")
        self.assertEqual(usage["model_served"], "claude-opus-5")

    def test_codex_exec_gets_skip_git_flag(self) -> None:
        argv = _with_cli_identity_flags("codex", ["codex", "exec", "do the plan"])
        self.assertEqual(argv[1:4], ["exec", "--skip-git-repo-check", "-c"])
        self.assertIn("model_reasoning_effort=", argv[4])

    def test_codex_banner_model_is_served_model(self) -> None:
        from iot_ai.mesh import _extract_cli_banner_model
        banner = "OpenAI Codex v0.148.0\nmodel: gpt-5.6-sol\nprovider: openai\n"
        self.assertEqual(_extract_cli_banner_model(banner), "gpt-5.6-sol")

    def test_blocked_decision_is_nonzero_exit(self) -> None:
        self.assertEqual(_result_exit_code({"decision": "blocked", "execution_authorized": False}), 1)
        self.assertEqual(_result_exit_code({"decision": "pass"}), 0)

    @patch("iot_ai.mesh.save_receipt")
    @patch("iot_ai.mesh.record", return_value="contribution-1")
    @patch("iot_ai.mesh.eligible_routes")
    @patch("iot_ai.mesh.subprocess.run")
    def test_delegate_never_inherits_open_stdin(self, run_mock, eligible_mock, record_mock, receipt_mock) -> None:
        eligible_mock.return_value = [
            {
                "route_id": "codex-subscription",
                "provider": "codex",
                "kind": "cli",
                "auth_mode": "subscription",
                "command": [sys.executable, "exec", "{prompt}"],
                "enabled": True,
                "priority": 10,
                "model": "auto",
                "cloud": True,
            }
        ]
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"model": "gpt-5.6-sol", "response": "Substantive independent plan with tests."}),
            stderr="",
        )
        result = delegate(self.home, "codex", "Review this design", model="auto")
        kwargs = run_mock.call_args.kwargs
        self.assertEqual(kwargs.get("input"), "")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["model_served"], "gpt-5.6-sol")

    @patch("iot_ai.mesh.save_receipt")
    @patch("iot_ai.mesh.record", return_value="contribution-grok")
    @patch("iot_ai.mesh.eligible_routes")
    @patch("iot_ai.mesh.subprocess.run")
    def test_grok_api_key_error_is_auth_fail_even_on_exit_zero(self, run_mock, eligible_mock, record_mock, receipt_mock) -> None:
        eligible_mock.return_value = [
            {
                "route_id": "grok-subscription",
                "provider": "grok",
                "kind": "cli",
                "auth_mode": "subscription",
                "command": [sys.executable, "-p", "{prompt}"],
                "enabled": True,
                "priority": 10,
                "model": "auto",
                "cloud": True,
            }
        ]
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr='Error: API key required. Set GROK_API_KEY environment variable',
        )
        result = delegate(self.home, "grok", "Review this design", model="auto")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failure_class"], "auth")
        self.assertNotEqual(result.get("exit_code"), 0)

    @patch("iot_ai.mesh.save_receipt")
    @patch("iot_ai.mesh.record", return_value="contribution-claude")
    @patch("iot_ai.mesh.eligible_routes")
    @patch("iot_ai.mesh.subprocess.run")
    def test_claude_plan_mentioning_grok_api_key_is_not_auth_fail(self, run_mock, eligible_mock, record_mock, receipt_mock) -> None:
        eligible_mock.return_value = [
            {
                "route_id": "claude-subscription",
                "provider": "claude",
                "kind": "cli",
                "auth_mode": "subscription",
                "command": [sys.executable, "-p", "{prompt}"],
                "enabled": True,
                "priority": 10,
                "model": "auto",
                "cloud": True,
            }
        ]
        plan = (
            "Independent plan: vibe-kit grok failed with GROK_API_KEY missing. "
            "Pin user-local Grok Build instead. Tests and rollback included."
        )
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({
                "result": plan,
                "modelUsage": {"claude-opus-5[1m]": {"canonicalModel": "claude-opus-5"}},
            }),
            stderr="",
        )
        result = delegate(self.home, "claude", "Review this design", model="auto")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["model_served"], "claude-opus-5")
        self.assertIsNone(result.get("failure_class"))
