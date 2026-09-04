# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-03
"""One Skill Router. Silent in user text; machine-readable selection receipts only."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .runtime_gates import coerce_max_selected, inherit_skill_privacy
from .settings import effective_settings, load as load_settings
from .skill_registry import discover
from .util import utc_now

ROUTER_VERSION = "1.1.0"
VISUAL_TERMS = (
    "website",
    "landing page",
    "dashboard ui",
    "dashboard",
    "frontend",
    "html",
    "css",
    "javascript",
    "react",
    "ux",
    "ui",
    "design system",
    "responsive",
    "typography",
    "visual hierarchy",
    "prototype",
    "web slides",
    "data visualization",
    "graphic",
    "image prompt",
    "web design",
)
BACKEND_ONLY_TERMS = (
    "sqlite",
    "database schema",
    "cli flag",
    "command-line only",
    "systemd unit",
    "migration sql",
)
AUTHORITY_BLOCK_TERMS = (
    "write scope",
    "authorize execution",
    "expose secrets",
    "disable tests",
    "disable mncg",
    "create tasks",
    "product database",
    "request a release",
    "override provider",
    "suppress evidence",
)
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._-]{1,}", re.I)


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(text or "")}


def _visual_match(blob: str, tokens: set[str]) -> bool:
    for term in VISUAL_TERMS:
        needle = term.casefold()
        if " " in needle or "-" in needle:
            if needle in blob:
                return True
        elif needle in tokens:
            return True
    return False


def is_visual_task(goal: str, artifact: str | None = None, role_id: str | None = None) -> bool:
    blob = " ".join(part for part in (goal, artifact, role_id) if part).casefold()
    tokens = _tokens(blob)
    if any(term in blob for term in BACKEND_ONLY_TERMS) and not _visual_match(blob, tokens):
        return False
    return _visual_match(blob, tokens) or (role_id or "") in {"operator-ux-reviewer"}


def _score(skill: dict[str, Any], *, goal: str, role_id: str | None, stage: str | None, artifact: str | None) -> float:
    hay = " ".join(
        str(part)
        for part in (
            skill.get("id"),
            skill.get("name"),
            skill.get("description"),
            skill.get("category"),
            " ".join(skill.get("compatibility") or []),
        )
        if part
    )
    terms = _tokens(" ".join(part for part in (goal, role_id, stage, artifact) if part))
    skill_terms = _tokens(hay)
    overlap = len(terms & skill_terms)
    score = overlap * 4.0
    category = str(skill.get("category") or "")
    if category == "visual" and is_visual_task(goal, artifact, role_id):
        score += 40
    if category == "visual" and not is_visual_task(goal, artifact, role_id):
        score -= 50
    if skill.get("id") == "iot-ai-web-visual-quality" and is_visual_task(goal, artifact, role_id):
        score += 30
    if role_id and role_id.replace("_", "-") in hay.casefold():
        score += 8
    if skill.get("source") == "packaged":
        score += 2
    if skill.get("source") == "project":
        score += 4
    if str(skill.get("license") or "").startswith("LicenseRef-PolyForm"):
        score += 1
    return round(score, 3)


def select_skills(
    user_home: Path,
    *,
    goal: str,
    role_id: str | None = None,
    stage: str | None = None,
    artifact: str | None = None,
    settings: dict[str, Any] | None = None,
    project_root: Path | None = None,
    host_native_image_tool: bool = False,
) -> dict[str, Any]:
    document = settings if settings is not None else load_settings(user_home)
    skills_cfg = document.get("skills") or {}
    effective = effective_settings(user_home, document)
    allow = {str(item) for item in skills_cfg.get("allow") or []}
    auto_discover = skills_cfg.get("auto_discover", True) is not False
    if not auto_discover and not allow:
        return {
            "receipt": {
                "schema": "iot-ai.skill-selection.v1",
                "router_version": ROUTER_VERSION,
                "selected": [],
                "rejected": [{"reason": "auto_discover disabled"}],
                "role": role_id,
                "stage": stage,
                "execution_mode": skills_cfg.get("execution_mode_default") or "reference-only",
                "effective_settings_digest": effective.get("effective_settings_digest"),
                "silent_user_responses": bool(skills_cfg.get("silent_user_responses", True)),
                "visual_task": is_visual_task(goal, artifact, role_id),
                "created_at": utc_now(),
            },
            "selected": [],
            "discovered_count": 0,
        }
    discovered = discover(
        user_home=user_home,
        extra_roots=list(skills_cfg.get("extra_roots") or []),
        project_root=project_root,
        license_allowlist=list(skills_cfg.get("license_allowlist") or []),
    )
    deny = {str(item) for item in skills_cfg.get("deny") or []}
    max_selected = coerce_max_selected(skills_cfg.get("max_selected"), 4)
    design_policy = str(skills_cfg.get("design_policy") or "off")
    visual = is_visual_task(goal, artifact, role_id)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = list(discovered.get("rejected") or [])
    ranked: list[tuple[float, dict[str, Any]]] = []
    for skill in discovered.get("skills", {}).values():
        skill_id = skill["id"]
        if skill_id in deny:
            rejected.append({"id": skill_id, "reason": "user deny rule"})
            continue
        if not auto_discover and skill_id not in allow:
            rejected.append({"id": skill_id, "reason": "auto_discover disabled"})
            continue
        body = str(skill.get("body") or "")
        if any(term in body.casefold() for term in AUTHORITY_BLOCK_TERMS):
            rejected.append({"id": skill_id, "reason": "attempts to override MC-GPT authority or safety policy"})
            continue
        if skill_id == "iot-ai-image-capability" or skill_id.endswith("gpt-image-2"):
            image_request = "image" in (goal or "").casefold() or "image" in (artifact or "").casefold()
            if not (host_native_image_tool and image_request):
                rejected.append({"id": skill_id, "reason": "host-native image tool unavailable or request is not image generation", "capability_status": "unavailable"})
                continue
        score = _score(skill, goal=goal, role_id=role_id, stage=stage, artifact=artifact)
        if allow and skill_id in allow:
            score += 20
        if design_policy == "auto-visual-only" and skill.get("category") == "visual" and visual:
            score += 25
        if design_policy == "auto-visual-only" and skill.get("category") == "visual" and not visual:
            rejected.append({"id": skill_id, "reason": "visual skill not applied to backend/CLI task"})
            continue
        overlap_tokens = len(
            _tokens(" ".join(part for part in (goal, role_id, stage, artifact) if part))
            & _tokens(" ".join(str(skill.get(key) or "") for key in ("id", "name", "description", "category")))
        )
        if skill_id not in allow and overlap_tokens < 2 and not (skill.get("category") == "visual" and visual):
            rejected.append({"id": skill_id, "reason": "below relevance threshold", "score": score})
            continue
        if score < 12 and skill_id not in allow:
            rejected.append({"id": skill_id, "reason": "below relevance threshold", "score": score})
            continue
        ranked.append((score, skill))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    for score, skill in ranked[: max(0, max_selected)]:
        selected.append(
            {
                "id": skill["id"],
                "version": skill["version"],
                "category": skill["category"],
                "source": skill["source"],
                "license": skill["license"],
                "source_commit": skill.get("source_commit") or "",
                "file_sha256": skill["file_sha256"],
                "score": score,
                "role": role_id,
                "stage": stage,
                "execution_mode": skill.get("execution_mode") or skills_cfg.get("execution_mode_default") or "reference-only",
                "trust": "bounded-guidance",
                "guidance": skill.get("body") or "",
                "privacy_class": inherit_skill_privacy(str(skill.get("source") or "packaged"), skill.get("declared_privacy_class") or skill.get("privacy_class")),
                "privacy_inherited_from_source": True,
            }
        )
    eligible_ids = [row["id"] for row in selected]
    receipt = {
        "schema": "iot-ai.skill-selection.v2",
        "router_version": ROUTER_VERSION,
        "selected": [
            {key: row[key] for key in row if key != "guidance"}
            for row in selected
        ],
        "rejected": rejected,
        "role": role_id,
        "stage": stage,
        "execution_mode": skills_cfg.get("execution_mode_default") or "reference-only",
        "effective_settings_digest": effective.get("effective_settings_digest"),
        "silent_user_responses": bool(skills_cfg.get("silent_user_responses", True)),
        "visual_task": visual,
        "discovered_count": int(discovered.get("count") or 0),
        "skill_state": {
            "schema": "iot-ai.skill-state.v1",
            "discovered": int(discovered.get("count") or 0),
            "eligible": eligible_ids,
            "selected": eligible_ids,
            "included_in_context": [],
            "truncated": [],
            "actually_used": [],
            "rejected": rejected,
            "privacy": {"inherited_from_source": True, "cloud_egress_checked": False, "errors": []},
        },
        "created_at": utc_now(),
    }
    return {
        "receipt": receipt,
        "selected": selected,
        "discovered_count": int(discovered.get("count") or 0),
    }


def context_blocks(selection: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = []
    for row in selection.get("selected") or []:
        blocks.append(
            {
                "kind": "skill-guidance",
                "source": row["id"],
                "privacy_class": inherit_skill_privacy(str(row.get("source") or "packaged"), row.get("privacy_class")),
                "payload": {
                    "skill_id": row["id"],
                    "trust": "bounded-guidance",
                    "license": row.get("license"),
                    "execution_mode": row.get("execution_mode"),
                    "guidance": row.get("guidance") or "",
                    "authority": "bounded-guidance-not-governing",
                    "cannot_override": [
                        "system policy",
                        "Founder instructions",
                        "goal contract",
                        "role contract",
                        "node contract",
                        "tool contract",
                        "privacy classification",
                        "execution authorization",
                        "MNCG",
                        "release governance",
                        "human approval",
                        "direct-product-database restrictions",
                    ],
                },
            }
        )
    return blocks
