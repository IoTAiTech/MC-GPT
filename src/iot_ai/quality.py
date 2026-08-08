# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08

from __future__ import annotations
import re
from typing import Any

RUBRIC_VERSION = "iot-ai.response-quality-heuristic.v1"
_WORD = re.compile(r"[A-Za-z0-9_\-]{3,}")

def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD.finditer(text)}

def score_response(prompt: str, output: str, peers: list[str] | None = None) -> dict[str, Any]:
    """Return a transparent response-quality heuristic, not a correctness claim."""
    peers = peers or []
    p = _tokens(prompt); o = _tokens(output)
    relevance = 0.0 if not p else min(100.0, 100.0 * len(p & o) / max(1, min(len(p), 20)))
    length = len(output.strip())
    completeness = min(100.0, 20.0 + length / 6.0) if length else 0.0
    action_markers = sum(token in output.lower() for token in ("step", "test", "risk", "because", "verify", "implement", "blocker"))
    actionability = min(100.0, 15.0 + action_markers * 12.0 + (20.0 if "```" in output else 0.0)) if output.strip() else 0.0
    evidence_markers = sum(marker in output for marker in ("/", "SHA-256", "http", "test", "evidence", "file", "line"))
    grounding_signals = min(100.0, evidence_markers * 14.0)
    if peers and o:
        similarities=[]
        for peer in peers:
            t=_tokens(peer)
            similarities.append(len(o&t)/max(1,len(o|t)))
        unique_value=max(0.0,100.0*(1.0-max(similarities,default=0.0)))
    else:
        unique_value=50.0 if o else 0.0
    score=round(0.25*relevance+0.20*completeness+0.20*actionability+0.15*grounding_signals+0.20*unique_value,2)
    return {
        "score": score,
        "rubric_version": RUBRIC_VERSION,
        "basis": "automatic-heuristic-not-correctness",
        "components": {
            "relevance": round(relevance,2),
            "completeness": round(completeness,2),
            "actionability": round(actionability,2),
            "grounding_signals": round(grounding_signals,2),
            "unique_value": round(unique_value,2),
        },
    }
