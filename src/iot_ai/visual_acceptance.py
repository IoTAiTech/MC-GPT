# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-05
"""Orchestrator-owned visual runs. Model-authored files/booleans grant no pass."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import struct
import subprocess
import sys
import uuid
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .util import open_secure

REQUIRED_VIEWPORTS = ("desktop", "tablet", "mobile")
VIEWPORT_PIXELS = {"desktop": (1280, 800), "tablet": (768, 1024), "mobile": (390, 844)}
REQUIRED_STATES = ("loading", "empty", "error")
UNAVAILABLE = "VISUAL_ACCEPTANCE_TOOL_UNAVAILABLE"
MAX_IMAGE_BYTES = 12_000_000
WEB_SUFFIXES = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".woff2"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _read(path: Path, root: Path, limit: int) -> bytes:
    with open_secure(path, root, max_bytes=limit) as stream:
        return stream.read(limit + 1)


def validate_screenshot(data: bytes, width: int, height: int) -> None:
    """Validate Chromium's bounded, non-interlaced 8-bit RGB/RGBA PNG output."""
    if (isinstance(width, bool) or isinstance(height, bool)
            or not isinstance(width, int) or not isinstance(height, int)
            or not 1 <= width <= 4096 or not 1 <= height <= 4096
            or width * height > 4_000_000):
        raise ValueError("screenshot-dimension-limit")
    if not isinstance(data, bytes) or len(data) > MAX_IMAGE_BYTES or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("screenshot-format-invalid")
    offset, channels, ended, idat_started, idat_ended = 8, 0, False, False, False
    compressed = bytearray()
    for index in range(2048):
        if offset + 12 > len(data):
            raise ValueError("screenshot-truncated")
        size, kind = struct.unpack(">I4s", data[offset:offset + 8])
        end = offset + 12 + size
        if end > len(data):
            raise ValueError("screenshot-truncated")
        chunk = data[offset + 8:offset + 8 + size]
        crc = struct.unpack(">I", data[offset + 8 + size:end])[0]
        if zlib.crc32(kind + chunk) & 0xffffffff != crc:
            raise ValueError("screenshot-crc-invalid")
        if index == 0:
            if kind != b"IHDR" or size != 13:
                raise ValueError("screenshot-header-invalid")
            w, h, bits, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunk)
            if (w, h) != (width, height) or bits != 8 or color not in {2, 6} or any((compression, filtering, interlace)):
                raise ValueError("screenshot-dimensions-or-format-invalid")
            channels = 3 if color == 2 else 4
        elif kind == b"IHDR":
            raise ValueError("screenshot-duplicate-header")
        elif kind == b"IDAT":
            if idat_ended:
                raise ValueError("screenshot-idat-order-invalid")
            idat_started = True
            compressed.extend(chunk)
        elif kind == b"IEND":
            if size or not idat_started or end != len(data):
                raise ValueError("screenshot-end-invalid")
            ended = True
            break
        elif not kind[0] & 32:
            raise ValueError("screenshot-critical-chunk-unsupported")
        elif idat_started:
            idat_ended = True
        offset = end
    if not ended:
        raise ValueError("screenshot-end-missing")
    row_size = width * channels + 1
    expected = row_size * height
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(compressed), expected + 1)
    if len(raw) != expected or decoder.unconsumed_tail or decoder.unused_data or not decoder.eof:
        raise ValueError("screenshot-pixels-invalid")
    if any(raw[index] > 4 for index in range(0, expected, row_size)):
        raise ValueError("screenshot-filter-invalid")


@dataclass(frozen=True)
class TrustedVisualRun:
    """Created by the orchestrator after its runner returns; never from JSON."""
    artifact_root: Path
    run_id: str
    source_digest: str
    receipt_digest: str
    runner_digest: str


def _runner_command() -> list[str]:
    return [sys.executable, str(Path(__file__).with_name("visual_runner.py"))]


def _invoke(args: list[str], request: dict | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    # No inherited provider tokens, CLI homes or arbitrary PYTHONPATH.
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "DISPLAY", "IOT_AI_CHROMIUM", "IOT_AI_VISUAL_ISOLATED_CONTAINER"}}
    env.update({"DO_NOT_TRACK": "1", "PYTHONNOUSERSITE": "1"})
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, start_new_session=(os.name != "nt"))
    try:
        out, err = process.communicate(_canonical(request) if request is not None else None, timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.communicate()
        raise
    if len(out) > 262144 or len(err) > 262144:
        raise ValueError("visual-runner-output-limit")
    return subprocess.CompletedProcess(args, process.returncode, out, err)


def visual_runner_probe(*, explicit: bool | None = None) -> dict[str, Any]:
    if explicit is False:
        return {"available": False, "reason": "explicitly-disabled"}
    try:
        result = _invoke([*_runner_command(), "--probe"], timeout=20)
        payload = json.loads(result.stdout)
        if result.returncode or payload.get("schema") != "iot-ai.visual-runner-probe.v1" or payload.get("available") is not True:
            raise ValueError("unavailable")
        return payload
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return {"available": False, "reason": "native-visual-runner-unavailable"}


def visual_tools_available(*, explicit: bool | None = None) -> bool:
    return visual_runner_probe(explicit=explicit).get("available") is True


def evaluate_visual_acceptance(
    *, visual_task: bool, require_browser_acceptance: bool,
    tool_available: bool | None = None, evidence: Mapping[str, Any] | None = None,
    trusted_run: TrustedVisualRun | None = None,
) -> dict[str, Any]:
    """Verify the controlled runner output, not model-supplied evidence paths."""
    required = bool(visual_task and require_browser_acceptance)
    base = {"required": required, "visual_acceptance_claim": False,
            "visual_quality_proven": False, "full_accessibility_certification": False,
            "human_design_review_required": required, "real_visual_runner": False,
            "browser_render_required": required, "screenshot_evidence_required": required,
            "accessibility_required": required}
    if not required:
        return {**base, "decision": "not-applicable", "missing": []}
    if tool_available is False:
        return {**base, "decision": UNAVAILABLE, "missing": ["browser-tool"]}
    # A claimed available tool and valid-looking images do not establish origin.
    if not isinstance(trusted_run, TrustedVisualRun):
        return {**base, "decision": "block", "missing": ["orchestrator-run-receipt-required"]}
    missing, hashes = [], []
    try:
        raw = _read(trusted_run.artifact_root / "receipt.json", trusted_run.artifact_root, 262144)
        if _sha(raw) != trusted_run.receipt_digest:
            raise ValueError("visual-receipt-digest-mismatch")
        payload = json.loads(raw)
        if (payload.get("schema") != "iot-ai.visual-runner-result.v1"
                or payload.get("run_id") != trusted_run.run_id
                or payload.get("source_digest") != trusted_run.source_digest
                or payload.get("runner_digest") != trusted_run.runner_digest):
            raise ValueError("visual-run-binding-mismatch")
        viewports = payload.get("viewports")
        if not isinstance(viewports, dict) or set(viewports) != set(REQUIRED_VIEWPORTS):
            raise ValueError("visual-viewports-invalid")
        for name, (width, height) in VIEWPORT_PIXELS.items():
            row = viewports[name]
            # Fixed filenames: no caller-selected paths, traversal or arbitrary reads.
            data = _read(trusted_run.artifact_root / f"{name}.png", trusted_run.artifact_root, MAX_IMAGE_BYTES)
            validate_screenshot(data, width, height)
            digest = _sha(data)
            hashes.append(digest)
            if row.get("screenshot_sha256") != digest or row.get("width") != width or row.get("height") != height:
                missing.append(f"viewport-binding:{name}")
            if row.get("horizontal_overflow") is not False or row.get("clipping") is not False:
                missing.append(f"viewport-layout:{name}")
        if len(set(hashes)) != 3:
            missing.append("duplicate-viewport-artifacts")
        checks = payload.get("checks") or {}
        for check in ("automated_accessibility", "interaction_states", "network_isolation", "page_errors_absent"):
            row = checks.get(check)
            if not isinstance(row, dict) or row.get("executed") is not True or row.get("passed") is not True:
                missing.append(check)
        if payload.get("decision") != "pass" or not payload.get("browser_version"):
            missing.append("runner-result")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, struct.error, zlib.error):
        missing.append("visual-evidence-invalid")
    passed = not missing
    return {**base, "decision": "pass" if passed else "block", "visual_acceptance_claim": passed,
            "real_visual_runner": True, "acceptance_scope": "static-preview-automated-v1",
            "recomputed_screenshot_sha256": hashes, "missing": sorted(set(missing))}


def run_visual_acceptance(
    *, source_root: Path, entry: str, artifact_parent: Path, run_id: str,
) -> dict[str, Any]:
    """Run reviewed local static-preview code only for operator-selected scope."""
    try:
        root = source_root.absolute()
        if root == Path(root.anchor) or not root.is_dir() or root.is_symlink():
            raise ValueError("visual-scope-invalid")
        assets = {}
        total = 0
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if any(part.startswith(".") or part in {"node_modules", "venv", "__pycache__"} for part in rel.parts):
                continue
            if path.suffix.lower() not in WEB_SUFFIXES or path.is_dir():
                continue
            data = _read(path, root, MAX_IMAGE_BYTES)
            assets[rel.as_posix()] = _sha(data)
            total += len(data)
            if len(assets) > 512 or total > 32_000_000:
                raise ValueError("visual-source-budget-exceeded")
        if entry not in assets or not entry.endswith(".html"):
            raise ValueError("visual-entry-invalid")
        source_digest = _sha(_canonical(assets))
        output = artifact_parent / ("visual-" + uuid.uuid4().hex)
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
        runner = Path(__file__).with_name("visual_runner.py")
        runner_digest = _sha(_read(runner, runner.parent, 262144))
        request = {"run_id": run_id, "source_root": str(root), "entry": entry,
                   "assets": assets, "source_digest": source_digest,
                   "artifact_root": str(output), "runner_digest": runner_digest,
                   "viewports": VIEWPORT_PIXELS}
        completed = _invoke(_runner_command(), request, timeout=90)
        if completed.returncode == 78:
            return {"decision": UNAVAILABLE, "visual_acceptance_claim": False, "missing": ["optional-browser-runtime-unavailable"]}
        if completed.returncode not in {0, 1} or _sha(_read(runner, runner.parent, 262144)) != runner_digest:
            raise ValueError("visual-runner-failed-or-changed")
        receipt_digest = _sha(_read(output / "receipt.json", output, 262144))
        trusted = TrustedVisualRun(output, run_id, source_digest, receipt_digest, runner_digest)
        return {**evaluate_visual_acceptance(visual_task=True, require_browser_acceptance=True, trusted_run=trusted),
                "run_id": run_id, "source_digest": source_digest, "receipt_digest": receipt_digest,
                "artifact_ref": output.name}
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return {"decision": "block", "visual_acceptance_claim": False, "missing": ["visual-run-failed"]}


def capture_viewport_screenshot(url: str, destination: Path, *, viewport: str, runner: str | None = None) -> dict[str, Any]:
    """Legacy URL capture cannot grant acceptance or arbitrary network access."""
    return {"decision": UNAVAILABLE, "path": None, "sha256": None,
            "reason": "use-operator-scoped-static-visual-run"}
