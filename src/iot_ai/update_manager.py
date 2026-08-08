# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Single public update authority with safe nested-delivery resolution."""
from __future__ import annotations

import re
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .installer import status as package_status
from .logging_config import log_locations
from .paths import config_root, data_root, update_state_path
from .suite_package import install_package, rollback_package
from .suite_version import MC_GPT_VERSION, SUITE_VERSION
from .util import atomic_json, load_json, sha256_file, trusted_operator_roots, utc_now

_NESTED_ALL_IN_ONE = re.compile(
    r"(?:^|/)(IoT-AI-Tech-iot-ai-Coder-Suite-v[^/]+-ALL-IN-ONE\.zip)$"
)
_MAX_NESTED_PACKAGE_BYTES = 2 * 1024 * 1024 * 1024


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


def _safe_archive_name(name: str) -> bool:
    pure = PurePosixPath(name)
    return (
        bool(name)
        and not pure.is_absolute()
        and ".." not in pure.parts
        and not name.startswith(("/", "\\"))
        and "\\" not in name
        and "\x00" not in name
    )


def _archive_member_is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)


def _parse_sha256_sidecar(text: str, expected_name: str) -> str:
    rows = [line.strip() for line in text.splitlines() if line.strip()]
    if len(rows) != 1:
        raise ValueError("nested package SHA-256 sidecar must contain exactly one record")
    parts = rows[0].split()
    if not parts:
        raise ValueError("nested package SHA-256 sidecar is empty")
    digest = parts[0].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("nested package SHA-256 sidecar has an invalid digest")
    if len(parts) > 1:
        recorded = parts[-1].lstrip("*")
        if PurePosixPath(recorded).name != expected_name:
            raise ValueError("nested package SHA-256 sidecar names a different file")
    return digest


def _persist_nested_update_receipt(user_home: Path, result: dict[str, Any], provenance: dict[str, Any]) -> None:
    transaction_id = str(result.get("transaction_id") or "")
    if not transaction_id:
        return
    state_path = update_state_path(user_home)
    state = load_json(state_path, {}) or {}
    if not state:
        return
    state.update(provenance)
    state["package"] = provenance["input_package"]
    state["package_sha256"] = provenance["outer_sha256"]
    atomic_json(state_path, state)
    receipt = data_root(user_home) / "update-transactions" / transaction_id / "receipt.json"
    if receipt.parent.is_dir():
        atomic_json(receipt, state)


def _apply_nested_delivery(
    user_home: Path,
    package: Path,
    outer_sha256: str,
    *,
    apply: bool,
    package_store: Path | None,
    package_archive: Path | None,
) -> dict[str, Any]:
    with zipfile.ZipFile(package) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("complete delivery contains duplicate ZIP members")
        if any(not _safe_archive_name(name) for name in names):
            raise ValueError("complete delivery contains an unsafe ZIP member")
        if any(_archive_member_is_symlink(info) for info in infos):
            raise ValueError("complete delivery contains a symlink member")
        if any(info.flag_bits & 0x1 for info in infos):
            raise ValueError("encrypted ZIP members are not supported")

        matches = [info for info in infos if _NESTED_ALL_IN_ONE.search(info.filename)]
        if len(matches) != 1:
            raise ValueError(
                "complete delivery must contain exactly one canonical nested ALL-IN-ONE package"
            )
        nested_info = matches[0]
        if nested_info.file_size <= 0 or nested_info.file_size > _MAX_NESTED_PACKAGE_BYTES:
            raise ValueError("nested ALL-IN-ONE package size is invalid")

        nested_name = nested_info.filename
        nested_basename = PurePosixPath(nested_name).name
        sidecar_name = nested_name + ".sha256"
        sidecar_digest: str | None = None
        if sidecar_name in names:
            sidecar_digest = _parse_sha256_sidecar(
                archive.read(sidecar_name).decode("utf-8"),
                nested_basename,
            )

        scratch_root = data_root(user_home) / "update-inputs"
        scratch_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="nested-delivery-", dir=str(scratch_root)) as temporary:
            resolved_package = Path(temporary) / nested_basename
            with archive.open(nested_info, "r") as source, resolved_package.open("wb") as destination:
                copied = 0
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > _MAX_NESTED_PACKAGE_BYTES:
                        raise ValueError("nested ALL-IN-ONE package exceeds the size limit")
                    destination.write(chunk)
            if copied != nested_info.file_size:
                raise ValueError("nested ALL-IN-ONE package extraction size mismatch")

            inner_sha256 = sha256_file(
                resolved_package,
                allowed_roots=[scratch_root],
                max_bytes=None,
            )
            if sidecar_digest and inner_sha256 != sidecar_digest:
                raise ValueError("nested ALL-IN-ONE package SHA-256 mismatch")

            result = install_package(
                user_home,
                resolved_package,
                inner_sha256,
                apply=apply,
                package_store=package_store,
                package_archive=package_archive,
                clean_install=True,
            )

    provenance = {
        "input_package": str(package),
        "resolved_apply_package": nested_name,
        "nested_package": True,
        "outer_sha256": outer_sha256,
        "inner_sha256": inner_sha256,
        "inner_sha256_sidecar_present": sidecar_digest is not None,
        "inner_sha256_sidecar_verified": bool(sidecar_digest),
        "complete_delivery_extracted_members": 1,
    }
    if apply and result.get("decision") == "pass":
        _persist_nested_update_receipt(user_home, result, provenance)
    return {
        **result,
        **provenance,
        "package": str(package),
        "sha256": outer_sha256,
    }


def apply_local(
    user_home: Path,
    package: Path,
    expected_sha256: str,
    *,
    apply: bool = False,
    package_store: Path | None = None,
    package_archive: Path | None = None,
) -> dict[str, Any]:
    """Plan or apply a root ALL-IN-ONE or a complete private delivery.

    Complete deliveries are not unpacked wholesale. The resolver validates the
    outer digest, admits exactly one safe canonical nested ALL-IN-ONE member,
    verifies its optional checksum sidecar, and invokes the normal transactional
    installer on that single payload.
    """
    package = package.expanduser()
    outer_sha256 = sha256_file(
        package,
        allowed_roots=trusted_operator_roots(user_home),
        max_bytes=None,
    )
    if outer_sha256 != expected_sha256.lower():
        raise ValueError("package SHA-256 mismatch")

    try:
        with zipfile.ZipFile(package) as archive:
            root_members = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise ValueError("update input is not a valid ZIP archive") from exc

    if {"PACKAGE_METADATA.json", "MANIFEST.json"}.issubset(root_members):
        result = install_package(
            user_home,
            package,
            outer_sha256,
            apply=apply,
            package_store=package_store,
            package_archive=package_archive,
            clean_install=True,
        )
        return {
            **result,
            "input_package": str(package),
            "resolved_apply_package": str(package),
            "nested_package": False,
            "outer_sha256": outer_sha256,
            "inner_sha256": outer_sha256,
        }

    return _apply_nested_delivery(
        user_home,
        package,
        outer_sha256,
        apply=apply,
        package_store=package_store,
        package_archive=package_archive,
    )


def rollback(user_home: Path, *, apply: bool = False) -> dict[str, Any]:
    return rollback_package(user_home, apply=apply)
