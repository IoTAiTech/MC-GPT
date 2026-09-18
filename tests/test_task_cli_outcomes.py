# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
"""No providers: exact CLI outcomes and requested route/quorum preservation."""
from pathlib import Path
from unittest.mock import patch
import pytest
from iot_ai.cli import main, _result_exit_code
from iot_ai.task_execute import run_meeting_then_multicoder
from iot_ai.tasks import create


@pytest.mark.parametrize('decision',['block','blocked','failed','fail','error','needs-work','requires-user-confirmation'])
def test_all_failure_spellings_have_failure_exit(decision):
    assert _result_exit_code({'decision':decision})==1


def test_real_incomplete_submission_returns_nonzero(tmp_path):
    task=create(tmp_path,'Synthetic CLI task')
    with patch('iot_ai.cli.emit') as emit:
        assert main(['--home',str(tmp_path),'tasks','submit','--task-id',task['task_id']])==1
    assert emit.call_args.args[0]['decision']=='needs-work'
    assert emit.call_args.args[0]['founder_queue_entered'] is False


@pytest.mark.parametrize('command,dependency',[(('audit','task-synthetic'),'audit_task'),
                                              (('run','--task-id','task-synthetic'),'run_autopilot')])
def test_task_commands_propagate_failed_outcome(tmp_path,command,dependency):
    with patch('iot_ai.cli.'+dependency,return_value={'decision':'needs-work'}), patch('iot_ai.cli.emit'):
        assert main(['--home',str(tmp_path),'tasks',*command])==1


@pytest.mark.parametrize('decision,exit_code',[('needs-work',1),('blocked',1),('approve',0)])
def test_executed_calls_do_not_manufacture_success(tmp_path,decision,exit_code):
    plan={'decision':'pass','eligible_count':1,'selected':[{'id':'task-synthetic','risk_class':'R1'}]}
    with patch('iot_ai.cli.solve_all_plan',return_value=plan), patch('iot_ai.cli.emit') as emit:
        with patch('iot_ai.cli.run_meeting_then_multicoder',return_value={'decision':decision,'executed':True,'meeting_id':'synthetic-meeting','provider_calls':1}) as run:
            code=main(['--home',str(tmp_path),'tasks','solve-all','--apply','--providers','codex,grok','--quorum','2'])
    assert code==exit_code
    assert emit.call_args.args[0]['decision']==('pass' if exit_code==0 else 'needs-work')
    assert run.call_args.kwargs['quorum']==2


def test_cli_never_silently_reduces_quorum(tmp_path):
    plan={'decision':'pass','eligible_count':1,'selected':[{'id':'task-synthetic'}]}
    with patch('iot_ai.cli.solve_all_plan',return_value=plan), patch('iot_ai.cli.emit') as emit:
        with patch('iot_ai.cli.run_meeting_then_multicoder') as run:
            assert main(['--home',str(tmp_path),'tasks','solve-all','--apply','--providers','codex','--quorum','2'])==1
    run.assert_not_called()
    assert emit.call_args.args[0]['reason']=='requested-quorum-unavailable'
    assert emit.call_args.args[0]['provider_calls']==0


def test_wrapper_preserves_exact_models_and_quorum(tmp_path):
    providers=['codex@synthetic-model-a','grok@synthetic-model-b']
    accepted={'decision':'pass','task_id':'task-synthetic','meeting_id':'synthetic-meeting','status':'awaiting-user-decision',
              'plan_acceptance':'accepted','plan_digest':'a'*64,'hard_gates':{'same_digest':True}}
    with patch('iot_ai.task_execute.meeting_start',return_value=accepted) as meeting:
        with patch('iot_ai.task_execute.validation_gate',return_value={'decision':'pass'}):
            with patch('iot_ai.task_execute.multicoder_run',return_value={'decision':'needs-work','provider_calls':1}) as run:
                result=run_meeting_then_multicoder(tmp_path,{'id':'task-synthetic'},providers=providers,quorum=2)
    assert meeting.call_args.args[2:4]==(providers,2)
    assert run.call_args.kwargs['providers']==providers
    assert run.call_args.kwargs['quorum']==2
    assert result['decision']=='needs-work'


@pytest.mark.parametrize('quorum',[0,2,True])
def test_direct_wrapper_quorum_blocks_before_meeting(tmp_path,quorum):
    with patch('iot_ai.task_execute.meeting_start') as meeting:
        result=run_meeting_then_multicoder(tmp_path,{'id':'task-synthetic'},providers=['codex'],quorum=quorum)
    meeting.assert_not_called()
    assert result['decision']=='blocked'
    assert result['provider_calls']==0


@pytest.mark.parametrize('control,value',[('--providers','codex'),('--quorum','3'),('--implementer','grok'),
    ('--test-profile','profile.json'),('--risk-class','R4'),('--effort','low'),('--max-repair-rounds','0'),('--mode','multi-coder')])
def test_task_run_rejects_unenforced_controls(tmp_path,control,value):
    with patch('iot_ai.cli.run_autopilot') as run, patch('iot_ai.cli.emit') as emit:
        assert main(['--home',str(tmp_path),'tasks','run','--task-id','task-synthetic',control,value])==2
    run.assert_not_called()
    assert emit.call_args.args[0]['reason']=='unsupported-task-run-controls'


@pytest.mark.parametrize('command',['authorize-execution','execute'])
def test_authorization_refusal_is_nonzero(tmp_path,command):
    with patch('iot_ai.cli.list_open',return_value=[{'id':'task-synthetic','status':'ready'}]):
        with patch('iot_ai.cli.validation_gate',return_value={'decision':'requires-user-confirmation'}), patch('iot_ai.cli.emit') as emit:
            assert main(['--home',str(tmp_path),'tasks',command,'--task-id','task-synthetic'])==1
    assert emit.call_args.args[0]['decision']=='requires-user-confirmation'


@pytest.mark.parametrize('decision',['needs-work','blocked','pass'])
def test_unaccepted_current_meeting_cannot_dispatch(tmp_path,decision):
    rejected={'decision':decision,'meeting_id':'current-rejected','status':'needs-review','hard_gates':{'same_digest':False}}
    with patch('iot_ai.task_execute.meeting_start',return_value=rejected):
        with patch('iot_ai.task_execute.validation_gate',return_value={'decision':'pass'}):
            with patch('iot_ai.task_execute.multicoder_run') as run:
                result=run_meeting_then_multicoder(tmp_path,{'id':'task-synthetic'},providers=['codex','grok'],quorum=2)
    run.assert_not_called()
    assert result['reason']=='planning-meeting-not-accepted'
