# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Platform-independent filesystem layout for the unified IOT-AI Suite.

The Suite owns a new namespace and observes legacy beta.12 paths without
modifying them unless an explicit migration transaction is authorized.
"""
from __future__ import annotations

import os
from pathlib import Path

from .suite_version import COMPONENT_ID, MC_GPT_VERSION, SUITE_VERSION

SUITE_NAMESPACE = "iot-ai-tech/iot-ai-suite/v1"
WINDOWS_VENDOR = "IoT-AI.Tech"
WINDOWS_PRODUCT = "IOT-AI-Suite"
WINDOWS_NAMESPACE_VERSION = "v1"
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
    return base / SUITE_NAMESPACE / "logs"


def transaction_log_root(user_home: Path) -> Path:
    return log_root(user_home) / "transactions"


def diagnostics_log_root(user_home: Path) -> Path:
    return log_root(user_home) / "diagnostics"


def audit_log_path(user_home: Path) -> Path:
    return log_root(user_home) / "audit.jsonl"


def application_log_path(user_home: Path) -> Path:
    return log_root(user_home) / "iot-ai.jsonl"
