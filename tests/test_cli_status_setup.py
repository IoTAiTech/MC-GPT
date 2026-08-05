# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from iot_ai.cli import main
from iot_ai.setup_wizard import discover, init_inventory, show_inventory
from iot_ai.status import unified_status

from tests.common import IsolatedHomeTestCase


class CliStatusSetupTests(IsolatedHomeTestCase):
    def _run_cli(self, argv):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(["--home", str(self.home), *argv])
        return code, stream.getvalue()

    def test_cli_help(self) -> None:
        code, output = self._run_cli(["help", "quickstart"])
        self.assertEqual(code, 0)
        self.assertIn("five-minute quickstart", output)

    def test_cli_status_json(self) -> None:
        code, output = self._run_cli(["status", "--json"])
        self.assertEqual(code, 0)
        value = json.loads(output)
        self.assertEqual(value["suite"]["version"], "6.5.0-beta.2")
        self.assertIn("workflow_scores", value)

    def test_cli_settings_show(self) -> None:
        code, output = self._run_cli(["settings", "show"])
        self.assertEqual(code, 0)
        self.assertIn('"ollama"', output)

    def test_setup_discover_does_not_claim_live_readiness(self) -> None:
        with patch("iot_ai.setup_wizard.shutil.which", return_value="/usr/bin/tool"):
            value = discover()
        self.assertEqual(value["providers"]["claude"]["subscription_session"], "unknown-until-live-doctor")
        self.assertFalse(value["providers"]["claude"]["secret_value_recorded"])

    def test_setup_rejects_credentials_in_url(self) -> None:
        with self.assertRaises(ValueError):
            init_inventory(self.home, None, ["dev=https://user:password@example.invalid"], False)

    def test_setup_init_is_dry_run_by_default(self) -> None:
        value = init_inventory(self.home, ".", ["dev=https://example.invalid"], False)
        self.assertEqual(value["decision"], "plan")
        self.assertFalse(show_inventory(self.home).get("configured", True))

    def test_status_has_provider_model_effort_and_scores(self) -> None:
        value = unified_status(self.home, live=False, window="24h")
        self.assertIn("providers", value)
        self.assertIn("workflow_scores", value)
        self.assertIn("effective_profile", value)


if __name__ == "__main__":
    unittest.main()
