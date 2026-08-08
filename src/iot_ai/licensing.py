# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Entitlements:
    edition:str
    commercial_use:bool
    pmd_adapter:bool
    fleet:bool
    max_providers:int
    max_effort:str
    license_id:str|None=None
    expires_at:str|None=None
    retention_days:int=30

COMMUNITY=Entitlements("community",False,False,False,16,"medium",retention_days=30)

def current()->Entitlements:
    """Remain Community unless an explicitly configured private add-on verifies a signed entitlement."""
    if not os.environ.get("IOT_AI_ENTITLEMENT_FILE"):return COMMUNITY
    try:from iot_ai_enterprise.runtime import current_entitlements
    except ImportError as exc:raise PermissionError("commercial entitlement configured but the private Enterprise add-on is not installed") from exc
    value=current_entitlements();required=("edition","commercial_use","pmd_adapter","fleet","max_providers","max_effort")
    if any(name not in value for name in required):raise PermissionError("enterprise entitlement bridge returned an incomplete feature set")
    return Entitlements(edition=str(value["edition"]),commercial_use=bool(value["commercial_use"]),pmd_adapter=bool(value["pmd_adapter"]),fleet=bool(value["fleet"]),max_providers=int(value["max_providers"]),max_effort=str(value["max_effort"]),license_id=str(value.get("license_id")) if value.get("license_id") else None,expires_at=str(value.get("expires_at")) if value.get("expires_at") else None,retention_days=int(value.get("retention_days",365)))

def require(feature:str)->None:
    ent=current();allowed={"pmd_adapter":ent.pmd_adapter,"fleet":ent.fleet,"commercial_use":ent.commercial_use}.get(feature,True)
    if not allowed:raise PermissionError(f"feature requires an IoT-AI.Tech Commercial License: {feature}")
