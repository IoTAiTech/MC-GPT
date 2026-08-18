# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from iot_ai.acceptance_scorecard import criteria_digest, validate_scorecard
from iot_ai.agent_seats import build_agent_envelope, delegate_agent_seat, validate_agent_reply
from iot_ai.autopilot import _schedule_waves
from iot_ai.conversation_state import empty_state
from iot_ai.intent_router import compile_intent
from iot_ai.meeting_integration import register_agent_seat
from iot_ai.task_backends import TaskRecord
from iot_ai.tasks import complete, create, record_progress, show, submit_task
from iot_ai.workspace import connect_write
from tests.common import IsolatedHomeTestCase


class NaturalIntentTests:
    def test_execution_verbs_default_to_terminal_closed_loop(self):
        intent = compile_intent("finish these tasks through to the end")
        assert intent["execution"]["requested"] is True
        assert intent["execution"]["until_terminal"] is True
        assert intent["execution"]["meeting_policy"] == "automatic"
        assert intent["execution"]["multi_coder_policy"] == "mandatory-at-gates"

    def test_plan_only_stays_non_mutating(self):
        intent = compile_intent("only inspect the plan and do not execute")
        assert intent["execution"]["requested"] is False
        assert intent["action"] == "plan"

    def test_continue_resolves_previous_task_set(self):
        state = empty_state("c1")
        state["selected_task_ids"] = ["task-abc", "task-def"]
        intent = compile_intent("continue and finish the rest", conversation_state=state, conversation_id="c1")
        assert intent["scope"]["task_ids"] == ["task-abc", "task-def"]
        assert intent["action"] == "continue"

    def test_all_tasks_is_a_broad_selection_not_a_new_task_query(self):
        intent = compile_intent("finish all tasks until the end")
        assert intent["scope"]["all_tasks"] is True
        assert intent["scope"]["task_query"] is None
        assert intent["scope"]["create_if_none"] is False
        assert intent["execution"]["until_terminal"] is True


class ScorecardTests:
    def test_overlap_and_stale_verification_are_blocked(self):
        digest = criteria_digest(["a", "b", "c"])
        result = validate_scorecard(
            {
                "criteria_total": 3,
                "pass": [1, 2],
                "partial": [1, 3],
                "fail": [],
                "criteria_passed_honest": 2,
                "current_result": "partial work",
                "verification": {"trusted": True, "decision": "pass", "revision": 3, "criteria_digest": digest},
            },
            current_revision=4,
            expected_criteria_digest=digest,
        )
        assert result["decision"] == "block"
        assert any("criterion-status-overlap" in item for item in result["errors"])
        assert any("stale-revision" in item for item in result["errors"])

    def test_full_current_trusted_scorecard_passes(self):
        digest = criteria_digest(["a", "b"])
        result = validate_scorecard(
            {
                "criteria_total": 2,
                "pass": [1, 2],
                "partial": [],
                "fail": [],
                "criteria_passed_honest": 2,
                "current_result": "all criteria proven",
                "verification": {"trusted": True, "decision": "pass", "revision": 7, "criteria_digest": digest},
            },
            current_revision=7,
            expected_criteria_digest=digest,
        )
        assert result["decision"] == "pass"
        assert result["can_submit"] is True


class SchedulerTests:
    def test_wip_waves_eventually_schedule_every_task(self):
        records = [
            TaskRecord(f"task-{index}", "suite", "suite", "ready", "critical" if index < 7 else "high", f"T{index}")
            for index in range(11)
        ]
        waves = _schedule_waves(records, 6)
        flattened = [row.task_id for wave in waves for row in wave]
        assert sorted(flattened) == sorted(row.task_id for row in records)
        assert all(len(wave) <= 6 for wave in waves)
        assert len(waves) >= 2


class LifecycleTruthTests(IsolatedHomeTestCase):
    def _task(self) -> str:
        return create(
            self.home,
            "Truthful task",
            "Test lifecycle truth",
            "high",
            risk_class="R2",
            acceptance_criteria="1. test\n2. evidence",
        )["task_id"]

    def test_progress_does_not_reopen_awaiting_founder(self):
        task_id = self._task()
        conn = connect_write(self.home)
        conn.execute("UPDATE tasks SET status='awaiting_founder' WHERE id=?", (task_id,))
        conn.commit(); conn.close()
        result = record_progress(self.home, task_id, "observe", 50, "heartbeat only")
        assert result["status"] == "awaiting_founder"
        assert show(self.home, task_id)["task"]["status"] == "awaiting_founder"

    def test_failed_audit_never_enters_founder_queue(self):
        task_id = self._task()
        result = submit_task(self.home, task_id, result_summary="Not enough evidence")
        assert result["decision"] == "needs-work"
        assert result["founder_queue_entered"] is False
        assert show(self.home, task_id)["task"]["status"] == "needs-work"

    def test_legacy_complete_cannot_bypass_founder_decision(self):
        task_id = self._task()
        before = show(self.home, task_id)["task"]["status"]
        result = complete(self.home, task_id, "self-approved")
        assert result["decision"] == "block"
        assert result["reason"] == "founder-final-decision-required"
        assert result["mutation_performed"] is False
        assert show(self.home, task_id)["task"]["status"] == before

    def test_agent_semantic_capability_is_enforced_before_network(self):
        register_agent_seat(
            self.home,
            surface="pmd",
            agent_id="reviewer",
            display_name="Reviewer",
            model_binding="local-model",
            endpoint_ref="http://127.0.0.1:9999/consult",
            capabilities=["meeting.review"],
            reachable=True,
        )
        result = delegate_agent_seat(
            self.home, "agent:pmd/reviewer", "Give an opinion", "meeting-opinion",
            "meeting-1", "opinion-provider", 5,
        )
        assert result["failure_class"] == "semantic_capability_mismatch"
        assert result["required_capability"] == "meeting.opinion"

    def test_agent_reply_attests_required_capability(self):
        envelope = build_agent_envelope(
            "agent:pmd/reviewer", "Review", "meeting-final-review", "meeting-1", "reviewer", 30
        )
        text = "Evidence-backed review with an explicit decision."
        os.environ["IOT_AI_AGENT_REPLY_KEY"] = "K" * 32
        from iot_ai.agent_seats import agent_reply_signature
        signature = agent_reply_signature(envelope, text)
        base = {
            "status": "pass",
            "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "model_served": "local-model",
            "envelope_id": envelope["envelope_id"],
            "envelope_sha256": envelope["envelope_sha256"],
            "writes_performed": 0,
            "independent_signature": signature,
        }
        missing = validate_agent_reply(envelope, dict(base))
        assert missing["failure_class"] == "semantic_capability_unattested"
        passed = validate_agent_reply(envelope, {**base, "capability": "meeting.review"})
        assert passed["status"] == "pass"
