# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Governed Multi-Coder implementation, verification, and audit workflow.

Provider seats are bound to explicit roles and exact served-model receipts.  A
passing command, a long answer, or one positive reviewer never substitutes for
an accepted plan digest and deterministic test closure.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path
from typing import Any

from .change_binding import bind_post_change, prepare_writer_worktree, snapshot_tree
from .eu_ai_act import classify_risk, record_prohibited_practice_screen, screen_prohibited_practices
from .exec_pin import pin_command, test_env
from .licensing import current
from .mesh import delegate
from .owned_delegate import owned_delegate
from .privacy_class import authoritative_privacy_class
from .projection import export_workspace
from .quality import score_response
from .tasks import (
    add_evidence,
    add_work_unit,
    claim_work_unit,
    record_progress,
    release_lease,
    submit_task,
)
from .telemetry import update_quality
from .transparency import record_disclosure, runtime_output_provenance
from .util import atomic_json, atomic_text, sha256_file, utc_now
from .workspace import connect_read, connect_write, evidence_root, new_id, one


def claim_refusal_copy(claim: dict[str, Any], *, created_work_unit: bool) -> tuple[str, str]:
    """Return (reason, remediation) for a claim that has no lease_id."""
    claim_source = str(claim.get("source") or "").casefold()
    claim_status = str(claim.get("status") or "").casefold()
    claim_why = " ".join(
        str(claim.get(key) or "") for key in ("reason", "why", "warning")
    ).casefold()
    skip_bound = (
        claim_status == "skipped"
        or claim_source in {"explicit-risk-acceptance"}
        or "skip" in claim_why
    )
    if created_work_unit and skip_bound:
        return (
            "validation-skip-stale-after-work-unit-creation",
            "This run created the work unit, which bumped the task revision and "
            "invalidated the validation skip bound to the previous revision -- the run "
            "consumed its own authorisation. Re-issue the skip and re-run; the work unit "
            "now exists, so the revision will not move again. To avoid the wasted run "
            "entirely, pre-create the work unit (`iot-ai tasks add-work-unit`) BEFORE "
            "recording the skip.",
        )
    if created_work_unit:
        return (
            str(claim.get("reason") or "task-validation-required-after-work-unit-creation"),
            "This run created the work unit and bumped the task revision, so a "
            "validation that passed at the previous revision no longer matches. "
            "Re-run validation or approval for the current revision. Do not skip "
            "unless you intend to accept the risk. The work unit already exists.",
        )
    return (
        str(claim.get("reason") or "work-unit-claim-refused"),
        "The validation gate refused this claim; resolve the gate decision below "
        "and re-run.",
    )

TEST_TIERS = ("unit", "integration", "smoke", "ab", "stress", "security", "e2e", "quality")
SYNTHESIZER_ORDER = ("codex", "grok", "claude", "gemini", "ollama")


def _seat_parts(seat: str) -> tuple[str, str]:
    value = seat.strip().lower()
    if "@" in value and not value.startswith("agent:"):
        provider, model = value.split("@", 1)
        if provider and model:
            return provider, model
    return value, "auto"


def _substantive(result: dict[str, Any]) -> bool:
    text = str(result.get("output") or "").strip()
    return result.get("status") == "pass" and len(text) >= 30 and bool(result.get("model_served"))


def _safe_delegate(
    user_home: Path,
    seat: str,
    prompt: str,
    stage: str,
    *,
    run_id: str,
    role: str,
    timeout: int,
    effort: str,
    privacy_class: str = "D1",
) -> dict[str, Any]:
    return owned_delegate(
        user_home,
        seat,
        prompt,
        stage,
        run_id=run_id,
        role=role,
        timeout=timeout,
        effort=effort,
        privacy_class=authoritative_privacy_class(privacy_class),
        delegate_fn=delegate,
    )


def _record_attempt(
    user_home: Path,
    task_id: str | None,
    work_unit_id: str | None,
    run_id: str,
    seat: str,
    role: str,
    stage: str,
    result: dict[str, Any],
) -> str:
    attempt_id = new_id("attempt")
    connection = connect_write(user_home)
    try:
        connection.execute(
            """INSERT INTO attempts(
            id,task_id,work_unit_id,run_id,provider,role,stage,status,
            model_requested,model_served,request_or_job_id,auth_route,
            input_tokens,cached_tokens,output_tokens,reasoning_tokens,latency_ms,
            fallback_used,failure_class,retry_after,output_sha256,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                attempt_id,
                task_id,
                work_unit_id,
                run_id,
                seat,
                role,
                stage,
                result.get("status", "failed"),
                result.get("model_requested"),
                result.get("model_served"),
                result.get("request_id"),
                result.get("route_id"),
                result.get("input_tokens"),
                result.get("cached_tokens"),
                result.get("output_tokens"),
                result.get("reasoning_tokens"),
                result.get("latency_ms"),
                int(bool(result.get("fallback_used"))),
                result.get("failure_class"),
                result.get("retry_after"),
                hashlib.sha256(str(result.get("output") or "").encode()).hexdigest(),
                utc_now(),
            ),
        )
        if result.get("contribution_id"):
            connection.execute(
                "UPDATE contributions SET task_id=?,stage=?,role=?,auth_route=? WHERE id=?",
                (task_id, stage, role, result.get("route_id"), result["contribution_id"]),
            )
        connection.commit()
        return attempt_id
    finally:
        connection.close()


def _quality(user_home: Path, prompt: str, result: dict[str, Any], peers: list[str]) -> dict[str, Any] | None:
    if result.get("status") != "pass":
        return None
    quality = score_response(prompt, str(result.get("output") or ""), peers)
    if result.get("contribution_id"):
        update_quality(user_home, result["contribution_id"], quality)
    return quality


def _provider_entry(seat: str, result: dict[str, Any], quality: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "seat_id": seat,
        "provider": result.get("provider") or _seat_parts(seat)[0],
        "status": result.get("status"),
        "text": result.get("output", ""),
        "request_or_job_id": result.get("request_id"),
        "route_id": result.get("route_id"),
        "model_requested": result.get("model_requested"),
        "model_served": result.get("model_served"),
        "tokens": {
            "input": result.get("input_tokens"),
            "cached": result.get("cached_tokens"),
            "output": result.get("output_tokens"),
            "reasoning": result.get("reasoning_tokens"),
        },
        "latency_ms": result.get("latency_ms"),
        "fallback_used": bool(result.get("fallback_used")),
        "failure_class": result.get("failure_class"),
        "substantive": _substantive(result),
        "quality": quality,
    }


def _load_profile(path: Path | None, test_argv: list[str] | None) -> list[dict[str, Any]]:
    if path:
        value = json.loads(path.read_text(encoding="utf-8"))
        tiers = value.get("tiers") if isinstance(value, dict) else None
        if not isinstance(tiers, list) or not tiers:
            raise ValueError("test profile must contain a non-empty tiers list")
        result = []
        for item in tiers:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("name"), str)
                or not isinstance(item.get("argv"), list)
                or not all(isinstance(value, str) for value in item["argv"])
            ):
                raise ValueError("invalid test profile tier")
            result.append(
                {
                    "name": item["name"],
                    "argv": item["argv"],
                    "timeout": int(item.get("timeout_seconds", 900)),
                }
            )
        return result
    if test_argv:
        return [{"name": "unit", "argv": test_argv, "timeout": 900}]
    return []


def _parse_counts(output: str, exit_code: int) -> tuple[int, int, int]:
    passed = failed = skipped = 0
    for pattern, target in ((r"(\d+) passed", "p"), (r"(\d+) failed", "f"), (r"(\d+) skipped", "s")):
        match = re.search(pattern, output)
        if match:
            if target == "p":
                passed = int(match.group(1))
            elif target == "f":
                failed = int(match.group(1))
            else:
                skipped = int(match.group(1))
    if passed == failed == skipped == 0:
        passed = 1 if exit_code == 0 else 0
        failed = 0 if exit_code == 0 else 1
    return passed, failed, skipped


def _run_tests(
    user_home: Path,
    task_id: str | None,
    work_unit_id: str | None,
    run_id: str,
    tiers: list[dict[str, Any]],
    cwd: Path,
) -> list[dict[str, Any]]:
    results = []
    root = evidence_root(user_home) / (task_id or run_id) / run_id
    root.mkdir(parents=True, exist_ok=True)
    for tier in tiers:
        argv = pin_command(list(tier["argv"]))
        started = time.monotonic()
        try:
            process = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=tier["timeout"],
                check=False,
                env=test_env(extra_path_dirs=[Path(argv[0]).parent]),
            )
            exit_code = process.returncode
            output = (process.stdout or "") + ("\n" + process.stderr if process.stderr else "")
            decision = "pass" if exit_code == 0 else "fail"
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            output = stdout + stderr
            decision = "fail"
        duration = int((time.monotonic() - started) * 1000)
        passed, failed, skipped = _parse_counts(output, exit_code)
        path = root / f"test-{tier['name']}.log"
        atomic_text(path, output, 0o600)
        digest = sha256_file(path, allowed_roots=[user_home, root])
        test_id = new_id("test")
        if task_id:
            connection = connect_write(user_home)
            connection.execute(
                "INSERT INTO test_results VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    test_id,
                    task_id,
                    work_unit_id,
                    run_id,
                    tier["name"],
                    json.dumps(argv),
                    hashlib.sha256(json.dumps(argv, separators=(",", ":")).encode()).hexdigest(),
                    exit_code,
                    passed,
                    failed,
                    skipped,
                    duration,
                    str(path),
                    digest,
                    decision,
                    utc_now(),
                ),
            )
            connection.commit()
            connection.close()
            add_evidence(
                user_home,
                task_id,
                path,
                digest,
                "test",
                work_unit_id,
                argv,
                exit_code,
                decision == "pass",
                {"tier": tier["name"], "passed": passed, "failed": failed, "skipped": skipped},
            )
        results.append(
            {
                "test_id": test_id,
                "tier": tier["name"],
                "argv": argv,
                "exit_code": exit_code,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "duration_ms": duration,
                "decision": decision,
                "output": str(path),
                "sha256": digest,
            }
        )
    return results


def _write_evidence(
    user_home: Path,
    task_id: str | None,
    work_unit_id: str | None,
    run_id: str,
    name: str,
    value: Any,
) -> dict[str, Any]:
    root = evidence_root(user_home) / (task_id or run_id) / run_id
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}.json"
    atomic_json(path, value)
    if task_id:
        return add_evidence(
            user_home,
            task_id,
            path,
            sha256_file(path, allowed_roots=[user_home]),
            name,
            work_unit_id,
            metadata={
                "run_id": run_id,
                "decision": value.get("decision") if isinstance(value, dict) else None,
                "reason": value.get("reason") if isinstance(value, dict) else None,
            },
        )
    return {"artifact": str(path), "artifact_sha256": sha256_file(path, allowed_roots=[user_home])}


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json|yaml)?\s*", "", stripped, flags=re.I)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.S)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


def _review_acceptance(text: str, expected_digest: str) -> dict[str, Any]:
    parsed = _extract_json(text)
    decision = str(parsed.get("decision") or "").casefold()
    digest = str(parsed.get("plan_digest") or "")
    accepted = decision in {"accept", "approve", "pass"} and digest == expected_digest
    return {
        "decision": decision or "unparseable",
        "plan_digest": digest or None,
        "accepted": accepted,
        "findings": parsed.get("findings") or [],
        "dissent": parsed.get("dissent") or [],
    }


def run(
    user_home: Path,
    task: str | None = None,
    providers: list[str] | None = None,
    quorum: int = 2,
    test_argv: list[str] | None = None,
    cwd: Path | None = None,
    *,
    task_id: str | None = None,
    implementer: str | None = None,
    test_profile: Path | None = None,
    risk_class: str = "R2",
    effort: str = "high",
    max_repair_rounds: int | None = None,
    privacy_class: str = "D1",
    mutation_required: bool = True,
) -> dict[str, Any]:
    seats = list(dict.fromkeys(providers or ["claude", "codex", "gemini", "ollama@auto:cloud"]))
    entitlement = current()
    if len(seats) > entitlement.max_providers:
        raise PermissionError(f"{entitlement.edition} edition supports at most {entitlement.max_providers} providers")
    if quorum < 1 or quorum > len(seats):
        raise ValueError("invalid quorum")
    cwd = (cwd or Path.cwd()).resolve()
    privacy_class = authoritative_privacy_class(privacy_class)
    delegate_turn = partial(_safe_delegate, privacy_class=privacy_class)
    tiers = _load_profile(test_profile, test_argv)
    run_id = new_id("run")
    work_unit_id = lease_id = lease_token = None
    task_text = task or ""
    task_row: dict[str, Any] | None = None
    existing_work_unit: dict[str, Any] | None = None

    if task_id:
        connection = connect_read(user_home)
        if connection is None:
            raise ValueError("Task not found")
        task_row = one(connection, "SELECT * FROM tasks WHERE id=?", (task_id,))
        existing_work_unit = one(
            connection,
            "SELECT * FROM work_units WHERE task_id=? AND status IN ('ready','claimed','active') ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        )
        connection.close()
        if not task_row:
            raise ValueError("Task not found")
        from .task_validation import gate as validation_gate
        validation = validation_gate(user_home, task_id, "execute")
        if validation.get("decision") != "pass":
            return {
                "schema": "iot-ai.multi-coder-result.v4",
                "run_id": run_id,
                "task_id": task_id,
                "decision": "requires-user-confirmation",
                "reason": "task-validation-required",
                "task_validation": validation,
                "provider_calls": 0,
                "execution_authorized": False,
            }
        task_text = task_row["description"] or task_row["title"]

    if not task_text.strip():
        raise ValueError("task or task_id is required")

    article5 = screen_prohibited_practices(task_text)
    record_prohibited_practice_screen(user_home, task_text, context="multi-coder-run")
    disclosure = record_disclosure(user_home, surface="multi-coder", language="en")
    if article5.decision == "block":
        return {
            "schema": "iot-ai.multi-coder-result.v3",
            "run_id": run_id,
            "task_id": task_id,
            "decision": "blocked",
            "reason": "eu-ai-act-article-5-prohibited-practice",
            "article_5": article5.to_dict(),
            "provider_calls": 0,
            "execution_authorized": False,
            "global_compliance_claim_allowed": False,
        }
    article6 = classify_risk(task_text)
    if article6.get("decision") == "high-risk-candidate":
        return {
            "schema": "iot-ai.multi-coder-result.v3",
            "run_id": run_id,
            "task_id": task_id,
            "decision": "blocked",
            "reason": "high-risk-deployment-classification-required",
            "article_5": article5.to_dict(),
            "article_6": article6,
            "provider_calls": 0,
            "execution_authorized": False,
            "global_compliance_claim_allowed": False,
        }

    if task_id and task_row:
        # Recorded BEFORE the create, so the refusal path below can tell the operator
        # whether this run is what moved the task revision.
        existing_work_unit_preexisted = existing_work_unit is not None
        if not existing_work_unit:
            existing_work_unit = add_work_unit(
                user_home,
                task_id,
                f"Implementation: {task_row['title']}",
                "implementation",
                read_scope=[str(cwd)],
                write_scope=[str(cwd)],
            )
            work_unit_id = existing_work_unit["work_unit_id"]
        else:
            work_unit_id = existing_work_unit["id"]
        implementer = implementer or seats[0]
        claim = claim_work_unit(user_home, work_unit_id, implementer, f"{implementer}-{run_id}", 7200, enforce_validation=True, trigger_action="execute")
        # claim_work_unit returns the VALIDATION GATE dict (no lease_id) whenever the gate
        # does not pass -- tasks.py: `if validation.get("decision") != "pass": return validation`.
        # Reading claim["lease_id"] blindly turned every gate refusal into a bare
        # `KeyError: 'lease_id'`, which surfaced to the operator as `error: 'lease_id'` and
        # hid the real, actionable reason (e.g. a stale revision-bound validation skip).
        # Propagate the gate's own decision instead of masking it.
        if "lease_id" not in claim:
            # SELF-REVIEW FINDING (2026-08-13): `add_work_unit` above runs BEFORE this
            # claim and does `UPDATE tasks SET revision=revision+1` (tasks.py:145). So on
            # a FIRST run the work unit is created, the revision moves, and a validation
            # skip recorded against the previous revision is invalidated by the very run
            # it was authorising -- the gate then refuses and we land here. The work unit
            # is NOT orphaned (the next run finds it via `existing_work_unit` and does not
            # bump the revision again), so a re-issued skip succeeds. Report that
            # precisely rather than leaving the operator to rediscover it.
            created_wu = not existing_work_unit_preexisted
            reason, remediation = claim_refusal_copy(claim, created_work_unit=created_wu)
            return {
                "schema": "iot-ai.multi-coder-result.v3",
                "run_id": run_id,
                "task_id": task_id,
                "work_unit_id": work_unit_id,
                "decision": claim.get("decision", "requires-user-confirmation"),
                "reason": reason,
                "work_unit_created_this_run": created_wu,
                "remediation": remediation,
                "task_validation": claim,
                "provider_calls": 0,
                "execution_authorized": False,
                "global_compliance_claim_allowed": False,
            }
        lease_id = claim["lease_id"]
        lease_token = claim["lease_token"]
        record_progress(user_home, task_id, "planning", 10, "Multi-Coder planning started", work_unit_id, basis="manual-estimate", confidence="medium")

    implementer = implementer or seats[0]
    max_repairs = max_repair_rounds if max_repair_rounds is not None else (
        1 if risk_class in {"R0", "R1"} else 2 if risk_class == "R2" else 3
    )

    plan_prompt = (
        "Produce an independent implementation plan under the immutable specialist role contract. "
        "Include scope, dependencies, interfaces, security and privacy risks, EU AI Act Article 5/50 implications, "
        "deterministic tests, rollback and missing evidence. Do not authorize implementation.\nTASK:\n"
        + task_text
    )
    raw: list[tuple[str, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=min(8, len(seats))) as pool:
        futures = {
            pool.submit(
                delegate_turn,
                user_home,
                seat,
                plan_prompt,
                "plan",
                run_id=run_id,
                role="specialist-planner",
                timeout=900,
                effort=effort,
            ): seat
            for seat in seats
        }
        for future in as_completed(futures):
            raw.append((futures[future], future.result()))

    peer_outputs = [str(result.get("output") or "") for _, result in raw if _substantive(result)]
    plans = []
    for seat, result in raw:
        quality = _quality(user_home, task_text, result, [value for value in peer_outputs if value != result.get("output")])
        plans.append(_provider_entry(seat, result, quality))
        if task_id:
            _record_attempt(user_home, task_id, work_unit_id, run_id, seat, "specialist-planner", "plan", result)
    good = [entry for entry in plans if entry["substantive"]]
    unsatisfied_seats = [entry["seat_id"] for entry in plans if not entry["substantive"]]
    # Every explicitly selected seat is required by default. Quorum is a minimum
    # safety floor, never permission to silently discard configured coder/model
    # seats and call the remainder "Multi-Coder consensus".
    if len(good) < quorum or unsatisfied_seats:
        if lease_id and lease_token:
            release_lease(user_home, lease_id, lease_token, "required-seat-coverage-unsatisfied")
        return {
            "schema": "iot-ai.multi-coder-result.v4",
            "run_id": run_id,
            "task_id": task_id,
            "decision": "blocked",
            "reason": "required-seat-coverage-unsatisfied" if unsatisfied_seats else "insufficient-substantive-quorum",
            "requested_seats": seats,
            "substantive_seats": [entry["seat_id"] for entry in good],
            "unsatisfied_seats": unsatisfied_seats,
            "plans": plans,
            "article_5": article5.to_dict(),
            "article_6": article6,
            "article_50": disclosure,
            "provider_calls": len(plans),
            "execution_authorized": False,
            "global_compliance_claim_allowed": False,
        }

    bundle = "\n\n".join(f"[{entry['seat_id']}] {entry['text']}" for entry in good)
    critiques = []
    critique_raw: list[tuple[str, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=min(8, len(good))) as pool:
        futures = {
            pool.submit(
                delegate_turn,
                user_home,
                entry["seat_id"],
                "Blind-critique the plans. Find conflicts, unsupported assumptions, missing tests, security/privacy/legal risks, and duplicated work.\n" + bundle,
                "plan-critique",
                run_id=run_id,
                role="independent-critic",
                timeout=900,
                effort=effort,
            ): entry["seat_id"]
            for entry in good
        }
        for future in as_completed(futures):
            critique_raw.append((futures[future], future.result()))
    for seat, result in critique_raw:
        quality = _quality(user_home, bundle, result, [])
        critiques.append(_provider_entry(seat, result, quality))
        if task_id:
            _record_attempt(user_home, task_id, work_unit_id, run_id, seat, "independent-critic", "plan-critique", result)

    good_seat_ids = [entry["seat_id"] for entry in good]
    synthesis_seat = next(
        (
            entry["seat_id"]
            for provider in SYNTHESIZER_ORDER
            for entry in good
            if _seat_parts(entry["seat_id"])[0] == provider
        ),
        sorted(good_seat_ids)[0],
    )
    synthesis_prompt = (
        "Synthesize one final executable plan from the independent plans and critiques. Preserve blockers, dissent, "
        "missing evidence, Article 5/50 controls, deterministic acceptance and rollback. Return a complete plan, not a status update.\n"
        f"PLANS\n{bundle}\nCRITIQUES\n"
        + "\n".join(entry["text"] for entry in critiques if entry["substantive"])
    )
    synthesis = delegate_turn(
        user_home,
        synthesis_seat,
        synthesis_prompt,
        "plan-synthesis",
        run_id=run_id,
        role="plan-synthesizer",
        timeout=1200,
        effort="xhigh" if effort == "xhigh" else "high",
    )
    if task_id:
        _record_attempt(user_home, task_id, work_unit_id, run_id, synthesis_seat, "plan-synthesizer", "plan-synthesis", synthesis)
    synthesis_text = str(synthesis.get("output") or "").strip()
    plan_digest = hashlib.sha256(synthesis_text.encode()).hexdigest() if _substantive(synthesis) else None

    plan_reviews: list[dict[str, Any]] = []
    if plan_digest:
        review_prompt = (
            "Review the frozen plan independently. Return JSON only with decision, plan_digest, findings, dissent. "
            "Accept only this exact digest if it is complete, safe, evidence-bound, testable and in scope.\n"
            f"PLAN_DIGEST:{plan_digest}\nPLAN:\n{synthesis_text}"
        )
        review_raw: list[tuple[str, dict[str, Any]]] = []
        with ThreadPoolExecutor(max_workers=min(8, len(good))) as pool:
            futures = {
                pool.submit(
                    delegate_turn,
                    user_home,
                    entry["seat_id"],
                    review_prompt,
                    "plan-final-review",
                    run_id=run_id,
                    role="independent-judge",
                    timeout=900,
                    effort=effort,
                ): entry["seat_id"]
                for entry in good
            }
            for future in as_completed(futures):
                review_raw.append((futures[future], future.result()))
        for seat, result in review_raw:
            parsed = _review_acceptance(str(result.get("output") or ""), plan_digest)
            entry = _provider_entry(seat, result, _quality(user_home, review_prompt, result, []))
            entry["review"] = parsed
            plan_reviews.append(entry)
            if task_id:
                _record_attempt(user_home, task_id, work_unit_id, run_id, seat, "independent-judge", "plan-final-review", result)

    required_plan_acceptance = (
        bool(plan_digest)
        and len(plan_reviews) == len(good)
        and all(entry["review"]["accepted"] for entry in plan_reviews)
    )
    planning_evidence = {
        "plans": plans,
        "critiques": critiques,
        "synthesis": synthesis,
        "plan_digest": plan_digest,
        "plan_reviews": plan_reviews,
        "plan_accepted": required_plan_acceptance,
    }
    _write_evidence(user_home, task_id, work_unit_id, run_id, "planning", planning_evidence)
    if not required_plan_acceptance:
        if lease_id and lease_token:
            release_lease(user_home, lease_id, lease_token, "plan-not-accepted")
        export_workspace(user_home, task_id=task_id)
        return {
            "schema": "iot-ai.multi-coder-result.v3",
            "run_id": run_id,
            "task_id": task_id,
            "decision": "needs-work",
            "reason": "required-seats-did-not-accept-same-plan-digest",
            **planning_evidence,
            "article_5": article5.to_dict(),
            "article_6": article6,
            "article_50": disclosure,
            "execution_authorized": False,
            "global_compliance_claim_allowed": False,
        }

    if task_id:
        record_progress(user_home, task_id, "implementation", 35, "Digest-bound plan accepted; implementation started", work_unit_id, basis="manual-estimate", confidence="medium")
    writer = prepare_writer_worktree(
        user_home,
        cwd,
        _seat_parts(implementer)[0],
        f"{run_id}:{plan_digest}",
        apply=True,
    )
    if writer.get("decision") != "pass":
        if lease_id and lease_token:
            release_lease(user_home, lease_id, lease_token, str(writer.get("reason") or "worktree-binding-unavailable"))
        return {
            "schema": "iot-ai.multi-coder-result.v4",
            "run_id": run_id,
            "task_id": task_id,
            "decision": "blocked",
            "reason": writer.get("reason") or "worktree-binding-unavailable",
            "change_binding": writer,
            "plan_digest": plan_digest,
            "provider_calls": len(plans),
            "execution_authorized": False,
            "global_compliance_claim_allowed": False,
        }
    worktree_path = Path(str(writer["path"]))
    write_scope = [str(worktree_path)]
    implementation = delegate_turn(
        user_home,
        implementer,
        "Implement only the frozen plan in the exact writer worktree. Do not modify unrelated files. Preserve public/private boundaries.\n"
        f"TASK:{task_text}\nPLAN_DIGEST:{plan_digest}\nWORKTREE_PATH:{worktree_path}\nWRITE_SCOPE:{worktree_path}\nPLAN:{synthesis_text}",
        "implementation",
        run_id=run_id,
        role="implementation-engineer",
        timeout=1800,
        effort=effort,
    )
    if task_id:
        _record_attempt(user_home, task_id, work_unit_id, run_id, implementer, "implementation-engineer", "implementation", implementation)
    _write_evidence(user_home, task_id, work_unit_id, run_id, "implementation", implementation)

    results = _run_tests(user_home, task_id, work_unit_id, run_id, tiers, worktree_path) if tiers else []
    repair_round = 0
    seen_failures: set[tuple[Any, ...]] = set()
    while results and any(result["decision"] != "pass" for result in results) and repair_round < max_repairs:
        failure_tuple = tuple(
            (result["tier"], result["exit_code"], result["sha256"])
            for result in results
            if result["decision"] != "pass"
        )
        if failure_tuple in seen_failures:
            break
        seen_failures.add(failure_tuple)
        repair_round += 1
        failure_text = json.dumps([result for result in results if result["decision"] != "pass"], ensure_ascii=False)
        failure_reviews = []
        for entry in good:
            seat = entry["seat_id"]
            result = delegate_turn(
                user_home,
                seat,
                f"Diagnose deterministic failures and propose the smallest coherent repair.\nTASK:{task_text}\nFAILURES:{failure_text}",
                "failure-review",
                run_id=run_id,
                role="failure-reviewer",
                timeout=900,
                effort=effort,
            )
            failure_reviews.append(_provider_entry(seat, result, _quality(user_home, failure_text, result, [])))
            if task_id:
                _record_attempt(user_home, task_id, work_unit_id, run_id, seat, "failure-reviewer", "failure-review", result)
        repair = delegate_turn(
            user_home,
            implementer,
            "Apply one bounded repair. Do not expand scope.\n"
            f"FAILURES:{failure_text}\nREVIEWS:{json.dumps(failure_reviews, ensure_ascii=False)}",
            "repair",
            run_id=run_id,
            role="implementation-engineer",
            timeout=1800,
            effort=effort,
        )
        if task_id:
            _record_attempt(user_home, task_id, work_unit_id, run_id, implementer, "implementation-engineer", "repair", repair)
        results = _run_tests(user_home, task_id, work_unit_id, run_id, tiers, worktree_path)

    post_tree = snapshot_tree(worktree_path)
    change_binding = bind_post_change(
        base=writer["base"],
        post=post_tree,
        write_scope=write_scope,
        mutation_required=mutation_required,
    )
    _write_evidence(user_home, task_id, work_unit_id, run_id, "change-binding", change_binding)
    tests_pass = bool(results) and all(result["decision"] == "pass" for result in results)
    if not tiers:
        tests_pass = False
    if change_binding.get("decision") != "pass":
        tests_pass = False
    if task_id:
        record_progress(
            user_home,
            task_id,
            "verify",
            80,
            "Deterministic tests complete" if tests_pass else "Deterministic tests absent or failing",
            work_unit_id,
            basis="deterministic-tests",
            evidence_ids=[str(row.get("test_id")) for row in results if row.get("test_id")],
            confidence="high" if tests_pass else "low",
        )

    final_reviews = []
    if tests_pass and _substantive(implementation):
        packet = (
            f"TASK:{task_text}\nPLAN_DIGEST:{plan_digest}\nPLAN:{synthesis_text}\n"
            f"IMPLEMENTATION:{implementation.get('output', '')}\nTESTS:{json.dumps(results, ensure_ascii=False)}\n"
            f"CHANGE_BINDING:{json.dumps(change_binding, ensure_ascii=False)}"
        )
        reviewer_seats = [entry["seat_id"] for entry in good if entry["seat_id"] != implementer]
        for seat in reviewer_seats:
            result = delegate_turn(
                user_home,
                seat,
                "Independently review the final result. Return JSON only with decision, plan_digest, findings, dissent. "
                "Accept only when implementation matches the frozen digest and deterministic evidence passes.\n" + packet,
                "final-review",
                run_id=run_id,
                role="independent-judge",
                timeout=1200,
                effort=effort,
            )
            entry = _provider_entry(seat, result, _quality(user_home, packet, result, []))
            entry["review"] = _review_acceptance(str(result.get("output") or ""), str(plan_digest))
            final_reviews.append(entry)
            if task_id:
                _record_attempt(user_home, task_id, work_unit_id, run_id, seat, "independent-judge", "final-review", result)

    independent_review_pass = bool(final_reviews) and all(entry["review"]["accepted"] for entry in final_reviews)
    _write_evidence(
        user_home,
        task_id,
        work_unit_id,
        run_id,
        "final-review",
        {
            "reviews": final_reviews,
            "tests": results,
            "repair_rounds": repair_round,
            "plan_digest": plan_digest,
            "independent_review_pass": independent_review_pass,
        },
    )

    decision = "approve" if tests_pass and independent_review_pass else "needs-work"
    generated_body = json.dumps(
        {
            "synthesis": synthesis_text,
            "implementation": str(implementation.get("output") or ""),
            "plan_digest": plan_digest,
            "decision": decision,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    model_providers = sorted({str(entry.get("provider")) for entry in plans + plan_reviews + final_reviews if entry.get("provider")})
    model_ids = sorted({str(entry.get("model_served")) for entry in plans + plan_reviews + final_reviews if entry.get("model_served")})
    content_provenance = runtime_output_provenance(
        generated_body,
        content_type="application/json",
        model_providers=model_providers,
        model_ids=model_ids,
    )
    result = {
        "schema": "iot-ai.multi-coder-result.v3",
        "run_id": run_id,
        "task_id": task_id,
        "decision": decision,
        "plans": plans,
        "critiques": critiques,
        "synthesis": synthesis,
        "plan_digest": plan_digest,
        "plan_reviews": plan_reviews,
        "implementation": implementation,
        "change_binding": change_binding,
        "tests": results,
        "repair_rounds": repair_round,
        "final_reviews": final_reviews,
        "article_5": article5.to_dict(),
        "article_6": article6,
        "article_50": disclosure,
        "content_provenance": content_provenance,
        "execution_authorized": decision == "approve",
        "global_compliance_claim_allowed": False,
    }
    if task_id and decision == "approve":
        record_progress(
            user_home,
            task_id,
            "complete",
            95,
            "Implementation, deterministic tests and digest-bound independent review passed",
            work_unit_id,
            basis="deterministic-tests",
            evidence_ids=[str(row.get("test_id")) for row in results if row.get("test_id")],
            confidence="high",
        )
        submitted = submit_task(
            user_home,
            task_id,
            work_unit_id,
            lease_id,
            lease_token,
            "Multi-Coder implementation, deterministic tests and independent review completed",
        )
        result["submission"] = submitted
        result["decision"] = "approve" if submitted["audit"]["decision"] == "approve_technical" else "needs-work"
    elif lease_id and lease_token:
        release_lease(user_home, lease_id, lease_token, "needs-work")
    export_workspace(user_home, task_id=task_id)
    return result
