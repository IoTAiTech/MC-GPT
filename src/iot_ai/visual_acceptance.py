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
import struct
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


def _png_identity(data: bytes) -> tuple[str, int, int] | None:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    length = struct.unpack(">I", data[8:12])[0]
    if data[12:16] != b"IHDR" or length < 8 or len(data) < 24:
        return None
    width, height = struct.unpack(">II", data[16:24])
    if width < 1 or height < 1:
        return None
    return ("png", width, height)


def _jpeg_identity(data: bytes) -> tuple[str, int, int] | None:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in {0xC0, 0xC1, 0xC2}:
            height, width = struct.unpack(">HH", data[index + 5 : index + 9])
            if width < 1 or height < 1:
                return None
            return ("jpeg", width, height)
        if marker in {0xD8, 0xD9}:
            index += 2
            continue
        if index + 4 > len(data):
            break
        length = struct.unpack(">H", data[index + 2 : index + 4])[0]
        index += 2 + length
    return None


def decode_image_identity(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError:
        return {"ok": False, "reason": "unreadable"}
    identity = _png_identity(data) or _jpeg_identity(data)
    if not identity:
        return {"ok": False, "reason": "not-an-image"}
    fmt, width, height = identity
    return {"ok": True, "format": fmt, "width": width, "height": height}


def _controlled_path(path: Path, controlled_root: Path | None) -> str | None:
    if path.is_symlink() or not path.is_file():
        return "viewport-symlink-or-missing"
    resolved = path.resolve()
    if not controlled_root:
        return "runner-output-dir"
    root = controlled_root.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return "foreign-artifact"
    return None


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
    controlled_value = payload.get("runner_output_dir") or os.environ.get("IOT_AI_VISUAL_OUTPUT_DIR")
    controlled_root = Path(str(controlled_value)).resolve() if controlled_value else None
    if controlled_root is None:
        missing.append("runner-output-dir")
    expected_run = payload.get("run_id")
    captured_run = payload.get("captured_run_id") or probe.get("run_id")
    if expected_run and captured_run and str(expected_run) != str(captured_run):
        missing.append("foreign-run")
    expected_tree = payload.get("source_tree")
    captured_tree = payload.get("captured_tree")
    if expected_tree and captured_tree and str(expected_tree) != str(captured_tree):
        missing.append("stale-tree")
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
        control_error = _controlled_path(path, controlled_root)
        if control_error:
            missing.append(f"{control_error}:{name}" if control_error.startswith("viewport") else control_error)
            continue
        if path.stat().st_size < 32:
            missing.append(f"viewport-file:{name}")
            continue
        identity = decode_image_identity(path)
        if not identity.get("ok"):
            missing.append(f"viewport-not-image:{name}")
            continue
        expected_size = VIEWPORT_PIXELS[name]
        if (int(identity["width"]), int(identity["height"])) != expected_size:
            missing.append(f"viewport-dimensions:{name}")
            continue
        digest = _file_sha256(path)
        recomputed.append(digest)
        claimed = None
        if isinstance(row, Mapping):
            claimed = row.get("screenshot_sha256")
        if claimed and (not _digest_ok(claimed) or claimed != digest):
            missing.append(f"viewport-rehash:{name}")
        if isinstance(row, Mapping) and row.get("origin") not in {"runner", "authorized-runner"}:
            missing.append(f"viewport-origin:{name}")
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
        runner_layout = payload.get("runner_layout") if isinstance(payload.get("runner_layout"), Mapping) else {}
        if runner_layout.get(check) is True:
            continue
        if payload.get(check) is True:
            missing.append(f"{check}-model-authored")
        else:
            missing.append(check)
    runner_a11y = payload.get("runner_accessibility") if isinstance(payload.get("runner_accessibility"), Mapping) else {}
    if not (runner_a11y.get("tool") and runner_a11y.get("decision") == "pass"):
        missing.append("accessibility-runner")
    if payload.get("accessibility") is True and not runner_a11y:
        missing.append("accessibility-forged")
    states = payload.get("states") or {}
    runner_states = payload.get("runner_states") if isinstance(payload.get("runner_states"), Mapping) else states
    for name in REQUIRED_STATES:
        if not (isinstance(runner_states, Mapping) and runner_states.get(name) is True):
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
