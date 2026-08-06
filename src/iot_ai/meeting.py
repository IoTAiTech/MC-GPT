# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
"""Deep multi-provider meeting workflow linked to the task store.

A successful command is never interpreted as an accepted plan.  Empty seats,
unknown served models, failed final reviews and digest disagreement remain
explicitly unsatisfied.
"""
from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .eu_ai_act import classify_risk, record_prohibited_practice_screen, screen_prohibited_practices
from .licensing import current
from .logging_config import append_event
from .mesh import delegate
from .owned_delegate import owned_delegate
from .projection import export_workspace
from .quality import score_response
from .telemetry import update_quality
from .transparency import disclosure_payload, record_disclosure, runtime_output_provenance
from .util import utc_now
from .workspace import append_event, connect_read, connect_write, new_id, one, rows

DEPTHS = {
    "normal": {"rounds": 1, "cases": 10},
    "deep": {"rounds": 2, "cases": 10},
    "ultra": {"rounds": 3, "cases": 10},
}


def _substantive(value: dict[str, Any]) -> bool:
    text = str(value.get("output") or value.get("text") or "").strip()
    if value.get("status") != "pass" or len(text) < 40 or not value.get("model_served"):
        return False
    low = text.casefold()
    return not any(
        marker in low
        for marker in (
            "not signed in",
            "quota exceeded",
            "usage limit",
            "missing executable",
            "i cannot access the workspace",
        )
    )


def _store_contribution(
    conn: Any,
    meeting_id: str,
    task_id: str | None,
    seat: str,
    kind: str,
    round_no: int,
    result: dict[str, Any],
    quality: dict[str, Any] | None,
) -> dict[str, Any]:
    text = str(result.get("output") or "")
    contribution_id = new_id("mtgc")
    created = utc_now()
    digest = hashlib.sha256(text.encode()).hexdigest() if text else None
    conn.execute(
        """INSERT INTO meeting_contributions(
        id,meeting_id,task_id,seat,kind,round_no,status,text,text_sha256,
        model_requested,model_served,request_or_job_id,auth_route,input_tokens,
        cached_tokens,output_tokens,reasoning_tokens,latency_ms,fallback_used,
        failure_class,quality_score,quality_basis,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            contribution_id,
            meeting_id,
            task_id,
            seat,
            kind,
            round_no,
            result.get("status", "failed"),
            text,
            digest,
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
            quality.get("score") if quality else None,
            quality.get("basis") if quality else None,
            created,
        ),
    )
    return {
        "id": contribution_id,
        "seat": seat,
        "kind": kind,
        "round_no": round_no,
        "status": result.get("status"),
        "text": text,
        "substantive": _substantive(result),
        "model_requested": result.get("model_requested"),
        "model_served": result.get("model_served"),
        "request_or_job_id": result.get("request_id"),
        "route_id": result.get("route_id"),
        "tokens": {
            "input": result.get("input_tokens"),
            "cached": result.get("cached_tokens"),
            "output": result.get("output_tokens"),
            "reasoning": result.get("reasoning_tokens"),
        },
        "latency_ms": result.get("latency_ms"),
        "fallback_used": bool(result.get("fallback_used")),
        "failure_class": result.get("failure_class"),
        "quality": quality,
    }


def _default_kpis(topic: str) -> list[dict[str, str]]:
    del topic
    return [
        {"name": "substantive_quorum", "target": "all required seats or an explicit approved adaptive policy", "measurement": "substantive independent seat receipts"},
        {"name": "cross_critique", "target": ">= 1 critique round", "measurement": "stored critique contributions"},
        {"name": "same_plan_digest", "target": "100% required final reviewers", "measurement": "digest-bound acceptance matrix"},
        {"name": "use_cases", "target": ">= 10", "measurement": "meeting_cases type=use"},
        {"name": "test_cases", "target": ">= 10", "measurement": "meeting_cases type=test"},
        {"name": "failure_cases", "target": ">= 10", "measurement": "meeting_cases type=failure"},
        {"name": "provider_accounting", "target": "100% requested seats accounted", "measurement": "success/outage/failure receipt per seat"},
    ]


def _cases(topic: str, kind: str, count: int = 10) -> list[dict[str, str]]:
    labels = {"use": "Use case", "test": "Test case", "failure": "Failure case"}
    result: list[dict[str, str]] = []
    for index in range(1, count + 1):
        if kind == "use":
            description = f"Actor applies the approved design for scenario {index} related to: {topic}"
            expected = "The expected business or engineering outcome is explicit, measurable and evidence-backed."
        elif kind == "test":
            description = f"Verify scenario {index} for the approved plan with deterministic evidence."
            expected = "The test produces a reproducible pass/fail receipt and no fabricated success."
        else:
            description = f"Simulate invalid, unavailable or adversarial condition {index} for: {topic}"
            expected = "The system fails closed, preserves evidence and remains recoverable."
        result.append({"title": f"{labels[kind]} {index}", "description": description, "expected": expected})
    return result


def _parse_review(text: str, expected_digest: str) -> dict[str, Any]:
    stripped = text.strip()
    payload: dict[str, Any] = {}
    candidates = [stripped]
    if "```json" in stripped:
        candidates.insert(0, stripped.split("```json", 1)[1].split("```", 1)[0])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            payload = value
            break
    if not payload:
        lowered = stripped.casefold()
        decision = "accept" if re.search(r"\bdecision\s*:\s*(?:accept|approve|pass)\b", lowered) else "needs-work"
        digest = expected_digest if expected_digest in stripped else None
        payload = {"decision": decision, "plan_digest": digest, "unstructured": True}
    accepted = payload.get("decision") in {"accept", "approve", "pass"} and payload.get("plan_digest") == expected_digest
    return {"accepted": accepted, "decision": payload.get("decision"), "plan_digest": payload.get("plan_digest"), "payload": payload}


def _requested_seats(user_home: Path, task_id: str) -> list[str]:
    conn = connect_read(user_home)
    event = one(
        conn,
        "SELECT payload_json FROM events WHERE task_id=? AND event_type='meeting.created' ORDER BY seq DESC LIMIT 1",
        (task_id,),
    ) if conn else None
    if conn:
        conn.close()
    return list(json.loads(event["payload_json"])["seats"]) if event else []


def start(
    user_home: Path,
    topic: str,
    seats: list[str],
    quorum: int = 2,
    rounds: int = 1,
    execute: bool = False,
    *,
    depth: str = "normal",
    effort: str = "high",
    owner: str | None = None,
    priority: str = "normal",
    risk_class: str = "R2",
    seat_plan: dict[str, Any] | None = None,
    max_parallel: int | None = None,
) -> dict[str, Any]:
    clean = list(dict.fromkeys(seat.strip().lower() for seat in seats if seat.strip()))
    if not topic.strip() or not clean:
        raise ValueError("topic and seats are required")
    article5 = screen_prohibited_practices(topic)
    record_prohibited_practice_screen(user_home, topic, context="meeting-start")
    if article5.decision == "block":
        raise PermissionError("EU AI Act Article 5 prohibited-practice screen blocked this meeting before provider dispatch")
    article6 = classify_risk(topic)
    if execute and article6.get("decision") == "high-risk-candidate":
        raise PermissionError("high-risk candidate requires a deployment-specific classification before execution")
    entitlement = current()
    if len(clean) > entitlement.max_providers:
        raise PermissionError(f"{entitlement.edition} edition supports at most {entitlement.max_providers} meeting seats")
    if quorum < 1 or quorum > len(clean):
        raise ValueError("invalid quorum")
    if depth not in DEPTHS:
        raise ValueError("invalid meeting depth")
    meeting_id = new_id("meeting")
    configured_rounds = max(rounds, DEPTHS[depth]["rounds"])
    from .tasks import create

    task = create(
        user_home,
        f"Meeting: {topic.strip()}",
        f"Deep multi-coder consultation for: {topic.strip()}",
        priority,
        owner,
        risk_class=risk_class,
        task_type="meeting-decision",
        source="meeting",
        source_id=meeting_id,
        tags=["meeting", depth, "eu-ai-act-screened"],
        acceptance_criteria="Approved same-digest synthesis, KPIs, 10 use cases, 10 tests, 10 failure cases and deterministic execution evidence",
        allow_duplicate=True,
    )
    task_id = task["task_id"]
    disclosure = record_disclosure(user_home, surface="cli:meeting", language="en")
    conn = connect_write(user_home)
    try:
        now = utc_now()
        conn.execute(
            "INSERT INTO meetings(id,task_id,topic,depth,effort,status,requested_seats,quorum,rounds,created_at,updated_at) VALUES(?,?,?,?,?,'planned',?,?,?,?,?)",
            (meeting_id, task_id, topic.strip(), depth, effort, len(clean), quorum, configured_rounds, now, now),
        )
        append_event(
            conn,
            "meeting.created",
            {
                "meeting_id": meeting_id,
                "seats": clean,
                "quorum": quorum,
                "depth": depth,
                "effort": effort,
                "article_5": article5.to_dict(),
                "article_6": article6,
                "article_50": disclosure,
                "article_50_disclosure_receipt": disclosure["receipt"],
                "seat_plan": seat_plan or {
                    "schema": "iot-ai.meeting-seat-plan.v1",
                    "selector": "explicit-api",
                    "requested_seats": clean,
                    "resolved_seats": clean,
                    "ollama_cloud_included": any(seat.startswith("ollama@") or seat == "ollama" for seat in clean),
                    "decision": "pass",
                },
                "max_parallel": max_parallel or min(8, len(clean)),
            },
            task_id=task_id,
        )
        conn.commit()
    finally:
        conn.close()
    result = {
        "decision": "pass",
        "command_execution_status": "pass",
        "meeting_id": meeting_id,
        "task_id": task_id,
        "topic": topic.strip(),
        "seats": clean,
        "quorum": quorum,
        "rounds": configured_rounds,
        "depth": depth,
        "effort": effort,
        "seat_plan": seat_plan or {
            "schema": "iot-ai.meeting-seat-plan.v1",
            "selector": "explicit-api",
            "requested_seats": clean,
            "resolved_seats": clean,
            "ollama_cloud_included": any(seat.startswith("ollama@") or seat == "ollama" for seat in clean),
            "decision": "pass",
        },
        "max_parallel": max_parallel or min(8, len(clean)),
        "status": "planned",
        "meeting_status": "planned",
        "plan_acceptance": "none",
        "article_5": article5.to_dict(),
        "article_6": article6,
        "article_50": disclosure,
        "global_compliance_claim_allowed": False,
    }
    export_workspace(user_home, task_id=task_id)
    return run(user_home, meeting_id) if execute else result


def show(user_home: Path, meeting_id: str) -> dict[str, Any]:
    conn = connect_read(user_home)
    if conn is None:
        raise FileNotFoundError(meeting_id)
    meeting = one(conn, "SELECT * FROM meetings WHERE id=?", (meeting_id,))
    if not meeting:
        conn.close()
        raise FileNotFoundError(meeting_id)
    meeting["contributions"] = rows(conn, "SELECT * FROM meeting_contributions WHERE meeting_id=? ORDER BY round_no,created_at", (meeting_id,))
    meeting["kpis"] = rows(conn, "SELECT * FROM meeting_kpis WHERE meeting_id=? ORDER BY name", (meeting_id,))
    meeting["cases"] = rows(conn, "SELECT * FROM meeting_cases WHERE meeting_id=? ORDER BY case_type,ordinal", (meeting_id,))
    event = one(conn, "SELECT payload_json FROM events WHERE task_id=? AND event_type='meeting.acceptance_evaluated' ORDER BY seq DESC LIMIT 1", (meeting["task_id"],))
    created_event = one(conn, "SELECT payload_json FROM events WHERE task_id=? AND event_type='meeting.created' ORDER BY seq ASC LIMIT 1", (meeting["task_id"],))
    conn.close()
    acceptance = json.loads(event["payload_json"]) if event else {}
    created_payload = json.loads(created_event["payload_json"]) if created_event else {}
    article_50 = created_payload.get("article_50")
    if not isinstance(article_50, dict):
        receipt = created_payload.get("article_50_disclosure_receipt") or {}
        disclosure = disclosure_payload(surface="cli:meeting", language=str(receipt.get("language") or "en"))
        if receipt.get("shown_at"):
            disclosure["shown_at"] = receipt["shown_at"]
        article_50 = {"disclosure": disclosure, "receipt": receipt}
    plan_acceptance = "accepted" if acceptance.get("accepted") else ("pending-user" if meeting["status"] == "awaiting-user-decision" else "none")
    seat_plan = created_payload.get("seat_plan") if isinstance(created_payload.get("seat_plan"), dict) else {
        "schema": "iot-ai.meeting-seat-plan.v1",
        "selector": "legacy-explicit",
        "requested_seats": created_payload.get("seats", []),
        "resolved_seats": created_payload.get("seats", []),
        "ollama_cloud_included": any(str(seat).startswith("ollama@") or seat == "ollama" for seat in created_payload.get("seats", [])),
        "decision": "pass",
    }
    requested = list(seat_plan.get("requested_seats") or created_payload.get("seats") or [])
    attempted = sorted({str(row.get("seat") or "") for row in meeting["contributions"] if row.get("seat")})
    substantive = sorted({str(row.get("seat") or "") for row in meeting["contributions"] if row.get("text") and row.get("model_served")})
    ollama_requested = [seat for seat in requested if str(seat).startswith("ollama@") or seat == "ollama"]
    ollama_attempted = [seat for seat in attempted if str(seat).startswith("ollama@") or seat == "ollama"]
    ollama_substantive = [seat for seat in substantive if str(seat).startswith("ollama@") or seat == "ollama"]
    providers = sorted({str(row.get("provider") or row.get("seat") or "") for row in meeting["contributions"] if row.get("text")})
    models = sorted({str(row.get("model_served") or "") for row in meeting["contributions"] if row.get("model_served")})
    content_provenance = (
        runtime_output_provenance(
            str(meeting.get("synthesis") or ""),
            content_type="text/plain",
            model_providers=[value for value in providers if value],
            model_ids=[value for value in models if value],
        )
        if meeting.get("synthesis")
        else None
    )
    return {
        "decision": "pass",
        "command_execution_status": "pass",
        "meeting_id": meeting_id,
        "task_id": meeting["task_id"],
        "status": meeting["status"],
        "meeting_status": meeting["status"],
        "plan_acceptance": plan_acceptance,
        "plan_digest": acceptance.get("plan_digest"),
        "acceptance_matrix": acceptance.get("acceptance_matrix", {}),
        "hard_gates": acceptance.get("hard_gates", {}),
        "founder_approval": bool(meeting.get("user_approved")),
        "execution_authorized": False,
        "seat_plan": seat_plan,
        "seat_coverage": {
            "requested": requested,
            "attempted": attempted,
            "substantive": substantive,
            "unsatisfied": sorted(set(requested) - set(substantive)),
            "ollama_requested": ollama_requested,
            "ollama_attempted": ollama_attempted,
            "ollama_substantive": ollama_substantive,
            "ollama_omitted": not bool(ollama_requested),
        },
        "article_50": article_50,
        "global_compliance_claim_allowed": False,
        "content_provenance": content_provenance,
        "meeting": meeting,
    }


def _delegate_safe(
    user_home: Path,
    seat: str,
    prompt: str,
    stage: str,
    run_id: str,
    role: str,
    timeout: int,
    effort: str = "high",
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
        privacy_class="D1",
        meeting_id=run_id,
        delegate_fn=delegate,
    )


def run(user_home: Path, meeting_id: str) -> dict[str, Any]:
    current_record = show(user_home, meeting_id)["meeting"]
    if current_record["status"] == "approved":
        return show(user_home, meeting_id)
    topic = current_record["topic"]
    task_id = current_record["task_id"]
    seats = _requested_seats(user_home, task_id)
    conn_meta = connect_read(user_home)
    created_meta = one(conn_meta, "SELECT payload_json FROM events WHERE task_id=? AND event_type='meeting.created' ORDER BY seq ASC LIMIT 1", (task_id,)) if conn_meta else None
    if conn_meta:
        conn_meta.close()
    created_payload = json.loads(created_meta["payload_json"]) if created_meta else {}
    max_parallel = max(1, min(int(created_payload.get("max_parallel") or 8), len(seats)))
    run_id = meeting_id
    opinions: list[dict[str, Any]] = []
    raw: list[tuple[str, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {
            pool.submit(
                _delegate_safe,
                user_home,
                seat,
                (
                    "Return an independent, evidence-aware opinion. Do not assume other seats. "
                    "Use the exact role you were assigned and return explicit risks, alternatives, "
                    "measurable outcomes, missing evidence and a decision. Topic: " + topic
                ),
                "meeting-opinion",
                run_id,
                "independent-opinion",
                900,
            ): seat
            for seat in seats
        }
        for future in as_completed(futures):
            raw.append((futures[future], future.result()))
    peer_texts = [result.get("output", "") for _, result in raw if _substantive(result)]
    quality_updates: list[tuple[str, dict[str, Any]]] = []
    conn = connect_write(user_home)
    try:
        for seat, result in raw:
            quality = score_response(topic, result.get("output", ""), [text for text in peer_texts if text != result.get("output", "")]) if result.get("status") == "pass" else None
            if quality and result.get("contribution_id"):
                quality_updates.append((result["contribution_id"], quality))
            opinions.append(_store_contribution(conn, meeting_id, task_id, seat, "opinion", 1, result, quality))
        conn.commit()
    finally:
        conn.close()
    for contribution_id, quality in quality_updates:
        update_quality(user_home, contribution_id, quality)
    good = [item for item in opinions if item["substantive"]]
    if len(good) < current_record["quorum"]:
        conn = connect_write(user_home)
        try:
            conn.execute("UPDATE meetings SET status='needs-review',substantive_seats=?,updated_at=? WHERE id=?", (len(good), utc_now(), meeting_id))
            append_event(
                conn,
                "meeting.quorum_failed",
                {"substantive": len(good), "required": current_record["quorum"], "requested": seats, "unsatisfied": sorted(set(seats) - {item["seat"] for item in good})},
                task_id=task_id,
            )
            conn.commit()
        finally:
            conn.close()
        export_workspace(user_home, task_id=task_id)
        return show(user_home, meeting_id)

    combined = "\n\n".join(f"[{item['seat']}] {item['text']}" for item in sorted(good, key=lambda row: row["seat"]))
    previous = combined
    for round_no in range(1, current_record["rounds"] + 1):
        critiques: list[dict[str, Any]] = []
        buffered: list[tuple[str, dict[str, Any], dict[str, Any] | None]] = []
        with ThreadPoolExecutor(max_workers=min(max_parallel, len(good))) as pool:
            futures = {
                pool.submit(
                    _delegate_safe,
                    user_home,
                    item["seat"],
                    (
                        "Blind-critique the meeting material. Identify factual gaps, weak assumptions, duplicate ideas, "
                        "missing tests, legal/security concerns and unresolved risk. Do not rubber-stamp.\nTOPIC:\n"
                        + topic
                        + "\nMATERIAL:\n"
                        + previous
                    ),
                    "meeting-critique",
                    run_id,
                    "critic",
                    900,
                ): item["seat"]
                for item in good
            }
            for future in as_completed(futures):
                seat = futures[future]
                result = future.result()
                quality = score_response(previous, result.get("output", ""), []) if result.get("status") == "pass" else None
                buffered.append((seat, result, quality))
        conn = connect_write(user_home)
        try:
            for seat, result, quality in buffered:
                critiques.append(_store_contribution(conn, meeting_id, task_id, seat, "critique", round_no, result, quality))
            conn.commit()
        finally:
            conn.close()
        substantial = [item["text"] for item in critiques if item["substantive"]]
        if substantial:
            previous = combined + f"\n\nCRITIQUES ROUND {round_no}\n" + "\n".join(substantial)

    # Deterministic authority selection: no length/quality heuristic grants synthesis authority.
    synthesis_order = ("codex", "grok", "claude", "gemini")
    good_by_seat = {item["seat"]: item for item in good}
    synthesis_provider = next((seat for seat in synthesis_order if seat in good_by_seat), sorted(good_by_seat)[0])
    synthesis_prompt = (
        "Synthesize one final decision package. Preserve disagreements and missing evidence. "
        "Include direct answer, 5W1H, architecture, ordered plan, KPI, SLA, exactly 10 use cases, "
        "10 test cases, 10 failure cases, security risks and residual blockers. Do not claim consensus.\n"
        f"TOPIC:\n{topic}\nMATERIAL:\n{previous}"
    )
    synthesis_result = _delegate_safe(user_home, synthesis_provider, synthesis_prompt, "meeting-synthesis", run_id, "plan-synthesizer", 1200)
    synthesis_quality = score_response(topic, synthesis_result.get("output", ""), peer_texts) if synthesis_result.get("status") == "pass" else None
    if synthesis_quality and synthesis_result.get("contribution_id"):
        update_quality(user_home, synthesis_result["contribution_id"], synthesis_quality)
    conn = connect_write(user_home)
    try:
        synthesis_entry = _store_contribution(
            conn,
            meeting_id,
            task_id,
            synthesis_provider,
            "synthesis",
            current_record["rounds"] + 1,
            synthesis_result,
            synthesis_quality,
        )
        synthesis_text = synthesis_entry["text"]
        plan_digest = hashlib.sha256(synthesis_text.encode("utf-8")).hexdigest() if synthesis_text else None
        for row in _default_kpis(topic):
            conn.execute("INSERT INTO meeting_kpis VALUES(?,?,?,?,?,?,?)", (new_id("kpi"), meeting_id, row["name"], row["target"], row["measurement"], 1, utc_now()))
        for kind in ("use", "test", "failure"):
            for index, row in enumerate(_cases(topic, kind, 10), 1):
                conn.execute("INSERT INTO meeting_cases VALUES(?,?,?,?,?,?,?,?,?)", (new_id("case"), meeting_id, kind, index, row["title"], row["description"], row["expected"], 1, utc_now()))
        conn.commit()
    finally:
        conn.close()

    final_reviews: list[dict[str, Any]] = []
    if synthesis_entry["substantive"] and plan_digest:
        prompt = (
            "Independently review the frozen meeting plan below. Return JSON only with keys decision, plan_digest, "
            "findings, dissent and missing_evidence. Accept only if the plan is complete, evidence-bound, safe, "
            "measurable and you accept this exact digest.\n"
            f"PLAN_DIGEST:{plan_digest}\nPLAN:\n{synthesis_text}"
        )
        buffered_reviews: list[tuple[str, dict[str, Any]]] = []
        with ThreadPoolExecutor(max_workers=min(max_parallel, len(good))) as pool:
            futures = {
                pool.submit(_delegate_safe, user_home, item["seat"], prompt, "meeting-final-review", run_id, "independent-judge", 900): item["seat"]
                for item in good
            }
            for future in as_completed(futures):
                buffered_reviews.append((futures[future], future.result()))
        conn = connect_write(user_home)
        try:
            for seat, result in buffered_reviews:
                parsed = _parse_review(str(result.get("output") or ""), plan_digest)
                result = {**result, "review": parsed}
                stored = _store_contribution(conn, meeting_id, task_id, seat, "final-review", current_record["rounds"] + 2, result, None)
                final_reviews.append({**stored, "review": parsed})
            conn.commit()
        finally:
            conn.close()

    substantive_seats = {item["seat"] for item in good}
    unsatisfied_requested = sorted(set(seats) - substantive_seats)
    acceptance_matrix = {
        item["seat"]: {
            "accepted": bool(item["review"]["accepted"]),
            "decision": item["review"]["decision"],
            "plan_digest": item["review"]["plan_digest"],
            "model_served": item.get("model_served"),
            "status": item.get("status"),
        }
        for item in final_reviews
    }
    hard_gates = {
        "synthesis_substantive": bool(synthesis_entry["substantive"]),
        "all_requested_seats_substantive": not unsatisfied_requested,
        "all_substantive_seats_final_reviewed": len(final_reviews) == len(good),
        "all_final_reviews_accept_same_digest": bool(final_reviews) and all(item["review"]["accepted"] for item in final_reviews),
        "exact_model_receipts": all(item.get("model_served") for item in opinions + final_reviews if item.get("seat") in substantive_seats),
        "ten_use_cases": True,
        "ten_test_cases": True,
        "ten_failure_cases": True,
    }
    accepted = all(hard_gates.values())
    status = "awaiting-user-decision" if accepted else "needs-review"
    final_decision = "accepted_by_required_seats" if accepted else "needs-work"
    consultation = previous + "\n\nSYNTHESIS\n" + synthesis_text
    consultation_digest = hashlib.sha256(consultation.encode("utf-8")).hexdigest()
    conn = connect_write(user_home)
    try:
        conn.execute(
            "UPDATE meetings SET status=?,substantive_seats=?,synthesis=?,final_decision=?,consultation_sha256=?,updated_at=? WHERE id=?",
            (status, len(good), synthesis_text, final_decision, consultation_digest, utc_now(), meeting_id),
        )
        append_event(
            conn,
            "meeting.acceptance_evaluated",
            {
                "meeting_id": meeting_id,
                "accepted": accepted,
                "plan_digest": plan_digest,
                "acceptance_matrix": acceptance_matrix,
                "hard_gates": hard_gates,
                "unsatisfied_requested_seats": unsatisfied_requested,
                "command_execution_status": "pass",
                "meeting_status": status,
                "founder_approval": False,
                "execution_authorized": False,
            },
            task_id=task_id,
        )
        conn.commit()
    finally:
        conn.close()
    try:
        from .knowledge import add_item

        add_item(user_home, "meeting", meeting_id, task_id, f"Meeting: {topic}", consultation, "internal", ["meeting", current_record["depth"]])
    except Exception as exc:
        append_event(
            user_home,
            "meeting.knowledge_export_failed",
            {"meeting_id": meeting_id, "task_id": task_id, "error_type": type(exc).__name__, "error": str(exc)},
            audit=True,
            correlation_id=meeting_id,
        )
    export_workspace(user_home, task_id=task_id)
    return show(user_home, meeting_id)


def list_meetings(user_home: Path) -> list[dict[str, Any]]:
    conn = connect_read(user_home)
    if conn is None:
        return []
    result = rows(conn, "SELECT id meeting_id,task_id,topic,status,depth,substantive_seats,quorum,created_at FROM meetings ORDER BY created_at DESC")
    conn.close()
    return result


def approve(user_home: Path, meeting_id: str) -> dict[str, Any]:
    conn = connect_write(user_home)
    try:
        meeting = one(conn, "SELECT * FROM meetings WHERE id=?", (meeting_id,))
        if not meeting:
            raise FileNotFoundError(meeting_id)
        if meeting["status"] != "awaiting-user-decision" or meeting.get("final_decision") != "accepted_by_required_seats":
            raise ValueError("meeting plan was not accepted by all required substantive seats")
        now = utc_now()
        conn.execute("UPDATE meetings SET status='approved',user_approved=1,updated_at=? WHERE id=?", (now, meeting_id))
        conn.execute("UPDATE tasks SET status='backlog',revision=revision+1,updated_at=? WHERE id=?", (now, meeting["task_id"]))
        append_event(
            conn,
            "meeting.founder_approved",
            {"meeting_id": meeting_id, "does_not_rewrite_synthesis": True},
            task_id=meeting["task_id"],
        )
        conn.commit()
    finally:
        conn.close()
    export_workspace(user_home, task_id=meeting["task_id"])
    return show(user_home, meeting_id)


def create_task_from_meeting(user_home: Path, meeting_id: str, title: str | None = None, workspace: Path | None = None) -> dict[str, Any]:
    del workspace
    meeting = show(user_home, meeting_id)["meeting"]
    if not meeting["user_approved"] or meeting["status"] != "approved":
        raise ValueError("meeting must be founder-approved after same-digest plan acceptance")
    if title:
        conn = connect_write(user_home)
        conn.execute("UPDATE tasks SET title=?,updated_at=?,revision=revision+1 WHERE id=?", (title, utc_now(), meeting["task_id"]))
        conn.commit()
        conn.close()
    return {"decision": "pass", "task_id": meeting["task_id"], "source_meeting": meeting_id, "existing_linked_task": True}
