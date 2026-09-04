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
