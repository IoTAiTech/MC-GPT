# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import hashlib
import json
import os
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from iot_ai.installer import _wrapper_path, install, plan, repair, rollback, status, uninstall, verify
from iot_ai.paths import config_root, data_root, home as resolve_home
from iot_ai.update_manager import (
    apply_local as update_apply_local,
    default_index,
    load_index,
    plan as update_plan,
    status as update_status,
)

from tests.common import IsolatedHomeTestCase


class InstallerUpdateTests(IsolatedHomeTestCase):
    def test_install_plan_is_non_mutating(self) -> None:
        result = plan(self.home, ["claude", "codex", "gemini", "grok"])
        self.assertEqual(result["decision"], "plan")
        self.assertFalse((self.home / ".config").exists())

    def test_install_sh_dry_run_pins_current_suite_version(self) -> None:
        import subprocess

        script = Path(__file__).resolve().parents[1] / "installers" / "install.sh"
        completed = subprocess.run(
            ["sh", str(script), "--home", str(self.home)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["version"], "6.8.0-beta.1")
        self.assertFalse(payload["apply"])
        self.assertIn("6.8.0-beta.1", payload["runtime"])

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
        if os.name == "nt":
            expected_config = self.home / "AppData" / "Roaming" / "IoT-AI.Tech" / "IOT-AI-Suite" / "v1"
            expected_data = self.home / "AppData" / "Local" / "IoT-AI.Tech" / "IOT-AI-Suite" / "v1"
        else:
            expected_config = self.home / ".config" / "iot-ai-tech/iot-ai-suite/v1"
            expected_data = self.home / ".local" / "share" / "iot-ai-tech/iot-ai-suite/v1"
        self.assertEqual(config_root(scoped), expected_config)
        self.assertEqual(data_root(scoped), expected_data)
        install(scoped, ["grok"] )
        self.assertTrue((expected_config / "install-state.json").is_file())
        self.assertFalse(foreign.exists())


    def test_complete_delivery_resolves_exactly_one_nested_all_in_one(self) -> None:
        inner_name = "IoT-AI-Tech-iot-ai-Coder-Suite-v6.7.0-beta.5-ALL-IN-ONE.zip"
        inner_bytes = b"verified nested payload"
        inner_sha = hashlib.sha256(inner_bytes).hexdigest()
        outer = self.home / "complete-private-delivery.zip"
        with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            member = f"02_RELEASE_ASSETS/COMMUNITY/{inner_name}"
            archive.writestr(member, inner_bytes)
            archive.writestr(member + ".sha256", f"{inner_sha}  {inner_name}\n")
        outer_sha = hashlib.sha256(outer.read_bytes()).hexdigest()

        def fake_install(user_home, package, expected_sha256, **kwargs):
            self.assertEqual(user_home, self.home)
            self.assertEqual(Path(package).read_bytes(), inner_bytes)
            self.assertEqual(expected_sha256, inner_sha)
            self.assertFalse(kwargs["apply"])
            return {"decision": "plan", "version": "6.7.0-beta.5"}

        with patch("iot_ai.update_manager.install_package", side_effect=fake_install) as mocked:
            result = update_apply_local(self.home, outer, outer_sha, apply=False)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(result["decision"], "plan")
        self.assertTrue(result["nested_package"])
        self.assertEqual(result["outer_sha256"], outer_sha)
        self.assertEqual(result["inner_sha256"], inner_sha)
        self.assertTrue(result["inner_sha256_sidecar_verified"])
        self.assertEqual(result["complete_delivery_extracted_members"], 1)
        self.assertTrue(result["resolved_apply_package"].endswith(inner_name))

    def test_complete_delivery_rejects_ambiguous_nested_packages(self) -> None:
        outer = self.home / "ambiguous-private-delivery.zip"
        with zipfile.ZipFile(outer, "w") as archive:
            for suffix in ("a", "b"):
                archive.writestr(
                    f"{suffix}/IoT-AI-Tech-iot-ai-Coder-Suite-v6.7.0-beta.5-ALL-IN-ONE.zip",
                    suffix.encode(),
                )
        digest = hashlib.sha256(outer.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "exactly one"):
            update_apply_local(self.home, outer, digest, apply=False)

    def test_complete_delivery_rejects_nested_sidecar_mismatch(self) -> None:
        inner_name = "IoT-AI-Tech-iot-ai-Coder-Suite-v6.7.0-beta.5-ALL-IN-ONE.zip"
        outer = self.home / "mismatched-private-delivery.zip"
        with zipfile.ZipFile(outer, "w") as archive:
            member = f"02_RELEASE_ASSETS/COMMUNITY/{inner_name}"
            archive.writestr(member, b"actual")
            archive.writestr(member + ".sha256", f"{'0' * 64}  {inner_name}\n")
        digest = hashlib.sha256(outer.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "nested ALL-IN-ONE package SHA-256 mismatch"):
            update_apply_local(self.home, outer, digest, apply=False)

    def test_update_rejects_outer_digest_mismatch_before_opening_nested_payload(self) -> None:
        outer = self.home / "complete-private-delivery.zip"
        with zipfile.ZipFile(outer, "w") as archive:
            archive.writestr(
                "02_RELEASE_ASSETS/COMMUNITY/IoT-AI-Tech-iot-ai-Coder-Suite-v6.7.0-beta.5-ALL-IN-ONE.zip",
                b"payload",
            )
        with patch("iot_ai.update_manager.install_package") as mocked:
            with self.assertRaisesRegex(ValueError, "package SHA-256 mismatch"):
                update_apply_local(self.home, outer, "f" * 64, apply=False)
        mocked.assert_not_called()

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
