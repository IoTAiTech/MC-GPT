# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from iot_ai.model_policy import clamp_effort, select_candidates
from iot_ai.providers import DEFAULT_ROUTES, add_route, eligible_routes, load, mutate_route, static_status
from iot_ai.readiness import live_receipt, provider_candidates, save_receipt

from tests.common import IsolatedHomeTestCase


class ProviderReadinessTests(IsolatedHomeTestCase):
    def test_default_routes_include_ollama_cloud(self) -> None:
        routes = load(self.home)["routes"]
        self.assertTrue(any(r["provider"] == "ollama" and r.get("cloud") for r in routes))

    @patch("iot_ai.providers.shutil.which", return_value="/usr/bin/provider")
    def test_static_presence_is_not_live_ready(self, which) -> None:
        status = static_status(DEFAULT_ROUTES[0])
        self.assertTrue(status["installed"])
        self.assertFalse(status["live_ready"])
        self.assertEqual(status["status_basis"], "static-only")

    @patch("iot_ai.providers.shutil.which", return_value="/usr/bin/provider")
    def test_eligible_route_filters_disabled(self, which) -> None:
        mutate_route(self.home, "claude-subscription", "disable", apply=True)
        providers = {r["provider"] for r in eligible_routes(self.home)}
        self.assertNotIn("claude", providers)

    def test_api_route_requires_secret_reference_presence(self) -> None:
        routes = load(self.home)
        api = next(r for r in routes["routes"] if r["route_id"] == "ollama-cloud-api")
        api["enabled"] = True
        from iot_ai.providers import save
        from iot_ai.settings import load as load_settings, save as save_settings
        save(self.home, routes)
        settings = load_settings(self.home)
        settings["cloud"]["enabled"] = True
        save_settings(self.home, settings)
        self.assertFalse(any(r["route_id"] == "ollama-cloud-api" for r in eligible_routes(self.home)))
        os.environ["OLLAMA_API_KEY"] = "test-value-not-persisted"
        try:
            self.assertTrue(any(r["route_id"] == "ollama-cloud-api" for r in eligible_routes(self.home)))
        finally:
            os.environ.pop("OLLAMA_API_KEY", None)

    def test_add_route_rejects_secret_value(self) -> None:
        with self.assertRaises(ValueError):
            add_route(self.home, {"route_id": "bad", "provider": "x", "kind": "api", "endpoint": "https://example.invalid", "protocol": "ollama", "secret_value": "bad"})

    def test_fresh_live_receipt_enables_candidate(self) -> None:
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        save_receipt(self.home, {
            "route_id": "ollama-cloud-subscription",
            "status": "pass",
            "authenticated": True,
            "model_requested": "demo:cloud",
            "model_served": "demo:cloud",
            "model_identity_verified": True,
            "request_or_job_id": "req-1",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": future,
        })
        with patch("iot_ai.providers.shutil.which", return_value="/usr/bin/provider"):
            candidates = provider_candidates(self.home, require_live=True)
        item = next(c for c in candidates if c["provider"] == "ollama")
        self.assertTrue(item["live_ready"])
        self.assertEqual(item["model"], "demo:cloud")

    def test_expired_receipt_is_not_live(self) -> None:
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        save_receipt(self.home, {"route_id": "claude-subscription", "status": "pass", "model_served": "x", "expires_at": past})
        self.assertIsNone(live_receipt(self.home, "claude-subscription", "x"))

    def test_effort_clamping(self) -> None:
        effective, reason = clamp_effort("xhigh", ["low", "medium", "high"])
        self.assertEqual(effective, "high")
        self.assertIsNotNone(reason)


if __name__ == "__main__":
    unittest.main()

class ProviderCapTests(IsolatedHomeTestCase):
    def test_candidate_selection_respects_provider_cap_and_preserves_ollama(self) -> None:
        from unittest.mock import patch
        from iot_ai.model_policy import select_candidates
        candidates = [
            {"candidate_id": "claude:auto", "provider": "claude", "model": "auto", "live_ready": True, "priority": 10, "cloud": True},
            {"candidate_id": "codex:auto", "provider": "codex", "model": "auto", "live_ready": True, "priority": 10, "cloud": True},
            {"candidate_id": "gemini:auto", "provider": "gemini", "model": "auto", "live_ready": True, "priority": 10, "cloud": True},
            {"candidate_id": "grok:auto", "provider": "grok", "model": "auto", "live_ready": True, "priority": 10, "cloud": True},
            {"candidate_id": "ollama:model:cloud", "provider": "ollama", "model": "model:cloud", "live_ready": True, "priority": 20, "cloud": True},
        ]
        with patch("iot_ai.model_policy.provider_candidates", return_value=candidates):
            result = select_candidates(
                self.home,
                ["requirements-analyst", "domain-architect", "security-challenger", "quality-verifier"],
                max_providers=3,
            )
        providers = {row["provider"] for row in result.values()}
        self.assertLessEqual(len(providers), 3)
        self.assertIn("ollama", providers)
