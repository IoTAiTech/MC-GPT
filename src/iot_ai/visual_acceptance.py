# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
"""Hard visual-acceptance gate. Guidance is not proof of visual review."""
from __future__ import annotations

import os
import shutil
from typing import Any, Mapping

REQUIRED_VIEWPORTS = ("desktop", "tablet", "mobile")
REQUIRED_STATES = ("loading", "empty", "error")
UNAVAILABLE = "VISUAL_ACCEPTANCE_TOOL_UNAVAILABLE"


def visual_tools_available(*, explicit: bool | None = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    if os.environ.get("IOT_AI_BROWSER_ACCEPTANCE_TOOL"):
        return True
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        if shutil.which(name):
            return True
    return False


def evaluate_visual_acceptance(
    *,
    visual_task: bool,
    require_browser_acceptance: bool,
    tool_available: bool | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    required = bool(visual_task and require_browser_acceptance)
    if not required:
        return {
            "decision": "not-applicable",
            "required": False,
            "visual_acceptance_claim": False,
            "browser_render_required": False,
            "screenshot_evidence_required": False,
            "accessibility_required": False,
            "missing": [],
        }
    available = visual_tools_available(explicit=tool_available)
    if not available:
        return {
            "decision": UNAVAILABLE,
            "required": True,
            "visual_acceptance_claim": False,
            "browser_render_required": True,
            "screenshot_evidence_required": True,
            "accessibility_required": True,
            "missing": ["browser-tool"],
        }
    payload = dict(evidence or {})
    missing: list[str] = []
    viewports = payload.get("viewports") or {}
    for name in REQUIRED_VIEWPORTS:
        row = viewports.get(name) if isinstance(viewports, Mapping) else None
        if not (isinstance(row, Mapping) and row.get("rendered") is True and row.get("screenshot_sha256")):
            missing.append(f"viewport:{name}")
    for check in ("overflow", "clipping"):
        if payload.get(check) is not True:
            missing.append(check)
    if payload.get("accessibility") is not True:
        missing.append("accessibility")
    states = payload.get("states") or {}
    for name in REQUIRED_STATES:
        if not (isinstance(states, Mapping) and states.get(name) is True):
            missing.append(f"state:{name}")
    if payload.get("visual_critique") is not True:
        missing.append("visual_critique")
    digests = payload.get("screenshot_digests") or []
    if not isinstance(digests, list) or len(digests) < len(REQUIRED_VIEWPORTS):
        missing.append("screenshot_digests")
    passed = not missing
    return {
        "decision": "pass" if passed else "block",
        "required": True,
        "visual_acceptance_claim": passed,
        "browser_render_required": True,
        "screenshot_evidence_required": True,
        "accessibility_required": True,
        "missing": missing,
    }
