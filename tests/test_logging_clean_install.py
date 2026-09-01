# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from iot_ai.installer import install
from iot_ai.logging_config import append_event, log_locations
from iot_ai.paths import data_root, install_state_path
from iot_ai.status import unified_status
from iot_ai.suite_package import archive_old_active_versions, clean_package_store
from iot_ai.util import atomic_json, sha256_file
from tests.common import synthetic_bearer_header, synthetic_xai_token


class LoggingAndCleanInstallTests(unittest.TestCase):
    def test_log_locations_are_scope_bound_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            locations = log_locations(home)
            self.assertTrue(locations["logs_root"].startswith(str(home)))
            secret_value = synthetic_xai_token()
            auth_header = synthetic_bearer_header()
            bearer_value = auth_header.split()[-1]
            event = append_event(
                home,
                "test.event",
                {
                    "api_key": secret_value,
                    "message": auth_header,
                },
            )
            line = Path(event["path"]).read_text(encoding="utf-8")
            self.assertNotIn(secret_value, line)
            self.assertNotIn(bearer_value, line)
            self.assertIn("<redacted>", line)

    def test_status_always_reports_log_locations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            payload = unified_status(home)
            self.assertEqual(payload["logs"], log_locations(home))

    def test_host_adapter_upgrade_removes_only_stale_managed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            first = install(home, ["claude"])
            self.assertEqual(first["decision"], "pass")
            state = json.loads(install_state_path(home).read_text(encoding="utf-8"))
            stale = home / ".claude" / "skills" / "iot-ai-obsolete" / "SKILL.md"
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.write_text("managed old skill\n", encoding="utf-8")
            state["files"].append({"path": str(stale), "sha256": sha256_file(stale, allowed_roots=[home])})
            atomic_json(install_state_path(home), state)
            unknown = stale.parent.parent / "customer-owned" / "NOTE.md"
            unknown.parent.mkdir(parents=True, exist_ok=True)
            unknown.write_text("preserve me\n", encoding="utf-8")

            upgraded = install(home, ["claude"], "upgrade")
            self.assertEqual(upgraded["decision"], "pass")
            self.assertFalse(stale.exists())
            self.assertTrue(unknown.exists())
            self.assertIn(str(stale), upgraded["clean_install"]["obsolete_managed_removed"])

    def test_old_active_versions_are_archived_not_left_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            suite_root = data_root(home) / "suite"
            current = suite_root / "6.6.0-beta.3"
            old = suite_root / "6.4.0-beta.1"
            unknown = suite_root / "customer-data"
            for root, version in ((current, "6.6.0-beta.3"), (old, "6.4.0-beta.1")):
                (root / "venv" / "bin").mkdir(parents=True)
                (root / "venv" / "bin" / "iot-ai").write_text("#!/bin/sh\n", encoding="utf-8")
                (root / "PACKAGE_METADATA.json").write_text(
                    json.dumps({"schema": "iot-ai.suite-package.v1", "product_id": "iot-ai-tech.iot-ai-suite", "version": version}),
                    encoding="utf-8",
                )
            unknown.mkdir(parents=True)
            (unknown / "keep.txt").write_text("not a managed runtime", encoding="utf-8")
            transaction = data_root(home) / "update-transactions" / "TX"
            result = archive_old_active_versions(home, "6.6.0-beta.3", transaction, apply=True)
            self.assertEqual(result["decision"], "pass")
            self.assertTrue(current.exists())
            self.assertFalse(old.exists())
            self.assertTrue((transaction / "retired-active-versions" / "suite" / old.name).exists())
            self.assertTrue(unknown.exists())

    def test_package_store_cleanup_archives_only_canonical_old_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = root / "IoT-AI-Tech-iot-ai-Coder-Suite-v6.6.0-beta.3-ALL-IN-ONE.zip"
            old = root / "IoT-AI-Tech-iot-ai-Coder-Suite-v6.4.0-beta.1-ALL-IN-ONE.zip"
            unrelated = root / "notes.zip"
            current.write_bytes(b"current")
            old.write_bytes(b"old")
            old.with_suffix(old.suffix + ".sha256").write_text("old\n", encoding="utf-8")
            unrelated.write_bytes(b"keep")
            archive = root / "archive"
            result = clean_package_store(root, current, archive, apply=True)
            self.assertEqual(result["decision"], "pass")
            self.assertTrue(current.exists())
            self.assertFalse(old.exists())
            self.assertTrue((archive / old.name).exists())
            self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
