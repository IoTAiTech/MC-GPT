# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-18
"""Memoized external-gate receipts. Do not rerun a known immutable authority block."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .paths import config_root
from .util import atomic_json, load_json, utc_now

BLOCKER_ID = "PMD_SCHEMA_RECOVERY_AUTHORITY"
SCHEMA = "iot-ai.external-blocker-receipt.v1"
ISSUER_ANCHOR = Path("/etc/ai-iot/pmd/trust/restart-issuer-anchor.v1.json")
REVOCATIONS = Path("/etc/ai-iot/pmd/trust/restart-issuer-revocations.v1.json")
ENVELOPES = Path("/etc/ai-iot/pmd/recovery-envelopes")


def _public_file_digest(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authority_bundle_inventory() -> dict[str, Any]:
    """Inspect only public authority paths. Never open private keys or credentials."""
    files = {
        "restart-issuer-anchor.v1.json": _public_file_digest(ISSUER_ANCHOR),
        "restart-issuer-revocations.v1.json": _public_file_digest(REVOCATIONS),
    }
    envelope_names: list[str] = []
    if ENVELOPES.is_dir() and not ENVELOPES.is_symlink():
        envelope_names = sorted(item.name for item in ENVELOPES.iterdir() if item.is_file() and not item.is_symlink())
    digest_material = json.dumps({"files": files, "envelopes": envelope_names}, sort_keys=True, separators=(",", ":"))
    return {
        "files": files,
        "envelope_names": envelope_names,
        "authority_bundle_digest": hashlib.sha256(digest_material.encode("utf-8")).hexdigest(),
    }


def _first_missing(inventory: dict[str, Any]) -> tuple[str, str, str] | None:
    files = inventory["files"]
    if files["restart-issuer-anchor.v1.json"] is None:
        return (
            str(ISSUER_ANCHOR),
            "Founder-appointed Recovery Authority | root provisioner",
            "provision the root-owned Ed25519 public issuer anchor at the canonical path from an offline/HSM key; do not mint the private key on this host",
        )
    if files["restart-issuer-revocations.v1.json"] is None:
        return (
            str(REVOCATIONS),
            "Founder-appointed Recovery Authority | root provisioner",
            "provision the signed revocation state next to the issuer anchor",
        )
    names = inventory["envelope_names"]
    bodies = [name for name in names if name.endswith(".json") and not name.endswith(".sig.json")]
    if not bodies:
        return (
            str(ENVELOPES / "<authorization-id>.json"),
            "Founder-appointed Recovery Authority",
            "place one one-use signed recovery authorization envelope; keep the Ed25519 private key offline",
        )
    body = bodies[0]
    sig = body[:-5] + ".sig.json" if body.endswith(".json") else body + ".sig.json"
    if sig not in names:
        return (
            str(ENVELOPES / sig),
            "Founder-appointed Recovery Authority",
            "place the detached signature beside the authorization envelope",
        )
    return None


def receipt_path(user_home: Path) -> Path:
    return config_root(user_home) / "blockers" / f"{BLOCKER_ID}.json"


def evaluate_pmd_schema_recovery(user_home: Path, *, refresh: bool = False) -> dict[str, Any]:
    """Return a memoized AUTHORITY_BLOCKED receipt. Never runs PRCS preflight."""
    inventory = authority_bundle_inventory()
    missing = _first_missing(inventory)
    path = receipt_path(user_home)
    previous = load_json(path) if path.is_file() else None
    if (
        not refresh
        and isinstance(previous, dict)
        and previous.get("blocker_id") == BLOCKER_ID
        and previous.get("authority_bundle_digest") == inventory["authority_bundle_digest"]
        and previous.get("status") == "open"
    ):
        return {
            **previous,
            "memoized": True,
            "normal_preflight_retried": False,
            "state_changed": False,
            "returned_at": utc_now(),
        }
    if missing is None:
        payload = {
            "schema": SCHEMA,
            "blocker_id": BLOCKER_ID,
            "status": "authority-present-recovery-not-executed",
            "security_vulnerability": False,
            "fail_closed_behavior": True,
            "normal_preflight_required_now": False,
            "normal_preflight_retried": False,
            "memoized": False,
            "state_changed": True,
            "authority_bundle_digest": inventory["authority_bundle_digest"],
            "missing_artifact": None,
            "owner": "Founder-appointed Recovery Authority + root provisioner",
            "next_actor": ["Founder-appointed Recovery Authority", "root provisioner"],
            "retry_allowed_after": "authority_bundle_changed",
            "last_checked_at": utc_now(),
            "note": "Public trust files are present. Do not run normal PRCS preflight until the signed prepare/execute transaction is authorized.",
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(path, payload)
        return payload
    artifact, owner, action = missing
    payload = {
        "schema": SCHEMA,
        "blocker_id": BLOCKER_ID,
        "status": "open",
        "result": "PMD_RECOVERY_EXTERNAL_BLOCKER",
        "security_vulnerability": False,
        "fail_closed_behavior": True,
        "normal_preflight_required_now": False,
        "normal_preflight_retried": False,
        "memoized": False,
        "state_changed": not (
            isinstance(previous, dict)
            and previous.get("missing_artifact") == artifact
            and previous.get("authority_bundle_digest") == inventory["authority_bundle_digest"]
        ),
        "authority_bundle_digest": inventory["authority_bundle_digest"],
        "missing_artifact": artifact,
        "owner": owner,
        "secure_provisioning_action": action,
        "next_actor": ["Founder-appointed Recovery Authority", "root provisioner"],
        "retry_allowed_after": "authority_bundle_changed",
        "last_checked_at": utc_now(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, payload)
    return payload
