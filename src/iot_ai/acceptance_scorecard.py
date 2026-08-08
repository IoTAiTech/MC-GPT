# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Fail-closed acceptance-scorecard validation.

A task may move to technical review only when every declared acceptance
criterion is proven exactly once and a trusted verification receipt is bound to
the current revision and criteria digest.  Progress numbers and narrative
claims are never treated as completion authority.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Iterable


def criteria_digest(criteria: Any) -> str:
    """Return a deterministic digest for acceptance-criteria content."""
    if isinstance(criteria, str):
        normalized: Any = [line.strip() for line in criteria.splitlines() if line.strip()]
    else:
        normalized = criteria
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ids(values: Iterable[Any] | None, name: str, errors: list[str]) -> set[int]:
    result: set[int] = set()
    for raw in values or []:
        if isinstance(raw, bool):
            errors.append(f"{name}:boolean-is-not-a-criterion-id")
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            errors.append(f"{name}:invalid-id:{raw!r}")
            continue
        if value in result:
            errors.append(f"{name}:duplicate-id:{value}")
        result.add(value)
    return result


def validate_scorecard(
    scorecard: dict[str, Any],
    *,
    current_revision: int,
    expected_criteria_digest: str | None = None,
    require_all_assessed: bool = True,
) -> dict[str, Any]:
    """Validate a PMD/Suite acceptance scorecard without mutating source state."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        total = int(scorecard.get("criteria_total"))
    except (TypeError, ValueError):
        total = 0
        errors.append("criteria_total:invalid")
    if total < 1:
        errors.append("criteria_total:must-be-positive")

    passed = _ids(scorecard.get("pass") or scorecard.get("passed"), "pass", errors)
    partial = _ids(scorecard.get("partial"), "partial", errors)
    failed = _ids(scorecard.get("fail") or scorecard.get("failed"), "fail", errors)

    overlap = (passed & partial) | (passed & failed) | (partial & failed)
    if overlap:
        errors.append("criterion-status-overlap:" + ",".join(str(value) for value in sorted(overlap)))

    allowed = set(range(1, total + 1)) if total > 0 else set()
    out_of_range = (passed | partial | failed) - allowed
    if out_of_range:
        errors.append("criterion-out-of-range:" + ",".join(str(value) for value in sorted(out_of_range)))
    assessed = (passed | partial | failed) & allowed
    unassessed = allowed - assessed
    if require_all_assessed and unassessed:
        errors.append("criterion-unassessed:" + ",".join(str(value) for value in sorted(unassessed)))

    declared_passed = scorecard.get("criteria_passed_honest", scorecard.get("criteria_passed"))
    if declared_passed is not None:
        try:
            if int(declared_passed) != len(passed):
                errors.append(f"criteria_passed-mismatch:{declared_passed}!={len(passed)}")
        except (TypeError, ValueError):
            errors.append("criteria_passed:invalid")

    verification = scorecard.get("verification") if isinstance(scorecard.get("verification"), dict) else {}
    trusted = bool(verification.get("trusted") or verification.get("trusted_verifier"))
    verified_pass = str(verification.get("decision") or verification.get("status") or "").casefold() in {
        "pass", "passed", "approve", "approved", "verified"
    }
    try:
        verified_revision = int(verification.get("revision"))
    except (TypeError, ValueError):
        verified_revision = -1
    if not trusted:
        errors.append("verification:not-trusted")
    if not verified_pass:
        errors.append("verification:not-passed")
    if verified_revision != int(current_revision):
        errors.append(f"verification:stale-revision:{verified_revision}!={current_revision}")

    receipt_digest = str(verification.get("criteria_digest") or "")
    expected_digest = expected_criteria_digest or str(scorecard.get("criteria_digest") or "")
    if expected_digest:
        if not receipt_digest:
            errors.append("verification:criteria-digest-missing")
        elif not hmac.compare_digest(receipt_digest, expected_digest):
            errors.append("verification:criteria-digest-mismatch")
    elif receipt_digest:
        warnings.append("criteria-digest-present-without-local-baseline")

    current_result = str(scorecard.get("current_result") or scorecard.get("result") or "").strip()
    if not current_result:
        errors.append("current_result:missing")

    can_submit = bool(
        total > 0
        and passed == allowed
        and not partial
        and not failed
        and not unassessed
        and trusted
        and verified_pass
        and verified_revision == int(current_revision)
        and current_result
        and not errors
    )
    return {
        "schema": "iot-ai.acceptance-scorecard-validation.v1",
        "decision": "pass" if can_submit else "block",
        "can_submit": can_submit,
        "criteria_total": total,
        "criteria_passed_calculated": len(passed),
        "passed": sorted(passed),
        "partial": sorted(partial),
        "failed": sorted(failed),
        "unassessed": sorted(unassessed),
        "current_revision": int(current_revision),
        "verification_revision": verified_revision,
        "trusted_verification": trusted and verified_pass,
        "errors": errors,
        "warnings": warnings,
    }
