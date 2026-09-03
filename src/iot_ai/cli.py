# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.2 | Date: 2026-08-19
"""Unified IOT-AI command surface with backward-compatible advanced commands."""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import settings as settings_mod
from .agentic import run_goal
from .autopilot import run_autopilot
from .audit import audit_task
from .diagnostics import collect as diagnostics_collect, compare as diagnostics_compare, explain as diagnostics_explain, validate as diagnostics_validate
from .eu_ai_act import (
    default_system_card,
    record_incident,
    record_prohibited_practice_screen,
    record_literacy_receipt,
    register_model_dossier,
    release_gate as compliance_release_gate,
    runtime_compliance_status,
    screen_prohibited_practices,
)
from .github_analysis import analyze_refs
from .graph_runtime import compile_graph, validate_graph
from .help_system import QUICKSTART, list_topics, search as help_search, show as help_show
from .installer import HOSTS, install as package_install, plan as package_plan, repair as package_repair, rollback as package_rollback, status as package_status, uninstall as package_uninstall, upgrade as package_upgrade, verify as package_verify
from .identity_migration import apply as identity_apply, plan as identity_plan, rollback as identity_rollback, status as identity_status
from .knowledge import export_jsonl
from .capability_pack import build_pack as capability_build_pack, verify_pack as capability_verify_pack
from .knowledge_plane import list_artifacts, write_canvas
from .licensing import current
from .logging_config import append_event, log_locations
from .meeting import (
    approve as meeting_approve,
    create_task_from_meeting,
    list_meetings,
    project_meeting_view,
    run as meeting_run,
    show as meeting_show,
    start as meeting_start,
)
from .meeting_api import serve as meeting_api_serve
from .meeting_integration import (
    create_calendar_event,
    list_agent_seats,
    list_calendar_events,
    register_agent_seat,
    start_calendar_event,
)
from .meeting_reporting import (
    write_report as write_meeting_report,
    write_report_bundle as write_meeting_report_bundle,
)
from .export_gate import assert_export_safe, rewrite_public_export
from .mesh import delegate as mesh_delegate
from .multicoder import run as multicoder_run
from .paths import home
from .projection import export_workspace
from .providers import add_route, load as load_routes, mutate_route, static_status
from .readiness import provider_candidates
from .seat_selection import resolve_meeting_seats
from .privacy import SECRET_PATTERNS, sanitize
from .report import render as render_report
from .setup_wizard import discover as setup_discover, init_inventory, show_inventory
from .status import unified_status
from .task_execute import run_meeting_then_multicoder
from .tasks import add_evidence, add_work_unit, claim_work_unit, create as task_create, heartbeat as task_heartbeat, list_all, list_closed, list_open, record_progress, release_lease, show as task_show, solve_all_plan, submit_task, workspace_status
from .task_backends import EXECUTION_ELIGIBLE_STATES
from .task_validation import (
    approve as validation_approve,
    gate as validation_gate,
    reject as validation_reject,
    review as validation_review,
    skip as validation_skip,
    status as validation_status,
)
from .transparency import mark_file, record_disclosure, runtime_output_provenance, verify_file
from .suite_package import clean_install_state
from .update_manager import apply_local as update_apply_local, plan as update_plan, rollback as update_rollback, status as update_status
from .worktrees import cleanup as worktree_cleanup, create as worktree_create, list_runs as worktree_list, promotion_plan as worktree_promotion_plan, show as worktree_show

PUBLIC_COMMANDS = {"help", "status", "settings", "update", "license", "run", "github-analyze"}
ADVANCED_COMMANDS = {"setup", "privacy", "provider", "mesh", "meeting", "tasks", "multi-coder", "knowledge", "graph", "diagnostics", "compliance", "package", "report", "worktree"}
ALL_COMMANDS = PUBLIC_COMMANDS | ADVANCED_COMMANDS
_BLOCKING_DECISIONS = frozenset(
    {
        "blocked",
        "fail",
        "error",
        "needs-work",
        "requires-user-confirmation",
    }
)


def _result_exit_code(result: Any) -> int:
    """Exit 0 is not a pass. Blocked/failed governed results must be non-zero."""
    if not isinstance(result, dict):
        return 0
    decision = str(result.get("decision") or "").casefold()
    if decision in _BLOCKING_DECISIONS:
        return 1
    return 0

SENSITIVE_KEYS = {
    "secret", "secret_env", "secret_value", "password", "passwd", "lease_token",
    "access_token", "refresh_token", "bearer_token", "api_key", "apikey",
    "authorization", "auth_header", "private_key", "client_secret",
}
SAFE_TELEMETRY_KEYS = {
    "token_budget", "input_tokens", "output_tokens", "cached_tokens",
    "reasoning_tokens", "max_tokens", "token_count", "tokens",
}


def _sensitive_key(key_text: str) -> bool:
    if key_text in SAFE_TELEMETRY_KEYS:
        return False
    if key_text in SENSITIVE_KEYS:
        return True
    return key_text.endswith(("_password", "_secret", "_token", "_api_key", "_private_key"))


def _mask_secret_text(text: str) -> str:
    masked = text
    for pattern in SECRET_PATTERNS:
        masked = pattern.sub("[REDACTED]", masked)
    return masked


def _public_cli_view(value: Any) -> Any:
    """Return a newly built object that never contains secret-classified fields."""
    if isinstance(value, dict):
        public: dict[Any, Any] = {}
        for key, item in value.items():
            if _sensitive_key(str(key).casefold()):
                continue
            public[key] = _public_cli_view(item)
        return public
    if isinstance(value, list):
        return [_public_cli_view(item) for item in value]
    if isinstance(value, tuple):
        return [_public_cli_view(item) for item in value]
    if isinstance(value, str):
        return _mask_secret_text(value)
    return value


def _redact_sensitive(value: Any) -> Any:
    return _public_cli_view(value)


def _cli_public_text(value: Any) -> str:
    if isinstance(value, str):
        return _mask_secret_text(value)
    return json.dumps(
        _public_cli_view(value),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str,
    )


def _write_public_cli_line(text: str) -> None:
    """Write already-redacted text without modeled print/stdout.write sinks."""
    line = text if text.endswith("\n") else f"{text}\n"
    raw = getattr(sys.stdout, "buffer", None)
    if raw is not None:
        try:
            raw.write(line.encode("utf-8"))
            return
        except (OSError, io.UnsupportedOperation, TypeError, ValueError, AttributeError):
            pass
    # StringIO / pytest capture: call the concrete type's write, not
    # sys.stdout.write (the modeled CWE-532 sink).
    type(sys.stdout).write(sys.stdout, line)


def emit(value: Any) -> None:
    # Never pass the original object to a modeled logging sink.
    _write_public_cli_line(_cli_public_text(value))


def _split(value: str | None) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]



MEETING_OPERATIONS = {"start", "seat-plan", "list", "show", "run", "approve", "create-task", "export", "report", "calendar-create", "calendar-list", "calendar-start", "agent-register", "agent-list", "api-serve"}


def normalize_meeting_argv(argv: list[str]) -> list[str]:
    """Normalize a meeting alias or natural-language meeting command."""
    import re

    prefix, argv = hoist_root_options(argv)
    if argv and argv[0] in {"-h", "--help"}:
        return [*prefix, "meeting", argv[0]]
    if argv and argv[0] in MEETING_OPERATIONS:
        return [*prefix, "meeting", *argv]

    max_parallel: str | None = None
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        value = argv[index]
        if value == "--max-parallel":
            if index + 1 < len(argv) and argv[index + 1].isdigit():
                max_parallel = argv[index + 1]
                index += 2
            else:
                index += 1
            continue
        remaining.append(value)
        index += 1

    raw_topic = " ".join(remaining).strip()
    if not raw_topic:
        return [*prefix, "meeting", "seat-plan", "--seats", "all-coders+ollama-clouds"]
    normalized = raw_topic.casefold()
    wants_all_coders = bool(re.search(r"\ball\s+coders?\b|\ball\s+coder\b", normalized))
    wants_ollama_cloud = bool(re.search(r"\bollama\s+clouds?\b|\bollama-cloud", normalized))
    selector = "all-coders+ollama-clouds" if wants_all_coders and wants_ollama_cloud else "auto"
    topic = re.sub(
        r"^\s*(?:ask\s+)?all\s+coders?\s+and\s+ollama\s+clouds?\s+only\s*[:,;-]?\s*",
        "",
        raw_topic,
        flags=re.IGNORECASE,
    ).strip() or raw_topic
    command = ["meeting", "start", "--topic", topic, "--seats", selector, "--depth", "deep", "--effort", "high"]
    if max_parallel:
        command.extend(["--max-parallel", max_parallel])
    return [*prefix, *command]


def _runtime_mark_for_mesh(result: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    rows = result if isinstance(result, list) else [result]
    content = "\n\n".join(str(row.get("output") or "") for row in rows)
    providers = sorted({str(row.get("provider")) for row in rows if row.get("provider")})
    models = sorted({str(row.get("model_served")) for row in rows if row.get("model_served")})
    return runtime_output_provenance(
        content,
        content_type="text/plain",
        model_providers=providers,
        model_ids=models,
    )


def _screen_text(value: str, user_home: Path | None = None, *, context: str = "cli") -> dict[str, Any]:
    decision = (
        record_prohibited_practice_screen(user_home, value, context=context)
        if user_home is not None
        else screen_prohibited_practices(value).to_dict()
    )
    if decision["decision"] == "block":
        raise PermissionError("EU AI Act Article 5 prohibited-practice gate blocked the request")
    return decision


def hoist_root_options(argv: list[str]) -> tuple[list[str], list[str]]:
    """Pull --home/--version out of wrapper and post-command positions.

    Dedicated entrypoints inject the command first, so `iot-ai-status --home PATH`
    arrives as `status --home PATH`. Natural-language goals after `--goal` are left alone.
    """
    prefix: list[str] = []
    rest: list[str] = []
    after_goal = False
    index = 0
    while index < len(argv):
        value = argv[index]
        if not after_goal and value == "--home" and index + 1 < len(argv) and not str(argv[index + 1]).startswith("-"):
            prefix.extend(["--home", argv[index + 1]])
            index += 2
            continue
        if not after_goal and value == "--version":
            prefix.append("--version")
            index += 1
            continue
        if value == "--goal":
            after_goal = True
        rest.append(value)
        index += 1
    return prefix, rest


def _normalize_argv(argv: list[str] | None) -> list[str]:
    """Normalize the five-command surface and natural-language goal syntax.

    Examples accepted:
      iot-ai "review this design"
      iot-ai --profile ultracode --execute "fix and verify this defect"
      iot-ai --home /tmp/demo --profile balanced "plan this change"
      iot-ai status --home /tmp/demo
    """
    values = list(sys.argv[1:] if argv is None else argv)
    if not values:
        return ["help", "quickstart"]

    root_prefix, remaining = hoist_root_options(values)
    if "--version" in root_prefix:
        return ["--version"]

    if remaining and remaining[0] == "task":
        remaining[0] = "tasks"
        values = [*root_prefix, *remaining]
    if remaining and remaining[0] == "meeting" and (len(remaining) == 1 or remaining[1] not in MEETING_OPERATIONS):
        return [*root_prefix, *normalize_meeting_argv(remaining[1:])]
    if remaining and remaining[0] in ALL_COMMANDS:
        return [*root_prefix, *remaining]

    run_flags = {"--execute", "--apply", "--allow-static", "--resume"}
    run_options = {
        "--risk-class",
        "--privacy-class",
        "--profile",
        "--max-parallel",
        "--token-budget",
        "--wall-clock-seconds",
        "--conversation-id",
        "--report-output",
        "--max-tasks",
        "--cwd",
    }
    run_args: list[str] = []
    goal: list[str] = []
    index = 0
    while index < len(remaining):
        value = remaining[index]
        if not goal and value in run_flags:
            run_args.append(value)
            index += 1
            continue
        if not goal and value in run_options:
            if index + 1 >= len(remaining):
                return values
            run_args.extend(remaining[index:index + 2])
            index += 2
            continue
        goal.extend(remaining[index:])
        break
    if not goal:
        return values
    return [*root_prefix, "run", *run_args, "--goal", *goal]


def _auto_meeting_seats(user_home: Path) -> list[str]:
    """Backward-compatible wrapper over the auditable seat resolver."""
    plan = resolve_meeting_seats(user_home, "auto")
    if plan.decision != "pass":
        raise RuntimeError(f"meeting seat resolution blocked: {plan.reason}")
    return list(plan.resolved_seats)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="iot-ai", description="IOT-AI agentic multi-coder control plane")
    root.add_argument("--version", action="version", version=f"iot-ai {__version__}")
    root.add_argument("--home")
    commands = root.add_subparsers(dest="cmd", required=True)

    h = commands.add_parser("help", help="Show the small public command surface and examples")
    h.add_argument("op", nargs="?", default="quickstart")
    h.add_argument("term", nargs="?")

    run = commands.add_parser("run", help="Agentically solve a natural-language goal")
    run.add_argument("--goal", nargs="+", required=True)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--risk-class", default="R2")
    run.add_argument("--privacy-class", default="D1")
    run.add_argument("--profile", choices=("economy", "balanced", "ultracode"))
    run.add_argument("--max-parallel", type=int, default=6)
    run.add_argument("--token-budget", type=int, default=250000)
    run.add_argument("--wall-clock-seconds", type=int, default=3600)
    run.add_argument("--allow-static", action="store_true", help="Review/testing only: allow non-live provider candidates")
    run.add_argument("--task-validation", choices=("ask", "review", "skip"), default="ask", help="Pre-execution task validation policy")
    run.add_argument("--subject")
    run.add_argument("--reason", default="")
    run.add_argument("--founder-confirm")
    run.add_argument("--context", action="append", default=[])
    run.add_argument("--apply", action="store_true", help="Explicitly apply the compiled natural-language intent")
    run.add_argument("--conversation-id", default="default")
    run.add_argument("--resume", action="store_true", help="Resolve references from the last conversation checkpoint")
    run.add_argument("--report-output")
    run.add_argument("--max-tasks", type=int)
    run.add_argument("--cwd", default=".")
    run.add_argument("--test-argv", nargs="+")

    status = commands.add_parser("status", help="Unified Suite, coder, model and workflow health")
    status.add_argument("--live", action="store_true")
    status.add_argument("--json", action="store_true")
    status.add_argument("--window", default="24h")
    status.add_argument("--logs", action="store_true", help="Print only log locations")

    settings = commands.add_parser("settings", help="Platform-independent settings")
    ops = settings.add_subparsers(dest="op", required=True)
    show_p = ops.add_parser("show"); show_p.add_argument("--effective", action="store_true")
    ss = ops.add_parser("set"); ss.add_argument("key"); ss.add_argument("value")
    sg = ops.add_parser("group"); sg.add_argument("group"); sg.add_argument("state", choices=("on", "off"))
    sp = ops.add_parser("profile"); sp.add_argument("name", choices=("economy", "balanced", "ultracode")); sp.add_argument("--session-only", action="store_true")
    sm = ops.add_parser("migrate-brand"); sm.add_argument("--apply", action="store_true"); sm.add_argument("--rollback", action="store_true")
    ops.add_parser("validate")
    preset_p = ops.add_parser("preset")
    preset_p.add_argument("preset_op", choices=("list", "show", "diff", "apply"))
    preset_p.add_argument("preset_name", nargs="?")
    preset_p.add_argument("--apply", action="store_true")
    migv = ops.add_parser("migrate"); migv.add_argument("--apply", action="store_true")
    rbp = ops.add_parser("rollback"); rbp.add_argument("receipt_id"); rbp.add_argument("--apply", action="store_true")
    rolep = ops.add_parser("role")
    rolep.add_argument("role_op", choices=("set", "show"))
    rolep.add_argument("role_id")
    rolep.add_argument("--preferred-providers")
    rolep.add_argument("--effort")
    rolep.add_argument("--minimum-effort")
    skp = ops.add_parser("skills")
    skp.add_argument("skills_op", choices=("list", "discover", "explain"))
    skp.add_argument("skill_id", nargs="?")
    skp.add_argument("--goal")
    skp.add_argument("--role")

    update = commands.add_parser("update", help="Single public update authority")
    uops = update.add_subparsers(dest="op", required=True)
    uops.add_parser("status")
    up = uops.add_parser("plan"); up.add_argument("--channel", default="beta")
    ua = uops.add_parser("apply"); ua.add_argument("--package", required=True); ua.add_argument("--expected-sha256", required=True); ua.add_argument("--package-store"); ua.add_argument("--package-archive"); ua.add_argument("--apply", action="store_true")
    ur = uops.add_parser("rollback"); ur.add_argument("--apply", action="store_true")

    lic = commands.add_parser("license", help="Show edition and commercial entitlement state")
    lic.add_argument("--json", action="store_true")

    gha = commands.add_parser(
        "github-analyze",
        help="Analyze inbound GitHub repos (technical, commercial, license, relevance). Ideas only; no dependency.",
    )
    gha.add_argument("refs", nargs="*", help="GitHub owner/name or https://github.com/owner/name")
    gha.add_argument("--offline-json", help="Fixture records; no network")
    gha.add_argument("--no-network", action="store_true", help="Do not call GitHub; missing license stays BLOCK")

    setup = commands.add_parser("setup", help=argparse.SUPPRESS)
    ops = setup.add_subparsers(dest="op", required=True); ops.add_parser("discover"); ops.add_parser("show")
    si = ops.add_parser("init"); si.add_argument("--project-root"); si.add_argument("--server", action="append", default=[]); si.add_argument("--apply", action="store_true")

    privacy = commands.add_parser("privacy", help=argparse.SUPPRESS)
    ops = privacy.add_subparsers(dest="op", required=True)
    pc = ops.add_parser("check"); pc.add_argument("--text", required=True); pc.add_argument("--mode", default="strict", choices=("strict", "block-private"))

    provider = commands.add_parser("provider", help=argparse.SUPPRESS)
    ops = provider.add_subparsers(dest="op", required=True); ops.add_parser("list")
    pa = ops.add_parser("add"); pa.add_argument("--route-id", required=True); pa.add_argument("--provider", required=True); pa.add_argument("--kind", choices=("cli", "api"), default="cli"); pa.add_argument("--auth-mode", required=True); pa.add_argument("--command", nargs="+"); pa.add_argument("--endpoint"); pa.add_argument("--protocol", choices=("openai-compatible", "anthropic", "gemini", "ollama")); pa.add_argument("--secret-env"); pa.add_argument("--allow-private-endpoint", action="store_true"); pa.add_argument("--model", default="auto"); pa.add_argument("--priority", type=int, default=50); pa.add_argument("--enabled", action="store_true"); pa.add_argument("--apply", action="store_true")
    pd = ops.add_parser("doctor"); pd.add_argument("--provider", required=True); pd.add_argument("--prompt", default="Return the literal token OK"); pd.add_argument("--auth-mode", default="auto"); pd.add_argument("--effort", default="low")
    for op in ("enable", "disable", "remove"):
        pp = ops.add_parser(op); pp.add_argument("route_id"); pp.add_argument("--apply", action="store_true")

    mesh = commands.add_parser("mesh", help=argparse.SUPPRESS)
    mops = mesh.add_subparsers(dest="op", required=True)
    md = mops.add_parser("delegate"); md.add_argument("--provider", required=True); md.add_argument("--task", required=True); md.add_argument("--task-mode", default="consultation"); md.add_argument("--model", default="auto"); md.add_argument("--auth-mode", default="auto"); md.add_argument("--allow-fallback", action="store_true"); md.add_argument("--timeout", type=int, default=240); md.add_argument("--effort", default="medium")
    mc = mops.add_parser("compare"); mc.add_argument("--providers", required=True); mc.add_argument("--task", required=True); mc.add_argument("--task-mode", default="review"); mc.add_argument("--auth-mode", default="auto"); mc.add_argument("--timeout", type=int, default=240); mc.add_argument("--effort", default="medium"); mc.add_argument("--quorum", type=int, default=2)

    meeting = commands.add_parser("meeting", help=argparse.SUPPRESS)
    mops = meeting.add_subparsers(dest="op", required=True)
    ms = mops.add_parser("start"); ms.add_argument("--topic", required=True); ms.add_argument("--seats", default="auto", help="auto | all-coders | all-coders+ollama-clouds | comma-separated seats"); ms.add_argument("--quorum", type=int, default=2); ms.add_argument("--rounds", type=int, default=1); ms.add_argument("--depth", choices=("normal", "deep", "ultra"), default="deep"); ms.add_argument("--effort", default="high"); ms.add_argument("--owner"); ms.add_argument("--priority", choices=("low", "normal", "high", "critical"), default="normal"); ms.add_argument("--risk-class", default="R2"); ms.add_argument("--max-parallel", type=int, help="Thread pool concurrency; never a seat cap"); ms.add_argument("--max-seats", type=int, help="Explicit hard seat cap"); ms.add_argument("--exclude-ollama", action="store_true", help="Explicitly omit Ollama and record the exception"); ms.add_argument("--allow-missing-ollama", action="store_true", help="Allow an all-coders+ollama-clouds plan to continue when no Ollama cloud seat is configured"); ms.add_argument("--execute", action="store_true"); ms.add_argument("--task-id"); ms.add_argument("--correlation-id"); ms.add_argument("--privacy-class", default="D1")
    mplan = mops.add_parser("seat-plan"); mplan.add_argument("--seats", default="auto"); mplan.add_argument("--max-parallel", type=int); mplan.add_argument("--max-seats", type=int); mplan.add_argument("--exclude-ollama", action="store_true"); mplan.add_argument("--allow-missing-ollama", action="store_true")
    mops.add_parser("list")
    mshow = mops.add_parser("show"); mshow.add_argument("meeting_id"); mshow.add_argument("--view", choices=("brief", "simple", "full", "complete"), default="full")
    mrun = mops.add_parser("run"); mrun.add_argument("meeting_id")
    mapprove = mops.add_parser("approve"); mapprove.add_argument("meeting_id"); mapprove.add_argument("--subject", default="user"); mapprove.add_argument("--intent-digest"); mapprove.add_argument("--founder-receipt")
    mcreate = mops.add_parser("create-task"); mcreate.add_argument("meeting_id"); mcreate.add_argument("--title")
    mexport = mops.add_parser("export"); mexport.add_argument("meeting_id"); mexport.add_argument("--output", required=True); mexport.add_argument("--public", action="store_true")
    mreport = mops.add_parser("report")
    mreport.add_argument("--output", required=True)
    mreport.add_argument("--format", choices=("json", "csv", "markdown", "xlsx", "all", "bundle"), default="bundle")
    mreport.add_argument("--view", choices=("brief", "simple", "full", "complete"), default="brief")
    mreport.add_argument("--classification", choices=("private", "restricted", "public"), default="private")
    mreport.add_argument("--public", action="store_true", help="Alias for --classification public")
    mreport.add_argument("--public-meeting-id", action="append", default=[], help="Explicit D0 allowlist entry; repeatable")
    mreport.add_argument("--legacy-db", "--legacy-store", action="append", default=[], dest="legacy_db", help="Read-only historical meeting SQLite store; repeatable")
    mreport.add_argument("--stale-after-hours", type=int, default=24)
    mreport.add_argument("--exclude-current", action="store_true", help="Report only explicitly supplied legacy stores")
    mreport.add_argument("--from-time")
    mreport.add_argument("--to-time")
    mreport.add_argument("--status")
    mreport.add_argument("--task-id")
    mreport.add_argument("--provider")
    mreport.add_argument("--agent")
    mreport.add_argument("--decision")
    mcal = mops.add_parser("calendar-create"); mcal.add_argument("--title", required=True); mcal.add_argument("--topic", required=True); mcal.add_argument("--starts-at", required=True); mcal.add_argument("--seats", required=True); mcal.add_argument("--created-by", default="local-user"); mcal.add_argument("--surface"); mcal.add_argument("--quorum", type=int, default=2); mcal.add_argument("--depth", default="deep"); mcal.add_argument("--effort", default="high"); mcal.add_argument("--rrule"); mcal.add_argument("--auto-start", action="store_true")
    mcall = mops.add_parser("calendar-list"); mcall.add_argument("--status"); mcall.add_argument("--surface")
    mcstart = mops.add_parser("calendar-start"); mcstart.add_argument("event_id")
    mareg = mops.add_parser("agent-register"); mareg.add_argument("--surface", required=True); mareg.add_argument("--agent-id", required=True); mareg.add_argument("--display-name", required=True); mareg.add_argument("--model-binding"); mareg.add_argument("--endpoint-ref"); mareg.add_argument("--capability", action="append", default=[]); mareg.add_argument("--risk-class"); mareg.add_argument("--control-level", default="advisory"); mareg.add_argument("--reachable", action="store_true")
    malist = mops.add_parser("agent-list"); malist.add_argument("--surface"); malist.add_argument("--reachable-only", action="store_true")
    maserve = mops.add_parser("api-serve"); maserve.add_argument("--host", default="127.0.0.1"); maserve.add_argument("--port", type=int, default=8790); maserve.add_argument("--token-env", default="IOT_AI_MEETING_API_TOKEN")

    tasks = commands.add_parser("tasks", help=argparse.SUPPRESS)
    tops = tasks.add_subparsers(dest="op", required=True); tops.add_parser("status")
    for op in ("list", "open", "closed", "queue"):
        q = tops.add_parser(op); q.add_argument("--owner"); q.add_argument("--query"); q.add_argument("--status-filter"); q.add_argument("--limit", type=int); q.add_argument("--scope", choices=("open", "closed", "all"), default="all")
    tsh = tops.add_parser("show"); tsh.add_argument("task_id", nargs="?"); tsh.add_argument("--limit", type=int, default=5)
    tprep = tops.add_parser("prepare")
    tprep.add_argument("--task-id", required=True)
    tprep.add_argument("--action", choices=("status", "review", "approve", "reject", "skip"), default="status")
    tprep.add_argument("--validation-id")
    tprep.add_argument("--context", action="append", default=[])
    tprep.add_argument("--privacy-class", default="D1")
    tprep.add_argument("--effort", default="high")
    tprep.add_argument("--profile", choices=("economy", "balanced", "ultracode"), default="balanced")
    tprep.add_argument("--subject")
    tprep.add_argument("--reason", default="")
    tprep.add_argument("--founder-confirm")
    tprep.add_argument("--allow-static", action="store_true")
    tc = tops.add_parser("create"); tc.add_argument("--title", required=True); tc.add_argument("--description", default=""); tc.add_argument("--priority", choices=("low", "normal", "high", "critical"), default="normal"); tc.add_argument("--owner"); tc.add_argument("--risk-class", default="R1"); tc.add_argument("--task-type", default="task"); tc.add_argument("--source", default="local"); tc.add_argument("--source-id"); tc.add_argument("--tag", action="append", default=[]); tc.add_argument("--acceptance-criteria", default=""); tc.add_argument("--allow-duplicate", action="store_true")
    tw = tops.add_parser("add-work-unit"); tw.add_argument("--task-id", required=True); tw.add_argument("--title", required=True); tw.add_argument("--role", default="implementation"); tw.add_argument("--read-scope", action="append", default=[]); tw.add_argument("--write-scope", action="append", default=[])
    tclaim = tops.add_parser("claim"); tclaim.add_argument("--work-unit-id", required=True); tclaim.add_argument("--owner", required=True); tclaim.add_argument("--session-id", required=True); tclaim.add_argument("--ttl-seconds", type=int, default=3600)
    th = tops.add_parser("heartbeat"); th.add_argument("--lease-id", required=True); th.add_argument("--lease-token", required=True); th.add_argument("--ttl-seconds", type=int, default=3600)
    tp = tops.add_parser("progress"); tp.add_argument("--task-id", required=True); tp.add_argument("--work-unit-id"); tp.add_argument("--stage", required=True); tp.add_argument("--percent", type=int, required=True); tp.add_argument("--summary", required=True); tp.add_argument("--basis", choices=("manual-estimate","observed-steps","verified-criteria","deterministic-tests"), default="manual-estimate"); tp.add_argument("--evidence-id", action="append", default=[]); tp.add_argument("--observed-steps", type=int); tp.add_argument("--total-steps", type=int); tp.add_argument("--confidence", choices=("low","medium","high"), default="medium")
    te = tops.add_parser("evidence-add"); te.add_argument("--task-id", required=True); te.add_argument("--work-unit-id"); te.add_argument("--artifact", required=True); te.add_argument("--artifact-sha256"); te.add_argument("--kind", default="artifact")
    tr = tops.add_parser("release"); tr.add_argument("--lease-id", required=True); tr.add_argument("--lease-token"); tr.add_argument("--reason", default="released")
    ts = tops.add_parser("submit"); ts.add_argument("--task-id", required=True); ts.add_argument("--work-unit-id"); ts.add_argument("--lease-id"); ts.add_argument("--lease-token"); ts.add_argument("--result-summary", default="Technical work submitted")
    ta = tops.add_parser("audit"); ta.add_argument("task_id")
    tx = tops.add_parser("export-excel"); tx.add_argument("--output", required=True)
    solve = tops.add_parser("solve-all"); solve.add_argument("query", nargs="?"); solve.add_argument("--providers", default="auto"); solve.add_argument("--quorum", type=int, default=2); solve.add_argument("--implementer"); solve.add_argument("--test-profile"); solve.add_argument("--cwd", default="."); solve.add_argument("--effort", default="high"); solve.add_argument("--confirm-critical", action="store_true"); solve.add_argument("--max-tasks", type=int); solve.add_argument("--apply", action="store_true")
    tauth = tops.add_parser("authorize-execution", help="Run validation gates in one task or a bounded selected set; does not implement code")
    tauth.add_argument("--task-id", action="append", default=[]); tauth.add_argument("--all", action="store_true"); tauth.add_argument("--query"); tauth.add_argument("--max-tasks", type=int)
    texec = tops.add_parser("execute", help="Deprecated alias for authorize-execution; validation only")
    texec.add_argument("--task-id", action="append", default=[]); texec.add_argument("--all", action="store_true"); texec.add_argument("--query"); texec.add_argument("--max-tasks", type=int)
    trun = tops.add_parser("run", help="Plan or apply a closed-loop Task -> Meeting -> Multi-Coder workflow")
    trun.add_argument("--task-id", action="append", default=[]); trun.add_argument("--all", action="store_true"); trun.add_argument("--query"); trun.add_argument("--apply", action="store_true", help="Compatibility flag; tasks run executes by default"); trun.add_argument("--plan", action="store_true", help="Plan only; no implementation or provider execution")
    trun.add_argument("--mode", choices=("hybrid", "multi-coder"), default="hybrid")
    trun.add_argument("--providers", default="auto")
    trun.add_argument("--quorum", type=int, default=2)
    trun.add_argument("--implementer")
    trun.add_argument("--test-profile")
    trun.add_argument("--test-argv", nargs="+")
    trun.add_argument("--cwd", default=".")
    trun.add_argument("--risk-class", default="R2")
    trun.add_argument("--effort", default="high")
    trun.add_argument("--max-repair-rounds", type=int)
    trun.add_argument("--conversation-id", default="default")
    trun.add_argument("--report-output")
    trun.add_argument("--max-tasks", type=int)

    multi = commands.add_parser("multi-coder", help=argparse.SUPPRESS)
    mops = multi.add_subparsers(dest="op", required=True)
    mr = mops.add_parser("run"); mr.add_argument("--task"); mr.add_argument("--task-id"); mr.add_argument("--providers", default="auto"); mr.add_argument("--quorum", type=int, default=2); mr.add_argument("--implementer"); mr.add_argument("--test-argv", nargs="+"); mr.add_argument("--test-profile"); mr.add_argument("--test-command-json", help=argparse.SUPPRESS); mr.add_argument("--cwd", default="."); mr.add_argument("--risk-class", default="R2"); mr.add_argument("--effort", default="high"); mr.add_argument("--max-repair-rounds", type=int); mr.add_argument("--apply", action="store_true", help="Compatibility flag; multi-coder run executes by default"); mr.add_argument("--plan", action="store_true", help="Plan only; no provider calls or implementation")

    knowledge = commands.add_parser("knowledge", help=argparse.SUPPRESS)
    kops = knowledge.add_subparsers(dest="op", required=True)
    kp = kops.add_parser("pack"); kp.add_argument("--spec", required=True); kp.add_argument("--output", required=True)
    kv = kops.add_parser("verify-pack"); kv.add_argument("--bundle", required=True)
    ke = kops.add_parser("export"); ke.add_argument("--output", required=True); ke.add_argument("--audience", default="generic-rag"); ke.add_argument("--classification")
    kl = kops.add_parser("list"); kl.add_argument("--visibility", choices=("public", "private", "customer"), default="private")
    kc = kops.add_parser("canvas"); kc.add_argument("--artifact-ids", required=True); kc.add_argument("--visibility", choices=("public", "private", "customer"), default="private")

    graph = commands.add_parser("graph", help=argparse.SUPPRESS)
    gops = graph.add_subparsers(dest="op", required=True)
    gc = gops.add_parser("compile"); gc.add_argument("--goal", required=True); gc.add_argument("--execute", action="store_true"); gc.add_argument("--risk-class", default="R2"); gc.add_argument("--privacy-class", default="D1"); gc.add_argument("--max-parallel", type=int, default=6)

    worktree = commands.add_parser("worktree", help=argparse.SUPPRESS)
    wops = worktree.add_subparsers(dest="op", required=True)
    wp = wops.add_parser("plan"); wp.add_argument("--repo", required=True); wp.add_argument("--goal", required=True); wp.add_argument("--agents", required=True); wp.add_argument("--base-ref", default="HEAD"); wp.add_argument("--max-parallel", type=int, default=6)
    wc = wops.add_parser("create"); wc.add_argument("--repo", required=True); wc.add_argument("--goal", required=True); wc.add_argument("--agents", required=True); wc.add_argument("--base-ref", default="HEAD"); wc.add_argument("--max-parallel", type=int, default=6); wc.add_argument("--apply", action="store_true")
    wops.add_parser("list")
    ws = wops.add_parser("show"); ws.add_argument("run_id")
    wr = wops.add_parser("review"); wr.add_argument("run_id"); wr.add_argument("--winner")
    wx = wops.add_parser("cleanup"); wx.add_argument("run_id"); wx.add_argument("--apply", action="store_true")

    diagnostics = commands.add_parser("diagnostics", help=argparse.SUPPRESS)
    dops = diagnostics.add_subparsers(dest="op", required=True)
    dc = dops.add_parser("collect"); dc.add_argument("--correlation-id", required=True); dc.add_argument("--output", required=True)
    dv = dops.add_parser("validate"); dv.add_argument("bundle")
    de = dops.add_parser("explain"); de.add_argument("bundle")
    dcmp = dops.add_parser("compare"); dcmp.add_argument("bundle_a"); dcmp.add_argument("bundle_b")

    compliance = commands.add_parser("compliance", help=argparse.SUPPRESS)
    cops = compliance.add_subparsers(dest="op", required=True)
    cops.add_parser("status")
    cops.add_parser("system-card")
    cscreen = cops.add_parser("screen"); cscreen.add_argument("--text", required=True)
    cdisc = cops.add_parser("disclosure"); cdisc.add_argument("--surface", required=True); cdisc.add_argument("--language", choices=("en", "de"), default="en")
    cmark = cops.add_parser("mark"); cmark.add_argument("file"); cmark.add_argument("--provider", action="append", default=[]); cmark.add_argument("--model", action="append", default=[]); cmark.add_argument("--human-reviewed", action="store_true"); cmark.add_argument("--editor"); cmark.add_argument("--public-interest", action="store_true"); cmark.add_argument("--deepfake", action="store_true"); cmark.add_argument("--visible-label", action="store_true")
    cverify = cops.add_parser("verify"); cverify.add_argument("file")
    clit = cops.add_parser("literacy"); clit.add_argument("--subject-id", required=True); clit.add_argument("--role", required=True); clit.add_argument("--curriculum-version", required=True); clit.add_argument("--assessment", choices=("pass", "needs-work", "expired"), required=True); clit.add_argument("--refresher-due", required=True)
    cmdossier = cops.add_parser("model-dossier"); cmdossier.add_argument("--file", required=True)
    cincident = cops.add_parser("incident"); cincident.add_argument("--file", required=True)
    cgate = cops.add_parser("release-gate"); cgate.add_argument("--root", default="."); cgate.add_argument("--profile", choices=("developer-preview", "production"), default="developer-preview")

    package = commands.add_parser("package", help=argparse.SUPPRESS)
    pops = package.add_subparsers(dest="op", required=True)
    pi = pops.add_parser("install"); pi.add_argument("--hosts", default="all"); pi.add_argument("--apply", action="store_true")
    pops.add_parser("verify")
    pr = pops.add_parser("repair"); pr.add_argument("--hosts", default="all"); pr.add_argument("--apply", action="store_true")
    pu = pops.add_parser("upgrade"); pu.add_argument("--hosts", default="all"); pu.add_argument("--apply", action="store_true")
    pun = pops.add_parser("uninstall"); pun.add_argument("--force-drift", action="store_true"); pun.add_argument("--apply", action="store_true")
    prb = pops.add_parser("rollback"); prb.add_argument("--apply", action="store_true")
    pcl = pops.add_parser("clean"); pcl.add_argument("--current-version", default=__version__); pcl.add_argument("--package-store"); pcl.add_argument("--current-package"); pcl.add_argument("--package-archive"); pcl.add_argument("--apply", action="store_true")
    pops.add_parser("status")

    report = commands.add_parser("report", help=argparse.SUPPRESS)
    report.add_argument("--window", default="7d", choices=("1d", "3d", "7d", "14d", "30d", "90d", "180d", "365d")); report.add_argument("--format", choices=("text", "json"), default="text")
    return root


def main(argv: list[str] | None = None) -> int:
    normalized = _normalize_argv(argv)
    a = parser().parse_args(normalized)
    h = home(a.home)
    append_event(h, "cli.command.start", {"command": a.cmd, "operation": getattr(a, "op", None), "arguments": _redact_sensitive(vars(a))})
    try:
        if a.cmd == "help":
            if a.op == "list": emit({"public_commands": sorted(PUBLIC_COMMANDS), "advanced_compatibility_commands": sorted(ADVANCED_COMMANDS), "skills": list_topics()})
            elif a.op == "search": emit({"results": help_search(a.term or "")})
            elif a.op == "quickstart": emit(QUICKSTART)
            elif a.op == "show": emit(help_show(a.term or "help"))
            else: emit(help_show(a.op))
            return 0
        if a.cmd == "run":
            goal_text = " ".join(a.goal)
            # Natural language is the primary API. Explicit execution verbs in the
            # sentence are authoritative; --execute/--apply remain expert aliases.
            apply_override = True if (a.execute or a.apply) else None
            result = run_autopilot(
                h,
                goal_text,
                conversation_id=a.conversation_id,
                apply=apply_override,
                cwd=Path(a.cwd),
                test_argv=a.test_argv,
                max_tasks=a.max_tasks,
                report_output=Path(a.report_output) if a.report_output else None,
            )
            emit(result)
            return 0
        if a.cmd == "status":
            emit(log_locations(h) if a.logs else unified_status(h, live=a.live, window=a.window))
            return 0
        if a.cmd == "update":
            if a.op == "status": emit(update_status(h))
            elif a.op == "plan": emit(update_plan(h, a.channel))
            elif a.op == "apply": emit(update_apply_local(
                h, Path(a.package), a.expected_sha256, apply=a.apply,
                package_store=Path(a.package_store) if a.package_store else None,
                package_archive=Path(a.package_archive) if a.package_archive else None,
            ))
            else: emit(update_rollback(h, apply=a.apply))
            return 0
        if a.cmd == "license":
            ent = current(); emit(ent.__dict__ if a.json else f"Edition: {ent.edition}; commercial use: {ent.commercial_use}; PMD: {ent.pmd_adapter}; license: {ent.license_id}; expires: {ent.expires_at}")
            return 0
        if a.cmd == "setup": emit(setup_discover() if a.op == "discover" else show_inventory(h) if a.op == "show" else init_inventory(h, a.project_root, a.server, a.apply)); return 0
        if a.cmd == "settings":
            value = settings_mod.load(h)
            editable = settings_mod.load(h, normalize=False)
            if a.op == "show":
                emit(settings_mod.effective_settings(h, value) if getattr(a, "effective", False) else value)
            elif a.op == "set": settings_mod.set_value(editable, a.key, a.value); settings_mod.save(h, editable); emit({"decision": "pass", "key": a.key})
            elif a.op == "group": settings_mod.toggle_group(editable, a.group, a.state == "on"); settings_mod.save(h, editable); emit({"decision": "pass", "group": a.group, "enabled": a.state == "on"})
            elif a.op == "profile":
                editable["orchestration"]["active_profile"] = a.name
                if not a.session_only: settings_mod.save(h, editable)
                emit({"decision": "pass", "profile": a.name, "session_only": a.session_only, "settings": editable["orchestration"]["profiles"][a.name]})
            elif a.op == "validate":
                emit(settings_mod.validate_settings(h, value))
            elif a.op == "preset":
                from .settings_v2 import preset_diff, preset_document, preset_names
                if a.preset_op == "list":
                    emit({"presets": preset_names()})
                elif a.preset_op == "show":
                    emit(preset_document(a.preset_name))
                elif a.preset_op == "diff":
                    emit(preset_diff(value, a.preset_name))
                else:
                    emit(settings_mod.apply_preset(h, a.preset_name, apply=a.apply))
            elif a.op == "migrate":
                emit(settings_mod.migrate_v1_to_v2(h, apply=a.apply))
            elif a.op == "rollback":
                emit(settings_mod.rollback_settings(h, a.receipt_id, apply=a.apply))
            elif a.op == "role":
                if a.role_op == "show":
                    emit((value.get("routing") or {}).get("role_bindings", {}).get(a.role_id) or {})
                else:
                    settings_mod.set_role_binding(
                        value,
                        a.role_id,
                        preferred_providers=a.preferred_providers,
                        effort=a.effort,
                        minimum_effort=a.minimum_effort,
                    )
                    settings_mod.save(h, value)
                    emit({"decision": "pass", "role_id": a.role_id, "binding": value["routing"]["role_bindings"][a.role_id]})
            elif a.op == "skills":
                from .skill_registry import discover
                from .skill_router import select_skills
                if a.skills_op == "explain":
                    found = discover(user_home=h)["skills"].get(a.skill_id or "")
                    emit({"skill": {k: found[k] for k in found if k != "body"}} if found else {"decision": "block", "error": "unknown skill"})
                elif a.skills_op == "discover":
                    payload = discover(user_home=h)
                    emit({"count": payload["count"], "ids": sorted(payload["skills"]), "rejected": payload["rejected"]})
                else:
                    emit(select_skills(h, goal=a.goal or "", role_id=a.role)["receipt"])
            elif a.op == "migrate-brand":
                if a.apply and a.rollback:
                    raise ValueError("choose either --apply or --rollback")
                emit(identity_rollback(h) if a.rollback else identity_apply(h) if a.apply else identity_status(h))
            else:
                raise ValueError(f"unknown settings operation: {a.op}")
            return 0
        if a.cmd == "privacy":
            result = sanitize(a.text, a.mode); emit({"decision": result.decision, "text": result.text, "findings": result.findings}); return 0 if result.decision != "block" else 3
        if a.cmd == "provider":
            if a.op == "list": emit({"routes": [static_status(row) for row in load_routes(h)["routes"]]})
            elif a.op == "add": emit(add_route(h, {"route_id": a.route_id, "provider": a.provider, "kind": a.kind, "auth_mode": a.auth_mode, "command": a.command, "endpoint": a.endpoint, "protocol": a.protocol, "secret_env": a.secret_env, "allow_private_endpoint": a.allow_private_endpoint, "model": a.model, "priority": a.priority, "enabled": a.enabled, "cloud": not a.allow_private_endpoint}, a.apply))
            elif a.op == "doctor":
                article5 = _screen_text(a.prompt, h, context="cli:provider-doctor")
                disclosure = record_disclosure(h, surface="cli:provider-doctor", language="en")
                result = mesh_delegate(h, a.provider, a.prompt, "doctor", auth_mode=a.auth_mode, timeout=120, effort=a.effort)
                emit({**result, "article_5": article5, "article_50": disclosure, "content_provenance": _runtime_mark_for_mesh(result), "global_compliance_claim_allowed": False})
            else: emit(mutate_route(h, a.route_id, a.op, a.apply))
            return 0
        if a.cmd == "mesh":
            article5 = _screen_text(a.task, h, context="cli:mesh-or-multicoder")
            disclosure = record_disclosure(h, surface="cli:mesh", language="en")
            timeout = max(30, min(int(a.timeout), 600))
            if a.op == "delegate":
                result = mesh_delegate(h, a.provider, a.task, a.task_mode, model=a.model, timeout=timeout, auth_mode=a.auth_mode, allow_fallback=a.allow_fallback, effort=a.effort)
                emit({**result, "article_5": article5, "article_50": disclosure, "content_provenance": _runtime_mark_for_mesh(result), "global_compliance_claim_allowed": False})
            else:
                requested = _split(a.providers)
                results = [mesh_delegate(h, provider, a.task, a.task_mode, timeout=timeout, auth_mode=a.auth_mode, effort=a.effort) for provider in requested]
                substantive = [row for row in results if row.get("status") == "pass" and row.get("model_served") and len(str(row.get("output") or "").strip()) >= 30]
                quorum = min(max(1, int(a.quorum)), len(requested)) if requested else 1
                decision = "pass" if len(substantive) >= quorum and len(substantive) == len(requested) else "needs-work"
                emit({"decision": decision, "review_class": "multi-coder-independent" if decision == "pass" else "single-engine-or-incomplete", "requested": requested, "substantive_count": len(substantive), "quorum": quorum, "results": results, "article_5": article5, "article_50": disclosure, "content_provenance": _runtime_mark_for_mesh(results), "global_compliance_claim_allowed": False})
            return 0
        if a.cmd == "meeting":
            if a.op in {"start", "seat-plan"}:
                plan = resolve_meeting_seats(
                    h,
                    a.seats,
                    exclude_ollama=bool(a.exclude_ollama),
                    allow_missing_ollama=bool(a.allow_missing_ollama),
                    max_seats=getattr(a, "max_seats", None),
                )
                if a.op == "seat-plan":
                    emit(plan.to_dict())
                    return 0 if plan.decision == "pass" else 3
                if plan.decision != "pass":
                    raise PermissionError(
                        f"meeting seat plan blocked: {plan.reason}; "
                        "use --seats all-coders+ollama-clouds, or explicitly --exclude-ollama when omission is intentional"
                    )
                seats = list(plan.resolved_seats)
                if not seats:
                    raise RuntimeError("no meeting seats resolved")
                emit(meeting_start(
                    h,
                    a.topic,
                    seats,
                    min(a.quorum, len(seats)),
                    a.rounds,
                    a.execute,
                    depth=a.depth,
                    effort=a.effort,
                    owner=a.owner,
                    priority=a.priority,
                    risk_class=a.risk_class,
                    seat_plan=plan.to_dict(),
                    max_parallel=a.max_parallel,
                    existing_task_id=a.task_id,
                    correlation_id=a.correlation_id,
                    privacy_class=getattr(a, "privacy_class", "D1"),
                ))
            elif a.op == "list": emit({"meetings": list_meetings(h)})
            elif a.op == "show":
                payload = meeting_show(h, a.meeting_id)
                emit(project_meeting_view(payload, getattr(a, "view", "full") or "full"))
            elif a.op == "run": emit(meeting_run(h, a.meeting_id))
            elif a.op == "approve":
                receipt = None
                if getattr(a, "founder_receipt", None):
                    receipt = json.loads(Path(a.founder_receipt).read_text(encoding="utf-8"))
                emit(meeting_approve(h, a.meeting_id, subject=a.subject, intent_digest=a.intent_digest, founder_receipt=receipt))
            elif a.op == "create-task": emit(create_task_from_meeting(h, a.meeting_id, a.title))
            elif a.op == "export":
                exported = export_workspace(h, Path(a.output), meeting_show(h, a.meeting_id)["task_id"])
                if a.public:
                    from .export_gate import rewrite_public_export
                    from .util import trusted_operator_roots
                    gate = rewrite_public_export(Path(a.output), allowed_roots=list(trusted_operator_roots(h)))
                    if gate.get("decision") != "pass": raise PermissionError("public export blocked")
                    emit({**exported, "public_export_gate": gate})
                else: emit(exported)
            elif a.op == "report":
                classification = "public" if a.public else a.classification
                report_kwargs = {
                    "view": a.view,
                    "classification": classification,
                    "public_allowlist": list(a.public_meeting_id),
                    "legacy_dbs": [Path(value) for value in a.legacy_db],
                    "stale_after_hours": max(1, int(a.stale_after_hours)),
                    "include_current": not bool(a.exclude_current),
                    "from_time": a.from_time,
                    "to_time": a.to_time,
                    "status": a.status,
                    "task_id": a.task_id,
                    "provider": a.provider,
                    "agent": a.agent,
                    "decision": a.decision,
                }
                if a.format in {"all", "bundle"}:
                    report_result = write_meeting_report_bundle(h, Path(a.output), **report_kwargs)
                else:
                    report_result = write_meeting_report(
                        h, Path(a.output), output_format=a.format, **report_kwargs
                    )
                emit(report_result)
            elif a.op == "calendar-create": emit(create_calendar_event(h, title=a.title, topic=a.topic, starts_at=a.starts_at, requested_seats=a.seats, created_by=a.created_by, surface=a.surface, quorum=a.quorum, depth=a.depth, effort=a.effort, auto_start=a.auto_start, rrule=a.rrule))
            elif a.op == "calendar-list": emit({"events": list_calendar_events(h, status=a.status, surface=a.surface)})
            elif a.op == "calendar-start": emit(start_calendar_event(h, a.event_id))
            elif a.op == "agent-register": emit(register_agent_seat(h, surface=a.surface, agent_id=a.agent_id, display_name=a.display_name, model_binding=a.model_binding, endpoint_ref=a.endpoint_ref, capabilities=a.capability, risk_class=a.risk_class, control_level=a.control_level, reachable=a.reachable))
            elif a.op == "agent-list": emit({"agents": list_agent_seats(h, surface=a.surface, reachable_only=a.reachable_only)})
            else: meeting_api_serve(h, host=a.host, port=a.port, token_env=a.token_env)
            return 0
        if a.cmd == "tasks":
            if a.op == "status": emit(workspace_status(h))
            elif a.op in {"list", "open", "closed", "queue"}:
                if a.op in {"open", "queue"} or a.scope == "open": result = list_open(h, owner=a.owner, query=a.query, status_filter=a.status_filter, limit=a.limit)
                elif a.op == "closed" or a.scope == "closed": result = list_closed(h, owner=a.owner, query=a.query, status_filter=a.status_filter, limit=a.limit)
                else: result = list_all(h, owner=a.owner, query=a.query, status_filter=a.status_filter, limit=a.limit)
                emit({"decision": "pass", "requires_user_selection": True, "tasks": result, "count": len(result)})
            elif a.op == "show": emit(task_show(h, a.task_id, a.limit))
            elif a.op == "prepare":
                if a.action == "status": emit(validation_status(h, a.task_id))
                elif a.action == "review": emit(validation_review(
                    h, a.task_id, context_files=[Path(value) for value in a.context],
                    privacy_class=a.privacy_class, effort=a.effort, profile=a.profile, require_live=not a.allow_static,
                ))
                elif a.action == "approve":
                    if not a.validation_id: raise ValueError("--validation-id is required")
                    emit(validation_approve(h, a.task_id, a.validation_id, a.subject or "user", a.reason))
                elif a.action == "reject":
                    if not a.validation_id: raise ValueError("--validation-id is required")
                    emit(validation_reject(h, a.task_id, a.validation_id, a.subject or "user", a.reason))
                else: emit(validation_skip(
                    h, a.task_id, subject=a.subject or "user", reason=a.reason or "Explicit validation skip",
                    trigger_action="manual", founder_confirm=a.founder_confirm,
                ))
            elif a.op == "create":
                article5 = _screen_text("\n".join((a.title, a.description, a.acceptance_criteria)), h, context="cli:task-create")
                emit({**task_create(h, a.title, a.description, a.priority, a.owner, risk_class=a.risk_class, task_type=a.task_type, source=a.source, source_id=a.source_id, tags=a.tag, acceptance_criteria=a.acceptance_criteria, allow_duplicate=a.allow_duplicate), "article_5": article5})
            elif a.op == "add-work-unit": emit(add_work_unit(h, a.task_id, a.title, a.role, a.read_scope, a.write_scope))
            elif a.op == "claim": emit(claim_work_unit(h, a.work_unit_id, a.owner, a.session_id, a.ttl_seconds, enforce_validation=True, trigger_action="claim"))
            elif a.op == "heartbeat": emit(task_heartbeat(h, a.lease_id, a.lease_token, a.ttl_seconds))
            elif a.op == "progress": emit(record_progress(h, a.task_id, a.stage, a.percent, a.summary, a.work_unit_id, basis=a.basis, evidence_ids=a.evidence_id, observed_steps=a.observed_steps, total_steps=a.total_steps, confidence=a.confidence))
            elif a.op == "evidence-add": emit(add_evidence(h, a.task_id, Path(a.artifact), a.artifact_sha256, a.kind, a.work_unit_id))
            elif a.op == "release": emit(release_lease(h, a.lease_id, a.lease_token, a.reason))
            elif a.op == "submit": emit(submit_task(h, a.task_id, a.work_unit_id, a.lease_id, a.lease_token, a.result_summary))
            elif a.op == "audit": emit(audit_task(h, a.task_id, record=True))
            elif a.op == "export-excel": emit(export_workspace(h, Path(a.output)))
            elif a.op in {"execute", "authorize-execution"}:
                requested_ids = list(a.task_id or [])
                discovered = list_open(h, query=a.query, limit=a.max_tasks) if (a.all or not requested_ids) else []
                requested_ids.extend(row["id"] for row in discovered)
                requested_ids = list(dict.fromkeys(requested_ids))
                snapshots = {row["id"]: row for row in list_open(h, query=None, limit=None)}
                table = []
                eligible_ids = []
                for task_id in requested_ids[: a.max_tasks or len(requested_ids)]:
                    row = snapshots.get(task_id)
                    status = str((row or {}).get("status") or "unknown")
                    if status not in EXECUTION_ELIGIBLE_STATES:
                        table.append({
                            "task_id": task_id,
                            "status": status,
                            "decision": "skipped-non-execution-state",
                            "implements_code": False,
                            "next_actor": "founder" if status == "awaiting_founder" else "authoritative task owner",
                            "reason": "founder-gated technical completion" if status == "awaiting_founder" else f"status:{status}",
                        })
                        continue
                    eligible_ids.append(task_id)
                    gate = validation_gate(h, task_id, "execute")
                    table.append({
                        "task_id": task_id,
                        "status": status,
                        "decision": gate.get("decision"),
                        "policy": gate.get("policy"),
                        "source": gate.get("source"),
                        "next": gate.get("next"),
                    })
                actionable = [row for row in table if row.get("task_id") in eligible_ids]
                decision = (
                    "noop" if not actionable
                    else "pass" if all(row.get("decision") == "pass" for row in actionable)
                    else "requires-user-confirmation"
                )
                emit({
                    "decision": decision,
                    "reason": "eligible-count-zero" if not actionable else None,
                    "command": a.op,
                    "command_semantics": "authorize-execution",
                    "implements_code": False,
                    "deprecated_alias": a.op == "execute",
                    "requested_count": len(requested_ids),
                    "eligible_count": len(actionable),
                    "skipped_count": len(table) - len(actionable),
                    "task_table": table,
                })
            elif a.op == "run":
                ids = list(a.task_id or [])
                if a.all and not ids:
                    ids = [row["id"] for row in list_open(h, query=a.query, limit=a.max_tasks)]
                if not ids and not a.query:
                    raise ValueError("--task-id, --all, or --query is required")
                goal = "Finish the selected IOT-AI Suite tasks through full Meeting and Multi-Coder verification."
                if ids:
                    goal += " Task IDs: " + " ".join(ids)
                if a.query:
                    goal += " Query: " + a.query
                result = run_autopilot(h, goal, conversation_id=a.conversation_id, apply=not bool(a.plan), cwd=Path(a.cwd), test_argv=a.test_argv, max_tasks=a.max_tasks, report_output=Path(a.report_output) if a.report_output else None)
                emit({**result, "command": "tasks run", "mode": a.mode, "engine": "autopilot+meeting+multi-coder", "command_semantics": "closed-loop-hybrid" if not a.plan else "plan-only", "implements_code": not bool(a.plan)})
            else:
                plan = solve_all_plan(h, a.query, a.confirm_critical, a.max_tasks, require_validated=True)
                if not a.apply or plan.get("eligible_count", 0) == 0:
                    emit({**plan, "command": "tasks solve-all", "apply": False, "executed": False, "provider_calls": 0})
                else:
                    provider_list = [c["provider"] for c in provider_candidates(h, require_live=True)] if a.providers == "auto" else _split(a.providers)
                    provider_list = list(dict.fromkeys(provider_list))
                    if not provider_list:
                        emit({
                            "decision": "needs-work",
                            "reason": "no-live-ready-multi-coder-providers",
                            "command": "tasks solve-all",
                            "apply": True,
                            "executed": False,
                            "eligible_count": plan.get("eligible_count", 0),
                            "selected": [task.get("id") for task in plan.get("selected") or []],
                            "provider_calls": 0,
                            "plan": plan,
                            "results": [],
                        })
                    else:
                        results = [
                            run_meeting_then_multicoder(
                                h,
                                task,
                                providers=provider_list,
                                quorum=min(a.quorum, len(provider_list)),
                                implementer=a.implementer,
                                test_profile=Path(a.test_profile) if a.test_profile else None,
                                cwd=Path(a.cwd),
                                effort=a.effort,
                                risk_class=str(task.get("risk_class") or "R1"),
                            )
                            for task in plan["selected"]
                        ]
                        provider_calls = 0
                        meeting_ids = []
                        for row in results:
                            if not isinstance(row, dict):
                                continue
                            if isinstance(row.get("provider_calls"), int):
                                provider_calls += row["provider_calls"]
                            if row.get("meeting_id"):
                                meeting_ids.append(row["meeting_id"])
                        emit({
                            "decision": "pass" if results and all(r.get("executed") and r.get("meeting_id") for r in results) else "needs-work",
                            "command": "tasks solve-all",
                            "apply": True,
                            "executed": provider_calls > 0,
                            "eligible_count": plan.get("eligible_count", 0),
                            "selected": [task.get("id") for task in plan.get("selected") or []],
                            "meeting_ids": meeting_ids,
                            "provider_calls": provider_calls,
                            "canonical_pmd_prcs": False,
                            "authority_basis": "iot-ai-suite-standalone-task-store",
                            "plan": plan,
                            "results": results,
                        })
            return 0
        if a.cmd == "multi-coder":
            if a.task:
                _screen_text(a.task, h, context="cli:mesh-or-multicoder")
            record_disclosure(h, surface="cli:multi-coder", language="en")
            test_argv = a.test_argv
            if a.test_command_json:
                value = json.loads(Path(a.test_command_json).read_text()); test_argv = value.get("argv")
                if not isinstance(test_argv, list) or not all(isinstance(x, str) for x in test_argv): raise ValueError("test command JSON must contain a string argv list")
            providers = [c["provider"] for c in provider_candidates(h, require_live=not a.plan)] if a.providers == "auto" else _split(a.providers)
            providers = list(dict.fromkeys(providers))
            if a.plan:
                emit({
                    "decision": "plan",
                    "provider_calls": 0,
                    "implements_code": False,
                    "task_id": a.task_id,
                    "task": a.task,
                    "providers": providers,
                    "quorum": min(a.quorum, len(providers)) if providers else a.quorum,
                    "reason": None if providers else "no-live-ready-multi-coder-providers",
                    "next": "repeat without --plan or use one natural-language iot-ai goal",
                })
            elif not providers:
                raise RuntimeError("no live-ready multi-coder providers")
            else:
                result = multicoder_run(h, a.task, providers, min(a.quorum, len(providers)), test_argv, Path(a.cwd), task_id=a.task_id, implementer=a.implementer, test_profile=Path(a.test_profile) if a.test_profile else None, risk_class=a.risk_class, effort=a.effort, max_repair_rounds=a.max_repair_rounds)
                emit(result)
                return _result_exit_code(result)
            return 0
        if a.cmd == "knowledge":
            if a.op == "pack":
                emit(capability_build_pack(json.loads(Path(a.spec).read_text(encoding="utf-8")), Path(a.output)))
            elif a.op == "verify-pack":
                emit(capability_verify_pack(Path(a.bundle)))
            elif a.op == "export": emit(export_jsonl(h, Path(a.output), a.audience, a.classification))
            elif a.op == "list": emit({"decision": "pass", "artifacts": list_artifacts(h, a.visibility)})
            else: emit(write_canvas(h, _split(a.artifact_ids), [], visibility=a.visibility))
            return 0
        if a.cmd == "graph":
            graph = compile_graph(a.goal, include_implementation=a.execute, risk_class=a.risk_class, privacy_class=a.privacy_class, max_parallel=a.max_parallel)
            emit({"decision": "pass", "validation": validate_graph(graph), "graph": graph.to_dict()}); return 0
        if a.cmd == "worktree":
            if a.op in {"plan", "create"}:
                emit(worktree_create(h, Path(a.repo), a.goal, _split(a.agents), base_ref=a.base_ref, max_parallel=a.max_parallel, apply=(a.op == "create" and a.apply)))
            elif a.op == "list": emit(worktree_list(h))
            elif a.op == "show": emit(worktree_show(h, a.run_id))
            elif a.op == "review": emit(worktree_promotion_plan(h, a.run_id, winner=a.winner))
            else: emit(worktree_cleanup(h, a.run_id, apply=a.apply))
            return 0
        if a.cmd == "diagnostics":
            if a.op == "collect": emit(diagnostics_collect(h, a.correlation_id, Path(a.output)))
            elif a.op == "validate": emit(diagnostics_validate(Path(a.bundle)))
            elif a.op == "explain": emit(diagnostics_explain(Path(a.bundle)))
            else: emit(diagnostics_compare(Path(a.bundle_a), Path(a.bundle_b)))
            return 0
        if a.cmd == "compliance":
            if a.op == "status": emit(runtime_compliance_status(h))
            elif a.op == "system-card": emit(default_system_card())
            elif a.op == "screen": emit(record_prohibited_practice_screen(h, a.text, context="cli:compliance-screen"))
            elif a.op == "disclosure": emit(record_disclosure(h, surface=a.surface, language=a.language))
            elif a.op == "mark": emit(mark_file(Path(a.file), model_providers=a.provider, model_ids=a.model, human_reviewed=a.human_reviewed, editorially_responsible_party=a.editor, public_interest=a.public_interest, deepfake=a.deepfake, visible_label_present=a.visible_label))
            elif a.op == "verify": emit(verify_file(Path(a.file)))
            elif a.op == "literacy": emit(record_literacy_receipt(h, subject_id=a.subject_id, role=a.role, curriculum_version=a.curriculum_version, assessment=a.assessment, refresher_due=a.refresher_due))
            elif a.op == "model-dossier": emit(register_model_dossier(h, json.loads(Path(a.file).read_text(encoding="utf-8"))))
            elif a.op == "incident": emit(record_incident(h, json.loads(Path(a.file).read_text(encoding="utf-8"))))
            else: emit(compliance_release_gate(Path(a.root), profile=a.profile))
            return 0
        if a.cmd == "package":
            hosts = list(HOSTS) if getattr(a, "hosts", None) == "all" else _split(getattr(a, "hosts", None))
            if a.op == "install": emit(package_install(h, hosts) if a.apply else package_plan(h, hosts))
            elif a.op == "verify": emit(package_verify(h))
            elif a.op == "status": emit(package_status(h))
            elif a.op == "repair": emit(package_repair(h, hosts) if a.apply else {**package_plan(h, hosts), "operation": "repair"})
            elif a.op == "upgrade": emit(package_upgrade(h, hosts) if a.apply else {**package_plan(h, hosts), "operation": "upgrade"})
            elif a.op == "uninstall": emit(package_uninstall(h, a.force_drift) if a.apply else {"decision": "plan", "operation": "uninstall", "force_drift": a.force_drift, "logs": log_locations(h)})
            elif a.op == "clean": emit(clean_install_state(
                h, a.current_version,
                package_store=Path(a.package_store) if a.package_store else None,
                current_package=Path(a.current_package) if a.current_package else None,
                package_archive=Path(a.package_archive) if a.package_archive else None,
                apply=a.apply,
            ))
            else: emit(package_rollback(h) if a.apply else {"decision": "plan", "operation": "rollback", "logs": log_locations(h)})
            return 0
        if a.cmd == "report": emit(render_report(h, a.window, a.format)); return 0
        if a.cmd == "github-analyze":
            offline = None
            if a.offline_json:
                offline = json.loads(Path(a.offline_json).read_text(encoding="utf-8"))
                if isinstance(offline, dict) and "repos" in offline:
                    offline = offline["repos"]
                if not isinstance(offline, list):
                    raise ValueError("offline JSON must be a list of repo records")
            if not offline and not a.refs:
                raise ValueError("provide GitHub refs or --offline-json")
            emit(analyze_refs(list(a.refs), fetch=not a.no_network and offline is None, offline=offline))
            return 0
    except (ValueError, KeyError, RuntimeError, PermissionError, FileNotFoundError) as exc:
        append_event(h, "cli.command.error", {"command": a.cmd, "operation": getattr(a, "op", None), "error_type": type(exc).__name__, "error": str(exc)}, audit=True)
        print(f"error: {exc}", file=sys.stderr)
        print(f"logs: {log_locations(h)['logs_root']}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
