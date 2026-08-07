# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Worktree-native isolation for governed parallel coder execution.

The implementation borrows the *pattern* of worktree-native parallelism used by
modern agent IDEs, but preserves IOT-AI's stronger role, evidence, privacy and
human-promotion controls.  It never copies untracked files or secrets into a
worker tree, never merges automatically, and never deletes dirty work.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any, Iterable

from .logging_config import append_event, log_locations
from .paths import state_root
from .util import atomic_json, ensure_under, load_json, utc_now

_SCHEMA = "iot-ai.worktree-registry.v1"
_SAFE = re.compile(r"[^a-z0-9._-]+")


def registry_path(user_home: Path) -> Path:
    return state_root(user_home) / "worktrees" / "registry.json"


def managed_root(user_home: Path) -> Path:
    return state_root(user_home) / "worktrees" / "runs"


def _run_git(repo: Path, args: Iterable[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repo), *list(args)]
    environment = dict(__import__("os").environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"): environment.pop(key, None)
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["LC_ALL"] = "C"
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=environment,
    )


def _git(repo: Path, *args: str) -> str:
    completed = _run_git(repo, args)
    if completed.returncode:
        message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise RuntimeError(message)
    return completed.stdout.strip()


def _slug(value: str, *, fallback: str, maximum: int = 48) -> str:
    text = _SAFE.sub("-", value.strip().lower()).strip("-._")
    return (text or fallback)[:maximum].rstrip("-._") or fallback


def _repo_identity(repo: Path) -> dict[str, Any]:
    root_text = _git(repo, "rev-parse", "--show-toplevel")
    root = Path(root_text).resolve()
    head = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "branch", "--show-current") or "detached"
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    return {
        "root": str(root),
        "head": head,
        "branch": branch,
        "dirty": bool(status),
        "status_lines": len(status.splitlines()) if status else 0,
        "repo_id": hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16],
    }


def _load(user_home: Path) -> dict[str, Any]:
    return load_json(registry_path(user_home), {"schema": _SCHEMA, "runs": []}) or {"schema": _SCHEMA, "runs": []}


def _save(user_home: Path, value: dict[str, Any]) -> None:
    value["schema"] = _SCHEMA
    atomic_json(registry_path(user_home), value)


def plan(
    user_home: Path,
    repo: Path,
    goal: str,
    agents: list[str],
    *,
    base_ref: str = "HEAD",
    max_parallel: int = 6,
) -> dict[str, Any]:
    """Create a deterministic, no-write worktree plan."""
    if not agents:
        raise ValueError("at least one agent is required")
    unique_agents = list(dict.fromkeys(_slug(agent, fallback="agent") for agent in agents))
    if len(unique_agents) > max_parallel:
        raise ValueError(f"agent count exceeds max_parallel={max_parallel}")
    identity = _repo_identity(repo.resolve())
    root = Path(identity["root"])
    base_sha = _git(root, "rev-parse", f"{base_ref}^{{commit}}")
    goal_digest = hashlib.sha256(goal.encode("utf-8")).hexdigest()
    task_slug = _slug(goal, fallback=f"task-{goal_digest[:8]}", maximum=36)
    run_id = f"wt-{goal_digest[:10]}-{uuid.uuid4().hex[:6]}"
    run_root = managed_root(user_home) / identity["repo_id"] / run_id
    workers = []
    for agent in unique_agents:
        branch = f"iot-ai/{task_slug}/{agent}-{run_id[-6:]}"
        path = run_root / agent
        workers.append(
            {
                "agent": agent,
                "branch": branch,
                "path": str(path),
                "base_sha": base_sha,
                "status": "planned",
            }
        )
    return {
        "schema": "iot-ai.worktree-plan.v1",
        "decision": "plan",
        "run_id": run_id,
        "goal": goal,
        "goal_sha256": goal_digest,
        "repository": identity,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "workers": workers,
        "tracked_content_only": True,
        "untracked_content_copied": False,
        "automatic_merge": False,
        "human_promotion_required": True,
        "logs": log_locations(user_home),
    }


def create(
    user_home: Path,
    repo: Path,
    goal: str,
    agents: list[str],
    *,
    base_ref: str = "HEAD",
    max_parallel: int = 6,
    apply: bool = False,
) -> dict[str, Any]:
    """Create isolated git worktrees and record a governed run receipt."""
    value = plan(user_home, repo, goal, agents, base_ref=base_ref, max_parallel=max_parallel)
    if not apply:
        return value
    root = Path(value["repository"]["root"])
    created: list[dict[str, Any]] = []
    try:
        for worker in value["workers"]:
            path = ensure_under(Path(worker["path"]), managed_root(user_home))
            if path.exists():
                raise RuntimeError(f"worktree destination already exists: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            completed = _run_git(root, ["worktree", "add", "--no-checkout", "-b", worker["branch"], str(path), value["base_sha"]], timeout=120)
            if completed.returncode:
                raise RuntimeError(completed.stderr.strip() or "git worktree add failed")
            checkout = _run_git(path, ["checkout", "--force"], timeout=120)
            if checkout.returncode:
                raise RuntimeError(checkout.stderr.strip() or "git checkout failed")
            worker["status"] = "ready"
            worker["head"] = _git(path, "rev-parse", "HEAD")
            created.append(worker)
    except Exception:
        for worker in reversed(created):
            _run_git(root, ["worktree", "remove", "--force", worker["path"]], timeout=120)
            _run_git(root, ["branch", "-D", worker["branch"]], timeout=60)
        raise
    value["decision"] = "pass"
    value["created_at"] = utc_now()
    value["status"] = "ready"
    registry = _load(user_home)
    registry.setdefault("runs", []).append(value)
    _save(user_home, registry)
    append_event(user_home, "worktree.run.created", value, audit=True, correlation_id=value["run_id"])
    return value


def _worker_status(worker: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(worker["path"]))
    if not path.is_dir():
        return {**worker, "status": "missing", "dirty": None, "changed_files": []}
    try:
        porcelain = _git(path, "status", "--porcelain=v1", "--untracked-files=all")
        changed = [line[3:] if len(line) > 3 else line for line in porcelain.splitlines()]
        return {
            **worker,
            "status": "dirty" if changed else "clean",
            "dirty": bool(changed),
            "changed_files": changed,
            "head": _git(path, "rev-parse", "HEAD"),
            "commits_ahead": int(_git(path, "rev-list", "--count", f"{worker['base_sha']}..HEAD") or "0"),
        }
    except (RuntimeError, subprocess.SubprocessError) as exc:
        return {**worker, "status": "unreadable", "dirty": None, "changed_files": [], "error": f"{type(exc).__name__}: {exc}"}


def list_runs(user_home: Path) -> dict[str, Any]:
    registry = _load(user_home)
    summaries = []
    for run in registry.get("runs", []):
        workers = [_worker_status(worker) for worker in run.get("workers", [])]
        summaries.append(
            {
                "run_id": run.get("run_id"),
                "goal": run.get("goal"),
                "status": run.get("status"),
                "repository": run.get("repository"),
                "workers": workers,
            }
        )
    return {"schema": _SCHEMA, "decision": "pass", "runs": summaries, "count": len(summaries)}


def show(user_home: Path, run_id: str) -> dict[str, Any]:
    for run in _load(user_home).get("runs", []):
        if run.get("run_id") == run_id:
            return {**run, "decision": "pass", "workers": [_worker_status(worker) for worker in run.get("workers", [])]}
    raise KeyError(f"unknown worktree run: {run_id}")


def promotion_plan(user_home: Path, run_id: str, *, winner: str | None = None) -> dict[str, Any]:
    """Return an evidence-rich human promotion plan; never merge automatically."""
    run = show(user_home, run_id)
    workers = run["workers"]
    if winner:
        workers = [worker for worker in workers if worker.get("agent") == _slug(winner, fallback="agent")]
        if not workers:
            raise KeyError(f"winner is not part of run: {winner}")
    candidates = []
    for worker in workers:
        path = Path(str(worker["path"]))
        diff = _git(path, "diff", "--stat", worker["base_sha"], "HEAD") if path.is_dir() else ""
        candidates.append(
            {
                "agent": worker.get("agent"),
                "branch": worker.get("branch"),
                "path": worker.get("path"),
                "head": worker.get("head"),
                "dirty": worker.get("dirty"),
                "commits_ahead": worker.get("commits_ahead"),
                "diff_stat": diff,
            }
        )
    return {
        "schema": "iot-ai.worktree-promotion-plan.v1",
        "decision": "plan",
        "run_id": run_id,
        "automatic_merge": False,
        "founder_or_reviewer_approval_required": True,
        "candidates": candidates,
        "recommended_flow": ["independent-review", "deterministic-tests", "select-winner", "open-draft-pr", "human-merge"],
    }


def cleanup(user_home: Path, run_id: str, *, apply: bool = False) -> dict[str, Any]:
    """Remove only clean worktrees; dirty or unpushed work is never deleted."""
    registry = _load(user_home)
    run = next((item for item in registry.get("runs", []) if item.get("run_id") == run_id), None)
    if not run:
        raise KeyError(f"unknown worktree run: {run_id}")
    workers = [_worker_status(worker) for worker in run.get("workers", [])]
    blockers = [worker for worker in workers if worker.get("dirty") or int(worker.get("commits_ahead") or 0) > 0]
    result = {
        "schema": "iot-ai.worktree-cleanup.v1",
        "decision": "block" if blockers else "plan",
        "run_id": run_id,
        "blockers": blockers,
        "worktrees": [worker.get("path") for worker in workers],
    }
    if blockers or not apply:
        return result
    root = Path(str(run["repository"]["root"]))
    removed = []
    for worker in workers:
        completed = _run_git(root, ["worktree", "remove", worker["path"]], timeout=120)
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or "git worktree remove failed")
        branch_delete = _run_git(root, ["branch", "-D", worker["branch"]], timeout=60)
        if branch_delete.returncode:
            raise RuntimeError(branch_delete.stderr.strip() or "git branch cleanup failed")
        removed.append(worker["path"])
    run["status"] = "cleaned"
    run["cleaned_at"] = utc_now()
    _save(user_home, registry)
    append_event(user_home, "worktree.run.cleaned", {"run_id": run_id, "removed": removed}, audit=True, correlation_id=run_id)
    return {**result, "decision": "pass", "removed": removed}
