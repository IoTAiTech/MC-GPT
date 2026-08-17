# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import unittest
from unittest.mock import patch

from iot_ai import __version__
from iot_ai.cli import _normalize_argv, parser
from iot_ai.help_system import list_topics, search, show
from iot_ai.settings import DEFAULTS, get_value, load, parse_scalar, set_value, toggle_group
from iot_ai.suite_version import COMPONENT_ID, MC_GPT_VERSION, SUITE_VERSION

from tests.common import IsolatedHomeTestCase


class VersionHelpSettingsTests(IsolatedHomeTestCase):
    def test_versions_are_aligned(self) -> None:
        self.assertEqual(__version__, "6.7.0-beta.6")
        self.assertEqual(SUITE_VERSION, __version__)
        self.assertEqual(MC_GPT_VERSION, "0.8.0-alpha.6")
        self.assertEqual(COMPONENT_ID, "iot-ai-mc-gpt")

    def test_natural_language_normalization(self) -> None:
        normalized = _normalize_argv(["--profile", "ultracode", "review", "this", "design"])
        self.assertEqual(normalized[:3], ["run", "--profile", "ultracode"])
        self.assertEqual(normalized[-4:], ["--goal", "review", "this", "design"])

    def test_command_passthrough(self) -> None:
        self.assertEqual(_normalize_argv(["status", "--json"]), ["status", "--json"])

    def test_home_after_command_is_hoisted(self) -> None:
        self.assertEqual(
            _normalize_argv(["status", "--home", "/tmp/demo-home", "--json"]),
            ["--home", "/tmp/demo-home", "status", "--json"],
        )
        self.assertEqual(
            _normalize_argv(["--home", "/tmp/demo-home", "status", "--json"]),
            ["--home", "/tmp/demo-home", "status", "--json"],
        )

    def test_wrapper_home_reaches_status(self) -> None:
        import io
        import json
        from contextlib import redirect_stdout
        from iot_ai.cli import main

        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(["status", "--home", str(self.home), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["suite"]["version"], "6.7.0-beta.6")

    def test_meeting_wrapper_keeps_home_and_list(self) -> None:
        from iot_ai.cli import normalize_meeting_argv

        self.assertEqual(
            normalize_meeting_argv(["--home", "/tmp/demo-home", "list"]),
            ["--home", "/tmp/demo-home", "meeting", "list"],
        )

    def test_parser_supports_minimal_surface(self) -> None:
        value = parser().parse_args(["status", "--window", "7d"])
        self.assertEqual(value.cmd, "status")
        self.assertEqual(value.window, "7d")

    def test_help_catalog(self) -> None:
        topics = list_topics()
        self.assertIn("meeting", topics["topics"])
        self.assertIn("iot-ai-status", topics["public_commands"])
        self.assertEqual(show("iot-ai-meeting")["decision"], "pass")
        self.assertIn("meeting", search("independent roles")["matches"])

    def test_settings_defaults_protect_raw_data(self) -> None:
        value = load(self.home)
        self.assertFalse(value["telemetry"]["store_raw_prompts"])
        self.assertFalse(value["telemetry"]["store_raw_outputs"])
        self.assertFalse(value["models"]["local_enabled"])
        self.assertTrue(value["ollama"]["first_class"])

    def test_settings_scalar_parser(self) -> None:
        self.assertIs(parse_scalar("true"), True)
        self.assertIs(parse_scalar("off"), False)
        self.assertEqual(parse_scalar("42"), 42)
        self.assertEqual(parse_scalar("xhigh"), "xhigh")

    def test_settings_secret_key_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            set_value(dict(DEFAULTS), "provider.api_key", "value")

    def test_settings_groups(self) -> None:
        value = load(self.home)
        toggle_group(value, "all-cloud", False)
        self.assertFalse(value["cloud"]["enabled"])
        toggle_group(value, "ollama", False)
        self.assertFalse(value["providers"]["ollama"]["enabled"])
        self.assertEqual(get_value(value, "providers.ollama.enabled"), False)

    def test_unknown_settings_group_lists_known(self) -> None:
        value = load(self.home)
        with self.assertRaises(ValueError) as raised:
            toggle_group(value, "providers", False)
        message = str(raised.exception)
        self.assertIn("all-cloud", message)
        self.assertIn("all-models", message)
        self.assertIn("ollama", message)

    def test_meeting_alias_help_does_not_require_topic(self):
        from iot_ai.cli import normalize_meeting_argv
        self.assertEqual(normalize_meeting_argv(["--help"]), ["meeting", "--help"])

    def test_multi_coder_plan_does_not_require_live_providers(self) -> None:
        import io
        import json
        from contextlib import redirect_stdout
        from iot_ai.cli import main

        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(["--home", str(self.home), "multi-coder", "run", "--plan", "--task", "independent sandbox"])
        self.assertEqual(code, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["decision"], "plan")
        self.assertEqual(payload["provider_calls"], 0)
        self.assertFalse(payload["implements_code"])



if __name__ == "__main__":
    unittest.main()

class CommunityPolicyTests(IsolatedHomeTestCase):
    def test_cloud_is_opt_in_and_retention_is_bounded(self) -> None:
        from iot_ai.settings import load
        value = load(self.home)
        self.assertFalse(value["cloud"]["enabled"])
        self.assertEqual(value["telemetry"]["retention_days"], 30)
