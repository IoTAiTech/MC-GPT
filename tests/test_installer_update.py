# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
from __future__ import annotations

import hashlib
import json
import os
import unittest
from pathlib import Path

from iot_ai.installer import _wrapper_path, install, plan, repair, rollback, status, uninstall, verify
from iot_ai.paths import config_root, data_root, home as resolve_home
from iot_ai.update_manager import default_index, load_index, plan as update_plan, status as update_status

from tests.common import IsolatedHomeTestCase


class InstallerUpdateTests(IsolatedHomeTestCase):
    def test_install_plan_is_non_mutating(self) -> None:
        result = plan(self.home, ["claude", "codex", "gemini", "grok"])
        self.assertEqual(result["decision"], "plan")
        self.assertFalse((self.home / ".config").exists())

    def test_install_verify_status(self) -> None:
        result = install(self.home, ["claude", "codex", "gemini", "grok"])
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(verify(self.home)["decision"], "pass")
        self.assertTrue(status(self.home)["installed"])
        self.assertTrue(_wrapper_path(self.home, "iot-ai").is_file())

    def test_drift_is_detected_and_repairable(self) -> None:
        install(self.home, ["claude"])
        wrapper = _wrapper_path(self.home, "iot-ai")
        wrapper.write_text("drift", encoding="utf-8")
        self.assertEqual(verify(self.home)["decision"], "needs-work")
        repair(self.home)
        self.assertEqual(verify(self.home)["decision"], "pass")

    def test_uninstall_and_rollback(self) -> None:
        install(self.home, ["grok"])
        uninstall_result = uninstall(self.home, force_drift=False)
        self.assertEqual(uninstall_result["decision"], "pass")
        self.assertFalse(_wrapper_path(self.home, "iot-ai").exists())
        rollback_result = rollback(self.home)
        self.assertEqual(rollback_result["decision"], "pass")
        self.assertTrue(_wrapper_path(self.home, "iot-ai").exists())


    def test_explicit_home_ignores_inherited_xdg_roots(self) -> None:
        foreign = self.home / "foreign-xdg"
        os.environ["XDG_CONFIG_HOME"] = str(foreign / "config")
        os.environ["XDG_DATA_HOME"] = str(foreign / "data")
        os.environ["APPDATA"] = str(foreign / "AppData" / "Roaming")
        os.environ["LOCALAPPDATA"] = str(foreign / "AppData" / "Local")
        scoped = resolve_home(str(self.home))
        self.assertEqual(config_root(scoped), config_root(self.home))
        self.assertEqual(data_root(scoped), data_root(self.home))
        # Explicit --home scope must not follow inherited XDG/AppData env roots.
        self.assertTrue(str(config_root(scoped)).startswith(str(self.home)))
        self.assertFalse(str(config_root(scoped)).startswith(str(foreign)))
        install(scoped, ["grok"])
        self.assertTrue((config_root(self.home) / "install-state.json").is_file())
        self.assertFalse(foreign.exists())

    def test_update_index_is_explicit_when_unpublished(self) -> None:
        index = default_index()
        self.assertFalse(index["channels"]["beta"]["available"])
        status_result = update_status(self.home)
        self.assertEqual(status_result["published"]["schema"], "iot-ai.release-index.v2")
        plan_result = update_plan(self.home, "beta")
        self.assertEqual(plan_result["decision"], "block")
        self.assertIn("reason", plan_result)


if __name__ == "__main__":
    unittest.main()
