# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
"""Policy-aware meeting seat resolution.

Seat selection is explicit, auditable and Ollama-aware.  A meeting may request
all coder families, every model-specific Ollama Cloud seat, or a bounded
policy-selected subset.  The resolver never silently drops a requested seat.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .licensing import current
from .providers import load as load_routes, static_status
from .readiness import discover_ollama_cloud_models, provider_candidates
from .settings import load as load_settings

CODER_PROVIDERS = ("claude", "codex", "gemini", "grok")
ALL_WITH_OLLAMA_SELECTORS = {
    "all",
    "all-coders+ollama-clouds",
    "all-coders-and-ollama-clouds",
    "all-coders+ollama",
    "coders+ollama",
}
ALL_CODER_SELECTORS = {"all-coders", "coders", "all-coder"}
OLLAMA_CLOUD_SELECTORS = {"ollama-clouds", "all-ollama-clouds", "ollama-cloud"}


@dataclass(frozen=True)
class SeatPlan:
    selector: str
    requested_seats: tuple[str, ...]
    resolved_seats: tuple[str, ...]
    candidate_status: tuple[dict[str, Any], ...]
    excluded: tuple[dict[str, Any], ...]
    ollama_cloud_available: bool
    ollama_cloud_included: bool
    max_seats: int
    decision: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "iot-ai.meeting-seat-plan.v1",
            "selector": self.selector,
            "requested_seats": list(self.requested_seats),
            "resolved_seats": list(self.resolved_seats),
            "candidate_status": [dict(item) for item in self.candidate_status],
            "excluded": [dict(item) for item in self.excluded],
            "ollama_cloud_available": self.ollama_cloud_available,
            "ollama_cloud_included": self.ollama_cloud_included,
            "max_seats": self.max_seats,
            "decision": self.decision,
            "reason": self.reason,
        }


def _split(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _provider_routes(user_home: Path) -> list[dict[str, Any]]:
    settings = load_settings(user_home)
    result: list[dict[str, Any]] = []
    for route in load_routes(user_home).get("routes", []):
        provider = str(route.get("provider") or "")
        if not route.get("enabled", False):
            continue
        if not settings.get("providers", {}).get(provider, {}).get("enabled", True):
            continue
        if bool(route.get("cloud", True)) and not settings.get("cloud", {}).get("enabled", False):
            continue
        result.append({**route, **static_status(route)})
    return result


def _coder_seats(user_home: Path) -> tuple[list[str], list[dict[str, Any]]]:
    routes = _provider_routes(user_home)
    seats: list[str] = []
    status: list[dict[str, Any]] = []
    for provider in CODER_PROVIDERS:
        matching = [route for route in routes if route.get("provider") == provider]
        if not matching:
            continue
        seat = provider
        if seat not in seats:
            seats.append(seat)
        best = sorted(matching, key=lambda row: int(row.get("priority", 100)))[0]
        status.append(
            {
                "seat": seat,
                "provider": provider,
                "route_id": best.get("route_id"),
                "installed": bool(best.get("installed")),
                "live_ready": False,
                "status_basis": best.get("status_basis", "static-only"),
                "cloud": bool(best.get("cloud", True)),
            }
        )
    return seats, status


def _ollama_cloud_seats(user_home: Path) -> tuple[list[str], list[dict[str, Any]]]:
    settings = load_settings(user_home)
    if not settings.get("cloud", {}).get("enabled", False):
        return [], []
    if not settings.get("providers", {}).get("ollama", {}).get("enabled", True):
        return [], []

    # Include every exact model with a fresh live receipt.  If none exist,
    # preserve one explicit auto:cloud seat so the meeting records an honest
    # readiness/dispatch failure instead of silently omitting Ollama.
    candidates = [
        item
        for item in provider_candidates(user_home, require_live=False, cloud_only=True)
        if item.get("provider") == "ollama" and item.get("cloud")
    ]
    discovered = discover_ollama_cloud_models()
    exact_models: list[str] = []
    for item in candidates:
        model = str(item.get("model") or "")
        if model and not model.startswith("auto"):
            exact_models.append(model)
    exact_models.extend(discovered)
    exact_models = list(dict.fromkeys(exact_models))

    routes = [route for route in _provider_routes(user_home) if route.get("provider") == "ollama" and route.get("cloud")]
    if not routes:
        return [], []

    if not exact_models:
        seats = ["ollama@auto:cloud"]
        route = sorted(routes, key=lambda row: int(row.get("priority", 100)))[0]
        return seats, [
            {
                "seat": seats[0],
                "provider": "ollama",
                "route_id": route.get("route_id"),
                "model": "auto:cloud",
                "installed": bool(route.get("installed")),
                "live_ready": False,
                "status_basis": route.get("status_basis", "static-only"),
                "cloud": True,
            }
        ]

    by_model = {str(item.get("model")): item for item in candidates if item.get("model")}
    seats: list[str] = []
    status: list[dict[str, Any]] = []
    for model in exact_models:
        seat = f"ollama@{model}"
        seats.append(seat)
        item = by_model.get(model, {})
        status.append(
            {
                "seat": seat,
                "provider": "ollama",
                "route_id": item.get("route_id") or routes[0].get("route_id"),
                "model": model,
                "installed": bool(item.get("candidate_id") or routes[0].get("installed")),
                "live_ready": bool(item.get("live_ready")),
                "status_basis": "fresh-live-receipt" if item.get("live_ready") else "static-or-discovered",
                "cloud": True,
            }
        )
    return seats, status


def _explicit_seats(selector: str, ollama_clouds: list[str]) -> list[str]:
    values: list[str] = []
    for item in _split(selector):
        if item in OLLAMA_CLOUD_SELECTORS or item == "ollama":
            values.extend(ollama_clouds or ["ollama@auto:cloud"])
        else:
            values.append(item)
    return list(dict.fromkeys(values))


def resolve_meeting_seats(
    user_home: Path,
    selector: str = "auto",
    *,
    exclude_ollama: bool = False,
    allow_missing_ollama: bool = False,
    max_seats: int | None = None,
) -> SeatPlan:
    """Resolve a selector without dispatching providers.

    `auto` is bounded by the active entitlement and guarantees one Ollama Cloud
    seat whenever the cloud family is configured.  The explicit
    `all-coders+ollama-clouds` selector includes every configured coder and
    every discovered model-specific Ollama Cloud seat.
    """
    normalized = (selector or "auto").strip().lower()
    entitlement = current()
    limit = int(max_seats or entitlement.max_providers)
    if limit < 1:
        raise ValueError("max_seats must be positive")

    coders, coder_status = _coder_seats(user_home)
    ollama, ollama_status = _ollama_cloud_seats(user_home)
    ollama_available = bool(ollama)

    if normalized in ALL_WITH_OLLAMA_SELECTORS:
        requested = [*coders, *ollama]
    elif normalized in ALL_CODER_SELECTORS:
        requested = list(coders)
    elif normalized in OLLAMA_CLOUD_SELECTORS:
        requested = list(ollama)
    elif normalized == "auto":
        # Keep provider diversity under the edition limit and reserve one seat
        # for first-class Ollama Cloud whenever available.
        requested = []
        coder_budget = limit - (1 if ollama_available and not exclude_ollama else 0)
        requested.extend(coders[: max(0, coder_budget)])
        if ollama_available and not exclude_ollama:
            # Prefer a live-ready exact model, otherwise retain auto:cloud so
            # the attempt/outage is recorded rather than hidden.
            live = [row["seat"] for row in ollama_status if row.get("live_ready")]
            requested.append((live or ollama)[0])
    else:
        requested = _explicit_seats(normalized, ollama)

    requested = list(dict.fromkeys(requested))
    settings = load_settings(user_home)
    require_ollama = bool(settings.get("meeting", {}).get("require_ollama_cloud_when_available", True))
    explicitly_allows_omission = exclude_ollama
    if exclude_ollama:
        requested = [seat for seat in requested if not seat.startswith("ollama@") and seat != "ollama"]

    contains_ollama = any(seat.startswith("ollama@") or seat == "ollama" for seat in requested)
    if (
        ollama_available
        and require_ollama
        and not contains_ollama
        and not explicitly_allows_omission
        and normalized not in ALL_CODER_SELECTORS
    ):
        return SeatPlan(
            selector=normalized,
            requested_seats=tuple(requested),
            resolved_seats=(),
            candidate_status=tuple([*coder_status, *ollama_status]),
            excluded=(),
            ollama_cloud_available=True,
            ollama_cloud_included=False,
            max_seats=limit,
            decision="block",
            reason="OLLAMA_CLOUD_FIRST_CLASS_SEAT_OMITTED",
        )

    # A literal list containing every coder but no Ollama is the exact failure
    # observed in prior meetings.  Block it when Ollama Cloud is configured.
    literal = set(_split(normalized))
    if (
        ollama_available
        and require_ollama
        and not contains_ollama
        and not explicitly_allows_omission
        and set(CODER_PROVIDERS).issubset(literal)
    ):
        return SeatPlan(
            selector=normalized,
            requested_seats=tuple(requested),
            resolved_seats=(),
            candidate_status=tuple([*coder_status, *ollama_status]),
            excluded=(),
            ollama_cloud_available=True,
            ollama_cloud_included=False,
            max_seats=limit,
            decision="block",
            reason="OLLAMA_CLOUD_FIRST_CLASS_SEAT_OMITTED",
        )

    if normalized in ALL_WITH_OLLAMA_SELECTORS and not ollama_available and not allow_missing_ollama:
        return SeatPlan(
            selector=normalized,
            requested_seats=tuple(requested),
            resolved_seats=(),
            candidate_status=tuple([*coder_status, *ollama_status]),
            excluded=(),
            ollama_cloud_available=False,
            ollama_cloud_included=False,
            max_seats=limit,
            decision="block",
            reason="NO_OLLAMA_CLOUD_SEAT_DISCOVERED",
        )

    if len(requested) > limit:
        return SeatPlan(
            selector=normalized,
            requested_seats=tuple(requested),
            resolved_seats=(),
            candidate_status=tuple([*coder_status, *ollama_status]),
            excluded=tuple({"seat": seat, "reason": "edition-seat-limit"} for seat in requested[limit:]),
            ollama_cloud_available=ollama_available,
            ollama_cloud_included=contains_ollama,
            max_seats=limit,
            decision="block",
            reason=f"SEAT_LIMIT_EXCEEDED:{len(requested)}>{limit}",
        )

    status_by_seat = {item["seat"]: item for item in [*coder_status, *ollama_status]}
    candidate_status = [status_by_seat.get(seat, {"seat": seat, "provider": seat.split("@", 1)[0], "status_basis": "explicit"}) for seat in requested]
    return SeatPlan(
        selector=normalized,
        requested_seats=tuple(requested),
        resolved_seats=tuple(requested),
        candidate_status=tuple(candidate_status),
        excluded=(),
        ollama_cloud_available=ollama_available,
        ollama_cloud_included=contains_ollama,
        max_seats=limit,
        decision="pass",
    )
