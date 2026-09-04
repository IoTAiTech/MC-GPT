# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
from __future__ import annotations

import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any
import ipaddress
import socket
from urllib.parse import parse_qs, urlparse

from .exec_pin import pin_executable
from .paths import routes_path
from .settings import load as load_settings
from .util import atomic_json, load_json, utc_now

DEFAULT_ROUTES = [
    {
        "route_id": "claude-subscription",
        "provider": "claude",
        "kind": "cli",
        "auth_mode": "subscription",
        "command": ["claude", "-p", "{prompt}"],
        "enabled": True,
        "priority": 10,
        "model": "auto",
        "cloud": True,
    },
    {
        "route_id": "codex-subscription",
        "provider": "codex",
        "kind": "cli",
        "auth_mode": "subscription",
        "command": ["codex", "exec", "{prompt}"],
        "enabled": True,
        "priority": 10,
        "model": "auto",
        "cloud": True,
    },
    {
        "route_id": "gemini-subscription",
        "provider": "gemini",
        "kind": "cli",
        "auth_mode": "subscription",
        "command": ["gemini", "-p", "{prompt}"],
        "enabled": True,
        "priority": 10,
        "model": "auto",
        "cloud": True,
    },
    {
        "route_id": "grok-subscription",
        "provider": "grok",
        "kind": "cli",
        "auth_mode": "subscription",
        "command": ["grok", "-p", "{prompt}"],
        "enabled": True,
        "priority": 10,
        "model": "auto",
        "cloud": True,
    },
    {
        "route_id": "ollama-cloud-subscription",
        "provider": "ollama",
        "kind": "cli",
        "auth_mode": "subscription",
        "command": ["ollama", "run", "{model}", "{prompt}"],
        "enabled": True,
        "priority": 20,
        "model": "auto:cloud",
        "models": [],
        "cloud": True,
    },
    {
        "route_id": "ollama-cloud-api",
        "provider": "ollama",
        "kind": "api",
        "auth_mode": "api",
        "endpoint": "https://ollama.com",
        "protocol": "ollama",
        "secret_env": "OLLAMA_API_KEY",
        "allow_private_endpoint": False,
        "enabled": False,
        "priority": 25,
        "model": "auto:cloud",
        "models": [],
        "cloud": True,
    },
]


def load(user_home: Path) -> dict[str, Any]:
    data = load_json(routes_path(user_home))
    if data is None:
        data = {"schema": "iot-ai.providers.v1", "routes": deepcopy(DEFAULT_ROUTES)}
    return data


def save(user_home: Path, data: dict[str, Any]) -> None:
    payload = dict(data)
    payload["updated_at"] = utc_now()
    atomic_json(routes_path(user_home), payload)


def _env_present(name: str | None) -> bool | None:
    if not name:
        return None
    return bool(os.environ.get(name))


def static_status(route: dict[str, Any]) -> dict[str, Any]:
    item = dict(route)
    if item.get("kind") == "api":
        item["installed"] = bool(item.get("endpoint") and item.get("protocol"))
        item["credential_reference_present"] = _env_present(item.get("secret_env"))
    else:
        command = item.get("command") or []
        executable = command[0] if isinstance(command, list) and command else ""
        try:
            item["installed"] = bool(executable and pin_executable(str(executable)))
        except (RuntimeError, PermissionError, OSError):
            item["installed"] = False
        item["credential_reference_present"] = None
    item["authenticated"] = None
    item["live_ready"] = False
    item["status_basis"] = "static-only"
    return item


def _ip_requires_private_allow(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def host_requires_private_allow(host: str, *, resolve_dns: bool = True) -> bool:
    raw = str(host or "").strip().strip("[]")
    if not raw:
        return True
    lowered = raw.casefold()
    if lowered in {"localhost", "metadata.google.internal", "metadata", "instance-data"} or lowered.endswith(
        (".local", ".internal", ".localhost")
    ):
        return True
    try:
        return _ip_requires_private_allow(ipaddress.ip_address(raw.split("%")[0]))
    except ValueError:
        pass
    if not resolve_dns:
        return False
    try:
        for info in socket.getaddrinfo(raw, None):
            ip = str(info[4][0]).split("%")[0]
            try:
                if _ip_requires_private_allow(ipaddress.ip_address(ip)):
                    return True
            except ValueError:
                continue
    except OSError:
        return False
    return False


def endpoint_is_forbidden(endpoint: str, *, allow_private: bool = False) -> str | None:
    parsed = urlparse(endpoint)
    if parsed.username or parsed.password:
        return "endpoint must not contain embedded credentials"
    if parsed.fragment:
        return "endpoint must not contain a fragment"
    query = parse_qs(parsed.query)
    secretish = ("token", "key", "secret", "password", "api_key", "access_token", "credential")
    for name in query:
        lowered = name.lower()
        if any(item in lowered for item in secretish):
            return "endpoint must not contain query credentials"
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        return "endpoint must be an http or https URL"
    if parsed.scheme != "https" and not allow_private:
        return "cloud API routes require HTTPS"
    if host_requires_private_allow(parsed.hostname) and not allow_private:
        return "private provider endpoint requires allow_private_endpoint"
    return None


def eligible_routes(
    user_home: Path,
    provider: str | None = None,
    auth_mode: str | None = None,
) -> list[dict[str, Any]]:
    settings = load_settings(user_home)
    rows: list[dict[str, Any]] = []
    for route in load(user_home)["routes"]:
        if not route.get("enabled", False):
            continue
        if provider and route.get("provider") != provider:
            continue
        if auth_mode and auth_mode not in {"auto", "hybrid"} and route.get("auth_mode") != auth_mode:
            continue
        if not settings.get("providers", {}).get(route.get("provider"), {}).get("enabled", True):
            continue
        if route.get("cloud", True) and not settings.get("cloud", {}).get("enabled", True):
            continue
        model = str(route.get("model", "auto"))
        if not settings.get("models", {}).get("all_enabled", True):
            continue
        if model in set(settings.get("models", {}).get("disabled", [])):
            continue
        if not route.get("cloud", True) and not settings.get("models", {}).get("local_enabled", False):
            continue
        routing = settings.get("routing") or {}
        ollama = routing.get("ollama") or {}
        if route.get("provider") == "ollama" and route.get("cloud") and ollama.get("cloud_policy") == "never":
            continue
        if route.get("provider") == "ollama" and not route.get("cloud") and ollama.get("local_policy") == "never":
            continue
        if ollama.get("local_policy") == "only" and not (route.get("provider") == "ollama" and not route.get("cloud")):
            continue
        if ollama.get("cloud_policy") == "only" and not (route.get("provider") == "ollama" and route.get("cloud")):
            continue
        allow = routing.get("model_allowlist") or []
        deny = routing.get("model_denylist") or []
        if deny and model in deny:
            continue
        if allow and model not in allow and model not in {"auto", "auto:cloud"}:
            continue
        status = static_status(route)
        if not status["installed"]:
            continue
        if route.get("kind") == "api" and route.get("secret_env") and not status.get("credential_reference_present"):
            continue
        rows.append(status)
    return sorted(rows, key=lambda item: int(item.get("priority", 100)))


def materialize_api_profiles(user_home: Path, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Turn credential-free settings API profiles into provider routes."""

    from .settings import load as load_settings

    document = settings if settings is not None else load_settings(user_home)
    profiles = document.get("api_profiles") or {}
    created: list[str] = []
    skipped: list[dict[str, str]] = []
    existing = {str(row.get("route_id")) for row in load(user_home).get("routes") or []}
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            skipped.append({"id": str(name), "reason": "invalid-profile"})
            continue
        if profile.get("enabled") is False:
            skipped.append({"id": str(name), "reason": "disabled"})
            continue
        route_id = f"settings-api-{name}"
        if route_id in existing:
            skipped.append({"id": str(name), "reason": "already-present"})
            continue
        endpoint = profile.get("endpoint")
        if not endpoint and profile.get("endpoint_env"):
            endpoint = os.environ.get(str(profile["endpoint_env"]))
        if not endpoint:
            skipped.append({"id": str(name), "reason": "endpoint-unresolved"})
            continue
        allow_private = bool(profile.get("allow_private_endpoint"))
        classification = str(profile.get("classification") or "cloud")
        if classification == "private" and not allow_private:
            skipped.append({"id": str(name), "reason": "private-endpoint-not-allowed"})
            continue
        forbidden = endpoint_is_forbidden(str(endpoint), allow_private=allow_private)
        if forbidden:
            skipped.append({"id": str(name), "reason": forbidden})
            continue
        route = {
            "route_id": route_id,
            "provider": str(profile.get("provider") or name),
            "kind": "api",
            "auth_mode": "api",
            "endpoint": str(endpoint),
            "protocol": str(profile.get("protocol") or "openai-compatible"),
            "model": profile.get("model") or "auto",
            "models": list(profile.get("models") or []),
            "enabled": True,
            "priority": int(profile.get("priority") or 50),
            "cloud": classification != "private",
            "allow_private_endpoint": allow_private,
            "secret_env": profile.get("secret_env"),
            "source": "settings-api-profile",
        }
        add_route(user_home, route, apply=True)
        created.append(route_id)
        existing.add(route_id)
    return {
        "schema": "iot-ai.api-profile-materialization.v1",
        "created": created,
        "skipped": skipped,
    }


def add_route(user_home: Path, route: dict[str, Any], apply: bool = False) -> dict[str, Any]:
    data = load(user_home)
    if any(row["route_id"] == route["route_id"] for row in data["routes"]):
        raise ValueError("route already exists")
    if route.get("kind") == "api":
        if not route.get("endpoint") or not route.get("protocol"):
            raise ValueError("API routes require endpoint and protocol")
        if route.get("secret_value"):
            raise ValueError("secret values are forbidden; use secret_env")
        forbidden = endpoint_is_forbidden(
            str(route.get("endpoint")),
            allow_private=bool(route.get("allow_private_endpoint")),
        )
        if forbidden:
            raise ValueError(forbidden)
        if any(key in route for key in ("password", "api_key", "token", "secret")):
            raise ValueError("secret values are forbidden; use secret_env")
    elif not route.get("command"):
        raise ValueError("CLI routes require a command template")
    if not apply:
        return {"decision": "plan", "route": route}
    data["routes"].append(route)
    save(user_home, data)
    return {"decision": "pass", "route": route}


def mutate_route(user_home: Path, route_id: str, action: str, apply: bool = False) -> dict[str, Any]:
    data = load(user_home)
    idx = next((i for i, row in enumerate(data["routes"]) if row["route_id"] == route_id), None)
    if idx is None:
        raise ValueError(f"unknown route: {route_id}")
    if not apply:
        return {"decision": "plan", "action": action, "route": data["routes"][idx]}
    if action == "remove":
        data["routes"].pop(idx)
    elif action in {"enable", "disable"}:
        data["routes"][idx]["enabled"] = action == "enable"
    else:
        raise ValueError(action)
    save(user_home, data)
    return {"decision": "pass", "action": action, "route_id": route_id}
