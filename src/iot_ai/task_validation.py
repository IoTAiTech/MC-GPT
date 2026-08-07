# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Pre-execution task validation and evidence-bound task optimisation.

The validation gate is intentionally separate from founder acceptance. It asks whether
an existing or user-supplied task should first be challenged by specialist coder roles
and eligible model-specific Ollama Cloud seats. The original task is immutable until a
human explicitly approves the proposed revision.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any, Callable

from .agentic import ProviderExecutor, run_goal
from .privacy import sanitize
from .projection import export_workspace
from .util import sha256_file, utc_now
from .workspace import append_event, connect_read, connect_write, new_id, one, rows

VALIDATION_POLICIES = {"optional", "recommended", "required"}
VALIDATION_ACTIONS = {"claim", "execute", "run", "go", "solve-all", "manual"}
RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}
TEXT_SUFFIXES = {
    ".txt", ".md", ".rst", ".log", ".json", ".jsonl", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".csv", ".py", ".js", ".ts", ".tsx",
    ".jsx", ".html", ".css", ".sql", ".sh", ".ps1",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
MAX_CONTEXT_BYTES = 2_000_000
MAX_TEXT_CHARS = 80_000


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _task_row(user_home: Path, task_id: str) -> dict[str, Any]:
    conn = connect_read(user_home)
    if conn is None:
        raise ValueError("Task not found")
    task = one(conn, "SELECT * FROM tasks WHERE id=?", (task_id,))
    conn.close()
    if not task:
        raise ValueError("Task not found")
    task["tags"] = json.loads(task.pop("tags_json") or "[]")
    return task


def validation_policy(task: dict[str, Any]) -> str:
    """Return the minimum review policy for the exact task revision."""
    tags = {str(value).casefold() for value in task.get("tags", [])}
    text = " ".join(
        [
            str(task.get("title") or ""),
            str(task.get("description") or ""),
            str(task.get("task_type") or ""),
            " ".join(tags),
        ]
    ).casefold()
    mandatory_terms = {
        "production", "deploy", "deployment", "release", "migration", "database",
        "security", "auth", "authorization", "identity", "credential", "secret",
        "customer", "tenant", "high-risk", "high risk", "safety", "firmware",
        "delete", "destructive", "rollback", "public github", "commercial",
    }
    risk = RISK_ORDER.get(str(task.get("risk_class") or "R1").upper(), 2)
    priority = str(task.get("priority") or "normal").casefold()
    if risk >= 3 or priority == "critical" or any(term in text for term in mandatory_terms):
        return "required"
    if risk == 2 or priority == "high":
        return "recommended"
    return "optional"


def _accepted_meeting(conn, task_id: str) -> dict[str, Any] | None:
    return one(
        conn,
        """SELECT * FROM meetings
           WHERE task_id=?
             AND user_approved=1
             AND substantive_seats>=quorum
             AND final_decision IN ('accept','approve','pass')
             AND consultation_sha256 IS NOT NULL
           ORDER BY updated_at DESC LIMIT 1""",
        (task_id,),
    )


def _latest_validation(conn, task_id: str) -> dict[str, Any] | None:
    return one(
        conn,
        "SELECT * FROM task_validations WHERE task_id=? ORDER BY created_at DESC LIMIT 1",
        (task_id,),
    )


def gate(user_home: Path, task_id: str, trigger_action: str = "claim") -> dict[str, Any]:
    """Read-only pre-execution gate. It never issues a lease or mutates a task."""
    trigger = trigger_action if trigger_action in VALIDATION_ACTIONS else "manual"
    conn = connect_read(user_home)
    if conn is None:
        raise ValueError("Task not found")
    task = one(conn, "SELECT * FROM tasks WHERE id=?", (task_id,))
    if not task:
        conn.close()
        raise ValueError("Task not found")
    task["tags"] = json.loads(task.get("tags_json") or "[]")
    policy = validation_policy(task)
    latest = _latest_validation(conn, task_id)
    accepted_meeting = _accepted_meeting(conn, task_id)
    conn.close()

    current_revision = int(task["revision"])
    if latest:
        latest_status = str(latest["status"])
        applied_revision = latest.get("applied_revision")
        source_revision = latest.get("source_revision")
        if latest_status == "approved" and int(applied_revision or -1) == current_revision:
            return {
                "decision": "pass",
                "gate": "task-validation",
                "source": "approved-validation",
                "task_id": task_id,
                "task_revision": current_revision,
                "validation_id": latest["id"],
                "plan_digest": latest.get("plan_digest"),
                "policy": policy,
                "trigger_action": trigger,
            }
        if latest_status == "skipped" and int(source_revision or -1) == current_revision:
            return {
                "decision": "pass",
                "gate": "task-validation",
                "source": "explicit-risk-acceptance",
                "task_id": task_id,
                "task_revision": current_revision,
                "validation_id": latest["id"],
                "policy": policy,
                "trigger_action": trigger,
                "warning": "Task validation was explicitly skipped; deterministic execution gates still apply.",
            }
    if accepted_meeting:
        return {
            "decision": "pass",
            "gate": "task-validation",
            "source": "approved-same-digest-meeting",
            "task_id": task_id,
            "task_revision": current_revision,
            "meeting_id": accepted_meeting["id"],
            "plan_digest": accepted_meeting["consultation_sha256"],
            "policy": policy,
            "trigger_action": trigger,
        }

    return {
        "decision": "requires-user-confirmation",
        "gate": "task-validation",
        "task_id": task_id,
        "task_revision": current_revision,
        "trigger_action": trigger,
        "policy": policy,
        "question": (
            "Do you want this task validated and optimised by specialist coder roles and "
            "eligible model-specific Ollama Cloud seats before execution?"
        ),
        "why": (
            "The review checks whether the reported problem is real, current, correctly scoped and "
            "technically sound; it challenges the request against registered evidence, optional "
            "screenshots/logs/docs, security/privacy/EU AI Act controls, and produces one digest-bound "
            "advanced execution prompt."
        ),
        "no_mutation": True,
        "next": {
            "review": f"iot-ai tasks prepare --task-id {task_id} --action review",
            "show": f"iot-ai tasks prepare --task-id {task_id} --action status",
            "skip": f"iot-ai tasks prepare --task-id {task_id} --action skip --subject <user> --reason <reason>",
        },
    }


def _context_item(path: Path, allowed_roots: list[Path]) -> dict[str, Any]:
    from .util import PathSecurityError
    try:
        candidate = path.expanduser()
        digest = sha256_file(candidate, allowed_roots=allowed_roots, max_bytes=MAX_CONTEXT_BYTES)
        candidate = candidate.resolve(strict=True)
    except PathSecurityError as exc:
        raise ValueError(f"context rejected: {exc}") from exc
    size = candidate.stat().st_size
    if size > MAX_CONTEXT_BYTES:
        raise ValueError(f"context file exceeds {MAX_CONTEXT_BYTES} bytes: {candidate.name}")
    suffix = candidate.suffix.casefold()
    item: dict[str, Any] = {
        "name": candidate.name,
        "sha256": digest,
        "size_bytes": size,
        "media_type": mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
        "kind": "image" if suffix in IMAGE_SUFFIXES else "text" if suffix in TEXT_SUFFIXES else "binary",
        "assessment": "metadata-only",
    }
    if suffix in TEXT_SUFFIXES:
        text = candidate.read_text(encoding="utf-8", errors="replace")[:MAX_TEXT_CHARS]
        screened = sanitize(text, "strict")
        if screened.decision == "block":
            raise PermissionError(f"context blocked by privacy gate ({','.join(screened.findings)}): {candidate.name}")
        item.update(
            {
                "assessment": "sanitized-text-included",
                "redactions": list(screened.findings),
                "excerpt": screened.text,
                "truncated": len(text) >= MAX_TEXT_CHARS or size > len(text.encode("utf-8", errors="ignore")),
            }
        )
    elif suffix in IMAGE_SUFFIXES:
        item["assessment"] = "vision-adapter-required"
        item["notice"] = (
            "Image is bound by digest. A vision-capable local/provider adapter must explicitly inspect it; "
            "otherwise the reviewer must report not-visually-assessed."
        )
    return item


def build_context_manifest(user_home: Path, task_id: str, context_files: list[Path] | None = None) -> dict[str, Any]:
    conn = connect_read(user_home)
    if conn is None:
        raise ValueError("Task not found")
    registered = rows(
        conn,
        "SELECT id,kind,artifact_path,artifact_sha256,metadata_json,created_at FROM evidence WHERE task_id=? ORDER BY created_at",
        (task_id,),
    )
    conn.close()
    roots = [Path(user_home).expanduser().resolve(), Path.cwd().resolve()]
    explicit = [_context_item(path, roots) for path in (context_files or [])]
    manifest = {
        "schema": "iot-ai.task-validation-context.v1",
        "task_id": task_id,
        "registered_evidence": [
            {
                "evidence_id": row["id"],
                "kind": row["kind"],
                "artifact_name": Path(row["artifact_path"]).name,
                "artifact_sha256": row["artifact_sha256"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in registered
        ],
        "explicit_context": explicit,
        "visual_items": sum(1 for item in explicit if item["kind"] == "image"),
        "text_items": sum(1 for item in explicit if item["kind"] == "text"),
        "binary_items": sum(1 for item in explicit if item["kind"] == "binary"),
        "created_at": utc_now(),
    }
    manifest["sha256"] = _digest({key: value for key, value in manifest.items() if key != "sha256"})
    return manifest


def _task_snapshot(task: dict[str, Any]) -> dict[str, Any]:
    return {
        key: task.get(key)
        for key in (
            "id", "title", "description", "status", "priority", "owner", "source", "source_id",
            "risk_class", "task_type", "tags", "acceptance_criteria", "engineering_stage",
            "engineering_progress", "task_progress", "revision", "blocker",
        )
    }


def _extract_plan(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    results = result.get("results") or {}
    final_gate = ((results.get("final-plan-gate") or {}).get("output") or (results.get("plan-acceptance") or {}).get("output") or {})
    selected_round = int(final_gate.get("selected_round") or 1)
    preferred = "plan-revision" if selected_round > 1 else "plan-synthesis"
    plan = ((results.get(preferred) or {}).get("parsed") or (results.get(preferred) or {}).get("output") or {})
    if not isinstance(plan, dict):
        plan = {"raw": str(plan)}
    final_audit = ((results.get("final-audit") or {}).get("output") or {})
    return plan, final_gate, final_audit


def _substantive_provider_families(result: dict[str, Any]) -> tuple[set[str], list[dict[str, Any]]]:
    """Return provider families that produced at least one non-empty, non-meta result."""
    families: set[str] = set()
    evidence: list[dict[str, Any]] = []
    for node_id, value in (result.get("results") or {}).items():
        if not isinstance(value, dict) or value.get("status") != "pass" or not value.get("provider"):
            continue
        parsed = value.get("parsed") or value.get("output")
        if not isinstance(parsed, dict) or not parsed:
            continue
        summary = str(parsed.get("summary") or parsed.get("position") or parsed.get("decision") or "").strip()
        findings = parsed.get("findings") or parsed.get("recommendations") or parsed.get("plan")
        if not summary and not findings:
            continue
        provider = str(value.get("provider")).strip().lower()
        model_served = str(value.get("model_served") or "").strip()
        families.add(provider)
        evidence.append(
            {
                "node_id": node_id,
                "provider": provider,
                "model_served": model_served or None,
                "request_id": value.get("request_id"),
                "decision": parsed.get("decision"),
            }
        )
    return families, evidence


def _advanced_prompt(task: dict[str, Any], plan: dict[str, Any], context_manifest: dict[str, Any], plan_digest: str | None) -> str:
    compact_plan = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    return f"""IOT-AI VALIDATED EXECUTION CONTRACT

TASK_ID: {task['id']}
SOURCE_REVISION: {task['revision']}
PLAN_DIGEST: {plan_digest or 'UNRESOLVED'}
RISK_CLASS: {task['risk_class']}
PRIORITY: {task['priority']}

WHY / ORIGINAL REQUEST
Title: {task['title']}
Description: {task['description']}

VALIDATION MISSION
1. Reconfirm the issue against current project evidence, visual context, documents and logs.
2. Do not implement claims that are outdated, duplicated, already solved, outside scope, or unsupported.
3. Preserve public/private/customer boundaries; do not expose secrets or customer data.
4. Use immutable specialist roles; provider/model selection follows live readiness and role fit.
5. Treat model opinions as proposals. Deterministic tests and evidence are authoritative.
6. Execute the smallest coherent change; preserve previously working behaviour.
7. Run functional, integration, negative-security, privacy, EU AI Act applicability, smoke,
   performance/stress and rollback tests appropriate to the task.
8. Store exact provider/model/effort/token/latency/quality receipts and a sanitised diagnostics bundle.
9. Submit technical completion for independent audit; never self-accept the founder decision.

CONTEXT_MANIFEST_SHA256: {context_manifest['sha256']}
VISUAL_ITEMS: {context_manifest['visual_items']}
TEXT_ITEMS: {context_manifest['text_items']}

CONSENSUS PLAN
{compact_plan}

ORIGINAL ACCEPTANCE CRITERIA
{task.get('acceptance_criteria') or 'Not supplied; use the measurable gates in the consensus plan.'}
""".strip()


def _proposal(task: dict[str, Any], plan: dict[str, Any], final_gate: dict[str, Any], final_audit: dict[str, Any], context_manifest: dict[str, Any]) -> dict[str, Any]:
    plan_digest = str(final_gate.get("plan_digest") or plan.get("plan_digest") or "") or None
    tags = list(dict.fromkeys([*task.get("tags", []), "task-validated", "evidence-bound-plan"] + ([f"plan:{plan_digest[:12]}"] if plan_digest else [])))
    plan_text = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    acceptance = "\n".join(
        filter(
            None,
            [
                str(task.get("acceptance_criteria") or "").strip(),
                f"Validation plan digest: {plan_digest}" if plan_digest else "Validation plan digest must be resolved before execution.",
                "The task must be reconfirmed against current code/runtime evidence before mutation.",
                "Required specialist roles must accept the same plan digest; empty/meta-only seats do not count.",
                "At least 10 use cases, 10 test cases and 10 failure cases must be present or explicitly justified as not applicable.",
                "Security, privacy, EU AI Act applicability, performance, rollback, evidence and independent-audit gates must pass.",
                "Technical completion is submitted for founder review and is not self-accepted.",
            ],
        )
    )
    return {
        "schema": "iot-ai.task-validation-proposal.v1",
        "optimized_title": str(task["title"]).strip(),
        "optimized_description": (
            f"{str(task.get('description') or '').strip()}\n\n"
            "VALIDATED TECHNICAL BRIEF\n"
            f"{plan_text}"
        ).strip(),
        "optimized_acceptance_criteria": acceptance,
        "optimized_priority": task["priority"],
        "optimized_risk_class": task["risk_class"],
        "optimized_tags": tags,
        "advanced_execution_prompt": _advanced_prompt(task, plan, context_manifest, plan_digest),
        "suggested_work_units": [
            {"role": "requirements-analyst", "title": "Reconfirm problem, scope, 5W1H and evidence"},
            {"role": "domain-architect", "title": "Freeze architecture, interfaces and rollback"},
            {"role": "implementation-engineer", "title": "Implement the approved minimal change"},
            {"role": "security-challenger", "title": "Run security, privacy and misuse tests"},
            {"role": "quality-verifier", "title": "Run deterministic closure and independent audit"},
        ],
        "plan": plan,
        "plan_digest": plan_digest,
        "acceptance_matrix": final_gate.get("acceptance_matrix", {}),
        "hard_gates": final_gate.get("hard_gates", {}),
        "dissent": final_gate.get("dissent", []),
        "final_audit": final_audit,
        "context_manifest_sha256": context_manifest["sha256"],
    }


def review(
    user_home: Path,
    task_id: str,
    *,
    context_files: list[Path] | None = None,
    privacy_class: str = "D1",
    effort: str = "high",
    profile: str = "balanced",
    provider_executor: ProviderExecutor | None = None,
    require_live: bool = True,
) -> dict[str, Any]:
    """Run a bounded, read-mostly specialist review; never mutate the task itself."""
    task = _task_row(user_home, task_id)
    screened = sanitize("\n".join([task["title"], task.get("description") or "", task.get("acceptance_criteria") or ""]), "strict")
    if screened.decision == "block":
        return {
            "decision": "blocked",
            "failure_class": "task-validation-privacy-gate",
            "task_id": task_id,
            "findings": list(screened.findings),
            "provider_calls": 0,
        }
    context_manifest = build_context_manifest(user_home, task_id, context_files)
    validation_id = new_id("tval")
    snapshot = _task_snapshot(task)
    now = utc_now()
    requested_roles = [
        "requirements-analyst", "domain-architect", "operator-ux-reviewer",
        "security-challenger", "eu-ai-act-compliance-reviewer", "performance-engineer",
        "quality-verifier", "plan-synthesizer", "independent-judge",
    ]
    required_provider_families = ["claude", "codex", "gemini", "grok", "ollama"]
    conn = connect_write(user_home)
    try:
        conn.execute(
            """INSERT INTO task_validations(
            id,task_id,source_revision,trigger_action,policy,status,original_json,original_sha256,
            requested_roles_json,context_manifest_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                validation_id, task_id, int(task["revision"]), "manual", validation_policy(task), "running",
                _canonical(snapshot), _digest(snapshot), _canonical(requested_roles), _canonical(context_manifest), now, now,
            ),
        )
        append_event(
            conn,
            "task.validation.started",
            {"validation_id": validation_id, "source_revision": task["revision"], "context_sha256": context_manifest["sha256"]},
            task_id=task_id,
        )
        conn.commit()
    finally:
        conn.close()

    context_summary = {
        "registered_evidence_count": len(context_manifest["registered_evidence"]),
        "explicit_context": [
            {key: item.get(key) for key in ("name", "kind", "sha256", "assessment", "redactions", "truncated")}
            for item in context_manifest["explicit_context"]
        ],
    }
    validation_goal = f"""Validate and optimise the following registered task before any claim, execution, run or go action.

TASK ID: {task_id}
TASK REVISION: {task['revision']}
TITLE: {task['title']}
DESCRIPTION: {task.get('description') or ''}
ACCEPTANCE: {task.get('acceptance_criteria') or ''}
PRIORITY: {task['priority']}
RISK: {task['risk_class']}
SOURCE: {task['source']} / {task.get('source_id') or ''}
TAGS: {', '.join(task.get('tags', []))}
CONTEXT: {json.dumps(context_summary, ensure_ascii=False, sort_keys=True)}

Mandatory review questions:
- Is the reported issue or requested change factually current, technically correct and within the named product scope?
- Is it duplicate, already solved, obsolete, unsupported by evidence, or based on a wrong assumption?
- What do screenshots/visual evidence, content, project documents, code-adjacent evidence and logs prove or fail to prove?
- What is the smallest correct solution and why is it better than the original wording?
- What security, privacy, EU AI Act, tenancy, supply-chain, performance, rollback and release risks apply?
- Produce one advanced execution plan with measurable KPI/SLA, 10 use cases, 10 tests and 10 failure cases.
- Required roles must challenge one another and accept the same frozen plan digest. Do not fake consensus.
- Every required provider family (Claude, Codex, Gemini, Grok and at least one exact Ollama Cloud model seat) must produce a substantive, receipt-bound contribution; unavailable or empty families remain unsatisfied.
- If visual files are digest-bound but not inspected by a vision-capable adapter, state not-visually-assessed.
""".strip()

    try:
        result = run_goal(
            user_home,
            validation_goal,
            execute=False,
            risk_class=str(task["risk_class"]),
            privacy_class=privacy_class,
            max_parallel=8,
            token_budget=500_000 if profile == "ultracode" else 250_000,
            wall_clock_seconds=7200 if profile == "ultracode" else 3600,
            provider_executor=provider_executor,
            require_live=require_live,
            profile=profile,
            required_provider_families=required_provider_families,
        )
        plan, final_gate, final_audit = _extract_plan(result)
        # Task validation is intentionally planning-only. A final implementation audit does not
        # exist until execution, so same-digest plan acceptance is the authoritative review gate.
        # When a future runtime supplies a final-audit node, it must also be positive.
        audit_decision = str(final_audit.get("decision") or "").casefold()
        substantive_families, provider_family_evidence = _substantive_provider_families(result)
        unsatisfied_families = [family for family in required_provider_families if family not in substantive_families]
        exact_ollama_cloud = any(
            row["provider"] == "ollama"
            and bool(row.get("model_served"))
            and str(row.get("model_served")).casefold() not in {"auto", "auto:cloud"}
            for row in provider_family_evidence
        )
        provider_family_gate = not unsatisfied_families and exact_ollama_cloud
        accepted = (
            final_gate.get("decision") == "accept"
            and (not final_audit or audit_decision in {"accept", "pass", "approve"})
            and provider_family_gate
        )
        proposal = _proposal(task, plan, final_gate, final_audit, context_manifest)
        proposal.setdefault("hard_gates", {}).update(
            {
                "all_required_provider_families_substantive": not unsatisfied_families,
                "exact_ollama_cloud_model_receipt": exact_ollama_cloud,
            }
        )
        proposal["provider_family_gate"] = {
            "required": required_provider_families,
            "substantive": sorted(substantive_families),
            "unsatisfied": unsatisfied_families,
            "evidence": provider_family_evidence,
        }
        substantive = len(provider_family_evidence)
        total = max(1, sum(1 for value in (result.get("results") or {}).values() if isinstance(value, dict)))
        confidence = round(min(1.0, substantive / max(1, min(total, len(requested_roles)))), 4)
        providers = sorted({
            str(value.get("provider"))
            for value in (result.get("provider_selection") or {}).values()
            if isinstance(value, dict) and value.get("provider")
        })
        status = "awaiting-user-approval" if accepted else "needs-work"
        verdict = "accept" if accepted else "needs-work"
        conn = connect_write(user_home)
        try:
            conn.execute(
                """UPDATE task_validations SET status=?,validation_task_id=?,validation_meeting_id=?,
                proposal_json=?,proposal_sha256=?,plan_digest=?,verdict=?,confidence=?,providers_json=?,updated_at=?
                WHERE id=?""",
                (
                    status, result.get("task_id"), result.get("meeting_id"), _canonical(proposal), _digest(proposal),
                    proposal.get("plan_digest"), verdict, confidence, _canonical(providers), utc_now(), validation_id,
                ),
            )
            append_event(
                conn,
                "task.validation.finished",
                {
                    "validation_id": validation_id,
                    "verdict": verdict,
                    "status": status,
                    "plan_digest": proposal.get("plan_digest"),
                    "providers": providers,
                },
                task_id=task_id,
            )
            conn.commit()
        finally:
            conn.close()
        export_workspace(user_home, task_id=task_id)
        return {
            "decision": "pass" if accepted else "needs-work",
            "task_id": task_id,
            "task_revision": task["revision"],
            "validation_id": validation_id,
            "status": status,
            "policy": validation_policy(task),
            "verdict": verdict,
            "confidence": confidence,
            "validation_task_id": result.get("task_id"),
            "validation_meeting_id": result.get("meeting_id"),
            "plan_digest": proposal.get("plan_digest"),
            "providers": providers,
            "required_provider_families": required_provider_families,
            "substantive_provider_families": sorted(substantive_families),
            "unsatisfied_provider_families": unsatisfied_families,
            "provider_family_gate": provider_family_gate,
            "ollama_used": "ollama" in substantive_families,
            "proposal": proposal,
            "context_manifest": context_manifest,
            "diagnostics": result.get("diagnostics"),
            "next": (
                f"iot-ai tasks prepare --task-id {task_id} --action approve --validation-id {validation_id} --subject <user>"
                if accepted else
                f"iot-ai tasks prepare --task-id {task_id} --action review --context <additional-evidence>"
            ),
            "execution_authorized": False,
        }
    except Exception as exc:
        conn = connect_write(user_home)
        try:
            conn.execute(
                "UPDATE task_validations SET status='blocked',verdict='block',decision_note=?,updated_at=? WHERE id=?",
                (f"{type(exc).__name__}: {exc}", utc_now(), validation_id),
            )
            append_event(
                conn,
                "task.validation.blocked",
                {"validation_id": validation_id, "error_type": type(exc).__name__, "error": str(exc)},
                task_id=task_id,
            )
            conn.commit()
        finally:
            conn.close()
        raise


def approve(user_home: Path, task_id: str, validation_id: str, subject: str, note: str = "") -> dict[str, Any]:
    if not subject.strip():
        raise ValueError("subject is required")
    conn = connect_write(user_home)
    try:
        task = one(conn, "SELECT * FROM tasks WHERE id=?", (task_id,))
        validation = one(conn, "SELECT * FROM task_validations WHERE id=? AND task_id=?", (validation_id, task_id))
        if not task or not validation:
            raise ValueError("Task or validation not found")
        if validation["status"] != "awaiting-user-approval" or validation["verdict"] != "accept":
            raise PermissionError("only an accepted validation awaiting user approval may be applied")
        if int(task["revision"]) != int(validation["source_revision"]):
            conn.execute("UPDATE task_validations SET status='stale',updated_at=? WHERE id=?", (utc_now(), validation_id))
            conn.commit()
            raise PermissionError("task changed after validation; run validation again")
        proposal = json.loads(validation["proposal_json"] or "{}")
        old = dict(task)
        new_revision = int(task["revision"]) + 1
        now = utc_now()
        conn.execute(
            """UPDATE tasks SET title=?,description=?,priority=?,risk_class=?,tags_json=?,acceptance_criteria=?,
            revision=?,engineering_stage='validated',updated_at=? WHERE id=?""",
            (
                proposal["optimized_title"], proposal["optimized_description"], proposal["optimized_priority"],
                proposal["optimized_risk_class"], _canonical(proposal["optimized_tags"]),
                proposal["optimized_acceptance_criteria"], new_revision, now, task_id,
            ),
        )
        conn.execute(
            """UPDATE task_validations SET status='approved',applied_revision=?,user_decision='approve',
            decision_subject=?,decision_note=?,updated_at=? WHERE id=?""",
            (new_revision, subject.strip(), note.strip(), now, validation_id),
        )
        existing_wu = one(conn, "SELECT id FROM work_units WHERE task_id=? LIMIT 1", (task_id,))
        if existing_wu is None:
            wu_id = new_id("wu")
            conn.execute(
                """INSERT INTO work_units(id,task_id,title,role,status,read_scope_json,write_scope_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (wu_id, task_id, "Validated implementation", "implementation-engineer", "ready", "[]", "[]", now, now),
            )
        append_event(
            conn,
            "task.validation.approved",
            {
                "validation_id": validation_id,
                "subject": subject.strip(),
                "source_revision": validation["source_revision"],
                "applied_revision": new_revision,
                "before_sha256": _digest(old),
                "after_sha256": _digest(proposal),
                "plan_digest": validation.get("plan_digest"),
            },
            task_id=task_id,
        )
        conn.commit()
    finally:
        conn.close()
    export_workspace(user_home, task_id=task_id)
    return {
        "decision": "pass",
        "task_id": task_id,
        "validation_id": validation_id,
        "status": "approved",
        "task_revision": new_revision,
        "execution_authorized": True,
        "next": f"iot-ai tasks claim --work-unit-id <work-unit-id> --owner <coder> --session-id <session>",
    }


def reject(user_home: Path, task_id: str, validation_id: str, subject: str, note: str) -> dict[str, Any]:
    if not subject.strip() or not note.strip():
        raise ValueError("subject and note are required")
    conn = connect_write(user_home)
    try:
        validation = one(conn, "SELECT * FROM task_validations WHERE id=? AND task_id=?", (validation_id, task_id))
        if not validation:
            raise ValueError("Validation not found")
        now = utc_now()
        conn.execute(
            "UPDATE task_validations SET status='rejected',user_decision='reject',decision_subject=?,decision_note=?,updated_at=? WHERE id=?",
            (subject.strip(), note.strip(), now, validation_id),
        )
        append_event(conn, "task.validation.rejected", {"validation_id": validation_id, "subject": subject.strip(), "note": note.strip()}, task_id=task_id)
        conn.commit()
    finally:
        conn.close()
    export_workspace(user_home, task_id=task_id)
    return {"decision": "pass", "task_id": task_id, "validation_id": validation_id, "status": "rejected", "execution_authorized": False}


def skip(
    user_home: Path,
    task_id: str,
    *,
    subject: str,
    reason: str,
    trigger_action: str = "manual",
    founder_confirm: str | None = None,
) -> dict[str, Any]:
    if not subject.strip() or not reason.strip():
        raise ValueError("subject and reason are required")
    task = _task_row(user_home, task_id)
    policy = validation_policy(task)
    if policy == "required" and founder_confirm != "FOUNDER_SKIP_TASK_VALIDATION":
        raise PermissionError("required task validation may be skipped only with FOUNDER_SKIP_TASK_VALIDATION")
    validation_id = new_id("tval")
    snapshot = _task_snapshot(task)
    now = utc_now()
    conn = connect_write(user_home)
    try:
        conn.execute(
            """INSERT INTO task_validations(
            id,task_id,source_revision,trigger_action,policy,status,original_json,original_sha256,
            verdict,user_decision,decision_subject,decision_note,created_at,updated_at)
            VALUES(?,?,?,?,?,'skipped',?,?,?,'skip',?,?,?,?)""",
            (
                validation_id, task_id, task["revision"], trigger_action, policy,
                _canonical(snapshot), _digest(snapshot), "risk-accepted", subject.strip(), reason.strip(), now, now,
            ),
        )
        append_event(
            conn,
            "task.validation.skipped",
            {"validation_id": validation_id, "policy": policy, "subject": subject.strip(), "reason": reason.strip()},
            task_id=task_id,
        )
        conn.commit()
    finally:
        conn.close()
    export_workspace(user_home, task_id=task_id)
    return {
        "decision": "pass",
        "task_id": task_id,
        "validation_id": validation_id,
        "status": "skipped",
        "policy": policy,
        "warning": "Validation skip is an explicit risk acceptance and does not bypass deterministic execution or audit gates.",
        "execution_authorized": True,
    }


def status(user_home: Path, task_id: str) -> dict[str, Any]:
    task = _task_row(user_home, task_id)
    conn = connect_read(user_home)
    if conn is None:
        raise ValueError("Task not found")
    validations = rows(conn, "SELECT * FROM task_validations WHERE task_id=? ORDER BY created_at DESC", (task_id,))
    conn.close()
    for row in validations:
        for field in ("original_json", "proposal_json", "requested_roles_json", "providers_json", "context_manifest_json"):
            if row.get(field):
                row[field.removesuffix("_json")] = json.loads(row[field])
            row.pop(field, None)
    return {
        "decision": "pass",
        "task_id": task_id,
        "task_revision": task["revision"],
        "policy": validation_policy(task),
        "gate": gate(user_home, task_id, "manual"),
        "validations": validations,
        "count": len(validations),
    }
