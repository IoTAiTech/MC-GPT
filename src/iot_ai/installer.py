# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
"""Transactional host-adapter and command-surface installer."""
from __future__ import annotations

import os
import shlex
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from . import __version__
from .logging_config import append_event, log_locations, transaction_log
from .paths import SUITE_NAMESPACE, data_root, install_state_path, legacy_locations
from .util import atomic_json, atomic_text, load_json, sha256_file, utc_now

HOSTS = ("claude", "codex", "gemini", "grok")
PUBLIC_SKILLS = (
    "iot-ai",
    "iot-ai-help",
    "iot-ai-status",
    "iot-ai-settings",
    "iot-ai-update",
)
SKILLS = PUBLIC_SKILLS


def _skill_content(skill: str) -> str:
    labels = {
        "iot-ai": "agentically solve a natural-language goal using the dependency graph",
        "iot-ai-help": "show current commands, roles, policies and examples",
        "iot-ai-status": "show Suite, coder, provider, model, effort and workflow health",
        "iot-ai-settings": "manage portable Suite and provider settings",
        "iot-ai-update": "use the single transactional update authority",
    }
    return (
        "---\n"
        f"name: {skill}\n"
        f"description: {labels[skill]}\n"
        "---\n"
        f"# {skill}\n\n"
        "Use the installed `iot-ai` CLI as the only public control surface.\n\n"
        f"- Example: `/{skill} ...` or `{skill} ...`\n"
        "- Read `iot-ai help` before inventing flags.\n"
        "- Preserve role contracts, evidence, privacy, task authority, and public/private boundaries.\n"
        "- Never claim a provider/model contribution without a live requested/served receipt.\n"
    )


def _target(user_home: Path, host: str, skill: str) -> Path:
    if host == "claude":
        return user_home / ".claude" / "skills" / skill / "SKILL.md"
    if host == "codex":
        return user_home / ".agents" / "skills" / skill / "SKILL.md"
    if host == "grok":
        return user_home / ".grok" / "skills" / skill / "SKILL.md"
    return user_home / ".gemini" / "commands" / f"{skill}.toml"


def _content(host: str, skill: str) -> str:
    if host != "gemini":
        return _skill_content(skill)
    return (
        f'description = "IOT-AI command {skill}"\n'
        'prompt = """\n'
        f"Use the installed `{skill}` command for this request.\n"
        "First inspect `iot-ai help`; do not invent flags, receipts, models or authority.\n"
        '"""\n'
    )


def _wrapper_specs() -> dict[str, list[str]]:
    return {
        "iot-ai": [],
        "iot-ai-help": ["help"],
        "iot-ai-status": ["status"],
        "iot-ai-settings": ["settings"],
        "iot-ai-update": ["update"],
    }


def _wrapper_path(user_home: Path, name: str) -> Path:
    if os.name == "nt":
        return user_home / "AppData" / "Local" / "IoT-AI.Tech" / "IOT-AI-Suite" / "v1" / "bin" / f"{name}.cmd"
    return user_home / ".local" / "bin" / name


def _legacy_observations(user_home: Path) -> dict[str, Any]:
    locations = legacy_locations(user_home)
    legacy_names = (
        "iot-ai",
        "iot-ai-help",
        "iot-ai-setup",
        "iot-ai-meeting",
        "iot-ai-tasks",
        "iot-ai-multi-coder",
        "iot-ai-mc-gpt-update",
    )
    binary_dir = locations["binary_dir"]
    observed = {
        "config_exists": locations["config"].exists(),
        "data_exists": locations["data"].exists(),
        "commands": [],
        "policy": "snapshot-before-replace-never-delete-legacy-state",
    }
    for name in legacy_names:
        suffix = ".cmd" if os.name == "nt" else ""
        if (binary_dir / f"{name}{suffix}").exists():
            observed["commands"].append(name)
    return observed


def plan(user_home: Path, hosts: list[str]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for host in hosts:
        if host not in HOSTS:
            raise ValueError(f"unsupported host: {host}")
        for skill in SKILLS:
            actions.append(
                {
                    "kind": "skill",
                    "host": host,
                    "skill": skill,
                    "target": str(_target(user_home, host, skill)),
                }
            )
    for name in _wrapper_specs():
        actions.append({"kind": "wrapper", "target": str(_wrapper_path(user_home, name))})
    existing = load_json(install_state_path(user_home), {}) or {}
    intended = {str(item["target"]) for item in actions}
    obsolete = [
        str(item.get("path"))
        for item in existing.get("files", [])
        if str(item.get("path")) not in intended
    ]
    return {
        "decision": "plan",
        "version": __version__,
        "home": str(user_home),
        "namespace": SUITE_NAMESPACE,
        "legacy": _legacy_observations(user_home),
        "actions": actions,
        "clean_install": {
            "obsolete_managed_candidates": obsolete,
            "unknown_user_files_preserved": True,
            "legacy_state_preserved": True,
        },
        "logs": log_locations(user_home),
    }


def _assert_safe_target(user_home: Path, target: Path) -> None:
    resolved_home = user_home.resolve()
    current = target
    while current != user_home.parent and current != current.parent:
        if current.exists() and current.is_symlink():
            raise ValueError(f"symlinked managed path is forbidden: {current}")
        if current == user_home:
            break
        current = current.parent
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.resolve(strict=False).is_relative_to(resolved_home):
        raise ValueError(f"managed path escapes home: {target}")


def _write_wrapper(target: Path, args: list[str], user_home: Path) -> None:
    """Write a wrapper permanently bound to the installation scope."""
    command = " ".join(args)
    if os.name == "nt":
        content = (
            f'@echo off\r\n"{sys.executable}" -m iot_ai.cli --home "{user_home}" '
            f'{command} %*\r\n'
        )
    else:
        home_arg = shlex.quote(str(user_home))
        content = (
            f'#!/usr/bin/env sh\nexec "{sys.executable}" -m iot_ai.cli --home '
            f'{home_arg} {command} "$@"\n'
        )
    atomic_text(target, content, 0o700)
    if os.name != "nt":
        target.chmod(0o700)


def install(user_home: Path, hosts: list[str], operation: str = "install") -> dict[str, Any]:
    existing = load_json(install_state_path(user_home), {}) or {}
    transaction_id = f"TX-{uuid.uuid4().hex[:12]}"
    backup_root = data_root(user_home) / "backups" / transaction_id
    backup_root.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, str]] = []
    existing_managed = {item.get("path") for item in existing.get("files", [])}
    backups = list(existing.get("backups", []))
    rollback_files: list[dict[str, str]] = []
    intended_targets = {
        str(_target(user_home, host, skill))
        for host in hosts
        for skill in SKILLS
    } | {str(_wrapper_path(user_home, name)) for name in _wrapper_specs()}
    stale_managed = [
        Path(str(item.get("path")))
        for item in existing.get("files", [])
        if str(item.get("path")) not in intended_targets
    ]
    stale_drift = [
        str(path)
        for path in stale_managed
        if path.exists()
        and sha256_file(path) != next(
            str(item.get("sha256"))
            for item in existing.get("files", [])
            if str(item.get("path")) == str(path)
        )
    ]
    if stale_drift:
        raise RuntimeError(f"obsolete managed files drifted; clean install stopped: {stale_drift}")

    def backup_target(target: Path) -> None:
        if not target.exists():
            return
        category = "managed" if str(target) in existing_managed else "original"
        backup = backup_root / category / target.relative_to(user_home)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
        entry = {"target": str(target), "backup": str(backup)}
        if category == "managed":
            rollback_files.append(entry)
        elif not any(item.get("target") == str(target) for item in backups):
            backups.append(entry)

    for host in hosts:
        if host not in HOSTS:
            raise ValueError(f"unsupported host: {host}")
        for skill in SKILLS:
            target = _target(user_home, host, skill)
            _assert_safe_target(user_home, target)
            backup_target(target)
            atomic_text(target, _content(host, skill), 0o600)
            files.append({"path": str(target), "sha256": sha256_file(target)})

    for name, args in _wrapper_specs().items():
        target = _wrapper_path(user_home, name)
        _assert_safe_target(user_home, target)
        backup_target(target)
        _write_wrapper(target, args, user_home)
        files.append({"path": str(target), "sha256": sha256_file(target)})

    obsolete_removed: list[str] = []
    for target in stale_managed:
        _assert_safe_target(user_home, target)
        if target.is_file():
            backup_target(target)
            target.unlink()
            _cleanup_empty(target.parent, user_home)
            obsolete_removed.append(str(target))

    state = {
        "schema": "iot-ai-suite.install-state.v2",
        "namespace": SUITE_NAMESPACE,
        "legacy": _legacy_observations(user_home),
        "operation": operation,
        "version": __version__,
        "installed_at": utc_now(),
        "transaction_id": transaction_id,
        "home": str(user_home),
        "hosts": hosts,
        "files": files,
        "backups": backups,
        "rollback_files": rollback_files,
        "restart_required": True,
        "previous_state": existing or None,
        "clean_install": {
            "obsolete_managed_removed": obsolete_removed,
            "unknown_user_files_preserved": True,
            "legacy_state_preserved": True,
        },
        "logs": log_locations(user_home),
    }
    atomic_json(install_state_path(user_home), state)
    transaction_log(user_home, operation, transaction_id, state)
    append_event(user_home, f"host_adapters.{operation}.completed", state, audit=True, correlation_id=transaction_id)
    return {"decision": "pass", **state}


def repair(user_home: Path, hosts: list[str] | None = None) -> dict[str, Any]:
    state = load_json(install_state_path(user_home), {}) or {}
    return install(user_home, list(hosts or state.get("hosts") or HOSTS), "repair")


def upgrade(user_home: Path, hosts: list[str] | None = None) -> dict[str, Any]:
    state = load_json(install_state_path(user_home), {}) or {}
    return install(user_home, list(hosts or state.get("hosts") or HOSTS), "upgrade")


def verify(user_home: Path) -> dict[str, Any]:
    state = load_json(install_state_path(user_home))
    if not state:
        return {"decision": "needs-work", "blockers": ["not-installed"]}
    blockers: list[str] = []
    for item in state.get("files", []):
        path = Path(item["path"])
        if not path.is_file():
            blockers.append(f"missing:{path}")
        elif sha256_file(path) != item["sha256"]:
            blockers.append(f"drift:{path}")
    return {
        "decision": "pass" if not blockers else "needs-work",
        "version": state.get("version"),
        "blockers": blockers,
        "restart_required": state.get("restart_required", False),
    }


def status(user_home: Path) -> dict[str, Any]:
    state = load_json(install_state_path(user_home))
    if not state:
        return {"decision": "needs-work", "installed": False, "version": None, "rollback_available": False, "logs": log_locations(user_home)}
    checked = verify(user_home)
    return {
        "decision": checked["decision"],
        "installed": True,
        "version": state.get("version"),
        "hosts": state.get("hosts", []),
        "operation": state.get("operation", "install"),
        "restart_required": state.get("restart_required", False),
        "rollback_available": bool(state.get("previous_state") or _uninstall_pointer(user_home).exists()),
        "blockers": checked.get("blockers", []),
        "logs": log_locations(user_home),
    }


def _cleanup_empty(path: Path, user_home: Path) -> None:
    current = path
    while current != user_home and current.is_relative_to(user_home):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _uninstall_pointer(user_home: Path) -> Path:
    return data_root(user_home) / "uninstall-rollbacks" / "LATEST.json"


def uninstall(user_home: Path, force_drift: bool = False) -> dict[str, Any]:
    state = load_json(install_state_path(user_home))
    if not state:
        return {"decision": "pass", "removed": 0, "note": "not installed"}
    drift = [
        str(path)
        for item in state.get("files", [])
        if (path := Path(item["path"])).exists() and sha256_file(path) != item["sha256"]
    ]
    if drift and not force_drift:
        return {"decision": "block", "blockers": [f"drift:{path}" for path in drift]}

    receipt_id = f"UNINSTALL-{uuid.uuid4().hex[:12]}"
    root = data_root(user_home) / "uninstall-rollbacks" / receipt_id
    snapshot_root = root / "managed"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    snapshots: list[dict[str, str]] = []
    for item in state.get("files", []):
        path = Path(item["path"])
        if path.is_file():
            destination = snapshot_root / path.relative_to(user_home)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            snapshots.append(
                {"target": str(path), "snapshot": str(destination), "sha256": sha256_file(destination)}
            )
    receipt = {
        "schema": "iot-ai-suite.uninstall-rollback.v2",
        "receipt_id": receipt_id,
        "created_at": utc_now(),
        "state": state,
        "snapshots": snapshots,
        "consumed": False,
    }
    atomic_json(root / "receipt.json", receipt)
    atomic_json(_uninstall_pointer(user_home), {"receipt": str(root / "receipt.json")})

    backup_by_target = {item["target"]: item["backup"] for item in state.get("backups", [])}
    removed = 0
    restored = 0
    for item in state.get("files", []):
        path = Path(item["path"])
        backup = backup_by_target.get(str(path))
        if backup and Path(backup).is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, path)
            restored += 1
        elif path.exists():
            path.unlink()
            removed += 1
            _cleanup_empty(path.parent, user_home)
    install_state_path(user_home).unlink(missing_ok=True)
    result = {
        "decision": "pass",
        "removed": removed,
        "restored": restored,
        "rollback_receipt": str(root / "receipt.json"),
        "logs": log_locations(user_home),
    }
    transaction_log(user_home, "uninstall", receipt_id, result)
    append_event(user_home, "host_adapters.uninstall.completed", result, audit=True, correlation_id=receipt_id)
    return result


def rollback(user_home: Path) -> dict[str, Any]:
    state = load_json(install_state_path(user_home))
    if not state:
        pointer = load_json(_uninstall_pointer(user_home), {}) or {}
        receipt_path = Path(pointer.get("receipt", ""))
        if not receipt_path.is_file():
            raise ValueError("no installation or uninstall rollback state")
        receipt = load_json(receipt_path, {}) or {}
        for item in receipt.get("snapshots", []):
            source = Path(item["snapshot"])
            target = Path(item["target"])
            _assert_safe_target(user_home, target)
            if sha256_file(source) != item["sha256"]:
                return {"decision": "block", "blockers": [f"snapshot-drift:{source}"]}
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        atomic_json(install_state_path(user_home), receipt["state"])
        receipt["consumed"] = True
        receipt["consumed_at"] = utc_now()
        atomic_json(receipt_path, receipt)
        checked = verify(user_home)
        return {
            "decision": checked["decision"],
            "restored_from_uninstall": True,
            "receipt_id": receipt.get("receipt_id"),
            "blockers": checked.get("blockers", []),
            "logs": log_locations(user_home),
        }

    current = verify(user_home)
    if current["decision"] != "pass":
        return {"decision": "block", "blockers": current["blockers"]}
    previous = state.get("previous_state")
    if not previous:
        result = uninstall(user_home, False)
        return {
            "decision": result["decision"],
            "rolled_back_transaction": state["transaction_id"],
            "previous_state_restored": False,
            "details": result,
        }
    rollback_by_target = {item["target"]: item["backup"] for item in state.get("rollback_files", [])}
    previous_paths = {item.get("path") for item in previous.get("files", [])}
    for item in state.get("files", []):
        path = Path(item["path"])
        backup = rollback_by_target.get(str(path))
        if backup and Path(backup).is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, path)
        elif str(path) not in previous_paths and path.exists():
            path.unlink()
            _cleanup_empty(path.parent, user_home)
    atomic_json(install_state_path(user_home), previous)
    checked = verify(user_home)
    return {
        "decision": checked["decision"],
        "rolled_back_transaction": state["transaction_id"],
        "previous_state_restored": True,
        "blockers": checked.get("blockers", []),
        "logs": log_locations(user_home),
    }
