# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
"""Fail-closed separation between MC-GPT and ProductX product stores."""
from __future__ import annotations
from pathlib import Path
from typing import Any

FORBIDDEN_PRODUCT_DB_MARKERS = (
    "/pmd/data/", "/fcc/data/", "/hid/data/", "/ace/data/",
    "/cws-next/", "/healthlab/data/", "/dgx_dld/",
    "aiiot_pmd", "aiiot_fcc", "aiiot_hid",
)

class ProductBoundaryError(PermissionError):
    """Raised when cross-product direct database access is attempted."""

def assert_not_product_database(path: str | Path, *, context: str = "open") -> None:
    text = str(path).replace("\\", "/").lower()
    for marker in FORBIDDEN_PRODUCT_DB_MARKERS:
        if marker in text:
            raise ProductBoundaryError(
                f"cross-product direct database access forbidden ({context}); "
                "use an authenticated, versioned ProductX API/adapter"
            )

def scan_text_for_direct_product_db(text: str) -> list[dict[str, Any]]:
    lower = text.lower()
    return [
        {"marker": marker, "severity": "P0"}
        for marker in FORBIDDEN_PRODUCT_DB_MARKERS
        if marker in lower
    ]
