# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-04
"""An authorized adapter may still malfunction; malformed reports fail closed."""
import json

import pytest

from iot_ai.visual_evidence import capture_visual_run
from tests.test_runtime_boundary_evidence import simulated_capture


@pytest.mark.parametrize("report", [None, [], "not-an-object", 42, True])
def test_non_object_adapter_report_cannot_mint_evidence(tmp_path, report):
    def broken(root, viewports):
        result = simulated_capture(root, viewports)
        (root / "mobile.json").write_text(json.dumps(report), encoding="utf-8")
        return result

    with pytest.raises(ValueError, match="visual-measurement-object-required"):
        capture_visual_run(evidence_root=tmp_path, run_id="adapter-failure",
            source_digest=lambda: "a" * 64, capture=broken)
