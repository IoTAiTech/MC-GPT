# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Minimal persisted conversation state for natural-language orchestration.

Only operator-visible workflow facts are stored. Private model reasoning and raw
provider prompts/outputs are deliberately excluded.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .paths import state_root
from .util import atomic_json, load_json, utc_now

DEFAULT_CONVERSATION_ID = "default"


def _safe_id(value: str | None) -> str:
    candidate = (value or DEFAULT_CONVERSATION_ID).strip()
    if not candidate or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", candidate):
        raise ValueError("invalid conversation_id")
    return candidate


def conversation_state_path(user_home: Path, conversation_id: str | None = None) -> Path:
    return state_root(user_home) / "conversations" / f"{_safe_id(conversation_id)}.json"


def empty_state(conversation_id: str | None = None) -> dict[str, Any]:
    return {
        "schema": "iot-ai.conversation-state.v1",
        "conversation_id": _safe_id(conversation_id),
        "active_goal_id": None,
        "last_intent_id": None,
        "active_product": None,
        "active_backend": None,
        "selected_task_ids": [],
        "last_task_table_digest": None,
        "pending_human_decisions": [],
        "external_blockers": [],
        "last_checkpoint": None,
        "updated_at": utc_now(),
    }


def load_state(user_home: Path, conversation_id: str | None = None) -> dict[str, Any]:
    path = conversation_state_path(user_home, conversation_id)
    value = load_json(path, None)
    if not isinstance(value, dict) or value.get("schema") != "iot-ai.conversation-state.v1":
        return empty_state(conversation_id)
    state = empty_state(conversation_id)
    state.update(value)
    state["conversation_id"] = _safe_id(conversation_id or str(value.get("conversation_id") or "default"))
    for name in ("selected_task_ids", "pending_human_decisions", "external_blockers"):
        if not isinstance(state.get(name), list):
            state[name] = []
    return state


def save_state(user_home: Path, state: dict[str, Any]) -> dict[str, Any]:
    value = dict(state)
    value["schema"] = "iot-ai.conversation-state.v1"
    value["conversation_id"] = _safe_id(str(value.get("conversation_id") or DEFAULT_CONVERSATION_ID))
    value["updated_at"] = utc_now()
    atomic_json(conversation_state_path(user_home, value["conversation_id"]), value)
    return value


def update_state(user_home: Path, conversation_id: str | None = None, **changes: Any) -> dict[str, Any]:
    state = load_state(user_home, conversation_id)
    for key, value in changes.items():
        if key in {"schema", "conversation_id", "updated_at"}:
            continue
        state[key] = value
    return save_state(user_home, state)
