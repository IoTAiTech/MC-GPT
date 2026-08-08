# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Live-readiness receipts and provider/model candidate expansion."""
from __future__ import annotations

from datetime import datetime, timezone
import os
import subprocess
from pathlib import Path
from typing import Any

from .paths import config_root
from .providers import load as load_routes, static_status
from .util import atomic_json, load_json, utc_now


def receipt_path(user_home: Path) -> Path:
    return config_root(user_home) / "readiness-receipts.json"


def load_receipts(user_home: Path) -> dict[str, Any]:
    return load_json(receipt_path(user_home), {"schema": "iot-ai.readiness.v1", "receipts": []}) or {"schema": "iot-ai.readiness.v1", "receipts": []}


def save_receipt(user_home: Path, receipt: dict[str, Any]) -> None:
    data = load_receipts(user_home)
    receipts = [r for r in data.get("receipts", []) if not (r.get("route_id") == receipt.get("route_id") and r.get("model_served") == receipt.get("model_served"))]
    receipts.append(receipt)
    data["receipts"] = receipts
    data["updated_at"] = utc_now()
    atomic_json(receipt_path(user_home), data)


def _fresh(receipt: dict[str, Any], now: datetime | None = None) -> bool:
    expires = receipt.get("expires_at")
    if not expires:
        return False
    try:
        dt = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
    except ValueError:
        return False
    return dt > (now or datetime.now(timezone.utc))


def live_receipt(user_home: Path, route_id: str, model: str | None = None) -> dict[str, Any] | None:
    candidates = [r for r in load_receipts(user_home).get("receipts", []) if r.get("route_id") == route_id]
    if model:
        candidates = [r for r in candidates if r.get("model_served") == model]
    candidates = [r for r in candidates if _fresh(r)]
    return max(candidates, key=lambda r: str(r.get("observed_at", "")), default=None)




def discover_ollama_cloud_models() -> list[str]:
    """Discover model-specific Ollama Cloud candidates without claiming readiness."""
    configured = [x.strip() for x in os.environ.get("IOT_AI_OLLAMA_CLOUD_MODELS", "").split(",") if x.strip()]
    if configured:
        return sorted(dict.fromkeys(configured))
    try:
        completed = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    models: list[str] = []
    for line in completed.stdout.splitlines()[1:]:
        value = line.split()[0] if line.split() else ""
        if value.endswith(":cloud") or "-cloud" in value:
            models.append(value)
    return sorted(dict.fromkeys(models))

def provider_candidates(user_home: Path, *, require_live: bool = True, cloud_only: bool = False) -> list[dict[str, Any]]:
    """Expand routes into exact model candidates; static presence never means ready."""
    result: list[dict[str, Any]] = []
    for route in load_routes(user_home).get("routes", []):
        if not route.get("enabled", False):
            continue
        status = static_status(route)
        if not status.get("installed"):
            continue
        if cloud_only and not route.get("cloud", True):
            continue
        configured_model = str(route.get("model", "auto"))
        if route.get("provider") == "ollama" and configured_model == "auto:cloud":
            models: list[str] = list(route.get("models") or discover_ollama_cloud_models())
        else:
            models = list(route.get("models") or [configured_model])
        route_receipts = [
            receipt
            for receipt in load_receipts(user_home).get("receipts", [])
            if receipt.get("route_id") == route.get("route_id") and _fresh(receipt)
        ]
        if configured_model.startswith("auto") and route_receipts:
            observed_models = [
                str(receipt.get("model_served"))
                for receipt in route_receipts
                if receipt.get("model_served")
            ]
            models = list(dict.fromkeys([*models, *observed_models]))
        if not models:
            models = [configured_model]
        for configured in dict.fromkeys(str(model) for model in models if str(model)):
            exact_model = None if configured.startswith("auto") else configured
            receipt = live_receipt(user_home, str(route.get("route_id")), exact_model)
            served_model = str(receipt.get("model_served")) if receipt and receipt.get("model_served") else None
            candidate_model = served_model or configured
            live_ready = bool(
                receipt
                and receipt.get("status") == "pass"
                and receipt.get("authenticated") is not False
                and receipt.get("model_identity_verified", bool(served_model))
                and served_model
            )
            if require_live and not live_ready:
                continue
            result.append(
                {
                    "candidate_id": f"{route.get('provider')}:{candidate_model}:{route.get('route_id')}",
                    "provider": route.get("provider"),
                    "route_id": route.get("route_id"),
                    "model": candidate_model,
                    "configured_model": configured,
                    "auth_mode": route.get("auth_mode"),
                    "cloud": bool(route.get("cloud", True)),
                    "priority": int(route.get("priority", 100)),
                    "live_ready": live_ready,
                    "receipt": receipt,
                    "kind": route.get("kind"),
                }
            )
    return sorted(
        result,
        key=lambda item: (
            0 if item["live_ready"] else 1,
            int(item["priority"]),
            str(item["candidate_id"]),
        ),
    )


def probe_routes(
    user_home: Path,
    *,
    max_probes: int = 8,
    timeout: int = 90,
) -> list[dict[str, Any]]:
    """Run explicit minimal live probes. This may consume provider quota."""
    from .mesh import delegate

    candidates = provider_candidates(user_home, require_live=False, cloud_only=False)
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        key = (
            str(candidate.get("provider")),
            str(candidate.get("route_id")),
            str(candidate.get("model")),
        )
        if key in seen:
            continue
        seen.add(key)
        if len(results) >= max_probes:
            break
        try:
            result = delegate(
                user_home,
                key[0],
                "Return only the text IOT-AI-READY.",
                stage="status-live-probe",
                model=key[2],
                auth_mode=str(candidate.get("auth_mode") or "auto"),
                allow_fallback=False,
                timeout=timeout,
                role="readiness-probe",
            )
        except Exception as exc:
            result = {
                "provider": key[0],
                "route_id": key[1],
                "model_requested": key[2],
                "status": "failed",
                "failure_class": type(exc).__name__,
                "error": str(exc),
            }
        results.append(result)
    return results
