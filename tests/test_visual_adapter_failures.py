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


@pytest.mark.parametrize("field,value", [
    ("engine", []), ("engine", {"name": "not-text"}),
    ("engine", 42), ("engine", "   "),
    ("checks_run", True), ("checks_run", 0),
    ("violations", {}),
])
def test_malformed_accessibility_measurements_cannot_pass(tmp_path, field, value):
    from iot_ai.visual_evidence import verify_visual_run
    def broken(root, viewports):
        result = simulated_capture(root, viewports)
        path = root / "mobile.json"
        report = json.loads(path.read_text())
        report["accessibility"][field] = value
        path.write_text(json.dumps(report), encoding="utf-8")
        return result
    handle = capture_visual_run(evidence_root=tmp_path, run_id="malformed-a11y",
        source_digest=lambda: "a" * 64, capture=broken)
    result = verify_visual_run(handle, run_id="malformed-a11y", source_sha256="a" * 64)
    assert result["decision"] == "block"


def test_numeric_coercion_is_not_viewport_evidence(tmp_path):
    from iot_ai.visual_evidence import verify_visual_run
    def broken(root, viewports):
        result = simulated_capture(root, viewports)
        path = root / "mobile.json"
        report = json.loads(path.read_text())
        report["viewport"]["width"] = float(report["viewport"]["width"])
        path.write_text(json.dumps(report), encoding="utf-8")
        return result
    handle = capture_visual_run(evidence_root=tmp_path, run_id="numeric-viewport",
        source_digest=lambda: "a" * 64, capture=broken)
    assert verify_visual_run(handle, run_id="numeric-viewport", source_sha256="a" * 64)["decision"] == "block"


def test_source_change_during_capture_never_issues_evidence(tmp_path):
    current = ["a" * 64]
    def changing(root, viewports):
        result = simulated_capture(root, viewports)
        current[0] = "b" * 64
        return result
    with pytest.raises(ValueError, match="visual-source-changed-during-capture"):
        capture_visual_run(evidence_root=tmp_path, run_id="source-drift",
            source_digest=lambda: current[0], capture=changing)


@pytest.mark.parametrize("version", ["", "   ", None, 42, "x" * 201])
def test_browser_version_is_bounded_nonempty_text(tmp_path, version):
    def broken(root, viewports):
        simulated_capture(root, viewports)
        return {"browser_version": version}
    with pytest.raises(ValueError, match="visual-browser-version-missing"):
        capture_visual_run(evidence_root=tmp_path, run_id="invalid-version",
            source_digest=lambda: "a" * 64, capture=broken)
