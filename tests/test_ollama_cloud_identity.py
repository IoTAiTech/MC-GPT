# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
"""Cloud selector != model substitution; identities and reported usage stay raw."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from iot_ai.mesh import _extract_usage, delegate
from iot_ai.provider_catalog import model_binding_kind
from iot_ai.readiness import live_receipt, provider_candidates
from iot_ai.tool_router import validate_provider_binding


@pytest.mark.parametrize("requested,served",[("kimi-k2.7-code:cloud","kimi-k2.7-code"),
    ("glm-5.2:cloud","glm-5.2"),("mistral-large-3:675b-cloud","mistral-large-3:675b")])
def test_known_cloud_transport_qualifier(requested,served):
    assert model_binding_kind("ollama",requested,served)=="ollama-cloud-selector"
    assert validate_provider_binding(selected_provider="ollama",selected_model=requested,
        result={"provider":"ollama","model_served":served})["decision"]=="pass"


@pytest.mark.parametrize("provider,requested,served",[("codex","model:cloud","model"),
    ("ollama","model:cloud","other"),("ollama","model:20b-cloud","model:120b"),
    ("ollama","model:0731-cloud","model"),("ollama","auto-custom","other"),
    ("ollama","org/model:cloud","model"),("ollama","model:cloud",None)])
def test_actual_drift_is_not_normalized(provider,requested,served):
    assert model_binding_kind(provider,requested,served) is None


def test_cloud_receipt_is_found_by_original_request(tmp_path):
    row={"provider":"ollama","route_id":"r","model_requested":"glm-5.2:cloud","model_served":"glm-5.2",
         "expires_at":(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()}
    with patch("iot_ai.readiness.load_receipts",return_value={"receipts":[row]}):
        assert live_receipt(tmp_path,"r","glm-5.2:cloud")==row
        assert live_receipt(tmp_path,"r","other:cloud") is None


@pytest.mark.parametrize("selector",["auto","auto:cloud"])
def test_auto_discovery_preserves_one_cloud_dispatch_selector(tmp_path,selector):
    route={"provider":"ollama","route_id":"r","model":selector,"models":[selector],"enabled":True,"cloud":True}
    receipt={"provider":"ollama","route_id":"r","model_requested":"glm-5.2:cloud","model_served":"glm-5.2",
             "status":"pass","authenticated":True,"expires_at":(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()}
    with patch("iot_ai.readiness.load_routes",return_value={"routes":[route]}), patch("iot_ai.readiness.static_status",return_value={"installed":True}):
        with patch("iot_ai.readiness.load_receipts",return_value={"receipts":[receipt]}):
            candidates=provider_candidates(tmp_path)
    assert [r["model"] for r in candidates]==["glm-5.2:cloud"]


def test_requested_field_alone_cannot_make_wrong_model_ready(tmp_path):
    receipt={"provider":"ollama","route_id":"r","model_requested":"glm-5.2:cloud","model_served":"other",
             "expires_at":(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()}
    with patch("iot_ai.readiness.load_receipts",return_value={"receipts":[receipt]}):
        assert live_receipt(tmp_path,"r","glm-5.2:cloud") is None


@pytest.mark.parametrize("value",[True,-1,"10",None])
def test_malformed_ollama_usage_remains_unknown(value):
    row=_extract_usage({"prompt_eval_count":value,"eval_count":value})
    assert row["input_tokens"] is None and row["output_tokens"] is None


def test_ollama_usage_retains_zero_and_reported_counts():
    row=_extract_usage({"model":"m","prompt_eval_count":0,"eval_count":19})
    assert row["input_tokens"]==0 and row["output_tokens"]==19
    assert row["reasoning_tokens"] is None


def test_real_dispatch_boundary_preserves_raw_model_names(tmp_path):
    route={"provider":"ollama","route_id":"r","kind":"api","model":"glm-5.2:cloud","cloud":True,"auth_mode":"api"}
    response={"payload":{"model":"glm-5.2","message":{"content":"A substantive answer for the bounded example."},"prompt_eval_count":21,"eval_count":8},
              "effort":{"effort_applied":True,"effort_effective":"low"}}
    with patch("iot_ai.mesh.eligible_routes",return_value=[route]), patch("iot_ai.mesh._api_request",return_value=response):
        result=delegate(tmp_path,"ollama","Review the public example",model="glm-5.2:cloud",effort="low")
    assert result["status"]=="pass"
    assert result["model_requested"]=="glm-5.2:cloud" and result["model_served"]=="glm-5.2"
    assert result["model_binding_kind"]=="ollama-cloud-selector"
    assert result["input_tokens"]==21 and result["output_tokens"]==8
