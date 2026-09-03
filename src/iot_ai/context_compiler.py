# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Typed, inspectable context compilation with explicit privacy and token gates."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .privacy import sanitize
from .util import utc_now

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-]{2,}")
_PRIVACY_ORDER = {"D0": 0, "D1": 1, "D2": 2, "D3": 3}


def estimate_tokens(value: Any) -> int:
    """Return a conservative model-agnostic token estimate."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return max(1, math.ceil(len(text.encode("utf-8")) / 3.5))


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _keywords(value: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_PATTERN.findall(value) if len(token) > 2}


def _relevance(query: str, payload: Any) -> float:
    query_terms = _keywords(query)
    if not query_terms:
        return 0.5
    payload_terms = _keywords(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)[:20000])
    if not payload_terms:
        return 0.0
    overlap = len(query_terms & payload_terms)
    return round(min(1.0, overlap / max(1, len(query_terms))), 4)


def _compact_runtime_value(value: Any, *, max_chars: int = 12000) -> tuple[Any, bool, int]:
    """Compact runtime values without pretending the complete body is present."""
    if not isinstance(value, dict):
        serialized = str(value)
        if len(serialized) <= max_chars:
            return value, False, estimate_tokens(value)
        return {
            "compacted": True,
            "original_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            "original_characters": len(serialized),
            "preview": serialized[:max_chars],
            "preview_truncated": True,
        }, True, estimate_tokens(serialized)

    compact: dict[str, Any] = {}
    for key in (
        "status",
        "failure_class",
        "provider",
        "model_requested",
        "model_served",
        "request_id",
        "request_or_job_id",
        "role_id",
        "node_id",
        "duration_ms",
        "latency_ms",
        "evidence_refs",
        "parsed",
        "output",
    ):
        if key in value:
            compact[key] = value[key]
    if not compact:
        compact = value
    serialized = json.dumps(compact, ensure_ascii=False, sort_keys=True, default=str)
    if len(serialized) <= max_chars:
        return compact, compact is not value, estimate_tokens(value)
    reduced = {
        key: compact[key]
        for key in (
            "status",
            "failure_class",
            "provider",
            "model_requested",
            "model_served",
            "request_id",
            "request_or_job_id",
            "role_id",
            "node_id",
            "evidence_refs",
        )
        if key in compact
    }
    reduced.update(
        {
            "compacted": True,
            "original_sha256": _sha(compact),
            "original_tokens_estimate": estimate_tokens(compact),
            "available_top_level_keys": sorted(compact),
            "full_payload_location": "protected node-result store referenced by correlation_id/node_id",
        }
    )
    return reduced, True, estimate_tokens(value)


@dataclass(frozen=True, slots=True)
class ContextBlock:
    block_id: str
    kind: str
    source: str
    privacy_class: str
    mandatory: bool
    relevance: float
    token_estimate: int
    content_sha256: str
    payload: Any
    compacted: bool = False
    original_token_estimate: int | None = None
    inclusion_reason: str | None = None
    exclusion_reason: str | None = None

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        result = asdict(self)
        if not include_payload:
            result.pop("payload", None)
        return result


@dataclass(frozen=True, slots=True)
class ContextManifest:
    context_id: str
    goal_contract_digest: str
    node_id: str
    role_id: str
    privacy_class: str
    egress: str
    token_budget: int
    reserved_output_tokens: int
    used_tokens: int
    selected: tuple[ContextBlock, ...]
    excluded: tuple[ContextBlock, ...]
    no_silent_truncation: bool
    created_at: str
    digest: str
    decision: str = "pass"
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self, *, include_payloads: bool = True) -> dict[str, Any]:
        return {
            "schema": "iot-ai.context-manifest.v1",
            "context_id": self.context_id,
            "goal_contract_digest": self.goal_contract_digest,
            "node_id": self.node_id,
            "role_id": self.role_id,
            "privacy_class": self.privacy_class,
            "egress": self.egress,
            "token_budget": self.token_budget,
            "reserved_output_tokens": self.reserved_output_tokens,
            "used_tokens": self.used_tokens,
            "selected": [block.to_dict(include_payload=include_payloads) for block in self.selected],
            "excluded": [block.to_dict(include_payload=False) for block in self.excluded],
            "no_silent_truncation": self.no_silent_truncation,
            "created_at": self.created_at,
            "digest": self.digest,
            "decision": self.decision,
            "blockers": list(self.blockers),
        }


def _block(
    *,
    kind: str,
    source: str,
    payload: Any,
    privacy_class: str,
    mandatory: bool,
    query: str,
) -> ContextBlock:
    compacted_payload, compacted, original_tokens = _compact_runtime_value(payload)
    block_sha = _sha(payload)
    return ContextBlock(
        block_id=f"ctx-{hashlib.sha256(f'{kind}:{source}:{block_sha}'.encode()).hexdigest()[:20]}",
        kind=kind,
        source=source,
        privacy_class=privacy_class if privacy_class in _PRIVACY_ORDER else "D1",
        mandatory=mandatory,
        relevance=1.0 if mandatory else _relevance(query, compacted_payload),
        token_estimate=estimate_tokens(compacted_payload),
        content_sha256=block_sha,
        payload=compacted_payload,
        compacted=compacted,
        original_token_estimate=original_tokens if compacted else None,
    )


def _privacy_allowed(block: ContextBlock, egress: str) -> tuple[bool, str | None, Any]:
    if egress == "local":
        return True, None, block.payload
    if block.privacy_class == "D3":
        return False, "D3-secret-or-customer-restricted-data-cannot-egress", None
    if block.privacy_class == "D2":
        return False, "D2-confidential-payload-replaced-by-hash-reference", None
    result = sanitize(json.dumps(block.payload, ensure_ascii=False, sort_keys=True, default=str), "strict")
    if result.decision == "block":
        return False, "secret-pattern-detected", None
    try:
        clean_payload = json.loads(result.text)
    except json.JSONDecodeError:
        clean_payload = result.text
    return True, None, clean_payload


def compile_context(
    *,
    goal_contract: dict[str, Any],
    role_contract: dict[str, Any],
    node_contract: dict[str, Any],
    inputs: dict[str, Any],
    privacy_class: str,
    token_budget: int = 32000,
    reserve_ratio: float = 0.2,
    egress: str = "cloud",
    extra_blocks: list[dict[str, Any]] | None = None,
) -> ContextManifest:
    """Select explicit context blocks and record every omission.

    D2/D3 payloads never enter a cloud prompt. Their source hash and exclusion
    reason remain in the manifest so the missing evidence is visible rather
    than silently discarded.
    """
    if egress not in {"cloud", "local"}:
        raise ValueError("egress must be cloud or local")
    token_budget = max(2048, int(token_budget))
    reserve = max(512, min(token_budget - 512, int(token_budget * reserve_ratio)))
    input_budget = token_budget - reserve
    query = " ".join(
        str(value)
        for value in (
            goal_contract.get("outcome"),
            goal_contract.get("why"),
            node_contract.get("mission"),
            role_contract.get("mission"),
        )
        if value
    )

    blocks: list[ContextBlock] = [
        _block(
            kind="goal-contract",
            source=str(goal_contract.get("contract_id") or "goal"),
            payload=goal_contract,
            privacy_class=str(goal_contract.get("privacy_class") or privacy_class or "D1"),
            mandatory=True,
            query=query,
        ),
        _block(
            kind="role-contract",
            source=str(role_contract.get("role_id") or "role"),
            payload=role_contract,
            privacy_class="D0",
            mandatory=True,
            query=query,
        ),
        _block(
            kind="node-contract",
            source=str(node_contract.get("node_id") or "node"),
            payload=node_contract,
            privacy_class="D0",
            mandatory=True,
            query=query,
        ),
    ]
    for source, value in sorted(inputs.items()):
        value_privacy = privacy_class
        if isinstance(value, dict) and str(value.get("privacy_class")) in _PRIVACY_ORDER:
            value_privacy = str(value["privacy_class"])
        blocks.append(
            _block(
                kind="dependency-result",
                source=source,
                payload=value,
                privacy_class=value_privacy,
                mandatory=False,
                query=query,
            )
        )
    for extra in extra_blocks or []:
        blocks.append(
            _block(
                kind=str(extra.get("kind") or "skill-guidance"),
                source=str(extra.get("source") or "skill"),
                payload=extra.get("payload"),
                privacy_class=str(extra.get("privacy_class") or "D0"),
                mandatory=False,
                query=query,
            )
        )

    selected: list[ContextBlock] = []
    excluded: list[ContextBlock] = []
    used = 0
    blockers: list[str] = []
    ordered = sorted(blocks, key=lambda item: (not item.mandatory, -item.relevance, item.source))
    for block in ordered:
        allowed, privacy_reason, clean_payload = _privacy_allowed(block, egress)
        if not allowed:
            replacement = ContextBlock(
                **{
                    **block.to_dict(include_payload=True),
                    "payload": {
                        "content_sha256": block.content_sha256,
                        "privacy_class": block.privacy_class,
                        "payload_available_in_protected_store": True,
                    },
                    "token_estimate": 40,
                    "exclusion_reason": privacy_reason,
                }
            )
            if block.mandatory:
                blockers.append(f"mandatory block {block.source} blocked: {privacy_reason}")
                excluded.append(replacement)
                continue
            if used + replacement.token_estimate <= input_budget:
                selected.append(
                    ContextBlock(
                        **{
                            **replacement.to_dict(include_payload=True),
                            "inclusion_reason": "privacy-preserving hash reference",
                        }
                    )
                )
                used += replacement.token_estimate
            else:
                excluded.append(replacement)
            continue

        candidate = ContextBlock(
            **{
                **block.to_dict(include_payload=True),
                "payload": clean_payload,
                "token_estimate": estimate_tokens(clean_payload),
                "inclusion_reason": "mandatory contract" if block.mandatory else f"relevance={block.relevance:.4f}",
            }
        )
        if used + candidate.token_estimate > input_budget:
            excluded_block = ContextBlock(
                **{
                    **candidate.to_dict(include_payload=True),
                    "inclusion_reason": None,
                    "exclusion_reason": "context-token-budget",
                }
            )
            excluded.append(excluded_block)
            if block.mandatory:
                blockers.append(f"mandatory block {block.source} exceeds context budget")
            continue
        selected.append(candidate)
        used += candidate.token_estimate

    body = {
        "schema": "iot-ai.context-manifest.v1",
        "goal_contract_digest": goal_contract.get("digest"),
        "node_id": node_contract.get("node_id"),
        "role_id": role_contract.get("role_id"),
        "privacy_class": privacy_class,
        "egress": egress,
        "token_budget": token_budget,
        "reserved_output_tokens": reserve,
        "used_tokens": used,
        "selected": [block.to_dict(include_payload=True) for block in selected],
        "excluded": [block.to_dict(include_payload=False) for block in excluded],
        "no_silent_truncation": True,
    }
    digest = _sha(body)
    return ContextManifest(
        context_id=f"context-{digest[:20]}",
        goal_contract_digest=str(goal_contract.get("digest") or ""),
        node_id=str(node_contract.get("node_id") or ""),
        role_id=str(role_contract.get("role_id") or ""),
        privacy_class=privacy_class,
        egress=egress,
        token_budget=token_budget,
        reserved_output_tokens=reserve,
        used_tokens=used,
        selected=tuple(selected),
        excluded=tuple(excluded),
        no_silent_truncation=True,
        created_at=utc_now(),
        digest=digest,
        decision="block" if blockers else "pass",
        blockers=tuple(blockers),
    )


def validate_context_manifest(manifest: ContextManifest | dict[str, Any]) -> dict[str, Any]:
    payload = manifest.to_dict(include_payloads=True) if isinstance(manifest, ContextManifest) else dict(manifest)
    errors: list[str] = []
    if payload.get("used_tokens", 0) + payload.get("reserved_output_tokens", 0) > payload.get("token_budget", 0):
        errors.append("context budget exceeded")
    if not payload.get("no_silent_truncation"):
        errors.append("silent truncation policy is disabled")
    selected_ids = [row.get("block_id") for row in payload.get("selected", [])]
    if len(selected_ids) != len(set(selected_ids)):
        errors.append("duplicate selected context block")
    for row in payload.get("selected", []):
        if row.get("privacy_class") == "D3" and payload.get("egress") == "cloud":
            reference = row.get("payload") or {}
            if not (isinstance(reference, dict) and reference.get("payload_available_in_protected_store") and reference.get("content_sha256")):
                errors.append("D3 payload selected for cloud egress")
    if payload.get("blockers"):
        errors.extend(str(item) for item in payload["blockers"])
    return {"decision": "pass" if not errors else "block", "errors": errors, "context_id": payload.get("context_id")}
