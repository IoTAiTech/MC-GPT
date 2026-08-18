# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-18
"""Authoritative privacy-class arithmetic. Downgrade is forbidden."""
from __future__ import annotations

from typing import Any, Iterable

PRIVACY_ORDER = {"D0": 0, "D1": 1, "D2": 2, "D3": 3}
DEFAULT_CLASS = "D1"


def normalize_privacy_class(value: Any, *, default: str = DEFAULT_CLASS) -> str:
    text = str(value or "").strip().upper()
    if text in PRIVACY_ORDER:
        return text
    return default if default in PRIVACY_ORDER else DEFAULT_CLASS


def max_privacy_class(*values: Any, default: str = DEFAULT_CLASS) -> str:
    current = normalize_privacy_class(default)
    for value in values:
        if value is None:
            continue
        candidate = normalize_privacy_class(value, default=current)
        if PRIVACY_ORDER[candidate] > PRIVACY_ORDER[current]:
            current = candidate
    return current


def collect_block_classes(blocks: Iterable[Any] | None) -> list[str]:
    found: list[str] = []
    for block in blocks or []:
        if isinstance(block, dict):
            found.append(normalize_privacy_class(block.get("privacy_class")))
        else:
            found.append(normalize_privacy_class(getattr(block, "privacy_class", None)))
    return found


def authoritative_privacy_class(
    *declared: Any,
    blocks: Iterable[Any] | None = None,
    default: str = DEFAULT_CLASS,
) -> str:
    return max_privacy_class(*declared, *collect_block_classes(blocks), default=default)


def deny_downgrade(current: Any, requested: Any) -> str:
    resolved_current = normalize_privacy_class(current)
    resolved_requested = normalize_privacy_class(requested, default=resolved_current)
    if PRIVACY_ORDER[resolved_requested] < PRIVACY_ORDER[resolved_current]:
        raise PermissionError(
            f"privacy-class-downgrade-denied:{resolved_current}->{resolved_requested}"
        )
    return max_privacy_class(resolved_current, resolved_requested)
