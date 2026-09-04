# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
from __future__ import annotations

import os
import re
import shutil
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any
import ipaddress
import socket
from urllib.parse import parse_qs, unquote, urlparse

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


_METADATA_HOSTS = frozenset(
    {
        "metadata",
        "metadata.google.internal",
        "metadata.tencentyun.com",
        "instance-data",
        "instance-data.ec2.internal",
    }
)
_AWS_IMDS_V6 = ipaddress.ip_network("fd00:ec2::/32")
_NEVER_ALLOW_REASON = "metadata and link-local endpoints are forbidden"
_DOT_STRIP = ".\u3002\uff0e\u2024\uff61\ufe52"
_DOT_SEPARATORS = (
    "\u3002",
    "\uff0e",
    "\u2024",
    "\uff61",
    "\ufe52",
    "\u00b7",
    "\u2022",
    "\u2027",
    "\u2219",
    "\u22c5",
    "\u30fb",
    "\uff65",
)
_HYPHEN_IPV4_RUN = re.compile(r"(?<![\dA-Fa-f])(\d{1,10}(?:-\d{1,10}){1,3})(?![\dA-Fa-f])")
_DASH_SEPARATORS = (
    "\u00ad",
    "\u2010",
    "\u2011",
    "\u2012",
    "\u2013",
    "\u2014",
    "\u2212",
    "\ufe63",
    "\uff0d",
)
_CLOUD_IMDS_V4 = frozenset(
    {
        ipaddress.IPv4Address("169.254.169.254"),
        ipaddress.IPv4Address("100.100.100.200"),
        ipaddress.IPv4Address("168.63.129.16"),
    }
)
_IPV4_LABELS = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{1,3}){3})(?!\d)")


def _canonical_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    mapped = getattr(address, "ipv4_mapped", None)
    return mapped if mapped is not None else address


def _ipv4s_from_ipv6(address: ipaddress.IPv6Address) -> list[ipaddress.IPv4Address]:
    packed = address.packed
    found: list[ipaddress.IPv4Address] = []
    mapped = address.ipv4_mapped
    if mapped is not None:
        found.append(mapped)
    if packed[0:2] == b"\x20\x02":
        found.append(ipaddress.IPv4Address(packed[2:6]))
    if packed[0:12] == bytes.fromhex("0064ff9b0000000000000000"):
        found.append(ipaddress.IPv4Address(packed[12:16]))
    if packed[0:4] == bytes.fromhex("20010000"):
        found.append(ipaddress.IPv4Address(packed[4:8]))
        found.append(ipaddress.IPv4Address(bytes(byte ^ 0xFF for byte in packed[12:16])))
        found.append(ipaddress.IPv4Address(packed[12:16]))
    found.append(ipaddress.IPv4Address(packed[12:16]))
    return found


def _parse_numeric_label(part: str) -> int | None:
    try:
        lowered = part.casefold()
        if lowered.startswith("0x"):
            value = int(part, 16)
        elif len(part) > 1 and part.startswith("0") and all(ch in "01234567" for ch in part):
            value = int(part, 8)
        elif part.isdigit():
            value = int(part, 10)
        else:
            return None
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def _ipv4_from_numeric_parts(parts: list[int]) -> ipaddress.IPv4Address | None:
    if not parts or len(parts) > 4:
        return None
    if len(parts) == 4:
        if any(item > 255 for item in parts):
            return None
        octets = parts
    elif len(parts) == 3:
        first, second, packed = parts
        if first > 255 or second > 255 or packed > 0xFFFF:
            return None
        octets = [first, second, (packed >> 8) & 0xFF, packed & 0xFF]
    elif len(parts) == 2:
        first, packed = parts
        if first > 255 or packed > 0xFFFFFF:
            return None
        octets = [first, (packed >> 16) & 0xFF, (packed >> 8) & 0xFF, packed & 0xFF]
    else:
        packed = parts[0]
        if packed > 0xFFFFFFFF:
            return None
        octets = [(packed >> 24) & 0xFF, (packed >> 16) & 0xFF, (packed >> 8) & 0xFF, packed & 0xFF]
    try:
        return ipaddress.IPv4Address(bytes(octets))
    except ValueError:
        return None


def _ipv4s_from_hostname(raw: str) -> list[ipaddress.IPv4Address]:
    labels = [part for part in raw.split(".") if part]
    values = [_parse_numeric_label(part) for part in labels]
    found: list[ipaddress.IPv4Address] = []
    seen: set[ipaddress.IPv4Address] = set()

    def remember(address: ipaddress.IPv4Address | None) -> None:
        if address is None or address in seen:
            return
        seen.add(address)
        found.append(address)

    index = 0
    while index < len(values):
        if values[index] is None:
            index += 1
            continue
        end = index
        while end < len(values) and values[end] is not None:
            end += 1
        run = [int(item) for item in values[index:end]]
        skip_short: set[int] = set()
        for start in range(0, len(run) - 3):
            address = _ipv4_from_numeric_parts(run[start : start + 4])
            if address is None:
                continue
            remember(address)
            skip_short.add(start)
            skip_short.update(range(start + 1, start + 3))
        for start in range(len(run)):
            if start + 3 <= len(run) and run[start + 2] > 255:
                remember(_ipv4_from_numeric_parts(run[start : start + 3]))
            if start + 2 <= len(run) and run[start + 1] > 255:
                remember(_ipv4_from_numeric_parts(run[start : start + 2]))
            if start in skip_short:
                continue
            for width in (3, 2):
                if start + width > len(run):
                    continue
                remember(_ipv4_from_numeric_parts(run[start : start + width]))
        if len(run) == 1:
            remember(_ipv4_from_numeric_parts(run))
        index = end
    for match in _HYPHEN_IPV4_RUN.finditer(raw):
        parts = [_parse_numeric_label(part) for part in match.group(1).split("-")]
        if any(part is None for part in parts):
            continue
        remember(_ipv4_from_numeric_parts([int(part) for part in parts]))
    return found


def _metadata_host_match(lowered: str) -> bool:
    for name in _METADATA_HOSTS:
        if lowered == name or lowered.startswith(name + ".") or lowered.endswith("." + name):
            return True
    return False


def _ipv4_never_allowed(address: ipaddress.IPv4Address) -> bool:
    if address in _CLOUD_IMDS_V4:
        return True
    return bool(address.is_link_local or address.is_multicast or address.is_reserved or address.is_unspecified)


def _ip_is_never_allowed(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    address = _canonical_ip(address)
    if isinstance(address, ipaddress.IPv4Address):
        return _ipv4_never_allowed(address)
    for embedded in _ipv4s_from_ipv6(address):
        if _ipv4_never_allowed(embedded):
            return True
    if address in _AWS_IMDS_V6:
        return True
    return bool(address.is_link_local or address.is_multicast or address.is_reserved or address.is_unspecified)


def _ip_requires_private_allow(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    address = _canonical_ip(address)
    if _ip_is_never_allowed(address):
        return True
    if isinstance(address, ipaddress.IPv6Address):
        for embedded in _ipv4s_from_ipv6(address):
            if _ip_requires_private_allow(embedded):
                return True
    if address.is_private or address.is_loopback:
        return True
    return not address.is_global


def _normalize_host(host: str) -> str:
    raw = str(host or "").strip().strip("[]")
    previous = None
    while previous != raw:
        previous = raw
        raw = unicodedata.normalize("NFKC", unquote(raw))
    if "%" in raw:
        hostpart, _, _zone = raw.rpartition("%")
        if hostpart and ":" in hostpart:
            raw = hostpart
    raw = raw.strip()
    for separator in _DOT_SEPARATORS:
        raw = raw.replace(separator, ".")
    for separator in _DASH_SEPARATORS:
        raw = raw.replace(separator, "-")
    while raw and raw[-1] in _DOT_STRIP:
        raw = raw[:-1]
    return raw.rstrip(".")


def _host_has_forbidden_chars(raw: str) -> bool:
    return any(ord(ch) < 33 or ch in "/\\" for ch in raw)


def _contains_never_allow_ipv4(raw: str) -> bool:
    for match in _IPV4_LABELS.finditer(raw):
        try:
            address = ipaddress.IPv4Address(match.group(1))
        except ValueError:
            continue
        if _ip_is_never_allowed(address):
            return True
    return False


def _leading_ipv4(raw: str) -> ipaddress.IPv4Address | None:
    labels = raw.split(".")
    if len(labels) < 4 or not all(part.isdigit() for part in labels[:4]):
        return None
    try:
        return ipaddress.IPv4Address(".".join(labels[:4]))
    except ValueError:
        return None


def _host_matches(host: str, *, never_allowed: bool, resolve_dns: bool) -> bool:
    raw = _normalize_host(host)
    if not raw:
        return True
    if _host_has_forbidden_chars(raw) or _contains_never_allow_ipv4(raw):
        return True
    leading = _leading_ipv4(raw)
    if leading is not None and _ip_is_never_allowed(leading):
        return True
    if not never_allowed:
        if leading is not None and _ip_requires_private_allow(leading):
            return True
        for match in _IPV4_LABELS.finditer(raw):
            try:
                address = ipaddress.IPv4Address(match.group(1))
            except ValueError:
                continue
            if _ip_requires_private_allow(address):
                return True
    lowered = raw.casefold()
    embedded = _ipv4s_from_hostname(raw)
    if never_allowed:
        if _metadata_host_match(lowered):
            return True
        for address in embedded:
            if _ipv4_never_allowed(address):
                return True
    elif lowered in {"localhost"} or lowered.endswith((".local", ".internal", ".localhost")) or _metadata_host_match(lowered):
        return True
    elif any(_ip_requires_private_allow(address) for address in embedded):
        return True
    try:
        address = ipaddress.ip_address(raw)
        return _ip_is_never_allowed(address) if never_allowed else _ip_requires_private_allow(address)
    except ValueError:
        pass
    if not resolve_dns:
        return False
    try:
        for info in socket.getaddrinfo(raw, None):
            ip = str(info[4][0]).split("%")[0]
            try:
                address = ipaddress.ip_address(ip)
                if _ip_is_never_allowed(address) if never_allowed else _ip_requires_private_allow(address):
                    return True
            except ValueError:
                continue
    except (OSError, UnicodeError):
        if raw.replace(".", "").isdigit() or ":" in raw:
            return True
        return False
    return False


def host_is_never_allowed(host: str, *, resolve_dns: bool = True) -> bool:
    """Link-local, metadata, multicast, reserved, and AWS IMDS hosts cannot be opted in."""

    return _host_matches(host, never_allowed=True, resolve_dns=resolve_dns)


def host_requires_private_allow(host: str, *, resolve_dns: bool = True) -> bool:
    if host_is_never_allowed(host, resolve_dns=resolve_dns):
        return True
    return _host_matches(host, never_allowed=False, resolve_dns=resolve_dns)


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
    if host_is_never_allowed(parsed.hostname):
        return _NEVER_ALLOW_REASON
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
