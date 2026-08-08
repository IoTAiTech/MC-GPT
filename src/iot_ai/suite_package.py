# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Transactional, PEP-668-safe installer for unified ALL-IN-ONE packages."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
import venv
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .installer import rollback as rollback_host_adapters
from .installer import verify as verify_host_adapters
from .logging_config import append_event, log_locations, transaction_log
from .paths import data_root, install_state_path, update_state_path
from .suite_version import MC_GPT_VERSION
from .util import atomic_json, load_json, sha256_file, utc_now

REQUIRED_MEMBERS = {"PACKAGE_METADATA.json", "MANIFEST.json"}
PACKAGE_SCHEMA = "iot-ai.suite-package.v1"
TRANSACTION_SCHEMA = "iot-ai.update-transaction.v3"


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and not path.is_absolute()
        and ".." not in path.parts
        and not name.startswith(("/", "\\"))
        and "\x00" not in name
    )


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)


def _same_device(source: Path, destination_parent: Path) -> bool:
    destination_parent.mkdir(parents=True, exist_ok=True)
    return source.stat().st_dev == destination_parent.stat().st_dev


def _clean_subprocess_env() -> dict[str, str]:
    """Prevent source-tree or active-venv leakage into isolated installs."""
    clean = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "__PYVENV_LAUNCHER__"):
        clean.pop(key, None)
    clean["PYTHONDONTWRITEBYTECODE"] = "1"
    clean["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return clean


def inspect_package(
    package: Path,
    expected_sha256: str | None = None,
    *,
    allowed_roots: list[Path] | tuple[Path, ...] | None = None,
) -> dict[str, Any]:
    """Validate package bytes, metadata, manifest coverage and wheelhouse.

    ``allowed_roots`` lets the update authority validate a safely extracted
    nested ALL-IN-ONE payload without widening the process-wide trust boundary.
    """
    if not package.is_file():
        raise FileNotFoundError(package)
    roots = list(allowed_roots or [
        Path.cwd().resolve(),
        Path.home().resolve(),
        *[
            Path(value).expanduser().resolve()
            for value in (os.environ.get("IOT_AI_ALLOWED_READ_ROOTS") or "").split(os.pathsep)
            if value.strip()
        ],
    ])
    actual = sha256_file(package, allowed_roots=roots, max_bytes=None)
    if expected_sha256 and actual != expected_sha256:
        raise ValueError("package SHA-256 mismatch")

    errors: list[str] = []
    metadata: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    entries: list[dict[str, Any]] = []
    wheels: list[str] = []
    with zipfile.ZipFile(package) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            errors.append("duplicate ZIP member")
        if any(not _safe_name(name) for name in names):
            errors.append("unsafe ZIP member")
        if any(_is_symlink(info) for info in infos):
            errors.append("symlink member forbidden")
        missing = REQUIRED_MEMBERS - set(names)
        if missing:
            errors.append(f"missing required members: {sorted(missing)}")
        if not errors:
            try:
                metadata = json.loads(archive.read("PACKAGE_METADATA.json"))
                manifest = json.loads(archive.read("MANIFEST.json"))
            except (json.JSONDecodeError, KeyError) as exc:
                errors.append(type(exc).__name__)
        if metadata and metadata.get("schema") != PACKAGE_SCHEMA:
            errors.append("invalid package metadata schema")
        if metadata:
            for field in ("product_id", "version", "python_distribution", "python_version"):
                if not str(metadata.get(field) or "").strip():
                    errors.append(f"missing package metadata field: {field}")
        entries = manifest.get("files", []) if isinstance(manifest, dict) else []
        if entries:
            indexed: dict[str, str] = {}
            for entry in entries:
                name = str(entry.get("path") or "")
                digest = str(entry.get("sha256") or "")
                if not _safe_name(name) or len(digest) != 64:
                    errors.append(f"invalid manifest entry: {name}")
                    continue
                if name in indexed:
                    errors.append(f"duplicate manifest entry: {name}")
                    continue
                indexed[name] = digest
            for name, digest in indexed.items():
                if name not in names:
                    errors.append(f"manifest missing member: {name}")
                elif hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    errors.append(f"manifest hash mismatch: {name}")
            unsealed = [
                name
                for name in names
                if not name.endswith("/") and name not in {"MANIFEST.json", "SHA256SUMS.txt"} and name not in indexed
            ]
            if unsealed:
                errors.append(f"unsealed members: {unsealed[:5]}")
        else:
            errors.append("manifest has no files")
        wheels = [name for name in names if name.startswith("wheels/") and name.endswith(".whl")]
        if not wheels:
            errors.append("wheelhouse is empty")

    return {
        "decision": "pass" if not errors else "block",
        "package": str(package),
        "sha256": actual,
        "metadata": metadata,
        "manifest_entries": len(entries),
        "wheels": wheels,
        "errors": errors,
    }


def _venv_paths(root: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        return root / "venv" / "Scripts" / "python.exe", root / "venv" / "Scripts" / "iot-ai.exe"
    return root / "venv" / "bin" / "python", root / "venv" / "bin" / "iot-ai"


def _wrapper_path(user_home: Path) -> Path:
    if os.name == "nt":
        return user_home / "AppData" / "Local" / "IoT-AI.Tech" / "IOT-AI-Suite" / "v1" / "bin" / "iot-ai.cmd"
    return user_home / ".local" / "bin" / "iot-ai"


def _restore_update_state(user_home: Path, prior_state: dict[str, Any] | None) -> None:
    path = update_state_path(user_home)
    if prior_state:
        atomic_json(path, prior_state)
    else:
        path.unlink(missing_ok=True)


def _restore_target(target: Path, target_backup: Path | None) -> None:
    shutil.rmtree(target, ignore_errors=True)
    if target_backup and target_backup.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(target_backup, target)


def _rollback_partial_host_install(user_home: Path, prior_install_state: dict[str, Any] | None) -> dict[str, Any]:
    current = load_json(install_state_path(user_home), {}) or {}
    if not current or current == (prior_install_state or {}):
        return {"decision": "pass", "action": "no-host-adapter-mutation"}
    try:
        return rollback_host_adapters(user_home)
    except Exception as exc:  # emergency restore is intentionally explicit
        if prior_install_state:
            atomic_json(install_state_path(user_home), prior_install_state)
        else:
            install_state_path(user_home).unlink(missing_ok=True)
        return {
            "decision": "needs-work",
            "action": "emergency-install-state-restore",
            "error": f"{type(exc).__name__}: {exc}",
        }



_CANONICAL_PACKAGE = re.compile(r"^IoT-AI-Tech-iot-ai-Coder-Suite-v(?P<version>[0-9A-Za-z.+-]+)-ALL-IN-ONE\.zip$")
_VERSION_NAME = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-.][0-9A-Za-z]+)*$")


def _managed_runtime_directory(path: Path) -> bool:
    """Return true only for recognisable Suite-managed active runtime roots."""
    metadata_path = path / "PACKAGE_METADATA.json"
    if metadata_path.is_file():
        metadata = load_json(metadata_path, {}) or {}
        product_id = str(metadata.get("product_id") or "")
        if metadata.get("schema") == PACKAGE_SCHEMA and product_id.startswith("iot-ai-tech.iot-ai"):
            return True
    _, entrypoint = _venv_paths(path)
    return bool(_VERSION_NAME.match(path.name)) and entrypoint.is_file()


def archive_old_active_versions(
    user_home: Path,
    current_version: str,
    transaction_root: Path,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Remove prior active code versions while retaining a rollback archive.

    Runtime data, settings, databases and unknown/customer directories are never
    touched.  Only recognised versioned Suite/component code roots are moved.
    """
    candidates: list[tuple[Path, Path]] = []
    suite_root = data_root(user_home) / "suite"
    if suite_root.is_dir():
        for child in sorted(suite_root.iterdir()):
            if child.is_dir() and child.name != current_version and _managed_runtime_directory(child):
                candidates.append((child, transaction_root / "retired-active-versions" / "suite" / child.name))
    component_base = data_root(user_home) / "components" / "iot-ai-mc-gpt"
    if component_base.is_dir():
        for child in sorted(component_base.iterdir()):
            if child.is_dir() and child.name != MC_GPT_VERSION and _VERSION_NAME.match(child.name):
                candidates.append((child, transaction_root / "retired-active-versions" / "components" / "iot-ai-mc-gpt" / child.name))
    result = {
        "decision": "plan",
        "operation": "clean-active-versions",
        "current_suite_version": current_version,
        "current_component_version": MC_GPT_VERSION,
        "candidates": [str(source) for source, _ in candidates],
        "archived": [],
        "unknown_directories_preserved": True,
        "runtime_state_preserved": True,
    }
    if not apply:
        return result
    archived: list[dict[str, str]] = []
    for source, destination in candidates:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise RuntimeError(f"clean-install archive already exists: {destination}")
        if not _same_device(source, destination.parent):
            raise RuntimeError("clean-install archive must share a filesystem with active runtime")
        os.replace(source, destination)
        archived.append({"source": str(source), "archive": str(destination)})
    return {**result, "decision": "pass", "archived": archived}


def _restore_archived_versions(records: list[dict[str, str]]) -> list[str]:
    restored: list[str] = []
    for item in reversed(records):
        source = Path(str(item["source"]))
        archive = Path(str(item["archive"]))
        if not archive.exists():
            continue
        if source.exists():
            shutil.rmtree(source)
        source.parent.mkdir(parents=True, exist_ok=True)
        os.replace(archive, source)
        restored.append(str(source))
    return restored


def clean_package_store(
    package_store: Path,
    current_package: Path,
    archive_root: Path,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Move prior canonical Suite packages out of the active package store."""
    store = package_store.expanduser().resolve()
    current = current_package.expanduser().resolve()
    candidates: list[Path] = []
    if store.is_dir():
        for path in sorted(store.iterdir()):
            if not path.is_file() or path.resolve() == current:
                continue
            if _CANONICAL_PACKAGE.match(path.name):
                candidates.append(path)
                for suffix in (".sha256", ".sig", ".asc"):
                    sidecar = path.with_name(path.name + suffix)
                    if sidecar.is_file():
                        candidates.append(sidecar)
    result = {
        "decision": "plan",
        "operation": "clean-package-store",
        "store": str(store),
        "current_package": str(current),
        "candidates": [str(path) for path in candidates],
        "archived": [],
        "unrelated_files_preserved": True,
    }
    if not apply:
        return result
    archive = archive_root.expanduser().resolve()
    if archive == store or store in archive.parents:
        # Nested archives are allowed but candidates are determined before it is created.
        pass
    archive.mkdir(parents=True, exist_ok=True)
    archived: list[dict[str, str]] = []
    for source in candidates:
        destination = archive / source.name
        if destination.exists():
            raise RuntimeError(f"package archive collision: {destination}")
        os.replace(source, destination)
        archived.append({"source": str(source), "archive": str(destination)})
    return {**result, "decision": "pass", "archived": archived}


def _restore_package_store(records: list[dict[str, str]]) -> list[str]:
    restored: list[str] = []
    for item in reversed(records):
        source = Path(str(item["source"]))
        archive = Path(str(item["archive"]))
        if not archive.exists():
            continue
        source.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            source.unlink()
        os.replace(archive, source)
        restored.append(str(source))
    return restored


def clean_install_state(
    user_home: Path,
    current_version: str,
    *,
    package_store: Path | None = None,
    current_package: Path | None = None,
    package_archive: Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Internal clean-install operation used by platform installers."""
    transaction_id = f"clean-{uuid.uuid4().hex[:12]}"
    root = data_root(user_home) / "update-transactions" / transaction_id
    active = archive_old_active_versions(user_home, current_version, root, apply=apply)
    packages = None
    if package_store is not None and current_package is not None:
        packages = clean_package_store(
            package_store,
            current_package,
            (package_archive or package_store / ".iot-ai-archive" / transaction_id),
            apply=apply,
        )
    result = {
        "decision": "pass" if apply else "plan",
        "operation": "clean-install",
        "transaction_id": transaction_id,
        "active_versions": active,
        "package_store": packages,
        "logs": log_locations(user_home),
    }
    if apply:
        transaction_log(user_home, "clean-install", transaction_id, result)
        append_event(user_home, "clean_install.completed", result, audit=True, correlation_id=transaction_id)
    return result


def install_package(
    user_home: Path,
    package: Path,
    expected_sha256: str,
    *,
    apply: bool = False,
    hosts: tuple[str, ...] = ("claude", "codex", "gemini", "grok"),
    package_store: Path | None = None,
    package_archive: Path | None = None,
    clean_install: bool = True,
) -> dict[str, Any]:
    """Install, verify and clean obsolete active versions transactionally."""
    inspection = inspect_package(
        package,
        expected_sha256,
        allowed_roots=[
            user_home.expanduser().resolve(),
            Path.cwd().resolve(),
            Path.home().resolve(),
            *[
                Path(value).expanduser().resolve()
                for value in (os.environ.get("IOT_AI_ALLOWED_READ_ROOTS") or "").split(os.pathsep)
                if value.strip()
            ],
        ],
    )
    if inspection["decision"] != "pass":
        return inspection
    metadata = inspection["metadata"]
    version = str(metadata["version"])
    python_distribution = str(metadata["python_distribution"])
    python_version = str(metadata["python_version"])
    target = data_root(user_home) / "suite" / version
    wrapper = _wrapper_path(user_home)
    plan = {
        "decision": "plan",
        "operation": "clean-install",
        "version": version,
        "python_distribution": python_distribution,
        "python_version": python_version,
        "package": str(package),
        "sha256": expected_sha256,
        "target": str(target),
        "wrapper": str(wrapper),
        "pep668_safe": True,
        "system_site_packages": False,
        "hosts": list(hosts),
        "clean_install": clean_install,
        "active_cleanup_plan": archive_old_active_versions(
            user_home, version, data_root(user_home) / "update-transactions" / "PLAN", apply=False
        ),
        "package_store_cleanup_plan": clean_package_store(
            (package_store or package.parent),
            package,
            (package_archive or (package_store or package.parent) / ".iot-ai-archive" / "PLAN"),
            apply=False,
        ) if clean_install else None,
        "logs": log_locations(user_home),
    }
    if not apply:
        return plan

    transaction_id = f"update-{uuid.uuid4().hex[:12]}"
    transaction_root = data_root(user_home) / "update-transactions" / transaction_id
    transaction_root.mkdir(parents=True, exist_ok=False)
    prior_update_state = load_json(update_state_path(user_home), {}) or None
    prior_install_state = load_json(install_state_path(user_home), {}) or None
    target_backup: Path | None = None
    activated = False
    active_cleanup: dict[str, Any] = {"decision": "pass", "archived": []}
    package_cleanup: dict[str, Any] = {"decision": "pass", "archived": []}
    transaction_log(user_home, "plan", transaction_id, plan)
    append_event(user_home, "update.started", plan, audit=True, correlation_id=transaction_id)

    with tempfile.TemporaryDirectory(prefix="iot-ai-suite-install-") as temporary:
        extract_root = Path(temporary) / "extract"
        with zipfile.ZipFile(package) as archive:
            for info in archive.infolist():
                if not _safe_name(info.filename) or _is_symlink(info):
                    raise ValueError("unsafe package member")
            archive.extractall(extract_root)

        staging = target.with_name(f".{target.name}.staging-{transaction_id}")
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(extract_root, staging)
        if target.exists():
            target_backup = transaction_root / "previous-target"
            if target_backup.exists():
                shutil.rmtree(target_backup)
            if not _same_device(target, transaction_root):
                raise RuntimeError("target and transaction backup must share a filesystem for atomic rollback")
            os.replace(target, target_backup)
        os.replace(staging, target)
        activated = True

    try:
        # Virtual environments are not relocatable. Create it only after the
        # payload reaches its final versioned target path.
        python_path, _ = _venv_paths(target)
        venv.EnvBuilder(
            with_pip=True,
            clear=True,
            symlinks=False,
            system_site_packages=False,
        ).create(target / "venv")
        wheelhouse = target / "wheels"
        command = [
            str(python_path),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--disable-pip-version-check",
            "--no-input",
            "--force-reinstall",
            "--find-links",
            str(wheelhouse),
            f"{python_distribution}=={python_version}",
        ]
        completed = subprocess.run(
            command,
            cwd=target,
            env=_clean_subprocess_env(),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        atomic_json(
            transaction_root / "wheel-install.json",
            {
                "command_sha256": hashlib.sha256(json.dumps(command).encode()).hexdigest(),
                "exit_code": completed.returncode,
                "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
                "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
            },
        )
        if completed.returncode != 0:
            raise RuntimeError(f"offline wheel installation failed: {completed.stderr[-2000:]}")
    except Exception:
        _restore_target(target, target_backup)
        _restore_update_state(user_home, prior_update_state)
        raise

    _, active_entrypoint = _venv_paths(target)
    if not active_entrypoint.is_file():
        _restore_target(target, target_backup)
        raise RuntimeError("installed entrypoint missing after activation")

    try:
        host_install = subprocess.run(
            [
                str(active_entrypoint),
                "--home",
                str(user_home),
                "package",
                "install",
                "--hosts",
                ",".join(hosts),
                "--apply",
            ],
            cwd=target,
            env=_clean_subprocess_env(),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        atomic_json(
            transaction_root / "host-install.json",
            {
                "exit_code": host_install.returncode,
                "stdout": host_install.stdout[-8000:],
                "stderr": host_install.stderr[-8000:],
            },
        )
        if host_install.returncode != 0:
            raise RuntimeError(f"host-adapter installation failed: {host_install.stderr[-2000:]}")
        checked = verify_host_adapters(user_home)
        if checked.get("decision") != "pass":
            raise RuntimeError(f"host-adapter verification failed: {checked.get('blockers')}")
        if clean_install:
            active_cleanup = archive_old_active_versions(user_home, version, transaction_root, apply=True)
            selected_store = (package_store or package.parent).expanduser().resolve()
            selected_archive = (package_archive or selected_store / ".iot-ai-archive" / transaction_id).expanduser().resolve()
            package_cleanup = clean_package_store(selected_store, package, selected_archive, apply=True)
    except Exception:
        host_rollback = _rollback_partial_host_install(user_home, prior_install_state)
        atomic_json(transaction_root / "failure-host-rollback.json", host_rollback)
        _restore_archived_versions(list(active_cleanup.get("archived") or []))
        _restore_package_store(list(package_cleanup.get("archived") or []))
        _restore_target(target, target_backup)
        _restore_update_state(user_home, prior_update_state)
        append_event(user_home, "update.failed", {"transaction_id": transaction_id}, audit=True, correlation_id=transaction_id)
        raise

    state = {
        "schema": TRANSACTION_SCHEMA,
        "transaction_id": transaction_id,
        "version": version,
        "python_distribution": python_distribution,
        "python_version": python_version,
        "package": str(package),
        "package_sha256": expected_sha256,
        "target": str(target),
        "target_backup": str(target_backup) if target_backup else None,
        "wrapper": str(wrapper),
        "wrapper_sha256": sha256_file(wrapper, allowed_roots=[user_home], max_bytes=None) if wrapper.is_file() else None,
        "prior_update_state": prior_update_state,
        "prior_install_state": prior_install_state,
        "activated_at": utc_now(),
        "rollback_available": True,
        "activated": activated,
        "clean_install": {
            "active_versions": active_cleanup,
            "package_store": package_cleanup,
        },
        "logs": log_locations(user_home),
    }
    atomic_json(update_state_path(user_home), state)
    atomic_json(transaction_root / "receipt.json", state)
    transaction_log(user_home, "result", transaction_id, state)
    append_event(user_home, "update.completed", state, audit=True, correlation_id=transaction_id)
    return {**plan, "decision": "pass", "transaction_id": transaction_id, "activated": True, "clean_install_result": state["clean_install"], "logs": state["logs"]}


def rollback_package(user_home: Path, *, apply: bool = False) -> dict[str, Any]:
    """Restore host adapters, wrapper, Suite target and transaction state."""
    state = load_json(update_state_path(user_home), {}) or {}
    if not state:
        return {"decision": "block", "reason": "no-update-transaction"}
    result = {
        "decision": "plan",
        "transaction_id": state.get("transaction_id"),
        "target": state.get("target"),
        "target_backup": state.get("target_backup"),
        "wrapper": state.get("wrapper"),
    }
    if not apply:
        return result

    adapter_result = rollback_host_adapters(user_home)
    if adapter_result.get("decision") != "pass":
        return {**result, "decision": "block", "reason": "host-adapter-rollback-failed", "details": adapter_result}

    target = Path(str(state["target"]))
    target_backup = Path(str(state["target_backup"])) if state.get("target_backup") else None
    _restore_target(target, target_backup)
    clean_state = state.get("clean_install") or {}
    restored_active = _restore_archived_versions(list((clean_state.get("active_versions") or {}).get("archived") or []))
    restored_packages = _restore_package_store(list((clean_state.get("package_store") or {}).get("archived") or []))
    _restore_update_state(user_home, state.get("prior_update_state"))

    prior_install_state = state.get("prior_install_state")
    current_install_state = load_json(install_state_path(user_home), {}) or None
    if prior_install_state != current_install_state:
        return {
            **result,
            "decision": "block",
            "reason": "install-state-rollback-mismatch",
            "expected_prior_state": bool(prior_install_state),
            "actual_state": bool(current_install_state),
        }
    return {
        **result,
        "decision": "pass",
        "restored_previous_target": bool(target_backup),
        "removed_candidate_target": not target.exists() if not target_backup else False,
        "host_adapter_rollback": adapter_result,
        "restored_active_versions": restored_active,
        "restored_package_store": restored_packages,
        "logs": log_locations(user_home),
    }
