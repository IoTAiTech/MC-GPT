# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Verify the public repository contract before publication."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED = {
    "README.md", "USAGE.md", "CONTACT.md", "LICENSE", "SECURITY.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
    "SUPPORT.md", "GOVERNANCE.md", "TRADEMARKS.md", "NOTICE", "THIRD_PARTY_NOTICES.md",
    "CITATION.cff", "SBOM.cdx.json", "CHANGELOG.md", "PUBLIC_REPOSITORY_NOTICE.md",
    "pyproject.toml", ".github/CODEOWNERS", ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml", ".github/FUNDING.yml",
    ".github/workflows/ci.yml", ".github/workflows/security.yml",
    ".github/workflows/public-boundary.yml", ".github/workflows/release.yml",
    ".github/workflows/dependency-review.yml",
    ".gitattributes", ".editorconfig",
    "docs/compliance/LEGAL_BASELINE.json", "docs/compliance/AI_ACT_SYSTEM_CARD.json",
    "docs/compliance/EU_AI_ACT_COMPLIANCE_MATRIX.json", "docs/compliance/UPSTREAM_MODEL_REGISTER.json",
    "docs/compliance/CLAIM_EVIDENCE_REGISTER.json", "docs/compliance/AI_ACT_SYSTEM_CARD.md",
    "docs/compliance/INTENDED_PURPOSE_AND_LIMITATIONS.md", "docs/compliance/AI_ACT_CLASSIFICATION.md",
    "docs/compliance/PROHIBITED_USES.md", "docs/compliance/AI_INTERACTION_TRANSPARENCY.md",
    "docs/compliance/AI_GENERATED_CONTENT_MARKING.md", "docs/compliance/AI_LITERACY_PROGRAM.md",
    "docs/compliance/HUMAN_OVERSIGHT.md", "docs/compliance/POST_MARKET_MONITORING.md",
    "docs/compliance/AI_INCIDENT_RESPONSE.md", "docs/compliance/PUBLIC_PRIVATE_DATA_BOUNDARY.md",
    "docs/compliance/EVIDENCE_INDEX.json", "docs/compliance/RELEASE_GATE_DECISION.md",
    "schemas/ai-system-card-v1.schema.json", "schemas/ai-content-provenance-v1.schema.json",
    "schemas/eu-ai-act-conformance-v1.schema.json", "tools/eu_ai_act_release_gate.py",
    "tools/mark_ai_content.py",
    "tools/brand_identity_check.py", "LEGACY_IDENTITY_ALLOWLIST.json",
    "docs/brand-identity-migration.md", "docs/worktree-orchestration.md",
    "docs/comparison/ORCA_COMPARISON.md", "docs/comparison/ORCA_COMPARISON.json",
    "docs/github-analysis.md",
    "schemas/worktree-run-v1.schema.json", "docs/meeting-integration.md", "docs/bootstrap-installation.md",
    "installers/bootstrap.sh", "npm/package.json", "npm/bin/iot-ai-bootstrap.mjs",
    "scripts/PREPARE_SANITIZED_HISTORY.sh", "scripts/REPLACE_PUBLIC_HISTORY.sh",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--check-sbom", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    source_root = root / "src"
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    errors: list[str] = []
    for rel in sorted(REQUIRED):
        if not (root / rel).is_file():
            errors.append(f"missing:{rel}")
    tracked_compiled: list[str] = []
    git_dir = root / ".git"
    if git_dir.exists():
        import subprocess
        completed = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=False)
        if completed.returncode == 0:
            tracked_compiled = [line for line in completed.stdout.splitlines() if line.endswith((".pyc", ".pyo")) or "__pycache__/" in line]
    if tracked_compiled:
        errors.append("compiled-python-artifacts-tracked")
    suite_source = (root / "src/iot_ai/suite_version.py").read_text(encoding="utf-8")
    match = re.search(r'SUITE_VERSION\s*=\s*"([^"]+)"', suite_source)
    version = match.group(1) if match else None
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    expected_python = version.replace("-beta.", "b") if version else None
    if expected_python and f'version = "{expected_python}"' not in pyproject:
        errors.append("pyproject-version-mismatch")
    for entry in ("suite_main", "help_main", "status_main", "settings_main", "update_main"):
        if entry not in pyproject:
            errors.append(f"missing-entrypoint:{entry}")
    if args.check_sbom:
        try:
            sbom = json.loads((root / "SBOM.cdx.json").read_text(encoding="utf-8"))
            if sbom.get("bomFormat") != "CycloneDX":
                errors.append("invalid-sbom-format")
            if not sbom.get("components"):
                errors.append("empty-sbom-components")
        except (OSError, json.JSONDecodeError):
            errors.append("invalid-sbom")
    try:
        from iot_ai.eu_ai_act import release_gate
        compliance = release_gate(root, profile="developer-preview")
        if compliance.get("decision") != "pass":
            errors.extend(f"eu-ai-act:{item}" for item in compliance.get("errors", []))
    except Exception as exc:
        errors.append(f"eu-ai-act-gate-error:{type(exc).__name__}")

    payload = {
        "schema": "iot-ai.repository-verification.v1",
        "decision": "pass" if not errors else "block",
        "version": version,
        "errors": errors,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
