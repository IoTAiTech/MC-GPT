# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-03
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from iot_ai.model_policy import select_candidates
from iot_ai.providers import add_route, eligible_routes
from iot_ai.settings import (
    apply_preset,
    effective_settings,
    load,
    migrate_v1_to_v2,
    rollback_settings,
    save,
    set_value,
    validate_settings,
)
from iot_ai.settings_v2 import PRESETS, SCHEMA_V1, SCHEMA_V2, resolve_effort

from tests.common import IsolatedHomeTestCase


class SettingsV2Tests(IsolatedHomeTestCase):
    def test_v1_loads_without_persist(self) -> None:
        value = load(self.home)
        self.assertEqual(value.get("schema"), SCHEMA_V1)
        self.assertIn("routing", value)
        self.assertFalse(Path(self.home).joinpath(".config").exists() or False)
        path = __import__("iot_ai.paths", fromlist=["settings_path"]).settings_path(self.home)
        self.assertFalse(path.exists())

    def test_invalid_governed_value_rejected(self) -> None:
        value = load(self.home)
        with self.assertRaises(ValueError):
            set_value(value, "routing.ollama.local_policy", "sometimes")
            save(self.home, value)

    def test_unknown_extension_preserved(self) -> None:
        value = load(self.home)
        value["custom_extension"] = {"note": "keep"}
        save(self.home, value)
        loaded = load(self.home)
        self.assertEqual(loaded["custom_extension"]["note"], "keep")

    def test_secret_rejected(self) -> None:
        value = load(self.home)
        with self.assertRaises(ValueError):
            set_value(value, "providers.claude.api_key", "sk-demo")

    def test_migrate_and_rollback(self) -> None:
        plan = migrate_v1_to_v2(self.home, apply=False)
        self.assertEqual(plan["decision"], "plan")
        applied = migrate_v1_to_v2(self.home, apply=True)
        self.assertEqual(applied["decision"], "pass")
        self.assertEqual(load(self.home)["schema"], SCHEMA_V2)
        self.assertRegex(applied["source_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(applied["destination_sha256"], r"^[0-9a-f]{64}$")
        rolled = rollback_settings(self.home, applied["rollback_id"], apply=True)
        self.assertEqual(rolled["decision"], "pass")
        self.assertEqual(load(self.home).get("schema"), SCHEMA_V1)

    def test_effective_digest_and_fields(self) -> None:
        value = load(self.home)
        effective = effective_settings(self.home, value)
        self.assertRegex(effective["effective_settings_digest"], r"^[0-9a-f]{64}$")
        field = effective["fields"]["routing.effort.default"]
        self.assertIn("configured_value", field)
        self.assertIn("effective_value", field)
        self.assertIn("source_layer", field)
        self.assertEqual(field["entitlement_limit"], "medium")

    def test_cli_session_overrides_user(self) -> None:
        value = load(self.home)
        value["routing"]["max_distinct_models"] = 8
        save(self.home, value)
        layered = load(self.home, session_override={"routing": {"max_distinct_models": 2}})
        self.assertEqual(layered["routing"]["max_distinct_models"], 2)

    def test_project_overrides_user(self) -> None:
        value = load(self.home)
        value["routing"]["max_distinct_models"] = 9
        save(self.home, value)
        project = self.home / "proj"
        (project / ".iot-ai").mkdir(parents=True)
        (project / ".iot-ai" / "settings.json").write_text(
            json.dumps({"routing": {"max_distinct_models": 3}}),
            encoding="utf-8",
        )
        layered = load(self.home, project_root=project)
        self.assertEqual(layered["routing"]["max_distinct_models"], 3)

    def test_presets_exist(self) -> None:
        for name in (
            "balanced",
            "no-ollama",
            "no-local-ollama",
            "ollama-local-first",
            "ollama-cloud-first",
            "sovereign-local",
            "cloud-first",
            "design-quality",
            "maximum-quality",
        ):
            self.assertIn(name, PRESETS)
        diff = apply_preset(self.home, "no-ollama", apply=False)
        self.assertEqual(diff["decision"], "plan")
        self.assertEqual(diff["diff"]["after"]["routing"]["ollama"]["local_policy"], "never")
        self.assertEqual(diff["diff"]["after"]["routing"]["ollama"]["cloud_policy"], "never")

    def test_design_quality_does_not_force_backend(self) -> None:
        result = apply_preset(self.home, "design-quality", apply=False)
        self.assertEqual(result["diff"]["after"]["skills"]["design_policy"], "auto-visual-only")

    def test_effort_role_beats_provider(self) -> None:
        routing = load(self.home)["routing"]
        routing["effort"]["default"] = "low"
        routing["effort"]["by_provider"]["codex"] = "medium"
        routing["effort"]["by_role"]["implementation-engineer"] = "high"
        resolved = resolve_effort(role_id="implementation-engineer", provider="codex", routing=routing)
        self.assertEqual(resolved["configured_value"], "high")
        self.assertEqual(resolved["effective_value"], "medium")
        self.assertIn("exceeds medium", resolved["clamp_reason"] or "")

    def test_validate_pass(self) -> None:
        self.assertEqual(validate_settings(self.home)["decision"], "pass")

    def test_schema_file_parses(self) -> None:
        schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "iot-ai-settings-v2.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["title"], "iot-ai.settings.v2")

    def test_cli_show_effective(self) -> None:
        import io
        import json as json_mod
        from contextlib import redirect_stdout
        from iot_ai.cli import main

        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(["settings", "show", "--effective", "--home", str(self.home)])
        self.assertEqual(code, 0)
        payload = json_mod.loads(stream.getvalue())
        self.assertEqual(payload["schema"], SCHEMA_V2)
        self.assertIn("effective_settings_digest", payload)


class RoutingPolicyTests(IsolatedHomeTestCase):
    def _candidates(self):
        return [
            {"candidate_id": "claude:auto", "provider": "claude", "model": "auto", "live_ready": True, "priority": 10, "cloud": True},
            {"candidate_id": "codex:auto", "provider": "codex", "model": "auto", "live_ready": True, "priority": 10, "cloud": True},
            {"candidate_id": "grok:auto", "provider": "grok", "model": "auto", "live_ready": True, "priority": 10, "cloud": True},
            {"candidate_id": "ollama:local", "provider": "ollama", "model": "llama", "live_ready": True, "priority": 20, "cloud": False},
            {"candidate_id": "ollama:cloud", "provider": "ollama", "model": "cloud-model", "live_ready": True, "priority": 20, "cloud": True},
        ]

    def test_never_local_ollama(self) -> None:
        settings = load(self.home)
        settings["routing"]["ollama"] = {"local_policy": "never", "cloud_policy": "prefer"}
        with patch("iot_ai.model_policy.provider_candidates", return_value=self._candidates()):
            result = select_candidates(self.home, ["implementation-engineer"], settings=settings)
        providers = {(row["provider"], row.get("cloud")) for row in result.values()}
        self.assertNotIn(("ollama", False), providers)

    def test_only_local_ollama(self) -> None:
        settings = load(self.home)
        settings["routing"]["ollama"] = {"local_policy": "only", "cloud_policy": "never"}
        settings["models"]["local_enabled"] = True
        with patch("iot_ai.model_policy.provider_candidates", return_value=self._candidates()):
            result = select_candidates(self.home, ["implementation-engineer"], settings=settings)
        self.assertTrue(all(row["provider"] == "ollama" and not row.get("cloud") for row in result.values()))

    def test_required_local_ollama(self) -> None:
        settings = load(self.home)
        settings["routing"]["ollama"] = {"local_policy": "required", "cloud_policy": "never"}
        settings["models"]["local_enabled"] = True
        with patch("iot_ai.model_policy.provider_candidates", return_value=self._candidates()):
            result = select_candidates(
                self.home,
                ["implementation-engineer", "security-challenger", "quality-verifier"],
                settings=settings,
            )
        self.assertTrue(any(row["provider"] == "ollama" and not row.get("cloud") for row in result.values()))

    def test_max_distinct_models(self) -> None:
        settings = load(self.home)
        settings["routing"]["max_distinct_models"] = 2
        settings["routing"]["ollama"] = {"local_policy": "never", "cloud_policy": "never"}
        with patch("iot_ai.model_policy.provider_candidates", return_value=self._candidates()):
            result = select_candidates(
                self.home,
                ["implementation-engineer", "security-challenger", "quality-verifier"],
                settings=settings,
            )
        models = {f"{row['provider']}:{row['model']}" for row in result.values()}
        self.assertLessEqual(len(models), 2)

    def test_role_binding_codex_and_grok(self) -> None:
        settings = load(self.home)
        settings["routing"]["role_bindings"]["implementation-engineer"]["preferred_providers"] = ["codex"]
        settings["routing"]["role_bindings"]["implementation-engineer"]["effort"] = "xhigh"
        settings["routing"]["role_bindings"]["security-challenger"]["preferred_providers"] = ["grok"]
        settings["routing"]["role_bindings"]["security-challenger"]["effort"] = "high"
        settings["routing"]["ollama"] = {"local_policy": "never", "cloud_policy": "never"}
        with patch("iot_ai.model_policy.provider_candidates", return_value=self._candidates()):
            result = select_candidates(
                self.home,
                ["implementation-engineer", "security-challenger"],
                settings=settings,
            )
        self.assertEqual(result["implementation-engineer"]["provider"], "codex")
        self.assertEqual(result["security-challenger"]["provider"], "grok")
        self.assertEqual(result["implementation-engineer"]["requested_effort"], "xhigh")
        self.assertEqual(result["implementation-engineer"]["effective_effort"], "medium")

    def test_api_endpoint_rejects_credentials(self) -> None:
        with self.assertRaises(ValueError):
            add_route(
                self.home,
                {
                    "route_id": "bad-url",
                    "provider": "ollama",
                    "kind": "api",
                    "endpoint": "https://user:pass@example.invalid/v1",
                    "protocol": "ollama",
                    "secret_env": "OLLAMA_API_KEY",
                },
            )
        with self.assertRaises(ValueError):
            add_route(
                self.home,
                {
                    "route_id": "bad-query",
                    "provider": "ollama",
                    "kind": "api",
                    "endpoint": "https://example.invalid/v1?api_key=demo",
                    "protocol": "ollama",
                    "secret_env": "OLLAMA_API_KEY",
                },
            )

    @patch("iot_ai.providers.pin_executable", return_value={"path": "/usr/bin/true", "sha256": "0" * 64, "name": "true"})
    def test_eligible_respects_no_ollama(self, pin) -> None:
        settings = load(self.home)
        settings["cloud"]["enabled"] = True
        settings["routing"]["ollama"] = {"local_policy": "never", "cloud_policy": "never"}
        save(self.home, settings)
        providers = {row["provider"] for row in eligible_routes(self.home)}
        self.assertNotIn("ollama", providers)
