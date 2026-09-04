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


def _model_record(provider: str, model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    providers = load_catalog().get("providers") or {}
    block = providers.get(provider) or {}
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
) -> dict[str, Any]:
    """Map aliases, retirements, client floors and privacy gates without claiming served identity."""

    errors: list[str] = []
    warnings: list[str] = []
    served = requested
    redirected_from = None
    block, record = _model_record(provider, requested)
    if not record:
        errors.append("unknown-model")
        return _result(provider, requested, served, errors, warnings, redirected_from, sampling, client_product, client_version)
    status = str(record.get("status") or "ga")
    multi_agent = bool(record.get("multi_agent"))
    adaptive = bool(record.get("adaptive_thinking"))
    if status == "retired" and record.get("redirect_to"):
        redirected_from = requested
        served = str(record["redirect_to"])
        warnings.append(f"retired-redirect:{requested}->{served}")
        block, record = _model_record(provider, served)
        status = str(record.get("status") or "ga")
        multi_agent = multi_agent or bool(record.get("multi_agent"))
        adaptive = adaptive or bool(record.get("adaptive_thinking"))
    if status == "alias" and record.get("alias_of"):
        served = str(record["alias_of"])
        warnings.append(f"alias:{requested}->{served}")
        block, record = _model_record(provider, served)
        status = str(record.get("status") or "ga")
        multi_agent = multi_agent or bool(record.get("multi_agent"))
        adaptive = adaptive or bool(record.get("adaptive_thinking"))
    elif record.get("alias_of"):
        served = str(record["alias_of"])
        multi_agent = multi_agent or bool(record.get("multi_agent"))
        adaptive = adaptive or bool(record.get("adaptive_thinking"))
    if status == "limited-access" and not limited_access:
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
        warnings.append("zdr-training-retention-forbidden")
    cleaned_sampling = dict(sampling or {})
    for param in list(block.get("unsupported_sampling_parameters") or []):
        if param in cleaned_sampling:
            cleaned_sampling.pop(param, None)
            warnings.append(f"unsupported-sampling-removed:{param}")
    merged = dict(record or {})
    merged["multi_agent"] = multi_agent
    merged["adaptive_thinking"] = adaptive
    return _result(provider, requested, served, errors, warnings, redirected_from, cleaned_sampling, client_product, client_version, merged)


_CLIENT_PRODUCT = {
    "claude": "claude-code",
    "openai": "codex",
    "codex": "codex",
    "xai": "grok-cli",
    "grok": "grok-cli",
}


def apply_catalog_to_candidate(candidate: dict[str, Any] | None) -> dict[str, Any]:
    """Rewrite aliases/retirements and block entitled-limited models before dispatch."""

    row = dict(candidate or {})
    provider = str(row.get("provider") or "")
    requested = str(row.get("model") or "")
    if requested in {"", "auto", "auto:cloud"}:
        return row
    providers = load_catalog().get("providers") or {}
    if provider not in providers:
        return row
    models = (providers.get(provider) or {}).get("models") or {}
    if requested not in models:
        return row
    resolved = resolve_model(
        provider,
        requested,
        client_product=_CLIENT_PRODUCT.get(provider),
        limited_access=bool(row.get("limited_access")),
    )
    row["requested_model"] = requested
    row["catalog"] = resolved
    if resolved.get("decision") == "block":
        row["catalog_block"] = True
        row["catalog_errors"] = list(resolved.get("errors") or [])
        return row
    served = resolved.get("served_model")
    if served:
        row["model"] = served
        row["served_model"] = served
    row["catalog_block"] = False
    row["multi_agent"] = bool(resolved.get("multi_agent") or row.get("multi_agent"))
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
                    "served": record.get("alias_of") or record.get("redirect_to") or model,
                    "client_products": list(record.get("client_products") or []),
                }
            )
        matrix[provider] = {
            "models": rows,
            "clients": block.get("clients") or {},
        }
    return {
        "catalog_version": catalog.get("catalog_version"),
        "source_dates": catalog.get("source_dates"),
        "providers": matrix,
    }


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for item in str(value).split("."):
        digits = "".join(ch for ch in item if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or (0,))


def _result(
    provider: str,
    requested: str,
    served: str,
    errors: list[str],
    warnings: list[str],
    redirected_from: str | None,
    sampling: dict[str, Any] | None,
    client_product: str | None,
    client_version: str | None,
    record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "requested_model": requested,
        "served_model": served if not errors else None,
        "client_product": client_product,
        "client_version": client_version,
        "redirected_from": redirected_from,
        "adaptive_thinking": bool((record or {}).get("adaptive_thinking")),
        "multi_agent": bool((record or {}).get("multi_agent")),
        "sampling": sampling or {},
        "errors": errors,
        "warnings": warnings,
        "decision": "pass" if not errors else "block",
        "identity_separation": {
            "requested_model": requested,
            "served_model": served if not errors else None,
            "client_product": client_product,
        },
    }
