# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from iot_ai.worktrees import cleanup, create, list_runs, promotion_plan, show
from tests.common import IsolatedHomeTestCase


class WorktreeOrchestrationTests(IsolatedHomeTestCase):
    def _repo(self) -> Path:
        root = self.home / "repo"
        root.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test Author"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        (root / "README.md").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-m", "chore: baseline"], check=True, capture_output=True)
        return root

    def test_plan_is_read_only_and_does_not_copy_untracked_files(self) -> None:
        repo = self._repo()
        (repo / ".env").write_text("PRIVATE=not-for-workers\n", encoding="utf-8")
        value = create(self.home, repo, "Review the release", ["codex", "grok"], apply=False)
        self.assertEqual(value["decision"], "plan")
        self.assertTrue(value["repository"]["dirty"])
        self.assertFalse(Path(value["workers"][0]["path"]).exists())
        self.assertFalse(value["untracked_content_copied"])

    def test_create_isolates_agents_and_requires_human_promotion(self) -> None:
        repo = self._repo()
        (repo / "local-secret.txt").write_text("not tracked\n", encoding="utf-8")
        value = create(self.home, repo, "Implement safe status", ["codex", "grok"], apply=True)
        self.assertEqual(value["decision"], "pass")
        self.assertEqual(len(value["workers"]), 2)
        for worker in value["workers"]:
            path = Path(worker["path"])
            self.assertTrue((path / "README.md").is_file())
            self.assertFalse((path / "local-secret.txt").exists())
        overview = list_runs(self.home)
        self.assertEqual(overview["count"], 1)
        plan = promotion_plan(self.home, value["run_id"])
        self.assertFalse(plan["automatic_merge"])
        self.assertTrue(plan["founder_or_reviewer_approval_required"])
        cleaned = cleanup(self.home, value["run_id"], apply=True)
        self.assertEqual(cleaned["decision"], "pass")

    def test_dirty_worker_blocks_cleanup(self) -> None:
        repo = self._repo()
        value = create(self.home, repo, "Implement diagnostics", ["codex"], apply=True)
        worker = Path(value["workers"][0]["path"])
        (worker / "README.md").write_text("changed\n", encoding="utf-8")
        state = show(self.home, value["run_id"])
        self.assertTrue(state["workers"][0]["dirty"])
        blocked = cleanup(self.home, value["run_id"], apply=True)
        self.assertEqual(blocked["decision"], "block")
        self.assertTrue(worker.exists())

    def test_committed_unmerged_worker_blocks_cleanup(self) -> None:
        repo = self._repo()
        value = create(self.home, repo, "Implement tests", ["grok"], apply=True)
        worker = Path(value["workers"][0]["path"])
        (worker / "result.txt").write_text("result\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(worker), "add", "result.txt"], check=True)
        subprocess.run(["git", "-C", str(worker), "-c", "user.name=Worker", "-c", "user.email=worker@example.invalid", "commit", "-m", "test: result"], check=True, capture_output=True)
        blocked = cleanup(self.home, value["run_id"], apply=True)
        self.assertEqual(blocked["decision"], "block")
        self.assertEqual(blocked["blockers"][0]["commits_ahead"], 1)


if __name__ == "__main__":
    unittest.main()
