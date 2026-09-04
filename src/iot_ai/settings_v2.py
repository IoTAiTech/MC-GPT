# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-04
"""Settings v2 helper for the single settings authority in settings.py.

This module is not a second settings store. load/save remain in settings.py.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from .licensing import current as current_entitlements
from .util import utc_now

SCHEMA_V1 = "iot-ai.settings.v1"
SCHEMA_V2 = "iot-ai.settings.v2"
ROUTER_VERSION = "1.0.0"
OLLAMA_POLICIES = ("never", "fallback", "prefer", "required", "only")
EFFORT_ORDER = ("none", "low", "medium", "high", "xhigh", "max")
SETTINGS_EFFORT_VALUES = ("low", "medium", "high", "xhigh")
GOVERNED_TOP_LEVEL = frozenset(
    {
        "schema",
        "edition",
        "cloud",
        "providers",
        "models",
        "meeting",
        "multi_coder",
        "telemetry",
        "autopilot",
        "dashboard",
        "agent_runtime",
        "orchestration",
        "knowledge",
        "diagnostics",
        "storage",
        "platform",
        "ollama",
        "agent_contracts",
        "superpowers_profile",
        "compliance",
        "routing",
        "skills",
        "api_profiles",
        "updated_at",
    }
)
LICENSE_ALLOWLIST = (
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "LicenseRef-PolyForm-Noncommercial-1.0.0",
)
SECRET_KEY_RE = re.compile(
    r"(?:^|_)(password|passwd|secret|api_key|apikey|token|private_key|credential|authorization)s?(?:$|_value)",
    re.I,
)
SECRET_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|xai-[A-Za-z0-9]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.I,
)
EXACT_SECRET_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "token",
        "private_key",
        "credential",
        "authorization",
        "secret_value",
        "access_token",
        "key",
        "keys",
        "openai_api_key",
        "xai_api_key",
        "anthropic_api_key",
    }
)
DEFAULT_ROLE_BINDINGS: dict[str, dict[str, Any]] = {
    "implementation-engineer": {
        "preferred_providers": ["codex"],
        "permitted_providers": [],
        "denied_providers": [],
        "preferred_models": [],
        "permitted_models": [],
        "fallback_sequence": ["codex", "grok", "claude"],
        "required_provider_family": None,
        "effort": None,
        "minimum_effort": None,
        "allow_reuse": True,
    },
    "security-challenger": {
        "preferred_providers": ["grok"],
        "permitted_providers": [],
        "denied_providers": [],
        "preferred_models": [],
        "permitted_models": [],
        "fallback_sequence": ["grok", "codex", "claude"],
        "required_provider_family": None,
        "effort": None,
        "minimum_effort": None,
        "allow_reuse": True,
    },
}

ROUTING_DEFAULTS: dict[str, Any] = {
    "active_preset": "balanced",
    "provider_order": ["claude", "codex", "gemini", "grok", "ollama"],
    "max_distinct_models": 16,
    "max_distinct_providers": 16,
    "max_candidates_per_role": 4,
    "require_provider_diversity": True,
    "model_allowlist": [],
    "model_denylist": [],
    "role_bindings": deepcopy(DEFAULT_ROLE_BINDINGS),
    "effort": {"default": "medium", "by_role": {}, "by_provider": {}, "by_model": {}},
    "ollama": {"local_policy": "never", "cloud_policy": "prefer"},
}

SKILLS_DEFAULTS: dict[str, Any] = {
    "auto_discover": True,
    "max_selected": 4,
    "silent_user_responses": True,
    "execution_mode_default": "reference-only",
    "license_allowlist": list(LICENSE_ALLOWLIST),
    "allow": [],
    "deny": [],
    "extra_roots": [],
    "design_policy": "off",
    "require_browser_acceptance": False,
}

API_PROFILES_DEFAULTS: dict[str, Any] = {}

PRESETS: dict[str, dict[str, Any]] = {
    "balanced": {
        "routing": {
            "active_preset": "balanced",
            "provider_order": ["claude", "codex", "gemini", "grok", "ollama"],
            "max_distinct_models": 16,
            "require_provider_diversity": True,
            "ollama": {"local_policy": "never", "cloud_policy": "prefer"},
        },
        "skills": {"design_policy": "off", "require_browser_acceptance": False},
    },
    "no-ollama": {
        "routing": {
            "active_preset": "no-ollama",
            "ollama": {"local_policy": "never", "cloud_policy": "never"},
        }
    },
    "no-local-ollama": {
        "routing": {
            "active_preset": "no-local-ollama",
            "ollama": {"local_policy": "never", "cloud_policy": "prefer"},
        }
    },
    "ollama-local-first": {
        "routing": {
            "active_preset": "ollama-local-first",
            "provider_order": ["ollama", "claude", "codex", "grok", "gemini"],
            "ollama": {"local_policy": "prefer", "cloud_policy": "fallback"},
        },
        "models": {"local_enabled": True},
    },
    "ollama-cloud-first": {
        "routing": {
            "active_preset": "ollama-cloud-first",
            "provider_order": ["ollama", "claude", "codex", "grok", "gemini"],
            "ollama": {"local_policy": "never", "cloud_policy": "prefer"},
        }
    },
    "sovereign-local": {
        "routing": {
            "active_preset": "sovereign-local",
            "provider_order": ["ollama"],
            "max_distinct_models": 4,
            "ollama": {"local_policy": "only", "cloud_policy": "never"},
        },
        "cloud": {"enabled": False},
        "models": {"local_enabled": True, "cloud_preferred": False},
    },
    "cloud-first": {
        "routing": {
            "active_preset": "cloud-first",
            "provider_order": ["claude", "codex", "grok", "gemini", "ollama"],
            "ollama": {"local_policy": "never", "cloud_policy": "fallback"},
        },
        "cloud": {"enabled": True},
    },
    "design-quality": {
        "routing": {
            "active_preset": "design-quality",
            "effort": {"default": "high", "by_role": {"operator-ux-reviewer": "high"}},
        },
        "skills": {
            "design_policy": "auto-visual-only",
            "require_browser_acceptance": True,
            "allow": ["iot-ai-web-visual-quality"],
        },
    },
    "maximum-quality": {
        "routing": {
            "active_preset": "maximum-quality",
            "max_distinct_models": 8,
            "require_provider_diversity": True,
            "effort": {"default": "xhigh"},
            "ollama": {"local_policy": "fallback", "cloud_policy": "prefer"},
        },
        "skills": {
            "design_policy": "auto-visual-only",
            "require_browser_acceptance": True,
            "max_selected": 6,
        },
    },
}


def canonical_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_dumps(value).encode("utf-8")).hexdigest()


def empty_role_binding() -> dict[str, Any]:
    return {
        "preferred_providers": [],
        "permitted_providers": [],
        "denied_providers": [],
        "preferred_models": [],
        "permitted_models": [],
        "fallback_sequence": [],
        "required_provider_family": None,
        "effort": None,
        "minimum_effort": None,
        "allow_reuse": True,
    }


def _as_str_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"invalid {field}: expected a list of strings")
    return [item.strip() for item in value if item.strip()]


def _as_policy(value: Any, field: str) -> str:
    text = str(value or "never").strip().lower()
    if text not in OLLAMA_POLICIES:
        raise ValueError(f"invalid {field}: {value}; allowed: {', '.join(OLLAMA_POLICIES)}")
    return text


def _as_effort(value: Any, field: str, *, allow_none: bool = False) -> str | None:
    if value in (None, "", "null") and allow_none:
        return None
    text = str(value or "medium").strip().lower()
    if text not in SETTINGS_EFFORT_VALUES:
        raise ValueError(f"invalid {field}: {value}; allowed: {', '.join(SETTINGS_EFFORT_VALUES)}")
    return text


def _as_int(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"invalid {field}: boolean is not an integer")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().lstrip("+-").isdigit():
        number = int(value)
    else:
        raise ValueError(f"invalid {field}: {value}")
    if number < minimum or number > maximum:
        raise ValueError(f"invalid {field}: {number} not in {minimum}..{maximum}")
    return number


def normalize_role_binding(raw: Any, role_id: str) -> dict[str, Any]:
    data = empty_role_binding()
    if raw is None:
        return data
    if not isinstance(raw, dict):
        raise ValueError(f"invalid role binding for {role_id}")
    data["preferred_providers"] = _as_str_list(raw.get("preferred_providers"), f"{role_id}.preferred_providers")
    data["permitted_providers"] = _as_str_list(raw.get("permitted_providers"), f"{role_id}.permitted_providers")
    data["denied_providers"] = _as_str_list(raw.get("denied_providers"), f"{role_id}.denied_providers")
    data["preferred_models"] = _as_str_list(raw.get("preferred_models") or raw.get("preferred_exact_models"), f"{role_id}.preferred_models")
    data["permitted_models"] = _as_str_list(raw.get("permitted_models") or raw.get("permitted_exact_models"), f"{role_id}.permitted_models")
    data["fallback_sequence"] = _as_str_list(raw.get("fallback_sequence"), f"{role_id}.fallback_sequence")
    family = raw.get("required_provider_family")
    data["required_provider_family"] = None if family in (None, "", "null") else str(family).strip().lower()
    data["effort"] = _as_effort(raw.get("effort") or raw.get("requested_effort"), f"{role_id}.effort", allow_none=True)
    data["minimum_effort"] = _as_effort(raw.get("minimum_effort") or raw.get("minimum_acceptable_effort"), f"{role_id}.minimum_effort", allow_none=True)
    reuse = raw.get("allow_reuse", raw.get("reuse_same_candidate", True))
    if not isinstance(reuse, bool):
        raise ValueError(f"invalid {role_id}.allow_reuse")
    data["allow_reuse"] = reuse
    return data


def normalize_routing(raw: Any) -> dict[str, Any]:
    routing = deepcopy(ROUTING_DEFAULTS)
    if raw is None:
        return routing
    if not isinstance(raw, dict):
        raise ValueError("routing must be an object")
    if "active_preset" in raw and raw["active_preset"] is not None:
        routing["active_preset"] = str(raw["active_preset"]).strip() or "balanced"
    if "provider_order" in raw:
        routing["provider_order"] = _as_str_list(raw.get("provider_order"), "routing.provider_order")
    if "max_distinct_models" in raw:
        routing["max_distinct_models"] = _as_int(raw["max_distinct_models"], "routing.max_distinct_models", minimum=1, maximum=64)
    if "max_distinct_providers" in raw:
        routing["max_distinct_providers"] = _as_int(raw["max_distinct_providers"], "routing.max_distinct_providers", minimum=1, maximum=64)
    if "max_candidates_per_role" in raw:
        routing["max_candidates_per_role"] = _as_int(raw["max_candidates_per_role"], "routing.max_candidates_per_role", minimum=1, maximum=16)
    if "require_provider_diversity" in raw:
        if not isinstance(raw["require_provider_diversity"], bool):
            raise ValueError("routing.require_provider_diversity must be boolean")
        routing["require_provider_diversity"] = raw["require_provider_diversity"]
    if "model_allowlist" in raw:
        routing["model_allowlist"] = _as_str_list(raw.get("model_allowlist"), "routing.model_allowlist")
    if "model_denylist" in raw:
        routing["model_denylist"] = _as_str_list(raw.get("model_denylist"), "routing.model_denylist")
    bindings = raw.get("role_bindings")
    if bindings is not None:
        if not isinstance(bindings, dict):
            raise ValueError("routing.role_bindings must be an object")
        merged = deepcopy(routing["role_bindings"])
        for role_id, binding in bindings.items():
            merged[str(role_id)] = normalize_role_binding(binding, str(role_id))
        routing["role_bindings"] = merged
    effort = raw.get("effort")
    if effort is not None:
        if not isinstance(effort, dict):
            raise ValueError("routing.effort must be an object")
        routing["effort"]["default"] = _as_effort(effort.get("default", routing["effort"]["default"]), "routing.effort.default")
        for key in ("by_role", "by_provider", "by_model"):
            block = effort.get(key, routing["effort"][key])
            if not isinstance(block, dict):
                raise ValueError(f"routing.effort.{key} must be an object")
            routing["effort"][key] = {
                str(name): _as_effort(level, f"routing.effort.{key}.{name}")
                for name, level in block.items()
            }
    ollama = raw.get("ollama")
    if ollama is not None:
        if not isinstance(ollama, dict):
            raise ValueError("routing.ollama must be an object")
        routing["ollama"]["local_policy"] = _as_policy(ollama.get("local_policy", routing["ollama"]["local_policy"]), "routing.ollama.local_policy")
        routing["ollama"]["cloud_policy"] = _as_policy(ollama.get("cloud_policy", routing["ollama"]["cloud_policy"]), "routing.ollama.cloud_policy")
    return routing


def normalize_skills(raw: Any) -> dict[str, Any]:
    skills = deepcopy(SKILLS_DEFAULTS)
    if raw is None:
        return skills
    if not isinstance(raw, dict):
        raise ValueError("skills must be an object")
    for flag in ("auto_discover", "silent_user_responses", "require_browser_acceptance"):
        if flag in raw:
            if not isinstance(raw[flag], bool):
                raise ValueError(f"skills.{flag} must be boolean")
            skills[flag] = raw[flag]
    if "max_selected" in raw:
        skills["max_selected"] = _as_int(raw["max_selected"], "skills.max_selected", minimum=0, maximum=16)
    if "execution_mode_default" in raw:
        mode = str(raw["execution_mode_default"]).strip()
        if mode not in {"reference-only", "host-native"}:
            raise ValueError("skills.execution_mode_default must be reference-only or host-native")
        skills["execution_mode_default"] = mode
    if "license_allowlist" in raw:
        skills["license_allowlist"] = _as_str_list(raw.get("license_allowlist"), "skills.license_allowlist")
    for key in ("allow", "deny", "extra_roots"):
        if key in raw:
            skills[key] = _as_str_list(raw.get(key), f"skills.{key}")
    if "design_policy" in raw:
        policy = str(raw["design_policy"]).strip()
        if policy not in {"off", "auto-visual-only"}:
            raise ValueError("skills.design_policy must be off or auto-visual-only")
        skills["design_policy"] = policy
    return skills


def normalize_api_profiles(raw: Any) -> dict[str, Any]:
    if raw in (None, {}):
        return {}
    if not isinstance(raw, dict):
        raise ValueError("api_profiles must be an object")
    out: dict[str, Any] = {}
    for name, profile in raw.items():
        if not isinstance(profile, dict):
            raise ValueError(f"api_profiles.{name} must be an object")
        forbidden = [key for key in profile if SECRET_KEY_RE.search(str(key))]
        if forbidden:
            raise ValueError("secret values are forbidden in settings; use an environment-variable reference")
        if profile.get("secret") or profile.get("api_key") or profile.get("token"):
            raise ValueError("secret values are forbidden in settings; use secret_env")
        endpoint = profile.get("endpoint")
        endpoint_env = profile.get("endpoint_env")
        if endpoint and ("://" in str(endpoint) and ("@" in str(endpoint).split("://", 1)[-1].split("/", 1)[0] or "?" in str(endpoint) or "#" in str(endpoint))):
            raise ValueError(f"api_profiles.{name}.endpoint must not contain credentials, query or fragment")
        enabled = profile.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"api_profiles.{name}.enabled must be boolean")
        out[str(name)] = {
            "endpoint": None if endpoint in (None, "") else str(endpoint),
            "endpoint_env": None if endpoint_env in (None, "") else str(endpoint_env),
            "protocol": str(profile.get("protocol") or "openai-compatible"),
            "provider": str(profile.get("provider") or name),
            "model": profile.get("model"),
            "models": _as_str_list(profile.get("models"), f"api_profiles.{name}.models"),
            "secret_env": None if not profile.get("secret_env") else str(profile.get("secret_env")),
            "priority": _as_int(profile.get("priority", 50), f"api_profiles.{name}.priority", minimum=1, maximum=1000),
            "classification": str(profile.get("classification") or profile.get("cloud_private") or ("cloud" if profile.get("cloud", True) else "private")),
            "enabled": enabled,
        }
    return out


def _forbidden_settings_key(key: str) -> bool:
    lowered = str(key).lower().replace("-", "_")
    if lowered in {"secret_env", "endpoint_env"}:
        return False
    compact = lowered.replace("_", "")
    if compact in {"apikey", "passwd", "authorization"}:
        return True
    if lowered in EXACT_SECRET_KEYS or bool(SECRET_KEY_RE.fullmatch(lowered)):
        return True
    if "api_key" in lowered or "password" in lowered or "private_key" in lowered:
        return True
    if lowered.endswith("_token") or lowered.endswith("_secret"):
        return True
    if lowered.endswith("_key") and lowered not in {"schema"}:
        return True
    return False


def assert_no_secrets(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            dotted = f"{path}.{key}" if path else str(key)
            if _forbidden_settings_key(str(key)):
                raise ValueError("secret values are forbidden in settings; use an environment-variable reference")
            assert_no_secrets(item, dotted)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_no_secrets(item, f"{path}[{index}]")
    elif isinstance(value, str) and SECRET_VALUE_RE.search(value):
        raise ValueError("secret values are forbidden in settings; use an environment-variable reference")


def inject_v2(document: dict[str, Any]) -> dict[str, Any]:
    """In-memory v1→v2 normalization. Does not persist."""
    out = deepcopy(document)
    schema = out.get("schema")
    if schema not in {SCHEMA_V1, SCHEMA_V2, None, ""}:
        raise ValueError(f"unsupported-schema: {schema}")
    out["routing"] = normalize_routing(out.get("routing"))
    out["skills"] = normalize_skills(out.get("skills"))
    out["api_profiles"] = normalize_api_profiles(out.get("api_profiles"))
    if schema in {None, ""}:
        out["schema"] = SCHEMA_V1
    return out


def validate_settings_document(document: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return {"decision": "block", "errors": ["settings document is not an object"]}
    try:
        assert_no_secrets(document)
    except ValueError as exc:
        errors.append(str(exc))
    try:
        normalize_routing(document.get("routing"))
    except ValueError as exc:
        errors.append(str(exc))
    try:
        normalize_skills(document.get("skills"))
    except ValueError as orig:
        errors.append(str(orig))
    try:
        normalize_api_profiles(document.get("api_profiles"))
    except ValueError as orig:
        errors.append(str(orig))
    schema = document.get("schema")
    if schema not in {SCHEMA_V1, SCHEMA_V2, None}:
        errors.append(f"unsupported schema: {schema}")
    return {"decision": "pass" if not errors else "block", "errors": errors, "schema": schema or SCHEMA_V1}


def migrate_document(document: dict[str, Any]) -> dict[str, Any]:
    migrated = inject_v2(document)
    migrated["schema"] = SCHEMA_V2
    check = validate_settings_document(migrated)
    if check["decision"] != "pass":
        raise ValueError("; ".join(check["errors"]))
    return migrated


def layer_merge(built_in: dict[str, Any], user: dict[str, Any], project: dict[str, Any], session: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, str]]:
    """Merge layers and record the highest layer that set each dotted routing/skills key."""
    from .settings import _merge

    sources: dict[str, str] = {}

    def _mark(prefix: str, payload: dict[str, Any], layer: str) -> None:
        for key, value in payload.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            sources[dotted] = layer
            if isinstance(value, dict):
                _mark(dotted, value, layer)

    merged = deepcopy(built_in)
    _mark("", built_in, "built-in")
    if user:
        merged = _merge(merged, user)
        _mark("", user, "user")
    if project:
        merged = _merge(merged, project)
        _mark("", project, "project")
    if session:
        merged = _merge(merged, session)
        _mark("", session, "cli/session")
    return merged, sources


def _clamp_effort(requested: str, ceiling: str) -> tuple[str, str | None]:
    if requested not in EFFORT_ORDER:
        requested = "medium"
    if ceiling not in EFFORT_ORDER:
        ceiling = "medium"
    if EFFORT_ORDER.index(requested) <= EFFORT_ORDER.index(ceiling):
        return requested, None
    return ceiling, f"requested {requested} exceeds {ceiling}"


def resolve_effort(
    *,
    role_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    routing: dict[str, Any] | None = None,
    requested: str | None = None,
    supported: list[str] | tuple[str, ...] | None = None,
    role_contract_default: str | None = None,
) -> dict[str, Any]:
    """role > exact-model > provider > global default > immutable role-contract default."""
    routing = normalize_routing(routing)
    source = "immutable-role-contract"
    configured = role_contract_default or routing["effort"]["default"]
    if routing["effort"]["default"]:
        configured = routing["effort"]["default"]
        source = "global-default"
    if provider and routing["effort"]["by_provider"].get(provider):
        configured = routing["effort"]["by_provider"][provider]
        source = "provider-override"
    if model and routing["effort"]["by_model"].get(model):
        configured = routing["effort"]["by_model"][model]
        source = "exact-model-override"
    if role_id and routing["effort"]["by_role"].get(role_id):
        configured = routing["effort"]["by_role"][role_id]
        source = "role-override"
    binding = routing["role_bindings"].get(role_id or "")
    if isinstance(binding, dict) and binding.get("effort"):
        configured = binding["effort"]
        source = "role-override"
    if requested:
        configured = requested
        source = "requested"
    entitlement = current_entitlements()
    ceiling = entitlement.max_effort
    minimum = binding.get("minimum_effort") if isinstance(binding, dict) else None
    errors = []
    if configured not in EFFORT_ORDER or ceiling not in EFFORT_ORDER or (minimum is not None and minimum not in EFFORT_ORDER):
        errors.append("invalid-effort-policy")
    allowed = list(EFFORT_ORDER)
    if supported is not None:
        if not isinstance(supported, (list, tuple)) or any(item not in EFFORT_ORDER for item in supported):
            errors.append("invalid-provider-effort-capabilities")
            allowed = []
        else:
            allowed = [item for item in allowed if item in supported]
    if not errors:
        allowed = [item for item in allowed if EFFORT_ORDER.index(item) <= EFFORT_ORDER.index(ceiling)]
        if minimum is not None:
            allowed = [item for item in allowed if EFFORT_ORDER.index(item) >= EFFORT_ORDER.index(minimum)]
    if errors or not allowed:
        return {"configured_value": configured, "effective_value": None, "source_layer": source,
                "clamp_reason": "No effort satisfies the combined policy.", "entitlement_limit": ceiling,
                "policy_limit": list(allowed), "requested_effort": requested or configured,
                "decision": "block", "block_reason": errors[0] if errors else ("minimum-effort-unsatisfied" if minimum else "effort-policy-intersection-empty")}
    lower = [item for item in allowed if EFFORT_ORDER.index(item) <= EFFORT_ORDER.index(configured)]
    effective = lower[-1] if lower else allowed[0]
    return {"configured_value": configured, "effective_value": effective, "source_layer": source,
            "clamp_reason": None if configured == effective else (f"requested effort {configured} exceeds {ceiling}" if EFFORT_ORDER.index(configured) > EFFORT_ORDER.index(ceiling) else "Provider/entitlement/role intersection adjusted effort."),
            "entitlement_limit": ceiling, "policy_limit": list(allowed),
            "requested_effort": requested or configured, "decision": "pass", "block_reason": None}


def describe_field(configured: Any, effective: Any, source_layer: str, clamp_reason: str | None = None, entitlement_limit: Any = None, policy_limit: Any = None) -> dict[str, Any]:
    return {
        "configured_value": configured,
        "effective_value": effective,
        "source_layer": source_layer,
        "clamp_reason": clamp_reason,
        "entitlement_limit": entitlement_limit,
        "policy_limit": policy_limit,
    }


def compute_effective(document: dict[str, Any], sources: dict[str, str] | None = None) -> dict[str, Any]:
    routing = normalize_routing(document.get("routing"))
    skills = normalize_skills(document.get("skills"))
    entitlement = current_entitlements()
    sources = sources or {}
    max_models_configured = routing["max_distinct_models"]
    max_models_effective = max_models_configured
    fields = {
        "routing.active_preset": describe_field(routing["active_preset"], routing["active_preset"], sources.get("routing.active_preset", "built-in")),
        "routing.provider_order": describe_field(routing["provider_order"], routing["provider_order"], sources.get("routing.provider_order", "built-in")),
        "routing.max_distinct_models": describe_field(max_models_configured, max_models_effective, sources.get("routing.max_distinct_models", "built-in")),
        "routing.max_distinct_providers": describe_field(routing["max_distinct_providers"], routing["max_distinct_providers"], sources.get("routing.max_distinct_providers", "built-in")),
        "routing.max_providers": describe_field(entitlement.max_providers, entitlement.max_providers, "entitlement", None, entitlement.max_providers),
        "routing.max_candidates_per_role": describe_field(routing["max_candidates_per_role"], routing["max_candidates_per_role"], sources.get("routing.max_candidates_per_role", "built-in")),
        "routing.require_provider_diversity": describe_field(routing["require_provider_diversity"], routing["require_provider_diversity"], sources.get("routing.require_provider_diversity", "built-in")),
        "routing.model_allowlist": describe_field(routing["model_allowlist"], routing["model_allowlist"], sources.get("routing.model_allowlist", "built-in")),
        "routing.model_denylist": describe_field(routing["model_denylist"], routing["model_denylist"], sources.get("routing.model_denylist", "built-in")),
        "routing.ollama.local_policy": describe_field(routing["ollama"]["local_policy"], routing["ollama"]["local_policy"], sources.get("routing.ollama.local_policy", "built-in")),
        "routing.ollama.cloud_policy": describe_field(routing["ollama"]["cloud_policy"], routing["ollama"]["cloud_policy"], sources.get("routing.ollama.cloud_policy", "built-in")),
        "skills.design_policy": describe_field(skills["design_policy"], skills["design_policy"], sources.get("skills.design_policy", "built-in")),
        "skills.max_selected": describe_field(skills["max_selected"], skills["max_selected"], sources.get("skills.max_selected", "built-in")),
    }
    default_effort = resolve_effort(routing=routing)
    fields["routing.effort.default"] = describe_field(
        default_effort["configured_value"],
        default_effort["effective_value"],
        default_effort["source_layer"],
        default_effort["clamp_reason"],
        default_effort["entitlement_limit"],
        default_effort["policy_limit"],
    )
    payload = {
        "schema": SCHEMA_V2,
        "routing": {**routing, "max_distinct_models": max_models_effective},
        "skills": skills,
        "api_profiles": normalize_api_profiles(document.get("api_profiles")),
        "edition": entitlement.edition,
        "max_providers": entitlement.max_providers,
        "fields": fields,
    }
    digest = sha256_json(
        {
            "routing": payload["routing"],
            "skills": payload["skills"],
            "api_profiles": payload["api_profiles"],
            "edition": payload["edition"],
        }
    )
    payload["effective_settings_digest"] = digest
    payload["computed_at"] = utc_now()
    return payload


def preset_names() -> list[str]:
    return list(PRESETS)


def preset_document(name: str) -> dict[str, Any]:
    if name not in PRESETS:
        raise KeyError(f"unknown preset: {name}; known: {', '.join(preset_names())}")
    return deepcopy(PRESETS[name])


def apply_preset_overlay(document: dict[str, Any], name: str) -> dict[str, Any]:
    from .settings import _merge

    overlay = preset_document(name)
    merged = _merge(document, overlay)
    merged["routing"] = normalize_routing(merged.get("routing"))
    merged["routing"]["active_preset"] = name
    merged["skills"] = normalize_skills(merged.get("skills"))
    return merged


def preset_diff(document: dict[str, Any], name: str) -> dict[str, Any]:
    current_doc = inject_v2(document)
    proposed = apply_preset_overlay(current_doc, name)
    before = {"routing": current_doc.get("routing"), "skills": current_doc.get("skills"), "cloud": current_doc.get("cloud"), "models": current_doc.get("models")}
    after = {"routing": proposed.get("routing"), "skills": proposed.get("skills"), "cloud": proposed.get("cloud"), "models": proposed.get("models")}
    return {
        "preset": name,
        "before": before,
        "after": after,
        "before_digest": sha256_json(before),
        "after_digest": sha256_json(after),
        "unrelated_keys_preserved": sorted(set(current_doc) - {"routing", "skills", "cloud", "models", "schema", "updated_at"}),
    }
