# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from iot_ai.capability_pack import build_pack, verify_pack
from iot_ai.util import sha256_file


class CapabilityPackTests(unittest.TestCase):
    def test_pack_is_deterministic_secret_safe_and_multi_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = {
                "name": "security-reviewer",
                "version": "1.0.0",
                "classification": "public",
                "operations": [
                    {
                        "name": "review",
                        "input_schema": {"type": "object", "properties": {"diff": {"type": "string"}}},
                        "output_schema": {"type": "object", "properties": {"decision": {"type": "string"}}},
                    }
                ],
                "skills": ["security-review"],
                "mcp_servers": {"scanner": {"command": "scanner", "env": {"API_KEY": "top-secret-123456789"}}},
                "materialize_targets": ["claude", "codex", "gemini", "grok", "mcp", "rest", "openapi"],
            }
            first = root / "first.capability.zip"
            second = root / "second.capability.zip"
            a = build_pack(spec, first)
            b = build_pack(spec, second)
            self.assertEqual(a["decision"], "pass")
            self.assertEqual(sha256_file(first), sha256_file(second))
            self.assertEqual(verify_pack(first)["decision"], "pass")
            payload = first.read_bytes()
            self.assertNotIn(b"top-secret", payload)
            self.assertIn(b"<redacted>", payload)
            self.assertEqual(set(a["boundaries"]), {"mcp", "openapi", "rest"})

    def test_pack_tamper_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "pack.zip"
            build_pack({"name": "x", "version": "1", "classification": "private", "operations": []}, path)
            data = bytearray(path.read_bytes())
            data[-20] ^= 0x01
            path.write_bytes(data)
            self.assertEqual(verify_pack(path)["decision"], "block")


if __name__ == "__main__":
    unittest.main()
