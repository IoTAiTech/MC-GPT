# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-05
"""Actual subprocess evidence, corruption, scope, failure and runtime integration."""
import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from iot_ai.agentic import run_goal
from iot_ai.roles import ROLE_CATALOG
from iot_ai.tasks import create, show
from iot_ai.test_execution_evidence import (CheckCommand, HostTestRunner, TestExecutionHandle as _Handle,
                                           execution_binding, source_digest, verify_test_execution)
from iot_ai.workspace import connect_write, connect_read, one
from tests.host_test_fixture import host_runner
from tests.test_agentic import fake_node_executor


@pytest.fixture
def scope(tmp_path, monkeypatch):
    for name in ('XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'IOT_AI_EXPLICIT_HOME', 'IOT_AI_ENTITLEMENT_FILE'):
        monkeypatch.delenv(name, raising=False)
    runner = host_runner(tmp_path)
    task_id = create(tmp_path, title='Verify fixture', acceptance_criteria='Assert fixture content')["task_id"]
    task = show(tmp_path, task_id)["task"]
    binding = execution_binding('fixture-run', task)
    return tmp_path, runner, binding


def execute(scope):
    home, runner, binding = scope
    return runner.run(user_home=home, binding=binding, evidence_root=home/'evidence-fixture')


def verify(scope, handle, **overrides):
    home, runner, binding = scope
    args = dict(user_home=home, binding=binding, current_source_sha256=runner.current_source_digest(),
                profile_sha256=runner.profile_sha256)
    args.update(overrides)
    return verify_test_execution(handle, **args)


def test_real_child_execution_is_persisted_and_reverified(scope):
    handle = execute(scope)
    result = verify(scope, handle)
    assert result['decision'] == 'pass'
    assert result['count_unit'] == 'executed-host-commands-not-framework-testcases'
    c = connect_read(scope[0])
    try:
        assert one(c, 'SELECT count(*) AS n FROM test_results')['n'] == 1
    finally:
        c.close()
    assert result['test_results'][0]['exit_code'] == 0
    assert 'argv' not in result['test_results'][0]
    assert str(handle.root) not in json.dumps(result)
    if os.name == 'posix':
        assert (handle.root/'check-01.log').stat().st_mode & 0o777 == 0o600
        assert handle.root.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize('value', [None, {}, {'decision':'pass'}, True, 'pass'])
def test_json_or_boolean_cannot_be_a_host_evidence_handle(scope, value):
    assert verify(scope, value)['decision'] == 'block'


def test_copy_of_handle_is_not_host_issued(scope):
    handle = execute(scope)
    forged = _Handle(handle.root, handle.receipt_sha256)
    assert verify(scope, forged)['decision'] == 'block'


@pytest.mark.parametrize('field,value', [('run_id','foreign-run'), ('task_id','foreign-task'),
    ('task_revision',999), ('task_revision',True), ('acceptance_sha256','b'*64)])
def test_cross_run_task_revision_or_criteria_replay_is_rejected(scope, field, value):
    handle = execute(scope)
    binding = dict(scope[2]); binding[field] = value
    assert verify(scope, handle, binding=binding)['decision'] == 'block'


@pytest.mark.parametrize('name', ['receipt.json','check-01.log'])
def test_tampered_artifacts_do_not_verify(scope, name):
    handle = execute(scope)
    (handle.root/name).write_text('changed', encoding='utf-8')
    assert verify(scope, handle)['decision'] == 'block'


def test_source_and_profile_drift_block(scope):
    handle = execute(scope)
    assert verify(scope, handle, profile_sha256='b'*64)['decision'] == 'block'
    (scope[1].cwd/'fixture.txt').write_text('changed', encoding='utf-8')
    assert verify(scope, handle)['decision'] == 'block'


def test_ledger_tampering_or_missing_row_blocks(scope):
    handle = execute(scope)
    c = connect_write(scope[0])
    try:
        c.execute("UPDATE test_results SET exit_code=9"); c.commit()
    finally:
        c.close()
    assert verify(scope, handle)['decision'] == 'block'


def test_stale_binding_does_not_start_child(scope):
    home, runner, binding = scope
    stale = dict(binding, task_revision=binding['task_revision']+1)
    with patch('iot_ai.test_execution_evidence.subprocess.Popen') as child:
        with pytest.raises(ValueError, match='test-task-authority-changed'):
            runner.run(user_home=home, binding=stale, evidence_root=home/'never-created')
    child.assert_not_called()
    assert not (home/'never-created').exists()


def test_known_failed_check_does_not_pass_despite_success_text(scope):
    home, original, binding = scope
    runner = HostTestRunner(cwd=original.cwd, current_source_digest=original.current_source_digest,
        commands=[CheckCommand((sys.executable,'-I','-c','print("9999 passed"); raise SystemExit(1)'))])
    scope = home, runner, binding
    result = verify(scope, execute(scope))
    assert result['decision'] == 'block'
    assert result['test_results'][0]['exit_code'] == 1


def test_timeout_is_a_failure_not_a_fake_pass(scope):
    home, original, binding = scope
    runner = HostTestRunner(cwd=original.cwd, current_source_digest=original.current_source_digest,
        commands=[CheckCommand((sys.executable,'-I','-c','import time; time.sleep(30)'),1)])
    result = verify((home,runner,binding), execute((home,runner,binding)))
    assert result['decision'] == 'block'
    assert result['test_results'][0]['exit_code'] != 0


def test_source_mutation_by_check_cannot_issue_evidence(scope):
    home, original, binding = scope
    runner = HostTestRunner(cwd=original.cwd, current_source_digest=original.current_source_digest,
        commands=[CheckCommand((sys.executable,'-I','-c','from pathlib import Path; Path("fixture.txt").write_text("changed")'))])
    with pytest.raises(ValueError, match='test-source-changed'):
        execute((home,runner,binding))
    c=connect_read(home)
    try:
        assert one(c,'SELECT count(*) AS n FROM test_results')['n'] == 0
    finally: c.close()


def test_secret_environment_not_inherited(scope, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-canary')
    monkeypatch.setenv('GH_TOKEN','synthetic-canary')
    home, original, binding = scope
    code = 'import os; assert "OPENAI_API_KEY" not in os.environ; assert "GH_TOKEN" not in os.environ; assert "PYTHONPATH" not in os.environ'
    runner=HostTestRunner(cwd=original.cwd,current_source_digest=original.current_source_digest,
                         commands=[CheckCommand((sys.executable,'-I','-c',code))])
    assert verify((home,runner,binding),execute((home,runner,binding)))['decision']=='pass'


@pytest.mark.parametrize('timeout',[0,-1,True,1.5,901])
def test_invalid_time_budget_is_rejected(scope,timeout):
    with pytest.raises(ValueError, match='test-command-invalid'):
        HostTestRunner(cwd=scope[1].cwd,current_source_digest=scope[1].current_source_digest,
                       commands=[CheckCommand((sys.executable,'-I','-c','pass'),timeout)])


@pytest.mark.parametrize('argv',[(),[],('python',''),('python',True),('python','bad\0argument')])
def test_malformed_argv_is_rejected(scope,argv):
    with pytest.raises(ValueError, match='test-command-invalid'):
        HostTestRunner(cwd=scope[1].cwd,current_source_digest=scope[1].current_source_digest,
                       commands=[CheckCommand(argv)])


@pytest.mark.parametrize('names',[[],['../outside'],['fixture.txt','fixture.txt'],[42],'fixture.txt'])
def test_source_inventory_is_strict(scope,names):
    with pytest.raises(ValueError):
        source_digest(scope[1].cwd,names)


def test_symlink_cannot_replace_receipt(scope):
    handle=execute(scope)
    receipt=handle.root/'receipt.json'; target=handle.root/'other.json'
    target.write_bytes(receipt.read_bytes()); receipt.unlink()
    try:
        receipt.symlink_to(target)
    except (OSError,NotImplementedError):
        pytest.skip('symlinks unavailable on this target')
    assert verify(scope,handle)['decision']=='block'


def run_graph(home, *, failing=False, mutate_at_verifier=False):
    runner=host_runner(home,fail=failing)
    def provider(node,prompt,context):
        value=fake_node_executor(node,prompt,context); output=value['parsed']
        if 'kpis' in output: output['kpis']=[{'name':'acceptance','target':'pass'}]
        frozen=json.loads(prompt).get('node_contract',{}).get('frozen_plan_digest')
        if frozen and 'plan_digest' in output: output['plan_digest']=frozen
        if mutate_at_verifier and node.node_id=='final-verifier':
            (runner.cwd/'fixture.txt').write_text('late mutation',encoding='utf-8')
        return value
    candidates={role:{'candidate_id':f'codex:fixture:{role}','provider':'codex','model':'fixture',
                      'live_ready':True,'cloud':True,'fallback_candidates':[]} for role in ROLE_CATALOG}
    with patch('iot_ai.agentic.select_candidates',return_value=candidates):
        return run_goal(home,'Export inventory with verified checks',execute=True,
                        provider_executor=provider,test_runner=runner)


def test_runtime_success_includes_real_command_evidence(scope):
    result=run_graph(scope[0])
    assert result['decision']=='pass'
    assert result['terminal_state']=='TECHNICAL_COMPLETE_AWAITING_FOUNDER'
    assert result['results']['deterministic-tests']['output']['test_results'][0]['exit_code']==0
    assert result['production_claim'] is False


@pytest.mark.parametrize('failing,mutation',[(True,False),(False,True)])
def test_model_pass_cannot_override_real_failure_or_source_drift(scope,failing,mutation):
    result=run_graph(scope[0],failing=failing,mutate_at_verifier=mutation)
    assert result['decision']!='pass'
    task=show(scope[0],result['task_id'])['task']
    assert task['status']=='needs-work'
    assert task['task_progress']<100
    assert result['terminal_state']=='NEEDS_WORK'


def test_failed_execution_meeting_does_not_advertise_acceptance(scope):
    result = run_graph(scope[0], failing=True)
    connection = connect_read(scope[0])
    try:
        meeting = one(connection, "SELECT status,final_decision FROM meetings WHERE id=?", (result["meeting_id"],))
    finally:
        connection.close()
    assert meeting["status"] == "needs-review"
    assert meeting["final_decision"] == "execution-needs-work"


def test_deleted_test_row_invalidates_receipt(scope):
    handle = execute(scope)
    connection = connect_write(scope[0])
    try:
        connection.execute("DELETE FROM test_results")
        connection.commit()
    finally:
        connection.close()
    assert verify(scope, handle)["decision"] == "block"


def test_pinned_executable_drift_stops_before_child(scope):
    home, runner, binding = scope
    with patch("iot_ai.test_execution_evidence.pin_executable", return_value={"sha256": "b" * 64}):
        with patch("iot_ai.test_execution_evidence.subprocess.Popen") as child:
            with pytest.raises(ValueError, match="test-executable-changed"):
                execute(scope)
    child.assert_not_called()


def test_output_budget_is_enforced(scope):
    home, original, binding = scope
    runner = HostTestRunner(cwd=original.cwd, current_source_digest=original.current_source_digest,
        commands=[CheckCommand((sys.executable, "-I", "-c", "import sys; sys.stdout.write('x'*8192)"))])
    with patch("iot_ai.test_execution_evidence.MAX_OUTPUT", 4096):
        with pytest.raises(ValueError, match="test-output-limit"):
            execute((home, runner, binding))
