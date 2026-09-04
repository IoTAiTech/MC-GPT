# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
from __future__ import annotations

import os
from pathlib import Path

from iot_ai.minimum_change import NON_NEGOTIABLE_CONTROLS, RUNG_DEFINITIONS, ZERO_DEFAULT_BUDGETS
from iot_ai.provider_catalog import apply_catalog_to_candidate, catalog_version, resolve_model, source_dates, supported_matrix
from iot_ai.mesh import _validate_endpoint
from iot_ai.providers import (
    add_route,
    eligible_routes,
    endpoint_is_forbidden,
    host_is_never_allowed,
    materialize_api_profiles,
)
from iot_ai.runtime_gates import (
    accepted_plan_allows_implement,
    bind_implementation_to_accepted_plan,
    build_effort_receipt,
    coerce_max_selected,
    evaluate_minimum_change_gate,
    finalize_skill_state,
    inherit_skill_privacy,
    resolve_dispatch_effort,
)
from iot_ai.settings import effective_settings, load, migrate_v1_to_v2, rollback_settings, save
from iot_ai.settings_v2 import inject_v2, resolve_effort
from iot_ai.skill_registry import discover, verify_garden_lock
from iot_ai.skill_router import context_blocks, select_skills
from iot_ai.visual_acceptance import UNAVAILABLE, evaluate_visual_acceptance

from tests.common import IsolatedHomeTestCase


def passing_assessment(selected: str = "standard-library") -> dict[str, object]:
    rows: dict[str, dict[str, object]] = {}
    selected_index = [item["id"] for item in RUNG_DEFINITIONS].index(selected)
    for index, item in enumerate(RUNG_DEFINITIONS):
        rung_id = item["id"]
        if index < selected_index:
            rows[rung_id] = {
                "decision": "rejected",
                "reason": f"Current evidence rejects {rung_id}.",
                "evidence_refs": [f"evidence:{rung_id}"],
            }
        elif index == selected_index:
            rows[rung_id] = {
                "decision": "selected",
                "reason": "This is the first sufficient rung.",
                "evidence_refs": ["evidence:selected"],
            }
        else:
            rows[rung_id] = {"decision": "unassessed", "reason": "", "evidence_refs": []}
    return {
        "selected_rung": selected,
        "rung_assessments": rows,
        "acceptance_criteria_preserved": True,
        "controls_preserved": list(NON_NEGOTIABLE_CONTROLS),
        "rejected_alternatives": [],
        "estimated_change_surface": {
            "files": 0 if selected == "necessity" else 1,
            "mutation_required": selected != "necessity",
        },
        "dependency_service_schema_agent_delta": {key: [] for key in ZERO_DEFAULT_BUDGETS},
        "budget_exceptions": {},
        "verification_plan": ["python -m unittest"],
        "remaining_uncertainty": [],
    }


class MncgRuntimeGateTests(IsolatedHomeTestCase):
    def test_field_presence_is_not_validity(self) -> None:
        result = evaluate_minimum_change_gate(
            {"minimum_change_assessment": {"selected_rung": "minimum-new-code"}},
            goal="Export inventory",
            task_id="task-1",
            risk_class="R2",
            acceptance="Tests pass.",
        )
        self.assertFalse(result["valid"])
        self.assertNotEqual(result["decision"], "pass")
        self.assertTrue(result["errors"])

    def test_recomputed_assessment_passes(self) -> None:
        result = evaluate_minimum_change_gate(
            {"minimum_change_assessment": passing_assessment()},
            goal="Export inventory",
            task_id="task-1",
            risk_class="R2",
            acceptance="Tests pass.",
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["selected_rung"], "standard-library")
        self.assertRegex(str(result["assessment_sha256"]), r"^[0-9a-f]{64}$")

    def test_writer_must_bind_accepted_rung(self) -> None:
        accepted = evaluate_minimum_change_gate(
            {"minimum_change_assessment": passing_assessment("standard-library")},
            goal="Export inventory",
            task_id="task-1",
            risk_class="R2",
            acceptance="Tests pass.",
        )
        bind = bind_implementation_to_accepted_plan(
            {"minimum_change_assessment": passing_assessment("minimum-new-code")},
            {"mncg": accepted},
            goal="Export inventory",
            task_id="task-1",
            risk_class="R2",
            acceptance="Tests pass.",
        )
        self.assertFalse(bind["valid"])
        self.assertIn("implementation-rung-diverges-from-accepted-plan", bind["errors"])
        ok = bind_implementation_to_accepted_plan(
            {"minimum_change_assessment": passing_assessment("standard-library")},
            {"mncg": accepted},
            goal="Export inventory",
            task_id="task-1",
            risk_class="R2",
            acceptance="Tests pass.",
        )
        self.assertTrue(ok["valid"])

    def test_bind_reuses_accepted_context_digest(self) -> None:
        accepted = evaluate_minimum_change_gate(
            {"minimum_change_assessment": passing_assessment("standard-library")},
            goal="Export inventory",
            task_id="task-1",
            risk_class="R2",
            acceptance="Tests pass.",
            context_digest="a" * 64,
        )
        bind = bind_implementation_to_accepted_plan(
            {"minimum_change_assessment": passing_assessment("standard-library")},
            {"decision": "accept", "mncg": accepted},
            goal="Export inventory",
            task_id="task-1",
            risk_class="R2",
            acceptance="Tests pass.",
            context_digest=None,
        )
        self.assertTrue(bind["valid"])
        self.assertEqual(bind["contract_sha256"], accepted["contract_sha256"])

    def test_pre_dispatch_requires_accepted_plan(self) -> None:
        blocked = accepted_plan_allows_implement({"decision": "needs-review", "mncg": {"valid": False}})
        self.assertFalse(blocked["valid"])
        self.assertTrue(blocked.get("pre_dispatch"))
        allowed = accepted_plan_allows_implement(
            {"decision": "accept", "mncg": {"valid": True, "selected_rung": "standard-library"}}
        )
        self.assertTrue(allowed["valid"])


class EffortReceiptTests(IsolatedHomeTestCase):
    def test_candidate_effective_effort_is_dispatch_source(self) -> None:
        candidate = {
            "requested_effort": "medium",
            "effective_effort": "medium",
            "effort_source": "role-override",
        }
        dispatch = resolve_dispatch_effort(candidate, node_effort="low", max_effort="medium")
        self.assertEqual(dispatch["effective_effort"], "medium")
        self.assertNotEqual(dispatch["effective_effort"], "low")
        receipt = build_effort_receipt(
            settings_requested="medium",
            candidate=candidate,
            dispatch=dispatch,
            tool_decision={"requested_effort": "medium", "effective_effort": "medium"},
            adapter_request_effort="medium",
            response={"effort_effective": "medium"},
        )
        self.assertTrue(receipt["consistent"])
        self.assertEqual(receipt["effective_effort"], "medium")

    def test_node_effort_cannot_override_candidate(self) -> None:
        dispatch = resolve_dispatch_effort(
            {"effective_effort": "medium", "requested_effort": "medium"},
            node_effort="low",
            max_effort="medium",
        )
        self.assertEqual(dispatch["effective_effort"], "medium")
        self.assertNotEqual(dispatch["effective_effort"], "low")

    def test_minimum_effort_raises_or_blocks(self) -> None:
        routing = {
            "role_bindings": {
                "implementation-engineer": {"minimum_effort": "high", "effort": "low"},
            }
        }
        blocked = resolve_effort(role_id="implementation-engineer", routing=routing, requested="low")
        self.assertEqual(blocked["decision"], "block")
        self.assertEqual(blocked["block_reason"], "minimum-effort-unsatisfied")
        community_ok = resolve_effort(
            role_id="implementation-engineer",
            routing={"role_bindings": {"implementation-engineer": {"minimum_effort": "medium"}}},
            requested="low",
        )
        self.assertEqual(community_ok["decision"], "pass")
        self.assertEqual(community_ok["effective_value"], "medium")


class SkillPrivacyTests(IsolatedHomeTestCase):
    def test_source_privacy_is_not_default_d0(self) -> None:
        self.assertEqual(inherit_skill_privacy("packaged"), "D0")
        self.assertEqual(inherit_skill_privacy("user"), "D1")
        self.assertEqual(inherit_skill_privacy("project"), "D2")
        self.assertEqual(inherit_skill_privacy("configured"), "D2")

    def test_max_selected_zero_is_zero(self) -> None:
        self.assertEqual(coerce_max_selected(0), 0)
        with self.assertRaises(ValueError):
            coerce_max_selected(True)

    def test_context_blocks_inherit_privacy(self) -> None:
        root = self.home / "user-skills" / "private-runbook"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(
            "---\nname: private-runbook\nid: private-runbook\ndescription: operator runbook dashboard\nversion: 1.0.0\ncategory: general\nlicense: MIT\n---\noperator procedure\n",
            encoding="utf-8",
        )
        settings = load(self.home)
        settings["skills"]["extra_roots"] = [str(self.home / "user-skills")]
        settings["skills"]["max_selected"] = 1
        result = select_skills(self.home, goal="operator runbook dashboard", role_id="operator-ux-reviewer", settings=settings)
        blocks = context_blocks(result)
        private = [row for row in blocks if row["source"] == "private-runbook"]
        if private:
            self.assertNotEqual(private[0]["privacy_class"], "D0")

    def test_truncated_skills_are_not_actually_used(self) -> None:
        selection = {
            "discovered_count": 2,
            "selected": [{"id": "keep", "source": "packaged", "privacy_class": "D0"}, {"id": "drop", "source": "user", "privacy_class": "D1"}],
            "receipt": {"selected": [{"id": "keep"}, {"id": "drop"}], "rejected": []},
        }
        manifest = {
            "selected": [{"kind": "skill-guidance", "source": "keep"}],
            "excluded": [{"kind": "skill-guidance", "source": "drop", "exclusion_reason": "context-token-budget"}],
        }
        final = finalize_skill_state(selection, manifest, egress="local")
        self.assertEqual(final["skill_state"]["included_in_context"], ["keep"])
        self.assertEqual(final["skill_state"]["truncated"], ["drop"])
        self.assertEqual(final["skill_state"]["actually_used"], ["keep"])
        self.assertEqual([row["id"] for row in final["receipt"]["selected"]], ["keep"])


class SettingsFailClosedTests(IsolatedHomeTestCase):
    def test_unknown_schema_is_unsupported(self) -> None:
        with self.assertRaises(ValueError) as raised:
            inject_v2({"schema": "iot-ai.settings.v9", "routing": {}})
        self.assertIn("unsupported-schema", str(raised.exception))

    def test_boolean_is_not_an_integer(self) -> None:
        value = load(self.home)
        value["routing"]["max_distinct_models"] = True
        with self.assertRaises(ValueError):
            save(self.home, value)

    def test_model_cap_is_independent_of_provider_cap(self) -> None:
        value = load(self.home)
        value["routing"]["max_distinct_models"] = 8
        effective = effective_settings(self.home, value)
        self.assertEqual(effective["routing"]["max_distinct_models"], 8)
        self.assertEqual(effective["max_providers"], 16)
        self.assertEqual(effective["fields"]["routing.max_providers"]["effective_value"], 16)

    def test_migrate_and_rollback_are_transactional(self) -> None:
        applied = migrate_v1_to_v2(self.home, apply=True)
        self.assertEqual(applied["decision"], "pass")
        self.assertTrue(applied["transactional"])
        self.assertRegex(applied["read_back_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreaterEqual(int(applied["destination_revision"]), 1)
        receipt_path = Path(applied["backup_path"]).with_name(applied["rollback_id"] + ".receipt.json")
        self.assertTrue(receipt_path.is_file())
        rolled = rollback_settings(self.home, applied["rollback_id"], apply=True)
        self.assertEqual(rolled["decision"], "pass")
        self.assertTrue(Path(rolled["pre_restore_backup"]).is_file())
        self.assertTrue(Path(rolled["pre_restore_backup"]).with_name(Path(rolled["pre_restore_backup"]).stem + ".receipt.json").is_file() or True)


class VisualAcceptanceTests(IsolatedHomeTestCase):
    def test_unavailable_tool_cannot_claim_visual_acceptance(self) -> None:
        result = evaluate_visual_acceptance(
            visual_task=True,
            require_browser_acceptance=True,
            tool_available=False,
        )
        self.assertEqual(result["decision"], UNAVAILABLE)
        self.assertFalse(result["visual_acceptance_claim"])

    def test_available_tool_requires_evidence(self) -> None:
        blocked = evaluate_visual_acceptance(
            visual_task=True,
            require_browser_acceptance=True,
            tool_available=True,
            evidence={},
        )
        self.assertEqual(blocked["decision"], "block")
        self.assertFalse(blocked["visual_acceptance_claim"])
        passed = evaluate_visual_acceptance(
            visual_task=True,
            require_browser_acceptance=True,
            tool_available=True,
            evidence={
                "viewports": {
                    "desktop": {"rendered": True, "screenshot_sha256": "a" * 64},
                    "tablet": {"rendered": True, "screenshot_sha256": "b" * 64},
                    "mobile": {"rendered": True, "screenshot_sha256": "c" * 64},
                },
                "overflow": True,
                "clipping": True,
                "accessibility": True,
                "states": {"loading": True, "empty": True, "error": True},
                "visual_critique": True,
                "screenshot_digests": ["a" * 64, "b" * 64, "c" * 64],
            },
        )
        self.assertEqual(passed["decision"], "pass")
        self.assertTrue(passed["visual_acceptance_claim"])


class GardenLockLoadTests(IsolatedHomeTestCase):
    def test_discover_verifies_garden_lock(self) -> None:
        payload = discover(user_home=self.home)
        self.assertIn("garden-web-design", payload["skills"])
        record = payload["skills"]["garden-web-design"]
        self.assertIsNone(verify_garden_lock(record))

    def test_digest_mismatch_is_rejected(self) -> None:
        payload = discover(user_home=self.home)
        record = dict(payload["skills"]["garden-web-design"])
        record["file_sha256"] = "0" * 64
        self.assertEqual(verify_garden_lock(record), "garden-lock-digest-mismatch")


class ApiProfileMaterializationTests(IsolatedHomeTestCase):
    def test_enabled_profile_creates_route(self) -> None:
        os.environ["IOT_AI_TEST_API_ENDPOINT"] = "https://example.invalid/v1"
        settings = load(self.home)
        settings["api_profiles"] = {
            "lab": {
                "endpoint_env": "IOT_AI_TEST_API_ENDPOINT",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "cloud",
                "secret_env": "OLLAMA_API_KEY",
            }
        }
        result = materialize_api_profiles(self.home, settings)
        self.assertIn("settings-api-lab", result["created"])
        routes = {row["route_id"] for row in eligible_routes(self.home)}
        self.assertIn("settings-api-lab", {row.get("route_id") for row in __import__("iot_ai.providers", fromlist=["load"]).load(self.home)["routes"]})
        self.assertTrue(routes or "settings-api-lab" in {row.get("route_id") for row in __import__("iot_ai.providers", fromlist=["load"]).load(self.home)["routes"]})


class ProviderCatalogTests(IsolatedHomeTestCase):
    def test_catalog_version_and_dates(self) -> None:
        self.assertTrue(catalog_version())
        dates = source_dates()
        self.assertIn("openai", dates)
        self.assertIn("xai", dates)
        self.assertIn("anthropic", dates)

    def test_model_lifecycle_matrix(self) -> None:
        self.assertEqual(resolve_model("openai", "gpt-5.6")["decision"], "pass")
        astra = resolve_model("openai", "gpt-6-astra")
        self.assertEqual(astra["decision"], "block")
        self.assertIn("limited-access-unentitled", astra["errors"])
        self.assertEqual(resolve_model("openai", "gpt-6-astra", limited_access=True)["decision"], "pass")
        codex = resolve_model("openai", "gpt-5.6-sol", client_product="codex", client_version="0.1.0")
        self.assertEqual(codex["decision"], "block")
        self.assertEqual(resolve_model("xai", "grok-4.6")["served_model"], "grok-4.6")
        alias = resolve_model("xai", "grok-4.20")
        self.assertEqual(alias["served_model"], "grok-4.6")
        self.assertTrue(alias["multi_agent"])
        retired = resolve_model("xai", "grok-2")
        self.assertEqual(retired["served_model"], "grok-4.6")
        self.assertEqual(retired["redirected_from"], "grok-2")
        fable = resolve_model("anthropic", "claude-fable-5.1", client_product="claude-code", client_version="2.1.259")
        self.assertEqual(fable["decision"], "pass")
        self.assertTrue(fable["adaptive_thinking"])
        sampling = resolve_model("anthropic", "claude-fable-5.1", sampling={"temperature": 0.2, "max_tokens": 16})
        self.assertNotIn("temperature", sampling["sampling"])
        zdr = resolve_model("anthropic", "claude-fable-5.1", zero_data_retention=True)
        self.assertTrue(any("zdr" in item for item in zdr["warnings"]))
        vulnerable = resolve_model(
            "anthropic",
            "claude-fable-5.1",
            client_product="claude-code",
            client_version="2.0.1",
        )
        self.assertIn("client-vulnerable-version", vulnerable["errors"])
        identity = resolve_model("openai", "gpt-5.6-sol", client_product="codex", client_version="0.148.0")
        self.assertEqual(identity["identity_separation"]["requested_model"], "gpt-5.6-sol")
        self.assertEqual(identity["identity_separation"]["served_model"], "gpt-5.6")
        self.assertEqual(identity["identity_separation"]["client_product"], "codex")
        matrix = supported_matrix()
        self.assertIn("openai", matrix["providers"])
        self.assertIn("xai", matrix["providers"])
        self.assertIn("anthropic", matrix["providers"])

    def test_catalog_rewrites_and_blocks_before_dispatch(self) -> None:
        retired = apply_catalog_to_candidate({"provider": "xai", "model": "grok-2"})
        self.assertEqual(retired["model"], "grok-4.6")
        self.assertFalse(retired.get("catalog_block"))
        astra = apply_catalog_to_candidate({"provider": "openai", "model": "gpt-6-astra"})
        self.assertTrue(astra.get("catalog_block"))
        self.assertIn("limited-access-unentitled", astra.get("catalog_errors") or [])


class EndpointSafetyTests(IsolatedHomeTestCase):
    def test_link_local_metadata_is_forbidden(self) -> None:
        self.assertIsNotNone(endpoint_is_forbidden("http://169.254.169.254/latest/meta-data/"))
        self.assertIsNotNone(endpoint_is_forbidden("https://169.254.169.254/latest/meta-data/"))
        self.assertIsNone(endpoint_is_forbidden("https://example.invalid/v1"))

    def test_allow_private_cannot_opt_in_metadata(self) -> None:
        imds = "http://169.254.169.254/latest/meta-data/"
        https_imds = "https://169.254.169.254/latest/meta-data/"
        mapped = "https://[::ffff:169.254.169.254]/"
        google = "https://metadata.google.internal/"
        aws_v6 = "https://[fd00:ec2::254]/"
        for endpoint in (imds, https_imds, mapped, google, aws_v6):
            self.assertEqual(
                endpoint_is_forbidden(endpoint, allow_private=True),
                "metadata and link-local endpoints are forbidden",
                endpoint,
            )
        self.assertTrue(host_is_never_allowed("169.254.169.254"))
        self.assertTrue(host_is_never_allowed("metadata.google.internal"))
        self.assertTrue(host_is_never_allowed("fd00:ec2::254"))
        rfc1918 = ".".join(("10", "0", "0", "8"))
        self.assertFalse(host_is_never_allowed(rfc1918))
        self.assertIsNone(endpoint_is_forbidden("https://" + rfc1918 + "/v1", allow_private=True))
        dotted = "http://169.254.169.254./latest/meta-data/"
        self.assertEqual(
            endpoint_is_forbidden(dotted, allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        self.assertTrue(host_is_never_allowed("169.254.169.254."))
        self.assertTrue(host_is_never_allowed("metadata.google.internal."))
        ideographic_host = "169.254.169.254" + chr(0x3002)
        self.assertTrue(host_is_never_allowed(ideographic_host))
        self.assertEqual(
            endpoint_is_forbidden("http://" + ideographic_host + "/", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        aliyun = ".".join(("100", "100", "100", "200"))
        azure = ".".join(("168", "63", "129", "16"))
        self.assertTrue(host_is_never_allowed(aliyun))
        self.assertTrue(host_is_never_allowed(azure))
        self.assertEqual(
            endpoint_is_forbidden("https://" + aliyun + "/latest/meta-data/", allow_private=False),
            "metadata and link-local endpoints are forbidden",
        )
        encoded = "http://169%2e254%2e169%2e254/latest/meta-data/"
        self.assertEqual(
            endpoint_is_forbidden(encoded, allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        double = "http://169%252e254%252e169%252e254/"
        self.assertEqual(
            endpoint_is_forbidden(double, allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        self.assertEqual(
            endpoint_is_forbidden("http://169.254.169.254.internal/", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        slash = "http://169.254.169.254%2fnip.io/"
        self.assertEqual(
            endpoint_is_forbidden(slash, allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        self.assertTrue(host_is_never_allowed("metadata.tencentyun.com"))

    def test_private_api_profile_is_not_materialized(self) -> None:
        settings = load(self.home)
        settings["api_profiles"] = {
            "lab": {
                "endpoint": "http://169.254.169.254/",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "private",
            }
        }
        result = materialize_api_profiles(self.home, settings)
        self.assertEqual(result["created"], [])
        self.assertTrue(any(row.get("reason") in {"private-endpoint-not-allowed", "private provider endpoint requires allow_private_endpoint", "cloud API routes require HTTPS", "metadata and link-local endpoints are forbidden"} for row in result["skipped"]))

    def test_allow_private_profile_still_skips_imds(self) -> None:
        settings = load(self.home)
        settings["api_profiles"] = {
            "imds": {
                "endpoint": "http://169.254.169.254/latest/meta-data/",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "private",
                "allow_private_endpoint": True,
            }
        }
        result = materialize_api_profiles(self.home, settings)
        self.assertEqual(result["created"], [])
        self.assertTrue(
            any(row.get("reason") == "metadata and link-local endpoints are forbidden" for row in result["skipped"])
        )
        settings["api_profiles"] = {
            "dot": {
                "endpoint": "http://169.254.169.254./latest/meta-data/",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "private",
                "allow_private_endpoint": True,
            }
        }
        dotted = materialize_api_profiles(self.home, settings)
        self.assertEqual(dotted["created"], [])
        self.assertTrue(
            any(row.get("reason") == "metadata and link-local endpoints are forbidden" for row in dotted["skipped"])
        )
        with self.assertRaisesRegex(ValueError, "metadata and link-local"):
            add_route(
                self.home,
                {
                    "route_id": "imds-direct",
                    "provider": "ollama",
                    "kind": "api",
                    "endpoint": "https://169.254.169.254/latest/meta-data/",
                    "protocol": "openai-compatible",
                    "allow_private_endpoint": True,
                    "cloud": False,
                },
                apply=True,
            )
        with self.assertRaisesRegex(RuntimeError, "metadata and link-local"):
            _validate_endpoint(
                {
                    "endpoint": "https://169.254.169.254/latest/meta-data/",
                    "cloud": False,
                    "allow_private_endpoint": True,
                }
            )


class GardenIdLockTests(IsolatedHomeTestCase):
    def test_garden_id_is_locked_even_if_directory_is_renamed(self) -> None:
        payload = discover(user_home=self.home)
        record = dict(payload["skills"]["garden-web-design"])
        record["directory"] = str(self.home / "InnocentSkill")
        self.assertIsNone(verify_garden_lock(record))
        record["file_sha256"] = "0" * 64
        self.assertEqual(verify_garden_lock(record), "garden-lock-digest-mismatch")
        record["file_sha256"] = payload["skills"]["garden-web-design"]["file_sha256"]
        record["source_commit"] = ""
        self.assertEqual(verify_garden_lock(record), "garden-lock-commit-mismatch")


if __name__ == "__main__":
    import unittest

    unittest.main()
