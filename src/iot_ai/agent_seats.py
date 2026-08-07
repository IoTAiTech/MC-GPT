# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
"""Read-only dashboard-agent seats for governed meetings."""
from __future__ import annotations
import hashlib
import hmac
import ipaddress
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from .meeting_integration import get_agent_seat
from .util import utc_now

SEAT_RE = re.compile(r"^agent:(pmd|fcc|hid|healthlab|cws|dgx)/([A-Za-z0-9._-]+)$")

def parse_agent_seat(seat: str) -> tuple[str, str]:
    match = SEAT_RE.fullmatch(seat)
    if not match:
        raise ValueError("invalid agent seat")
    return match.group(1), match.group(2)

def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def build_agent_envelope(
    seat: str,
    prompt: str,
    stage: str,
    meeting_id: str,
    role: str,
    timeout: int,
    *,
    issued_by: str = "iot-ai-meeting",
) -> dict[str, Any]:
    surface, agent_id = parse_agent_seat(seat)
    body = {
        "schema": "iot-ai.agent-seat-envelope.v1",
        "contract_type": "consultation",
        "envelope_id": "env-" + hashlib.sha256(f"{meeting_id}:{seat}:{stage}:{prompt}".encode()).hexdigest()[:24],
        "meeting_id": meeting_id,
        "seat": seat,
        "seat_type": "agent",
        "surface": surface,
        "agent_id": agent_id,
        "stage": stage,
        "role": role,
        "prompt": prompt,
        "read_only": True,
        "write_scope": [],
        "assignment": None,
        "execution_lease": None,
        "child_delegation": False,
        "privacy_class": "D1",
        "timeout_seconds": max(1, min(int(timeout), 3600)),
        "reply_mode": "sync",
        "issued_at": utc_now(),
        "issued_by": issued_by,
    }
    body["envelope_sha256"] = hashlib.sha256(_canonical(body)).hexdigest()
    return body

def validate_agent_reply(envelope: dict[str, Any], reply: dict[str, Any]) -> dict[str, Any]:
    text = str(reply.get("text") or "")
    writes = int(reply.get("writes_performed") or 0)
    failure = reply.get("failure_class")
    status = str(reply.get("status") or "failed")
    if reply.get("envelope_id") != envelope["envelope_id"] or not hmac.compare_digest(str(reply.get("envelope_sha256") or ""), envelope["envelope_sha256"]):
        status, failure = "failed", "envelope_mismatch"
    elif writes != 0:
        status, failure = "failed", "policy_violation"
    elif not text.strip():
        status, failure = "failed", "no_output"
    elif not reply.get("model_served"):
        status, failure = "failed", "model_unverified"
    text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if reply.get("text_sha256") and not hmac.compare_digest(str(reply["text_sha256"]), text_sha):
        status, failure = "failed", "reply_digest_mismatch"
    return {
        "status": status,
        "output": text,
        "provider": "agent",
        "model_requested": reply.get("model_requested"),
        "model_served": reply.get("model_served"),
        "request_id": envelope["envelope_id"],
        "route_id": f"agent-seat:{envelope['surface']}",
        "input_tokens": reply.get("input_tokens"),
        "cached_tokens": reply.get("cached_tokens"),
        "output_tokens": reply.get("output_tokens"),
        "reasoning_tokens": reply.get("reasoning_tokens"),
        "latency_ms": reply.get("latency_ms"),
        "fallback_used": False,
        "failure_class": failure,
        "writes_performed": writes,
        "envelope_sha256": envelope["envelope_sha256"],
        "evidence_refs": list(reply.get("evidence_refs") or []),
    }

def _private_endpoint(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return False
    if parsed.hostname == "localhost":
        return parsed.scheme == "http"
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return False
    private_networks = tuple(
        ipaddress.ip_network(value)
        for value in ("10." + "0.0.0/8", "172." + "16.0.0/12", "192." + "168.0.0/16")
    )
    allowed = address.is_loopback or any(address in network for network in private_networks)
    return bool(allowed and not address.is_link_local and not address.is_multicast and not address.is_reserved and (parsed.scheme == "https" or address.is_loopback))

def delegate_agent_seat(
    user_home: Path,
    seat: str,
    prompt: str,
    stage: str,
    run_id: str,
    role: str,
    timeout: int,
    effort: str = "high",
) -> dict[str, Any]:
    del effort
    record = get_agent_seat(user_home, seat)
    if not record:
        return {"status": "failed", "output": "", "provider": "agent", "model_served": None, "failure_class": "unknown_agent"}
    if not record.get("reachable"):
        return {"status": "failed", "output": "", "provider": "agent", "model_requested": record.get("model_binding"), "model_served": None, "failure_class": "unreachable"}
    endpoint = str(record.get("endpoint_ref") or "")
    if not _private_endpoint(endpoint):
        return {"status": "failed", "output": "", "provider": "agent", "model_requested": record.get("model_binding"), "model_served": None, "failure_class": "endpoint_policy"}
    envelope = build_agent_envelope(seat, prompt, stage, run_id, role, timeout)
    surface, _ = parse_agent_seat(seat)
    token = os.environ.get(f"IOT_AI_AGENT_{surface.upper()}_TOKEN", "")
    if len(token) < 24:
        return {"status": "failed", "output": "", "provider": "agent", "model_requested": record.get("model_binding"), "model_served": None, "failure_class": "auth_missing"}
    request = urllib.request.Request(
        endpoint,
        data=_canonical(envelope),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1, min(timeout, 3600))) as response:
            payload = json.loads(response.read(1_048_576).decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"status": "failed", "output": "", "provider": "agent", "model_requested": record.get("model_binding"), "model_served": None, "failure_class": type(exc).__name__}
    return validate_agent_reply(envelope, payload)
