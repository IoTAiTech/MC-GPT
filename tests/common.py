# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class IsolatedHomeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="iot-ai-public-test-")
        self.home = Path(self._tmp.name).resolve()
        self._old_env = dict(os.environ)
        for key in (
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "IOT_AI_EXPLICIT_HOME",
            "IOT_AI_ENTITLEMENT_FILE",
            "IOT_AI_OLLAMA_CLOUD_MODELS",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "XAI_API_KEY",
            "OLLAMA_API_KEY",
        ):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_env)
        self._tmp.cleanup()
