# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
from __future__ import annotations

import unittest
from pathlib import Path

from iot_ai.identity_migration import apply, plan, rollback, status
from iot_ai.paths import config_root, data_root, log_root
from tests.common import IsolatedHomeTestCase


class BrandIdentityMigrationTests(IsolatedHomeTestCase):
    def _legacy(self) -> tuple[Path, Path, Path]:
        config = self.home / ".config" / "ai-iot-tech" / "iot-ai-suite" / "v1"
        data = self.home / ".local" / "share" / "ai-iot-tech" / "iot-ai-suite" / "v1"
        state = self.home / ".local" / "state" / "ai-iot-tech" / "iot-ai-suite" / "v1"
        for root, name in ((config, "settings.json"), (data, "database.bin"), (state, "old.log")):
            root.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(f"{name}\n", encoding="utf-8")
        return config, data, state

    def test_plan_is_hash_bound_and_read_only(self) -> None:
        legacy = self._legacy()
        value = plan(self.home)
        self.assertEqual(value["decision"], "plan")
        self.assertTrue(all(item["manifest_sha256"] for item in value["items"]))
        self.assertTrue(all(path.exists() for path in legacy))
        self.assertFalse(config_root(self.home).exists())

    def test_apply_and_rollback_are_atomic_for_unchanged_state(self) -> None:
        legacy = self._legacy()
        result = apply(self.home)
        self.assertEqual(result["decision"], "pass")
        self.assertTrue((config_root(self.home) / "settings.json").is_file())
        self.assertTrue((data_root(self.home) / "database.bin").is_file())
        self.assertTrue((log_root(self.home).parent / "old.log").is_file())
        self.assertTrue(all(not path.exists() for path in legacy))
        restored = rollback(self.home)
        self.assertEqual(restored["decision"], "pass")
        self.assertTrue(all(path.exists() for path in legacy))

    def test_existing_canonical_state_blocks_migration(self) -> None:
        self._legacy()
        config_root(self.home).mkdir(parents=True)
        (config_root(self.home) / "settings.json").write_text("canonical\n", encoding="utf-8")
        value = apply(self.home)
        self.assertEqual(value["decision"], "block")
        self.assertTrue(value["blockers"])

    def test_changed_canonical_state_blocks_rollback(self) -> None:
        self._legacy()
        result = apply(self.home)
        self.assertEqual(result["decision"], "pass")
        (data_root(self.home) / "database.bin").write_text("changed\n", encoding="utf-8")
        value = rollback(self.home)
        self.assertEqual(value["decision"], "block")
        self.assertEqual(value["reason"], "rollback-precondition-failed")


if __name__ == "__main__":
    unittest.main()
