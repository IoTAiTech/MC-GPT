# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-06
"""Platform-independent filesystem layout for the unified IOT-AI Suite.

Canonical legal/display vendor is IoT-AI.Tech. Legacy AI-IoT.Tech filesystem
namespaces remain readable for migration only and never receive new writes.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .suite_version import COMPONENT_ID, MC_GPT_VERSION, SUITE_VERSION

# Canonical namespace (new writes)
SUITE_NAMESPACE = "iot-ai-tech/iot-ai-suite/v1"
STATE_NAMESPACE = "iot-ai-tech"
WINDOWS_VENDOR = "IoT-AI.Tech"
WINDOWS_PRODUCT = "IOT-AI-Suite"
WINDOWS_NAMESPACE_VERSION = "v1"

# Legacy namespace (compatibility / migration source only)
LEGACY_SUITE_NAMESPACE = "ai-iot-tech/iot-ai-suite/v1"
LEGACY_STATE_NAMESPACE = "ai-iot-tech"
WINDOWS_VENDOR_LEGACY = "AI-IoT.Tech"

LEGACY_CONFIG_RELATIVE = Path(".config/iot-ai")
LEGACY_DATA_RELATIVE = Path(".local/share/iot-ai")
EXPLICIT_HOME_ENV = "IOT_AI_EXPLICIT_HOME"


def home(explicit: str | None = None) -> Path:
    """Resolve the active user scope and bind explicit ``--home`` safely.

    An explicit Suite home is authoritative over inherited XDG/AppData
    variables.  This prevents one coder session or disposable test HOME from
    reading or rolling back another user's state.
    """
    if explicit:
        resolved = Path(explicit).expanduser().resolve()
        os.environ[EXPLICIT_HOME_ENV] = str(resolved)
        return resolved
    os.environ.pop(EXPLICIT_HOME_ENV, None)
    return Path.home().resolve()


def _explicit_scope(user_home: Path) -> bool:
    marker = os.environ.get(EXPLICIT_HOME_ENV)
    return bool(marker) and Path(marker).expanduser().resolve() == user_home.resolve()


def _xdg_base(user_home: Path, env_name: str, fallback: Path) -> Path:
    if _explicit_scope(user_home):
        return fallback
    process_home = Path.home().resolve()
    if user_home.resolve() == process_home and os.environ.get(env_name):
        return Path(os.environ[env_name]).expanduser().resolve()
    return fallback


def config_root(user_home: Path) -> Path:
    if os.name == "nt":
        use_process_env = not _explicit_scope(user_home) and user_home.resolve() == Path.home().resolve()
        base = Path(os.environ.get("APPDATA", user_home / "AppData" / "Roaming")) if use_process_env else user_home / "AppData" / "Roaming"
        return base / WINDOWS_VENDOR / WINDOWS_PRODUCT / WINDOWS_NAMESPACE_VERSION
    base = _xdg_base(user_home, "XDG_CONFIG_HOME", user_home / ".config")
    return base / SUITE_NAMESPACE


def data_root(user_home: Path) -> Path:
    if os.name == "nt":
        use_process_env = not _explicit_scope(user_home) and user_home.resolve() == Path.home().resolve()
        base = Path(os.environ.get("LOCALAPPDATA", user_home / "AppData" / "Local")) if use_process_env else user_home / "AppData" / "Local"
        return base / WINDOWS_VENDOR / WINDOWS_PRODUCT / WINDOWS_NAMESPACE_VERSION
    base = _xdg_base(user_home, "XDG_DATA_HOME", user_home / ".local" / "share")
    return base / SUITE_NAMESPACE


def component_root(user_home: Path, component_id: str = COMPONENT_ID, version: str = MC_GPT_VERSION) -> Path:
    return data_root(user_home) / "components" / component_id / version


def runtime_root(user_home: Path, version: str = SUITE_VERSION) -> Path:
    return data_root(user_home) / "suite" / version


def state_root(user_home: Path) -> Path:
    return data_root(user_home) / "state"


def legacy_vendor_locations(user_home: Path) -> dict[str, Path]:
    """Return pre-beta.2 vendor filesystem roots (read/migrate only)."""
    if os.name == "nt":
        use_process_env = not _explicit_scope(user_home) and user_home.resolve() == Path.home().resolve()
        appdata = Path(os.environ.get("APPDATA", user_home / "AppData" / "Roaming")) if use_process_env else user_home / "AppData" / "Roaming"
        local = Path(os.environ.get("LOCALAPPDATA", user_home / "AppData" / "Local")) if use_process_env else user_home / "AppData" / "Local"
        return {
            "config": appdata / WINDOWS_VENDOR_LEGACY / WINDOWS_PRODUCT / WINDOWS_NAMESPACE_VERSION,
            "data": local / WINDOWS_VENDOR_LEGACY / WINDOWS_PRODUCT / WINDOWS_NAMESPACE_VERSION,
            "state_logs": local / WINDOWS_VENDOR_LEGACY / WINDOWS_PRODUCT / WINDOWS_NAMESPACE_VERSION / "logs",
        }
    xdg_config = _xdg_base(user_home, "XDG_CONFIG_HOME", user_home / ".config")
    xdg_data = _xdg_base(user_home, "XDG_DATA_HOME", user_home / ".local" / "share")
    xdg_state = _xdg_base(user_home, "XDG_STATE_HOME", user_home / ".local" / "state")
    return {
        "config": xdg_config / LEGACY_SUITE_NAMESPACE,
        "data": xdg_data / LEGACY_SUITE_NAMESPACE,
        "state_logs": xdg_state / LEGACY_STATE_NAMESPACE / "logs",
        "state_root": xdg_state / LEGACY_STATE_NAMESPACE,
    }


def legacy_locations(user_home: Path) -> dict[str, Path]:
    if os.name == "nt":
        use_process_env = not _explicit_scope(user_home) and user_home.resolve() == Path.home().resolve()
        appdata = Path(os.environ.get("APPDATA", user_home / "AppData" / "Roaming")) if use_process_env else user_home / "AppData" / "Roaming"
        local = Path(os.environ.get("LOCALAPPDATA", user_home / "AppData" / "Local")) if use_process_env else user_home / "AppData" / "Local"
        return {
            "config": appdata / "IOT-AI",
            "data": local / "IOT-AI",
            "binary_dir": local / "IOT-AI" / "bin",
        }
    return {
        "config": user_home / LEGACY_CONFIG_RELATIVE,
        "data": user_home / LEGACY_DATA_RELATIVE,
        "binary_dir": user_home / ".local" / "bin",
    }


def settings_path(user_home: Path) -> Path:
    return config_root(user_home) / "settings.json"


def routes_path(user_home: Path) -> Path:
    return config_root(user_home) / "providers.json"


def db_path(user_home: Path) -> Path:
    return state_root(user_home) / "iot-ai-control.sqlite3"


def meetings_root(user_home: Path) -> Path:
    return state_root(user_home) / "meetings"


def receipts_root(user_home: Path) -> Path:
    return state_root(user_home) / "receipts"


def install_state_path(user_home: Path) -> Path:
    return config_root(user_home) / "install-state.json"


def update_state_path(user_home: Path) -> Path:
    return config_root(user_home) / "update-state.json"


def inventory_path(user_home: Path) -> Path:
    return config_root(user_home) / "inventory.json"


def compliance_root(user_home: Path) -> Path:
    """Return the private runtime root for EU AI Act control evidence."""
    return state_root(user_home) / "compliance"


def disclosure_receipts_path(user_home: Path) -> Path:
    return compliance_root(user_home) / "article-50-disclosures.jsonl"


def article5_screens_path(user_home: Path) -> Path:
    return compliance_root(user_home) / "article-5-screens.jsonl"


def literacy_receipts_path(user_home: Path) -> Path:
    return compliance_root(user_home) / "ai-literacy-receipts.jsonl"


def model_dossiers_path(user_home: Path) -> Path:
    return compliance_root(user_home) / "model-supplier-dossiers.json"


def incidents_path(user_home: Path) -> Path:
    return compliance_root(user_home) / "ai-incidents.jsonl"


def compliance_state_path(user_home: Path) -> Path:
    return compliance_root(user_home) / "compliance-state.json"


def public_knowledge_root(user_home: Path) -> Path:
    return data_root(user_home) / "knowledge-public"


def private_knowledge_root(user_home: Path) -> Path:
    return data_root(user_home) / "knowledge-private"


def customer_knowledge_root(user_home: Path, tenant_id: str) -> Path:
    safe = "".join(ch for ch in tenant_id if ch.isalnum() or ch in {"-", "_"})
    if not safe or safe != tenant_id:
        raise ValueError("invalid tenant identifier")
    return data_root(user_home) / "knowledge-customer" / safe


def log_root(user_home: Path) -> Path:
    """Return the platform-native structured log root for this user scope."""
    if os.name == "nt":
        use_process_env = not _explicit_scope(user_home) and user_home.resolve() == Path.home().resolve()
        base = Path(os.environ.get("LOCALAPPDATA", user_home / "AppData" / "Local")) if use_process_env else user_home / "AppData" / "Local"
        return base / WINDOWS_VENDOR / WINDOWS_PRODUCT / WINDOWS_NAMESPACE_VERSION / "logs"
    base = _xdg_base(user_home, "XDG_STATE_HOME", user_home / ".local" / "state")
    return base / STATE_NAMESPACE / "logs"


def transaction_log_root(user_home: Path) -> Path:
    return log_root(user_home) / "transactions"


def diagnostics_log_root(user_home: Path) -> Path:
    return log_root(user_home) / "diagnostics"


def audit_log_path(user_home: Path) -> Path:
    return log_root(user_home) / "audit.jsonl"


def application_log_path(user_home: Path) -> Path:
    return log_root(user_home) / "iot-ai.jsonl"


def _hash_tree(root: Path) -> dict[str, str]:
    inventory: dict[str, str] = {}
    if not root.exists():
        return inventory
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        inventory[rel] = digest
    return inventory


def _copy_tree_preserve(source: Path, destination: Path) -> list[str]:
    copied: list[str] = []
    if not source.exists():
        return copied
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            continue
        rel = path.relative_to(source)
        target = destination / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not path.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            # never overwrite customer data already on canonical path
            continue
        shutil.copy2(path, target)
        copied.append(rel.as_posix())
    return copied


def migrate_vendor_namespace(
    user_home: Path,
    *,
    apply: bool = False,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    """Transactionally migrate legacy AI-IoT.Tech paths to IoT-AI.Tech.

    Dry-run by default. Apply performs backup + atomic directory moves where
    the canonical path is empty, and merge-copy when canonical already has
    content (never clobber). Rollback restores from backup.
    """
    legacy = legacy_vendor_locations(user_home)
    pairs: list[tuple[str, Path, Path]] = [
        ("config", legacy["config"], config_root(user_home)),
        ("data", legacy["data"], data_root(user_home)),
        ("logs", legacy["state_logs"], log_root(user_home)),
    ]
    inventory = {
        name: {
            "legacy": str(src),
            "canonical": str(dst),
            "legacy_exists": src.exists(),
            "canonical_exists": dst.exists(),
            "legacy_file_hashes": _hash_tree(src),
            "canonical_file_hashes": _hash_tree(dst),
        }
        for name, src, dst in pairs
    }
    plan = {
        "schema": "iot-ai.vendor-namespace-migration.v1",
        "suite_version": SUITE_VERSION,
        "decision": "dry-run",
        "apply": False,
        "canonical_windows_vendor": WINDOWS_VENDOR,
        "legacy_windows_vendor": WINDOWS_VENDOR_LEGACY,
        "canonical_linux_state": STATE_NAMESPACE,
        "legacy_linux_state": LEGACY_STATE_NAMESPACE,
        "inventory": inventory,
        "actions": [],
        "backup_root": None,
        "rollback": {"supported": True, "steps": []},
    }
    actions: list[dict[str, Any]] = []
    for name, src, dst in pairs:
        if not src.exists():
            actions.append({"path_class": name, "action": "skip", "reason": "legacy-absent"})
            continue
        if dst.exists() and any(dst.rglob("*")):
            actions.append({
                "path_class": name,
                "action": "merge-copy-missing-only",
                "source": str(src),
                "destination": str(dst),
                "reason": "canonical-already-present",
            })
        else:
            actions.append({
                "path_class": name,
                "action": "atomic-replace-move",
                "source": str(src),
                "destination": str(dst),
            })
    plan["actions"] = actions
    if not apply:
        return plan

    if backup_root is None:
        # Keep backup outside migrated trees (not under legacy or canonical vendor roots).
        backup_root = user_home / ".cache" / "iot-ai-tech" / "vendor-namespace-migration" / "backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    plan["backup_root"] = str(backup_root)
    plan["apply"] = True
    performed: list[dict[str, Any]] = []
    rollback_steps: list[dict[str, str]] = []

    # lock marker prevents dual writers
    lock = backup_root / "MIGRATION_IN_PROGRESS.lock"
    if lock.exists():
        return {**plan, "decision": "block", "error": "migration already in progress"}
    lock.write_text(SUITE_VERSION, encoding="utf-8")
    try:
        for item in actions:
            if item["action"] == "skip":
                performed.append(item)
                continue
            src = Path(item["source"])
            dst = Path(item["destination"])
            bak = backup_root / item["path_class"]
            if bak.exists():
                shutil.rmtree(bak)
            if src.exists():
                shutil.copytree(src, bak, dirs_exist_ok=False)
                rollback_steps.append({"restore_from": str(bak), "restore_to": str(src), "path_class": item["path_class"]})
            if item["action"] == "atomic-replace-move":
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    shutil.rmtree(dst)
                os.replace(src, dst)
                performed.append({**item, "status": "moved"})
            elif item["action"] == "merge-copy-missing-only":
                copied = _copy_tree_preserve(src, dst)
                # leave legacy in place as compatibility-only (do not delete when merge)
                performed.append({**item, "status": "merged", "copied": copied})
        # write receipt
        receipt = {
            "schema": "iot-ai.vendor-namespace-migration-receipt.v1",
            "suite_version": SUITE_VERSION,
            "performed": performed,
            "inventory": inventory,
            "backup_root": str(backup_root),
        }
        (backup_root / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        plan["decision"] = "pass"
        plan["performed"] = performed
        plan["rollback"] = {"supported": True, "steps": rollback_steps, "method": "restore_vendor_namespace_backup"}
        return plan
    except Exception as exc:
        # best-effort rollback of moves already done
        for step in reversed(rollback_steps):
            try:
                src = Path(step["restore_from"])
                dst = Path(step["restore_to"])
                if src.exists() and not dst.exists():
                    os.replace(src, dst)
            except Exception:
                pass
        plan["decision"] = "block"
        plan["error"] = f"{type(exc).__name__}: {exc}"
        return plan
    finally:
        lock.unlink(missing_ok=True)


def restore_vendor_namespace_backup(backup_root: Path) -> dict[str, Any]:
    """Restore legacy path bytes from a migration backup directory."""
    receipt_path = backup_root / "receipt.json"
    if not receipt_path.is_file():
        return {"decision": "block", "error": "backup receipt missing"}
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    restored = []
    for item in receipt.get("performed", []):
        cls = item.get("path_class")
        bak = backup_root / str(cls)
        legacy = Path(str(item.get("source")))
        if not bak.exists():
            continue
        if legacy.exists():
            shutil.rmtree(legacy)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bak, legacy)
        restored.append(str(legacy))
    return {"decision": "pass", "restored": restored, "backup_root": str(backup_root)}
