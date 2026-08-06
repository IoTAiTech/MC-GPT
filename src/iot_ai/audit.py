# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
"""Independent, discrete hard-gate task audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .logging_config import append_event
from .util import sha256_file, utc_now
from .workspace import connect_read, connect_write, excel_manifest_path, excel_path, new_id, one, rows, verify_event_chain

MANDATORY_TIERS=("unit","integration","smoke","ab","stress","security","e2e","quality")


def _evidence_integrity(records:list[dict[str,Any]])->tuple[bool,list[str]]:
    findings=[]
    for row in records:
        path=Path(row["artifact_path"])
        if not path.is_file(): findings.append(f"missing-evidence:{row['id']}"); continue
        if sha256_file(path)!=row["artifact_sha256"]: findings.append(f"evidence-hash-mismatch:{row['id']}")
    return not findings,findings


def audit_task(user_home:Path,task_id:str,*,record:bool=True)->dict[str,Any]:
    conn=connect_read(user_home)
    if conn is None: raise ValueError("Task not found")
    task=one(conn,"SELECT * FROM tasks WHERE id=?",(task_id,))
    if not task: conn.close(); raise ValueError("Task not found")
    meetings=rows(conn,"SELECT * FROM meetings WHERE task_id=? ORDER BY created_at",(task_id,))
    meeting=next((m for m in reversed(meetings) if m["status"]=="approved" and m["user_approved"]),None)
    kpis=rows(conn,"SELECT * FROM meeting_kpis WHERE meeting_id=?",(meeting["id"],)) if meeting else []
    cases=rows(conn,"SELECT * FROM meeting_cases WHERE meeting_id=?",(meeting["id"],)) if meeting else []
    case_counts={kind:sum(1 for row in cases if row["case_type"]==kind) for kind in ("use","test","failure")}
    contributions=rows(conn,"SELECT * FROM contributions WHERE task_id=? ORDER BY created_at",(task_id,))
    substantive={row["provider"] for row in contributions if row["status"]=="pass" and row["stage"] in {"meeting-opinion","plan","critique","final-review"}}
    work_units=rows(conn,"SELECT * FROM work_units WHERE task_id=?",(task_id,))
    attempts=rows(conn,"SELECT * FROM attempts WHERE task_id=?",(task_id,))
    evidence=rows(conn,"SELECT * FROM evidence WHERE task_id=?",(task_id,))
    tests=rows(conn,"SELECT * FROM test_results WHERE task_id=?",(task_id,))
    active_leases=rows(conn,"SELECT * FROM leases WHERE task_id=? AND status='active'",(task_id,))
    final_reviews=[row for row in contributions if row["stage"]=="final-review" and row["status"]=="pass"]
    conn.close()
    evidence_ok,evidence_findings=_evidence_integrity(evidence)
    test_by_tier={row["tier"]:row for row in tests if row["decision"]=="pass" and row["exit_code"]==0}
    excel_ok=False; excel_sha=None
    if excel_path(user_home).is_file() and excel_manifest_path(user_home).is_file():
        manifest=json.loads(excel_manifest_path(user_home).read_text(encoding='utf-8'))
        excel_sha=sha256_file(excel_path(user_home)); excel_ok=manifest.get("sha256")==excel_sha
    chain=verify_event_chain(user_home)
    governed=task["risk_class"] in {"R2","R3","R4"} or bool(meetings)
    gates={
        "event_chain":chain["decision"]=="pass",
        "meeting_approved":(meeting is not None) if governed else True,
        "kpis_present":len(kpis)>=1 if governed else True,
        "use_cases_10":case_counts["use"]>=10 if governed else True,
        "test_cases_10":case_counts["test"]>=10 if governed else True,
        "failure_cases_10":case_counts["failure"]>=10 if governed else True,
        "substantive_quorum":len(substantive)>=(meeting["quorum"] if meeting else 1) if governed else True,
        "work_unit_present":bool(work_units) if governed else True,
        "provider_attempts_present":bool(attempts) if governed else True,
        "evidence_present_and_valid":bool(evidence) and evidence_ok if governed else evidence_ok,
        "mandatory_tests_pass":all(tier in test_by_tier for tier in MANDATORY_TIERS) if governed else all(row["decision"]=="pass" for row in tests),
        "independent_final_review":len({r["provider"] for r in final_reviews})>=1 if governed else True,
        "no_active_lease":not active_leases,
        "progress_complete":task["engineering_progress"]==100 and task["task_progress"]==100,
        "excel_projection_sealed":excel_ok,
    }
    findings=list(evidence_findings)
    findings.extend(f"gate-failed:{name}" for name,passed in gates.items() if not passed)
    passed=sum(1 for x in gates.values() if x); score=round(100*passed/len(gates),4)
    decision="approve_technical" if all(gates.values()) else "needs-work"
    payload={"schema":"iot-ai.task-audit.v2","task_id":task_id,"decision":decision,"gate_score":score,"gates":gates,"findings":findings,"case_counts":case_counts,"substantive_providers":sorted(substantive),"mandatory_tiers":list(MANDATORY_TIERS),"excel_sha256":excel_sha,"event_chain":chain,"created_at":utc_now()}
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest(); payload["evidence_sha256"]=digest
    if record:
        conn=connect_write(user_home); aid=new_id("audit"); conn.execute("INSERT INTO audits(id,task_id,decision,gate_score,gates_json,findings_json,evidence_sha256,created_at) VALUES(?,?,?,?,?,?,?,?)",(aid,task_id,decision,score,json.dumps(gates,sort_keys=True),json.dumps(findings),digest,payload["created_at"])); conn.commit(); conn.close(); payload["audit_id"]=aid
        try:
            from .knowledge import add_item
            add_item(user_home,"audit",aid,task_id,f"Audit {task_id}",json.dumps(payload,ensure_ascii=False),"internal",["audit",decision])
        except Exception as exc:
            append_event(
                user_home,
                "audit.knowledge_export_failed",
                {"task_id": task_id, "audit_id": aid, "error_type": type(exc).__name__, "error": str(exc)},
                audit=True,
                correlation_id=aid,
            )
    return payload
