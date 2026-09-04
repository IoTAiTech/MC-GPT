# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Role-aware, evidence-driven provider/model selection with Ollama first-class."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .readiness import provider_candidates
from .settings import load as load_settings
from .settings_v2 import normalize_routing, resolve_effort
from .telemetry import summary

ROLE_PREFERENCES: dict[str, tuple[str, ...]] = {
    "requirements-analyst": ("claude", "gemini", "ollama", "codex", "grok"),
    "domain-architect": ("claude", "codex", "ollama", "grok", "gemini"),
    "security-challenger": ("grok", "codex", "ollama", "claude", "gemini"),
    "operator-ux-reviewer": ("claude", "gemini", "ollama", "grok", "codex"),
    "performance-engineer": ("gemini", "ollama", "codex", "grok", "claude"),
    "implementation-engineer": ("codex", "grok", "claude", "ollama", "gemini"),
    "quality-verifier": ("codex", "grok", "gemini", "ollama", "claude"),
    "plan-synthesizer": ("claude", "codex", "grok", "ollama", "gemini"),
    "independent-judge": ("grok", "codex", "ollama", "claude", "gemini"),
}

EFFORT_ORDER = ("none", "low", "medium", "high", "xhigh", "max")


class CandidateSelection(dict):
    """Role-to-candidate map plus typed selection errors. Extra keys stay off .values()."""

    errors: list[dict[str, Any]]
    decision: str

    def __init__(self, mapping: dict[str, Any] | None = None) -> None:
        super().__init__(mapping or {})
        self.errors = []
        self.decision = "pass"


def clamp_effort(requested: str, supported: list[str] | tuple[str, ...] | None) -> tuple[str, str | None]:
    """Clamp requested effort to an explicitly supported level."""
    if requested not in EFFORT_ORDER:
        requested = "medium"
    values = [value for value in (supported or EFFORT_ORDER) if value in EFFORT_ORDER]
    if requested in values:
        return requested, None
    requested_index = EFFORT_ORDER.index(requested)
    lower = [value for value in values if EFFORT_ORDER.index(value) <= requested_index]
    effective = (
        max(lower, key=EFFORT_ORDER.index)
        if lower
        else min(values, key=EFFORT_ORDER.index)
        if values
        else "medium"
    )
    return effective, f"requested {requested} is unsupported; clamped to {effective}"


def _historical_map(user_home: Path) -> dict[tuple[str, str | None], dict[str, Any]]:
    return {(row.get("provider"), row.get("model_served")): row for row in summary(user_home, "30d")}


def _ollama_plane(candidate: dict[str, Any]) -> str:
    if str(candidate.get("provider")) != "ollama":
        return "other"
    return "cloud" if candidate.get("cloud") else "local"


def _policy_allows(policy: str, plane: str, candidate_plane: str) -> bool:
    if plane != candidate_plane:
        return True
    if policy == "never":
        return False
    if policy == "only":
        return candidate_plane == plane
    return True


def _candidate_allowed(candidate: dict[str, Any], routing: dict[str, Any]) -> bool:
    provider = str(candidate.get("provider"))
    model = str(candidate.get("model") or "")
    allow = routing.get("model_allowlist") or []
    deny = routing.get("model_denylist") or []
    if deny and model in deny:
        return False
    if allow and model not in allow and model not in {"auto", "auto:cloud", ""}:
        return False
    local_policy = routing.get("ollama", {}).get("local_policy", "never")
    cloud_policy = routing.get("ollama", {}).get("cloud_policy", "prefer")
    if local_policy == "only" and not (provider == "ollama" and not candidate.get("cloud")):
        return False
    if cloud_policy == "only" and not (provider == "ollama" and candidate.get("cloud")):
        return False
    if provider == "ollama" and candidate.get("cloud") and cloud_policy == "never":
        return False
    if provider == "ollama" and not candidate.get("cloud") and local_policy == "never":
        return False
    return True


def _role_preferences(role_id: str, routing: dict[str, Any]) -> tuple[str, ...]:
    binding = (routing.get("role_bindings") or {}).get(role_id) or {}
    preferred = tuple(binding.get("preferred_providers") or ())
    fallback = tuple(binding.get("fallback_sequence") or ())
    order = tuple(routing.get("provider_order") or ())
    if preferred or fallback:
        return tuple(dict.fromkeys((*preferred, *fallback, *order, *ROLE_PREFERENCES.get(role_id, ()))))
    if order:
        return tuple(dict.fromkeys((*order, *ROLE_PREFERENCES.get(role_id, ()))))
    return ROLE_PREFERENCES.get(role_id, tuple())


def _score(candidate: dict[str, Any], role_id: str, history: dict[tuple[str, str | None], dict[str, Any]], routing: dict[str, Any] | None = None) -> float:
    routing = routing or {}
    provider = str(candidate.get("provider"))
    preferences = _role_preferences(role_id, routing)
    preference = len(preferences) - preferences.index(provider) if provider in preferences else 0
    historical = history.get((provider, candidate.get("model"))) or history.get((provider, None)) or {}
    quality = float(historical.get("avg_quality") or 0)
    latency = float(historical.get("avg_latency_ms") or 0)
    success_rate = float(historical.get("success_rate") or 0)
    score = (
        (120 if candidate.get("live_ready") else 0)
        + preference * 10
        + quality
        + success_rate * 20
        - min(latency / 10_000.0, 20)
        - float(candidate.get("priority") or 100) / 20.0
    )
    if provider == "ollama" and candidate.get("cloud") and candidate.get("model") not in {"auto", "auto:cloud", None}:
        score += 20 if str((routing.get("ollama") or {}).get("cloud_policy") or "prefer") in {"prefer", "required", "only"} else 0
    if provider == "ollama" and not candidate.get("cloud") and str((routing.get("ollama") or {}).get("local_policy") or "never") in {"prefer", "required", "only"}:
        score += 24
    binding = (routing.get("role_bindings") or {}).get(role_id) or {}
    if provider in set(binding.get("denied_providers") or ()):
        score -= 1000
    if str(candidate.get("model") or "") in set(binding.get("preferred_models") or ()):
        score += 30
    return score


def rank_candidates(
    user_home: Path,
    role_ids: list[str],
    *,
    require_live: bool = True,
    cloud_only: bool = False,
    max_candidates_per_role: int = 4,
    settings: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return explicit same-role candidate ladders; no fallback is implicit."""
    routing = normalize_routing((settings if settings is not None else load_settings(user_home)).get("routing"))
    max_candidates_per_role = int(routing.get("max_candidates_per_role") or max_candidates_per_role)
    candidates = [
        candidate
        for candidate in provider_candidates(user_home, require_live=require_live, cloud_only=cloud_only)
        if _candidate_allowed(candidate, routing)
    ]
    history = _historical_map(user_home)
    ranked_by_role: dict[str, list[dict[str, Any]]] = {}
    for role_id in role_ids:
        binding = (routing.get("role_bindings") or {}).get(role_id) or {}
        permitted_providers = set(binding.get("permitted_providers") or ())
        denied_providers = set(binding.get("denied_providers") or ())
        permitted_models = set(binding.get("permitted_models") or ())
        role_candidates = []
        for candidate in candidates:
            provider = str(candidate.get("provider"))
            model = str(candidate.get("model") or "")
            if denied_providers and provider in denied_providers:
                continue
            if permitted_providers and provider not in permitted_providers:
                continue
            if permitted_models and model not in permitted_models and model not in {"auto", "auto:cloud", ""}:
                continue
            role_candidates.append(candidate)
        ranked = sorted(
            role_candidates,
            key=lambda candidate: (
                -_score(candidate, role_id, history, routing),
                str(candidate.get("provider")),
                str(candidate.get("model")),
                str(candidate.get("route_id")),
            ),
        )
        distinct: list[dict[str, Any]] = []
        seen_candidates: set[str] = set()
        for candidate in ranked:
            candidate_id = str(candidate.get("candidate_id"))
            if candidate_id in seen_candidates:
                continue
            seen_candidates.add(candidate_id)
            distinct.append({**candidate, "selection_score": round(_score(candidate, role_id, history, routing), 3)})
            if len(distinct) >= max(1, max_candidates_per_role):
                break
        ranked_by_role[role_id] = distinct
    return ranked_by_role


def select_candidates(
    user_home: Path,
    role_ids: list[str],
    *,
    require_live: bool = True,
    cloud_only: bool = False,
    allow_reuse: bool = True,
    require_ollama_when_available: bool = True,
    max_providers: int | None = None,
    required_provider_families: list[str] | tuple[str, ...] | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Assign candidates to roles with diversity and an explicit fallback ladder."""
    document = settings if settings is not None else load_settings(user_home)
    routing = normalize_routing(document.get("routing"))
    selection_errors: list[dict[str, Any]] = []
    from .provider_catalog import apply_catalog_to_candidate

    ladders = rank_candidates(
        user_home,
        role_ids,
        require_live=require_live,
        cloud_only=cloud_only,
        settings=document,
    )
    selected: dict[str, dict[str, Any]] = {}
    used_candidates: set[str] = set()
    used_providers: set[str] = set()
    if str(routing.get("ollama", {}).get("cloud_policy")) == "never":
        require_ollama_when_available = False
    elif str(routing.get("ollama", {}).get("cloud_policy")) in {"prefer", "required"}:
        require_ollama_when_available = True

    for role_id in role_ids:
        binding = (routing.get("role_bindings") or {}).get(role_id) or {}
        role_allow_reuse = allow_reuse if binding.get("allow_reuse", True) else False
        options = [apply_catalog_to_candidate(row) for row in ladders.get(role_id, [])]
        options = [row for row in options if not row.get("catalog_block")]
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for candidate in options:
            candidate_id = str(candidate.get("candidate_id"))
            if not role_allow_reuse and candidate_id in used_candidates:
                continue
            score = float(candidate.get("selection_score") or 0)
            if str(candidate.get("provider")) not in used_providers:
                score += 18
            if candidate_id in used_candidates:
                score -= 25
            scored.append((score, candidate_id, candidate))
        if not scored:
            continue
        _, candidate_id, best = max(scored, key=lambda item: (item[0], item[1]))
        alternates = [candidate for candidate in options if candidate.get("candidate_id") != candidate_id]
        selected[role_id] = {**best, "fallback_candidates": alternates}
        used_candidates.add(candidate_id)
        used_providers.add(str(best.get("provider")))

    ollama_options = [
        candidate
        for options in ladders.values()
        for candidate in options
        if candidate.get("provider") == "ollama"
        and candidate.get("cloud")
        and candidate.get("model") not in {"auto", "auto:cloud", None}
    ]
    if (
        require_ollama_when_available
        and len(role_ids) >= 3
        and ollama_options
        and not any(candidate.get("provider") == "ollama" for candidate in selected.values())
    ):
        replacement_options: list[tuple[float, str, dict[str, Any]]] = []
        history = _historical_map(user_home)
        for role_id in role_ids:
            if role_id not in selected:
                continue
            best_ollama = max(ollama_options, key=lambda candidate: _score(candidate, role_id, history, routing))
            current_score = _score(selected[role_id], role_id, history, routing)
            ollama_score = _score(best_ollama, role_id, history, routing)
            replacement_options.append((current_score - ollama_score, role_id, best_ollama))
        if replacement_options:
            _, role_id, ollama = min(replacement_options, key=lambda item: (item[0], item[1]))
            old = selected[role_id]
            selected[role_id] = {
                **ollama,
                "selection_score": round(_score(ollama, role_id, history, routing), 3),
                "selection_reason": "first-class-ollama-diversity",
                "fallback_candidates": [old, *[c for c in ladders.get(role_id, []) if c.get("candidate_id") not in {old.get("candidate_id"), ollama.get("candidate_id")}]],
            }

    required_families = tuple(dict.fromkeys(str(value).strip().lower() for value in (required_provider_families or ()) if str(value).strip()))
    if required_families:
        if max_providers is not None and max_providers > 0 and len(required_families) > max_providers:
            raise PermissionError(
                f"required provider-family count {len(required_families)} exceeds edition limit {max_providers}"
            )
        for required_provider in required_families:
            if any(str(candidate.get("provider")) == required_provider for candidate in selected.values()):
                continue
            replacement_options: list[tuple[float, str, dict[str, Any]]] = []
            provider_counts: dict[str, int] = {}
            for candidate in selected.values():
                provider = str(candidate.get("provider"))
                provider_counts[provider] = provider_counts.get(provider, 0) + 1
            for role_id in role_ids:
                current = selected.get(role_id)
                if not current:
                    continue
                current_provider = str(current.get("provider"))
                if current_provider in required_families and provider_counts.get(current_provider, 0) <= 1:
                    continue
                candidate = next(
                    (row for row in ladders.get(role_id, []) if str(row.get("provider")) == required_provider),
                    None,
                )
                if candidate is None:
                    continue
                loss = float(current.get("selection_score") or 0.0) - float(candidate.get("selection_score") or 0.0)
                replacement_options.append((loss, role_id, candidate))
            if replacement_options:
                _, role_id, replacement = min(replacement_options, key=lambda item: (item[0], item[1]))
                previous = selected[role_id]
                selected[role_id] = {
                    **replacement,
                    "selection_reason": "required-provider-family",
                    "fallback_candidates": [
                        previous,
                        *[
                            candidate
                            for candidate in ladders.get(role_id, [])
                            if candidate.get("candidate_id") not in {previous.get("candidate_id"), replacement.get("candidate_id")}
                        ],
                    ],
                }

    if max_providers is not None and max_providers > 0:
        provider_scores: dict[str, float] = {}
        for role_id, candidate in selected.items():
            provider = str(candidate.get("provider"))
            provider_scores[provider] = provider_scores.get(provider, 0.0) + float(candidate.get("selection_score") or 0.0)
        ollama_present = any(
            candidate.get("provider") == "ollama" and candidate.get("cloud")
            for options in ladders.values()
            for candidate in options
        )
        ranked_providers = sorted(provider_scores, key=lambda provider: (-provider_scores[provider], provider))
        allowed: list[str] = ranked_providers[:max_providers]
        if require_ollama_when_available and ollama_present and "ollama" not in allowed:
            if len(allowed) >= max_providers:
                allowed[-1] = "ollama"
            else:
                allowed.append("ollama")
        allowed_set = set(allowed)
        for role_id in list(selected):
            if selected[role_id].get("provider") not in allowed_set:
                replacement = next(
                    (candidate for candidate in ladders.get(role_id, []) if candidate.get("provider") in allowed_set),
                    None,
                )
                if replacement is None:
                    selection_errors.append({"code": "model-cap-conflict", "role_id": role_id})
                    selected.pop(role_id, None)
                    continue
                selected[role_id] = {**replacement, "selection_reason": "community-provider-cap"}
            selected[role_id]["fallback_candidates"] = [
                candidate
                for candidate in selected[role_id].get("fallback_candidates", [])
                if candidate.get("provider") in allowed_set
            ]

    local_policy = str(routing.get("ollama", {}).get("local_policy") or "never")
    if local_policy in {"required", "only"}:
        local_options = [
            candidate
            for options in ladders.values()
            for candidate in options
            if candidate.get("provider") == "ollama" and not candidate.get("cloud")
        ]
        if local_policy == "only":
            for role_id in list(selected):
                if not (selected[role_id].get("provider") == "ollama" and not selected[role_id].get("cloud")):
                    replacement = next(
                        (candidate for candidate in ladders.get(role_id, []) if candidate.get("provider") == "ollama" and not candidate.get("cloud")),
                        None,
                    )
                    if replacement is None:
                        selection_errors.append({"code": "required-provider-family-unavailable", "role_id": role_id, "family": "ollama"})
                        selected.pop(role_id, None)
                    else:
                        selected[role_id] = {**replacement, "selection_reason": "ollama-local-only"}
        elif local_policy == "required":
            if not local_options:
                for role_id in list(selected):
                    selection_errors.append({"code": "required-provider-family-unavailable", "role_id": role_id, "family": "ollama"})
                    selected.pop(role_id, None)
            elif not any(row.get("provider") == "ollama" and not row.get("cloud") for row in selected.values()):
                role_id = next(iter(selected), None)
                if role_id:
                    selected[role_id] = {**local_options[0], "selection_reason": "ollama-local-required", "fallback_candidates": [selected[role_id]]}

    max_models = int(routing.get("max_distinct_models") or 16)
    used_models: list[str] = []
    for role_id in list(selected):
        model_key = f"{selected[role_id].get('provider')}:{selected[role_id].get('model')}"
        if model_key not in used_models and len(used_models) >= max_models:
            replacement = next(
                (
                    candidate
                    for candidate in ladders.get(role_id, [])
                    if f"{candidate.get('provider')}:{candidate.get('model')}" in used_models
                ),
                None,
            )
            if replacement is None:
                selection_errors.append({"code": "model-cap-conflict", "role_id": role_id})
                selected.pop(role_id, None)
                continue
            selected[role_id] = {**replacement, "selection_reason": "max-distinct-models"}
            model_key = f"{replacement.get('provider')}:{replacement.get('model')}"
        if model_key not in used_models:
            used_models.append(model_key)

    for role_id, candidate in selected.items():
        effort = resolve_effort(
            role_id=role_id,
            provider=str(candidate.get("provider") or ""),
            model=str(candidate.get("model") or ""),
            routing=routing,
            requested=candidate.get("requested_effort"),
        )
        candidate["requested_effort"] = effort["requested_effort"]
        candidate["effective_effort"] = effort["effective_value"]
        candidate["effort_clamp_reason"] = effort["clamp_reason"]
        candidate["effort_source"] = effort["source_layer"]
        candidate["effort_decision"] = effort.get("decision") or "pass"
        candidate["effort_block_reason"] = effort.get("block_reason")
    for role_id in role_ids:
        if role_id not in selected:
            selection_errors.append({"code": "required-role-unsatisfied", "role_id": role_id})
    if routing.get("require_provider_diversity") and len([role for role in role_ids if role in selected]) >= 2:
        from .provider_catalog import normalize_provider

        families = {normalize_provider(str(row.get("provider") or "")) for row in selected.values()}
        families.discard("")
        if len(families) < 2:
            selection_errors.append({"code": "provider-diversity-unsatisfied", "families": sorted(families)})
    result = CandidateSelection(selected)
    result.errors = selection_errors
    result.decision = "pass" if not selection_errors else "block"
    return result
