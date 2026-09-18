# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
"""Synthetic local plumbing tests; not live provider or release qualification."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

from iot_ai import multicoder, tasks
from iot_ai.audit import audit_task
from iot_ai.change_binding import snapshot_tree, tree_digest
from iot_ai.completion_evidence import latest_start
from iot_ai.telemetry import record
from iot_ai.util import utc_now
from iot_ai.workspace import connect_read, connect_write, one, rows, verify_event_chain, new_id
from tests.common import IsolatedHomeTestCase
from tests.test_multicoder_governance import successful_delegate
from tests.test_remaining_closeout import _repo


class TestPublicCompletion(IsolatedHomeTestCase):
    def setup_task(self):
        self.repo = _repo(self.home / "repo")
        self.task_id = tasks.create(self.home, "Synthetic tool change", "Improve the local developer tool",
                                    risk_class="R2", acceptance_criteria="implemented.txt contains implemented") ["task_id"]
        tasks.add_work_unit(self.home, self.task_id, "Synthetic implementation", "implementation",
                            read_scope=[str(self.repo)], write_scope=[str(self.repo)])
        now = utc_now()
        conn = connect_write(self.home)
        conn.execute("INSERT INTO meetings(id,task_id,topic,depth,effort,status,requested_seats,substantive_seats,quorum,rounds,final_decision,user_approved,consultation_sha256,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     ("synthetic-meeting", self.task_id, "Synthetic fixture approval", "bounded", "low", "approved", 2, 2, 2, 1, "accept", 1, "a" * 64, now, now))
        conn.execute("INSERT INTO meeting_kpis VALUES(?,?,?,?,?,?,?)", ("synthetic-kpi", "synthetic-meeting", "Fixture acceptance", "pass", "child assertion", 1, now))
        for kind in ("use", "test", "failure"):
            for index in range(10):
                conn.execute("INSERT INTO meeting_cases VALUES(?,?,?,?,?,?,?,?,?)",
                             (f"synthetic-{kind}-{index}", "synthetic-meeting", kind, index, "Fixture", "Plumbing only", "pass", 1, now))
        conn.commit()
        conn.close()
        self.profile = self.home / "profile.json"
        # Eight declarations exercise policy plumbing, not eight coverage claims.
        self.profile.write_text(json.dumps({"tiers": [{"name": tier, "argv": [sys.executable, "-c",
            "from pathlib import Path; assert Path('implemented.txt').read_text() == 'implemented\\n'"],
            "timeout_seconds": 10} for tier in multicoder.TEST_TIERS]}))

    def execute(self, *, delegate_hook=None, result_hook=None, submit_hook=None, export_hook=None,
                intake_hook=None, export_failure_phase=None):
        self.setup_task()
        if intake_hook:
            intake_hook()
        real_submit = tasks.submit_task
        real_export = tasks.export_workspace
        def delegate(home, provider, prompt, stage="consultation", model="auto", **kwargs):
            result = successful_delegate(home, provider, prompt, stage, model, **kwargs)
            if result_hook:
                result_hook(stage,result)
            result["contribution_id"] = record(home, {**result, "run_id": kwargs["run_id"], "stage": stage})
            if delegate_hook:
                delegate_hook(stage, prompt)
            return result
        def submit(*args, **kwargs):
            if submit_hook:
                submit_hook()
            return real_submit(*args, **kwargs)
        exports=0
        def export(*args, **kwargs):
            nonlocal exports
            exports+=1
            if exports==export_failure_phase:
                raise OSError("synthetic projection failure")
            result = real_export(*args, **kwargs)
            if export_hook:
                export_hook()
            return result
        with patch("iot_ai.multicoder.delegate", side_effect=delegate):
            if not submit_hook and not export_hook and not export_failure_phase:
                return multicoder.run(self.home, task_id=self.task_id, providers=["codex", "grok"],
                                      quorum=2, test_profile=self.profile, cwd=self.repo)
            with patch("iot_ai.multicoder.submit_task", side_effect=submit), patch("iot_ai.tasks.export_workspace", side_effect=export):
                return multicoder.run(self.home, task_id=self.task_id, providers=["codex", "grok"],
                                      quorum=2, test_profile=self.profile, cwd=self.repo)

    def test_task_backed_happy_path(self):
        result = self.execute()
        self.assertEqual(result["submission"]["status"], "awaiting_founder", result)
        self.assertTrue(result["submission"]["audit"]["gates"]["completion_evidence_bound"])
        conn = connect_read(self.home)
        binding = latest_start(conn, self.task_id)
        task = one(conn, "SELECT * FROM tasks WHERE id=?", (self.task_id,))
        self.assertEqual(task["revision"], binding["task_revision"] + 2)
        self.assertEqual(len(rows(conn, "SELECT * FROM test_results WHERE task_id=?", (self.task_id,))), 8)
        self.assertFalse(rows(conn, "SELECT * FROM leases WHERE task_id=? AND status='active'", (self.task_id,)))
        conn.close()
        self.assertEqual(verify_event_chain(self.home)["decision"], "pass")
        self.assertEqual(audit_task(self.home,self.task_id,record=False)["decision"],"approve_technical")

    def test_failed_transport_cannot_accept_final_review(self):
        def mutate(stage,result):
            if stage=="final-review":
                result["model_served"]=None
        result=self.execute(result_hook=mutate)
        self.assertEqual(result["decision"],"needs-work")
        self.assertFalse(result["final_reviews"][0]["review"]["accepted"])

    def test_failed_transport_cannot_accept_plan_review(self):
        def mutate(stage,result):
            if stage=="plan-final-review":
                result["model_served"]=None
        result=self.execute(result_hook=mutate)
        self.assertEqual(result["decision"],"needs-work")
        self.assertEqual(result["reason"],"required-seats-did-not-accept-same-plan-digest")
        self.assertFalse(result["execution_authorized"])

    def test_cancelled_intake_never_calls_providers(self):
        def cancel():
            conn=connect_write(self.home)
            conn.execute("UPDATE tasks SET status='cancelled',revision=revision+1 WHERE id=?",(self.task_id,))
            conn.commit()
            conn.close()
        result=self.execute(intake_hook=cancel)
        self.assertEqual(result["reason"],"task-state-not-executable")
        self.assertEqual(result["provider_calls"],0)
        self.assertEqual(tasks.show(self.home,self.task_id)["task"]["status"],"cancelled")

    def test_atomic_claim_preserves_terminal_task(self):
        self.setup_task()
        conn=connect_write(self.home)
        work=one(conn,"SELECT * FROM work_units WHERE task_id=?",(self.task_id,))
        conn.execute("UPDATE tasks SET status='cancelled' WHERE id=?",(self.task_id,))
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(PermissionError,"claim-task-state-not-executable"):
            tasks.claim_work_unit(self.home,work["id"],"synthetic","synthetic")
        with self.assertRaisesRegex(PermissionError,"work-unit-task-state-not-executable"):
            tasks.add_work_unit(self.home,self.task_id,"Must not reopen")
        self.assertEqual(tasks.show(self.home,self.task_id)["task"]["status"],"cancelled")

    def test_projection_failure_recovers_to_fresh_work(self):
        result=self.execute(export_failure_phase=1)
        self.assertEqual(result["submission"]["reason"],"submission-projection-failed")
        self.assertTrue(result["submission"]["retry_requires_fresh_execution"])
        details=tasks.show(self.home,self.task_id)["task"]
        self.assertEqual(details["status"],"needs-work")
        self.assertTrue(all(row["status"]!="active" for row in details["leases"]))
        self.assertEqual(details["work_units"][0]["status"],"ready")

    def test_final_projection_failure_is_not_delivered(self):
        result=self.execute(export_failure_phase=2)
        self.assertEqual(result["submission"]["status"],"needs-work")
        self.assertFalse(result["submission"]["founder_queue_entered"])
        self.assertEqual(tasks.show(self.home,self.task_id)["task"]["status"],"needs-work")

    def corrupt_latest_test(self, *, new_run=False, skipped=False):
        conn = connect_write(self.home)
        row = one(conn, "SELECT * FROM test_results WHERE task_id=? ORDER BY rowid DESC LIMIT 1", (self.task_id,))
        row.update(id=new_id("test"), created_at="2000-01-01T00:00:00Z", decision="pass" if skipped else "fail",
                   skipped=int(skipped), exit_code=0 if skipped else 1)
        if new_run:
            row["run_id"] = "newer-failed-run"
        conn.execute(f"INSERT INTO test_results({','.join(row)}) VALUES({','.join('?' for _ in row)})", list(row.values()))
        conn.commit()
        conn.close()

    def test_same_run_later_failure_supersedes_pass(self):
        result = self.execute(submit_hook=self.corrupt_latest_test)
        self.assertEqual(result["submission"]["status"], "needs-work")
        self.assertIn("completion-ledger-drift", result["submission"]["audit"]["findings"])

    def test_later_skip_is_not_success(self):
        result = self.execute(submit_hook=lambda: self.corrupt_latest_test(skipped=True))
        self.assertEqual(result["decision"], "needs-work")

    def test_new_run_without_tests_supersedes_prior_pass(self):
        def mutate():
            conn = connect_write(self.home)
            row = one(conn, "SELECT * FROM attempts WHERE task_id=? ORDER BY rowid DESC LIMIT 1", (self.task_id,))
            row.update(id=new_id("attempt"), run_id="newer-failed-run", status="failed", created_at="2000-01-01T00:00:00Z")
            conn.execute(f"INSERT INTO attempts({','.join(row)}) VALUES({','.join('?' for _ in row)})", list(row.values()))
            conn.commit()
            conn.close()
        result = self.execute(submit_hook=mutate)
        self.assertEqual(result["decision"], "needs-work")
        self.assertIn("completion-run-superseded", result["submission"]["audit"]["findings"])

    def test_unversioned_acceptance_edit_preserved(self):
        def mutate():
            conn = connect_write(self.home)
            conn.execute("UPDATE tasks SET acceptance_criteria='new contract' WHERE id=?", (self.task_id,))
            conn.commit()
            conn.close()
        result = self.execute(submit_hook=mutate)
        self.assertEqual(result["submission"]["reason"], "submission-authority-conflict")
        self.assertEqual(tasks.show(self.home, self.task_id)["task"]["acceptance_criteria"], "new contract")

    def test_terminal_cancellation_is_not_overwritten(self):
        def cancel():
            conn = connect_write(self.home)
            conn.execute("UPDATE tasks SET status='cancelled',revision=revision+1 WHERE id=?", (self.task_id,))
            conn.commit()
            conn.close()
        result = self.execute(export_hook=cancel)
        self.assertEqual(result["submission"]["status"], "cancelled")
        self.assertFalse(result["submission"]["founder_queue_entered"])
        self.assertEqual(tasks.show(self.home, self.task_id)["task"]["status"], "cancelled")

    def test_source_changed_during_review_blocks(self):
        def mutate(stage, prompt):
            if stage == "final-review":
                payload, _ = json.JSONDecoder().raw_decode(prompt.split("CHANGE_BINDING:", 1)[1])
                (Path(payload["root"]) / "implemented.txt").write_text("not tested")
        result = self.execute(delegate_hook=mutate)
        self.assertEqual(result["decision"], "needs-work")
        self.assertIn("completion-source-drift", result["submission"]["audit"]["findings"])

    def test_audit_observes_caller_transaction_and_does_not_own_it(self):
        self.setup_task()
        conn = connect_write(self.home)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE tasks SET acceptance_criteria='uncommitted' WHERE id=?", (self.task_id,))
        result = audit_task(self.home, self.task_id, record=False, connection=conn)
        self.assertEqual(result["decision"], "needs-work")
        self.assertTrue(conn.in_transaction)
        with self.assertRaises(ValueError):
            audit_task(self.home, self.task_id, record=True, connection=conn)
        conn.rollback()
        self.assertNotEqual(one(conn, "SELECT acceptance_criteria FROM tasks WHERE id=?", (self.task_id,))["acceptance_criteria"], "uncommitted")
        conn.close()

    def test_unrelated_lease_rejected_and_preserved(self):
        self.setup_task()
        other = tasks.create(self.home, "Other task")["task_id"]
        work = tasks.add_work_unit(self.home, other, "Other work", "implementation")["work_unit_id"]
        lease = tasks.claim_work_unit(self.home, work, "synthetic-owner", "synthetic-session")
        with self.assertRaises(PermissionError):
            tasks.submit_task(self.home, self.task_id, work, lease["lease_id"], lease["lease_token"])
        conn = connect_read(self.home)
        self.assertEqual(one(conn, "SELECT status FROM leases WHERE id=?", (lease["lease_id"],))["status"], "active")
        conn.close()

    def test_tree_filenames_and_symlink_boundary(self):
        repo = _repo(self.home / "names")
        name = repo / "space and\nnewline.txt"
        name.write_text("synthetic")
        snapshot = snapshot_tree(repo)
        self.assertIn(name.name, snapshot["files"])
        self.assertEqual(len(tree_digest(snapshot)), 64)
        secret = self.home / "outside.txt"
        secret.write_text("synthetic")
        (repo / "link").symlink_to(secret)
        with self.assertRaises(ValueError):
            snapshot_tree(repo)
