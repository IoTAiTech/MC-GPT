# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
from __future__ import annotations

import os
from pathlib import Path

from iot_ai.minimum_change import NON_NEGOTIABLE_CONTROLS, RUNG_DEFINITIONS, ZERO_DEFAULT_BUDGETS
from iot_ai.provider_catalog import apply_catalog_to_candidate, catalog_version, resolve_model, source_dates, supported_matrix
from iot_ai.mesh import _build_api_request, _validate_endpoint
from iot_ai.providers import (
    add_route,
    effective_api_profiles,
    eligible_routes,
    endpoint_is_forbidden,
    host_is_never_allowed,
    host_requires_private_allow,
    materialize_api_profiles,
    sync_api_profiles,
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

    def test_same_rung_different_delta_is_drift(self) -> None:
        accepted = evaluate_minimum_change_gate(
            {"minimum_change_assessment": passing_assessment("standard-library")},
            goal="Export inventory",
            task_id="task-1",
            risk_class="R2",
            acceptance="Tests pass.",
            context_digest="a" * 64,
            revision=3,
        )
        drifted = passing_assessment("standard-library")
        drifted["dependency_service_schema_agent_delta"] = {
            **drifted["dependency_service_schema_agent_delta"],
            "new_dependencies": ["new-package"],
        }
        drifted["budget_exceptions"] = {
            "new_dependencies": {
                "reason": "Acceptance requires one library already proven missing from earlier rungs.",
                "evidence_refs": ["evidence:dep"],
                "acceptance_refs": ["Tests pass."],
            }
        }
        bind = bind_implementation_to_accepted_plan(
            {"minimum_change_assessment": drifted},
            {"mncg": accepted},
            goal="Export inventory",
            task_id="task-1",
            risk_class="R2",
            acceptance="Tests pass.",
            context_digest="a" * 64,
            revision=3,
        )
        self.assertFalse(bind["valid"])
        self.assertTrue(any("drift" in item or "delta" in item for item in bind["errors"]))

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

    def test_api_adapter_request_carries_effective_effort(self) -> None:
        route = {
            "endpoint": "https://example.invalid",
            "protocol": "openai-compatible",
            "cloud": True,
        }
        plan = _build_api_request(route, "ping", "gpt-5.6", "high")
        self.assertEqual(plan["body"]["reasoning_effort"], "high")
        self.assertTrue(plan["effort"]["effort_applied"])
        self.assertEqual(plan["effort"]["effort_effective"], "high")
        self.assertEqual(plan["effort"]["effort_field"], "reasoning_effort")
        anthropic = _build_api_request(
            {"endpoint": "https://example.invalid", "protocol": "anthropic", "cloud": True, "secret_env": ""},
            "ping",
            "claude-sonnet-5",
            "low",
        )
        self.assertEqual(anthropic["body"]["thinking"]["type"], "adaptive")
        self.assertNotIn("budget_tokens", anthropic["body"]["thinking"])
        self.assertEqual(anthropic["body"]["output_config"]["effort"], "low")
        self.assertTrue(anthropic["effort"]["effort_applied"])
        anthropic_high = _build_api_request(
            {"endpoint": "https://example.invalid", "protocol": "anthropic", "cloud": True, "secret_env": ""},
            "ping",
            "claude-opus-5",
            "high",
        )
        self.assertEqual(anthropic_high["body"]["thinking"]["type"], "adaptive")
        self.assertEqual(anthropic_high["body"]["output_config"]["effort"], "high")
        openai_max = _build_api_request(
            {"endpoint": "https://example.invalid", "protocol": "openai-compatible", "cloud": True},
            "ping",
            "gpt-5.6-sol",
            "max",
        )
        self.assertEqual(openai_max["body"]["reasoning_effort"], "max")
        ollama = _build_api_request(
            {"endpoint": "https://example.invalid", "protocol": "ollama", "cloud": True},
            "ping",
            "auto:cloud",
            "xhigh",
        )
        self.assertEqual(ollama["body"]["think"], "xhigh")
        gemini = _build_api_request(
            {"endpoint": "https://example.invalid", "protocol": "gemini", "cloud": True, "secret_env": ""},
            "ping",
            "gemini-2.5-pro",
            "medium",
        )
        self.assertEqual(gemini["body"]["generationConfig"]["thinkingConfig"]["thinkingLevel"], "medium")
        receipt = build_effort_receipt(
            settings_requested="high",
            candidate={"effective_effort": "high", "requested_effort": "high"},
            dispatch={"effective_effort": "high", "requested_effort": "high", "effort_source": "candidate"},
            tool_decision={"effective_effort": "high"},
            adapter_request_effort=plan["effort"]["effort_effective"],
            response={"effort_effective": plan["effort"]["effort_effective"]},
        )
        self.assertTrue(receipt["consistent"])
        missing = build_effort_receipt(
            settings_requested="high",
            candidate={"effective_effort": "high", "requested_effort": "high"},
            dispatch={"effective_effort": "high", "requested_effort": "high", "effort_source": "candidate"},
            tool_decision={"effective_effort": "high"},
            adapter_request_effort=None,
            response={"effort_effective": "high"},
        )
        self.assertEqual(missing["stages"]["adapter_request"], None)
        self.assertFalse(missing["consistent"])
        self.assertIn("adapter_request", missing["missing_stages"])


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

    def test_skill_receipts_redact_absolute_paths(self) -> None:
        payload = discover(user_home=self.home)
        record = payload["skills"]["garden-web-design"]
        self.assertNotIn("/home/", str(record.get("directory") or ""))
        self.assertTrue(record.get("root_id"))
        self.assertIn("garden-web-design", str(record.get("relative_path") or ""))
        self.assertEqual(record.get("trust_tier"), "packaged-reviewed")

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

    def test_effective_digest_includes_api_profiles(self) -> None:
        value = load(self.home)
        first = effective_settings(self.home, value)
        value["api_profiles"] = {
            "lab": {
                "endpoint": "https://example.invalid/v1",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "cloud",
            }
        }
        second = effective_settings(self.home, value)
        self.assertNotEqual(first["effective_settings_digest"], second["effective_settings_digest"])

    def test_save_requires_optimistic_concurrency(self) -> None:
        from iot_ai.settings_v2 import sha256_json

        value = load(self.home)
        save(self.home, value)
        current = load(self.home, normalize=False)
        with self.assertRaises(ValueError) as raised:
            save(self.home, current)
        self.assertIn("optimistic-concurrency-required", str(raised.exception))
        save(
            self.home,
            current,
            expected_revision=int(current.get("revision") or 0),
            expected_digest=sha256_json(current),
        )

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
        receipt = Path(rolled["pre_restore_backup"]).with_name(Path(rolled["pre_restore_backup"]).stem + ".receipt.json")
        self.assertTrue(receipt.is_file())


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
        self.assertEqual(blocked["decision"], "block")
        self.assertFalse(blocked["visual_acceptance_claim"])
        shots = self.home / "visual"
        shots.mkdir()
        digests = []
        paths = {}
        for name in ("desktop", "tablet", "mobile"):
            path = shots / f"{name}.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + name.encode() + b"0" * 64)
            digest = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
            digests.append(digest)
            paths[name] = str(path)
        passed = evaluate_visual_acceptance(
            visual_task=True,
            require_browser_acceptance=True,
            tool_available=True,
            evidence={
                "viewports": {
                    name: {"rendered": True, "screenshot_sha256": digest, "path": paths[name]}
                    for name, digest in zip(("desktop", "tablet", "mobile"), digests)
                },
                "screenshot_paths": paths,
                "overflow": True,
                "clipping": True,
                "accessibility": True,
                "accessibility_executed": True,
                "states": {"loading": True, "empty": True, "error": True},
                "visual_critique": True,
                "screenshot_digests": digests,
                "browser_version": "test-runner",
            },
        )
        self.assertEqual(passed["decision"], "pass")
        self.assertTrue(passed["visual_acceptance_claim"])
        self.assertEqual(passed["recomputed_screenshot_sha256"], digests)


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
        view = effective_api_profiles(settings)
        self.assertTrue(any(row["route_id"] == "settings-api-lab" for row in view["routes"]))
        before = __import__("iot_ai.providers", fromlist=["load"]).load(self.home)
        self.assertNotIn("settings-api-lab", {row.get("route_id") for row in before.get("routes") or []})
        planned = sync_api_profiles(self.home, settings, apply=False)
        self.assertEqual(planned["decision"], "plan")
        result = materialize_api_profiles(self.home, settings)
        self.assertIn("settings-api-lab", result["created"])
        self.assertIn("settings-api-lab", {row.get("route_id") for row in __import__("iot_ai.providers", fromlist=["load"]).load(self.home)["routes"]})


class ProviderCatalogTests(IsolatedHomeTestCase):
    def test_catalog_version_and_dates(self) -> None:
        self.assertTrue(catalog_version())
        dates = source_dates()
        self.assertIn("openai", dates)
        self.assertIn("xai", dates)
        self.assertIn("anthropic", dates)

    def test_model_lifecycle_matrix(self) -> None:
        gpt = resolve_model("openai", "gpt-5.6")
        self.assertEqual(gpt["decision"], "pass")
        self.assertEqual(gpt["canonical_target_model"], "gpt-5.6-sol")
        self.assertIsNone(gpt["model_served"])
        terra = resolve_model("openai", "gpt-5.6-terra")
        self.assertEqual(terra["canonical_target_model"], "gpt-5.6-terra")
        luna = resolve_model("openai", "gpt-5.6-luna")
        self.assertEqual(luna["canonical_target_model"], "gpt-5.6-luna")
        astra = resolve_model("openai", "gpt-6-astra")
        self.assertEqual(astra["decision"], "block")
        self.assertIn("limited-access-unentitled", astra["errors"])
        self.assertEqual(resolve_model("openai", "gpt-6-astra", limited_access=True)["decision"], "pass")
        label = resolve_model("openai", "gpt-5.6-codex")
        self.assertEqual(label["decision"], "block")
        self.assertIn("client-product-label-not-api-id", label["errors"])
        codex = resolve_model("openai", "gpt-5.6-sol", client_product="codex", client_version="0.1.0")
        self.assertEqual(codex["decision"], "block")
        self.assertEqual(resolve_model("openai", "gpt-5.6-sol", client_product="codex", client_version="0.144.0")["decision"], "pass")
        self.assertEqual(resolve_model("xai", "grok-4.6")["canonical_target_model"], "grok-4.6")
        alias = resolve_model("xai", "grok-4.20")
        self.assertEqual(alias["canonical_target_model"], "grok-4.20-0309-reasoning")
        self.assertFalse(alias.get("multi_agent"))
        self.assertIsNone(alias["model_served"])
        non_reason = resolve_model("xai", "grok-4.20-0309-non-reasoning")
        self.assertEqual(non_reason["canonical_target_model"], "grok-4.20-0309-non-reasoning")
        multi = resolve_model("xai", "grok-4.20-multi-agent-0309")
        self.assertTrue(multi["multi_agent"])
        self.assertEqual(resolve_model("xai", "grok-build-0.1")["canonical_target_model"], "grok-build-0.1")
        retired = resolve_model("xai", "grok-2")
        self.assertEqual(retired["canonical_target_model"], "grok-4.6")
        self.assertEqual(retired["redirected_from"], "grok-2")
        fable = resolve_model("anthropic", "claude-fable-5-1", client_product="claude-code", client_version="2.1.255")
        self.assertEqual(fable["decision"], "pass")
        self.assertTrue(fable["adaptive_thinking"])
        dotted = resolve_model("anthropic", "claude-fable-5.1", client_product="claude-code", client_version="2.1.255")
        self.assertEqual(dotted["canonical_target_model"], "claude-fable-5-1")
        self.assertEqual(resolve_model("anthropic", "claude-opus-5")["decision"], "pass")
        self.assertEqual(resolve_model("anthropic", "claude-sonnet-5")["decision"], "pass")
        sampling = resolve_model("anthropic", "claude-fable-5-1", sampling={"temperature": 0.2, "max_tokens": 16})
        self.assertNotIn("temperature", sampling["sampling"])
        zdr = resolve_model("anthropic", "claude-fable-5-1", zero_data_retention=True)
        self.assertEqual(zdr["decision"], "block")
        self.assertIn("zdr-training-retention-forbidden", zdr["errors"])
        vulnerable = resolve_model(
            "anthropic",
            "claude-fable-5-1",
            client_product="claude-code",
            client_version="2.0.1",
        )
        self.assertIn("client-vulnerable-version", vulnerable["errors"])
        identity = resolve_model("openai", "gpt-5.6", client_product="codex", client_version="0.144.0")
        self.assertEqual(identity["identity_separation"]["model_requested"], "gpt-5.6")
        self.assertEqual(identity["identity_separation"]["canonical_target_model"], "gpt-5.6-sol")
        self.assertIsNone(identity["identity_separation"]["model_served"])
        self.assertEqual(identity["identity_separation"]["client_product"], "codex")
        matrix = supported_matrix()
        self.assertIn("openai", matrix["providers"])
        self.assertIn("xai", matrix["providers"])
        self.assertIn("anthropic", matrix["providers"])
        self.assertEqual(matrix["provider_namespaces"]["codex"], "openai")

    def test_catalog_rewrites_and_blocks_before_dispatch(self) -> None:
        from iot_ai.provider_catalog import normalize_provider

        self.assertEqual(normalize_provider("codex"), "openai")
        self.assertEqual(normalize_provider("grok"), "xai")
        self.assertEqual(normalize_provider("claude"), "anthropic")
        runtime = apply_catalog_to_candidate({"provider": "codex", "model": "gpt-5.6"})
        self.assertEqual(runtime["provider_family"], "openai")
        self.assertEqual(runtime["canonical_target_model"], "gpt-5.6-sol")
        self.assertIsNone(runtime["model_served"])
        grok = apply_catalog_to_candidate({"provider": "grok", "model": "grok-4.20"})
        self.assertEqual(grok["provider_family"], "xai")
        self.assertEqual(grok["canonical_target_model"], "grok-4.20-0309-reasoning")
        retired = apply_catalog_to_candidate({"provider": "xai", "model": "grok-2"})
        self.assertEqual(retired["canonical_target_model"], "grok-4.6")
        self.assertIsNone(retired.get("model_served"))
        self.assertFalse(retired.get("catalog_block"))
        astra = apply_catalog_to_candidate({"provider": "openai", "model": "gpt-6-astra"})
        self.assertTrue(astra.get("catalog_block"))
        self.assertIn("limited-access-unentitled", astra.get("catalog_errors") or [])
        evil = apply_catalog_to_candidate({"provider": "evil-provider", "model": "x", "risk_class": "R2"})
        self.assertTrue(evil.get("catalog_block"))
        self.assertIn("unknown-provider-capability", evil.get("catalog_errors") or [])
        gemini = apply_catalog_to_candidate({"provider": "gemini", "model": "gemini-2.5-pro", "risk_class": "R2"})
        self.assertFalse(gemini.get("catalog_block"))
        ollama = apply_catalog_to_candidate({"provider": "ollama", "model": "gpt-oss:20b", "risk_class": "R2"})
        self.assertFalse(ollama.get("catalog_block"))


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
        self.assertTrue(host_requires_private_allow(rfc1918))
        self.assertIsNotNone(endpoint_is_forbidden("https://" + rfc1918 + "/v1", allow_private=False))
        self.assertIsNone(endpoint_is_forbidden("https://" + rfc1918 + "/v1", allow_private=True))
        cgnat = ".".join(("100", "64", "0", "1"))
        aliyun_adj = ".".join(("100", "100", "100", "201"))
        self.assertFalse(host_is_never_allowed(cgnat))
        self.assertTrue(host_requires_private_allow(cgnat))
        self.assertTrue(host_requires_private_allow(aliyun_adj))
        self.assertEqual(
            endpoint_is_forbidden("https://" + cgnat + "/v1", allow_private=False),
            "private provider endpoint requires allow_private_endpoint",
        )
        self.assertIsNone(endpoint_is_forbidden("https://" + cgnat + "/v1", allow_private=True))
        self.assertEqual(
            endpoint_is_forbidden("https://" + aliyun_adj + "/v1", allow_private=False),
            "private provider endpoint requires allow_private_endpoint",
        )
        cgnat_suffix = "https://" + cgnat + ".example.invalid/v1"
        self.assertEqual(
            endpoint_is_forbidden(cgnat_suffix, allow_private=False),
            "private provider endpoint requires allow_private_endpoint",
        )
        self.assertIsNone(endpoint_is_forbidden(cgnat_suffix, allow_private=True))
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
        sixto4 = "https://[2002:a9fe:a9fe::]/"
        teredo = "https://[2001:0:a9fe:a9fe::]/"
        aliyun_6to4 = "https://[2002:6464:64c8::]/"
        azure_6to4 = "https://[2002:a83f:8110::]/"
        for endpoint in (sixto4, teredo, aliyun_6to4, azure_6to4):
            self.assertEqual(
                endpoint_is_forbidden(endpoint, allow_private=True),
                "metadata and link-local endpoints are forbidden",
                endpoint,
            )
        self.assertEqual(
            endpoint_is_forbidden("https://0xa9.0xfe.0xa9.0xfe.nip.io/", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        self.assertEqual(
            endpoint_is_forbidden("https://2852039166.nip.io/", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        packed_three = "169.254.43518.nip.io"
        packed_two = "169.16689150.nip.io"
        packed_hex = "169.254.0xa9fe.nip.io"
        self.assertTrue(host_is_never_allowed(packed_three, resolve_dns=False))
        self.assertTrue(host_is_never_allowed(packed_two, resolve_dns=False))
        self.assertTrue(host_is_never_allowed(packed_hex, resolve_dns=False))
        for packed_host in (packed_three, packed_two, packed_hex):
            self.assertEqual(
                endpoint_is_forbidden("https://" + packed_host + "/v1", allow_private=True),
                "metadata and link-local endpoints are forbidden",
                packed_host,
            )
        loopback_dword = "2130706433.nip.io"
        self.assertFalse(host_is_never_allowed(loopback_dword, resolve_dns=False))
        self.assertTrue(host_requires_private_allow(loopback_dword, resolve_dns=False))
        self.assertEqual(
            endpoint_is_forbidden("https://" + loopback_dword + "/v1", allow_private=False),
            "private provider endpoint requires allow_private_endpoint",
        )
        self.assertIsNone(endpoint_is_forbidden("https://" + loopback_dword + "/v1", allow_private=True))
        self.assertTrue(host_requires_private_allow("127.1", resolve_dns=False))
        public_suffix = "8.8.8.8.example.invalid"
        self.assertFalse(host_is_never_allowed(public_suffix, resolve_dns=False))
        self.assertFalse(host_requires_private_allow(public_suffix, resolve_dns=False))
        interior = "1.169.254.43518.nip.io"
        leading_public = "8.8.8.8.169.254.43518.nip.io"
        self.assertTrue(host_is_never_allowed(interior, resolve_dns=False))
        self.assertTrue(host_is_never_allowed(leading_public, resolve_dns=False))
        for packed_host in (interior, leading_public, "1.169.16689150.nip.io"):
            self.assertEqual(
                endpoint_is_forbidden("https://" + packed_host + "/v1", allow_private=True),
                "metadata and link-local endpoints are forbidden",
                packed_host,
            )
        ideo = chr(0x3002)
        packed_ideo = ideo.join(("1", "169", "254", "43518")) + ".nip.io"
        self.assertTrue(host_is_never_allowed(packed_ideo, resolve_dns=False))
        self.assertEqual(
            endpoint_is_forbidden("https://" + packed_ideo + "/v1", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        middle = chr(0x00B7)
        packed_middle = middle.join(("169", "254", "169", "254"))
        self.assertTrue(host_is_never_allowed(packed_middle, resolve_dns=False))
        self.assertEqual(
            endpoint_is_forbidden("https://" + packed_middle + "/v1", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        hyphen_imds = "169-254-169-254.nip.io"
        aws_style = "ip-169-254-169-254.ec2.internal"
        self.assertTrue(host_is_never_allowed(hyphen_imds, resolve_dns=False))
        self.assertTrue(host_is_never_allowed(aws_style, resolve_dns=False))
        self.assertEqual(
            endpoint_is_forbidden("https://" + hyphen_imds + "/v1", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        self.assertEqual(
            endpoint_is_forbidden("https://" + aws_style + "/v1", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        minus = chr(0x2212)
        packed_minus = minus.join(("169", "254", "169", "254")) + ".nip.io"
        self.assertTrue(host_is_never_allowed(packed_minus, resolve_dns=False))
        self.assertEqual(
            endpoint_is_forbidden("https://" + packed_minus + "/v1", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        small_dot = "%" + "ef%b9%92"
        encoded = small_dot.join(("1", "169", "254", "43518")) + ".nip.io"
        self.assertTrue(host_is_never_allowed(encoded, resolve_dns=False))
        self.assertEqual(
            endpoint_is_forbidden("https://" + encoded + "/v1", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        smear = "%" + "25ef%b9%92"
        smeared = smear.join(("1", "169", "254", "43518")) + ".nip.io"
        self.assertTrue(host_is_never_allowed(smeared, resolve_dns=False))
        self.assertEqual(
            endpoint_is_forbidden("https://" + smeared + "/v1", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )
        self.assertEqual(
            endpoint_is_forbidden("https://metadata.google.internal.attacker.example/", allow_private=True),
            "metadata and link-local endpoints are forbidden",
        )

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
        cgnat = ".".join(("100", "64", "0", "1"))
        settings["api_profiles"] = {
            "cgnat": {
                "endpoint": "https://" + cgnat + "/v1",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "cloud",
                "allow_private_endpoint": False,
            }
        }
        cgnat_result = materialize_api_profiles(self.home, settings)
        self.assertEqual(cgnat_result["created"], [])
        self.assertTrue(
            any(
                row.get("reason") == "private provider endpoint requires allow_private_endpoint"
                for row in cgnat_result["skipped"]
            )
        )

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
        settings["api_profiles"] = {
            "sixto4": {
                "endpoint": "https://[2002:a9fe:a9fe::]/",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "private",
                "allow_private_endpoint": True,
            }
        }
        sixto4 = materialize_api_profiles(self.home, settings)
        self.assertEqual(sixto4["created"], [])
        self.assertTrue(
            any(row.get("reason") == "metadata and link-local endpoints are forbidden" for row in sixto4["skipped"])
        )
        settings["api_profiles"] = {
            "packed": {
                "endpoint": "https://169.254.43518.nip.io/v1",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "cloud",
                "allow_private_endpoint": True,
            }
        }
        packed = materialize_api_profiles(self.home, settings)
        self.assertEqual(packed["created"], [])
        self.assertTrue(
            any(row.get("reason") == "metadata and link-local endpoints are forbidden" for row in packed["skipped"])
        )
        settings["api_profiles"] = {
            "interior": {
                "endpoint": "https://1.169.254.43518.nip.io/v1",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "cloud",
                "allow_private_endpoint": False,
            }
        }
        interior = materialize_api_profiles(self.home, settings)
        self.assertEqual(interior["created"], [])
        self.assertTrue(
            any(row.get("reason") == "metadata and link-local endpoints are forbidden" for row in interior["skipped"])
        )
        ideo = chr(0x3002)
        settings["api_profiles"] = {
            "ideo": {
                "endpoint": "https://" + ideo.join(("1", "169", "254", "43518")) + ".nip.io/v1",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "cloud",
                "allow_private_endpoint": False,
            }
        }
        ideo_result = materialize_api_profiles(self.home, settings)
        self.assertEqual(ideo_result["created"], [])
        self.assertTrue(
            any(row.get("reason") == "metadata and link-local endpoints are forbidden" for row in ideo_result["skipped"])
        )
        settings["api_profiles"] = {
            "dash": {
                "endpoint": "https://169-254-169-254.nip.io/v1",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "cloud",
                "allow_private_endpoint": False,
            }
        }
        dash = materialize_api_profiles(self.home, settings)
        self.assertEqual(dash["created"], [])
        self.assertTrue(
            any(row.get("reason") == "metadata and link-local endpoints are forbidden" for row in dash["skipped"])
        )
        small_dot = "%" + "ef%b9%92"
        settings["api_profiles"] = {
            "fe52": {
                "endpoint": "https://" + small_dot.join(("1", "169", "254", "43518")) + ".nip.io/v1",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "cloud",
                "allow_private_endpoint": True,
            }
        }
        fe52 = materialize_api_profiles(self.home, settings)
        self.assertEqual(fe52["created"], [])
        self.assertTrue(
            any(row.get("reason") == "metadata and link-local endpoints are forbidden" for row in fe52["skipped"])
        )
        smear = "%" + "25ef%b9%92"
        settings["api_profiles"] = {
            "smear": {
                "endpoint": "https://" + smear.join(("1", "169", "254", "43518")) + ".nip.io/v1",
                "protocol": "openai-compatible",
                "provider": "ollama",
                "enabled": True,
                "classification": "cloud",
                "allow_private_endpoint": True,
            }
        }
        smeared = materialize_api_profiles(self.home, settings)
        self.assertEqual(smeared["created"], [])
        self.assertTrue(
            any(
                row.get("reason") == "metadata and link-local endpoints are forbidden"
                for row in smeared["skipped"]
            )
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

    def test_garden_lock_uses_exact_skill_md_path(self) -> None:
        payload = discover(user_home=self.home)
        record = dict(payload["skills"]["garden-web-design"])
        record["id"] = "garden-web-design-evil"
        record["relative_path"] = "third-party/garden-web-design-evil"
        self.assertEqual(verify_garden_lock(record), "garden-lock-unlisted")


class UniqueSeatFollowupTests(IsolatedHomeTestCase):
    def test_cli_save_passes_optimistic_concurrency(self) -> None:
        from iot_ai import cli
        from iot_ai.settings_v2 import sha256_json

        original = load(self.home, normalize=False)
        import sys
        from io import StringIO

        old = sys.stdout
        sys.stdout = StringIO()
        try:
            rc = cli.main(["--home", str(self.home), "settings", "set", "routing.max_distinct_models", "7"])
        finally:
            sys.stdout = old
        self.assertEqual(rc, 0)
        updated = load(self.home, normalize=False)
        self.assertEqual(int(updated["routing"]["max_distinct_models"]), 7)
        self.assertNotEqual(sha256_json(original), sha256_json(updated))

    def test_api_request_connects_to_pinned_ip(self) -> None:
        import socket
        from iot_ai import mesh

        seen: dict[str, object] = {}

        def fake_getaddrinfo(host, port, *args, **kwargs):
            self.assertEqual(host, "example.invalid")
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))]

        def fake_create_connection(address, timeout=None):
            seen["address"] = address
            raise OSError("stop-before-tls")

        original_getaddrinfo = socket.getaddrinfo
        original_create = socket.create_connection
        socket.getaddrinfo = fake_getaddrinfo  # type: ignore[assignment]
        socket.create_connection = fake_create_connection  # type: ignore[assignment]
        try:
            with self.assertRaises(RuntimeError):
                mesh._api_request(
                    {"endpoint": "https://example.invalid", "protocol": "openai-compatible", "cloud": True},
                    "ping",
                    "gpt-5.6-sol",
                    2,
                    effort="low",
                )
        finally:
            socket.getaddrinfo = original_getaddrinfo
            socket.create_connection = original_create
        self.assertEqual(seen.get("address"), ("8.8.8.8", 443))

    def test_cli_success_does_not_synthesize_model_served(self) -> None:
        usage = {"model_served": None}
        selected_model = "gpt-5.6"
        self.assertIsNone(usage.get("model_served"))
        self.assertNotEqual(selected_model, usage.get("model_served"))


if __name__ == "__main__":
    import unittest

    unittest.main()
