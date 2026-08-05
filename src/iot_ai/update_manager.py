# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
"""Single public update authority; package/index/native managers stay internal."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .installer import status as package_status
from .logging_config import log_locations
from .paths import config_root
from .suite_package import install_package, rollback_package
from .suite_version import MC_GPT_VERSION, SUITE_VERSION
from .util import load_json, utc_now


def index_path(user_home: Path) -> Path:
    return config_root(user_home) / "release-index-v2.json"


def default_index() -> dict[str, Any]:
    return {
        "schema": "iot-ai.release-index.v2",
        "generated_at": utc_now(),
        "channels": {
            "beta": {"available": False, "reason": "no_published_signed_target", "suite": None, "components": {}},
            "stable": {"available": False, "reason": "no_published_signed_target", "suite": None, "components": {}},
        },
    }


def load_index(user_home: Path) -> dict[str, Any]:
    return load_json(index_path(user_home), default_index()) or default_index()


def status(user_home: Path) -> dict[str, Any]:
    return {
        "decision": "pass",
        "installed": {"suite": SUITE_VERSION, "components": {"iot-ai-mc-gpt": MC_GPT_VERSION}},
        "published": load_index(user_home),
        "package": package_status(user_home),
        "authority": "iot-ai update",
        "logs": log_locations(user_home),
        "clean_install_default": True,
        "legacy_aliases": {
            "iot-ai-mc-gpt-update": "deprecated alias to iot-ai update",
            "iot-ai-update-manager": "internal module, not a public command",
        },
    }


def plan(user_home: Path, channel: str = "beta") -> dict[str, Any]:
    row = load_index(user_home).get("channels", {}).get(channel)
    if not row or not row.get("available"):
        return {
            "decision": "block",
            "channel": channel,
            "reason": (row or {}).get("reason", "channel_missing"),
            "message": "No published signed target exists.",
        }
    suite = row.get("suite") or {}
    missing = [field for field in ("version", "url", "sha256", "signature") if not suite.get(field)]
    if missing:
        return {"decision": "block", "reason": "incomplete_signed_target", "missing": missing}
    return {"decision": "plan", "channel": channel, "target": suite}


def apply_local(
    user_home: Path,
    package: Path,
    expected_sha256: str,
    *,
    apply: bool = False,
    package_store: Path | None = None,
    package_archive: Path | None = None,
) -> dict[str, Any]:
    return install_package(
        user_home,
        package,
        expected_sha256,
        apply=apply,
        package_store=package_store,
        package_archive=package_archive,
        clean_install=True,
    )


def rollback(user_home: Path, *, apply: bool = False) -> dict[str, Any]:
    return rollback_package(user_home, apply=apply)
