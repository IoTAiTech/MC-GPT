# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Role-aware, evidence-driven provider/model selection with Ollama first-class."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .readiness import provider_candidates
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

EFFORT_ORDER = ("low", "medium", "high", "xhigh")


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


def _score(candidate: dict[str, Any], role_id: str, history: dict[tuple[str, str | None], dict[str, Any]]) -> float:
    provider = str(candidate.get("provider"))
    preferences = ROLE_PREFERENCES.get(role_id, tuple())
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
        score += 20
    return score


def rank_candidates(
    user_home: Path,
    role_ids: list[str],
    *,
    require_live: bool = True,
    cloud_only: bool = False,
    max_candidates_per_role: int = 4,
) -> dict[str, list[dict[str, Any]]]:
    """Return explicit same-role candidate ladders; no fallback is implicit."""
    candidates = provider_candidates(user_home, require_live=require_live, cloud_only=cloud_only)
    history = _historical_map(user_home)
    ranked_by_role: dict[str, list[dict[str, Any]]] = {}
    for role_id in role_ids:
        ranked = sorted(
            candidates,
            key=lambda candidate: (
                -_score(candidate, role_id, history),
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
            distinct.append({**candidate, "selection_score": round(_score(candidate, role_id, history), 3)})
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
) -> dict[str, dict[str, Any]]:
    """Assign candidates to roles with diversity and an explicit fallback ladder."""
    ladders = rank_candidates(user_home, role_ids, require_live=require_live, cloud_only=cloud_only)
    selected: dict[str, dict[str, Any]] = {}
    used_candidates: set[str] = set()
    used_providers: set[str] = set()

    for role_id in role_ids:
        options = ladders.get(role_id, [])
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for candidate in options:
            candidate_id = str(candidate.get("candidate_id"))
            if not allow_reuse and candidate_id in used_candidates:
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
            best_ollama = max(ollama_options, key=lambda candidate: _score(candidate, role_id, history))
            current_score = _score(selected[role_id], role_id, history)
            ollama_score = _score(best_ollama, role_id, history)
            replacement_options.append((current_score - ollama_score, role_id, best_ollama))
        if replacement_options:
            _, role_id, ollama = min(replacement_options, key=lambda item: (item[0], item[1]))
            old = selected[role_id]
            selected[role_id] = {
                **ollama,
                "selection_score": round(_score(ollama, role_id, history), 3),
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
                    selected.pop(role_id, None)
                    continue
                selected[role_id] = {**replacement, "selection_reason": "community-provider-cap"}
            selected[role_id]["fallback_candidates"] = [
                candidate
                for candidate in selected[role_id].get("fallback_candidates", [])
                if candidate.get("provider") in allowed_set
            ]
    return selected
