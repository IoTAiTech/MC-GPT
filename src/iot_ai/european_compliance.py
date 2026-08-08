# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""EU regulatory engineering readiness without issuing legal certification."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASELINES: dict[str, Any] = {
    "schema": "iot-ai.eu-regulatory-baseline.v1",
    "assessment_date": "2026-08-06",
    "eu_ai_act": {
        "primary": "Regulation (EU) 2024/1689",
        "article_50_applies_from": "2026-08-02",
        "claim": "technical-controls-not-legal-certification",
    },
    "cra": {
        "primary": "Regulation (EU) 2024/2847",
        "reporting_applies_from": "2026-09-11",
        "main_application": "2027-12-11",
    },
    "nis2": {
        "primary": "Directive (EU) 2022/2555",
        "applicability": "entity-and-national-transposition-specific",
    },
    "gdpr": {
        "primary": "Regulation (EU) 2016/679",
        "applicability": "processing-context-specific",
    },
}

_REQUIRED_DOCS = {
    "eu_ai_act": "EU_AI_ACT_TECHNICAL_CONTROLS.md",
    "cra": "CRA_READINESS.md",
    "gdpr": "GDPR_ENGINEERING_CONTROLS.md",
    "nis2": "NIS2_CUSTOMER_ALIGNMENT.md",
    "incident": "AI_INCIDENT_RESPONSE.md",
}


def cra_reporting_schedule(discovered_at: datetime, *, reportable: bool) -> dict[str, Any]:
    """Calculate CRA operational deadlines after a human/legal reportability decision."""
    if discovered_at.tzinfo is None:
        raise ValueError("discovered_at must be timezone-aware")
    return {
        "schema": "iot-ai.cra-reporting-schedule.v1",
        "reportable": bool(reportable),
        "discovered_at": discovered_at.isoformat(),
        "early_warning_due": (discovered_at + timedelta(hours=24)).isoformat() if reportable else None,
        "notification_due": (discovered_at + timedelta(hours=72)).isoformat() if reportable else None,
        "final_report_due": "determine-from-official-current-rule-and-incident-closure",
        "legal_determination_claimed": False,
        "note": "Timeline helper; reportability and authority routing require qualified review.",
    }


def repository_readiness(root: Path) -> dict[str, Any]:
    compliance = root / "docs" / "compliance"
    controls: dict[str, Any] = {}
    errors: list[str] = []
    for control, filename in _REQUIRED_DOCS.items():
        path = compliance / filename
        present = path.is_file() and path.stat().st_size > 0
        controls[control] = {"status": "documented" if present else "missing", "path": str(path)}
        if not present:
            errors.append(f"missing:{path.relative_to(root)}")
    security = root / "SECURITY.md"
    controls["security_policy"] = {"status": "documented" if security.is_file() else "missing", "path": str(security)}
    if not security.is_file():
        errors.append("missing:SECURITY.md")
    return {
        "schema": "iot-ai.eu-regulatory-readiness.v1",
        "decision": "pass" if not errors else "block",
        "controls": controls,
        "errors": errors,
        "legal_baselines": BASELINES,
        "legal_certification_claimed": False,
        "applicability_determination_claimed": False,
        "release_claim": "technical developer-preview readiness for declared use only",
    }
