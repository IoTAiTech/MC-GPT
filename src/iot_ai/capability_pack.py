# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
"""Portable, deterministic and secret-safe capability archives.

The format applies the useful AgentGem pattern—one neutral archive and one
operation contract across REST, MCP and OpenAPI—without making the public
Community package a hosted marketplace or copying provider credentials.
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .suite_version import SUITE_VERSION
from .util import sha256_file

PACK_SCHEMA = "iot-ai.capability-pack.v1"
MANIFEST_SCHEMA = "iot-ai.capability-pack-manifest.v1"
_FIXED_TIME = (2026, 1, 1, 0, 0, 0)
_SECRET_KEYS = re.compile(
    r"(?i)(?:secret|token|password|passwd|api[_-]?key|authorization|cookie|credential|private[_-]?key)"
)
_SECRET_VALUES = re.compile(
    r"(?i)(?:(?:sk|xai|ghp|AIza)[-_A-Za-z0-9.]{8,}|Bearer\s+[-_A-Za-z0-9.~+/=]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
_BOUNDARIES = {"mcp", "rest", "openapi"}


def _redact(value: Any, key: str = "") -> Any:
    if key and _SECRET_KEYS.search(key):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {str(k): _redact(v, str(k)) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return _SECRET_VALUES.sub("<redacted>", value)
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\x00" not in name


def _zip_bytes(files: dict[str, bytes], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, _FIXED_TIME)
            info.compress_type = zipfile.ZIP_STORED if name == "CAPABILITY.json" else zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.create_system = 3
            archive.writestr(info, files[name])


def _contracts(spec: dict[str, Any]) -> dict[str, Any]:
    operations = list(spec.get("operations") or [])
    return {
        "rest": {
            "schema": "iot-ai.capability-rest.v1",
            "base_path": "/capabilities/" + str(spec["name"]),
            "operations": operations,
        },
        "mcp": {
            "schema": "iot-ai.capability-mcp.v1",
            "server": str(spec["name"]),
            "tools": [
                {
                    "name": str(item.get("name") or "operation"),
                    "inputSchema": item.get("input_schema") or {"type": "object"},
                    "outputSchema": item.get("output_schema") or {"type": "object"},
                }
                for item in operations
            ],
        },
        "openapi": {
            "openapi": "3.1.0",
            "info": {"title": str(spec["name"]), "version": str(spec["version"])},
            "paths": {
                f"/capabilities/{spec['name']}/{item.get('name', 'operation')}": {
                    "post": {
                        "operationId": str(item.get("name") or "operation"),
                        "requestBody": {
                            "required": True,
                            "content": {"application/json": {"schema": item.get("input_schema") or {"type": "object"}}},
                        },
                        "responses": {
                            "200": {
                                "description": "Capability result",
                                "content": {"application/json": {"schema": item.get("output_schema") or {"type": "object"}}},
                            }
                        },
                    }
                }
                for item in operations
            },
        },
    }


def build_pack(spec: Mapping[str, Any], output: Path) -> dict[str, Any]:
    """Build a neutral capability archive and return its immutable identity."""
    clean = _redact(dict(spec))
    name = str(clean.get("name") or "").strip()
    version = str(clean.get("version") or "").strip()
    classification = str(clean.get("classification") or "private")
    if not name or not version:
        raise ValueError("capability pack requires name and version")
    if classification not in {"public", "unlisted", "private", "customer"}:
        raise ValueError("invalid capability pack classification")
    clean.update(
        {
            "schema": PACK_SCHEMA,
            "name": name,
            "version": version,
            "classification": classification,
            "suite_compatibility": {"minimum": SUITE_VERSION, "maximum_exclusive": "7.0.0"},
            "secrets_embedded": False,
            "capture_policy": "redact-by-key-and-value-before-archive",
        }
    )
    requested_targets = {str(value).lower() for value in clean.get("materialize_targets") or []}
    boundaries = sorted(requested_targets & _BOUNDARIES)
    contracts = _contracts(clean)
    files: dict[str, bytes] = {"CAPABILITY.json": _canonical(clean)}
    for boundary in boundaries:
        files[f"CONTRACTS/{boundary}.json"] = _canonical(contracts[boundary])
    for target in sorted(requested_targets - _BOUNDARIES):
        files[f"MATERIALIZERS/{target}.json"] = _canonical(
            {
                "schema": "iot-ai.capability-materializer.v1",
                "target": target,
                "capability": name,
                "mode": "render-only-no-secret-transfer",
            }
        )
    indexed = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "capability": {"name": name, "version": version, "classification": classification},
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(indexed.items())],
        "boundaries": boundaries,
        "secret_scan": "pass",
    }
    files["MANIFEST.json"] = _canonical(manifest)
    files["SHA256SUMS.txt"] = "".join(f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n" for name in sorted(files)).encode("utf-8")
    _zip_bytes(files, output)
    return {
        "decision": "pass",
        "path": str(output),
        "sha256": sha256_file(output, allowed_roots=[Path.cwd().resolve(), Path.home().resolve(), output.parent.resolve()], max_bytes=None),
        "name": name,
        "version": version,
        "classification": classification,
        "boundaries": boundaries,
        "files": len(files),
        "secrets_embedded": False,
    }


def verify_pack(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                errors.append("duplicate-member")
            if any(not _safe_name(name) for name in names):
                errors.append("unsafe-member")
            if any(stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF) for info in infos):
                errors.append("symlink-member")
            if "MANIFEST.json" not in names or "CAPABILITY.json" not in names:
                errors.append("required-member-missing")
            if not errors:
                manifest = json.loads(archive.read("MANIFEST.json"))
                if manifest.get("schema") != MANIFEST_SCHEMA:
                    errors.append("manifest-schema")
                for item in manifest.get("files", []):
                    name = str(item.get("path") or "")
                    if name not in names:
                        errors.append(f"missing:{name}")
                    elif hashlib.sha256(archive.read(name)).hexdigest() != item.get("sha256"):
                        errors.append(f"hash:{name}")
                all_payload = b"\n".join(archive.read(name) for name in names if not name.endswith("/"))
                if _SECRET_VALUES.search(all_payload.decode("utf-8", errors="ignore")):
                    errors.append("secret-like-value")
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError) as exc:
        errors.append(type(exc).__name__)
    return {
        "decision": "pass" if not errors else "block",
        "path": str(path),
        "sha256": sha256_file(path, allowed_roots=[Path.cwd().resolve(), Path.home().resolve(), path.parent.resolve()], max_bytes=None) if path.is_file() else None,
        "errors": errors,
    }
