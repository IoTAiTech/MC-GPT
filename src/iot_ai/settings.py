# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05

from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Any
from .paths import settings_path
from .util import atomic_json, load_json, utc_now

DEFAULTS: dict[str, Any] = {
    "schema": "iot-ai.settings.v1",
    "edition": "community",
    "cloud": {"enabled": False, "privacy_mode": "strict", "allow_private_network_data": False},
    "providers": {p: {"enabled": True} for p in ("claude", "codex", "gemini", "grok", "ollama")},
    "models": {"all_enabled": True, "disabled": [], "local_enabled": False, "cloud_preferred": True},
    "meeting": {"default_quorum": 3, "max_revision_rounds": 2, "max_seats_community": 3},
    "multi_coder": {"max_repair_rounds": 2, "max_effort_community": "medium"},
    "telemetry": {"enabled": True, "store_raw_prompts": False, "store_raw_outputs": False, "retention_days": 30},
    "dashboard": {"planned": True, "enabled": False},
    "agent_runtime": {
        "goal_first": True,
        "own_prompt": True,
        "own_context": True,
        "own_tools": True,
        "own_control_flow": True,
        "context_token_budget": 64000,
        "output_reserve_ratio": 0.2,
        "checkpoint_enabled": True,
        "max_identical_failures": 2,
        "max_no_new_finding_rounds": 2,
        "clarify_only_when_blocked": True,
    },
    "orchestration": {
        "active_profile": "balanced",
        "profiles": {
            "economy": {"max_parallel": 3, "token_budget": 100000, "wall_clock_seconds": 1800, "require_live": True},
            "balanced": {"max_parallel": 6, "token_budget": 250000, "wall_clock_seconds": 3600, "require_live": True},
            "ultracode": {"max_parallel": 8, "token_budget": 500000, "wall_clock_seconds": 7200, "require_live": True},
        },
    },
    "knowledge": {"reuse_threshold": 0.85, "public_root_enabled": True, "private_root_enabled": True},
    "diagnostics": {"auto_collect": True, "privacy_mode": "strict", "include_stdout_stderr": True},
    "storage": {"control_backend": "sqlite", "knowledge_backend": "versioned-files", "projection_backend": "xlsx", "rag_backend": "adapter"},
    "platform": {"project_root": None, "product_roots": {}, "server_inventory": {}},
    "ollama": {"first_class": True, "cloud_preferred": True, "local_enabled": False, "minimum_cloud_roles_when_available": 1},
    "agent_contracts": {"immutable": True, "required_role_acceptance": True, "same_plan_digest": True},
    "superpowers_profile": {
        "systematic_debugging": True,
        "test_driven_development": True,
        "receiving_code_review": True,
        "executing_plans": True,
        "dispatching_parallel_agents": True,
        "verification_before_completion": True,
        "using_superpowers": True,
    },
    "compliance": {
        "legal_baseline": "EU-2024-1689+EU-2026-1744",
        "global_compliance_claim_allowed": False,
        "article_5_enforced": True,
        "article_50": {
            "first_interaction_disclosure": True,
            "languages": ["en", "de", "fa"],
            "machine_readable_marking": True,
            "visible_label_for_public_interest": True,
        },
        "ai_literacy_receipts_required": True,
        "high_risk_default": "blocked-until-classified",
        "upstream_model_dossier_required": True,
        "post_market_monitoring_configured": True,
        "incident_process_configured": True,
    },
}

FORBIDDEN_KEY_WORDS = ("password", "secret", "api_key", "token", "private_key", "credential")


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict): out[k] = _merge(out[k], v)
        else: out[k] = v
    return out


def load(user_home: Path) -> dict[str, Any]:
    return _merge(DEFAULTS, load_json(settings_path(user_home), {}) or {})


def save(user_home: Path, value: dict[str, Any]) -> None:
    value = deepcopy(value); value["updated_at"] = utc_now(); atomic_json(settings_path(user_home), value)


def get_value(value: dict[str, Any], dotted: str) -> Any:
    node: Any = value
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node: raise KeyError(dotted)
        node = node[part]
    return node


def parse_scalar(raw: str) -> Any:
    s=raw.strip(); low=s.lower()
    if low in {"true","on","yes","enabled"}: return True
    if low in {"false","off","no","disabled"}: return False
    if low == "null": return None
    try: return int(s)
    except ValueError: return s


def set_value(value: dict[str, Any], dotted: str, raw: str) -> dict[str, Any]:
    if any(word in dotted.lower() for word in FORBIDDEN_KEY_WORDS):
        raise ValueError("secret values are forbidden in settings; use an environment-variable reference")
    node=value
    parts=dotted.split(".")
    for part in parts[:-1]:
        node=node.setdefault(part,{})
        if not isinstance(node,dict): raise ValueError(f"not a settings group: {part}")
    node[parts[-1]]=parse_scalar(raw)
    return value


def toggle_group(value: dict[str, Any], group: str, enabled: bool) -> dict[str, Any]:
    if group == "all-cloud": value["cloud"]["enabled"] = enabled
    elif group == "all-models": value["models"]["all_enabled"] = enabled
    elif group in value.get("providers", {}): value["providers"][group]["enabled"] = enabled
    else: raise ValueError(f"unknown settings group: {group}")
    return value
