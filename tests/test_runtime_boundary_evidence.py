# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-04
"""Synthetic positive and negative contracts; no external providers or credentials."""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from unittest.mock import patch

import pytest

from iot_ai.agentic import run_goal
from iot_ai.roles import ROLE_CATALOG
from iot_ai.runtime_gates import (accepted_plan_allows_implement, bind_implementation_to_accepted_plan,
    evaluate_minimum_change_gate, plan_output_digest, resolve_dispatch_effort)
from iot_ai.settings_v2 import EFFORT_ORDER
from iot_ai.visual_acceptance import evaluate_visual_acceptance
from iot_ai.visual_evidence import VIEWPORTS, VisualEvidenceHandle, capture_visual_run, validate_png, verify_visual_run
from iot_ai.workspace import connect_read, connect_write, one
from tests.common import IsolatedHomeTestCase
from tests.host_test_fixture import host_runner
from tests.test_agentic import fake_node_executor
from tests.test_runtime_enforcement_corrective import passing_assessment


def authority():
    return dict(goal="Export inventory", task_id="task-inventory", revision=7, risk_class="R2",
                acceptance="All acceptance tests pass.", context_digest="a" * 64)


def accepted():
    return {"decision": "accept", "mncg": evaluate_minimum_change_gate(
        {"minimum_change_assessment": passing_assessment()}, **authority())}


@pytest.mark.parametrize("field,value", [("task_id", "task-other"), ("revision", 8), ("revision", True),
    ("acceptance", "New acceptance"), ("risk_class", "R3"), ("context_digest", "b" * 64),
    ("goal", "Other goal"), ("context_digest", None)])
def test_current_authority_cannot_be_replaced(field, value):
    result = bind_implementation_to_accepted_plan({"minimum_change_assessment": passing_assessment()},
        accepted(), **(authority() | {field: value}))
    assert result["valid"] is False


def test_unchanged_reviewed_identity_can_continue():
    plan = accepted()
    assert accepted_plan_allows_implement(plan, persisted_output_sha256=plan_output_digest(plan), require_persistence=True)["valid"]
    assert bind_implementation_to_accepted_plan({"minimum_change_assessment": passing_assessment()}, plan, **authority())["valid"]


@pytest.mark.parametrize("forged", [None, {}, {"decision": "accept", "mncg": {"valid": True}},
    {"decision": "accept", "mncg": {"valid": True, "assessment_sha256": "a" * 64}}])
def test_boolean_or_hash_only_guard_cannot_grant_authority(forged):
    assert accepted_plan_allows_implement(forged)["valid"] is False


def test_persisted_digest_is_mandatory_at_runtime():
    plan = accepted()
    assert not accepted_plan_allows_implement(plan, require_persistence=True)["valid"]
    assert not accepted_plan_allows_implement(plan, persisted_output_sha256="0" * 64, require_persistence=True)["valid"]


@pytest.mark.parametrize("field", ["rung_assessments", "verification_plan", "controls_preserved", "estimated_change_surface"])
def test_same_rung_changed_strategy_requires_new_review(field):
    plan = accepted()
    proposed = passing_assessment()
    if field == "verification_plan":
        proposed[field] = ["Run a different test suite"]
    elif field == "estimated_change_surface":
        proposed[field]["files"] = 2
    elif field == "rung_assessments":
        proposed[field]["necessity"]["evidence_refs"] = ["evidence:different"]
    else:
        proposed[field] = proposed[field][:-1]
    assert not bind_implementation_to_accepted_plan({"minimum_change_assessment": proposed}, plan, **authority())["valid"]


@pytest.mark.parametrize("supported", [[item] for item in EFFORT_ORDER] + [[], ["unknown"]])
@pytest.mark.parametrize("ceiling", ["none", "low", "medium", "high", "xhigh", "max"])
def test_no_effort_can_escape_provider_or_ceiling(supported, ceiling):
    row = {"requested_effort": "high", "provider": "codex", "model": "fixture", "supported_efforts": supported}
    result = resolve_dispatch_effort(row, node_effort="high", max_effort=ceiling)
    if result["decision"] == "pass":
        assert result["effective_effort"] in supported
        assert EFFORT_ORDER.index(result["effective_effort"]) <= EFFORT_ORDER.index(ceiling)
    if not any(x in EFFORT_ORDER and EFFORT_ORDER.index(x) <= EFFORT_ORDER.index(ceiling) for x in supported):
        assert result["decision"] == "block"


def test_role_floor_and_entitlement_conflict_blocks():
    result = resolve_dispatch_effort({"requested_effort": "high", "supported_efforts": ["low", "high"]},
        node_effort="high", max_effort="low", role_id="implementation-engineer",
        routing={"role_bindings": {"implementation-engineer": {"minimum_effort": "high"}}})
    assert result["decision"] == "block"


def png(width, height):
    def chunk(kind, content):
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", zlib.crc32(kind + content) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress((b"\0" + b"\xff" * (width * 3)) * height)) + chunk(b"IEND", b"")


def simulated_capture(root, viewports):
    """Only a deterministic adapter fixture, not evidence of a browser run."""
    for name, (width, height) in viewports.items():
        (root / f"{name}.png").write_bytes(png(width, height))
        (root / f"{name}.json").write_text(json.dumps({"viewport": {"width": width, "height": height},
            "overflow_count": 0, "clipping_count": 0,
            "accessibility": {"engine": "synthetic-contract-fixture", "checks_run": 3, "violations": []},
            "states": {"loading": "pass", "empty": "pass", "error": "pass"}}))
    return {"browser_version": "synthetic-contract-fixture"}


def handle(tmp_path):
    return capture_visual_run(evidence_root=tmp_path, run_id="run-fixture", source_digest=lambda: "a" * 64, capture=simulated_capture)


def test_non_image_and_valid_image_without_runner_have_no_authority(tmp_path):
    arbitrary = tmp_path / "not-image.bin"
    arbitrary.write_bytes(b"not browser output" * 30)
    evidence = {"screenshot_paths": {name: str(arbitrary) for name in VIEWPORTS}, "accessibility": True}
    result = evaluate_visual_acceptance(visual_task=True, require_browser_acceptance=True, tool_available=True, evidence=evidence)
    assert result["decision"] != "pass"
    assert not result["visual_acceptance_claim"]


def test_trusted_adapter_contract_passes_but_does_not_certify_quality(tmp_path):
    proof = handle(tmp_path)
    result = verify_visual_run(proof, run_id="run-fixture", source_sha256="a" * 64)
    assert result["decision"] == "pass"
    assert result["visual_quality_proven"] is False


@pytest.mark.parametrize("tamper", ["source", "run", "image", "report", "receipt", "clone", "symlink"])
def test_visual_provenance_and_rehash_fail_closed(tmp_path, tamper):
    proof = handle(tmp_path)
    run, source = "run-fixture", "a" * 64
    if tamper == "source": source = "b" * 64
    if tamper == "run": run = "other-run"
    if tamper == "image": (proof.root / "mobile.png").write_bytes(png(10, 10))
    if tamper == "report": (proof.root / "mobile.json").write_text('{"accessibility": true}')
    if tamper == "receipt": (proof.root / "receipt.json").write_text('{}')
    if tamper == "clone": proof = VisualEvidenceHandle(proof.root, proof.run_id, proof.source_sha256, proof.receipt_sha256)
    if tamper == "symlink":
        path = proof.root / "mobile.png"
        other = tmp_path / "other.png"
        other.write_bytes(path.read_bytes()); path.unlink()
        try: path.symlink_to(other)
        except OSError: pytest.skip("Platform does not permit symlink creation")
    assert verify_visual_run(proof, run_id=run, source_sha256=source)["decision"] == "block"


@pytest.mark.parametrize("data", [b"", b"x" * 200, b"\x89PNG\r\n\x1a\n" + b"x" * 64, png(20, 20), png(390, 844)[:-3], png(390, 844) + b"trailing"], ids=["empty", "not-png", "header-only", "wrong-dimensions", "truncated", "trailing"])
def test_png_format_dimensions_and_completeness(data):
    with pytest.raises((ValueError, zlib.error)):
        validate_png(data, VIEWPORTS["mobile"])


class RuntimeCallerTests(IsolatedHomeTestCase):
    def exercise(self, mutate=None):
        calls = []
        def provider(node, prompt, context):
            calls.append(node.node_id)
            result = fake_node_executor(node, prompt, context)
            output = result["parsed"]
            if "kpis" in output: output["kpis"] = [{"name": "acceptance", "target": "pass"}]
            if "plan_digest" in output:
                frozen = json.loads(prompt).get("node_contract", {}).get("frozen_plan_digest")
                if frozen: output["plan_digest"] = frozen
            if mutate and node.node_id == "plan-synthesis":
                c = connect_write(self.home)
                try:
                    c.execute(f"UPDATE tasks SET {mutate}")
                    c.commit()
                finally: c.close()
            return result
        candidates = {r: {"candidate_id": f"codex:fixture:{r}", "provider": "codex", "model": "fixture",
            "live_ready": True, "cloud": True, "fallback_candidates": []} for r in ROLE_CATALOG}
        with patch("iot_ai.agentic.select_candidates", return_value=candidates):
            result = run_goal(self.home, "Implement inventory export with deterministic checks", execute=True,
                              provider_executor=provider, profile="balanced", test_runner=host_runner(self.home))
        return result, calls

    def test_instantiated_graph_uses_persisted_plan_then_dispatches(self):
        result, calls = self.exercise()
        self.assertIn("implement", calls)
        self.assertEqual(result["results"]["implement"]["status"], "pass")
        self.assertEqual(result["decision"], "pass")

    def test_current_revision_change_never_dispatches_writer(self):
        result, calls = self.exercise("revision=revision+1")
        self.assertNotIn("implement", calls)
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["failure_class"], "current-task-authority-changed")

    def test_unversioned_acceptance_change_is_not_overwritten_by_finish(self):
        result, calls = self.exercise("acceptance_criteria='Concurrent operator criteria',status='paused'")
        self.assertNotIn("implement", calls)
        c = connect_read(self.home)
        try: row = one(c, "SELECT * FROM tasks WHERE id=?", (result["task_id"],))
        finally: c.close()
        self.assertEqual(row["status"], "paused")
        self.assertEqual(row["acceptance_criteria"], "Concurrent operator criteria")


def test_requested_effort_is_not_confused_with_applied_effort():
    from iot_ai.runtime_gates import build_effort_receipt
    receipt = build_effort_receipt(settings_requested="high",
        candidate={"requested_effort": "high", "effective_effort": "medium"},
        dispatch={"effective_effort": "medium"}, tool_decision={"effective_effort": "medium"},
        adapter_request_effort="medium", response={"effort_effective": "medium"})
    assert receipt["consistent"] is True
    missing = build_effort_receipt(settings_requested="high",
        candidate={"effective_effort": "medium"}, dispatch={"effective_effort": "medium"},
        tool_decision={"effective_effort": "medium"}, adapter_request_effort=None,
        response={"effort_effective": "medium"})
    assert missing["consistent"] is False


def test_unknown_ceiling_fails_closed():
    assert resolve_dispatch_effort({"effective_effort": "medium"}, node_effort="medium", max_effort="unknown")["decision"] == "block"


def test_normal_skip_does_not_disable_real_failure_budget():
    from iot_ai.control_flow import ControlFlowState, continuation_decision
    state = ControlFlowState(graph_id="test")
    common = dict(state=state, node_id="optional", node_required=False, token_budget=100,
                  max_model_calls=10, wall_clock_seconds=60)
    for _ in range(5):
        result = continuation_decision(**common, result={"status": "skipped", "failure_class": "condition-not-satisfied"})
        assert result["action"] == "continue"
    for _ in range(2):
        result = continuation_decision(**common, result={"status": "failed", "failure_class": "timeout"})
    assert result["action"] == "stop"
    assert result["reason"] == "repeated-identical-failure"
