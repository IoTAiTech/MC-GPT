# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-18
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from iot_ai.change_binding import bind_post_change, prepare_writer_worktree, snapshot_tree
from iot_ai.exec_pin import pin_executable
from iot_ai.exec_pin import test_env as build_test_env
from iot_ai.founder_authority import issue_founder_receipt, persist_founder_key, verify_founder_receipt
from iot_ai.meeting import approve, run as meeting_run, start
from iot_ai.multicoder import run as multicoder_run
from iot_ai.owned_delegate import _node_id
from iot_ai.privacy_class import authoritative_privacy_class, deny_downgrade, max_privacy_class
from tests.common import IsolatedHomeTestCase


def _digest(prompt: str) -> str:
    import re
    match = re.search(r"PLAN_DIGEST:([0-9a-f]{64})", prompt)
    if not match:
        raise AssertionError("plan digest missing")
    return match.group(1)


def _repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test Author"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    (root / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "chore: baseline"], check=True, capture_output=True)
    return root


def writing_delegate(user_home, provider, prompt, stage="consultation", model="auto", **kwargs):
    del user_home, kwargs
    served = model if model not in {"auto", "auto:cloud"} else f"{provider}-served-model"
    if stage in {"plan-final-review", "final-review"}:
        output = json.dumps({"decision": "accept", "plan_digest": _digest(prompt), "findings": [], "dissent": []})
    elif stage == "plan-synthesis":
        output = (
            "Complete evidence-bound implementation plan with architecture, Article 5 and Article 50 controls, "
            "privacy boundaries, deterministic unit integration smoke security stress and rollback tests."
        )
    elif stage in {"implementation", "repair"}:
        marker = "WORKTREE_PATH:"
        if marker in prompt:
            path = Path(prompt.split(marker, 1)[1].split()[0])
            (path / "implemented.txt").write_text("changed by implementer\n", encoding="utf-8")
        output = "Implemented only the frozen plan in the writer worktree."
    else:
        output = (
            f"{stage} independent analysis with scope, dependencies, security risks, privacy controls, "
            "test evidence, alternatives, rollback and unresolved assumptions."
        )
    return {
        "status": "pass",
        "output": output,
        "provider": provider,
        "route_id": f"route-{provider}",
        "request_id": f"req-{provider}-{stage}",
        "model_requested": served,
        "model_served": served,
        "input_tokens": 10,
        "cached_tokens": 0,
        "output_tokens": 10,
        "reasoning_tokens": 0,
        "latency_ms": 5,
        "fallback_used": False,
        "failure_class": None,
    }


def silent_delegate(user_home, provider, prompt, stage="consultation", model="auto", **kwargs):
    if stage in {"implementation", "repair"}:
        result = writing_delegate(user_home, provider, "no-worktree-marker", stage="plan-synthesis", model=model, **kwargs)
        result["output"] = "Claimed implementation without touching the worktree."
        return result
    return writing_delegate(user_home, provider, prompt, stage=stage, model=model, **kwargs)


def meeting_delegate(user_home, provider, prompt, stage="consultation", model="auto", **kwargs):
    del user_home, kwargs
    served = f"{provider}-served-model"
    if "Independently review the frozen meeting plan" in prompt:
        import re
        match = re.search(r"PLAN_DIGEST:([0-9a-f]{64})", prompt)
        digest = match.group(1) if match else ""
        output = json.dumps({"decision": "accept", "plan_digest": digest, "findings": [], "dissent": []})
    else:
        output = (
            f"{stage} independent meeting opinion with architecture, measurable outcomes, "
            "risks, alternatives, missing evidence and an explicit decision for the topic."
        )
    return {
        "status": "pass",
        "output": output,
        "provider": provider,
        "model_requested": served,
        "model_served": served,
        "request_id": f"meet-{provider}-{stage}",
        "route_id": f"route-{provider}",
        "input_tokens": 8,
        "cached_tokens": 0,
        "output_tokens": 8,
        "reasoning_tokens": 0,
        "latency_ms": 4,
        "fallback_used": False,
        "failure_class": None,
    }


class NodeIdTests(unittest.TestCase):
    def test_windows_illegal_colon_is_stripped(self) -> None:
        node = _node_id("implementation", "ollama@model-x:cloud", "run-1")
        self.assertNotIn(":", node)
        self.assertIn("ollama@model-x-cloud", node)


class PrivacyClassTests(unittest.TestCase):
    def test_max_and_downgrade(self) -> None:
        self.assertEqual(max_privacy_class("D1", "D3", "D0"), "D3")
        self.assertEqual(authoritative_privacy_class("D1", blocks=[{"privacy_class": "D2"}]), "D2")
        with self.assertRaises(PermissionError):
            deny_downgrade("D3", "D1")


class ExecPinTests(IsolatedHomeTestCase):
    def test_path_hijack_is_rejected(self) -> None:
        trap = self.home / "trap"
        trap.mkdir()
        fake = trap / "python3"
        fake.write_text("#!/bin/sh\necho hijacked\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        old = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{trap}{os.pathsep}{old}"
        try:
            with self.assertRaises(PermissionError):
                pin_executable("python3", allowed_roots=[Path("/usr/bin")])
        finally:
            os.environ["PATH"] = old

    def test_test_env_drops_secrets(self) -> None:
        os.environ["IOT_AI_FOUNDER_AUTHORITY_KEY"] = "x" * 40
        os.environ["OPENAI_API_KEY"] = "sk-" + "test-not-for-child"
        env = build_test_env()
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("IOT_AI_FOUNDER_AUTHORITY_KEY", env)


class ChangeBindingTests(IsolatedHomeTestCase):
    def test_no_op_is_rejected(self) -> None:
        repo = _repo(self.home / "repo")
        writer = prepare_writer_worktree(self.home, repo, "codex", "bind-noop")
        self.assertEqual(writer["decision"], "pass")
        post = snapshot_tree(Path(writer["path"]))
        bound = bind_post_change(
            base=writer["base"],
            post=post,
            write_scope=[writer["path"]],
            mutation_required=True,
        )
        self.assertEqual(bound["decision"], "block")
        self.assertEqual(bound["reason"], "no-op-rejected")

    @patch("iot_ai.multicoder.delegate", side_effect=writing_delegate)
    def test_multicoder_requires_worktree_diff(self, _mock) -> None:
        repo = _repo(self.home / "workspace")
        result = multicoder_run(
            self.home,
            task="Improve a developer tool without processing personal data",
            providers=["codex", "grok"],
            quorum=2,
            test_argv=[sys.executable, "-c", "print('1 passed')"],
            cwd=repo,
        )
        self.assertEqual(result["decision"], "approve")
        self.assertEqual(result["change_binding"]["decision"], "pass")
        self.assertTrue(result["change_binding"]["in_scope"])

    @patch("iot_ai.multicoder.delegate", side_effect=silent_delegate)
    def test_multicoder_rejects_text_only_no_op(self, _mock) -> None:
        repo = _repo(self.home / "workspace")
        result = multicoder_run(
            self.home,
            task="Improve a developer tool without processing personal data",
            providers=["codex", "grok"],
            quorum=2,
            test_argv=[sys.executable, "-c", "print('1 passed')"],
            cwd=repo,
        )
        self.assertEqual(result["decision"], "needs-work")
        self.assertEqual(result["change_binding"]["reason"], "no-op-rejected")


class FounderAndMeetingTests(IsolatedHomeTestCase):
    def test_unsigned_approve_fails_closed(self) -> None:
        persist_founder_key(self.home, b"f" * 32)
        with self.assertRaises(PermissionError):
            verify_founder_receipt(
                self.home,
                None,
                audience="meeting.approve",
                subject_id="meeting-x",
                digest="a" * 64,
            )

    @patch("iot_ai.meeting.delegate", side_effect=meeting_delegate)
    def test_signed_one_use_receipt_and_cas(self, delegate_mock) -> None:
        persist_founder_key(self.home, b"k" * 32)
        created = start(self.home, "Review release architecture", ["codex", "grok"], quorum=2, privacy_class="D1")
        first = meeting_run(self.home, created["meeting_id"])
        self.assertEqual(first["meeting_status"], "awaiting-user-decision")
        second = meeting_run(self.home, created["meeting_id"])
        self.assertEqual(second["meeting_status"], "awaiting-user-decision")
        self.assertLessEqual(delegate_mock.call_count, 20)
        digest = first["meeting"]["consultation_sha256"]
        receipt = issue_founder_receipt(
            self.home, audience="meeting.approve", subject_id=created["meeting_id"], digest=digest
        )
        approved = approve(self.home, created["meeting_id"], founder_receipt=receipt)
        self.assertTrue(approved["founder_approval"])
        with self.assertRaises(PermissionError):
            verify_founder_receipt(
                self.home,
                receipt,
                audience="meeting.approve",
                subject_id=created["meeting_id"],
                digest=digest,
            )


class AuditChangeBindingTests(IsolatedHomeTestCase):
    def test_governed_submit_requires_change_binding(self) -> None:
        from iot_ai.audit import audit_task
        from iot_ai.tasks import create

        created = create(
            self.home,
            "Governed mutation",
            "Improve a developer tool without processing personal data",
            "high",
            risk_class="R2",
        )
        result = audit_task(self.home, created["task_id"], record=False)
        self.assertEqual(result["decision"], "needs-work")
        self.assertFalse(result["gates"]["change_binding_bound"])
        self.assertIn("change-binding-missing", result["findings"])


class ReleaseWorkflowCriticalTests(unittest.TestCase):
    def test_release_workflow_does_not_interpolate_or_clobber(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        run_chunks = []
        collecting = False
        current: list[str] = []
        for line in text.splitlines():
            if line.strip() == "run: |":
                collecting = True
                current = []
                continue
            if collecting:
                if line.startswith("      - ") or (line and not line.startswith(" ")):
                    run_chunks.append("\n".join(current))
                    collecting = False
                else:
                    current.append(line)
        if collecting:
            run_chunks.append("\n".join(current))
        joined = "\n".join(run_chunks)
        self.assertNotIn("${{ inputs.", joined)
        self.assertNotIn("--clobber", text)
        self.assertIn("git checkout --detach", text)
        self.assertIn("RAW_TAG: ${{ inputs.tag }}", text)


class ExternalBlockerTests(IsolatedHomeTestCase):
    def test_missing_issuer_anchor_is_memoized_without_preflight(self) -> None:
        from iot_ai.external_blocker import BLOCKER_ID, ISSUER_ANCHOR, evaluate_pmd_schema_recovery

        first = evaluate_pmd_schema_recovery(self.home)
        second = evaluate_pmd_schema_recovery(self.home)
        self.assertEqual(first["blocker_id"], BLOCKER_ID)
        self.assertEqual(first["result"], "PMD_RECOVERY_EXTERNAL_BLOCKER")
        self.assertEqual(first["missing_artifact"], str(ISSUER_ANCHOR))
        self.assertFalse(first["security_vulnerability"])
        self.assertFalse(first["normal_preflight_retried"])
        self.assertTrue(second["memoized"])
        self.assertFalse(second["normal_preflight_retried"])
        self.assertFalse(second["state_changed"])
        self.assertEqual(first["authority_bundle_digest"], second["authority_bundle_digest"])


class PlatformContractTests(unittest.TestCase):
    def test_windows_installer_parameter_and_version_lockstep(self) -> None:
        from iot_ai.suite_version import SUITE_VERSION
        root = Path(__file__).resolve().parents[1]
        script = (root / "installers" / "Install-IotAiSuite.ps1").read_text(encoding="utf-8")
        bootstrap = (root / "npm" / "bin" / "iot-ai-bootstrap.mjs").read_text(encoding="utf-8")
        self.assertIn("[string]$HomePath", script)
        self.assertNotIn("[string]$Home =", script)
        pep440 = SUITE_VERSION.replace("-beta.", "b")
        self.assertIn(f'iot-ai-coder-suite=={pep440}', script)
        self.assertIn(SUITE_VERSION, script)
        self.assertIn(SUITE_VERSION, bootstrap)
        ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("windows-latest", ci)
        self.assertIn("macos-latest", ci)


if __name__ == "__main__":
    unittest.main()
