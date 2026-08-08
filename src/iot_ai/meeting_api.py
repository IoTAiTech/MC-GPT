# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Loopback-only, bearer-authenticated Meeting Control Plane API v1."""
from __future__ import annotations
import hmac
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from .meeting import approve, create_task_from_meeting, list_meetings, project_meeting_view, show, start
from .seat_selection import resolve_meeting_seats
from .meeting_integration import create_calendar_event, list_agent_seats, list_calendar_events, lookup_idempotency, register_agent_seat, remember_idempotency, start_calendar_event
from .meeting_reporting import managed_report_output, write_report

MAX_BODY = 1_048_576

def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers(); handler.wfile.write(body)

def _handler(user_home: Path, token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "IOT-AI-Meeting/1"
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            supplied = header[7:] if header.startswith("Bearer ") else ""
            return bool(token) and hmac.compare_digest(supplied, token)
        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length < 0 or length > MAX_BODY: raise ValueError("request body too large")
            value = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if not isinstance(value, dict): raise ValueError("JSON object required")
            return value
        def _route(self, method: str) -> None:
            if self.path == "/health":
                _json(self, 200, {"ok": True, "service": "iot-ai-meeting", "version": "v1"}); return
            if not self._authorized():
                _json(self, 401, {"ok": False, "error": "unauthorized", "code": 401}); return
            parsed = urlparse(self.path); path = parsed.path; query = parse_qs(parsed.query)
            try:
                if method == "GET" and path == "/api/meeting/v1/meetings":
                    _json(self, 200, {"ok": True, "meetings": list_meetings(user_home)}); return
                if method == "POST" and path == "/api/meeting/v1/meetings":
                    body = self._body(); key = self.headers.get("Idempotency-Key")
                    if key and (previous := lookup_idempotency(user_home, key, "meeting.create")):
                        _json(self, 200, {"ok": True, "idempotent_replay": True, **previous}); return
                    seats_value = body.get("seats", "auto")
                    selector = ",".join(str(v) for v in seats_value) if isinstance(seats_value, list) else str(seats_value)
                    seat_plan = resolve_meeting_seats(user_home, selector, max_seats=int(body["max_seats"]) if body.get("max_seats") is not None else None)
                    if seat_plan.decision != "pass": raise PermissionError(f"meeting seat resolution blocked: {seat_plan.reason}")
                    result = start(user_home, str(body["topic"]), list(seat_plan.resolved_seats), quorum=int(body.get("quorum", 2)), depth=str(body.get("depth", "deep")), effort=str(body.get("effort", "high")), execute=bool(body.get("execute", False)), seat_plan=seat_plan.to_dict(), max_parallel=int(body.get("max_parallel") or min(8, len(seat_plan.resolved_seats))))
                    if key: remember_idempotency(user_home, key, "meeting.create", str(result["meeting_id"]), result)
                    _json(self, 201, {"ok": True, **result}); return
                if path.startswith("/api/meeting/v1/meetings/"):
                    suffix = path.removeprefix("/api/meeting/v1/meetings/")
                    meeting_id, _, operation = suffix.partition("/")
                    if method == "GET" and not operation:
                        _json(self, 200, {"ok": True, **project_meeting_view(show(user_home, meeting_id), query.get("view", ["full"])[0])}); return
                    if method == "POST" and operation == "approve":
                        _json(self, 200, {"ok": True, **approve(user_home, meeting_id)}); return
                    if method == "POST" and operation == "tasks":
                        body = self._body(); _json(self, 201, {"ok": True, **create_task_from_meeting(user_home, meeting_id, body.get("title"))}); return
                if method == "GET" and path == "/api/meeting/v1/calendar/events":
                    _json(self, 200, {"ok": True, "events": list_calendar_events(user_home, status=query.get("status", [None])[0], surface=query.get("surface", [None])[0])}); return
                if method == "POST" and path == "/api/meeting/v1/calendar/events":
                    body = self._body(); result = create_calendar_event(user_home, title=str(body["title"]), topic=str(body["topic"]), starts_at=str(body["starts_at"]), requested_seats=",".join(body["seats"]) if isinstance(body.get("seats"), list) else str(body.get("seats", "auto")), created_by="meeting-api", ends_at=body.get("ends_at"), surface=body.get("surface"), project_id=None, org_id=None, quorum=int(body.get("quorum", 2)), depth=str(body.get("depth", "deep")), effort=str(body.get("effort", "high")), auto_start=bool(body.get("auto_start", False)), rrule=body.get("rrule")); _json(self, 201, {"ok": True, **result}); return
                if method == "POST" and path.startswith("/api/meeting/v1/calendar/events/") and path.endswith("/start"):
                    event_id = path.split("/")[-2]; _json(self, 200, {"ok": True, **start_calendar_event(user_home, event_id)}); return
                if method == "GET" and path == "/api/meeting/v1/seats/agents":
                    _json(self, 200, {"ok": True, "agents": list_agent_seats(user_home, surface=query.get("surface", [None])[0], reachable_only=query.get("reachable", ["false"])[0].lower() == "true" )}); return
                if method == "POST" and path == "/api/meeting/v1/seats/agents":
                    body = self._body(); result = register_agent_seat(user_home, surface=str(body["surface"]), agent_id=str(body["agent_id"]), display_name=str(body.get("display_name") or body["agent_id"]), model_binding=body.get("model_binding"), endpoint_ref=body.get("endpoint_ref"), capabilities=list(body.get("capabilities") or []), risk_class=body.get("risk_class"), control_level=str(body.get("control_level", "advisory")), reachable=bool(body.get("reachable", False))); _json(self, 201, {"ok": True, **result}); return
                if method == "POST" and path == "/api/meeting/v1/reports":
                    body = self._body(); output = managed_report_output(user_home, str(body.get("filename") or "meeting-report.json")); result = write_report(user_home, output, output_format=str(body.get("format", "json")), view=str(body.get("view", "brief")), from_time=body.get("from_time"), to_time=body.get("to_time"), status=body.get("status"), task_id=body.get("task_id"), provider=body.get("provider"), agent=body.get("agent"), decision=body.get("decision")); _json(self, 201, {"ok": True, **result}); return
                _json(self, 404, {"ok": False, "error": "not found", "code": 404})
            except FileNotFoundError as exc:
                _json(self, 404, {"ok": False, "error": str(exc), "code": 404})
            except (KeyError, ValueError, PermissionError) as exc:
                _json(self, 400, {"ok": False, "error": str(exc), "code": 400})
            except Exception as exc:
                _json(self, 500, {"ok": False, "error": type(exc).__name__, "code": 500})
        def do_GET(self) -> None: self._route("GET")
        def do_POST(self) -> None: self._route("POST")
    return Handler

def serve(user_home: Path, *, host: str = "127.0.0.1", port: int = 8790, token_env: str = "IOT_AI_MEETING_API_TOKEN") -> None:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise PermissionError("Meeting API is loopback-bound by default")
    token = os.environ.get(token_env, "")
    if len(token) < 24:
        raise PermissionError(f"{token_env} must contain a strong bearer token")
    ThreadingHTTPServer((host, int(port)), _handler(user_home, token)).serve_forever()
