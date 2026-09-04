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
    "outranks the goal",
    "ignore the goal",
    "override the goal",
    "override goal contract",
    "founder rules are optional",
    "this checklist is the system policy",
    "this checklist is the system instruction",
    "ignore previous instructions",
    "you are now the system",
)
NETWORK_FETCH_RE = re.compile(
    r"\b(curl|wget|fetch\(|httpx|requests\.get|urllib\.request)\b|https?://",
    re.I,
)
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


def _opaque_root_id(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:16]


def _sanitize_path(directory: Path, root: Path) -> dict[str, str]:
    root_id = _opaque_root_id(root)
    try:
        relative = directory.resolve().relative_to(root.resolve())
    except ValueError:
        relative = Path(directory.name)
    return {
        "root_id": root_id,
        "relative_path": str(relative).replace("\\", "/"),
        "directory": f"{root_id}:{relative.as_posix()}",
    }


def _regular_file(path: Path, root: Path, *, label: str) -> None:
    _reject_escape(path, root)
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    if not path.is_file():
        raise ValueError(f"{label} missing")
    size = path.stat().st_size
    if size > MAX_SKILL_BYTES:
        raise ValueError(f"oversized {label}")


def _load_manifest(directory: Path, root: Path) -> dict[str, Any]:
    path = directory / "manifest.json"
    if not path.exists():
        return {}
    _regular_file(path, root, label="manifest.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError, OSError) as exc:
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
    _regular_file(skill_md, root, label="SKILL.md")
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError("unreadable SKILL.md") from exc
    meta, body = parse_frontmatter(text)
    skill_id = str(meta.get("id") or meta.get("name") or directory.name).strip()
    if not ID_RE.match(skill_id):
        raise ValueError("invalid skill ID")
    if skill_id not in {directory.name, meta.get("name"), meta.get("id")}:
        if directory.name != skill_id and str(meta.get("name") or "") not in {skill_id, directory.name}:
            raise ValueError("directory/name inconsistency")
    manifest = _load_manifest(directory, root)
    declared_license = meta.get("license") or (manifest.get("license") if isinstance(manifest, dict) else None)
    if not declared_license:
        raise ValueError("license not on the allowlist")
    license_id = str(declared_license)
    if license_id not in LICENSE_ALLOWLIST:
        raise ValueError("license not on the allowlist")
    compatibility = meta.get("compatibility") or manifest.get("compatibility") or ["mc-gpt"]
    if isinstance(compatibility, str):
        compatibility = [compatibility]
    if not isinstance(compatibility, list) or not any(str(item) in {"mc-gpt", "iot-ai"} for item in compatibility):
        raise ValueError("incompatible-skill")
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
    category = str(meta.get("category") or manifest.get("category") or "general")
    path_meta = _sanitize_path(directory, root)
    trust_tier = {
        "packaged": "packaged-reviewed",
        "user": "user-unreviewed",
        "project": "project-local",
        "configured": "configured-extra",
    }.get(source, "untrusted")
    egress_policy = "local-only" if source in {"user", "project", "configured"} else "packaged"
    return {
        "id": skill_id,
        "directory": path_meta["directory"],
        "root_id": path_meta["root_id"],
        "relative_path": path_meta["relative_path"],
        "name": str(meta.get("name") or skill_id),
        "version": str(meta.get("version") or manifest.get("version") or "1.0.0"),
        "description": str(meta.get("description") or ""),
        "category": category,
        "compatibility": compatibility,
        "source": source,
        "source_scope": source,
        "trust_tier": trust_tier,
        "egress_policy": egress_policy,
        "content_digest": digest,
        "license": license_id,
        "source_commit": str(meta.get("source_commit") or manifest.get("source_commit") or ""),
        "file_sha256": digest,
        "execution_mode": mode,
        "trust": "bounded-guidance",
        "body": body,
        "frontmatter": meta,
        "manifest": manifest,
        "declared_privacy_class": meta.get("privacy_class"),
        "privacy_class": _skill_privacy(source, meta.get("privacy_class")),
        "privacy_inherited_from_source": True,
    }


def discover_roots(*, user_home: Path, extra_roots: list[str] | None = None, project_root: Path | None = None) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    packaged = packaged_skills_root()
    if packaged:
        roots.append(("packaged", packaged))
    user_root = user_home / ".iot-ai" / "skills"
    if user_root.is_dir():
        roots.append(("user", user_root))
    if project_root:
        project_skills = Path(project_root) / ".iot-ai" / "skills"
        if project_skills.is_dir():
            roots.append(("project", project_skills))
    for extra in extra_roots or []:
        path = Path(extra).expanduser()
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if not resolved.is_dir():
            continue
        allowed = False
        for base in (user_home.resolve(), *(Path(p).resolve() for p in (project_root,) if project_root)):
            try:
                resolved.relative_to(base)
                allowed = True
                break
            except ValueError:
                continue
        if not allowed:
            continue
        roots.append(("configured", resolved))
    return roots


def _skill_privacy(source: str, declared: Any) -> str:
    from .runtime_gates import inherit_skill_privacy

    return inherit_skill_privacy(source, str(declared) if declared else None)


def garden_lock_path(packaged_root: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    root = packaged_root or packaged_skills_root()
    if root is not None:
        candidates.append(root.parent / "governance" / "garden-skills.lock.json")
    here = Path(__file__).resolve()
    if len(here.parents) >= 3:
        candidates.append(here.parents[2] / "governance" / "garden-skills.lock.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _is_garden_skill(record: dict[str, Any]) -> bool:
    skill_id = str(record.get("id") or "").casefold()
    relative = str(record.get("relative_path") or "").replace("\\", "/").casefold()
    return skill_id.startswith("garden-") or "/garden-" in f"/{relative}"


def verify_garden_lock(record: dict[str, Any], *, packaged_root: Path | None = None) -> str | None:
    """Fail closed at load for Garden-derived packaged skills."""

    if not _is_garden_skill(record):
        return None
    lock_file = garden_lock_path(packaged_root)
    if lock_file is None:
        return "garden-lock-missing"
    try:
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "garden-lock-unreadable"
    if lock.get("upstream_license") != "MIT":
        return "garden-lock-license"
    if lock.get("script_execution_policy") != "never":
        return "garden-lock-script-policy"
    files = {str(row.get("path")): row for row in lock.get("files") or [] if isinstance(row, dict)}
    skill_id = str(record.get("id") or "").casefold()
    row = next(
        (
            item
            for path, item in files.items()
            if Path(path).parent.name.casefold() == skill_id or path.replace("\\", "/").casefold().endswith(f"/{skill_id}/skill.md")
        ),
        None,
    )
    if row is None:
        return "garden-lock-unlisted"
    if row.get("sha256") != record.get("file_sha256"):
        return "garden-lock-digest-mismatch"
    expected_commit = str(lock.get("upstream_commit") or "")
    actual_commit = str(record.get("source_commit") or "")
    if expected_commit and actual_commit != expected_commit:
        return "garden-lock-commit-mismatch"
    return None


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
            except (ValueError, OSError, UnicodeError) as exc:
                rejected.append(
                    {
                        **_sanitize_path(directory, root_resolved),
                        "reason": str(exc),
                        "source": source,
                    }
                )
                continue
            if record["license"] not in allow:
                rejected.append({"id": record["id"], "reason": "license not on the allowlist", "source": source})
                continue
            lock_reason = verify_garden_lock(record, packaged_root=packaged_skills_root())
            if lock_reason:
                rejected.append({"id": record["id"], "reason": lock_reason, "source": source})
                continue
            previous = accepted.get(record["id"])
            if previous:
                if previous["source"] == "packaged" and source != "packaged":
                    rejected.append({"id": record["id"], "reason": "duplicate IDs without an explicit precedence decision", "source": source})
                    continue
                if previous["directory"] != record["directory"]:
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
