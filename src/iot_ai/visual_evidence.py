# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-04
"""Host-owned visual-run evidence. Model JSON cannot issue a trusted handle.

A trusted host adapter executes capture and measurement. This module owns the
receipt, confined file reads and PNG validation. It is not a remote attestation
service or a full accessibility/visual-quality certification.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import tempfile
import weakref
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from .util import atomic_json, open_secure

VIEWPORTS = {"desktop": (1280, 800), "tablet": (768, 1024), "mobile": (390, 844)}
MAX_FILE = 16 * 1024 * 1024
SHA = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, eq=False)
class VisualEvidenceHandle:
    """Opaque in-process capability, issued only after the configured adapter runs."""
    root: Path
    run_id: str
    source_sha256: str
    receipt_sha256: str


_ISSUED: weakref.WeakKeyDictionary[VisualEvidenceHandle, tuple[Any, ...]] = weakref.WeakKeyDictionary()


def _read(root: Path, name: str) -> bytes:
    parts = PurePosixPath(name)
    if not name or parts.is_absolute() or ".." in parts.parts or "\\" in name or ":" in name:
        raise ValueError("visual-artifact-path-invalid")
    with open_secure(root / name, allowed_roots=[root], max_bytes=MAX_FILE) as stream:
        return stream.read(MAX_FILE + 1)


def validate_png(data: bytes, expected: tuple[int, int]) -> None:
    """Validate bounded non-interlaced 8-bit browser PNG, including CRC and IDAT.

    This deliberately supports only the formats our screenshot adapter emits,
    not every image encoding. It does not execute or trust image metadata.
    """
    if len(expected) != 2 or any(type(v) is not int or v < 1 or v > 8192 for v in expected):
        raise ValueError("visual-viewport-limits")
    if len(data) > MAX_FILE or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("visual-image-not-png")
    offset, header, ended, idat_closed = 8, None, False, False
    compressed = bytearray()
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("visual-png-truncated")
        length = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        end = offset + length + 12
        if end > len(data) or length > MAX_FILE:
            raise ValueError("visual-png-length")
        body = data[offset + 8:end - 4]
        if zlib.crc32(kind + body) & 0xffffffff != int.from_bytes(data[end - 4:end], "big"):
            raise ValueError("visual-png-crc")
        if header is None and kind != b"IHDR":
            raise ValueError("visual-png-header")
        if kind == b"IHDR":
            if header is not None or length != 13:
                raise ValueError("visual-png-header")
            header = struct.unpack(">IIBBBBB", body)
            width, height, depth, color, compression, filtering, interlace = header
            if (width, height) != expected or depth != 8 or color not in {0, 2, 4, 6} or any((compression, filtering, interlace)):
                raise ValueError("visual-png-dimensions-or-format")
        elif kind == b"IDAT":
            if idat_closed:
                raise ValueError("visual-png-idat-order")
            compressed.extend(body)
        elif kind == b"IEND":
            if length or not compressed or end != len(data):
                raise ValueError("visual-png-trailer")
            ended = True
            break
        else:
            if compressed:
                idat_closed = True
            if kind[0] & 32 == 0 and kind != b"PLTE":
                raise ValueError("visual-png-unknown-critical")
        offset = end
    if header is None or not ended:
        raise ValueError("visual-png-incomplete")
    width, height, _, color, *_ = header
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
    stride = width * channels + 1
    expected_bytes = stride * height
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(bytes(compressed), expected_bytes + 1)
    if len(pixels) != expected_bytes or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("visual-png-data")
    if any(pixels[i] > 4 for i in range(0, len(pixels), stride)):
        raise ValueError("visual-png-filter")



def capture_visual_run(
    *, evidence_root: Path, run_id: str, source_digest: Callable[[], str],
    capture: Callable[[Path, Mapping[str, tuple[int, int]]], Mapping[str, Any]],
) -> VisualEvidenceHandle:
    """Trusted host call only; not a tool accepting provider-controlled callbacks.

    capture writes three PNGs and one measurement report per viewport. The
    adapter must execute those measurements, not copy the model's assertions.
    """
    if not isinstance(run_id, str) or not run_id or len(run_id) > 200:
        raise ValueError("visual-run-id-invalid")
    before = source_digest()
    if not isinstance(before, str) or not SHA.fullmatch(before):
        raise ValueError("visual-source-digest-invalid")
    evidence_root.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="visual-", dir=evidence_root))
    returned = dict(capture(root, dict(VIEWPORTS)))
    if source_digest() != before:
        raise ValueError("visual-source-changed-during-capture")
    if not isinstance(returned.get("browser_version"), str) or not returned["browser_version"]:
        raise ValueError("visual-browser-version-missing")
    rows = {}
    for name, dimensions in VIEWPORTS.items():
        image_name, report_name = f"{name}.png", f"{name}.json"
        image = _read(root, image_name)
        validate_png(image, dimensions)
        report = _read(root, report_name)
        json.loads(report)
        rows[name] = {"width": dimensions[0], "height": dimensions[1], "image": image_name,
                      "image_sha256": hashlib.sha256(image).hexdigest(), "report": report_name,
                      "report_sha256": hashlib.sha256(report).hexdigest()}
    receipt = {"schema": "iot-ai.host-visual-evidence.v1", "run_id": run_id, "source_sha256": before,
               "browser_version": returned["browser_version"], "viewports": rows}
    atomic_json(root / "receipt.json", receipt)
    receipt_digest = hashlib.sha256(_read(root, "receipt.json")).hexdigest()
    handle = VisualEvidenceHandle(root, run_id, before, receipt_digest)
    _ISSUED[handle] = (root, run_id, before, receipt_digest)
    return handle


def verify_visual_run(handle: Any, *, run_id: str | None, source_sha256: str | None) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(handle, VisualEvidenceHandle) or _ISSUED.get(handle) != (handle.root, handle.run_id, handle.source_sha256, handle.receipt_sha256):
        return {"decision": "block", "missing": ["trusted-visual-run-required"]}
    if not run_id or run_id != handle.run_id:
        errors.append("visual-run-mismatch")
    if not source_sha256 or source_sha256 != handle.source_sha256:
        errors.append("visual-source-mismatch")
    try:
        data = _read(handle.root, "receipt.json")
        if hashlib.sha256(data).hexdigest() != handle.receipt_sha256:
            raise ValueError("visual-receipt-changed")
        receipt = json.loads(data)
        for name, dimensions in VIEWPORTS.items():
            row = receipt["viewports"][name]
            image = _read(handle.root, row["image"])
            validate_png(image, dimensions)
            report_data = _read(handle.root, row["report"])
            if hashlib.sha256(image).hexdigest() != row["image_sha256"] or hashlib.sha256(report_data).hexdigest() != row["report_sha256"]:
                raise ValueError("visual-artifact-changed")
            report = json.loads(report_data)
            if report.get("viewport") != {"width": dimensions[0], "height": dimensions[1]}:
                errors.append(f"viewport-measurement:{name}")
            for field in ("overflow_count", "clipping_count"):
                if type(report.get(field)) is not int or report[field] != 0:
                    errors.append(f"{field}:{name}")
            a11y = report.get("accessibility", {})
            if not isinstance(a11y, dict) or not a11y.get("engine") or type(a11y.get("checks_run")) is not int or a11y["checks_run"] < 1 or a11y.get("violations") != []:
                errors.append(f"accessibility:{name}")
            states = report.get("states", {})
            if not isinstance(states, dict) or any(states.get(item) != "pass" for item in ("loading", "empty", "error")):
                errors.append(f"interaction-states:{name}")
    except (ValueError, TypeError, KeyError, OSError, OverflowError, zlib.error, RecursionError):
        errors.append("visual-artifact-verification-failed")
    return {"decision": "block" if errors else "pass", "missing": sorted(set(errors)),
            "run_id": handle.run_id, "source_sha256": handle.source_sha256,
            "receipt_sha256": handle.receipt_sha256, "checks_scope": "adapter-measured-render-and-interaction",
            "full_accessibility_certification": False, "visual_quality_proven": False}
