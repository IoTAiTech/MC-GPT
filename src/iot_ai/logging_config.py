# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
"""Structured, privacy-minimised runtime and transaction logging."""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Mapping

from .paths import (
    application_log_path,
    audit_log_path,
    diagnostics_log_root,
    log_root,
    transaction_log_root,
)
from .util import utc_now

_SECRET_KEY = re.compile(r"(?i)(secret|token|password|passwd|api[_-]?key|authorization|cookie|credential|lease[_-]?token)")
_SECRET_VALUE = re.compile(
    r"(?i)(?:(?:sk|xai|ghp|AIza)[-_A-Za-z0-9.]{8,}|Bearer\s+[-_A-Za-z0-9.~+/=]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def _sanitize(value: Any, key: str = "") -> Any:
    if key and _SECRET_KEY.search(key):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {str(k): _sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return _SECRET_VALUE.sub("<redacted>", value)
    return value


def log_locations(user_home: Path) -> dict[str, str]:
    """Return every operator-facing log path used by the Suite."""
    return {
        "logs_root": str(log_root(user_home)),
        "application_log": str(application_log_path(user_home)),
        "audit_log": str(audit_log_path(user_home)),
        "transaction_logs": str(transaction_log_root(user_home)),
        "diagnostics_logs": str(diagnostics_log_root(user_home)),
    }


def append_event(
    user_home: Path,
    event: str,
    payload: Mapping[str, Any] | None = None,
    *,
    audit: bool = False,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Append one fsync-backed JSONL record without raw secrets."""
    root = log_root(user_home)
    root.mkdir(parents=True, exist_ok=True)
    path = audit_log_path(user_home) if audit else application_log_path(user_home)
    record = {
        "schema": "iot-ai.log-event.v1",
        "event_id": f"log-{uuid.uuid4().hex[:16]}",
        "correlation_id": correlation_id,
        "event": event,
        "at": utc_now(),
        "pid": os.getpid(),
        "payload": _sanitize(dict(payload or {})),
    }
    line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    return {"path": str(path), "event_id": record["event_id"], "correlation_id": correlation_id}


def transaction_log(user_home: Path, operation: str, transaction_id: str, payload: Mapping[str, Any]) -> Path:
    root = transaction_log_root(user_home) / transaction_id
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{operation}.json"
    safe = _sanitize(dict(payload))
    path.write_text(json.dumps(safe, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
