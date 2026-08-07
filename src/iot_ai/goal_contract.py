# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Goal-first contracts for autonomous, bounded IOT-AI execution.

A goal contract captures the outcome, context, constraints and proof expected by
an operator.  It deliberately avoids turning user prose into a brittle list of
micro-steps; the execution graph remains free to choose the safest efficient
path while preserving every explicit constraint.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .util import utc_now

_SCHEMA = "iot-ai.goal-contract.v1"
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|[\r\n]+")
_CONSTRAINT_MARKERS = (
    "must",
    "must not",
    "do not",
    "don't",
    "never",
    "only",
    "without",
    "preserve",
    "keep",
    "avoid",
    "forbid",
    "cannot",
    "can't",
    "نباید",
    "باید",
    "فقط",
    "بدون",
)
_SUCCESS_MARKERS = (
    "done when",
    "success",
    "acceptance",
    "until",
    "target",
    "pass",
    "complete",
    "finish",
    "at least",
    "accuracy",
    "latency",
    "throughput",
    "وقتی تمام",
    "تا زمانی",
    "هدف",
    "پاس",
)
_WHY_MARKERS = ("because", "so that", "in order to", "why", "زیرا", "چون", "برای اینکه")
_PRIORITY_MARKERS = ("priority", "first", "critical", "p0", "اولویت", "ابتدا", "بحرانی")


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _clean(value)
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return tuple(result)


def _sentences(goal: str) -> tuple[str, ...]:
    parts = (_clean(part) for part in _SENTENCE_SPLIT.split(goal))
    return _unique(part for part in parts if part)


def _matches(value: str, markers: tuple[str, ...]) -> bool:
    low = value.casefold()
    return any(marker in low for marker in markers)


@dataclass(frozen=True, slots=True)
class GoalContract:
    """Immutable outcome contract consumed by the graph compiler and agents."""

    contract_id: str
    raw_goal: str
    outcome: str
    why: str
    context: tuple[str, ...]
    constraints: tuple[str, ...]
    non_goals: tuple[str, ...]
    priorities: tuple[str, ...]
    success_criteria: tuple[str, ...]
    verification: tuple[str, ...]
    stop_rules: tuple[str, ...]
    clarification_policy: str
    autonomy_policy: str
    risk_class: str
    privacy_class: str
    created_at: str
    digest: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema"] = _SCHEMA
        return payload


def _digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compile_goal_contract(
    goal: str,
    *,
    risk_class: str = "R2",
    privacy_class: str = "D1",
    explicit_constraints: Iterable[str] = (),
    explicit_success_criteria: Iterable[str] = (),
    explicit_stop_rules: Iterable[str] = (),
) -> GoalContract:
    """Compile user intent into a deterministic goal contract.

    The compiler preserves user wording as evidence.  Heuristics only classify
    sentences; they never delete an explicit instruction or invent a legal or
    operational authority.
    """
    normalized_goal = _clean(goal)
    if len(normalized_goal) < 8:
        raise ValueError("goal is too short to form a verifiable autonomous contract")

    sentences = _sentences(goal)
    constraints = list(explicit_constraints)
    success = list(explicit_success_criteria)
    priorities: list[str] = []
    context: list[str] = []
    why_candidates: list[str] = []
    non_goals: list[str] = []

    for sentence in sentences:
        low = sentence.casefold()
        if _matches(sentence, _CONSTRAINT_MARKERS):
            constraints.append(sentence)
            if any(marker in low for marker in ("must not", "do not", "don't", "never", "without", "نباید", "بدون")):
                non_goals.append(sentence)
        if _matches(sentence, _SUCCESS_MARKERS):
            success.append(sentence)
        if _matches(sentence, _PRIORITY_MARKERS):
            priorities.append(sentence)
        if _matches(sentence, _WHY_MARKERS):
            why_candidates.append(sentence)
        if any(marker in low for marker in ("current", "existing", "context", "project", "system", "source", "file", "dashboard", "اکنون", "فعلی", "پروژه", "سیستم")):
            context.append(sentence)

    outcome = sentences[0] if sentences else normalized_goal
    why = why_candidates[0] if why_candidates else "Deliver the requested outcome with measurable evidence, bounded autonomy and no hidden scope expansion."
    if not success:
        success.extend(
            (
                "All mandatory hard gates pass with reproducible evidence.",
                "The final output directly satisfies the stated goal without violating explicit constraints.",
                "Failures, unavailable providers and unresolved uncertainty remain visible rather than being silently replaced.",
            )
        )
    verification = (
        "Validate every material claim against deterministic evidence or an explicitly identified authoritative source.",
        "Run risk-appropriate functional, failure, security and regression checks before completion.",
        "Record provider/model identity, effort, latency, usage and evidence receipts for every material agent contribution.",
        "Keep public, private and customer-restricted data in separate roots and release histories.",
    )
    stop_rules = _unique(
        (
            *explicit_stop_rules,
            "Stop successfully when all mandatory gates pass and required roles accept the same result digest.",
            "Stop and report a blocker when a required role or evidence source is unavailable and no authorized equivalent exists.",
            "Stop revision after two consecutive rounds with no new material finding.",
            "Stop immediately when token, wall-clock, privacy, authorization or safety limits are reached.",
        )
    )

    body = {
        "schema": _SCHEMA,
        "raw_goal": normalized_goal,
        "outcome": outcome,
        "why": why,
        "context": _unique(context),
        "constraints": _unique(constraints),
        "non_goals": _unique(non_goals),
        "priorities": _unique(priorities),
        "success_criteria": _unique(success),
        "verification": verification,
        "stop_rules": stop_rules,
        "clarification_policy": "Ask only when a missing fact changes safety, authority, scope or the measurable definition of done; otherwise proceed and record assumptions.",
        "autonomy_policy": "Plan and execute autonomously inside declared authority, data, budget and human-approval gates; the outcome matters more than a preselected sequence of steps.",
        "risk_class": risk_class,
        "privacy_class": privacy_class,
    }
    digest = _digest(body)
    return GoalContract(
        contract_id=f"goal-{digest[:20]}",
        raw_goal=normalized_goal,
        outcome=outcome,
        why=why,
        context=body["context"],
        constraints=body["constraints"],
        non_goals=body["non_goals"],
        priorities=body["priorities"],
        success_criteria=body["success_criteria"],
        verification=verification,
        stop_rules=stop_rules,
        clarification_policy=body["clarification_policy"],
        autonomy_policy=body["autonomy_policy"],
        risk_class=risk_class,
        privacy_class=privacy_class,
        created_at=utc_now(),
        digest=digest,
    )


def validate_goal_contract(contract: GoalContract | dict[str, Any]) -> dict[str, Any]:
    payload = contract.to_dict() if isinstance(contract, GoalContract) else dict(contract)
    required = {
        "raw_goal",
        "outcome",
        "why",
        "constraints",
        "success_criteria",
        "verification",
        "stop_rules",
        "risk_class",
        "privacy_class",
        "digest",
    }
    missing = sorted(required - payload.keys())
    errors: list[str] = []
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    if not payload.get("success_criteria"):
        errors.append("success criteria are empty")
    if not payload.get("stop_rules"):
        errors.append("stop rules are empty")
    body = {
        key: payload[key]
        for key in (
            "schema",
            "raw_goal",
            "outcome",
            "why",
            "context",
            "constraints",
            "non_goals",
            "priorities",
            "success_criteria",
            "verification",
            "stop_rules",
            "clarification_policy",
            "autonomy_policy",
            "risk_class",
            "privacy_class",
        )
        if key in payload
    }
    if not errors and payload.get("digest") != _digest(body):
        errors.append("goal contract digest mismatch")
    return {"decision": "pass" if not errors else "block", "errors": errors, "contract_id": payload.get("contract_id")}
