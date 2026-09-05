# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
"""Hard visual-acceptance gate. Model-authored hashes are not proof."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .visual_evidence import verify_visual_run

REQUIRED_VIEWPORTS = ("desktop", "tablet", "mobile")
VIEWPORT_PIXELS = {"desktop": (1280, 800), "tablet": (768, 1024), "mobile": (390, 844)}
REQUIRED_STATES = ("loading", "empty", "error")
UNAVAILABLE = "VISUAL_ACCEPTANCE_TOOL_UNAVAILABLE"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SYNTHETIC_DIGEST = re.compile(r"^([0-9a-f])\1{63}$")


def _chrome_names() -> tuple[str, ...]:
    return ("google-chrome", "chromium", "chromium-browser", "chrome")


def _probe_command(command: list[str], timeout: float = 8.0) -> bool:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def visual_runner_probe(*, explicit: bool | None = None) -> dict[str, Any]:
    """A PATH browser is not enough. The runner must pass a capability probe."""

    if explicit is False:
        return {"available": False, "reason": "explicitly-disabled", "command": None, "version": None}
    env_tool = os.environ.get("IOT_AI_BROWSER_ACCEPTANCE_TOOL")
    if env_tool:
        path = Path(env_tool)
        if path.is_file() and os.access(path, os.X_OK) and _probe_command([str(path), "--probe"]):
            return {"available": True, "reason": "env-runner", "command": str(path), "version": "env"}
        return {"available": False, "reason": "env-runner-probe-failed", "command": env_tool, "version": None}
    if explicit is True:
        # Tests may inject a proven runner without spawning Chrome.
        return {"available": True, "reason": "explicit-runner", "command": "explicit", "version": "test"}
    for name in _chrome_names():
        binary = shutil.which(name)
        if not binary:
            continue
        if _probe_command([binary, "--headless=new", "--disable-gpu", "--dump-dom", "about:blank"]):
            version = ""
            try:
                ver = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5, check=False)
                version = (ver.stdout or ver.stderr or "").strip()[:120]
            except (OSError, subprocess.TimeoutExpired):
                version = name
            return {"available": True, "reason": "chrome-probe", "command": binary, "version": version or name}
    return {"available": False, "reason": "no-callable-runner", "command": None, "version": None}


def visual_tools_available(*, explicit: bool | None = None) -> bool:
    return bool(visual_runner_probe(explicit=explicit).get("available"))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_ok(value: Any) -> bool:
    text = str(value or "")
    return bool(HEX64.fullmatch(text)) and not SYNTHETIC_DIGEST.fullmatch(text)


def evaluate_visual_acceptance(
    *,
    visual_task: bool,
    require_browser_acceptance: bool,
    tool_available: bool | None = None,
    evidence: Mapping[str, Any] | None = None,
    runner_evidence: Any = None,
    expected_run_id: str | None = None,
    expected_source_sha256: str | None = None,
) -> dict[str, Any]:
    required = bool(visual_task and require_browser_acceptance)
    if not required:
        return {
            "decision": "not-applicable",
            "required": False,
            "visual_acceptance_claim": False,
            "visual_quality_proven": False,
            "browser_render_required": False,
            "screenshot_evidence_required": False,
            "accessibility_required": False,
            "real_visual_runner": False,
            "missing": [],
        }
    # Tool discovery is not authorization; model-authored evidence is not read.
    # A configured host adapter must have produced the opaque capability.
    if runner_evidence is None:
        return {"decision": UNAVAILABLE if not tool_available else "block", "required": True,
                "visual_acceptance_claim": False, "visual_quality_proven": False,
                "browser_render_required": True, "screenshot_evidence_required": True,
                "accessibility_required": True, "real_visual_runner": False,
                "missing": ["trusted-visual-run-required"]}
    verified = verify_visual_run(runner_evidence, run_id=expected_run_id, source_sha256=expected_source_sha256)
    return {**verified, "required": True, "visual_acceptance_claim": verified["decision"] == "pass",
            "browser_render_required": True, "screenshot_evidence_required": True,
            "accessibility_required": True, "real_visual_runner": verified["decision"] == "pass",
            "visual_quality_proven": False}


def capture_viewport_screenshot(url: str, destination: Path, *, viewport: str, runner: str | None = None) -> dict[str, Any]:
    """Capture one real screenshot. Fail closed when the runner cannot execute."""

    probe = visual_runner_probe()
    binary = runner or probe.get("command")
    if not binary or binary in {"explicit"} or not probe.get("available"):
        return {"decision": UNAVAILABLE, "path": None, "sha256": None}
    width, height = VIEWPORT_PIXELS.get(viewport, (1280, 800))
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = destination.resolve()
    command = [
        str(binary),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        f"--screenshot={target}",
        str(url),
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, timeout=20, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"decision": UNAVAILABLE, "error": str(exc), "path": None, "sha256": None}
    if completed.returncode != 0 or not target.is_file():
        return {"decision": UNAVAILABLE, "error": "screenshot-missing", "path": None, "sha256": None}
    return {"decision": "pass", "path": str(target), "sha256": _file_sha256(target), "viewport": viewport}
