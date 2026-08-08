# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Semantic validation for dashboard-agent contracts and aliases."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from typing import Any
from urllib.parse import urlparse

REQUIRED_FIELDS = ("task", "setting", "llm", "log", "report", "process", "workflow", "prompt")
_ALIAS_RE = re.compile(r"^\s*Alias\s+for\s+([A-Za-z0-9._-]+)", re.IGNORECASE)
_PRIVATE_PATH_RE = re.compile(r"(?:/(?:home|root)/[^\s]+|[A-Za-z]:\\Users\\[^\s]+)")

STAGE_CAPABILITY = {
    "opinion": "meeting.opinion",
    "meeting-opinion": "meeting.opinion",
    "critique": "meeting.critique",
    "meeting-critique": "meeting.critique",
    "plan-critique": "meeting.critique",
    "synthesis": "meeting.synthesis",
    "meeting-synthesis": "meeting.synthesis",
    "plan-synthesis": "meeting.synthesis",
    "final-review": "meeting.review",
    "meeting-final-review": "meeting.review",
    "plan-final-review": "meeting.review",
    "receipt": "meeting.receipt",
    "meeting-receipt": "meeting.receipt",
}


def required_capability_for_stage(stage: str) -> str | None:
    return STAGE_CAPABILITY.get(str(stage or "").strip().casefold())


def _contains_private_endpoint(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if _PRIVATE_PATH_RE.search(value):
        return True
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return parsed.hostname.casefold() == "localhost" or parsed.hostname.casefold().endswith(".local")
    return address.is_private or address.is_loopback or address.is_link_local


def normalize_contract(agent_id: str, value: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in value:
            errors.append(f"missing-field:{field}")
    alias_of = value.get("alias_of")
    if not alias_of:
        match = _ALIAS_RE.match(str(value.get("task") or ""))
        alias_of = match.group(1) if match else None
    kind = "alias" if alias_of else "canonical"
    capabilities = value.get("capabilities") or []
    if isinstance(capabilities, str):
        capabilities = [capabilities]
    capabilities = sorted({str(item).strip() for item in capabilities if str(item).strip()})
    if any(_contains_private_endpoint(value.get(field)) for field in ("llm", "log", "report", "process", "prompt")):
        errors.append("public-boundary:private-endpoint-or-path")
    digest_body = {
        "agent_id": agent_id,
        "kind": kind,
        "alias_of": alias_of,
        "capabilities": capabilities,
        "contract": value,
    }
    digest = hashlib.sha256(json.dumps(digest_body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    return {
        "agent_id": agent_id,
        "agent_kind": kind,
        "alias_of": alias_of,
        "capabilities": capabilities,
        "contract_sha256": digest,
        "decision": "pass" if not errors else "block",
        "errors": errors,
    }


def validate_contract_set(payload: dict[str, Any]) -> dict[str, Any]:
    agents = payload.get("agents") if isinstance(payload.get("agents"), dict) else {}
    rows = [normalize_contract(str(agent_id), dict(value)) for agent_id, value in agents.items() if isinstance(value, dict)]
    canonical = {row["agent_id"] for row in rows if row["agent_kind"] == "canonical"}
    for row in rows:
        if row["agent_kind"] == "alias" and row.get("alias_of") not in canonical:
            row["decision"] = "block"
            row["errors"].append(f"alias-target-missing:{row.get('alias_of')}")
    return {
        "schema": "iot-ai.agent-contract-validation.v1",
        "decision": "pass" if rows and all(row["decision"] == "pass" for row in rows) else "block",
        "agent_rows": rows,
        "source_rows": len(rows),
        "canonical_agents": sum(1 for row in rows if row["agent_kind"] == "canonical"),
        "aliases": sum(1 for row in rows if row["agent_kind"] == "alias"),
        "errors": [error for row in rows for error in row["errors"]],
    }


def validate_capabilities(capabilities: list[str] | tuple[str, ...], required_capability: str | None) -> dict[str, Any]:
    available = {str(value).strip().casefold() for value in capabilities if str(value).strip()}
    required = str(required_capability or "").strip().casefold() or None
    passed = required is None or required in available
    return {
        "decision": "pass" if passed else "block",
        "required_capability": required,
        "available_capabilities": sorted(available),
        "semantic_compatibility": passed,
        "failure_class": None if passed else "semantic_capability_mismatch",
    }
