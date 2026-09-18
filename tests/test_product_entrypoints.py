# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-06
"""Customer-facing command controls; synthetic fixtures and no providers."""
from pathlib import Path
from unittest.mock import patch
import pytest

from iot_ai.cli import _normalize_argv, main, parser
from iot_ai.autopilot import run_autopilot
from iot_ai.intent_router import compile_intent


@pytest.mark.parametrize("goal", [
    "Review the fix and do not implement anything.",
    "Inspect the repair without modifying code.",
    "Review the fix.", "Show completed tasks.", "Inspect the prefix configuration.",
    "Prüfen, nicht ausführen.",
])
def test_read_only_intent_cannot_start_execution(goal):
    assert compile_intent(goal)["execution"]["requested"] is False


@pytest.mark.parametrize("goal", ["Review and fix the error", "Finish the task", "Do not stop until complete"])
def test_explicit_execution_remains_an_execution_request(goal):
    assert compile_intent(goal)["execution"]["requested"] is True


def test_new_goal_does_not_inherit_unrelated_product():
    state = {"active_product": "PMD", "selected_task_ids": ["task-abc"]}
    assert compile_intent("Inspect the fixture", conversation_state=state)["scope"]["product"] is None
    assert compile_intent("Continue the remaining tasks", conversation_state=state)["scope"]["product"] == "PMD"


def test_documented_plan_flag_parses_and_is_forwarded(tmp_path):
    args = ["--home", str(tmp_path), "Inspect TASK.md", "--plan"]
    assert parser().parse_args(_normalize_argv(args)).plan is True
    with patch("iot_ai.cli.run_autopilot", return_value={"decision": "plan"}) as run:
        with patch("iot_ai.cli.append_event"), patch("iot_ai.cli.emit"):
            assert main(args) == 0
    assert run.call_args.kwargs["apply"] is False


@pytest.mark.parametrize("decision,code", [("blocked", 1), ("needs-work", 1), ("pass", 0), ("plan", 0), ("noop", 0)])
def test_terminal_cli_exit_reflects_decision(tmp_path, decision, code):
    with patch("iot_ai.cli.run_autopilot", return_value={"decision": decision}):
        with patch("iot_ai.cli.append_event"), patch("iot_ai.cli.emit"):
            assert main(["--home", str(tmp_path), "run", "--goal", "Inspect fixture"]) == code


def test_quickstart_reads_all_nine_criteria_before_any_provider_lookup(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / "examples/quickstart-demo"
    with patch("iot_ai.autopilot.load_state", return_value={}):
        with patch("iot_ai.autopilot.provider_candidates") as providers:
            result = run_autopilot(tmp_path, "Read TASK.md and do not execute.", cwd=fixture)
    providers.assert_not_called()
    assert result["decision"] == "plan"
    assert result["terminal_state"] == "PLAN_READY"
    assert len(result["plan"]["acceptance_criteria"]) == 9
    assert len(result["plan"]["planned_roles"]) == 3
    assert result["plan"]["review_approved"] is False
    assert result["provider_calls"] == 0
    assert list(tmp_path.iterdir()) == []


def test_missing_task_document_is_an_explicit_block(tmp_path):
    with patch("iot_ai.autopilot.load_state", return_value={}):
        with patch("iot_ai.autopilot.provider_candidates") as providers:
            result = run_autopilot(tmp_path, "Read TASK.md and do not execute.", cwd=tmp_path)
    providers.assert_not_called()
    assert result["decision"] == "blocked"
    assert result["provider_calls"] == 0


@pytest.mark.parametrize("control,value", [("--risk-class", "R4"), ("--privacy-class", "D3"),
    ("--profile", "economy"), ("--token-budget", "1"), ("--wall-clock-seconds", "1"),
    ("--max-parallel", "1"), ("--task-validation", "skip")])
def test_unenforced_controls_block_before_autopilot(tmp_path, control, value):
    with patch("iot_ai.cli.run_autopilot") as run:
        with patch("iot_ai.cli.append_event"), patch("iot_ai.cli.emit") as emit:
            result = main(["--home", str(tmp_path), "run", control, value, "--goal", "Implement fixture"])
    assert result == 2
    run.assert_not_called()
    assert emit.call_args.args[0]["reason"] == "unsupported-goal-controls"
