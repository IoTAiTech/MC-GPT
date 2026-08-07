# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
"""Canonical cross-meeting reporting directly from the SQLite source of truth."""
from __future__ import annotations
import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from .meeting import project_meeting_view, show
from .util import sha256_file, utc_now
from .paths import data_root
from .workspace import connect_read, rows

def _ids(
    user_home: Path,
    *,
    from_time: str | None = None,
    to_time: str | None = None,
    status: str | None = None,
    task_id: str | None = None,
    provider: str | None = None,
    agent: str | None = None,
    decision: str | None = None,
) -> list[str]:
    conn = connect_read(user_home)
    if conn is None:
        return []
    clauses: list[str] = []
    params: list[Any] = []
    if from_time: clauses.append("m.created_at>=?"); params.append(from_time)
    if to_time: clauses.append("m.created_at<=?"); params.append(to_time)
    if status: clauses.append("m.status=?"); params.append(status)
    if task_id: clauses.append("m.task_id=?"); params.append(task_id)
    if decision: clauses.append("m.final_decision=?"); params.append(decision)
    if provider:
        clauses.append("EXISTS(SELECT 1 FROM meeting_contributions c WHERE c.meeting_id=m.id AND (c.seat=? OR c.seat LIKE ?))")
        params.extend([provider, provider + "@%"])
    if agent:
        clauses.append("EXISTS(SELECT 1 FROM meeting_contributions c WHERE c.meeting_id=m.id AND c.seat=?)")
        params.append(agent if agent.startswith("agent:") else "agent:" + agent)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    result = [row["id"] for row in rows(conn, "SELECT m.id FROM meetings m" + where + " ORDER BY m.created_at,m.id", params)]
    conn.close()
    return result

def collect(user_home: Path, *, view: str = "brief", **filters: Any) -> dict[str, Any]:
    ids = _ids(user_home, **filters)
    meetings = [project_meeting_view(show(user_home, meeting_id), view) for meeting_id in ids]
    return {
        "schema": "iot-ai.cross-meeting-report.v1",
        "generated_at": utc_now(),
        "view": "brief" if view in {"brief", "simple"} else "full",
        "filters": {key: value for key, value in filters.items() if value is not None},
        "meeting_count": len(meetings),
        "meetings": meetings,
    }

def _flat(payload: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in payload["meetings"]:
        meeting = item.get("meeting") or item
        participants = item.get("participants") or meeting.get("contributions") or []
        output.append({
            "meeting_id": meeting.get("id") or item.get("meeting_id"),
            "task_id": meeting.get("task_id") or item.get("task_id"),
            "created_at": meeting.get("created_at") or item.get("created_at"),
            "updated_at": meeting.get("updated_at") or item.get("updated_at"),
            "topic": meeting.get("topic") or item.get("topic") or item.get("topic_preview"),
            "status": meeting.get("status") or item.get("status"),
            "final_decision": meeting.get("final_decision") or item.get("final_decision"),
            "requested_seats": meeting.get("requested_seats") or item.get("requested_seats"),
            "substantive_seats": meeting.get("substantive_seats") or item.get("substantive_seats"),
            "participant_models": json.dumps([{"seat": p.get("seat"), "model_served": p.get("model_served"), "status": p.get("status")} for p in participants], ensure_ascii=False),
            "synthesis_summary": item.get("synthesis_summary") or meeting.get("synthesis"),
            "blockers": json.dumps(item.get("blockers") or [], ensure_ascii=False),
        })
    return output


def managed_report_output(user_home: Path, filename: str) -> Path:
    """Resolve API-created reports below the Suite-managed report root."""
    if not filename or Path(filename).name != filename or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for ch in filename):
        raise ValueError("invalid report filename")
    root = (data_root(user_home) / "meeting-reports").resolve()
    root.mkdir(parents=True, exist_ok=True)
    output = (root / filename).resolve()
    if output.parent != root:
        raise PermissionError("report output escaped managed root")
    return output


def write_report(user_home: Path, output: Path, *, output_format: str, view: str = "brief", **filters: Any) -> dict[str, Any]:
    payload = collect(user_home, view=view, **filters)
    output.parent.mkdir(parents=True, exist_ok=True)
    fmt = output_format.lower()
    if fmt == "json":
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif fmt == "csv":
        rows_out = _flat(payload)
        fields = list(rows_out[0]) if rows_out else ["meeting_id", "task_id", "created_at", "topic", "status", "final_decision"]
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows_out)
    elif fmt in {"md", "markdown"}:
        lines = ["# IOT-AI Meeting Report", "", f"Generated: {payload['generated_at']}", f"Meetings: {payload['meeting_count']}", ""]
        for item in payload["meetings"]:
            meeting = item.get("meeting") or item
            meeting_id = meeting.get("id") or item.get("meeting_id")
            lines.extend([f"## {meeting_id}", "", f"- Status: `{meeting.get('status') or item.get('status')}`", f"- Decision: `{meeting.get('final_decision') or item.get('final_decision')}`", f"- Topic: {meeting.get('topic') or item.get('topic') or ''}", ""])
            for participant in item.get("participants") or []:
                lines.append(f"- **{participant.get('seat')}** · {participant.get('status')} · {participant.get('model_served') or 'unverified'} — {participant.get('opinion_summary') or ''}")
            lines.extend(["", item.get("synthesis_summary") or "", ""])
        output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    elif fmt == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook(); ws = wb.active; ws.title = "Meetings"
        flat = _flat(payload); headers = list(flat[0]) if flat else ["meeting_id", "status"]
        ws.append(headers)
        for cell in ws[1]: cell.font = Font(bold=True)
        for row in flat: ws.append([row.get(header) for header in headers])
        part = wb.create_sheet("Participants"); part_headers = ["meeting_id","seat","status","model_requested","model_served","quality_score","failure_class","opinion_summary"]
        part.append(part_headers)
        for cell in part[1]: cell.font = Font(bold=True)
        for item in payload["meetings"]:
            meeting_id = (item.get("meeting") or item).get("id") or item.get("meeting_id")
            for participant in item.get("participants") or []:
                part.append([meeting_id] + [participant.get(name) for name in part_headers[1:]])
        fd, temp_name = tempfile.mkstemp(prefix=".meeting-report-", suffix=".xlsx", dir=str(output.parent)); os.close(fd)
        try:
            wb.save(temp_name); os.replace(temp_name, output)
        finally:
            Path(temp_name).unlink(missing_ok=True)
    else:
        raise ValueError("format must be json, csv, markdown or xlsx")
    return {"decision": "pass", "output": str(output), "format": fmt, "view": payload["view"], "meeting_count": payload["meeting_count"], "sha256": sha256_file(output, allowed_roots=[user_home, output.parent.resolve()])}
