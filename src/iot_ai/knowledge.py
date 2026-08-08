# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .privacy import sanitize
from .util import atomic_text, utc_now
from .workspace import connect_read, connect_write, new_id, rows


def add_item(user_home:Path,source_type:str,source_id:str,task_id:str|None,title:str,content:str,classification:str="internal",tags:list[str]|None=None)->dict[str,Any]:
    result=sanitize(content,"strict")
    if result.decision=="block": raise ValueError("knowledge content contains blocked secret material")
    clean=result.text; digest=hashlib.sha256(clean.encode()).hexdigest(); kid=new_id("kb"); created=utc_now(); token_estimate=max(1,(len(clean)+3)//4)
    conn=connect_write(user_home)
    try:
        conn.execute("INSERT INTO knowledge_items VALUES(?,?,?,?,?,?,?,?,?,?,?)",(kid,source_type,source_id,task_id,title,clean,digest,classification,json.dumps(tags or []),token_estimate,created)); conn.commit()
    finally: conn.close()
    return {"knowledge_id":kid,"content_sha256":digest,"token_estimate":token_estimate,"redactions":result.findings}


def export_jsonl(user_home:Path,output:Path,audience:str="generic-rag",classification:str|None=None)->dict[str,Any]:
    conn=connect_read(user_home)
    records=[] if conn is None else rows(conn,"SELECT * FROM knowledge_items WHERE (? IS NULL OR classification=?) ORDER BY created_at",(classification,classification))
    if conn is not None: conn.close()
    lines=[]
    for row in records:
        payload={"schema":"iot-ai.knowledge-item.v1","audience":audience,"source_type":row["source_type"],"source_id":row["source_id"],"task_id":row["task_id"],"title":row["title"],"content":row["content"],"content_sha256":row["content_sha256"],"classification":row["classification"],"tags":json.loads(row["tags_json"]),"token_estimate":row["token_estimate"],"created_at":row["created_at"],"workflow_authority":False}
        lines.append(json.dumps(payload,ensure_ascii=False,sort_keys=True))
    atomic_text(output,"\n".join(lines)+("\n" if lines else ""),0o600)
    return {"decision":"pass","output":str(output),"items":len(lines),"audience":audience}
