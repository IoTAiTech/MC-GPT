# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-18
"""Bind Multi-Coder completion to one writer worktree, scoped diff and hashes."""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable

from .exec_pin import pin_executable, provider_env
from .util import utc_now
from .worktrees import create as create_worktrees


def _git(repo: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    git = pin_executable("git")
    return subprocess.run(
        [git["path"], "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=provider_env(executable=git["path"]),
    )


def git_root(path: Path) -> Path:
    completed = _git(path, "rev-parse", "--show-toplevel")
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "not-a-git-repository")
    return Path(completed.stdout.strip()).resolve()


def snapshot_tree(repo: Path) -> dict[str, Any]:
    root = git_root(repo)
    head = _git(root, "rev-parse", "HEAD")
    if head.returncode:
        raise RuntimeError(head.stderr.strip() or "missing-git-head")
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    listed = _git(root, "ls-files", "-z")
    files: dict[str, str] = {}
    names = {item for item in listed.stdout.split("\0") if item}
    for current, _dirs, filenames in os.walk(root):
        current_path = Path(current)
        if ".git" in current_path.parts:
            continue
        for filename in filenames:
            candidate = current_path / filename
            if not candidate.is_file() or candidate.is_symlink():
                continue
            rel = str(candidate.relative_to(root)).replace("\\", "/")
            names.add(rel)
    for name in names:
        candidate = (root / name).resolve()
        if not candidate.is_file() or candidate.is_symlink():
            continue
        files[name] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return {
        "schema": "iot-ai.tree-snapshot.v1",
        "root": str(root),
        "head": head.stdout.strip(),
        "dirty": bool(status.stdout.strip()),
        "file_count": len(files),
        "files": files,
        "captured_at": utc_now(),
    }


def _in_scope(relpath: str, write_scope: Iterable[str], root: Path) -> bool:
    target = (root / relpath).resolve()
    for item in write_scope:
        boundary = Path(item).resolve()
        try:
            target.relative_to(boundary)
            return True
        except ValueError:
            continue
    return False


def changed_files(base: dict[str, Any], post: dict[str, Any]) -> list[dict[str, str]]:
    before = dict(base.get("files") or {})
    after = dict(post.get("files") or {})
    names = sorted(set(before) | set(after))
    rows: list[dict[str, str]] = []
    for name in names:
        old = before.get(name)
        new = after.get(name)
        if old == new:
            continue
        action = "modified"
        if old is None:
            action = "added"
        elif new is None:
            action = "deleted"
        rows.append({"path": name, "action": action, "before_sha256": old or "", "after_sha256": new or ""})
    return rows


def bind_post_change(
    *,
    base: dict[str, Any],
    post: dict[str, Any],
    write_scope: Iterable[str],
    mutation_required: bool,
) -> dict[str, Any]:
    root = Path(str(post.get("root") or base.get("root") or ".")).resolve()
    rows = changed_files(base, post)
    in_scope = [row for row in rows if _in_scope(row["path"], write_scope, root)]
    out_of_scope = [row for row in rows if row not in in_scope]
    decision = "pass"
    reason = "scoped-diff-bound"
    if out_of_scope:
        decision = "block"
        reason = "out-of-scope-writes"
    elif mutation_required and not in_scope:
        decision = "block"
        reason = "no-op-rejected"
    return {
        "schema": "iot-ai.change-binding.v1",
        "decision": decision,
        "reason": reason,
        "base_head": base.get("head"),
        "post_head": post.get("head"),
        "base_tree_sha256": hashlib.sha256(
            "".join(f"{k}={v}\n" for k, v in sorted((base.get("files") or {}).items())).encode()
        ).hexdigest(),
        "post_tree_sha256": hashlib.sha256(
            "".join(f"{k}={v}\n" for k, v in sorted((post.get("files") or {}).items())).encode()
        ).hexdigest(),
        "changed_files": rows,
        "in_scope": in_scope,
        "out_of_scope": out_of_scope,
        "mutation_required": mutation_required,
        "write_scope": [str(Path(item).resolve()) for item in write_scope],
    }


def prepare_writer_worktree(
    user_home: Path,
    repo: Path,
    agent: str,
    goal: str,
    *,
    apply: bool = True,
) -> dict[str, Any]:
    try:
        root = git_root(repo)
    except RuntimeError as exc:
        return {"decision": "block", "reason": "worktree-binding-unavailable", "error": str(exc)}
    created = create_worktrees(user_home, root, goal, [agent], apply=apply)
    if not apply:
        return {**created, "decision": created.get("decision", "plan")}
    if created.get("decision") != "pass" or not created.get("workers"):
        return {"decision": "block", "reason": "worktree-create-failed", "plan": created}
    worker = created["workers"][0]
    path = Path(str(worker["path"])).resolve()
    base = snapshot_tree(path)
    return {
        "decision": "pass",
        "reason": "writer-worktree-ready",
        "run_id": created.get("run_id"),
        "path": str(path),
        "branch": worker.get("branch"),
        "agent": worker.get("agent"),
        "base": base,
        "repository": created.get("repository"),
    }
