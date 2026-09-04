# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-05
"""Synthetic, network-free safety regressions. No live provider qualification."""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
from pathlib import Path
import struct
from unittest.mock import patch
import zlib

import pytest
from iot_ai import agentic
from iot_ai.control_flow import ControlFlowState, continuation_decision
from iot_ai.roles import ROLE_CATALOG
from iot_ai.runtime_gates import (
    accepted_plan_allows_implement, bind_implementation_to_accepted_plan,
    evaluate_minimum_change_gate, resolve_dispatch_effort,
)
from iot_ai.settings_v2 import EFFORT_ORDER
from iot_ai.visual_acceptance import (
    TrustedVisualRun, VIEWPORT_PIXELS, evaluate_visual_acceptance, validate_screenshot,
)
from iot_ai.workspace import connect_write
from tests.test_agentic import fake_node_executor
from tests.test_runtime_enforcement_corrective import passing_assessment

ARGS = dict(goal="Export synthetic inventory", task_id="task-fixture", risk_class="R2",
            acceptance="The fixture tests pass.", context_digest="1" * 64, revision=7)


def accepted():
    proof = evaluate_minimum_change_gate({"minimum_change_assessment": passing_assessment()}, **ARGS)
    assert proof["valid"]
    return {"decision": "accept", "plan_digest": "2" * 64,
            "hard_gates": {"minimum_change_assessment_valid": True}, "mncg": proof}


def graph_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@pytest.mark.parametrize("change", [
    {"task_id": "task-other"}, {"revision": 8}, {"revision": True},
    {"acceptance": "An extra mandatory check."}, {"context_digest": "3" * 64},
    {"context_digest": None}, {"risk_class": "R4"}, {"goal": "Another goal"},
])
def test_live_authority_cannot_be_replaced_by_frozen_values(change):
    result = bind_implementation_to_accepted_plan(
        {"minimum_change_assessment": passing_assessment()}, accepted(), **(ARGS | change))
    assert result["valid"] is False
    assert result["errors"]


def test_unchanged_authority_still_passes():
    assert bind_implementation_to_accepted_plan(
        {"minimum_change_assessment": passing_assessment()}, accepted(), **ARGS)["valid"] is True


@pytest.mark.parametrize("field,value", [
    ("verification_plan", ["A different verification command"]),
    ("remaining_uncertainty", ["New unresolved risk"]),
    ("estimated_change_surface", {"files": 8, "mutation_required": True}),
    ("rejected_alternatives", [{"rung": "necessity", "reason": "Different evidence"}]),
])
def test_same_rung_different_strategy_is_blocked(field, value):
    assessment = passing_assessment()
    assessment[field] = value
    result = bind_implementation_to_accepted_plan({"minimum_change_assessment": assessment}, accepted(), **ARGS)
    assert result["valid"] is False


@pytest.mark.parametrize("proof", [None, {}, {"decision": "accept", "mncg": {"valid": True}},
                                    {"decision": "accept", "mncg": []}])
def test_boolean_or_missing_proof_never_authorizes(proof):
    assert accepted_plan_allows_implement(proof)["valid"] is False


def test_managed_digest_and_recomputed_assessment_both_required():
    plan = accepted()
    assert accepted_plan_allows_implement(plan)["valid"] is False
    digest = graph_hash(plan)
    assert accepted_plan_allows_implement(plan, persisted_output_sha256=digest)["valid"] is True
    changed = copy.deepcopy(plan)
    changed["mncg"]["normalized"]["controls_preserved"] = []
    # Even a freshly recomputed caller hash does not replace semantic validation.
    assert accepted_plan_allows_implement(changed, persisted_output_sha256=graph_hash(changed))["valid"] is False
    assert accepted_plan_allows_implement(plan, persisted_output_sha256="0" * 64)["valid"] is False


@pytest.mark.parametrize("maximum,support,floor", itertools.product(
    ["none", "low", "medium"], [[], ["high"], ["none", "low"], ["low", "medium"]],
    ["none", "low", "high"],
))
def test_effort_never_escapes_intersection(maximum, support, floor):
    result = resolve_dispatch_effort(
        {"provider": "codex", "model": "fixture", "requested_effort": "high",
         "supported_efforts": support, "risk_policy_floor": floor},
        node_effort="high", max_effort=maximum, role_id="implementation-engineer", routing={})
    allowed = [v for v in support if EFFORT_ORDER.index(floor) <= EFFORT_ORDER.index(v)
               <= EFFORT_ORDER.index(maximum)]
    if not allowed:
        assert result["decision"] == "block"
        assert result["effective_effort"] is None
    else:
        assert result["decision"] == "pass"
        assert result["effective_effort"] in allowed


def test_role_floor_cannot_be_undone_by_dispatch_ceiling():
    result = resolve_dispatch_effort(
        {"provider": "codex", "model": "fixture", "requested_effort": "medium", "supported_efforts": ["low", "medium"]},
        node_effort="medium", max_effort="low", role_id="implementation-engineer",
        routing={"role_bindings": {"implementation-engineer": {"minimum_effort": "medium"}}})
    assert result["decision"] == "block"


def candidates():
    return {role: {"candidate_id": f"fixture:{role}", "provider": "ollama", "model": "fixture",
                  "route_id": "fixture", "live_ready": True, "cloud": False, "fallback_candidates": []}
            for role in ROLE_CATALOG}


def provider(node, prompt, context):
    result = fake_node_executor(node, prompt, context)
    output = result["parsed"]
    if "kpis" in output:
        output["kpis"] = [{"name": "fixture-correctness", "target": 1}]
    if "plan_digest" in output:
        output["plan_digest"] = (json.loads(prompt).get("node_contract") or {}).get("frozen_plan_digest") or "0" * 64
    return result


def test_successful_first_plan_does_not_stop_on_skipped_revisions():
    state = ControlFlowState(graph_id="fixture")
    for count in range(6):
        result = continuation_decision(state=state, node_id=f"optional-{count}", node_required=False,
            result={"status": "skipped", "failure_class": "condition-not-satisfied", "output": {}},
            token_budget=1000, max_model_calls=50, wall_clock_seconds=60)
        assert result["action"] == "continue"
        assert result["identical_failure_count"] == 0


def test_runtime_positive_reaches_writer_with_managed_evidence(tmp_path):
    with patch("iot_ai.agentic.select_candidates", return_value=candidates()):
        result = agentic.run_goal(tmp_path, "Implement a bounded inventory export", execute=True, provider_executor=provider)
    assert result["results"]["implement"]["status"] == "pass"
    assert result["results"]["implement"]["mncg_writer_bind"]["valid"] is True
    assert result["decision"] == "pass"


@pytest.mark.parametrize("phase", ["before-dispatch", "after-dispatch"])
@pytest.mark.parametrize("field", ["revision", "acceptance_criteria", "source_id"])
def test_real_caller_rechecks_current_task(phase, field, tmp_path):
    calls = []
    changed = False
    original_guard = agentic.accepted_plan_allows_implement

    def mutate():
        nonlocal changed
        if changed:
            return
        changed = True
        connection = connect_write(tmp_path)
        try:
            if field == "revision":
                connection.execute("UPDATE tasks SET revision=revision+1")
            elif field == "acceptance_criteria":
                connection.execute("UPDATE tasks SET acceptance_criteria=?", ("Additional independent fixture check",))
            else:
                connection.execute("UPDATE tasks SET source_id=?", ("other-graph",))
            connection.commit()
        finally:
            connection.close()

    def guard(*args, **kwargs):
        result = original_guard(*args, **kwargs)
        if phase == "before-dispatch":
            mutate()
        return result

    def run_provider(node, prompt, context):
        calls.append(node.node_id)
        if node.node_id == "implement" and phase == "after-dispatch":
            mutate()
        return provider(node, prompt, context)

    with patch("iot_ai.agentic.select_candidates", return_value=candidates()), patch("iot_ai.agentic.accepted_plan_allows_implement", side_effect=guard):
        result = agentic.run_goal(tmp_path, "Implement a bounded inventory export", execute=True, provider_executor=run_provider)
    assert changed
    assert result["decision"] != "pass"
    assert result["results"]["implement"]["status"] != "pass"
    assert ("implement" in calls) is (phase == "after-dispatch")


def png(width, height):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    pixels = (b"\x00" + b"\x12\x34\x56" * width) * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


def visual_fixture(root):
    root.mkdir()
    rows = {}
    for name, (width, height) in VIEWPORT_PIXELS.items():
        data = png(width, height)
        (root / f"{name}.png").write_bytes(data)
        rows[name] = {"width": width, "height": height, "screenshot_sha256": hashlib.sha256(data).hexdigest(),
                      "horizontal_overflow": False, "clipping": False}
    receipt = {"schema": "iot-ai.visual-runner-result.v1", "decision": "pass", "run_id": "fixture-run",
               "source_digest": "1" * 64, "runner_digest": "2" * 64, "browser_version": "fixture-only",
               "viewports": rows, "checks": {name: {"executed": True, "passed": True} for name in (
                   "automated_accessibility", "interaction_states", "network_isolation", "page_errors_absent")}}
    raw = json.dumps(receipt).encode()
    (root / "receipt.json").write_bytes(raw)
    return TrustedVisualRun(root, "fixture-run", "1" * 64, hashlib.sha256(raw).hexdigest(), "2" * 64)


def test_complete_synthetic_runner_contract_passes_only_with_trusted_anchor(tmp_path):
    run = visual_fixture(tmp_path / "run")
    result = evaluate_visual_acceptance(visual_task=True, require_browser_acceptance=True, trusted_run=run)
    assert result["decision"] == "pass"
    assert result["visual_quality_proven"] is False
    assert result["full_accessibility_certification"] is False
    assert evaluate_visual_acceptance(visual_task=True, require_browser_acceptance=True,
        tool_available=True, evidence=json.loads((run.artifact_root / "receipt.json").read_text()))["decision"] == "block"


@pytest.mark.parametrize("change", ["file", "truncated", "wrong-dimension", "receipt", "reuse-image", "symlink"])
def test_visual_forgery_fails_closed(change, tmp_path):
    run = visual_fixture(tmp_path / "run")
    image = run.artifact_root / "mobile.png"
    if change == "file":
        image.write_bytes(b"not-an-image" * 20)
    elif change == "truncated":
        image.write_bytes(image.read_bytes()[:-3])
    elif change == "wrong-dimension":
        image.write_bytes(png(1280, 800))
    elif change == "receipt":
        (run.artifact_root / "receipt.json").write_text("{}")
    elif change == "reuse-image":
        image.write_bytes((run.artifact_root / "desktop.png").read_bytes())
    else:
        image.unlink()
        try:
            image.symlink_to(run.artifact_root / "desktop.png")
        except OSError:
            pytest.skip("symlink privilege unavailable")
    assert evaluate_visual_acceptance(visual_task=True, require_browser_acceptance=True, trusted_run=run)["decision"] == "block"


@pytest.mark.parametrize("data", [b"", b"garbage", b"\x89PNG\r\n\x1a\n" + b"0" * 64])
def test_png_magic_prefix_alone_is_not_a_decoded_image(data):
    with pytest.raises(ValueError):
        validate_screenshot(data, 390, 844)


@pytest.mark.parametrize("effort", ["none", "max"])
def test_extended_effort_is_configurable_but_not_unconditionally_authorized(effort):
    from iot_ai.settings_v2 import _as_effort
    assert _as_effort(effort, "effort.default") == effort
    result = resolve_dispatch_effort(
        {"provider": "codex", "model": "fixture", "supported_efforts": ["max"], "requested_effort": effort},
        node_effort=effort, max_effort="medium")
    assert result["decision"] == "block"
    assert result["effective_effort"] is None


@pytest.mark.parametrize("width,height", [(True, 800), (0, 800), (-1, 800), (999999, 800), (2048, 4096)])
def test_image_dimension_budgets_fail_before_decompression(width, height):
    with pytest.raises(ValueError, match="dimension-limit"):
        validate_screenshot(b"", width, height)


@pytest.mark.parametrize("reason,expected", [("entitlement-policy", True), (None, False)])
def test_effort_receipt_preserves_requested_value_with_explained_clamp(reason, expected):
    from iot_ai.runtime_gates import build_effort_receipt
    row = build_effort_receipt(settings_requested="high",
        candidate={"effective_effort": "medium", "requested_effort": "high"},
        dispatch={"decision": "pass", "effective_effort": "medium", "requested_effort": "high", "clamp_reason": reason},
        tool_decision={"effective_effort": "medium"}, adapter_request_effort="medium",
        response={"effort_effective": "medium"})
    assert row["consistent"] is expected
    assert row["configured_effort"] == "high"
    assert row["effective_effort"] == "medium"


def test_public_and_installed_settings_schemas_are_identical():
    root = Path(__file__).resolve().parents[1]
    public = json.loads((root / "schemas/iot-ai-settings-v2.schema.json").read_text())
    installed = json.loads((root / "src/iot_ai/data/iot-ai-settings-v2.schema.json").read_text())
    assert public == installed
    assert "max_distinct_providers" in public["properties"]["routing"]["properties"]
