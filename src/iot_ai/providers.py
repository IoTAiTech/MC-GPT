# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

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
        status = static_status(route)
        if not status["installed"]:
            continue
        if route.get("kind") == "api" and route.get("secret_env") and not status.get("credential_reference_present"):
            continue
        rows.append(status)
    return sorted(rows, key=lambda item: int(item.get("priority", 100)))


def add_route(user_home: Path, route: dict[str, Any], apply: bool = False) -> dict[str, Any]:
    data = load(user_home)
    if any(row["route_id"] == route["route_id"] for row in data["routes"]):
        raise ValueError("route already exists")
    if route.get("kind") == "api":
        if not route.get("endpoint") or not route.get("protocol"):
            raise ValueError("API routes require endpoint and protocol")
        if route.get("secret_value"):
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
