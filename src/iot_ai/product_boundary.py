# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3+boundary.1 | Date: 2026-08-06
"""Fail-closed product-boundary rules for IOT-AI / MC-GPT.

PMD (and other ProductX dashboards) must be reached only through authenticated
versioned APIs / adapters. Direct open of another product's SQLite/Postgres
data directory from this suite is forbidden.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Product trees that must never be opened as local DBs from this suite.
FORBIDDEN_PRODUCT_DB_MARKERS = (
    "/pmd/data/",
    "/fcc/data/",
    "/hid/data/",
    "/ACE/data/",
    "/cws-next/",
    "/healthlab/data/",
    "/dgx_dld/",
    "aiiot_pmd",
    "aiiot_fcc",
    "aiiot_hid",
)


class ProductBoundaryError(PermissionError):
    """Raised when a cross-product direct data path is requested."""


def assert_not_product_database(path: str | Path, *, context: str = "open") -> None:
    """Refuse to open another product's database path."""
    text = str(path).replace("\\", "/").lower()
    for marker in FORBIDDEN_PRODUCT_DB_MARKERS:
        if marker.lower() in text:
            raise ProductBoundaryError(
                f"cross-product direct database access forbidden ({context}): "
                f"path matches {marker!r}; use authenticated PMD/ProductX API only"
            )


def scan_text_for_direct_product_db(text: str) -> list[dict[str, Any]]:
    """Return matches for documentation/code scans (no exception)."""
    hits: list[dict[str, Any]] = []
    lower = text.lower()
    for marker in FORBIDDEN_PRODUCT_DB_MARKERS:
        if marker.lower() in lower:
            hits.append({"marker": marker, "severity": "P0"})
    return hits
