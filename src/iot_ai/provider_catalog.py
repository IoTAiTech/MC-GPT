# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
"""Lifecycle-aware provider/model catalog. Requested is not served identity."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_NAME = "provider_capability_catalog.json"
GOVERNED_RISKS = frozenset({"R2", "R3", "R4"})
DEFAULT_NAMESPACES = {
    "codex": "openai",
    "openai": "openai",
    "grok": "xai",
    "xai": "xai",
    "claude": "anthropic",
    "anthropic": "anthropic",
}
RUNTIME_WITHOUT_MODEL_CATALOG = frozenset({"gemini", "ollama"})
_CLIENT_PRODUCT = {
    "claude": "claude-code",
    "anthropic": "claude-code",
    "openai": "codex",
    "codex": "codex",
    "xai": "grok-cli",
    "grok": "grok-cli",
}


def catalog_path() -> Path:
    return Path(__file__).resolve().parent / "data" / CATALOG_NAME


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    path = catalog_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "iot-ai.provider-capability-catalog.v1":
        raise ValueError("provider capability catalog is missing or unsupported")
    return data


def catalog_version() -> str:
    return str(load_catalog().get("catalog_version") or "")


def source_dates() -> dict[str, str]:
    payload = load_catalog().get("source_dates") or {}
    return {str(key): str(value) for key, value in payload.items()}


def source_content_digest() -> dict[str, str]:
    payload = load_catalog().get("source_content_digest") or {}
    return {str(key): str(value) for key, value in payload.items()}


def provider_namespaces() -> dict[str, str]:
    payload = load_catalog().get("provider_namespaces") or {}
    merged = dict(DEFAULT_NAMESPACES)
    merged.update({str(key): str(value) for key, value in payload.items()})
    return merged


def normalize_provider(provider: str) -> str:
    key = str(provider or "").strip().casefold()
    return provider_namespaces().get(key, key)


def _model_record(catalog_provider: str, model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    providers = load_catalog().get("providers") or {}
    block = providers.get(catalog_provider) or {}
    models = block.get("models") or {}
    return block, dict(models.get(model) or {})


def resolve_model(
    provider: str,
    requested: str,
    *,
    client_product: str | None = None,
    client_version: str | None = None,
    limited_access: bool = False,
    zero_data_retention: bool = False,
    sampling: dict[str, Any] | None = None,
    risk_class: str | None = None,
) -> dict[str, Any]:
    """Map aliases and retirements to canonical_target_model. Never invent model_served."""

    errors: list[str] = []
    warnings: list[str] = []
    runtime_provider = str(provider or "")
    catalog_provider = normalize_provider(runtime_provider)
    requested_model = str(requested or "")
    canonical = requested_model
    redirected_from = None
    providers = load_catalog().get("providers") or {}
    if catalog_provider not in providers:
        if catalog_provider in RUNTIME_WITHOUT_MODEL_CATALOG:
            return _result(
                runtime_provider,
                catalog_provider,
                requested_model,
                canonical,
                errors,
                warnings,
                redirected_from,
                sampling,
                client_product,
                client_version,
                None,
            )
        errors.append("unknown-provider-capability")
        return _result(
            runtime_provider,
            catalog_provider,
            requested_model,
            None,
            errors,
            warnings,
            redirected_from,
            sampling,
            client_product,
            client_version,
            None,
        )
    block, record = _model_record(catalog_provider, requested_model)
    if not record:
        if (risk_class or "") in GOVERNED_RISKS:
            errors.append("unknown-model")
        else:
            errors.append("unknown-model")
        return _result(
            runtime_provider,
            catalog_provider,
            requested_model,
            canonical,
            errors,
            warnings,
            redirected_from,
            sampling,
            client_product,
            client_version,
            None,
        )
    if record.get("not_an_api_id") or record.get("classification") == "client_product_label":
        if record.get("canonical_if_codex_client") and (client_product or "") == "codex":
            canonical = str(record["canonical_if_codex_client"])
            warnings.append("client-product-label-not-api-id")
            block, record = _model_record(catalog_provider, canonical)
        elif record.get("canonical_if_coding"):
            errors.append("client-product-label-not-api-id")
            return _result(
                runtime_provider,
                catalog_provider,
                requested_model,
                None,
                errors,
                warnings,
                redirected_from,
                sampling,
                client_product,
                client_version,
                record,
            )
        else:
            errors.append("client-product-label-not-api-id")
            return _result(
                runtime_provider,
                catalog_provider,
                requested_model,
                None,
                errors,
                warnings,
                redirected_from,
                sampling,
                client_product,
                client_version,
                record,
            )
    status = str(record.get("status") or record.get("lifecycle") or "ga")
    multi_agent = bool(record.get("multi_agent"))
    adaptive = bool(record.get("adaptive_thinking"))
    rejects_budget = bool(record.get("rejects_budget_tokens"))
    if status == "retired" and record.get("redirect_to"):
        redirected_from = requested_model
        canonical = str(record["redirect_to"])
        warnings.append(f"retired-redirect:{requested_model}->{canonical}")
        block, record = _model_record(catalog_provider, canonical)
        status = str(record.get("status") or "ga")
        multi_agent = multi_agent or bool(record.get("multi_agent"))
        adaptive = adaptive or bool(record.get("adaptive_thinking"))
        rejects_budget = rejects_budget or bool(record.get("rejects_budget_tokens"))
    if status == "alias" and record.get("alias_of"):
        canonical = str(record["alias_of"])
        warnings.append(f"alias:{requested_model}->{canonical}")
        block, record = _model_record(catalog_provider, canonical)
        status = str(record.get("status") or "ga")
        multi_agent = multi_agent or bool(record.get("multi_agent"))
        adaptive = adaptive or bool(record.get("adaptive_thinking"))
        rejects_budget = rejects_budget or bool(record.get("rejects_budget_tokens"))
    if status in {"limited-access", "limited-rollout"} and not limited_access:
        errors.append("limited-access-unentitled")
    clients = (block.get("clients") or {}) if isinstance(block.get("clients"), dict) else {}
    if client_product:
        client = clients.get(client_product) or {}
        minimum = str(client.get("minimum_version") or "")
        vulnerable = list(client.get("vulnerable_versions") or [])
        if client_version and minimum and _version_tuple(client_version) < _version_tuple(minimum):
            errors.append("client-minimum-version")
        if client_version and client_version in vulnerable:
            errors.append("client-vulnerable-version")
        allowed_products = list(record.get("client_products") or [])
        if allowed_products and client_product not in allowed_products:
            errors.append("client-product-mismatch")
    privacy = block.get("privacy") or {}
    if zero_data_retention and "training-retention" in list(privacy.get("unsupported_when_zdr") or []):
        if str(privacy.get("zdr_policy") or "") == "hard-block":
            errors.append("zdr-training-retention-forbidden")
        else:
            warnings.append("zdr-training-retention-forbidden")
    cleaned_sampling = dict(sampling or {})
    for param in list(block.get("unsupported_sampling_parameters") or record.get("unsupported_params") or []):
        if param in cleaned_sampling:
            cleaned_sampling.pop(param, None)
            warnings.append(f"unsupported-sampling-removed:{param}")
    merged = dict(record or {})
    merged["multi_agent"] = multi_agent
    merged["adaptive_thinking"] = adaptive
    merged["rejects_budget_tokens"] = rejects_budget
    return _result(
        runtime_provider,
        catalog_provider,
        requested_model,
        canonical if not errors else None,
        errors,
        warnings,
        redirected_from,
        cleaned_sampling,
        client_product,
        client_version,
        merged,
    )


def apply_catalog_to_candidate(
    candidate: dict[str, Any] | None,
    *,
    risk_class: str | None = None,
) -> dict[str, Any]:
    """Attach catalog identity. Never populate model_served before a provider response."""

    row = dict(candidate or {})
    if risk_class:
        row["risk_class"] = risk_class
    runtime_provider = str(row.get("provider") or "")
    requested = str(row.get("model") or row.get("model_requested") or "")
    row["provider_family"] = normalize_provider(runtime_provider)
    row["model_requested"] = requested
    row["canonical_target_model"] = None
    row["model_served"] = None
    if "served_model" in row:
        row.pop("served_model", None)
    if requested in {"", "auto", "auto:cloud"}:
        return row
    resolved = resolve_model(
        runtime_provider,
        requested,
        client_product=_CLIENT_PRODUCT.get(str(runtime_provider).casefold()) or _CLIENT_PRODUCT.get(normalize_provider(runtime_provider)),
        limited_access=bool(row.get("limited_access")),
        zero_data_retention=bool(row.get("zero_data_retention")),
        risk_class=str(row.get("risk_class") or "") or None,
    )
    row["catalog"] = resolved
    row["provider_family"] = resolved.get("catalog_provider") or row["provider_family"]
    if resolved.get("decision") == "block":
        row["catalog_block"] = True
        row["catalog_errors"] = list(resolved.get("errors") or [])
        return row
    canonical = resolved.get("canonical_target_model")
    row["canonical_target_model"] = canonical
    row["catalog_block"] = False
    row["multi_agent"] = bool(resolved.get("multi_agent") or row.get("multi_agent"))
    row["adaptive_thinking"] = bool(resolved.get("adaptive_thinking"))
    row["rejects_budget_tokens"] = bool(resolved.get("rejects_budget_tokens"))
    row["supported_efforts"] = list(resolved.get("supported_efforts") or [])
    row["effort_axis"] = resolved.get("effort_axis") or "reasoning_depth"
    return row


def supported_matrix() -> dict[str, Any]:
    catalog = load_catalog()
    matrix: dict[str, Any] = {}
    for provider, block in (catalog.get("providers") or {}).items():
        rows = []
        for model, record in (block.get("models") or {}).items():
            rows.append(
                {
                    "requested": model,
                    "status": record.get("status"),
                    "lifecycle": record.get("lifecycle") or record.get("status"),
                    "canonical_target_model": record.get("alias_of") or record.get("redirect_to") or record.get("model_id") or model,
                    "model_served": None,
                    "client_products": list(record.get("client_products") or []),
                    "supported_efforts": list(record.get("supported_efforts") or []),
                    "classification": record.get("classification"),
                    "source_url": record.get("source_url"),
                    "source_checked_at": record.get("source_checked_at"),
                }
            )
        matrix[provider] = {
            "models": rows,
            "clients": block.get("clients") or {},
        }
    return {
        "catalog_version": catalog.get("catalog_version"),
        "source_dates": catalog.get("source_dates"),
        "source_content_digest": catalog.get("source_content_digest"),
        "provider_namespaces": provider_namespaces(),
        "providers": matrix,
    }


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for item in str(value).split("."):
        digits = "".join(ch for ch in item if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or (0,))


def _result(
    runtime_provider: str,
    catalog_provider: str,
    requested: str,
    canonical: str | None,
    errors: list[str],
    warnings: list[str],
    redirected_from: str | None,
    sampling: dict[str, Any] | None,
    client_product: str | None,
    client_version: str | None,
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = record or {}
    return {
        "provider": runtime_provider,
        "catalog_provider": catalog_provider,
        "requested_model": requested,
        "model_requested": requested,
        "canonical_target_model": canonical if not errors else None,
        "model_served": None,
        "served_model": None,
        "client_product": client_product,
        "client_version": client_version,
        "redirected_from": redirected_from,
        "adaptive_thinking": bool(payload.get("adaptive_thinking")),
        "rejects_budget_tokens": bool(payload.get("rejects_budget_tokens")),
        "multi_agent": bool(payload.get("multi_agent")),
        "supported_efforts": list(payload.get("supported_efforts") or []),
        "effort_axis": payload.get("effort_axis") or "reasoning_depth",
        "sampling": sampling or {},
        "errors": errors,
        "warnings": warnings,
        "decision": "pass" if not errors else "block",
        "identity_separation": {
            "model_requested": requested,
            "canonical_target_model": canonical if not errors else None,
            "model_served": None,
            "client_product": client_product,
            "runtime_provider": runtime_provider,
            "catalog_provider": catalog_provider,
        },
    }
