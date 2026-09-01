# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import ipaddress
import os
import tempfile
import unittest
from pathlib import Path


def synthetic_rfc1918_host() -> str:
    """Runtime-only RFC1918 example. Do not store the dotted form in source."""
    return str(ipaddress.IPv4Address(0x0A000001))


def synthetic_rfc1918_host_alt() -> str:
    """Second runtime-only RFC1918 example. Distinct from synthetic_rfc1918_host()."""
    return str(ipaddress.IPv4Address(0xAC100001))


def synthetic_home_operator(*parts: str) -> str:
    """Runtime-only POSIX personal path. Always use '/' so Windows CI redacts it."""
    home = "".join(chr(c) for c in (104, 111, 109, 101))
    root = "/" + home + "/" + "operator"
    if not parts:
        return root
    return root + "/" + "/".join(parts)


def synthetic_personal_path() -> str:
    """Runtime-only personal-path example. Do not store /home/<name> in source."""
    return synthetic_home_operator("private")


def synthetic_xai_token() -> str:
    return "".join(chr(c) for c in (120, 97, 105, 45) + (65,) * 24)


def synthetic_openai_token() -> str:
    return "".join(chr(c) for c in (115, 107, 45) + (90,) * 20)


def synthetic_google_token() -> str:
    return "".join(chr(c) for c in (65, 73, 122, 97) + (68,) * 24)


def synthetic_bearer_header() -> str:
    prefix = (65, 117, 116, 104, 111, 114, 105, 122, 97, 116, 105, 111, 110, 58, 32, 66, 101, 97, 114, 101, 114, 32)
    return "".join(chr(c) for c in prefix + (65,) * 32)


def synthetic_pem_block() -> str:
    header = (45, 45, 45, 45, 45, 66, 69, 71, 73, 78, 32, 80, 82, 73, 86, 65, 84, 69, 32, 75, 69, 89, 45, 45, 45, 45, 45, 10)
    body = (102, 105, 120, 116, 117, 114, 101, 10)
    footer = (45, 45, 45, 45, 45, 69, 78, 68, 32, 80, 82, 73, 86, 65, 84, 69, 32, 75, 69, 89, 45, 45, 45, 45, 45, 10)
    return "".join(chr(c) for c in header + body + footer)


def synthetic_labeled_secret() -> str:
    """Runtime-only api_key assignment using a synthetic xAI-shaped token."""
    label = "api"
    glue = "_key="
    return label + glue + synthetic_xai_token()


def synthetic_openai_env_line() -> str:
    """Runtime-only dotenv line. Avoid api_key= quotes in source."""
    vendor = "OPENAI"
    field = "_API_KEY"
    return vendor + field + "=" + synthetic_openai_token() + "\n"


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
