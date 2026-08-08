# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from iot_ai.tasks import (
    add_evidence,
    add_work_unit,
    claim_work_unit,
    create,
    heartbeat,
    list_closed,
    list_open,
    record_progress,
    release_lease,
    show,
    solve_all_plan,
    submit_task,
    workspace_status,
)
from iot_ai.workspace import excel_manifest_path, excel_path, verify_event_chain

from tests.common import IsolatedHomeTestCase


class TaskProjectionTests(IsolatedHomeTestCase):
    def _task_and_lease(self):
        task = create(self.home, "Implement public feature", "Evidence-bound task", "high", "codex", risk_class="R2")
        wu = add_work_unit(self.home, task["task_id"], "Implement", "implementation", ["src"], ["src/module.py"])
        lease = claim_work_unit(self.home, wu["work_unit_id"], "codex", "session-1", 3600)
        return task, wu, lease

    def test_create_and_show(self) -> None:
        task = create(self.home, "Task A", "Description", "normal", None)
        value = show(self.home, task["task_id"])
        self.assertEqual(value["task"]["title"], "Task A")
        self.assertEqual(value["task"]["source"], "local")

    def test_claim_requires_work_unit(self) -> None:
        task, wu, lease = self._task_and_lease()
        self.assertEqual(lease["work_unit_id"], wu["work_unit_id"])
        self.assertTrue(lease["lease_token"])

    def test_heartbeat_and_release(self) -> None:
        task, wu, lease = self._task_and_lease()
        self.assertEqual(heartbeat(self.home, lease["lease_id"], lease["lease_token"])["decision"], "pass")
        self.assertEqual(release_lease(self.home, lease["lease_id"], lease["lease_token"])["status"], "released")

    def test_invalid_lease_token_rejected(self) -> None:
        task, wu, lease = self._task_and_lease()
        with self.assertRaises(PermissionError):
            heartbeat(self.home, lease["lease_id"], "wrong")

    def test_progress_and_evidence(self) -> None:
        task, wu, lease = self._task_and_lease()
        progress = record_progress(self.home, task["task_id"], "implementation", 50, "Half complete", wu["work_unit_id"])
        self.assertEqual(progress["percent"], 50)
        artifact = self.home / "evidence.json"
        artifact.write_text('{"decision":"pass"}', encoding="utf-8")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        evidence = add_evidence(self.home, task["task_id"], artifact, digest, work_unit_id=wu["work_unit_id"], passed=True)
        self.assertEqual(evidence["artifact_sha256"], digest)

    def test_submit_releases_lease_and_exports_excel(self) -> None:
        task, wu, lease = self._task_and_lease()
        artifact = self.home / "test.txt"
        artifact.write_text("tests passed", encoding="utf-8")
        add_evidence(self.home, task["task_id"], artifact, kind="test", work_unit_id=wu["work_unit_id"], exit_code=0, passed=True)
        result = submit_task(self.home, task["task_id"], wu["work_unit_id"], lease["lease_id"], lease["lease_token"])
        # A bare evidence file is not a full R2 governance packet. The audit must
        # keep the task in needs-work rather than polluting the founder queue.
        self.assertEqual(result["status"], "needs-work")
        self.assertFalse(result["founder_queue_entered"])
        details = show(self.home, task["task_id"])
        self.assertTrue(all(row["status"] != "active" for row in details["task"]["leases"]))
        self.assertTrue(excel_path(self.home).is_file())
        self.assertTrue(excel_manifest_path(self.home).is_file())

    def test_event_chain_is_valid(self) -> None:
        self._task_and_lease()
        self.assertEqual(verify_event_chain(self.home)["decision"], "pass")

    def test_open_closed_and_solve_all(self) -> None:
        create(self.home, "PMD public task", "related to PMD", "high", None)
        create(self.home, "Critical task", "critical", "critical", None)
        open_rows = list_open(self.home, query="PMD")
        self.assertEqual(len(open_rows), 1)
        plan = solve_all_plan(self.home, "PMD")
        self.assertEqual(plan["eligible_count"], 1)
        critical = solve_all_plan(self.home, "Critical")
        self.assertEqual(critical["eligible_count"], 0)
        self.assertEqual(list_closed(self.home), [])

    def test_workspace_status(self) -> None:
        create(self.home, "Status task", "desc", "normal", None)
        result = workspace_status(self.home)
        self.assertEqual(result["integrity"], "ok")
        self.assertGreater(result["counts"]["tasks"], 0)


if __name__ == "__main__":
    unittest.main()
