# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-18
"""Independently provisioned, expiring, one-use Founder authority receipts.

Integrity hashes computed by the same runtime are not authorization. A Founder
receipt must be keyed by a provisioned secret that this process does not mint.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .paths import config_root
from .util import utc_now
from .workspace import connect_write, one

KEY_ENV = "IOT_AI_FOUNDER_AUTHORITY_KEY"
KEY_NAME = "founder_authority.key"
SCHEMA = "iot-ai.founder-authority-receipt.v1"
DEFAULT_TTL_SECONDS = 900


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def key_path(user_home: Path) -> Path:
    return config_root(user_home) / KEY_NAME


def load_founder_key(user_home: Path) -> bytes:
    env = os.environ.get(KEY_ENV, "")
    if env.strip():
        material = env.strip().encode("utf-8")
        if len(material) < 32:
            raise PermissionError("founder-authority-key-too-short")
        return material
    path = key_path(user_home)
    if not path.is_file():
        raise PermissionError("founder-authority-unprovisioned")
    material = path.read_bytes().strip()
    if len(material) < 32:
        raise PermissionError("founder-authority-key-too-short")
    return material


def persist_founder_key(user_home: Path, material: bytes) -> Path:
    if len(material) < 32:
        raise ValueError("founder-authority-key-too-short")
    path = key_path(user_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(material)
    try:
        path.chmod(0o600)
    except OSError:
        # Some filesystems reject chmod; the write already succeeded.
        pass
    return path


def issue_founder_receipt(
    user_home: Path,
    *,
    audience: str,
    subject_id: str,
    digest: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    actor: str = "founder",
) -> dict[str, Any]:
    if not audience or not subject_id or not digest:
        raise ValueError("founder-receipt-requires-audience-subject-digest")
    if not isinstance(digest, str) or len(digest) < 32:
        raise ValueError("founder-receipt-digest-invalid")
    key = load_founder_key(user_home)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=max(30, int(ttl_seconds)))
    body = {
        "schema": SCHEMA,
        "audience": str(audience),
        "subject_id": str(subject_id),
        "digest": str(digest),
        "nonce": secrets.token_hex(16),
        "actor": str(actor),
        "issued_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "expires_at": expires.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    body["signature"] = hmac.new(key, _canonical(body), hashlib.sha256).hexdigest()
    return body


def _parse_when(value: str) -> datetime:
    text = str(value or "").replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def verify_founder_receipt(
    user_home: Path,
    receipt: dict[str, Any] | None,
    *,
    audience: str,
    subject_id: str,
    digest: str,
    consume: bool = True,
) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise PermissionError("founder-receipt-required")
    key = load_founder_key(user_home)
    body = {item: receipt.get(item) for item in (
        "schema", "audience", "subject_id", "digest", "nonce", "actor", "issued_at", "expires_at"
    )}
    expected = hmac.new(key, _canonical(body), hashlib.sha256).hexdigest()
    provided = str(receipt.get("signature") or "")
    if not provided or not hmac.compare_digest(expected, provided):
        raise PermissionError("founder-receipt-signature-invalid")
    if receipt.get("schema") != SCHEMA:
        raise PermissionError("founder-receipt-schema-invalid")
    if receipt.get("audience") != audience:
        raise PermissionError("founder-receipt-audience-mismatch")
    if receipt.get("subject_id") != subject_id:
        raise PermissionError("founder-receipt-subject-mismatch")
    if receipt.get("digest") != digest:
        raise PermissionError("founder-receipt-digest-mismatch")
    nonce = str(receipt.get("nonce") or "")
    if len(nonce) < 16:
        raise PermissionError("founder-receipt-nonce-invalid")
    now = datetime.now(timezone.utc)
    try:
        expires = _parse_when(str(receipt.get("expires_at")))
    except ValueError as exc:
        raise PermissionError("founder-receipt-expiry-invalid") from exc
    if expires <= now:
        raise PermissionError("founder-receipt-expired")
    if consume:
        conn = connect_write(user_home)
        try:
            existing = one(conn, "SELECT nonce FROM founder_receipt_nonces WHERE nonce=?", (nonce,))
            if existing:
                raise PermissionError("founder-receipt-replay")
            conn.execute(
                "INSERT INTO founder_receipt_nonces(nonce,audience,subject_id,digest,consumed_at) VALUES(?,?,?,?,?)",
                (nonce, audience, subject_id, digest, utc_now()),
            )
            conn.commit()
        finally:
            conn.close()
    return {"decision": "pass", "audience": audience, "subject_id": subject_id, "nonce": nonce}
