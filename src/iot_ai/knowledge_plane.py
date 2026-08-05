# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
"""Portable, versioned knowledge artifacts; databases remain authoritative."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .paths import customer_knowledge_root, private_knowledge_root, public_knowledge_root
from .privacy import sanitize
from .util import atomic_json, atomic_text, utc_now
from .workspace import connect_write, new_id

_WORD_RE = re.compile(r"[A-Za-z0-9_\-]{3,}")


def root(user_home: Path, visibility: str = "private", tenant_id: str | None = None) -> Path:
    """Return physically separate roots for public, private and customer data."""
    if visibility == "public":
        return public_knowledge_root(user_home)
    if visibility == "private":
        return private_knowledge_root(user_home)
    if visibility == "customer":
        if not tenant_id:
            raise ValueError("customer knowledge requires a tenant_id")
        return customer_knowledge_root(user_home, tenant_id)
    raise ValueError("invalid knowledge visibility")


def _tokens(text: str) -> set[str]:
    return {m.group(0).casefold() for m in _WORD_RE.finditer(text)}


def coverage(goal: str, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    wanted = _tokens(goal)
    if not wanted:
        return {"score": 0.0, "covered": [], "missing": []}
    present: set[str] = set()
    refs: list[str] = []
    for artifact in artifacts:
        present |= _tokens(str(artifact.get("content", "")))
        if artifact.get("artifact_id"):
            refs.append(str(artifact["artifact_id"]))
    covered = sorted(wanted & present)
    missing = sorted(wanted - present)
    return {"score": round(len(covered) / len(wanted), 4), "covered": covered, "missing": missing, "artifact_refs": refs}


def write_artifact(
    user_home: Path,
    *,
    kind: str,
    title: str,
    content: str,
    source_ids: dict[str, str | None],
    visibility: str = "private",
    privacy_class: str = "D1",
    tags: list[str] | None = None,
    valid_until: str | None = None,
    supersedes: str | None = None,
) -> dict[str, Any]:
    result = sanitize(content, "strict")
    if result.decision == "block":
        raise ValueError("knowledge artifact contains blocked secret material")
    clean = result.text
    digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()
    artifact_id = f"ka-{digest[:20]}"
    tenant_id = source_ids.get("tenant_id") if visibility == "customer" else None
    directory = root(user_home, visibility, tenant_id) / kind
    directory.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema": "iot-ai.knowledge-artifact.v1",
        "artifact_id": artifact_id,
        "kind": kind,
        "title": title,
        "source": source_ids,
        "classification": {"privacy": privacy_class, "visibility": visibility},
        "integrity": {"content_sha256": digest, "supersedes": supersedes},
        "lifecycle": {"created_at": utc_now(), "valid_until": valid_until, "status": "active"},
        "rag": {"index_allowed": visibility != "customer", "audiences": ["generic-rag"]},
        "tags": tags or [],
        "redactions": result.findings,
    }
    md = (
        "---\n"
        f"artifact_id: {artifact_id}\n"
        f"kind: {kind}\n"
        f"privacy: {privacy_class}\n"
        f"visibility: {visibility}\n"
        f"content_sha256: {digest}\n"
        "---\n\n"
        f"# {title}\n\n"
        "<!-- UNTRUSTED_KNOWLEDGE_DATA -->\n"
        f"{clean.rstrip()}\n"
        "<!-- END_UNTRUSTED_KNOWLEDGE_DATA -->\n"
    )
    md_path = directory / f"{artifact_id}.md"
    json_path = directory / f"{artifact_id}.json"
    atomic_text(md_path, md, 0o600)
    atomic_json(json_path, metadata)
    connection = connect_write(user_home)
    try:
        connection.execute(
            """INSERT OR REPLACE INTO knowledge_artifact_receipts(
            id,artifact_id,kind,visibility,privacy_class,content_sha256,file_path,source_json,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                new_id("kar"), artifact_id, kind, visibility, privacy_class, digest,
                str(md_path), json.dumps(source_ids, sort_keys=True), "active", metadata["lifecycle"]["created_at"],
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return {**metadata, "markdown_path": str(md_path), "metadata_path": str(json_path), "content": clean}


def list_artifacts(user_home: Path, visibility: str = "private", tenant_id: str | None = None) -> list[dict[str, Any]]:
    base = root(user_home, visibility, tenant_id)
    if not base.exists():
        return []
    result: list[dict[str, Any]] = []
    for metadata_path in sorted(base.rglob("ka-*.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            md_path = metadata_path.with_suffix(".md")
            text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
            metadata["content"] = text
            result.append(metadata)
        except (OSError, json.JSONDecodeError):
            continue
    return result


def write_canvas(user_home: Path, artifact_ids: list[str], edges: list[tuple[str, str]], *, visibility: str = "private", tenant_id: str | None = None) -> dict[str, Any]:
    """Create a JSON Canvas projection. It is never workflow authority."""
    nodes = []
    for index, artifact_id in enumerate(artifact_ids):
        nodes.append({"id": artifact_id, "type": "text", "text": artifact_id, "x": (index % 4) * 320, "y": (index // 4) * 180, "width": 280, "height": 120})
    canvas_edges = [{"id": f"edge-{i}", "fromNode": a, "toNode": b} for i, (a, b) in enumerate(edges, 1)]
    payload = {"nodes": nodes, "edges": canvas_edges, "authority": False, "schema": "iot-ai.canvas-projection.v1"}
    path = root(user_home, visibility, tenant_id) / "canvases" / f"canvas-{hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]}.canvas"
    atomic_json(path, payload)
    return {"decision": "pass", "path": str(path), "nodes": len(nodes), "edges": len(canvas_edges), "authority": False}
