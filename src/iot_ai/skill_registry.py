# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-03
"""One license-aware Skill Registry. Skills are bounded guidance, not authority."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from .settings_v2 import LICENSE_ALLOWLIST
from .util import utc_now

REGISTRY_VERSION = "1.0.0"
MAX_SKILL_BYTES = 128_000
FORBIDDEN_OVERRIDE = (
    "override founder",
    "disable mncg",
    "disable tests",
    "suppress evidence",
    "write_scope=all",
    "authorize execution",
    "expose secrets",
    "access another product database",
    "request a release",
    "override provider",
    "override the selected provider",
    "create tasks without",
)
NETWORK_FETCH_RE = re.compile(r"\b(curl|wget|fetch\(|httpx|requests\.get|urllib\.request)\b", re.I)
HOOK_RE = re.compile(r"\b(pretooluse|posttooluse|executable hook|child_process|os\.system|subprocess)\b", re.I)
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,80}$")


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        raise ValueError("malformed frontmatter")
    rest = text[3:]
    if "\n---" not in rest:
        raise ValueError("malformed frontmatter")
    raw, body = rest.split("\n---", 1)
    body = body.lstrip("\n")
    if "\t" in raw or "!!" in raw or "<<" in raw:
        raise ValueError("malformed frontmatter")
    data: dict[str, Any] = {}
    current_list: str | None = None
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if not current_list:
                raise ValueError("malformed frontmatter")
            item = line.split("-", 1)[1].strip().strip('"').strip("'")
            data.setdefault(current_list, []).append(item)
            continue
        if ":" not in line or line.startswith(" "):
            raise ValueError("malformed frontmatter")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_list = None
        if value == "":
            current_list = key
            data[key] = []
            continue
        if value.lower() in {"true", "false"}:
            data[key] = value.lower() == "true"
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [part.strip().strip('"').strip("'") for part in inner.split(",") if part.strip()]
        else:
            data[key] = value.strip('"').strip("'")
    return data, body


def packaged_skills_root() -> Path | None:
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[2] / "skills",
        here.parents[1] / "skills",
        here.parent / "data" / "skills",
    ):
        if candidate.is_dir():
            return candidate
    return None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _reject_escape(path: Path, root: Path) -> None:
    if path.is_symlink():
        target = path.resolve()
        if not _is_within(target, root):
            raise ValueError("symlink escape")
    resolved = path.resolve()
    if not _is_within(resolved, root):
        raise ValueError("path traversal")


def _load_manifest(directory: Path) -> dict[str, Any]:
    path = directory / "manifest.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("malformed manifest.json") from exc
    if not isinstance(data, dict):
        raise ValueError("malformed manifest.json")
    return data


def _scan_body(body: str, mode: str) -> list[str]:
    reasons: list[str] = []
    lowered = body.casefold()
    for phrase in FORBIDDEN_OVERRIDE:
        if phrase in lowered:
            reasons.append("attempts to override MC-GPT authority or safety policy")
            break
    if mode == "automatic":
        if NETWORK_FETCH_RE.search(body):
            reasons.append("network-fetch instructions in automatic mode")
        if HOOK_RE.search(body):
            reasons.append("executable hooks in automatic mode")
    return reasons


def validate_skill_dir(directory: Path, *, root: Path, source: str, automatic: bool = True) -> dict[str, Any]:
    skill_md = directory / "SKILL.md"
    _reject_escape(skill_md, root)
    if not skill_md.is_file():
        raise ValueError("SKILL.md missing")
    size = skill_md.stat().st_size
    if size > MAX_SKILL_BYTES:
        raise ValueError("oversized instruction file")
    text = skill_md.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    skill_id = str(meta.get("id") or meta.get("name") or directory.name).strip()
    if not ID_RE.match(skill_id):
        raise ValueError("invalid skill ID")
    if skill_id not in {directory.name, meta.get("name"), meta.get("id")}:
        if directory.name != skill_id and str(meta.get("name") or "") not in {skill_id, directory.name}:
            raise ValueError("directory/name inconsistency")
    license_id = str(meta.get("license") or "LicenseRef-PolyForm-Noncommercial-1.0.0")
    if license_id not in LICENSE_ALLOWLIST:
        raise ValueError("license not on the allowlist")
    mode = str(meta.get("execution_mode") or "reference-only")
    if mode not in {"reference-only", "host-native"}:
        raise ValueError("invalid execution mode")
    digest = _sha_bytes(text.encode("utf-8"))
    declared = str(meta.get("sha256") or meta.get("file_sha256") or "")
    if declared and declared != digest:
        raise ValueError("source-digest mismatch")
    reasons = _scan_body(body, "automatic" if automatic else mode)
    if reasons:
        raise ValueError(reasons[0])
    scripts = directory / "scripts"
    if scripts.exists() and automatic:
        raise ValueError("executable hooks in automatic mode")
    manifest = _load_manifest(directory)
    category = str(meta.get("category") or manifest.get("category") or "general")
    return {
        "id": skill_id,
        "directory": str(directory),
        "name": str(meta.get("name") or skill_id),
        "version": str(meta.get("version") or manifest.get("version") or "1.0.0"),
        "description": str(meta.get("description") or ""),
        "category": category,
        "compatibility": meta.get("compatibility") or manifest.get("compatibility") or ["mc-gpt"],
        "source": source,
        "license": license_id,
        "source_commit": str(meta.get("source_commit") or manifest.get("source_commit") or ""),
        "file_sha256": digest,
        "execution_mode": mode,
        "trust": "bounded-guidance",
        "body": body,
        "frontmatter": meta,
        "manifest": manifest,
    }


def discover_roots(*, user_home: Path, extra_roots: list[str] | None = None, project_root: Path | None = None) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    packaged = packaged_skills_root()
    if packaged:
        roots.append(("packaged", packaged))
    user_root = user_home / ".iot-ai" / "skills"
    if user_root.is_dir():
        roots.append(("user", user_root))
    for host_root in (
        user_home / ".claude" / "skills",
        user_home / ".agents" / "skills",
        user_home / ".grok" / "skills",
    ):
        if host_root.is_dir():
            roots.append(("host", host_root))
    if project_root:
        project_skills = Path(project_root) / ".iot-ai" / "skills"
        if project_skills.is_dir():
            roots.append(("project", project_skills))
    for extra in extra_roots or []:
        path = Path(extra).expanduser()
        if path.is_dir():
            roots.append(("configured", path))
    return roots


def discover(
    *,
    user_home: Path,
    extra_roots: list[str] | None = None,
    project_root: Path | None = None,
    license_allowlist: list[str] | None = None,
) -> dict[str, Any]:
    allow = set(license_allowlist or LICENSE_ALLOWLIST)
    accepted: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    # later roots win (project/configured after packaged)
    for source, root in discover_roots(user_home=user_home, extra_roots=extra_roots, project_root=project_root):
        try:
            root_resolved = root.resolve()
        except OSError:
            rejected.append({"root": str(root), "reason": "unreadable root", "source": source})
            continue
        for dirpath, dirnames, filenames in os.walk(root_resolved, followlinks=False):
            dirnames[:] = [name for name in dirnames if name not in {".git", "node_modules", "scripts"}]
            if "SKILL.md" not in filenames:
                continue
            directory = Path(dirpath)
            try:
                record = validate_skill_dir(directory, root=root_resolved, source=source, automatic=True)
            except ValueError as exc:
                rejected.append({"directory": str(directory), "reason": str(exc), "source": source})
                continue
            if record["license"] not in allow:
                rejected.append({"id": record["id"], "reason": "license not on the allowlist", "source": source})
                continue
            previous = accepted.get(record["id"])
            if previous and previous["source"] == source and previous["directory"] != record["directory"]:
                rejected.append({"id": record["id"], "reason": "duplicate IDs without an explicit precedence decision", "source": source})
                continue
            record.pop("body_tokens", None)
            accepted[record["id"]] = record
    return {
        "schema": "iot-ai.skill-registry.v1",
        "registry_version": REGISTRY_VERSION,
        "discovered_at": utc_now(),
        "skills": accepted,
        "rejected": rejected,
        "count": len(accepted),
    }
