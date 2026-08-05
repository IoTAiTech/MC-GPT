# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
"""Provider contribution telemetry with explicit missing-data semantics."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .util import utc_now
from .licensing import current
from .workspace import connect_read, connect_write, new_id, rows

WINDOWS={"1d":1,"3d":3,"7d":7,"14d":14,"30d":30,"90d":90,"180d":180,"365d":365}


def quality_score(correctness:float|None,grounding:float|None,unique_value:float|None,actionability:float|None,efficiency:float|None)->float|None:
    values=[correctness,grounding,unique_value,actionability,efficiency]
    if any(v is None for v in values): return None
    weights=[0.30,0.25,0.20,0.15,0.10]
    return round(sum(float(v)*w for v,w in zip(values,weights)),2)


def record(user_home:Path,data:dict[str,Any])->str:
    row=dict(data); row.setdefault("id",new_id("ctr")); row.setdefault("created_at",utc_now()); row.setdefault("fallback_used",0); row.setdefault("retries",0)
    row["quality_total"]=quality_score(*(row.get(k) for k in ("correctness","grounding","unique_value","actionability","efficiency")))
    cols=["id","run_id","task_id","meeting_id","stage","provider","role","model_requested","model_served","request_id","auth_route","input_tokens","cached_tokens","output_tokens","reasoning_tokens","latency_ms","retries","timeout","status","failure_class","retry_after","fallback_used","correctness","grounding","unique_value","actionability","efficiency","quality_total","quality_score","quality_basis","quality_rubric_version","accepted_findings","rejected_findings","created_at"]
    if not row.get("run_id") or not row.get("stage") or not row.get("provider") or not row.get("status"): raise ValueError("run_id, stage, provider and status are required")
    conn=connect_write(user_home)
    try:
        conn.execute(f"INSERT INTO contributions({','.join(cols)}) VALUES({','.join('?' for _ in cols)})", [row.get(c) for c in cols])
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, current().retention_days))).isoformat().replace("+00:00", "Z")
        conn.execute("DELETE FROM contributions WHERE created_at < ?", (cutoff,))
        conn.commit()
        return str(row["id"])
    finally:
        conn.close()


def update_quality(user_home:Path,contribution_id:str,quality:dict[str,Any])->None:
    conn=connect_write(user_home)
    try:
        conn.execute("UPDATE contributions SET quality_score=?,quality_basis=?,quality_rubric_version=?,accepted_findings=?,rejected_findings=? WHERE id=?",(quality.get("score"),quality.get("basis"),quality.get("rubric_version"),quality.get("accepted_findings"),quality.get("rejected_findings"),contribution_id)); conn.commit()
    finally: conn.close()


def by_run(user_home:Path,run_id:str)->list[dict[str,Any]]:
    conn=connect_read(user_home)
    if conn is None:return []
    result=rows(conn,"SELECT * FROM contributions WHERE run_id=? ORDER BY created_at",(run_id,)); conn.close(); return result


def summary(user_home:Path,window:str="7d")->list[dict[str,Any]]:
    if window not in WINDOWS: raise ValueError(f"unsupported window: {window}")
    conn=connect_read(user_home)
    if conn is None:return []
    since=(datetime.now(timezone.utc)-timedelta(days=WINDOWS[window])).isoformat().replace('+00:00','Z')
    result=rows(conn,"""SELECT provider,model_served,COUNT(*) contributions,
      SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) successes,
      SUM(CASE WHEN status!='pass' THEN 1 ELSE 0 END) failures,
      SUM(input_tokens) input_tokens,SUM(cached_tokens) cached_tokens,
      SUM(output_tokens) output_tokens,SUM(reasoning_tokens) reasoning_tokens,
      AVG(latency_ms) avg_latency_ms,AVG(COALESCE(quality_score,quality_total)) avg_quality,
      SUM(fallback_used) fallback_count
      FROM contributions WHERE created_at>=? GROUP BY provider,model_served ORDER BY provider,model_served""",(since,)); conn.close(); return result
