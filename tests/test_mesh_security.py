# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import json
import subprocess
from unittest.mock import Mock, patch

from iot_ai.mesh import _prepare_cli_invocation, _validate_endpoint, delegate

from tests.common import IsolatedHomeTestCase


class MeshSecurityTests(IsolatedHomeTestCase):
    def _route(self, route_id: str = "route-1", model: str = "model-a") -> dict:
        return {
            "route_id": route_id,
            "provider": "test",
            "kind": "cli",
            "auth_mode": "subscription",
            "command": ["provider-cli", "--model", "{model}", "--prompt", "{prompt}"],
            "enabled": True,
            "priority": 10,
            "model": model,
            "cloud": True,
        }

    @patch("iot_ai.mesh.eligible_routes")
    @patch("iot_ai.mesh.subprocess.run")
    def test_cloud_secret_blocks_before_process_launch(self, run_mock, eligible_mock) -> None:
        eligible_mock.return_value = [self._route()]
        with self.assertRaisesRegex(RuntimeError, "privacy gate"):
            delegate(self.home, "test", "api_key=" + "A" * 30, model="model-a")
        run_mock.assert_not_called()

    @patch("iot_ai.mesh.save_receipt")
    @patch("iot_ai.mesh.record", return_value="contribution-1")
    @patch("iot_ai.mesh.eligible_routes")
    @patch("iot_ai.mesh.subprocess.run")
    def test_exact_model_drift_fails_closed(self, run_mock, eligible_mock, record_mock, receipt_mock) -> None:
        eligible_mock.return_value = [self._route(model="model-a")]
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"model": "model-b", "response": "substantive answer", "id": "req-1"}),
            stderr="",
        )
        result = delegate(self.home, "test", "Review this design", model="model-a")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failure_class"], "model-drift")
        self.assertFalse(result["live_ready"])
        receipt = receipt_mock.call_args.args[1]
        self.assertFalse(receipt["model_identity_verified"] is False and receipt["status"] == "pass")
        self.assertEqual(receipt["status"], "blocked")
        record_mock.assert_called_once()

    @patch("iot_ai.mesh.save_receipt")
    @patch("iot_ai.mesh.record", return_value="contribution-1")
    @patch("iot_ai.mesh.eligible_routes")
    @patch("iot_ai.mesh.subprocess.run")
    def test_no_silent_fallback_and_explicit_fallback_is_recorded(self, run_mock, eligible_mock, record_mock, receipt_mock) -> None:
        eligible_mock.return_value = [self._route("route-1"), self._route("route-2")]
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="usage limit")
        passed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({"model": "model-a", "response": "substantive answer", "id": "req-2"}), stderr=""
        )
        run_mock.side_effect = [failed]
        result = delegate(self.home, "test", "Review this design", model="model-a", allow_fallback=False)
        self.assertEqual(result["route_id"], "route-1")
        self.assertFalse(result["fallback_used"])
        self.assertEqual(run_mock.call_count, 1)

        run_mock.reset_mock(side_effect=True)
        run_mock.side_effect = [failed, passed]
        result = delegate(self.home, "test", "Review this design", model="model-a", allow_fallback=True)
        self.assertEqual(result["route_id"], "route-2")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(run_mock.call_count, 2)

    def test_prepare_cli_moves_only_prompt_slot_on_byte_overflow(self) -> None:
        huge = "x" * 140000
        argv, stdin, used = _prepare_cli_invocation(
            ["claude", "-p", "{prompt}"], huge, "model-a", "claude"
        )
        self.assertTrue(used)
        self.assertEqual(stdin, huge)
        self.assertEqual(argv, ["claude", "-p"])
        self.assertNotIn(huge, argv)

    def test_prepare_cli_keeps_deny_flag_and_rewrites_gemini_headless(self) -> None:
        huge = "y" * 140000
        argv, stdin, used = _prepare_cli_invocation(
            ["gemini", "-p", "{prompt}", "--deny", "shell"], huge, "model-a", "gemini"
        )
        self.assertTrue(used)
        self.assertEqual(stdin, huge)
        self.assertEqual(argv, ["gemini", "--deny", "shell", "-p", ""])
        self.assertNotIn(huge, argv)

    def test_prepare_cli_short_prompt_stays_in_argv(self) -> None:
        argv, stdin, used = _prepare_cli_invocation(
            ["codex", "exec", "{prompt}"], "short plan", "model-a", "codex"
        )
        self.assertFalse(used)
        self.assertIsNone(stdin)
        self.assertEqual(argv, ["codex", "exec", "short plan"])

    @patch("iot_ai.mesh.save_receipt")
    @patch("iot_ai.mesh.record", return_value="contribution-1")
    @patch("iot_ai.mesh.eligible_routes")
    @patch("iot_ai.mesh.subprocess.run")
    def test_e2big_without_stdin_retries_via_stdin(self, run_mock, eligible_mock, record_mock, receipt_mock) -> None:
        eligible_mock.return_value = [self._route()]
        passed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"model": "model-a", "response": "substantive answer", "id": "req-e2big"}',
            stderr="",
        )
        run_mock.side_effect = [OSError(7, "Argument list too long"), passed]
        result = delegate(self.home, "test", "Review this design", model="model-a")
        self.assertEqual(run_mock.call_count, 2)
        second_kwargs = run_mock.call_args_list[1].kwargs
        self.assertEqual(second_kwargs.get("input"), "Review this design")
        self.assertEqual(result["status"], "pass")

    @patch("iot_ai.mesh.save_receipt")
    @patch("iot_ai.mesh.record", return_value="contribution-ollama")
    @patch("iot_ai.mesh.eligible_routes")
    @patch("iot_ai.mesh.subprocess.run")
    def test_ollama_cli_exact_model_is_bound_as_served_model(self, run_mock, eligible_mock, record_mock, receipt_mock) -> None:
        route = self._route(model="demo:cloud")
        route["provider"] = "ollama"
        route["route_id"] = "ollama-cloud-subscription"
        route["command"] = ["ollama", "run", "{model}", "{prompt}"]
        eligible_mock.return_value = [route]
        run_mock.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Substantive Ollama Cloud review output.", stderr=""
        )
        result = delegate(self.home, "ollama", "Review this design", model="demo:cloud")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["model_requested"], "demo:cloud")
        self.assertEqual(result["model_served"], "demo:cloud")
        self.assertTrue(result["live_ready"])
        receipt = receipt_mock.call_args.args[1]
        self.assertTrue(receipt["model_identity_verified"])
        self.assertEqual(receipt["model_served"], "demo:cloud")

    def test_cloud_endpoint_rejects_credentials_query_redirect_surface_and_http(self) -> None:
        base = {"cloud": True, "allow_private_endpoint": False}
        with self.assertRaises(RuntimeError):
            _validate_endpoint({**base, "endpoint": "http://example.com"})
        with self.assertRaises(RuntimeError):
            _validate_endpoint({**base, "endpoint": "https://user:pass@example.com"})
        with self.assertRaises(RuntimeError):
            _validate_endpoint({**base, "endpoint": "https://example.com?token=x"})
        with self.assertRaises(RuntimeError):
            _validate_endpoint({**base, "endpoint": "https://localhost"})
        self.assertEqual(_validate_endpoint({**base, "endpoint": "https://example.com/"}), "https://example.com")


if __name__ == "__main__":
    import unittest
    unittest.main()
