# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
from __future__ import annotations

import json
import re
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from iot_ai.cli import main
from iot_ai.multicoder import run as multicoder_run
from iot_ai.roles import ROLE_CATALOG
from iot_ai.task_validation import approve, gate, review, skip, status, validation_policy
from iot_ai.tasks import add_work_unit, claim_work_unit, create, show
from iot_ai.paths import db_path
from iot_ai.workspace import connect_read, excel_path

from tests.common import IsolatedHomeTestCase


ROLE_PROVIDER = {
    "requirements-analyst": "claude",
    "domain-architect": "codex",
    "operator-ux-reviewer": "gemini",
    "security-challenger": "grok",
    "eu-ai-act-compliance-reviewer": "ollama",
    "performance-engineer": "gemini",
    "implementation-engineer": "codex",
    "quality-verifier": "codex",
    "plan-synthesizer": "claude",
    "independent-judge": "grok",
}


def _provider_for_role(role_id: str) -> str:
    return ROLE_PROVIDER.get(role_id, "ollama")


def validation_executor(node, prompt, context):
    output = {}
    for field in node.output_schema:
        if field == "verdict":
            output[field] = "PASS"
        elif field == "decision":
            output[field] = "accept"
        elif field == "plan_digest":
            try:
                envelope = json.loads(prompt)
                frozen = str((envelope.get("node_contract") or {}).get("frozen_plan_digest") or "")
            except (TypeError, ValueError, json.JSONDecodeError):
                frozen = ""
            output[field] = frozen if re.fullmatch(r"[0-9a-f]{64}", frozen) else "d" * 64
        elif field in {"use_cases", "test_cases", "failure_cases"}:
            output[field] = [{"id": index + 1, "decision": "pass", "expected": "verified"} for index in range(10)]
        elif field == "tests":
            output[field] = [{"name": "validation-contract", "decision": "pass"}]
        elif field == "kpis":
            output[field] = [{"name": "validation-quality", "target": ">=99%", "measurement": "evidence-bound"}]
        elif field in {"sla", "5w1h", "acceptance", "constraints"}:
            output[field] = {"defined": True, "measurable": True}
        elif field in {
            "findings", "risks", "unknowns", "disagreements", "missing_evidence", "alternatives",
            "dependencies", "threats", "controls", "residual_risk", "benchmarks", "bottlenecks",
            "capacity", "recovery", "journeys", "ia", "widgets", "a11y", "explainability",
            "dissent", "challenged_findings", "accepted_findings", "new_risks", "changed_files",
            "evidence_refs",
        }:
            output[field] = []
        else:
            output[field] = "Evidence-bound task validation result."
    provider = _provider_for_role(node.role_id)
    model = "nemotron-test:cloud" if provider == "ollama" else f"{provider}-test"
    return {
        "status": "pass",
        "output": output,
        "parsed": output,
        "provider": provider,
        "model_requested": model,
        "model_served": model,
        "request_id": f"req-{node.node_id}",
        "input_tokens": 100,
        "cached_tokens": 10,
        "output_tokens": 50,
        "reasoning_tokens": 5,
        "latency_ms": 10,
    }


def candidates():
    result = {}
    for role in ROLE_CATALOG:
        provider = _provider_for_role(role)
        model = "nemotron-test:cloud" if provider == "ollama" else f"{provider}-test"
        result[role] = {
            "candidate_id": f"{provider}:{model}:{role}",
            "provider": provider,
            "model": model,
            "route_id": f"{provider}-route",
            "live_ready": True,
            "cloud": True,
            "receipt": {"authenticated": True, "model_identity_verified": True, "model_served": model},
            "fallback_candidates": [],
        }
    return result


class TaskValidationTests(IsolatedHomeTestCase):
    def make_task(self, *, risk="R2", priority="high", title="Improve dashboard navigation"):
        created = create(
            self.home,
            title,
            "A tester reports confusing menus and asks for a verified improvement.",
            priority,
            risk_class=risk,
            acceptance_criteria="Evidence, security and browser tests pass.",
            tags=["dashboard", "ux"],
        )
        wu = add_work_unit(self.home, created["task_id"], "Implement validated navigation", "implementation")
        return created["task_id"], wu["work_unit_id"]

    def test_claim_defaults_to_non_mutating_validation_question(self):
        task_id, work_unit_id = self.make_task()
        result = claim_work_unit(
            self.home,
            work_unit_id,
            "codex",
            "session-1",
            enforce_validation=True,
        )
        self.assertEqual(result["decision"], "requires-user-confirmation")
        self.assertTrue(result["no_mutation"])
        conn = connect_read(self.home)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM leases").fetchone()[0], 0)
        conn.close()
        self.assertEqual(gate(self.home, task_id)["policy"], "recommended")

    @patch("iot_ai.agentic.select_candidates")
    def test_review_uses_specialists_and_ollama_then_waits_for_user(self, select):
        select.return_value = candidates()
        task_id, _ = self.make_task()
        before = show(self.home, task_id)["task"]
        log = self.home / "current.log"
        log.write_text("navigation renders twice; no secret values", encoding="utf-8")
        result = review(
            self.home,
            task_id,
            context_files=[log],
            provider_executor=validation_executor,
            require_live=True,
        )
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(result["status"], "awaiting-user-approval")
        self.assertTrue(result["ollama_used"])
        self.assertTrue(result["provider_family_gate"])
        self.assertEqual(
            result["substantive_provider_families"],
            ["claude", "codex", "gemini", "grok", "ollama"],
        )
        self.assertEqual(result["unsatisfied_provider_families"], [])
        self.assertRegex(result["proposal"]["plan_digest"], r"^[0-9a-f]{64}$")
        self.assertIn("IOT-AI VALIDATED EXECUTION CONTRACT", result["proposal"]["advanced_execution_prompt"])
        after = show(self.home, task_id)["task"]
        self.assertEqual(before["revision"], after["revision"])
        self.assertEqual(before["description"], after["description"])
        self.assertTrue(excel_path(self.home).is_file())

    @patch("iot_ai.agentic.select_candidates")
    def test_user_approval_applies_revision_and_allows_claim(self, select):
        select.return_value = candidates()
        task_id, work_unit_id = self.make_task()
        reviewed = review(self.home, task_id, provider_executor=validation_executor)
        approved = approve(self.home, task_id, reviewed["validation_id"], "tester@example.invalid", "Use the improved evidence-bound task")
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(gate(self.home, task_id, "claim")["decision"], "pass")
        claimed = claim_work_unit(self.home, work_unit_id, "codex", "session-2", enforce_validation=True)
        self.assertEqual(claimed["decision"], "pass")
        current = show(self.home, task_id)["task"]
        self.assertIn("VALIDATED TECHNICAL BRIEF", current["description"])
        self.assertIn("task-validated", current["tags"])

    @patch("iot_ai.agentic.select_candidates")
    def test_missing_required_provider_family_prevents_accepted_validation(self, select):
        select.return_value = candidates()
        task_id, _ = self.make_task()

        def missing_gemini(node, prompt, context):
            result = validation_executor(node, prompt, context)
            if result.get("provider") == "gemini":
                return {
                    "status": "failed",
                    "failure_class": "empty-output",
                    "output": {},
                    "parsed": {},
                    "provider": "gemini",
                    "model_requested": "gemini-test",
                    "model_served": None,
                    "request_id": f"req-{node.node_id}",
                }
            return result

        reviewed = review(self.home, task_id, provider_executor=missing_gemini)
        self.assertEqual(reviewed["decision"], "needs-work")
        self.assertFalse(reviewed["provider_family_gate"])
        self.assertIn("gemini", reviewed["unsatisfied_provider_families"])
        self.assertFalse(reviewed["execution_authorized"])

    def test_required_validation_skip_is_founder_gated(self):
        task_id, _ = self.make_task(risk="R3", priority="critical", title="Deploy security migration to production")
        self.assertEqual(validation_policy(show(self.home, task_id)["task"]), "required")
        with self.assertRaises(PermissionError):
            skip(self.home, task_id, subject="operator", reason="time pressure")
        result = skip(
            self.home,
            task_id,
            subject="founder",
            reason="Emergency risk acceptance",
            founder_confirm="FOUNDER_SKIP_TASK_VALIDATION",
        )
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(gate(self.home, task_id)["source"], "explicit-risk-acceptance")

    def test_secret_context_blocks_before_provider_calls(self):
        task_id, _ = self.make_task()
        secret = self.home / "secret.log"
        secret.write_text("api_" + "key=" + "xai" + "-" + "THIS_IS_A_REALISTIC_SECRET_VALUE_123456", encoding="utf-8")
        with self.assertRaises(PermissionError):
            review(self.home, task_id, context_files=[secret], provider_executor=validation_executor)
        self.assertEqual(status(self.home, task_id)["count"], 0)

    def test_multicoder_does_not_dispatch_before_validation(self):
        task_id, _ = self.make_task()
        result = multicoder_run(self.home, task_id=task_id, providers=["codex", "ollama@demo:cloud"], quorum=1)
        self.assertEqual(result["decision"], "requires-user-confirmation")
        self.assertEqual(result["provider_calls"], 0)

    def test_cli_execute_and_claim_surface_the_same_gate(self):
        task_id, work_unit_id = self.make_task()
        self.assertEqual(main(["--home", str(self.home), "tasks", "execute", "--task-id", task_id]), 0)
        self.assertEqual(main(["--home", str(self.home), "tasks", "authorize-execution", "--task-id", task_id]), 0)
        self.assertEqual(
            main([
                "--home", str(self.home), "tasks", "claim", "--work-unit-id", work_unit_id,
                "--owner", "codex", "--session-id", "cli-session",
            ]),
            0,
        )
        conn = connect_read(self.home)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM leases").fetchone()[0], 0)
        conn.close()

    def test_cli_tasks_run_is_hybrid_execution_not_gate_only(self):
        """tasks run routes to Multi-Coder; without validation it must not implement."""
        task_id, _ = self.make_task()
        # Capture stdout JSON from emit
        import io, contextlib, json as _json
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main([
                "--home", str(self.home), "tasks", "run",
                "--task-id", task_id, "--mode", "hybrid",
                "--providers", "codex", "--quorum", "1",
            ])
        self.assertEqual(code, 0)
        payload = _json.loads(buf.getvalue())
        self.assertEqual(payload.get("command"), "tasks run")
        self.assertEqual(payload.get("command_semantics"), "hybrid-execution")
        self.assertTrue(payload.get("implements_code"))
        # Still blocked until validation approved — same as multi-coder run
        self.assertEqual(payload.get("decision"), "requires-user-confirmation")
        self.assertEqual(payload.get("provider_calls"), 0)

    def test_natural_execute_registers_task_and_asks_before_provider_use(self):
        result = main([
            "--home", str(self.home), "run", "--goal", "Fix", "the", "dashboard", "menu", "--execute"
        ])
        self.assertEqual(result, 0)
        conn = connect_read(self.home)
        task_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE source='cli-run'").fetchone()[0]
        meeting_count = conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]
        conn.close()
        self.assertEqual(task_count, 1)
        self.assertEqual(meeting_count, 0)

    @patch("iot_ai.agentic.select_candidates")
    def test_stale_validation_cannot_overwrite_changed_task(self, select):
        select.return_value = candidates()
        task_id, _ = self.make_task()
        reviewed = review(self.home, task_id, provider_executor=validation_executor)
        conn = sqlite3.connect(db_path(self.home))
        conn.execute("UPDATE tasks SET revision=revision+1 WHERE id=?", (task_id,))
        conn.commit(); conn.close()
        with self.assertRaises(PermissionError):
            approve(self.home, task_id, reviewed["validation_id"], "user")
        self.assertEqual(status(self.home, task_id)["validations"][0]["status"], "stale")


if __name__ == "__main__":
    unittest.main()
