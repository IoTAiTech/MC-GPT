# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Authoritative task-backend routing.

The Community Suite owns its standalone task store. PMD/PRCS records are only
reachable through an authenticated, versioned Enterprise adapter; direct access
to another product's SQLite/PostgreSQL state is forbidden.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .external_blocker import evaluate_pmd_schema_recovery
from .licensing import current
from . import tasks as suite_tasks

TERMINAL_TECHNICAL_STATES = {
    "awaiting_founder",
    "technical_complete_awaiting_founder",
    "completed",
    "closed",
    "cancelled",
    "rejected",
}
EXECUTION_ELIGIBLE_STATES = {"backlog", "queued", "ready", "claimed", "active", "needs-work", "blocked"}


class ExternalBackendUnavailable(RuntimeError):
    """Raised when an external product authority cannot be reached safely."""


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    backend: str
    authority_basis: str
    status: str
    priority: str
    title: str
    description: str = ""
    risk_class: str = "R1"
    acceptance_criteria: str = ""
    revision: int = 1
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "backend": self.backend,
            "authority_basis": self.authority_basis,
            "status": self.status,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "risk_class": self.risk_class,
            "acceptance_criteria": self.acceptance_criteria,
            "revision": self.revision,
            "terminal": self.status in TERMINAL_TECHNICAL_STATES,
            "raw": self.raw or {},
        }


@runtime_checkable
class TaskBackend(Protocol):
    name: str
    authority_basis: str

    def discover(self, intent: dict[str, Any]) -> list[TaskRecord]: ...
    def snapshot(self, task_id: str) -> TaskRecord: ...
    def validation_gate(self, task_id: str, trigger_action: str = "run") -> dict[str, Any]: ...
    def adapter_receipt(self) -> dict[str, Any]: ...


def _suite_record(row: dict[str, Any]) -> TaskRecord:
    return TaskRecord(
        task_id=str(row["id"]),
        backend="suite",
        authority_basis="iot-ai-suite-standalone-task-store",
        status=str(row.get("status") or "unknown"),
        priority=str(row.get("priority") or "normal"),
        title=str(row.get("title") or row["id"]),
        description=str(row.get("description") or ""),
        risk_class=str(row.get("risk_class") or "R1"),
        acceptance_criteria=str(row.get("acceptance_criteria") or ""),
        revision=int(row.get("revision") or 1),
        raw=dict(row),
    )


class SuiteTaskBackend:
    name = "suite"
    authority_basis = "iot-ai-suite-standalone-task-store"

    def __init__(self, user_home: Path):
        self.user_home = user_home

    def discover(self, intent: dict[str, Any]) -> list[TaskRecord]:
        scope = intent.get("scope") or {}
        requested = [str(value) for value in scope.get("task_ids") or []]
        priorities = {str(value) for value in scope.get("priorities") or []}
        records: list[TaskRecord] = []
        if requested:
            for task_id in requested:
                if task_id.upper().startswith(("PMD-REQ-", "PRCS-")):
                    continue
                try:
                    records.append(self.snapshot(task_id))
                except ValueError:
                    continue
            return records
        query = scope.get("task_query")
        rows = suite_tasks.list_open(self.user_home, query=str(query) if query else None)
        for row in rows:
            if priorities and str(row.get("priority")) not in priorities:
                continue
            records.append(_suite_record(row))
        return records

    def snapshot(self, task_id: str) -> TaskRecord:
        payload = suite_tasks.show(self.user_home, task_id)
        return _suite_record(payload["task"])

    def validation_gate(self, task_id: str, trigger_action: str = "run") -> dict[str, Any]:
        from .task_validation import gate
        return gate(self.user_home, task_id, trigger_action)

    def adapter_receipt(self) -> dict[str, Any]:
        status = suite_tasks.workspace_status(self.user_home)
        return {
            "schema": "iot-ai.task-backend-receipt.v1",
            "backend": self.name,
            "authority_basis": self.authority_basis,
            "authenticated": True,
            "direct_product_db_access": False,
            "status": status,
        }


class PmdApiTaskBackend:
    name = "pmd-api"
    authority_basis = "authenticated-versioned-pmd-prcs-api"

    def __init__(self, user_home: Path):
        self.user_home = user_home
        entitlement = current()
        if not entitlement.pmd_adapter:
            raise ExternalBackendUnavailable("PMD task authority requires an Enterprise authenticated API adapter")
        self._blocker = evaluate_pmd_schema_recovery(user_home)
        if self._blocker.get("status") == "open":
            self._backend = None
            return
        try:
            from iot_ai_enterprise.pmd_adapter import current_task_backend  # type: ignore
        except ImportError as exc:
            raise ExternalBackendUnavailable("PMD entitlement is present but the Enterprise PMD adapter is not installed") from exc
        backend = current_task_backend(user_home)
        required = ("discover", "snapshot", "validation_gate", "adapter_receipt")
        if not all(callable(getattr(backend, name, None)) for name in required):
            raise ExternalBackendUnavailable("Enterprise PMD adapter does not implement the required versioned contract")
        self._backend = backend

    def discover(self, intent: dict[str, Any]) -> list[TaskRecord]:
        if self._backend is None:
            return []
        values = self._backend.discover(intent)
        result: list[TaskRecord] = []
        for value in values:
            row = dict(value)
            result.append(TaskRecord(
                task_id=str(row.get("task_id") or row.get("request_id")),
                backend=self.name,
                authority_basis=self.authority_basis,
                status=str(row.get("status") or "unknown"),
                priority=str(row.get("priority") or "normal"),
                title=str(row.get("title") or row.get("task_id") or row.get("request_id")),
                description=str(row.get("description") or ""),
                risk_class=str(row.get("risk_class") or "R2"),
                acceptance_criteria=str(row.get("acceptance_criteria") or ""),
                revision=int(row.get("revision") or 1),
                raw=row,
            ))
        return result

    def snapshot(self, task_id: str) -> TaskRecord:
        values = self.discover({"scope": {"task_ids": [task_id]}})
        if not values:
            raise ValueError("Task not found")
        return values[0]

    def validation_gate(self, task_id: str, trigger_action: str = "run") -> dict[str, Any]:
        if self._backend is None:
            return dict(self._blocker)
        return dict(self._backend.validation_gate(task_id, trigger_action))

    def adapter_receipt(self) -> dict[str, Any]:
        if self._backend is None:
            return {
                "schema": "iot-ai.task-backend-receipt.v1",
                "backend": self.name,
                "authority_basis": self.authority_basis,
                "authenticated": False,
                "direct_product_db_access": False,
                "blocker": dict(self._blocker),
            }
        receipt = dict(self._backend.adapter_receipt())
        return {
            "schema": "iot-ai.task-backend-receipt.v1",
            "backend": self.name,
            "authority_basis": self.authority_basis,
            "authenticated": bool(receipt.get("authenticated")),
            "direct_product_db_access": False,
            "adapter": receipt,
        }

    def run_task(self, task_id: str, *, intent: dict[str, Any], apply: bool) -> dict[str, Any]:
        """Delegate the complete closed-loop run to the authenticated PMD authority.

        The public Suite passes only a versioned intent contract. It never opens
        PMD SQLite/PostgreSQL files and never synthesizes a second task state.
        """
        if self._backend is None:
            return dict(self._blocker)
        handler = getattr(self._backend, "run_task", None)
        if not callable(handler):
            raise ExternalBackendUnavailable("Enterprise PMD adapter lacks governed run_task support")
        result = dict(handler(task_id=task_id, intent=intent, apply=apply))
        if result.get("direct_product_db_access") is True:
            raise ExternalBackendUnavailable("PMD adapter reported forbidden direct product database access")
        return result


def select_backend(user_home: Path, intent: dict[str, Any]) -> TaskBackend:
    backend = str((intent.get("scope") or {}).get("backend") or "suite")
    if backend == "pmd-api":
        return PmdApiTaskBackend(user_home)
    if backend != "suite":
        raise ExternalBackendUnavailable(f"unsupported task backend: {backend}")
    return SuiteTaskBackend(user_home)
