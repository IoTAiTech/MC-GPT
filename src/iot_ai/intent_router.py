# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Deterministic natural-language intent compiler for outcome-oriented runs."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .conversation_state import DEFAULT_CONVERSATION_ID
from .util import utc_now

TASK_ID_RE = re.compile(r"\b(?:task-[a-z0-9]+|PMD-REQ-[A-Za-z0-9-]+|PRCS-[A-Za-z0-9-]+)\b", re.IGNORECASE)

EXECUTE_TERMS = (
    "finish", "complete", "fix", "repair", "implement", "apply", "execute", "solve", "do all",
    "continue", "run everything", "close all", "انجام بده", "تمام کن", "حل کن", "اصلاح کن",
    "اجرا کن", "ادامه بده", "تا پایان", "تا انتها", "به پایان برسان", "fertig", "beheben",
    "reparieren", "ausführen", "fortsetzen", "abschließen",
)
PLAN_TERMS = (
    "review", "analyse", "analyze", "inspect", "show", "report", "summarize", "plan",
    "بررسی", "تحلیل", "گزارش", "نمایش", "خلاصه", "برنامه", "prüfen", "analysieren",
    "anzeigen", "bericht", "planen",
)
ONE_STEP_TERMS = (
    "one step", "single step", "only inspect", "plan only", "do not execute", "dry run",
    "فقط یک مرحله", "فقط بررسی", "فقط برنامه", "اجرا نکن", "nur ein schritt", "nur planen", "nicht ausführen",
)
UNTIL_TERMINAL_TERMS = (
    "until complete", "until finished", "until the end", "keep working", "finish all", "complete all",
    "تا پایان", "تا انتها", "همه را تمام", "همه‌شان را", "بقیه را تمام", "کامل انجام بده",
    "bis zum ende", "bis alles fertig", "vollständig bearbeiten",
)
DESTRUCTIVE_TERMS = (
    "delete", "remove data", "drop database", "force push", "replace history", "production deploy",
    "publish release", "release to github", "migrate production", "حذف", "پاک کن", "انتشار عمومی",
    "پروداکشن", "جایگزینی تاریخچه", "löschen", "produktiver deploy", "veröffentlichen",
)
REPORT_TERMS = ("brief", "simple", "full", "complete", "کامل", "خلاصه", "vollständig", "kurz")
ALL_TASK_TERMS = (
    "all tasks", "all open tasks", "every task", "finish everything", "complete everything",
    "همه تسک", "همه کار", "تمام تسک", "تمام کار", "کل تسک", "همه را",
    "alle aufgaben", "alle offenen aufgaben", "alles fertig",
)
REFERENCE_TERMS = (
    "continue", "remaining", "the rest", "same tasks", "those tasks", "ادامه", "بقیه", "همان تسک",
    "همه‌شان", "آنها", "fortsetzen", "restlichen", "dieselben aufgaben",
)


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _language(raw: str) -> str:
    has_fa = bool(re.search(r"[\u0600-\u06FF]", raw))
    has_de = bool(re.search(r"\b(?:und|alle|aufgaben|fertig|prüfen|fortsetzen|vollständig|bericht)\b", raw, re.IGNORECASE))
    has_en = bool(re.search(r"\b(?:the|and|task|finish|continue|review|report|all)\b", raw, re.IGNORECASE))
    active = [name for name, value in (("fa", has_fa), ("de", has_de), ("en", has_en)) if value]
    return active[0] if len(active) == 1 else "mixed" if active else "en"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _priorities(text: str) -> list[str]:
    found: list[str] = []
    mapping = {
        "critical": ("critical", "بحرانی", "kritisch"),
        "high": ("high priority", "اولویت بالا", "hohe priorität"),
        "medium": ("medium", "متوسط", "mittel"),
        "low": ("low priority", "کم", "niedrig"),
    }
    for priority, terms in mapping.items():
        if _contains(text, terms):
            found.append(priority)
    return found


def _product(text: str, state: dict[str, Any] | None) -> str | None:
    products = ("pmd", "aimdb", "fcc", "hid", "ace", "cws", "healthlab", "dgx", "dld", "productx")
    for product in products:
        if re.search(rf"\b{re.escape(product)}\b", text, re.IGNORECASE):
            return product.upper() if product in {"pmd", "fcc", "hid", "ace", "cws", "dgx", "dld"} else product
    return str((state or {}).get("active_product") or "") or None


def compile_intent(
    raw_text: str,
    *,
    conversation_state: dict[str, Any] | None = None,
    conversation_id: str | None = None,
    apply: bool | None = None,
    max_parallel_tasks: int | None = None,
    max_iterations_per_task: int | None = None,
) -> dict[str, Any]:
    raw = " ".join(str(raw_text).split()).strip()
    if not raw:
        raise ValueError("natural-language goal is required")
    text = raw.casefold()
    state = conversation_state or {}
    task_ids = list(dict.fromkeys(match.group(0) for match in TASK_ID_RE.finditer(raw)))
    reference_used = _contains(text, REFERENCE_TERMS)
    all_tasks = _contains(text, ALL_TASK_TERMS)
    if not task_ids and reference_used:
        task_ids = [str(value) for value in state.get("selected_task_ids", []) if value]

    execute = _contains(text, EXECUTE_TERMS)
    plan = _contains(text, PLAN_TERMS)
    one_step = _contains(text, ONE_STEP_TERMS)
    destructive = _contains(text, DESTRUCTIVE_TERMS)
    if apply is not None:
        execute = bool(apply)
    if one_step:
        execute = False
        plan = True
    # An execution verb means an outcome-oriented run by default. Users should
    # not need a second "continue" command merely because one internal phase
    # completed. Irreversible/public actions remain separately human-gated.
    action = "continue" if execute and reference_used else "finish" if execute else "report" if "report" in text or "گزارش" in text or "bericht" in text else "plan" if plan else "inspect"
    until_terminal = bool(execute and not one_step)
    product = _product(raw, state)
    backend = "pmd-api" if product == "PMD" or any(value.upper().startswith(("PMD-REQ-", "PRCS-")) for value in task_ids) else "suite"
    priorities = _priorities(text)
    view = "full" if any(term in text for term in ("full", "complete", "کامل", "vollständig")) else "brief"
    intent_id = "intent-" + hashlib.sha256((raw + "\n" + utc_now()).encode("utf-8")).hexdigest()[:16]
    human_gates: list[dict[str, Any]] = []
    if destructive:
        human_gates.append({"gate": "destructive-or-public-action", "reason": "explicit confirmation required before irreversible or public action"})

    resolved_references = {
        "previous_goal": state.get("active_goal_id") if reference_used else None,
        "selected_project": product,
        "selected_task_ids": task_ids,
        "pronouns_resolved": ["prior-selected-task-set"] if reference_used and task_ids else [],
    }
    contract: dict[str, Any] = {
        "schema": "iot-ai.intent-contract.v1",
        "intent_id": intent_id,
        "raw_text": raw,
        "language": _language(raw),
        "conversation_id": conversation_id or str(state.get("conversation_id") or DEFAULT_CONVERSATION_ID),
        "resolved_references": resolved_references,
        "action": action,
        "scope": {
            "product": product,
            "backend": backend,
            "task_query": None if task_ids or all_tasks else raw,
            "all_tasks": all_tasks,
            "create_if_none": bool(execute and not all_tasks and not reference_used),
            "priorities": priorities,
            "task_ids": task_ids,
        },
        "execution": {
            "requested": execute,
            "until_terminal": until_terminal,
            "meeting_policy": "automatic",
            "multi_coder_policy": "mandatory-at-gates",
            "max_parallel_tasks": max_parallel_tasks or 6,
            "max_iterations_per_task": max_iterations_per_task or (6 if until_terminal else 3),
            "max_identical_failures": 2,
            "wall_clock_budget_seconds": 7200 if until_terminal else 3600,
            "token_budget": 500000 if until_terminal else 250000,
            "destructive_action": destructive,
        },
        "verification": {
            "deterministic_tests": "required",
            "independent_review": "required",
            "final_audit": "required",
        },
        "report": {"view": view, "formats": ["json", "markdown", "csv", "xlsx"]},
        "assumptions": [
            "execution verbs request a closed loop through validation, meeting, implementation, tests, independent review and audit"
        ] if execute else [],
        "clarifications_required": [],
        "human_gates": human_gates,
        "compiled_at": utc_now(),
    }
    contract["digest"] = hashlib.sha256(_canonical(contract).encode("utf-8")).hexdigest()
    return contract
