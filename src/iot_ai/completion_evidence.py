# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
"""Bind local task submission to one run, task contract and tested source.

This is a shared-UID local integrity boundary, not authenticated remote approval
or a sandbox. Old unbound receipts cannot authorize technical completion.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .change_binding import snapshot_tree, tree_digest
from .exec_pin import pin_command
from .test_execution_evidence import execution_binding
from .util import open_secure
from .workspace import one, rows


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def task_authority(task: dict[str, Any]) -> str:
    fields = ("id", "title", "description", "acceptance_criteria", "priority",
              "risk_class", "task_type", "source", "source_id", "duplicate_of", "final_decision")
    return digest({**{key: task.get(key) for key in fields},
                   "tags": task.get("tags", json.loads(task.get("tags_json") or "[]"))})


def work_authority(work: dict[str, Any]) -> str:
    return digest({key: work[key] for key in
                   ("id", "task_id", "title", "role", "read_scope_json", "write_scope_json")})


def freeze(task: dict[str, Any], work: dict[str, Any], run_id: str, lease_id: str,
           implementer: str) -> dict[str, Any]:
    return {**execution_binding(run_id, task), "work_unit_id": work["id"],
            "work_unit_revision": work["revision"], "lease_id": lease_id,
            "task_authority_sha256": task_authority(task), "work_authority_sha256": work_authority(work),
            "implementer": implementer}


def latest_start(conn: Any, task_id: str) -> dict[str, Any] | None:
    row = one(conn, "SELECT * FROM events WHERE task_id=? AND event_type='execution.frozen' ORDER BY seq DESC LIMIT 1", (task_id,))
    return json.loads(row["payload_json"]) if row else None


def ledger_state(conn: Any, task_id: str, run_id: str) -> dict[str, Any]:
    tests = rows(conn, "SELECT * FROM test_results WHERE task_id=? AND run_id=? ORDER BY rowid", (task_id, run_id))
    latest = {row["tier"]: row for row in tests}
    attempts = rows(conn, "SELECT * FROM attempts WHERE task_id=? AND run_id=? ORDER BY rowid", (task_id, run_id))
    contributions = rows(conn, "SELECT * FROM contributions WHERE task_id=? AND run_id=? ORDER BY rowid", (task_id, run_id))
    return {"tests": latest, "attempts_sha256": digest(attempts), "contributions_sha256": digest(contributions)}


def read_artifact(user_home: Path, row: dict[str, Any]) -> Any:
    with open_secure(Path(row["artifact_path"]), allowed_roots=[user_home], max_bytes=4 * 1024 * 1024) as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != row["artifact_sha256"]:
        raise ValueError("completion-artifact-drift")
    return json.loads(raw)


def verify_completion(user_home: Path, conn: Any, task: dict[str, Any], *,
                      transition: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read-only verification on the caller's transaction snapshot."""
    findings: list[str] = []
    run_id = None
    try:
        binding = latest_start(conn, task["id"])
        if not binding:
            raise ValueError("completion-execution-binding-missing")
        run_id = binding["run_id"]
        work = one(conn, "SELECT * FROM work_units WHERE id=? AND task_id=?", (binding["work_unit_id"], task["id"]))
        revision = binding["task_revision"]
        work_revision = binding["work_unit_revision"]
        terminal=False
        if transition is None and task["status"]=="awaiting_founder":
            submitted=one(conn,"SELECT * FROM events WHERE task_id=? AND event_type='task.submitted' ORDER BY seq DESC LIMIT 1",(task["id"],))
            receipt=json.loads(submitted["payload_json"]) if submitted else {}
            if receipt.get("terminal_revision")!=revision+2 or not receipt.get("transition"):
                raise ValueError("completion-terminal-transition-missing")
            transition=receipt["transition"]
            terminal=True
        if transition:
            if (transition.get("run_id") != run_id or transition.get("binding_sha256") != digest(binding)
                or transition.get("source_revision") != revision or transition.get("verification_revision") != revision + 1):
                raise ValueError("completion-transition-invalid")
            event = one(conn, "SELECT * FROM events WHERE task_id=? AND event_type='task.verification_candidate' ORDER BY seq DESC LIMIT 1", (task["id"],))
            if not event or json.loads(event["payload_json"]).get("transition") != transition:
                raise ValueError("completion-transition-unrecorded")
            revision += 1
            work_revision += 1
            if terminal:
                revision+=1
                work_revision+=1
        if (task["revision"] != revision or task_authority(task) != binding["task_authority_sha256"]
            or not work or work["revision"] != work_revision or work_authority(work) != binding["work_authority_sha256"]):
            raise ValueError("completion-task-authority-changed")
        evidence = rows(conn, "SELECT * FROM evidence WHERE task_id=? AND work_unit_id=? ORDER BY rowid", (task["id"], work["id"]))
        current = [row for row in evidence if json.loads(row["metadata_json"]).get("run_id") == run_id]
        envelopes = [row for row in current if row["kind"] == "completion"]
        if not envelopes:
            raise ValueError("completion-envelope-missing")
        envelope = read_artifact(user_home, envelopes[-1])
        if envelope.get("schema") != "iot-ai.completion-evidence.v1" or envelope.get("binding") != binding:
            raise ValueError("completion-envelope-binding-invalid")
        state = ledger_state(conn, task["id"], run_id)
        if state != envelope.get("ledger"):
            raise ValueError("completion-ledger-drift")
        latest_attempt = one(conn, "SELECT run_id FROM attempts WHERE task_id=? ORDER BY rowid DESC LIMIT 1", (task["id"],))
        latest_test = one(conn, "SELECT run_id FROM test_results WHERE task_id=? ORDER BY rowid DESC LIMIT 1", (task["id"],))
        if any(row and row["run_id"] != run_id for row in (latest_attempt, latest_test)):
            raise ValueError("completion-run-superseded")
        tests = state["tests"]
        if not tests or any(row["work_unit_id"] != work["id"] or row["exit_code"] != 0
                            or row["decision"] != "pass" or row["failed"] or row["skipped"] for row in tests.values()):
            raise ValueError("completion-tests-not-passing")
        profile = envelope["test_profile"]
        if digest(profile) != envelope["test_profile_sha256"] or {r["name"] for r in profile} != set(tests):
            raise ValueError("completion-test-profile-invalid")
        for test in tests.values():
            argv = json.loads(test["argv_json"])
            command=next(item for item in profile if item["name"]==test["tier"])
            if digest(argv) != test["command_sha256"] or pin_command(command["argv"])!=argv:
                raise ValueError("completion-command-drift")
            with open_secure(Path(test["output_path"]), allowed_roots=[user_home], max_bytes=4 * 1024 * 1024) as stream:
                if hashlib.sha256(stream.read()).hexdigest() != test["output_sha256"]:
                    raise ValueError("completion-test-output-drift")
        def referenced(key: str, kind: str) -> Any:
            ref = envelope[key]
            row = next((r for r in current if r["id"] == ref["evidence_id"] and r["kind"] == kind), None)
            if not row or row["artifact_sha256"] != ref["artifact_sha256"]:
                raise ValueError("completion-evidence-reference-invalid")
            return read_artifact(user_home, row)
        change = referenced("change_evidence", "change-binding")
        review = referenced("review_evidence", "final-review")
        source = envelope["source_sha256"]
        if (change["decision"] != "pass" or change["post_tree_sha256"] != source
            or change["root"] != envelope["writer_root"] or not change.get("in_scope")):
            raise ValueError("completion-change-binding-invalid")
        results = review["tests"]
        if (not results or {r["test_id"] for r in results} != {r["id"] for r in tests.values()}
            or any(r.get("source_sha256") != source or not r.get("source_stable") for r in results)):
            raise ValueError("completion-tested-source-mismatch")
        reviewers = review["reviews"]
        implementer = binding["implementer"].split("@", 1)[0]
        if (review.get("plan_digest") != envelope["plan_digest"] or not review.get("independent_review_pass")
            or not reviewers or any(not r.get("review", {}).get("accepted")
                or r.get("status")!="pass" or not r.get("substantive")
                or not all(isinstance(r.get(key),str) and r[key].strip() for key in ("provider","model_requested","model_served"))
                or r.get("provider", "").split("@", 1)[0] == implementer for r in reviewers)):
            raise ValueError("completion-independent-review-invalid")
        for reviewer in reviewers:
            contribution=one(conn,"SELECT * FROM contributions WHERE id=? AND task_id=? AND run_id=? AND stage='final-review'",
                             (reviewer.get("contribution_id"),task["id"],run_id))
            if not contribution or any(contribution[key]!=reviewer.get(key) for key in ("status","provider","model_requested","model_served")):
                raise ValueError("completion-review-ledger-mismatch")
        if tree_digest(snapshot_tree(Path(envelope["writer_root"]))) != source:
            raise ValueError("completion-source-drift")
    except (KeyError, TypeError, ValueError, OSError, RuntimeError) as exc:
        # Do not echo source paths, credentials or arbitrary exception text.
        code = str(exc)
        findings.append(code if code.startswith("completion-") and len(code) < 100 else "completion-evidence-invalid")
    return {"decision": "pass" if not findings else "block", "run_id": run_id, "findings": findings,
            "remote_attestation": False}
