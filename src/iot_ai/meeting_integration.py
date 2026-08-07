# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
"""Calendar, dashboard-agent registry and PMD-facing integration primitives."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .util import utc_now
from .workspace import append_event, connect_read, connect_write, new_id, one, rows

SURFACES = {"pmd", "fcc", "hid", "healthlab", "cws", "dgx"}

def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _validate_time(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("calendar timestamps must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def create_calendar_event(
    user_home: Path,
    *,
    title: str,
    topic: str,
    starts_at: str,
    requested_seats: str,
    created_by: str,
    ends_at: str | None = None,
    timezone_name: str = "Europe/Berlin",
    surface: str | None = None,
    project_id: str | None = None,
    org_id: str | None = None,
    quorum: int = 2,
    depth: str = "deep",
    effort: str = "high",
    auto_start: bool = False,
    rrule: str | None = None,
) -> dict[str, Any]:
    if not title.strip() or not topic.strip() or not requested_seats.strip():
        raise ValueError("title, topic and requested_seats are required")
    if surface and surface not in SURFACES:
        raise ValueError("unsupported surface")
    start_utc = _validate_time(starts_at)
    end_utc = _validate_time(ends_at) if ends_at else None
    event_id = new_id("calevt")
    now = utc_now()
    digest = hashlib.sha256(topic.strip().encode("utf-8")).hexdigest()
    conn = connect_write(user_home)
    try:
        conn.execute(
            """INSERT INTO calendar_events(
            id,title,topic,topic_sha256,surface,project_id,org_id,starts_at,ends_at,
            timezone,rrule,requested_seats,quorum,depth,effort,auto_start,status,
            next_run_at,created_by,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event_id, title.strip(), topic.strip(), digest, surface, project_id, org_id,
                start_utc, end_utc, timezone_name, rrule, requested_seats.strip(), quorum,
                depth, effort, int(auto_start), "scheduled", start_utc, created_by, now, now,
            ),
        )
        for seat in [item.strip() for item in requested_seats.split(",") if item.strip()]:
            seat_type = "agent" if seat.startswith("agent:") else "provider"
            seat_surface = seat.split(":", 1)[1].split("/", 1)[0] if seat_type == "agent" else None
            conn.execute(
                "INSERT INTO calendar_participants(id,event_id,seat,seat_type,surface,created_at) VALUES(?,?,?,?,?,?)",
                (new_id("calpart"), event_id, seat, seat_type, seat_surface, now),
            )
        append_event(conn, "calendar.event.created", {"event_id": event_id, "topic_sha256": digest, "starts_at": start_utc})
        conn.commit()
    finally:
        conn.close()
    return {"decision": "pass", "event_id": event_id, "starts_at": start_utc, "topic_sha256": digest, "status": "scheduled"}

def list_calendar_events(user_home: Path, *, status: str | None = None, surface: str | None = None) -> list[dict[str, Any]]:
    conn = connect_read(user_home)
    if conn is None:
        return []
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status=?"); params.append(status)
    if surface:
        clauses.append("surface=?"); params.append(surface)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    result = rows(conn, "SELECT * FROM calendar_events" + where + " ORDER BY starts_at,id", params)
    for item in result:
        item["participants"] = rows(conn, "SELECT * FROM calendar_participants WHERE event_id=? ORDER BY seat", (item["id"],))
    conn.close()
    return result

def start_calendar_event(user_home: Path, event_id: str) -> dict[str, Any]:
    from .meeting import start
    from .seat_selection import resolve_meeting_seats
    conn = connect_read(user_home)
    if conn is None:
        raise FileNotFoundError(event_id)
    event = one(conn, "SELECT * FROM calendar_events WHERE id=?", (event_id,))
    conn.close()
    if not event:
        raise FileNotFoundError(event_id)
    if event["status"] not in {"scheduled", "failed"}:
        raise ValueError(f"calendar event cannot start from {event['status']}")
    seat_plan = resolve_meeting_seats(user_home, str(event["requested_seats"]))
    if seat_plan.decision != "pass":
        raise PermissionError(f"calendar seat resolution blocked: {seat_plan.reason}")
    result = start(
        user_home, str(event["topic"]), list(seat_plan.resolved_seats), quorum=int(event["quorum"]),
        depth=str(event["depth"]), effort=str(event["effort"]), execute=True, seat_plan=seat_plan.to_dict(),
    )
    conn = connect_write(user_home)
    try:
        status = "completed" if result.get("command_execution_status") == "pass" else "failed"
        conn.execute(
            "UPDATE calendar_events SET status=?,meeting_id=?,last_run_at=?,updated_at=?,failure_reason=? WHERE id=?",
            (status, result.get("meeting_id"), utc_now(), utc_now(), result.get("failure_class"), event_id),
        )
        append_event(conn, "calendar.event.started", {"event_id": event_id, "meeting_id": result.get("meeting_id"), "status": status})
        conn.commit()
    finally:
        conn.close()
    return {"decision": result.get("decision"), "event_id": event_id, "meeting": result}

def register_agent_seat(
    user_home: Path,
    *,
    surface: str,
    agent_id: str,
    display_name: str,
    model_binding: str | None,
    endpoint_ref: str | None,
    capabilities: list[str] | None = None,
    risk_class: str | None = None,
    control_level: str = "advisory",
    reachable: bool = False,
) -> dict[str, Any]:
    if surface not in SURFACES:
        raise ValueError("unsupported surface")
    if not agent_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for ch in agent_id):
        raise ValueError("invalid agent_id")
    seat = f"agent:{surface}/{agent_id}"
    conn = connect_write(user_home)
    try:
        conn.execute(
            """INSERT INTO agent_seat_registry(
            seat,surface,agent_id,display_name,capabilities,model_binding,risk_class,
            control_level,endpoint_ref,reachable,refreshed_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(seat) DO UPDATE SET display_name=excluded.display_name,
            capabilities=excluded.capabilities,model_binding=excluded.model_binding,
            risk_class=excluded.risk_class,control_level=excluded.control_level,
            endpoint_ref=excluded.endpoint_ref,reachable=excluded.reachable,refreshed_at=excluded.refreshed_at""",
            (
                seat, surface, agent_id, display_name, _canonical(capabilities or []),
                model_binding, risk_class, control_level, endpoint_ref, int(reachable), utc_now(),
            ),
        )
        append_event(conn, "agent.seat.registered", {"seat": seat, "surface": surface, "reachable": reachable})
        conn.commit()
    finally:
        conn.close()
    return {"decision": "pass", "seat": seat, "reachable": reachable}

def list_agent_seats(user_home: Path, *, surface: str | None = None, reachable_only: bool = False) -> list[dict[str, Any]]:
    conn = connect_read(user_home)
    if conn is None:
        return []
    clauses: list[str] = []
    params: list[Any] = []
    if surface:
        clauses.append("surface=?"); params.append(surface)
    if reachable_only:
        clauses.append("reachable=1")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    result = rows(conn, "SELECT * FROM agent_seat_registry" + where + " ORDER BY surface,agent_id", params)
    conn.close()
    for item in result:
        item["capabilities"] = json.loads(item.pop("capabilities") or "[]")
        item["reachable"] = bool(item["reachable"])
    return result

def get_agent_seat(user_home: Path, seat: str) -> dict[str, Any] | None:
    conn = connect_read(user_home)
    if conn is None:
        return None
    result = one(conn, "SELECT * FROM agent_seat_registry WHERE seat=?", (seat,))
    conn.close()
    if result:
        result["capabilities"] = json.loads(result.pop("capabilities") or "[]")
        result["reachable"] = bool(result["reachable"])
    return result

def remember_idempotency(user_home: Path, key: str, operation: str, resource_id: str, response: dict[str, Any]) -> None:
    conn = connect_write(user_home)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO meeting_api_idempotency VALUES(?,?,?,?,?)",
            (key, operation, resource_id, _canonical(response), utc_now()),
        )
        conn.commit()
    finally:
        conn.close()

def lookup_idempotency(user_home: Path, key: str, operation: str) -> dict[str, Any] | None:
    conn = connect_read(user_home)
    if conn is None:
        return None
    row = one(conn, "SELECT response_json FROM meeting_api_idempotency WHERE idempotency_key=? AND operation=?", (key, operation))
    conn.close()
    return json.loads(row["response_json"]) if row else None
