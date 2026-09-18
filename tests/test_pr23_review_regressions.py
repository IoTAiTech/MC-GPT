# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-06
"""PR23 boundary reproductions; real checks and synthetic provider responses."""
import json
import os
import subprocess
import sqlite3
import sys
import textwrap
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import pytest

from iot_ai import agentic
from iot_ai.exec_pin import test_env as command_env
from iot_ai.tasks import create, show
from iot_ai.test_execution_evidence import CheckCommand, HostTestRunner, verify_test_execution
from iot_ai.workspace import connect_read, connect_write, one
from tests.test_host_test_execution import execute, run_graph, scope, verify


def fallback_run(home, *, response_effort="medium", requested=None, routing=None):
    graph = SimpleNamespace(risk_class="R2", privacy_class="D0",
                            graph_id="fixture-graph", wall_clock_seconds=60)
    node = SimpleNamespace(role_id="implementation-engineer", effort="medium", stage="implementation")
    def row(name):
        return {"candidate_id": "ollama:" + name, "provider": "ollama", "model": name,
                "supported_efforts": ["low", "medium", "high"], "live_ready": True,
                "cloud": False, "receipt": {"authenticated": True,
                    "model_identity_verified": True, "model_served": name,
                    "effort_supported": ["low", "medium", "high"]}}
    alternative = row("fixture-alternative")
    if requested is not None:
        alternative["requested_effort"] = requested
    primary = {**row("fixture-primary"), "requested_effort": "medium",
               "fallback_candidates": [alternative]}
    def delegate(*args, **kwargs):
        if kwargs["model"] == "fixture-primary":
            return {"status": "blocked", "failure_class": "quota", "provider": "ollama"}
        return {"status": "pass", "provider": "ollama", "model_served": kwargs["model"],
                "output": '{"summary":"synthetic response"}',
                "adapter_request_effort": kwargs["effort"], "effort_effective": response_effort}
    with patch("iot_ai.settings_v2.current_entitlements", return_value=SimpleNamespace(max_effort="high")):
        with patch("iot_ai.agentic.delegate", side_effect=delegate) as called:
            result = agentic._default_provider_executor(home, {node.role_id: primary}, graph,
                max_effort="high", routing=routing)(node, "Synthetic check", {})
    return result, called


@pytest.mark.parametrize("level", ["medium", "high"])
def test_fallback_has_its_own_resolved_effort(tmp_path, level):
    routing = {"effort": {"by_model": {"fixture-alternative": level}}}
    result, calls = fallback_run(tmp_path, response_effort=level, routing=routing)
    assert result["status"] == "pass"
    assert result["fallback_used"] is True
    assert result["effort_receipt"]["stages"]["settings"] == level
    assert calls.call_args.kwargs["effort"] == level


@pytest.mark.parametrize("requested", [False, 0, [], "invalid"])
def test_malformed_fallback_effort_still_blocks(tmp_path, requested):
    result, calls = fallback_run(tmp_path, requested=requested)
    assert result["status"] == "blocked"
    assert calls.call_count == 1


@pytest.mark.parametrize("response", [None, "low"])
def test_fallback_does_not_invent_response_effort(tmp_path, response):
    result, calls = fallback_run(tmp_path, response_effort=response)
    assert result["status"] == "blocked"
    assert result["failure_class"] == "effort-evidence-mismatch"
    assert calls.call_count == 2


@pytest.mark.parametrize("mutation", ["source", "receipt", "ledger"])
def test_last_moment_drift_cannot_complete(scope, mutation):
    home = scope[0]
    original = agentic._finish_run
    def finish(*args, **kwargs):
        if mutation == "source":
            (home / "verification-source" / "fixture.txt").write_text("late change")
        elif mutation == "receipt":
            connection = connect_read(home)
            try:
                path = one(connection, "SELECT output_path FROM test_results LIMIT 1")["output_path"]
            finally:
                connection.close()
            Path(path).with_name("receipt.json").write_text("corrupted")
        else:
            connection = connect_write(home)
            try:
                connection.execute("UPDATE test_results SET exit_code=9")
                connection.commit()
            finally:
                connection.close()
        return original(*args, **kwargs)
    with patch("iot_ai.agentic._finish_run", side_effect=finish):
        result = run_graph(home)
    assert result["decision"] != "pass"
    assert result["failure_class"] == "test-execution-evidence-invalid-at-completion"
    task = show(home, result["task_id"])["task"]
    assert task["status"] == "needs-work"
    assert task["task_progress"] < 100
    connection = connect_read(home)
    try:
        assert one(connection, "SELECT status FROM meetings WHERE id=?", (result["meeting_id"],))["status"] == "needs-review"
    finally:
        connection.close()


def test_direct_completion_requires_host_guard(scope):
    home = scope[0]
    task_id = create(home, title="Check completion guard")["task_id"]
    result = {"decision": "pass", "results": {
        "final-plan-gate": {"output": {"decision": "accept"}},
        "final-audit": {"output": {"decision": "pass"}}}}
    agentic._finish_run(home, task_id, "fixture-meeting", result, True)
    assert result["decision"] != "pass"
    assert show(home, task_id)["task"]["status"] == "needs-work"


def test_evidence_verification_keeps_callers_transaction_open(scope):
    handle = execute(scope)
    home, runner, binding = scope
    connection = connect_write(home)
    try:
        connection.execute("BEGIN IMMEDIATE")
        result = verify_test_execution(handle, user_home=home, binding=binding,
            current_source_sha256=runner.current_source_digest(),
            profile_sha256=runner.profile_sha256, connection=connection)
        assert result["decision"] == "pass"
        assert connection.in_transaction
        connection.execute("UPDATE test_results SET exit_code=9")
        connection.rollback()
    finally:
        connection.close()
    assert verify(scope, handle)["decision"] == "pass"


def test_throwing_completion_guard_blocks(scope):
    home = scope[0]
    task_id = create(home, title="Throwing completion guard")["task_id"]
    result = {"decision": "pass", "results": {
        "final-plan-gate": {"output": {"decision": "accept"}},
        "final-audit": {"output": {"decision": "pass"}}}}
    def guard(connection):
        assert connection.in_transaction
        raise ValueError("unavailable evidence")
    agentic._finish_run(home, task_id, "fixture-meeting", result, True, completion_verifier=guard)
    assert result["decision"] == "blocked"
    assert show(home, task_id)["task"]["status"] == "needs-work"


@pytest.mark.parametrize("fd", [1, 2])
def test_burst_output_never_exceeds_persisted_cap(scope, fd):
    home, original, binding = scope
    code = f"import os; os.write({fd}, b'x' * (20 * 1024 * 1024))"
    runner = HostTestRunner(cwd=original.cwd, current_source_digest=original.current_source_digest,
        commands=[CheckCommand((sys.executable, "-I", "-c", code))])
    with patch("iot_ai.test_execution_evidence.MAX_OUTPUT", 4096):
        with pytest.raises(ValueError, match="test-output-limit"):
            execute((home, runner, binding))
    logs = list((home / "evidence-fixture").glob("*/check-01.log"))
    assert len(logs) == 1
    assert logs[0].stat().st_size <= 4096
    connection = connect_read(home)
    try:
        assert one(connection, "SELECT count(*) AS n FROM test_results")["n"] == 0
    finally:
        connection.close()


@pytest.mark.parametrize("size", [0, 4095, 4096])
def test_at_or_below_output_cap_preserves_success(scope, size):
    home, original, binding = scope
    runner = HostTestRunner(cwd=original.cwd, current_source_digest=original.current_source_digest,
        commands=[CheckCommand((sys.executable, "-I", "-c", f"import os; os.write(1, b'x'*{size})"))])
    with patch("iot_ai.test_execution_evidence.MAX_OUTPUT", 4096):
        handle = execute((home, runner, binding))
        assert verify((home, runner, binding), handle)["decision"] == "pass"
        assert (handle.root / "check-01.log").stat().st_size == size


def test_closed_output_still_waits_for_exit_or_timeout(scope):
    home, original, binding = scope
    code = "import os,time; os.close(1); os.close(2); time.sleep(30)"
    runner = HostTestRunner(cwd=original.cwd, current_source_digest=original.current_source_digest,
        commands=[CheckCommand((sys.executable, "-I", "-c", code), 1)])
    result = verify((home, runner, binding), execute((home, runner, binding)))
    assert result["decision"] == "block"
    assert result["test_results"][0]["exit_code"] != 0


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group behavior")
def test_normal_descendant_with_open_pipe_is_cleaned_up(scope):
    home, original, binding = scope
    code = "import os,time; pid=os.fork(); time.sleep(30) if pid == 0 else None"
    runner = HostTestRunner(cwd=original.cwd, current_source_digest=original.current_source_digest,
        commands=[CheckCommand((sys.executable, "-I", "-c", code), 2)])
    assert verify((home, runner, binding), execute((home, runner, binding)))["decision"] == "pass"


@pytest.mark.parametrize("outcome,step_outcome", [("pass", "success"), ("skipped", "success"),
    ("failure", "failure"), ("error", "failure"), ("pass", "failure"), ("pass", "cancelled")])
def test_qualification_script_rejects_missing_execution(tmp_path, outcome, step_outcome):
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/runtime-boundary-qualification.yml").read_text()
    step = workflow.split("      - name: Seal minimal qualification evidence\n", 1)[1]
    script = textwrap.dedent(step.split("          python - <<'PYCODE'\n", 1)[1].split("          PYCODE", 1)[0])
    marker = "" if outcome == "pass" else f"<{outcome}/>"
    (tmp_path / "junit.xml").write_text(f'<testsuites><testsuite><testcase name="fixture">{marker}</testcase></testsuite></testsuites>')
    environment = command_env()
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, env=environment,
                              capture_output=True, text=True, check=True, timeout=20).stdout.strip()
    git("init", "-q")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + str(tmp_path / "no-hooks"),
        "commit", "--allow-empty", "-qm", "Synthetic qualification fixture")
    environment.update(EVIDENCE_DIR=str(tmp_path), EXPECTED_HEAD=git("rev-parse", "HEAD"),
                       TEST_STEP_OUTCOME=step_outcome)
    result = subprocess.run([sys.executable, "-I", "-c", script], cwd=tmp_path,
                            env=environment, capture_output=True, text=True, timeout=20)
    passed = outcome == "pass" and step_outcome == "success"
    assert result.returncode == (0 if passed else 1), result.stderr
    if not passed:
        assert "boundary-tests-failed" in result.stderr
    receipt = json.loads((tmp_path / "receipt.json").read_text())
    assert receipt["decision"] == ("pass" if passed else "block")


@pytest.mark.parametrize("provider", ["gemini", "ollama"])
def test_receipt_effort_support_constrains_dispatch(provider):
    from iot_ai.provider_catalog import apply_catalog_to_candidate
    from iot_ai.runtime_gates import resolve_dispatch_effort
    row = {"provider": provider, "model": "fixture-model", "requested_effort": "high",
           "receipt": {"effort_supported": ["low"]}}
    candidate = apply_catalog_to_candidate(row)
    with patch("iot_ai.settings_v2.current_entitlements", return_value=SimpleNamespace(max_effort="high")):
        decision = resolve_dispatch_effort(candidate, node_effort="high", max_effort="high")
    assert candidate["supported_efforts"] == ["low"]
    assert decision["effective_effort"] == "low"
    assert apply_catalog_to_candidate(candidate)["supported_efforts"] == ["low"]


@pytest.mark.parametrize("declared,observed,expected", [
    (["low", "high"], ["low"], ["low"]), ([], ["low"], []),
    (["low"], [], []), (None, ["low"], ["low"]), (["low"], None, ["low"])])
def test_route_and_readiness_capabilities_are_intersected(declared, observed, expected):
    from iot_ai.provider_catalog import apply_catalog_to_candidate
    row = {"provider": "ollama", "model": "fixture-model", "supported_efforts": declared,
           "receipt": {"effort_supported": observed}}
    assert apply_catalog_to_candidate(row)["supported_efforts"] == expected


@pytest.mark.parametrize("support", [None, False, "low", [False], ["not-an-effort"]])
def test_absent_or_invalid_runtime_capability_cannot_grant_dispatch(support):
    from iot_ai.provider_catalog import apply_catalog_to_candidate
    row = {"provider": "gemini", "model": "fixture-model", "receipt": {"effort_supported": support}}
    assert apply_catalog_to_candidate(row)["catalog_block"] is True


def test_runtime_receipt_support_reaches_actual_adapter_request(tmp_path):
    from tests.test_effort_settings_parity import dispatch_fixture, provider_fixture
    response = provider_fixture()
    response.update(adapter_request_effort="low", effort_effective="low")
    result, calls = dispatch_fixture(tmp_path, response, supported_efforts=None,
        receipt={"authenticated": True, "model_identity_verified": True,
                 "model_served": "fixture-local", "effort_supported": ["low"]})
    assert result["status"] == "pass"
    assert calls.call_args.kwargs["effort"] == "low"
    assert result["effort_receipt"]["provider_supported_efforts"] == ["low"]


def test_two_graphs_retain_their_own_plan_rows(scope):
    from iot_ai.graph_runtime import compile_graph, _persist_graph_start, _persist_node
    home = scope[0]
    first = compile_graph("First synthetic goal")
    second = compile_graph("Second synthetic goal")
    for graph in (first, second):
        _persist_graph_start(home, graph)
        node = next(node for node in graph.nodes if node.node_id == "final-plan-gate")
        _persist_node(home, graph, node, {"status": "pass", "output": {"decision": "accept", "graph": graph.graph_id}})
    connection = connect_read(home)
    try:
        for graph in (first, second):
            assert one(connection, "SELECT status FROM graph_nodes WHERE graph_id=? AND id=?",
                       (graph.graph_id, "final-plan-gate"))["status"] == "pass"
        assert one(connection, "SELECT count(*) AS n FROM graph_nodes")["n"] == 2
    finally:
        connection.close()


def legacy_workspace():
    from iot_ai.workspace import SCHEMA
    sql = SCHEMA.replace("CREATE TABLE IF NOT EXISTS graph_nodes(\n id TEXT NOT NULL,",
                         "CREATE TABLE IF NOT EXISTS graph_nodes(\n id TEXT PRIMARY KEY,")
    sql = sql.replace(" PRIMARY KEY(graph_id,id),\n", "")
    connection = sqlite3.connect(":memory:")
    connection.executescript(sql)
    connection.execute("INSERT INTO meta VALUES('schema_version','6')")
    connection.execute("INSERT INTO graph_runs(id,correlation_id,goal,risk_class,privacy_class,status,token_budget,wall_clock_seconds,max_parallel,created_at,updated_at) VALUES('g1','c1','fixture','R2','D0','pass',10,10,1,'t','t')")
    connection.execute("INSERT INTO graph_nodes(id,graph_id,role_id,node_type,stage,required,status,created_at,updated_at) VALUES('final-plan-gate','g1','fixture','gate','plan',1,'pass','t','t')")
    connection.commit()
    return connection


def test_legacy_node_migration_preserves_rows_and_is_idempotent():
    from iot_ai.workspace import _initialize
    connection = legacy_workspace()
    try:
        before = connection.execute("SELECT * FROM graph_nodes").fetchall()
        _initialize(connection)
        _initialize(connection)
        assert connection.execute("SELECT * FROM graph_nodes").fetchall() == before
        keys = {row[1]: row[5] for row in connection.execute("PRAGMA table_info(graph_nodes)")}
        assert (keys["graph_id"], keys["id"]) == (1, 2)
        assert connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "7"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_legacy_node_migration_rolls_back_failed_swap():
    from iot_ai.workspace import _initialize
    connection = legacy_workspace()
    try:
        before = connection.execute("SELECT * FROM graph_nodes").fetchall()
        connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_ALTER_TABLE else sqlite3.SQLITE_OK)
        with pytest.raises(sqlite3.DatabaseError):
            _initialize(connection)
        connection.set_authorizer(None)
        assert connection.execute("SELECT * FROM graph_nodes").fetchall() == before
        assert connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "6"
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='graph_nodes_v7'").fetchall() == []
    finally:
        connection.close()


@pytest.mark.parametrize("version", ["999", "invalid", "0"])
def test_unknown_schema_is_not_migrated_or_restamped(version):
    from iot_ai.workspace import _initialize
    connection = legacy_workspace()
    try:
        connection.execute("UPDATE meta SET value=? WHERE key='schema_version'", (version,))
        connection.commit()
        before = list(connection.iterdump())
        with pytest.raises(ValueError, match="unsupported-workspace-schema-version"):
            _initialize(connection)
        assert list(connection.iterdump()) == before
    finally:
        connection.close()


def test_concurrent_fresh_initializers_do_not_observe_partial_schema(tmp_path):
    from iot_ai.workspace import _initialize
    path = tmp_path / "synthetic-workspace.db"
    meta_created = threading.Event()
    second_started = threading.Event()
    release_first = threading.Event()
    def initialize(pause=False):
        connection = sqlite3.connect(path, timeout=10)
        try:
            if pause:
                def trace(sql):
                    if sql.lstrip().startswith("CREATE TABLE IF NOT EXISTS tasks("):
                        meta_created.set()
                        assert release_first.wait(5)
                connection.set_trace_callback(trace)
            else:
                second_started.set()
            _initialize(connection)
            return connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(initialize, True)
        try:
            assert meta_created.wait(5)
            second = pool.submit(initialize)
            assert second_started.wait(5)
            # The second initializer either waits for the first or succeeds;
            # it must never fail because it saw only the meta table.
            try:
                assert second.result(timeout=0.2) == "7"
            except FutureTimeout:
                pass  # Correct: the first transaction still holds the lock.
        finally:
            release_first.set()
        assert first.result(timeout=10) == "7"
        assert second.result(timeout=10) == "7"
