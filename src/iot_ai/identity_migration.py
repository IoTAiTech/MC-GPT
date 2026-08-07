# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Transactional migration from the superseded AI-IoT.Tech state namespace."""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from .logging_config import append_event, log_locations
from .paths import config_root, data_root, log_root
from .util import atomic_json, load_json, sha256_file, utc_now

_SCHEMA = "iot-ai.brand-identity-migration.v1"


def receipt_path(user_home: Path) -> Path:
    return user_home / ".iot-ai-migrations" / "brand-identity-latest.json"


def _path_pairs(user_home: Path) -> list[tuple[str, Path, Path]]:
    """Return non-overlapping legacy-to-canonical namespace moves."""
    if os.name == "nt":
        app = user_home / "AppData" / "Roaming"
        local = user_home / "AppData" / "Local"
        return [
            ("config", app / "AI-IoT.Tech" / "IOT-AI-Suite" / "v1", config_root(user_home)),
            ("data-and-logs", local / "AI-IoT.Tech" / "IOT-AI-Suite" / "v1", data_root(user_home)),
        ]
    return [
        ("config", user_home / ".config" / "ai-iot-tech" / "iot-ai-suite" / "v1", config_root(user_home)),
        ("data", user_home / ".local" / "share" / "ai-iot-tech" / "iot-ai-suite" / "v1", data_root(user_home)),
        ("state", user_home / ".local" / "state" / "ai-iot-tech" / "iot-ai-suite" / "v1", log_root(user_home).parent),
    ]

def _tree_manifest(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    if root.is_symlink():
        raise ValueError(f"symlink root is not migratable: {root}")
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink is not migratable: {path}")
        if path.is_file():
            rows.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path), "size": path.stat().st_size})
    return rows


def _manifest_digest(rows: list[dict[str, Any]]) -> str:
    import json
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def plan(user_home: Path) -> dict[str, Any]:
    items = []
    blockers = []
    seen_sources: set[Path] = set()
    seen_destinations: set[Path] = set()
    for kind, raw_source, raw_destination in _path_pairs(user_home):
        source = raw_source.resolve()
        destination = raw_destination.resolve()
        if source in seen_sources:
            continue
        if destination in seen_destinations:
            blockers.append({"kind": kind, "reason": "duplicate-canonical-destination", "destination": str(destination)})
            continue
        seen_sources.add(source)
        seen_destinations.add(destination)
        manifest = _tree_manifest(source)
        exists = source.exists()
        destination_exists = destination.exists()
        if exists and destination_exists:
            blockers.append({"kind": kind, "reason": "canonical-destination-already-exists", "source": str(source), "destination": str(destination)})
        items.append(
            {
                "kind": kind,
                "source": str(source),
                "destination": str(destination),
                "source_exists": exists,
                "destination_exists": destination_exists,
                "file_count": len(manifest),
                "manifest_sha256": _manifest_digest(manifest),
                "manifest": manifest,
            }
        )
    return {
        "schema": _SCHEMA,
        "decision": "block" if blockers else "plan",
        "canonical_company": "IoT-AI.Tech",
        "superseded_company": "AI-IoT.Tech",
        "items": items,
        "blockers": blockers,
        "no_duplicate_active_writer": not blockers,
        "logs": log_locations(user_home),
    }


def apply(user_home: Path) -> dict[str, Any]:
    value = plan(user_home)
    if value["decision"] == "block":
        return value
    transaction_id = f"brand-{uuid.uuid4().hex[:12]}"
    moved = []
    try:
        for item in value["items"]:
            source = Path(item["source"])
            destination = Path(item["destination"])
            if not source.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.stat().st_dev != destination.parent.stat().st_dev:
                raise RuntimeError("brand migration requires atomic rename on one filesystem")
            os.replace(source, destination)
            moved.append({"kind": item["kind"], "source": str(source), "destination": str(destination), "manifest_sha256": item["manifest_sha256"]})
    except Exception:
        for item in reversed(moved):
            source = Path(item["source"])
            destination = Path(item["destination"])
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, source)
        raise
    result = {
        **value,
        "decision": "pass",
        "transaction_id": transaction_id,
        "moved": moved,
        "applied_at": utc_now(),
        "rollback_available": bool(moved),
    }
    append_event(user_home, "brand_identity.migrated", result, audit=True, correlation_id=transaction_id)
    # Bind rollback to the exact post-migration state, including the migration
    # audit record written into the canonical log namespace.
    for item in moved:
        destination = Path(item["destination"])
        item["manifest_sha256"] = _manifest_digest(_tree_manifest(destination))
    atomic_json(receipt_path(user_home), result)
    return result


def rollback(user_home: Path) -> dict[str, Any]:
    receipt = load_json(receipt_path(user_home), {}) or {}
    if not receipt:
        return {"schema": _SCHEMA, "decision": "block", "reason": "no-brand-migration-receipt"}
    blockers = []
    for item in receipt.get("moved", []):
        source = Path(item["source"])
        destination = Path(item["destination"])
        manifest = _tree_manifest(destination)
        if source.exists():
            blockers.append({"kind": item["kind"], "reason": "legacy-source-recreated", "path": str(source)})
        if not destination.exists():
            blockers.append({"kind": item["kind"], "reason": "canonical-destination-missing", "path": str(destination)})
        elif _manifest_digest(manifest) != item["manifest_sha256"]:
            blockers.append({"kind": item["kind"], "reason": "canonical-state-changed-since-migration", "path": str(destination)})
    if blockers:
        return {"schema": _SCHEMA, "decision": "block", "reason": "rollback-precondition-failed", "blockers": blockers}
    restored = []
    for item in reversed(receipt.get("moved", [])):
        source = Path(item["source"])
        destination = Path(item["destination"])
        source.parent.mkdir(parents=True, exist_ok=True)
        os.replace(destination, source)
        restored.append(str(source))
    receipt_path(user_home).unlink(missing_ok=True)
    return {"schema": _SCHEMA, "decision": "pass", "restored": restored, "logs": log_locations(user_home)}


def status(user_home: Path) -> dict[str, Any]:
    value = plan(user_home)
    value["migration_receipt_present"] = receipt_path(user_home).is_file()
    return value
