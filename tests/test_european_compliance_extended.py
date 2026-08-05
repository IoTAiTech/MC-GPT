# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from iot_ai.european_compliance import cra_reporting_schedule, repository_readiness


class EuropeanComplianceExtendedTests(unittest.TestCase):
    def test_cra_schedule_uses_24_and_72_hour_stages(self) -> None:
        discovered = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
        schedule = cra_reporting_schedule(discovered, reportable=True)
        self.assertEqual(schedule["early_warning_due"], "2026-09-12T12:00:00+00:00")
        self.assertEqual(schedule["notification_due"], "2026-09-14T12:00:00+00:00")
        self.assertFalse(schedule["legal_determination_claimed"])

    def test_repository_readiness_is_control_by_control_not_certification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs" / "compliance").mkdir(parents=True)
            for name in (
                "EU_AI_ACT_TECHNICAL_CONTROLS.md",
                "CRA_READINESS.md",
                "GDPR_ENGINEERING_CONTROLS.md",
                "NIS2_CUSTOMER_ALIGNMENT.md",
                "AI_INCIDENT_RESPONSE.md",
            ):
                (root / "docs" / "compliance" / name).write_text("# control\n", encoding="utf-8")
            (root / "SECURITY.md").write_text("# Security\n", encoding="utf-8")
            result = repository_readiness(root)
            self.assertEqual(result["decision"], "pass")
            self.assertFalse(result["legal_certification_claimed"])
            self.assertNotIn("score", result)


if __name__ == "__main__":
    unittest.main()
