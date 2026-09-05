# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-05
"""Settings accept the capability vocabulary; dispatch still enforces its subset."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from iot_ai.runtime_gates import resolve_dispatch_effort
from iot_ai.settings_v2 import EFFORT_ORDER, normalize_role_binding, normalize_routing


@pytest.mark.parametrize('level', EFFORT_ORDER)
def test_role_and_global_effort_share_dispatch_vocabulary(level):
    role = normalize_role_binding({'effort': level, 'minimum_effort': level}, 'security-challenger')
    assert role['effort'] == level
    assert role['minimum_effort'] == level
    assert normalize_routing({'effort': {'default': level}})['effort']['default'] == level


@pytest.mark.parametrize('value', [True, False, 0, 1, [], {}])
def test_present_nonstrings_are_not_silently_treated_as_missing(value):
    with pytest.raises(ValueError):
        normalize_role_binding({'effort': value}, 'security-challenger')
    with pytest.raises(ValueError):
        normalize_role_binding({'minimum_effort': value}, 'security-challenger')


def test_max_setting_does_not_grant_entitlement_or_provider_support():
    routing = {'role_bindings': {'security-challenger': {'effort': 'max', 'minimum_effort': 'max'}}}
    with patch('iot_ai.settings_v2.current_entitlements', return_value=SimpleNamespace(max_effort='medium')):
        result = resolve_dispatch_effort({'requested_effort': 'max', 'supported_efforts': ['low', 'medium', 'max']},
            node_effort='max', max_effort='medium', role_id='security-challenger', routing=routing)
    assert result['decision'] == 'block'
    assert result['effective_effort'] is None


def test_public_schema_and_parser_have_the_same_effort_vocabulary():
    path = Path(__file__).resolve().parents[1] / 'schemas/iot-ai-settings-v2.schema.json'
    routing = json.loads(path.read_text())['properties']['routing']['properties']
    role = routing['role_bindings']['additionalProperties']['properties']
    assert set(role['effort']['enum']) == set(EFFORT_ORDER) | {None}
    assert set(role['minimum_effort']['enum']) == set(EFFORT_ORDER) | {None}
    effort = routing['effort']['properties']
    assert set(effort['default']['enum']) == set(EFFORT_ORDER)
    for field in ('by_role', 'by_provider', 'by_model'):
        assert set(effort[field]['additionalProperties']['enum']) == set(EFFORT_ORDER)


def test_role_minimum_does_not_mask_stricter_risk_floor():
    routing = {'role_bindings': {'security-challenger': {'effort': 'low', 'minimum_effort': 'low'}}}
    candidate = {'requested_effort': 'low', 'supported_efforts': ['low', 'medium', 'high'],
                 'risk_policy_floor': 'high'}
    with patch('iot_ai.settings_v2.current_entitlements', return_value=SimpleNamespace(max_effort='high')):
        result = resolve_dispatch_effort(candidate, node_effort='low', max_effort='high',
                                         role_id='security-challenger', routing=routing)
    assert result['decision'] == 'pass'
    assert result['effective_effort'] == 'high'


def test_dispatch_never_raises_above_current_entitlement_to_meet_candidate_minimum():
    candidate = {'requested_effort': 'low', 'supported_efforts': ['low', 'medium', 'high', 'max'],
                 'minimum_effort': 'high'}
    with patch('iot_ai.settings_v2.current_entitlements', return_value=SimpleNamespace(max_effort='medium')):
        result = resolve_dispatch_effort(candidate, node_effort='low', max_effort='max')
    assert result['decision'] == 'block'
    assert result['effective_effort'] is None


def test_role_and_candidate_minimum_are_both_constraints():
    routing = {'role_bindings': {'security-challenger': {'minimum_effort': 'low'}}}
    candidate = {'requested_effort': 'low', 'supported_efforts': ['low', 'high', 'xhigh'],
                 'minimum_effort': 'xhigh', 'risk_policy_floor': 'high'}
    with patch('iot_ai.settings_v2.current_entitlements', return_value=SimpleNamespace(max_effort='max')):
        result = resolve_dispatch_effort(candidate, node_effort='low', max_effort='max',
                                         role_id='security-challenger', routing=routing)
    assert result['decision'] == 'pass'
    assert result['effective_effort'] == 'xhigh'


@pytest.mark.parametrize('field', ['minimum_effort', 'risk_policy_floor'])
@pytest.mark.parametrize('value', [False, True, '', 0, [], {}, 'unreviewed'])
def test_present_invalid_candidate_floor_is_not_discarded(field, value):
    candidate = {'requested_effort': 'low', 'supported_efforts': ['low', 'medium'], field: value}
    with patch('iot_ai.settings_v2.current_entitlements', return_value=SimpleNamespace(max_effort='medium')):
        result = resolve_dispatch_effort(candidate, node_effort='low', max_effort='medium')
    assert result['decision'] == 'block'
    assert result['effective_effort'] is None


def dispatch_fixture(tmp_path, response, **constraints):
    """Real executor/selector boundary, synthetic delegate only; no provider I/O."""
    from iot_ai.agentic import _default_provider_executor
    graph = SimpleNamespace(risk_class='R2', privacy_class='D0', graph_id='fixture-graph', wall_clock_seconds=60)
    node = SimpleNamespace(role_id='implementation-engineer', effort='medium', stage='implementation')
    candidate = {'candidate_id': 'ollama:fixture', 'provider': 'ollama', 'model': 'fixture-local',
                 'requested_effort': 'medium', 'supported_efforts': list(EFFORT_ORDER),
                 'live_ready': True, 'cloud': False, 'fallback_candidates': [],
                 'receipt': {'authenticated': True, 'model_identity_verified': True,
                             'model_served': 'fixture-local', 'effort_supported': list(EFFORT_ORDER)},
                 **constraints}
    with patch('iot_ai.settings_v2.current_entitlements', return_value=SimpleNamespace(max_effort='medium')):
        with patch('iot_ai.agentic.delegate', return_value=response) as delegate:
            executor = _default_provider_executor(tmp_path, {'implementation-engineer': candidate}, graph,
                                                   max_effort='max')
            result = executor(node, 'Synthetic offline prompt', {})
    return result, delegate


def provider_fixture():
    return {'status': 'pass', 'provider': 'ollama', 'model_served': 'fixture-local',
            'output': '{"summary":"synthetic verified response"}',
            'adapter_request_effort': 'medium', 'effort_effective': 'medium'}


def test_unsatisfied_effort_floor_never_reaches_delegate(tmp_path):
    result, delegate = dispatch_fixture(tmp_path, provider_fixture(), minimum_effort='high')
    delegate.assert_not_called()
    assert result['status'] == 'blocked'


def test_valid_effort_reaches_actual_delegate_and_receipt(tmp_path):
    result, delegate = dispatch_fixture(tmp_path, provider_fixture())
    delegate.assert_called_once()
    assert delegate.call_args.kwargs['effort'] == 'medium'
    assert result['status'] == 'pass'
    assert result['effort_receipt']['consistent'] is True
    assert result['effort_receipt']['entitlement_ceiling'] == 'medium'
    assert result['effort_receipt']['model_served'] == 'fixture-local'


@pytest.mark.parametrize('field,value', [('adapter_request_effort', None),
                                        ('adapter_request_effort', 'low'),
                                        ('effort_effective', None), ('effort_effective', 'low'),
                                        ('effort_effective', []), ('effort_effective', {}),
                                        ('adapter_request_effort', False), ('adapter_request_effort', 0)])
def test_inconsistent_provider_effort_cannot_become_success(tmp_path, field, value):
    response = provider_fixture()
    response[field] = value
    result, delegate = dispatch_fixture(tmp_path, response)
    delegate.assert_called_once()
    assert result['status'] == 'blocked'
    assert result['failure_class'] == 'effort-evidence-mismatch'
    assert result['effort_receipt']['consistent'] is False
    if value is not None and type(value) is not str:
        assert result[field] is None


@pytest.mark.parametrize('provider', ['ollama', 'gemini'])
@pytest.mark.parametrize('supported', [['low', 'medium'], [], None])
def test_uncatalogued_first_class_route_capabilities_are_not_erased(provider, supported):
    from iot_ai.provider_catalog import apply_catalog_to_candidate
    row = {'provider': provider, 'model': 'fixture-exact-model', 'supported_efforts': supported}
    result = apply_catalog_to_candidate(row)
    assert result['supported_efforts'] == supported
    assert result['canonical_target_model'] == 'fixture-exact-model'
    assert result['model_served'] is None
    assert result['capability_source'] == 'runtime-route'


def test_unknown_provider_does_not_gain_runtime_exception():
    from iot_ai.provider_catalog import apply_catalog_to_candidate
    result = apply_catalog_to_candidate({'provider': 'unregistered-fixture',
                                       'model': 'fixture-exact', 'supported_efforts': ['high']})
    assert result['catalog_block'] is True
    assert result['model_served'] is None


def test_compound_policy_matches_independent_set_oracle():
    from itertools import product
    levels = list(EFFORT_ORDER)
    supports = [[], levels, ['low', 'high'], ['none', 'max']]
    floors = [(None, None, None), ('low', 'medium', 'high'),
              ('xhigh', 'low', None), (None, 'max', 'medium')]
    for index, (lic, runtime, support, bounds) in enumerate(product(levels, levels, supports, floors)):
        request = levels[index % len(levels)]
        role_floor, candidate_floor, risk_floor = bounds
        routing = {'role_bindings': {'security-challenger': {'minimum_effort': role_floor}}}
        candidate = {'requested_effort': request, 'supported_efforts': support,
                     'minimum_effort': candidate_floor, 'risk_policy_floor': risk_floor}
        expected = {level for level in support if levels.index(level) <= min(levels.index(lic), levels.index(runtime))
                    and all(bound is None or levels.index(level) >= levels.index(bound) for bound in bounds)}
        with patch('iot_ai.settings_v2.current_entitlements', return_value=SimpleNamespace(max_effort=lic)):
            result = resolve_dispatch_effort(candidate, node_effort=request, max_effort=runtime,
                                            role_id='security-challenger', routing=routing)
        assert (result['decision'] == 'pass') == bool(expected)
        if expected:
            assert result['effective_effort'] in expected
            assert set(result['allowed_efforts']) == expected
        else:
            assert result['effective_effort'] is None
