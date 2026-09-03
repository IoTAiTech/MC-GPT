# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08

from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Any
from .paths import project_settings_path, settings_backup_root, settings_path
from .util import atomic_json, load_json, utc_now

DEFAULTS: dict[str, Any] = {
    "schema": "iot-ai.settings.v1",
    "edition": "community",
    "cloud": {"enabled": False, "privacy_mode": "strict", "allow_private_network_data": False},
    "providers": {p: {"enabled": True} for p in ("claude", "codex", "gemini", "grok", "ollama")},
    "models": {"all_enabled": True, "disabled": [], "local_enabled": False, "cloud_preferred": True},
    "meeting": {
        "default_quorum": 3,
        "max_revision_rounds": 2,
        "max_seats_community": 16,
        "seat_selector": "all-coders+ollama-clouds",
        "require_ollama_cloud_when_available": True,
        "automatic_on_failure": True,
        "automatic_on_disagreement": True,
        "automatic_final_hard_judge": True,
    },
    "multi_coder": {
        "max_repair_rounds": 3,
        "max_effort_community": "medium",
        "mandatory_at_material_gates": True,
        "all_eligible_provider_families": True,
        "minimum_independent_substantive_seats_r2_plus": 2,
        "single_engine_never_counts_as_multi_coder": True,
    },
    "telemetry": {"enabled": True, "store_raw_prompts": False, "store_raw_outputs": False, "retention_days": 30},
    "autopilot": {
        "natural_language_primary": True,
        "until_terminal_default": True,
        "meeting_policy": "automatic",
        "multi_coder_policy": "mandatory-at-gates",
        "max_iterations_per_task": 6,
        "max_identical_failures": 2,
        "max_no_new_evidence_rounds": 2,
        "wall_clock_budget_seconds": 7200,
        "token_budget": 500000,
        "wip_limits": {"critical": 4, "high": 2, "medium": 1, "normal": 1, "low": 1},
        "terminal_states": [
            "COMPLETE",
            "TECHNICAL_COMPLETE_AWAITING_FOUNDER",
            "EXTERNALLY_BLOCKED",
            "AUTHORITY_BLOCKED",
            "SAFETY_BLOCKED",
            "BUDGET_EXHAUSTED",
            "FAILED_TERMINAL",
            "CANCELLED"
        ],
        "final_report_formats": ["json", "markdown", "csv", "xlsx"],
        "founder_final_acceptance_is_human_only": True,
    },
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
            "languages": ["en", "de"],
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


def load(
    user_home: Path,
    *,
    project_root: Path | None = None,
    session_override: dict[str, Any] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Load v1 or v2 settings. v2 fields are injected in memory; persistence is explicit."""
    from .settings_v2 import inject_v2, layer_merge

    user = load_json(settings_path(user_home), {}) or {}
    project: dict[str, Any] = {}
    if project_root is not None:
        project = load_json(project_settings_path(project_root), {}) or {}
    merged, _sources = layer_merge(DEFAULTS, user, project, session_override)
    normalized = inject_v2(merged)
    if persist:
        raise ValueError("load() must not persist; use migrate_v1_to_v2 or save after an explicit apply")
    return normalized


def save(user_home: Path, value: dict[str, Any]) -> None:
    from .settings_v2 import assert_no_secrets, validate_settings_document

    value = deepcopy(value)
    assert_no_secrets(value)
    check = validate_settings_document(value)
    if check["decision"] != "pass":
        raise ValueError("; ".join(check["errors"]))
    value["updated_at"] = utc_now()
    atomic_json(settings_path(user_home), value)


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
    if s[:1] in {"{", "["}:
        import json
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
    if "," in s and not s.startswith("http"):
        parts = [part.strip() for part in s.split(",") if part.strip()]
        if len(parts) > 1:
            return parts
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
    else:
        known = ["all-cloud", "all-models", *sorted(value.get("providers", {}))]
        raise ValueError(f"unknown settings group: {group}; known: {', '.join(known)}")
    return value


def effective_settings(user_home: Path, value: dict[str, Any] | None = None, *, project_root: Path | None = None) -> dict[str, Any]:
    from .settings_v2 import compute_effective, inject_v2, layer_merge

    if value is None:
        user = load_json(settings_path(user_home), {}) or {}
        project = load_json(project_settings_path(project_root), {}) or {} if project_root else {}
        merged, sources = layer_merge(DEFAULTS, user, project, None)
        return compute_effective(merged, sources)
    return compute_effective(inject_v2(value))


def validate_settings(user_home: Path, value: dict[str, Any] | None = None) -> dict[str, Any]:
    from .settings_v2 import validate_settings_document

    document = value if value is not None else load(user_home)
    return validate_settings_document(document)


def migrate_v1_to_v2(user_home: Path, *, apply: bool = False) -> dict[str, Any]:
    from .settings_v2 import SCHEMA_V2, migrate_document, sha256_json

    path = settings_path(user_home)
    current = load_json(path, {}) or {}
    source_digest = sha256_json(current)
    migrated = migrate_document(_merge(DEFAULTS, current))
    dest_digest = sha256_json(migrated)
    receipt = {
        "decision": "plan" if not apply else "pass",
        "action": "migrate-v1-to-v2",
        "source_schema": current.get("schema") or "iot-ai.settings.v1",
        "destination_schema": SCHEMA_V2,
        "source_sha256": source_digest,
        "destination_sha256": dest_digest,
        "backup_path": None,
        "rollback_id": None,
    }
    if not apply:
        return receipt
    backup_dir = settings_backup_root(user_home)
    backup_dir.mkdir(parents=True, exist_ok=True)
    rollback_id = f"settings-v2-{utc_now().replace(':', '').replace('-', '')}"
    backup_path = backup_dir / f"{rollback_id}.json"
    atomic_json(backup_path, current or {"schema": "iot-ai.settings.v1"})
    save(user_home, migrated)
    receipt.update({"decision": "pass", "backup_path": str(backup_path), "rollback_id": rollback_id, "apply": True})
    atomic_json(backup_dir / f"{rollback_id}.receipt.json", receipt)
    return receipt


def rollback_settings(user_home: Path, rollback_id: str, *, apply: bool = False) -> dict[str, Any]:
    backup_dir = settings_backup_root(user_home)
    backup_path = backup_dir / f"{rollback_id}.json"
    if not backup_path.is_file():
        raise FileNotFoundError(f"unknown rollback receipt: {rollback_id}")
    previous = load_json(backup_path, {}) or {}
    receipt = {"decision": "plan" if not apply else "pass", "action": "rollback", "rollback_id": rollback_id, "backup_path": str(backup_path)}
    if not apply:
        return receipt
    save(user_home, previous)
    receipt["decision"] = "pass"
    return receipt


def apply_preset(user_home: Path, name: str, *, apply: bool = False) -> dict[str, Any]:
    from .settings_v2 import apply_preset_overlay, preset_diff, validate_settings_document

    current = load(user_home)
    diff = preset_diff(current, name)
    proposed = apply_preset_overlay(current, name)
    check = validate_settings_document(proposed)
    result = {"decision": "plan" if not apply else "pass", "preset": name, "diff": diff, "validation": check}
    if check["decision"] != "pass":
        result["decision"] = "block"
        return result
    if not apply:
        return result
    migrate = migrate_v1_to_v2(user_home, apply=True)
    save(user_home, proposed)
    result.update({"decision": "pass", "rollback_id": migrate.get("rollback_id"), "backup_path": migrate.get("backup_path")})
    return result


def set_role_binding(value: dict[str, Any], role_id: str, **fields: Any) -> dict[str, Any]:
    from .settings_v2 import normalize_role_binding

    routing = value.setdefault("routing", {})
    bindings = routing.setdefault("role_bindings", {})
    current = dict(bindings.get(role_id) or {})
    current.update({key: item for key, item in fields.items() if item is not None})
    bindings[role_id] = normalize_role_binding(current, role_id)
    return value
