# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .paths import config_root
from .util import atomic_json, load_json, utc_now

EXECUTABLES = {
    "claude": ("claude", "claude.exe"),
    "codex": ("codex", "codex.exe"),
    "gemini": ("gemini", "gemini.exe"),
    "grok": ("grok", "grok.exe"),
    "ollama": ("ollama", "ollama.exe"),
}
API_ENV_REFS = {
    "claude": "ANTHROPIC_API_KEY",
    "codex": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "grok": "XAI_API_KEY",
    "ollama": "OLLAMA_API_KEY",
}


def inventory_path(user_home: Path) -> Path:
    return config_root(user_home) / "inventory.json"


def _find_command(candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return str(Path(found).resolve())
    return None


def discover() -> dict[str, Any]:
    providers: dict[str, Any] = {}
    for provider, commands in EXECUTABLES.items():
        executable = _find_command(commands)
        env_name = API_ENV_REFS[provider]
        providers[provider] = {
            "executable": executable,
            "installed": executable is not None,
            "subscription_session": "unknown-until-live-doctor",
            "api_env_reference": env_name,
            "api_env_present": bool(os.environ.get(env_name)),
            "secret_value_recorded": False,
        }
    return {
        "schema": "iot-ai.discovery.v1",
        "generated_at": utc_now(),
        "providers": providers,
        "notice": "Executable discovery is not authentication or live-model proof. Run provider doctor for a bounded live check.",
    }


def _parse_server(raw: str) -> dict[str, str]:
    if "=" not in raw:
        raise ValueError("server must use NAME=URL")
    name, url = (part.strip() for part in raw.split("=", 1))
    if not name or not url:
        raise ValueError("server must use non-empty NAME=URL")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"invalid server URL: {url}")
    if parsed.username or parsed.password:
        raise ValueError("server URLs must not contain credentials")
    return {"name": name, "url": url, "enabled": "true"}


def init_inventory(
    user_home: Path,
    project_root: str | None,
    servers: list[str],
    apply: bool,
) -> dict[str, Any]:
    payload = {
        "schema": "iot-ai.inventory.v1",
        "updated_at": utc_now(),
        "project_root": str(Path(project_root).expanduser().resolve()) if project_root else None,
        "providers": discover()["providers"],
        "servers": [_parse_server(item) for item in servers],
        "secrets": {
            "storage": "environment-or-os-secret-store",
            "values_recorded": False,
        },
    }
    result = {"decision": "plan", "apply": apply, "inventory": payload}
    if apply:
        atomic_json(inventory_path(user_home), payload)
        result["decision"] = "pass"
        result["path"] = str(inventory_path(user_home))
    return result


def show_inventory(user_home: Path) -> dict[str, Any]:
    return load_json(inventory_path(user_home), {}) or {
        "schema": "iot-ai.inventory.v1",
        "configured": False,
        "providers": discover()["providers"],
        "servers": [],
    }
