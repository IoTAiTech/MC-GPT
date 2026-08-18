# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Canonical standalone task, meeting, evidence and telemetry workspace."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .paths import data_root, db_path
from .util import utc_now

SCHEMA_VERSION = 6
CLOSED_STATUSES = {"completed", "closed", "cancelled", "rejected"}
OPEN_STATUSES = {"backlog", "queued", "ready", "claimed", "active", "needs-work", "blocked", "meeting", "awaiting_founder"}

SCHEMA = r"""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(
 id TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL,
 priority TEXT NOT NULL DEFAULT 'normal',
 owner TEXT,
 source TEXT NOT NULL DEFAULT 'local',
 source_id TEXT,
 risk_class TEXT NOT NULL DEFAULT 'R1',
 task_type TEXT NOT NULL DEFAULT 'task',
 tags_json TEXT NOT NULL DEFAULT '[]',
 acceptance_criteria TEXT NOT NULL DEFAULT '',
 duplicate_of TEXT,
 engineering_stage TEXT NOT NULL DEFAULT 'discovery',
 engineering_progress INTEGER NOT NULL DEFAULT 0 CHECK(engineering_progress BETWEEN 0 AND 100),
 task_progress INTEGER NOT NULL DEFAULT 0 CHECK(task_progress BETWEEN 0 AND 100),
 revision INTEGER NOT NULL DEFAULT 1,
 blocker TEXT,
 final_decision TEXT,
 result_summary TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 FOREIGN KEY(duplicate_of) REFERENCES tasks(id)
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner);
CREATE INDEX IF NOT EXISTS idx_tasks_source ON tasks(source,source_id);
CREATE TABLE IF NOT EXISTS work_units(
 id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL,
 title TEXT NOT NULL,
 role TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'ready',
 provider TEXT,
 model_requested TEXT,
 model_served TEXT,
 engineering_stage TEXT NOT NULL DEFAULT 'discovery',
 engineering_progress INTEGER NOT NULL DEFAULT 0 CHECK(engineering_progress BETWEEN 0 AND 100),
 revision INTEGER NOT NULL DEFAULT 1,
 read_scope_json TEXT NOT NULL DEFAULT '[]',
 write_scope_json TEXT NOT NULL DEFAULT '[]',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_wu_task ON work_units(task_id);
CREATE TABLE IF NOT EXISTS leases(
 id TEXT PRIMARY KEY,
 work_unit_id TEXT NOT NULL,
 task_id TEXT NOT NULL,
 owner TEXT NOT NULL,
 session_id TEXT NOT NULL,
 token_hash TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active',
 issued_at TEXT NOT NULL,
 heartbeat_at TEXT NOT NULL,
 expires_at TEXT NOT NULL,
 released_at TEXT,
 revision INTEGER NOT NULL DEFAULT 1,
 FOREIGN KEY(work_unit_id) REFERENCES work_units(id) ON DELETE CASCADE,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_lease_per_wu ON leases(work_unit_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS progress_events(
 id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL,
 work_unit_id TEXT,
 stage TEXT NOT NULL,
 percent INTEGER NOT NULL CHECK(percent BETWEEN 0 AND 100),
 summary TEXT NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
 FOREIGN KEY(work_unit_id) REFERENCES work_units(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS attempts(
 id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL,
 work_unit_id TEXT,
 run_id TEXT,
 provider TEXT,
 role TEXT,
 stage TEXT NOT NULL,
 status TEXT NOT NULL,
 model_requested TEXT,
 model_served TEXT,
 request_or_job_id TEXT,
 auth_route TEXT,
 input_tokens INTEGER,
 cached_tokens INTEGER,
 output_tokens INTEGER,
 reasoning_tokens INTEGER,
 latency_ms INTEGER,
 fallback_used INTEGER NOT NULL DEFAULT 0,
 failure_class TEXT,
 retry_after TEXT,
 output_sha256 TEXT,
 created_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
 FOREIGN KEY(work_unit_id) REFERENCES work_units(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_task ON attempts(task_id);
CREATE TABLE IF NOT EXISTS evidence(
 id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL,
 work_unit_id TEXT,
 kind TEXT NOT NULL,
 artifact_path TEXT NOT NULL,
 artifact_sha256 TEXT NOT NULL,
 command_json TEXT,
 exit_code INTEGER,
 passed INTEGER,
 metadata_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
 FOREIGN KEY(work_unit_id) REFERENCES work_units(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_task ON evidence(task_id);
CREATE TABLE IF NOT EXISTS meetings(
 id TEXT PRIMARY KEY,
 task_id TEXT,
 topic TEXT NOT NULL,
 depth TEXT NOT NULL,
 effort TEXT NOT NULL,
 status TEXT NOT NULL,
 requested_seats INTEGER NOT NULL,
 substantive_seats INTEGER NOT NULL DEFAULT 0,
 quorum INTEGER NOT NULL,
 rounds INTEGER NOT NULL,
 synthesis TEXT,
 final_decision TEXT,
 user_approved INTEGER NOT NULL DEFAULT 0,
 consultation_sha256 TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS meeting_contributions(
 id TEXT PRIMARY KEY,
 meeting_id TEXT NOT NULL,
 task_id TEXT,
 seat TEXT NOT NULL,
 kind TEXT NOT NULL,
 round_no INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL,
 text TEXT NOT NULL DEFAULT '',
 text_sha256 TEXT,
 model_requested TEXT,
 model_served TEXT,
 request_or_job_id TEXT,
 auth_route TEXT,
 input_tokens INTEGER,
 cached_tokens INTEGER,
 output_tokens INTEGER,
 reasoning_tokens INTEGER,
 latency_ms INTEGER,
 fallback_used INTEGER NOT NULL DEFAULT 0,
 failure_class TEXT,
 quality_score REAL,
 quality_basis TEXT,
 created_at TEXT NOT NULL,
 FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_meeting_contrib ON meeting_contributions(meeting_id,kind,round_no);
CREATE TABLE IF NOT EXISTS meeting_kpis(
 id TEXT PRIMARY KEY,
 meeting_id TEXT NOT NULL,
 name TEXT NOT NULL,
 target TEXT NOT NULL,
 measurement TEXT NOT NULL,
 mandatory INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS meeting_cases(
 id TEXT PRIMARY KEY,
 meeting_id TEXT NOT NULL,
 case_type TEXT NOT NULL CHECK(case_type IN ('use','test','failure')),
 ordinal INTEGER NOT NULL,
 title TEXT NOT NULL,
 description TEXT NOT NULL,
 expected TEXT NOT NULL,
 mandatory INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 UNIQUE(meeting_id,case_type,ordinal),
 FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS test_results(
 id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL,
 work_unit_id TEXT,
 run_id TEXT,
 tier TEXT NOT NULL,
 argv_json TEXT NOT NULL,
 command_sha256 TEXT NOT NULL,
 exit_code INTEGER NOT NULL,
 passed INTEGER NOT NULL,
 failed INTEGER NOT NULL DEFAULT 0,
 skipped INTEGER NOT NULL DEFAULT 0,
 duration_ms INTEGER NOT NULL,
 output_path TEXT,
 output_sha256 TEXT,
 decision TEXT NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
 FOREIGN KEY(work_unit_id) REFERENCES work_units(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_tests_task ON test_results(task_id,tier);
CREATE TABLE IF NOT EXISTS audits(
 id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL,
 decision TEXT NOT NULL,
 gate_score REAL NOT NULL,
 gates_json TEXT NOT NULL,
 findings_json TEXT NOT NULL,
 evidence_sha256 TEXT,
 created_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS knowledge_items(
 id TEXT PRIMARY KEY,
 source_type TEXT NOT NULL,
 source_id TEXT NOT NULL,
 task_id TEXT,
 title TEXT NOT NULL,
 content TEXT NOT NULL,
 content_sha256 TEXT NOT NULL,
 classification TEXT NOT NULL,
 tags_json TEXT NOT NULL,
 token_estimate INTEGER NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS task_validations(
 id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL,
 source_revision INTEGER NOT NULL,
 applied_revision INTEGER,
 trigger_action TEXT NOT NULL,
 policy TEXT NOT NULL CHECK(policy IN ('optional','recommended','required')),
 status TEXT NOT NULL,
 validation_task_id TEXT,
 validation_meeting_id TEXT,
 original_json TEXT NOT NULL,
 original_sha256 TEXT NOT NULL,
 proposal_json TEXT,
 proposal_sha256 TEXT,
 plan_digest TEXT,
 verdict TEXT,
 confidence REAL,
 requested_roles_json TEXT NOT NULL DEFAULT '[]',
 providers_json TEXT NOT NULL DEFAULT '[]',
 context_manifest_json TEXT NOT NULL DEFAULT '{}',
 user_decision TEXT,
 decision_subject TEXT,
 decision_note TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
 FOREIGN KEY(validation_task_id) REFERENCES tasks(id) ON DELETE SET NULL,
 FOREIGN KEY(validation_meeting_id) REFERENCES meetings(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_task_validation_task ON task_validations(task_id,created_at);
CREATE INDEX IF NOT EXISTS idx_task_validation_status ON task_validations(status);

CREATE TABLE IF NOT EXISTS calendar_events(
 id TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 topic TEXT NOT NULL,
 topic_sha256 TEXT NOT NULL,
 kind TEXT NOT NULL DEFAULT 'meeting',
 surface TEXT,
 project_id TEXT,
 org_id TEXT,
 starts_at TEXT NOT NULL,
 ends_at TEXT,
 timezone TEXT NOT NULL DEFAULT 'Europe/Berlin',
 all_day INTEGER NOT NULL DEFAULT 0,
 rrule TEXT,
 rrule_until TEXT,
 parent_event_id TEXT,
 requested_seats TEXT NOT NULL,
 quorum INTEGER NOT NULL DEFAULT 2,
 mode TEXT NOT NULL DEFAULT 'consult',
 depth TEXT NOT NULL DEFAULT 'deep',
 effort TEXT NOT NULL DEFAULT 'high',
 privacy_policy TEXT NOT NULL DEFAULT 'strict',
 auth_mode TEXT NOT NULL DEFAULT 'auto',
 synthesizer_seat TEXT,
 max_parallel INTEGER,
 timeout_seconds INTEGER,
 status TEXT NOT NULL DEFAULT 'scheduled',
 auto_start INTEGER NOT NULL DEFAULT 0,
 meeting_id TEXT,
 last_run_at TEXT,
 next_run_at TEXT,
 failure_reason TEXT,
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE SET NULL,
 FOREIGN KEY(parent_event_id) REFERENCES calendar_events(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_calendar_next_run ON calendar_events(status,next_run_at);
CREATE INDEX IF NOT EXISTS idx_calendar_scope ON calendar_events(org_id,project_id,starts_at);
CREATE TABLE IF NOT EXISTS calendar_participants(
 id TEXT PRIMARY KEY,
 event_id TEXT NOT NULL,
 seat TEXT NOT NULL,
 seat_type TEXT NOT NULL,
 surface TEXT,
 required INTEGER NOT NULL DEFAULT 1,
 response_status TEXT NOT NULL DEFAULT 'invited',
 last_checked_at TEXT,
 created_at TEXT NOT NULL,
 UNIQUE(event_id,seat),
 FOREIGN KEY(event_id) REFERENCES calendar_events(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS calendar_reminders(
 id TEXT PRIMARY KEY,
 event_id TEXT NOT NULL,
 offset_minutes INTEGER NOT NULL,
 channel TEXT NOT NULL,
 target TEXT,
 sent_at TEXT,
 created_at TEXT NOT NULL,
 FOREIGN KEY(event_id) REFERENCES calendar_events(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS agent_seat_registry(
 seat TEXT PRIMARY KEY,
 surface TEXT NOT NULL,
 agent_id TEXT NOT NULL,
 display_name TEXT,
 capabilities TEXT NOT NULL DEFAULT '[]',
 model_binding TEXT,
 risk_class TEXT,
 control_level TEXT,
 endpoint_ref TEXT,
 reachable INTEGER NOT NULL DEFAULT 0,
 last_probe_at TEXT,
 last_probe_detail TEXT,
 refreshed_at TEXT NOT NULL,
 UNIQUE(surface,agent_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_seat_surface ON agent_seat_registry(surface,reachable);
CREATE TABLE IF NOT EXISTS meeting_webhooks(
 id TEXT PRIMARY KEY,
 subscriber TEXT NOT NULL,
 url TEXT NOT NULL,
 event_types TEXT NOT NULL,
 secret_ref TEXT,
 active INTEGER NOT NULL DEFAULT 1,
 last_delivery_at TEXT,
 last_status TEXT,
 consecutive_failures INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meeting_webhook_deliveries(
 id TEXT PRIMARY KEY,
 webhook_id TEXT NOT NULL,
 meeting_id TEXT,
 event_type TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 attempt INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL,
 response_code INTEGER,
 created_at TEXT NOT NULL,
 FOREIGN KEY(webhook_id) REFERENCES meeting_webhooks(id) ON DELETE CASCADE,
 FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS meeting_api_idempotency(
 idempotency_key TEXT PRIMARY KEY,
 operation TEXT NOT NULL,
 resource_id TEXT NOT NULL,
 response_json TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meeting_run_generations(
 meeting_id TEXT NOT NULL,
 generation INTEGER NOT NULL,
 status TEXT NOT NULL,
 claimed_at TEXT NOT NULL,
 sealed_at TEXT,
 PRIMARY KEY(meeting_id, generation),
 FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS one_running_meeting_generation
 ON meeting_run_generations(meeting_id) WHERE status='running';
CREATE TABLE IF NOT EXISTS meeting_seat_stages(
 meeting_id TEXT NOT NULL,
 generation INTEGER NOT NULL,
 seat TEXT NOT NULL,
 stage TEXT NOT NULL,
 status TEXT NOT NULL,
 result_json TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 PRIMARY KEY(meeting_id, generation, seat, stage)
);
CREATE TABLE IF NOT EXISTS founder_receipt_nonces(
 nonce TEXT PRIMARY KEY,
 audience TEXT NOT NULL,
 subject_id TEXT NOT NULL,
 digest TEXT NOT NULL,
 consumed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projection_jobs(
 id TEXT PRIMARY KEY,
 task_id TEXT,
 status TEXT NOT NULL,
 output_path TEXT,
 output_sha256 TEXT,
 manifest_path TEXT,
 error TEXT,
 attempts INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS events(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,
 event_id TEXT NOT NULL UNIQUE,
 task_id TEXT,
 work_unit_id TEXT,
 event_type TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 prev_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
 FOREIGN KEY(work_unit_id) REFERENCES work_units(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id,seq);
CREATE TABLE IF NOT EXISTS contributions(
 id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL,
 task_id TEXT,
 meeting_id TEXT,
 stage TEXT NOT NULL,
 provider TEXT NOT NULL,
 role TEXT,
 model_requested TEXT,
 model_served TEXT,
 request_id TEXT,
 auth_route TEXT,
 input_tokens INTEGER,
 cached_tokens INTEGER,
 output_tokens INTEGER,
 reasoning_tokens INTEGER,
 latency_ms INTEGER,
 retries INTEGER,
 timeout INTEGER,
 status TEXT NOT NULL,
 failure_class TEXT,
 retry_after TEXT,
 fallback_used INTEGER NOT NULL DEFAULT 0,
 correctness REAL,
 grounding REAL,
 unique_value REAL,
 actionability REAL,
 efficiency REAL,
 quality_total REAL,
 quality_score REAL,
 quality_basis TEXT,
 quality_rubric_version TEXT,
 accepted_findings INTEGER,
 rejected_findings INTEGER,
 created_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL,
 FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_contrib_created ON contributions(created_at);
CREATE INDEX IF NOT EXISTS idx_contrib_provider ON contributions(provider);
CREATE INDEX IF NOT EXISTS idx_contrib_run ON contributions(run_id);

CREATE TABLE IF NOT EXISTS graph_runs(
 id TEXT PRIMARY KEY,
 correlation_id TEXT NOT NULL UNIQUE,
 goal TEXT NOT NULL,
 risk_class TEXT NOT NULL,
 privacy_class TEXT NOT NULL,
 status TEXT NOT NULL,
 plan_digest TEXT,
 token_budget INTEGER NOT NULL,
 tokens_used INTEGER NOT NULL DEFAULT 0,
 wall_clock_seconds INTEGER NOT NULL,
 elapsed_ms INTEGER,
 max_parallel INTEGER NOT NULL,
 parallel_efficiency REAL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_nodes(
 id TEXT PRIMARY KEY,
 graph_id TEXT NOT NULL,
 role_id TEXT NOT NULL,
 node_type TEXT NOT NULL,
 stage TEXT NOT NULL,
 required INTEGER NOT NULL,
 status TEXT NOT NULL,
 provider TEXT,
 model_requested TEXT,
 model_served TEXT,
 effort_requested TEXT,
 effort_effective TEXT,
 latency_ms INTEGER,
 input_tokens INTEGER,
 cached_tokens INTEGER,
 output_tokens INTEGER,
 reasoning_tokens INTEGER,
 output_sha256 TEXT,
 failure_class TEXT,
 evidence_json TEXT NOT NULL DEFAULT '[]',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 FOREIGN KEY(graph_id) REFERENCES graph_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_graph ON graph_nodes(graph_id,stage,status);
CREATE TABLE IF NOT EXISTS role_bindings(
 id TEXT PRIMARY KEY,
 graph_id TEXT NOT NULL,
 node_id TEXT NOT NULL,
 role_id TEXT NOT NULL,
 contract_sha256 TEXT NOT NULL,
 provider_candidate_id TEXT,
 provider TEXT,
 model TEXT,
 authority_json TEXT NOT NULL,
 output_schema_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY(graph_id) REFERENCES graph_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS knowledge_artifact_receipts(
 id TEXT PRIMARY KEY,
 artifact_id TEXT NOT NULL UNIQUE,
 kind TEXT NOT NULL,
 visibility TEXT NOT NULL,
 privacy_class TEXT NOT NULL,
 content_sha256 TEXT NOT NULL,
 file_path TEXT NOT NULL,
 source_json TEXT NOT NULL,
 status TEXT NOT NULL,
 created_at TEXT NOT NULL
);
"""


def excel_path(user_home: Path) -> Path:
    return data_root(user_home) / "IOT-AI-Tasks.xlsx"


def excel_manifest_path(user_home: Path) -> Path:
    return data_root(user_home) / "IOT-AI-Tasks.xlsx.manifest.json"


def evidence_root(user_home: Path) -> Path:
    return data_root(user_home) / "evidence"


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
    conn.commit()


def connect_write(user_home: Path) -> sqlite3.Connection:
    path = db_path(user_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    from .product_boundary import assert_not_product_database
    assert_not_product_database(path, context="workspace.connect")
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    _initialize(conn)
    return conn


def connect_read(user_home: Path) -> sqlite3.Connection | None:
    path = db_path(user_home)
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def rows(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]


def one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def append_event(
    conn: sqlite3.Connection,
    event_type: str,
    payload: dict[str, Any],
    *,
    task_id: str | None = None,
    work_unit_id: str | None = None,
) -> dict[str, Any]:
    previous = conn.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
    prev_hash = str(previous[0]) if previous else "0" * 64
    event_id = "evt-" + secrets.token_hex(12)
    created_at = utc_now()
    body = {
        "event_id": event_id,
        "task_id": task_id,
        "work_unit_id": work_unit_id,
        "event_type": event_type,
        "payload": payload,
        "prev_hash": prev_hash,
        "created_at": created_at,
    }
    event_hash = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO events(event_id,task_id,work_unit_id,event_type,payload_json,prev_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (event_id, task_id, work_unit_id, event_type, _canonical(payload), prev_hash, event_hash, created_at),
    )
    return {**body, "event_hash": event_hash}


def verify_event_chain(user_home: Path) -> dict[str, Any]:
    conn = connect_read(user_home)
    if conn is None:
        return {"decision": "pass", "events": 0, "head": "0" * 64}
    records = rows(conn, "SELECT * FROM events ORDER BY seq")
    conn.close()
    prev_hash = "0" * 64
    for record in records:
        payload = json.loads(record["payload_json"])
        body = {
            "event_id": record["event_id"],
            "task_id": record["task_id"],
            "work_unit_id": record["work_unit_id"],
            "event_type": record["event_type"],
            "payload": payload,
            "prev_hash": record["prev_hash"],
            "created_at": record["created_at"],
        }
        expected = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        if record["prev_hash"] != prev_hash or record["event_hash"] != expected:
            return {"decision": "block", "events": len(records), "failed_seq": record["seq"]}
        prev_hash = record["event_hash"]
    return {"decision": "pass", "events": len(records), "head": prev_hash}


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6)}"


def normalize_title(value: str) -> str:
    return " ".join(value.casefold().split())
