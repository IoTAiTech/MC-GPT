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
    probe = visual_runner_probe(explicit=tool_available)
    if not probe.get("available"):
        return {
            "decision": UNAVAILABLE,
            "required": True,
            "visual_acceptance_claim": False,
            "visual_quality_proven": False,
            "browser_render_required": True,
            "screenshot_evidence_required": True,
            "accessibility_required": True,
            "real_visual_runner": False,
            "runner": probe,
            "missing": ["browser-tool"],
        }
    payload = dict(evidence or {})
    missing: list[str] = []
    recomputed: list[str] = []
    viewports = payload.get("viewports") or {}
    paths = payload.get("screenshot_paths") or {}
    for name in REQUIRED_VIEWPORTS:
        row = viewports.get(name) if isinstance(viewports, Mapping) else None
        path_value = None
        if isinstance(paths, Mapping):
            path_value = paths.get(name)
        elif isinstance(row, Mapping):
            path_value = row.get("path") or row.get("screenshot_path")
        if not path_value:
            missing.append(f"viewport-file:{name}")
            continue
        path = Path(str(path_value))
        if not path.is_file() or path.is_symlink() or path.stat().st_size < 32:
            missing.append(f"viewport-file:{name}")
            continue
        digest = _file_sha256(path)
        recomputed.append(digest)
        claimed = None
        if isinstance(row, Mapping):
            claimed = row.get("screenshot_sha256")
        if claimed and (not _digest_ok(claimed) or claimed != digest):
            missing.append(f"viewport-rehash:{name}")
        if isinstance(row, Mapping) and row.get("rendered") is not True:
            missing.append(f"viewport:{name}")
    claimed_digests = payload.get("screenshot_digests") or []
    if isinstance(claimed_digests, list):
        for item in claimed_digests:
            if not _digest_ok(item):
                missing.append("synthetic-screenshot-digest")
                break
        if claimed_digests and recomputed and list(claimed_digests) != recomputed:
            missing.append("screenshot_digests")
    if len(recomputed) < len(REQUIRED_VIEWPORTS):
        missing.append("screenshot_digests")
    for check in ("overflow", "clipping"):
        if payload.get(check) is not True:
            missing.append(check)
    a11y = payload.get("accessibility")
    if a11y is True and not payload.get("accessibility_executed"):
        missing.append("accessibility-execution")
    elif a11y is not True:
        missing.append("accessibility")
    states = payload.get("states") or {}
    for name in REQUIRED_STATES:
        if not (isinstance(states, Mapping) and states.get(name) is True):
            missing.append(f"state:{name}")
    if payload.get("visual_critique") is not True:
        missing.append("visual_critique")
    if not payload.get("browser_version") and not probe.get("version"):
        missing.append("browser-version")
    passed = not missing
    return {
        "decision": "pass" if passed else "block",
        "required": True,
        "visual_acceptance_claim": passed,
        "visual_quality_proven": passed,
        "browser_render_required": True,
        "screenshot_evidence_required": True,
        "accessibility_required": True,
        "real_visual_runner": True,
        "runner": probe,
        "recomputed_screenshot_sha256": recomputed,
        "missing": missing,
    }


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
