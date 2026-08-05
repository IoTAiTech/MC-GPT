# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from iot_ai.privacy import sanitize
from iot_ai.release_guard import export_public, root_digest, scan

from tests.common import IsolatedHomeTestCase


class PrivacyReleaseTests(IsolatedHomeTestCase):
    def test_secret_blocks_cloud_egress(self) -> None:
        result = sanitize("Authorization: Bearer " + "A" * 32, "strict")
        self.assertEqual(result.decision, "block")
        self.assertNotIn("A" * 32, result.text)

    def test_private_infrastructure_is_redacted(self) -> None:
        value = "server=10.255." + "255.1 path=/home/" + "example/private/file"
        result = sanitize(value, "strict")
        self.assertNotIn("10.255.", result.text)
        self.assertNotIn("/home/operator", result.text)
        self.assertTrue(result.findings)

    def test_public_text_passes(self) -> None:
        result = sanitize("Public architecture and evidence summary.", "strict")
        self.assertEqual(result.decision, "pass")

    def test_release_scanner_detects_private_ip(self) -> None:
        root = self.home / "scan"
        root.mkdir()
        (root / "bad.txt").write_text("endpoint=10." + "20.30.40", encoding="utf-8")
        self.assertTrue(scan(root))

    def test_release_scanner_clean_tree(self) -> None:
        root = self.home / "scan"
        root.mkdir()
        (root / "README.md").write_text("Public-only documentation", encoding="utf-8")
        self.assertEqual(scan(root), [])
        self.assertEqual(len(root_digest(root)), 64)

    def test_public_export_uses_allowlist(self) -> None:
        source = self.home / "source"
        destination = self.home / "public"
        (source / "src").mkdir(parents=True)
        (source / "enterprise").mkdir(parents=True)
        (source / "src" / "module.py").write_text("# public", encoding="utf-8")
        (source / "enterprise" / "secret.py").write_text("# private implementation", encoding="utf-8")
        (source / "README.md").write_text("Public", encoding="utf-8")
        result = export_public(source, destination)
        self.assertEqual(result["decision"], "pass")
        self.assertTrue((destination / "src" / "module.py").is_file())
        self.assertFalse((destination / "enterprise").exists())

    def test_public_export_rejects_symlink(self) -> None:
        source = self.home / "source"
        destination = self.home / "public"
        (source / "src").mkdir(parents=True)
        external = self.home / "external.txt"
        external.write_text("external", encoding="utf-8")
        try:
            (source / "src" / "link").symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(ValueError):
            export_public(source, destination)


if __name__ == "__main__":
    unittest.main()
