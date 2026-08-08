# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Standalone task lifecycle with work units, leases, evidence and audits."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .projection import export_workspace
from .util import sha256_file, utc_now
from .workspace import (
    CLOSED_STATUSES,
    OPEN_STATUSES,
    append_event,
    connect_read,
    connect_write,
    excel_manifest_path,
    excel_path,
    new_id,
    normalize_title,
    one,
    rows,
    verify_event_chain,
)

PRIORITIES = {"low", "normal", "high", "critical"}


def _priority(value: str | int) -> str:
    if isinstance(value, int):
        if value >= 90: return "critical"
        if value >= 70: return "high"
        if value <= 30: return "low"
        return "normal"
    val = str(value).strip().lower()
    if val not in PRIORITIES: raise ValueError(f"invalid priority: {value}")
    return val


def _task(conn, task_id: str) -> dict[str, Any]:
    value = one(conn, "SELECT * FROM tasks WHERE id=?", (task_id,))
    if not value: raise ValueError("Task not found")
    value["tags"] = json.loads(value.pop("tags_json") or "[]")
    return value


def create(
    user_home: Path,
    title: str,
    description: str = "",
    priority: str | int = "normal",
    owner: str | None = None,
    *,
    risk_class: str = "R1",
    task_type: str = "task",
    source: str = "local",
    source_id: str | None = None,
    tags: list[str] | None = None,
    acceptance_criteria: str = "",
    allow_duplicate: bool = False,
    task_id: str | None = None,
) -> dict[str, Any]:
    if not title.strip(): raise ValueError("title is required")
    tags = list(dict.fromkeys(x.strip() for x in (tags or []) if x.strip()))
    conn = connect_write(user_home)
    try:
        normalized = normalize_title(title)
        existing = rows(conn, "SELECT id,title,status FROM tasks WHERE status NOT IN ('completed','closed','cancelled','rejected')")
        duplicate = next((row for row in existing if normalize_title(row["title"]) == normalized), None)
        if duplicate and not allow_duplicate:
            return {"decision":"block","error":"duplicate-task","duplicate_of":duplicate["id"],"title":duplicate["title"],"status":duplicate["status"]}
        tid = task_id or new_id("task")
        now = utc_now()
        duplicate_of = duplicate["id"] if duplicate else None
        status = "backlog"
        conn.execute(
            """INSERT INTO tasks(id,title,description,status,priority,owner,source,source_id,risk_class,task_type,tags_json,acceptance_criteria,duplicate_of,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tid,title.strip(),description.strip(),status,_priority(priority),owner,source,source_id,risk_class,task_type,json.dumps(tags),acceptance_criteria.strip(),duplicate_of,now,now),
        )
        append_event(conn,"task.created",{"title":title.strip(),"source":source,"owner":owner,"duplicate_of":duplicate_of},task_id=tid)
        conn.commit()
        return {"decision":"pass","task_id":tid,"status":status,"title":title.strip(),"source":source,"owner":owner,"duplicate_of":duplicate_of}
    finally: conn.close()


def _list(user_home: Path, where: str = "1=1", params: tuple[Any,...] = (), *, owner: str | None=None, query: str | None=None, status_filter: str | None=None, limit: int | None=None) -> list[dict[str, Any]]:
    conn=connect_read(user_home)
    if conn is None: return []
    sql="SELECT * FROM tasks WHERE "+where; values=list(params)
    if owner: sql+=" AND owner=?"; values.append(owner)
    if status_filter: sql+=" AND status=?"; values.append(status_filter)
    if query:
        needle=f"%{query.casefold()}%"
        sql+=" AND (lower(title) LIKE ? OR lower(description) LIKE ? OR lower(COALESCE(source,'')) LIKE ? OR lower(COALESCE(owner,'')) LIKE ? OR lower(tags_json) LIKE ?)"
        values.extend([needle]*5)
    priority_order="CASE priority WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'normal' THEN 2 ELSE 1 END"
    sql+=f" ORDER BY {priority_order} DESC, updated_at DESC"
    if limit: sql+=" LIMIT ?"; values.append(limit)
    result=rows(conn,sql,values); conn.close()
    for row in result: row["tags"]=json.loads(row.pop("tags_json") or "[]")
    return result


def list_all(user_home:Path,**kwargs)->list[dict[str,Any]]: return _list(user_home,**kwargs)
def list_open(user_home:Path,owner:str|None=None,**kwargs)->list[dict[str,Any]]:
    placeholders=",".join("?" for _ in OPEN_STATUSES)
    return _list(user_home,f"status IN ({placeholders})",tuple(sorted(OPEN_STATUSES)),owner=owner,**kwargs)
def list_closed(user_home:Path,**kwargs)->list[dict[str,Any]]:
    placeholders=",".join("?" for _ in CLOSED_STATUSES)
    return _list(user_home,f"status IN ({placeholders})",tuple(sorted(CLOSED_STATUSES)),**kwargs)


def show(user_home:Path,task_id:str|None=None,limit:int=5)->dict[str,Any]:
    if not task_id:
        options=list_open(user_home,limit=limit)
        return {"decision":"pass","requires_user_selection":True,"open_tasks":options,"count":len(options)}
    conn=connect_read(user_home)
    if conn is None: raise ValueError("Task not found")
    task=_task(conn,task_id)
    task["work_units"]=rows(conn,"SELECT * FROM work_units WHERE task_id=? ORDER BY created_at",(task_id,))
    task["leases"]=rows(conn,"SELECT id,work_unit_id,task_id,owner,session_id,status,issued_at,heartbeat_at,expires_at,released_at,revision FROM leases WHERE task_id=? ORDER BY issued_at",(task_id,))
    task["progress_events"]=rows(conn,"SELECT * FROM progress_events WHERE task_id=? ORDER BY created_at",(task_id,))
    task["attempts"]=rows(conn,"SELECT * FROM attempts WHERE task_id=? ORDER BY created_at",(task_id,))
    task["evidence"]=rows(conn,"SELECT * FROM evidence WHERE task_id=? ORDER BY created_at",(task_id,))
    task["meetings"]=rows(conn,"SELECT * FROM meetings WHERE task_id=? ORDER BY created_at",(task_id,))
    task["tests"]=rows(conn,"SELECT * FROM test_results WHERE task_id=? ORDER BY created_at",(task_id,))
    task["audits"]=rows(conn,"SELECT * FROM audits WHERE task_id=? ORDER BY created_at",(task_id,))
    task["validations"]=rows(conn,"SELECT id,source_revision,applied_revision,trigger_action,policy,status,validation_task_id,validation_meeting_id,plan_digest,verdict,confidence,user_decision,decision_subject,decision_note,created_at,updated_at FROM task_validations WHERE task_id=? ORDER BY created_at",(task_id,))
    task["events"]=rows(conn,"SELECT seq,event_id,event_type,prev_hash,event_hash,created_at FROM events WHERE task_id=? ORDER BY seq",(task_id,))
    conn.close(); return {"decision":"pass","task":task}


def add_work_unit(user_home:Path,task_id:str,title:str,role:str="implementation",read_scope:list[str]|None=None,write_scope:list[str]|None=None)->dict[str,Any]:
    conn=connect_write(user_home)
    try:
        _task(conn,task_id); wid=new_id("wu"); now=utc_now()
        conn.execute("INSERT INTO work_units(id,task_id,title,role,read_scope_json,write_scope_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(wid,task_id,title,role,json.dumps(read_scope or []),json.dumps(write_scope or []),now,now))
        conn.execute("UPDATE tasks SET status='ready',revision=revision+1,updated_at=? WHERE id=?",(now,task_id))
        append_event(conn,"work_unit.created",{"title":title,"role":role},task_id=task_id,work_unit_id=wid); conn.commit()
        return {"decision":"pass","work_unit_id":wid,"task_id":task_id,"status":"ready"}
    finally: conn.close()


def _parse_time(value:str)->datetime: return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)


def claim_work_unit(
    user_home:Path,
    work_unit_id:str,
    owner:str,
    session_id:str,
    ttl_seconds:int=3600,
    *,
    enforce_validation:bool=False,
    trigger_action:str="claim",
)->dict[str,Any]:
    if not owner or not session_id: raise ValueError("owner and session_id are required")
    ttl=max(60,min(ttl_seconds,86400)); conn=connect_write(user_home)
    try:
        wu=one(conn,"SELECT * FROM work_units WHERE id=?",(work_unit_id,))
        if not wu: raise ValueError("Work unit not found")
        if enforce_validation:
            from .task_validation import gate as validation_gate
            validation=validation_gate(user_home,wu["task_id"],trigger_action)
            if validation.get("decision") != "pass":
                return validation
        active=one(conn,"SELECT * FROM leases WHERE work_unit_id=? AND status='active'",(work_unit_id,))
        now_dt=datetime.now(timezone.utc); now=now_dt.isoformat().replace('+00:00','Z')
        if active and _parse_time(active["expires_at"])>now_dt:
            raise ValueError("work unit already has an active lease")
        if active:
            conn.execute("UPDATE leases SET status='expired',released_at=? WHERE id=?",(now,active["id"]))
        token="IOTAI_LT_"+secrets.token_urlsafe(32); token_hash=hashlib.sha256(token.encode()).hexdigest(); lid=new_id("lease")
        expires=(now_dt+timedelta(seconds=ttl)).isoformat().replace('+00:00','Z')
        conn.execute("INSERT INTO leases(id,work_unit_id,task_id,owner,session_id,token_hash,issued_at,heartbeat_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?)",(lid,work_unit_id,wu["task_id"],owner,session_id,token_hash,now,now,expires))
        conn.execute("UPDATE work_units SET status='claimed',revision=revision+1,updated_at=? WHERE id=?",(now,work_unit_id))
        conn.execute("UPDATE tasks SET status='claimed',owner=COALESCE(owner,?),revision=revision+1,updated_at=? WHERE id=?",(owner,now,wu["task_id"]))
        append_event(conn,"lease.issued",{"lease_id":lid,"owner":owner,"session_id":session_id,"expires_at":expires},task_id=wu["task_id"],work_unit_id=work_unit_id); conn.commit()
        return {"decision":"pass","lease_id":lid,"lease_token":token,"work_unit_id":work_unit_id,"task_id":wu["task_id"],"owner":owner,"session_id":session_id,"expires_at":expires,"revision":1}
    finally: conn.close()


def _verified_lease(conn,lease_id:str,token:str|None=None)->dict[str,Any]:
    lease=one(conn,"SELECT * FROM leases WHERE id=?",(lease_id,))
    if not lease: raise ValueError("Lease not found")
    if lease["status"]!="active": raise ValueError("lease is not active")
    if _parse_time(lease["expires_at"])<=datetime.now(timezone.utc): raise ValueError("lease expired")
    if token is not None and hashlib.sha256(token.encode()).hexdigest()!=lease["token_hash"]: raise PermissionError("invalid lease token")
    return lease


def heartbeat(user_home:Path,lease_id:str,lease_token:str,ttl_seconds:int=3600)->dict[str,Any]:
    conn=connect_write(user_home)
    try:
        lease=_verified_lease(conn,lease_id,lease_token); now_dt=datetime.now(timezone.utc); now=now_dt.isoformat().replace('+00:00','Z'); expires=(now_dt+timedelta(seconds=max(60,min(ttl_seconds,86400)))).isoformat().replace('+00:00','Z')
        conn.execute("UPDATE leases SET heartbeat_at=?,expires_at=?,revision=revision+1 WHERE id=?",(now,expires,lease_id)); append_event(conn,"lease.heartbeat",{"lease_id":lease_id,"expires_at":expires},task_id=lease["task_id"],work_unit_id=lease["work_unit_id"]); conn.commit(); return {"decision":"pass","lease_id":lease_id,"expires_at":expires}
    finally: conn.close()


def record_progress(
    user_home:Path,
    task_id:str,
    stage:str,
    percent:int,
    summary:str,
    work_unit_id:str|None=None,
    *,
    basis:str="manual-estimate",
    evidence_ids:list[str]|None=None,
    observed_steps:int|None=None,
    total_steps:int|None=None,
    confidence:str="medium",
)->dict[str,Any]:
    if percent<0 or percent>100: raise ValueError("percent must be 0..100")
    if not stage.strip() or not summary.strip(): raise ValueError("stage and summary are required")
    if basis not in {"manual-estimate","observed-steps","verified-criteria","deterministic-tests"}:
        raise ValueError("invalid progress basis")
    if confidence not in {"low","medium","high"}: raise ValueError("invalid progress confidence")
    if observed_steps is not None or total_steps is not None:
        if observed_steps is None or total_steps is None or total_steps < 1 or observed_steps < 0 or observed_steps > total_steps:
            raise ValueError("observed_steps/total_steps are invalid")
        derived=round((observed_steps/total_steps)*100)
        if basis in {"observed-steps","verified-criteria"} and derived != percent:
            raise ValueError(f"percent must equal derived progress ({derived}) for basis {basis}")
    conn=connect_write(user_home)
    try:
        task=_task(conn,task_id)
        current_status=str(task.get("status") or "")
        if current_status in CLOSED_STATUSES:
            raise PermissionError(f"progress is forbidden for terminal task status: {current_status}")
        # Progress is telemetry, never authority. Founder-gated work must not be reopened.
        next_status=current_status if current_status=="awaiting_founder" else "active"
        pid=new_id("prg"); now=utc_now(); conn.execute("INSERT INTO progress_events VALUES(?,?,?,?,?,?,?)",(pid,task_id,work_unit_id,stage,percent,summary,now))
        conn.execute("UPDATE tasks SET status=?,engineering_stage=?,engineering_progress=?,task_progress=MAX(task_progress,?),revision=revision+1,updated_at=? WHERE id=?",(next_status,stage,percent,percent,now,task_id))
        if work_unit_id and current_status!="awaiting_founder":
            conn.execute("UPDATE work_units SET status='active',engineering_stage=?,engineering_progress=?,revision=revision+1,updated_at=? WHERE id=?",(stage,percent,now,work_unit_id))
        payload={
            "stage":stage,"percent":percent,"summary":summary,"basis":basis,
            "evidence_ids":list(evidence_ids or []),"observed_steps":observed_steps,
            "total_steps":total_steps,"confidence":confidence,"status_preserved":current_status=="awaiting_founder",
            "completion_authority":False,
        }
        append_event(conn,"progress.recorded",payload,task_id=task_id,work_unit_id=work_unit_id)
        conn.commit()
        return {"decision":"pass","progress_id":pid,"task_id":task_id,"percent":percent,"stage":stage,"basis":basis,"status":next_status,"completion_authority":False}
    finally: conn.close()


def add_evidence(user_home:Path,task_id:str,artifact:Path,artifact_sha256:str|None=None,kind:str="artifact",work_unit_id:str|None=None,command:list[str]|None=None,exit_code:int|None=None,passed:bool|None=None,metadata:dict[str,Any]|None=None)->dict[str,Any]:
    artifact=artifact.expanduser().resolve()
    if not artifact.is_file() or artifact.is_symlink(): raise ValueError("evidence artifact must be a regular non-symlink file")
    actual=sha256_file(artifact, allowed_roots=[user_home, Path.cwd().resolve(), artifact.parent.resolve()], max_bytes=None)
    if artifact_sha256 and artifact_sha256!=actual: raise ValueError("evidence SHA-256 mismatch")
    conn=connect_write(user_home)
    try:
        _task(conn,task_id); eid=new_id("evd"); now=utc_now(); conn.execute("INSERT INTO evidence(id,task_id,work_unit_id,kind,artifact_path,artifact_sha256,command_json,exit_code,passed,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(eid,task_id,work_unit_id,kind,str(artifact),actual,json.dumps(command) if command else None,exit_code,None if passed is None else int(passed),json.dumps(metadata or {},sort_keys=True),now)); append_event(conn,"evidence.registered",{"evidence_id":eid,"kind":kind,"sha256":actual},task_id=task_id,work_unit_id=work_unit_id); conn.commit(); return {"decision":"pass","evidence_id":eid,"artifact":str(artifact),"artifact_sha256":actual}
    finally: conn.close()


def release_lease(user_home:Path,lease_id:str,lease_token:str|None=None,reason:str="released")->dict[str,Any]:
    conn=connect_write(user_home)
    try:
        lease=_verified_lease(conn,lease_id,lease_token); now=utc_now(); conn.execute("UPDATE leases SET status='released',released_at=?,revision=revision+1 WHERE id=?",(now,lease_id)); conn.execute("UPDATE work_units SET status='ready',revision=revision+1,updated_at=? WHERE id=?",(now,lease["work_unit_id"])); append_event(conn,"lease.released",{"lease_id":lease_id,"reason":reason},task_id=lease["task_id"],work_unit_id=lease["work_unit_id"]); conn.commit(); return {"decision":"pass","lease_id":lease_id,"status":"released"}
    finally: conn.close()


def submit_task(
    user_home:Path,
    task_id:str,
    work_unit_id:str|None=None,
    lease_id:str|None=None,
    lease_token:str|None=None,
    result_summary:str="Technical work submitted for review",
) -> dict[str,Any]:
    """Submit technical work only after the independent audit passes.

    The former implementation moved a task to ``awaiting_founder`` before the
    audit and left it there even when hard gates failed.  This function now uses
    a verification phase: leases are released, the task is audited at 100%
    telemetry, and only an ``approve_technical`` result advances to the
    founder-only queue.  Failed audits return the task to ``needs-work``.
    """
    conn=connect_write(user_home)
    try:
        task=_task(conn,task_id)
        if task["status"] in CLOSED_STATUSES:
            raise PermissionError(f"submit is forbidden for terminal task status: {task['status']}")
        if lease_id:
            _verified_lease(conn,lease_id,lease_token)
        now=utc_now(); pid=new_id("prg")
        conn.execute(
            "INSERT INTO progress_events VALUES(?,?,?,?,?,?,?)",
            (pid,task_id,work_unit_id,"verification",100,"Technical verification candidate ready",now),
        )
        conn.execute(
            "UPDATE tasks SET status='verification',engineering_stage='verification',engineering_progress=100,task_progress=100,result_summary=?,revision=revision+1,updated_at=? WHERE id=?",
            (result_summary,now,task_id),
        )
        if work_unit_id:
            conn.execute(
                "UPDATE work_units SET status='review',engineering_stage='verification',engineering_progress=100,revision=revision+1,updated_at=? WHERE id=?",
                (now,work_unit_id),
            )
        active=rows(conn,"SELECT * FROM leases WHERE task_id=? AND status='active'",(task_id,))
        for lease in active:
            conn.execute("UPDATE leases SET status='released',released_at=?,revision=revision+1 WHERE id=?",(now,lease["id"]))
            append_event(conn,"lease.released",{"lease_id":lease["id"],"reason":"pre-submit-audit"},task_id=task_id,work_unit_id=lease["work_unit_id"])
        append_event(conn,"task.verification_candidate",{"result_summary":result_summary},task_id=task_id,work_unit_id=work_unit_id)
        conn.commit()
    finally:
        conn.close()

    export_workspace(user_home,task_id=task_id)
    from .audit import audit_task
    audit=audit_task(user_home,task_id,record=True)
    approved=audit["decision"]=="approve_technical"
    conn=connect_write(user_home)
    try:
        now=utc_now()
        if approved:
            status="awaiting_founder"
            stage="complete"
            engineering_progress=100
            task_progress=100
            event="task.submitted"
            event_payload={"status":status,"result_summary":result_summary,"audit_id":audit.get("audit_id")}
        else:
            status="needs-work"
            stage="verification-needs-work"
            engineering_progress=95
            task_progress=95
            event="task.submission_rejected"
            event_payload={"status":status,"audit_id":audit.get("audit_id"),"findings":audit.get("findings",[])}
        conn.execute(
            "UPDATE tasks SET status=?,engineering_stage=?,engineering_progress=?,task_progress=?,revision=revision+1,updated_at=? WHERE id=?",
            (status,stage,engineering_progress,task_progress,now,task_id),
        )
        if work_unit_id:
            conn.execute(
                "UPDATE work_units SET status=?,engineering_stage=?,engineering_progress=?,revision=revision+1,updated_at=? WHERE id=?",
                ("review" if approved else "ready",stage,engineering_progress,now,work_unit_id),
            )
        append_event(conn,event,event_payload,task_id=task_id,work_unit_id=work_unit_id)
        conn.commit()
    finally:
        conn.close()
    export_workspace(user_home,task_id=task_id)
    return {
        "decision":"pass" if approved else "needs-work",
        "task_id":task_id,
        "status":status,
        "audit":audit,
        "founder_queue_entered":approved,
    }


def complete(user_home:Path,task_id:str,result:str)->dict[str,Any]:
    """Deprecated fail-closed compatibility surface.

    Technical executors may submit evidence and enter ``awaiting_founder`` but
    may never close their own work.  Final accept/reject/rework remains a
    separately authenticated founder decision owned by the authoritative task
    backend.
    """
    conn=connect_read(user_home)
    try:
        task=_task(conn,task_id) if conn is not None else None
    finally:
        if conn is not None: conn.close()
    return {
        "decision":"block",
        "reason":"founder-final-decision-required",
        "task_id":task_id,
        "status":task.get("status") if task else "unknown",
        "requested_result":result,
        "mutation_performed":False,
        "next_actor":"founder or authoritative backend owner",
    }


def export_xlsx(user_home:Path,output:Path)->dict[str,Any]: return export_workspace(user_home,output)


def workspace_status(user_home:Path)->dict[str,Any]:
    conn=connect_read(user_home)
    if conn is None: return {"decision":"pass","backend":"standalone","configured":False,"integrity":"not-created","schema_version":None,"counts":{}}
    integrity=conn.execute("PRAGMA quick_check").fetchone()[0]; schema=one(conn,"SELECT value FROM meta WHERE key='schema_version'")
    tables=("tasks","work_units","leases","evidence","events","attempts","meetings","test_results","audits","knowledge_items","contributions","task_validations")
    counts={name:int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]) for name in tables}; conn.close()
    return {"decision":"pass" if integrity=="ok" else "block","backend":"standalone","configured":True,"integrity":integrity,"schema_version":schema["value"] if schema else None,"counts":counts,"event_chain":verify_event_chain(user_home),"excel":{"path":str(excel_path(user_home)),"exists":excel_path(user_home).exists(),"manifest":str(excel_manifest_path(user_home))}}


def solve_all_plan(
    user_home:Path,
    query:str|None=None,
    confirm_critical:bool=False,
    max_tasks:int|None=None,
    *,
    require_validated:bool=False,
)->dict[str,Any]:
    candidates=list_open(user_home,query=query)
    selected=[]; skipped=[]
    for task in candidates:
        reason=None
        if task.get("duplicate_of"): reason="duplicate"
        elif task["status"] in {"claimed","active","awaiting_founder","meeting","blocked"}: reason=f"status:{task['status']}"
        elif task["priority"]=="critical" and not confirm_critical: reason="critical-confirmation-required"
        elif require_validated:
            from .task_validation import gate as validation_gate
            validation=validation_gate(user_home,task["id"],"solve-all")
            if validation.get("decision") != "pass":
                reason="task-validation-required"
        if reason:
            item={"task_id":task["id"],"reason":reason}
            if reason=="task-validation-required": item["validation"]=validation
            skipped.append(item)
        else: selected.append(task)
        if max_tasks and len(selected)>=max_tasks: break
    eligible=len(selected)
    return {
        "decision":"plan" if eligible else "noop",
        "reason":None if eligible else "eligible-count-zero",
        "query":query,
        "selected":selected,
        "skipped":skipped,
        "eligible_count":eligible,
        "skipped_count":len(skipped),
        "requires_user_confirmation":bool(eligible),
        "apply":False,
        "provider_calls":0,
    }
