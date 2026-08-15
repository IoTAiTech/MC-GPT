# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.6 | Date: 2026-08-15
from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from iot_ai.cli import _cli_public_text, _public_cli_view, emit


class CliEmitRedactionTests(unittest.TestCase):
    def test_omits_secret_classified_keys(self) -> None:
        view = _public_cli_view(
            {
                "route_id": "ollama-cloud",
                "secret": "must-not-print",
                "secret_env": "XAI_API_KEY",
                "secret_value": "must-not-print-either",
                "password": "hunter2",
                "api_key": "example-api-key-value-not-real",
                "secret_value_recorded": False,
                "token_budget": 32000,
            }
        )
        self.assertEqual(view["route_id"], "ollama-cloud")
        self.assertFalse(view["secret_value_recorded"])
        self.assertEqual(view["token_budget"], 32000)
        for key in ("secret", "secret_env", "secret_value", "password", "api_key"):
            self.assertNotIn(key, view)

    def test_emit_never_prints_original_secret_fields(self) -> None:
        payload = {
            "nested": {"secret": "super-secret-value", "ok": True},
            "secret_env": "OPENAI_API_KEY",
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            emit(payload)
        text = buf.getvalue()
        self.assertNotIn("super-secret-value", text)
        self.assertNotIn("OPENAI_API_KEY", text)
        self.assertNotIn('"secret"', text)
        parsed = json.loads(text)
        self.assertEqual(parsed, {"nested": {"ok": True}})

    def test_string_emit_masks_inline_secrets(self) -> None:
        raw = "Authorization: Bearer " + ("A" * 32)
        text = _cli_public_text(raw)
        self.assertNotIn("A" * 32, text)
        self.assertIn("[REDACTED]", text)

    def test_public_status_text_is_unchanged(self) -> None:
        self.assertEqual(_cli_public_text("Edition: community"), "Edition: community")


if __name__ == "__main__":
    unittest.main()
