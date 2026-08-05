# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-06
"""Article 50 operator identity + brand residual scan + path migration."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from iot_ai.brand_identity import (
    CANONICAL_LEGAL_NAME,
    CANONICAL_PACKAGE_PREFIX,
    LEGACY_PACKAGE_PREFIX,
    scan_tree,
)
from iot_ai.paths import (
    STATE_NAMESPACE,
    WINDOWS_VENDOR,
    WINDOWS_VENDOR_LEGACY,
    config_root,
    data_root,
    log_root,
    migrate_vendor_namespace,
    restore_vendor_namespace_backup,
)
from iot_ai.suite_version import SUITE_VERSION
from iot_ai.transparency import DISCLOSURES, disclosure_payload


class Article50OperatorTests(unittest.TestCase):
    def test_operator_default_is_canonical(self) -> None:
        for lang in ("en", "de", "fa"):
            payload = disclosure_payload(surface="test", language=lang)
            self.assertEqual(payload["operator"], CANONICAL_LEGAL_NAME)
            self.assertIn(CANONICAL_LEGAL_NAME, payload["text"])
            self.assertNotIn("AI-IoT.Tech", payload["text"])
            self.assertEqual(payload["system_version"], SUITE_VERSION)

    def test_disclosure_dictionaries(self) -> None:
        for lang in ("en", "de", "fa"):
            self.assertIn(CANONICAL_LEGAL_NAME, DISCLOSURES[lang]["text"])
            self.assertNotIn("AI-IoT.Tech", DISCLOSURES[lang]["text"])


class PackagePrefixTests(unittest.TestCase):
    def test_canonical_prefix(self) -> None:
        self.assertEqual(CANONICAL_PACKAGE_PREFIX, "IoT-AI-Tech")
        self.assertEqual(LEGACY_PACKAGE_PREFIX, "AI-IoT-Tech")
        self.assertNotEqual(CANONICAL_PACKAGE_PREFIX, LEGACY_PACKAGE_PREFIX)


class VendorNamespaceMigrationTests(unittest.TestCase):
    def test_canonical_constants(self) -> None:
        self.assertEqual(WINDOWS_VENDOR, "IoT-AI.Tech")
        self.assertEqual(WINDOWS_VENDOR_LEGACY, "AI-IoT.Tech")
        self.assertEqual(STATE_NAMESPACE, "iot-ai-tech")

    def test_dry_run_and_apply_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "user"
            home.mkdir()
            # Build legacy layout (Linux)
            legacy_config = home / ".config" / "ai-iot-tech" / "iot-ai-suite" / "v1"
            legacy_data = home / ".local" / "share" / "ai-iot-tech" / "iot-ai-suite" / "v1"
            legacy_logs = home / ".local" / "state" / "ai-iot-tech" / "logs"
            for root in (legacy_config, legacy_data, legacy_logs):
                root.mkdir(parents=True)
            settings = legacy_config / "settings.json"
            settings.write_text(json.dumps({"theme": "dark", "customer": "acme"}), encoding="utf-8")
            db = legacy_data / "state" / "iot-ai-control.sqlite3"
            db.parent.mkdir(parents=True, exist_ok=True)
            db.write_bytes(b"SQLite-fake-bytes")
            (legacy_logs / "iot-ai.jsonl").write_text('{"event":1}\n', encoding="utf-8")

            dry = migrate_vendor_namespace(home, apply=False)
            self.assertEqual(dry["decision"], "dry-run")
            self.assertTrue(any(a["action"] != "skip" for a in dry["actions"]))
            # legacy still present after dry-run
            self.assertTrue(settings.is_file())

            applied = migrate_vendor_namespace(home, apply=True)
            self.assertEqual(applied["decision"], "pass", applied)
            # customer settings preserved on canonical
            canon_settings = config_root(home) / "settings.json"
            self.assertTrue(canon_settings.is_file())
            self.assertEqual(json.loads(canon_settings.read_text())["customer"], "acme")
            canon_db = data_root(home) / "state" / "iot-ai-control.sqlite3"
            self.assertTrue(canon_db.is_file())
            self.assertEqual(canon_db.read_bytes(), b"SQLite-fake-bytes")
            self.assertTrue((log_root(home) / "iot-ai.jsonl").is_file())

            backup = Path(applied["backup_root"])
            restored = restore_vendor_namespace_backup(backup)
            self.assertEqual(restored["decision"], "pass")
            self.assertTrue(settings.is_file())
            self.assertEqual(json.loads(settings.read_text())["customer"], "acme")


class BrandScanSelfTest(unittest.TestCase):
    def test_public_src_has_zero_unclassified_wrong_legal_brand(self) -> None:
        root = Path(__file__).resolve().parents[1] / "src" / "iot_ai"
        report = scan_tree(root)
        # Wrong legal brand AI-IoT.Tech must only appear as classified legacy constants
        for f in report["findings"]:
            if "AI-IoT.Tech" in f["snippet"] and f["classification"] is None:
                self.fail(f"unclassified wrong brand: {f}")
        # Explicit: no blocker for display brand outside legacy constants
        blockers = [b for b in report["blockers"] if "AI-IoT.Tech" in b.get("snippet", "")]
        self.assertEqual(blockers, [], blockers)


if __name__ == "__main__":
    unittest.main()
