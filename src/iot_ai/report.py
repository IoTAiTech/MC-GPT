# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations
from pathlib import Path
from typing import Any
from .telemetry import summary
from .workspace import connect_read,rows


def data(user_home:Path,window:str)->dict[str,Any]:
    providers=summary(user_home,window); conn=connect_read(user_home); task_counts={}; meeting_counts={}; audit_counts={}
    if conn is not None:
        task_counts={r["status"]:int(r["count"]) for r in rows(conn,"SELECT status,COUNT(*) count FROM tasks GROUP BY status")}
        meeting_counts={r["status"]:int(r["count"]) for r in rows(conn,"SELECT status,COUNT(*) count FROM meetings GROUP BY status")}
        audit_counts={r["decision"]:int(r["count"]) for r in rows(conn,"SELECT decision,COUNT(*) count FROM audits GROUP BY decision")}; conn.close()
    return {"schema":"iot-ai.report.v2","window":window,"providers":providers,"tasks_by_status":task_counts,"meetings_by_status":meeting_counts,"audits_by_decision":audit_counts,"quality_notice":"Quality values are rubric-based heuristics or explicit test/user scores, not guaranteed correctness."}


def render(user_home:Path,window:str,output_format:str="text")->str|dict[str,Any]:
    payload=data(user_home,window)
    if output_format=="json":return payload
    lines=[f"IOT-AI activity and provider report ({window})", "Tasks: "+(", ".join(f"{k}={v}" for k,v in sorted(payload['tasks_by_status'].items())) or "none"), "Meetings: "+(", ".join(f"{k}={v}" for k,v in sorted(payload['meetings_by_status'].items())) or "none"), "Audits: "+(", ".join(f"{k}={v}" for k,v in sorted(payload['audits_by_decision'].items())) or "none"),""]
    headers=("provider","model_served","contributions","successes","failures","input_tokens","cached_tokens","output_tokens","reasoning_tokens","avg_latency_ms","avg_quality","fallback_count")
    lines.append(" | ".join(headers))
    for row in payload["providers"]: lines.append(" | ".join(str(row.get(h)) for h in headers))
    lines.extend(["",payload["quality_notice"]]); return "\n".join(lines)
