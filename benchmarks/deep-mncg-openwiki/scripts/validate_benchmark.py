#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-31
"""Fail-closed validation for the public deep benchmark contract."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u0870-\u089f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")
PRIVATE_IP = re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")
PRIVATE_PATH = re.compile(r"(?:^|[\s`'\"])(?:/home/|/root/|[A-Za-z]:\\Users\\)", re.MULTILINE)
SECRET = re.compile(r"(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-proj-[A-Za-z0-9_-]{16,}|xai-[A-Za-z0-9_-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
REQUIRED = [
    "STATUS.json",
    "RUN_MATRIX.json",
    "TASK_SUITE.json",
    "SCORING_SPEC.json",
    "PREREGISTRATION.json",
    "MODELS.example.json",
    "TREATMENTS.json",
    "CODER_RUNTIME.json",
    "AMENDMENT_2026-08-31.json",
    "schemas/trial-receipt.schema.json",
]
REQUIRED_TREATMENT_FIELDS = ("kind", "runtime_component", "dependency_policy", "production_eligibility", "treatment_bundle")
REQUIRED_ELIGIBILITY = {
    "A_BASELINE": False,
    "B_SIMPLE_YAGNI": False,
    "C_PONYTAIL_PINNED": False,
    "D_MNCG": True,
    "E_OPENWIKI": "conditional",
    "F_MNCG_OPENWIKI": False,
}
REQUIRED_KINDS = {
    "A_BASELINE": "benchmark_control",
    "B_SIMPLE_YAGNI": "benchmark_ablation",
    "C_PONYTAIL_PINNED": "external_comparator",
    "D_MNCG": "native_runtime_gate",
    "E_OPENWIKI": "optional_context_adapter_benchmark",
    "F_MNCG_OPENWIKI": "integration_benchmark_profile",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    root = Path(parser.parse_args().root).resolve()
    errors = []
    data = {}

    for relative in REQUIRED:
        path = root / relative
        if not path.is_file():
            errors.append(f"missing:{relative}")
            continue
        try:
            data[relative] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"json:{relative}:{type(exc).__name__}")

    matrix = data.get("RUN_MATRIX.json", {})
    suite = data.get("TASK_SUITE.json", {})
    status = data.get("STATUS.json", {})
    preregistration = data.get("PREREGISTRATION.json", {})
    scoring = data.get("SCORING_SPEC.json", {})
    treatments = data.get("TREATMENTS.json", {})
    receipt = data.get("schemas/trial-receipt.schema.json", {})
    benchmark_id = status.get("benchmark_id")

    if len(matrix.get("arms", [])) != 6:
        errors.append("arm-count")
    tasks = suite.get("tasks", [])
    if len(tasks) != 30:
        errors.append("task-count")
    ids = [row.get("task_id") for row in tasks]
    names = [row.get("upstream_task_name") for row in tasks]
    if len(ids) != len(set(ids)):
        errors.append("duplicate-task-id")
    if len(names) != len(set(names)):
        errors.append("duplicate-upstream-task")

    for key, value in (matrix.get("source_freeze") or {}).items():
        if not SHA40.fullmatch(str(value)):
            errors.append(f"commit-sha:{key}")
    for payload_name, payload in (
        ("run-matrix", matrix),
        ("preregistration", preregistration),
        ("scoring", scoring),
        ("treatments", treatments),
    ):
        if payload.get("benchmark_id") != benchmark_id:
            errors.append(f"benchmark-id:{payload_name}")
    try:
        if receipt["properties"]["benchmark_id"]["const"] != benchmark_id:
            errors.append("benchmark-id:receipt-schema")
    except Exception:
        errors.append("receipt-schema-shape")

    arm_ids = {row.get("arm_id") for row in matrix.get("arms", [])}
    treatment_ids = set((treatments.get("treatments") or {}).keys())
    if arm_ids != treatment_ids:
        errors.append("treatment-arm-set")
    runtime = data.get("CODER_RUNTIME.json", {})
    if runtime.get("user_facing_coder_runtime") != "iot-ai":
        errors.append("coder-runtime-identity")
    if runtime.get("user_facing_coder_runtime_count") != 1:
        errors.append("coder-runtime-count")
    if runtime.get("benchmark_treatments_are_not_products") is not True:
        errors.append("treatments-must-not-be-products")
    if runtime.get("native_mncg_authoritative") is not True:
        errors.append("native-mncg-not-authoritative")
    if runtime.get("native_mncg_production_eligible") is not True:
        errors.append("native-mncg-not-production-eligible")
    if runtime.get("openwiki_default_off") is not True:
        errors.append("openwiki-not-default-off")
    if runtime.get("benchmark_runner_selects_treatments") is not True:
        errors.append("benchmark-runner-must-select-treatments")
    if "optional_knowledge_context_adapter" not in (runtime.get("pipeline") or []):
        errors.append("coder-runtime-pipeline")
    for arm_id, expected_kind in REQUIRED_KINDS.items():
        row = (treatments.get("treatments") or {}).get(arm_id) or {}
        for field in REQUIRED_TREATMENT_FIELDS:
            if field not in row:
                errors.append(f"treatment-field:{arm_id}:{field}")
        if row.get("kind") != expected_kind:
            errors.append(f"treatment-kind:{arm_id}")
        if row.get("production_eligibility") != REQUIRED_ELIGIBILITY.get(arm_id):
            errors.append(f"treatment-production:{arm_id}")
        if "components" in row:
            errors.append(f"treatment-architecture-component-key:{arm_id}")
    for arm in matrix.get("arms") or []:
        arm_id = arm.get("arm_id")
        if "components" in arm:
            errors.append(f"run-matrix-architecture-component-key:{arm_id}")
        bundle = arm.get("treatment_bundle")
        expected_bundle = ((treatments.get("treatments") or {}).get(arm_id) or {}).get("treatment_bundle")
        if "treatment_bundle" not in arm:
            errors.append(f"run-matrix-treatment-bundle:{arm_id}")
        elif bundle != expected_bundle:
            errors.append(f"run-matrix-treatment-bundle-mismatch:{arm_id}")
    d_mncg = (treatments.get("treatments") or {}).get("D_MNCG") or {}
    if d_mncg.get("runtime_component") is not True or d_mncg.get("authoritative") is not True:
        errors.append("native-mncg-classification")
    if d_mncg.get("production_eligibility") is not True:
        errors.append("native-mncg-eligibility")
    b_yagni = (treatments.get("treatments") or {}).get("B_SIMPLE_YAGNI") or {}
    folded = b_yagni.get("folded_into") or {}
    if folded.get("component") != "native_mncg" or folded.get("function") != "reuse_first_precheck":
        errors.append("yagni-not-folded-into-mncg")
    e_openwiki = (treatments.get("treatments") or {}).get("E_OPENWIKI") or {}
    if e_openwiki.get("runtime_component") is not False or e_openwiki.get("default_enabled") is not False:
        errors.append("openwiki-classification")
    if e_openwiki.get("task_authority") is not False or e_openwiki.get("direct_product_db_access") is not False:
        errors.append("openwiki-authority")
    f_combo = (treatments.get("treatments") or {}).get("F_MNCG_OPENWIKI") or {}
    if f_combo.get("runtime_component") is not False or f_combo.get("composition") != ["D_MNCG", "E_OPENWIKI"]:
        errors.append("combo-classification")
    common_commit = (matrix.get("source_freeze") or {}).get("mcgpt_common_source")
    common_tree = (matrix.get("source_freeze") or {}).get("mcgpt_common_tree")
    if status.get("common_source_commit") != common_commit:
        errors.append("common-source-commit")
    if status.get("common_source_tree") != common_tree:
        errors.append("common-source-tree")
    if treatments.get("common_source_commit") != common_commit:
        errors.append("treatment-source-commit")
    if treatments.get("common_source_tree") != common_tree:
        errors.append("treatment-source-tree")
    if status.get("provider_trials_executed") != 0:
        errors.append("unexpected-provider-trials")

    scanned = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".json", ".py", ".yml", ".yaml", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(root).as_posix()
        scanned += 1
        if ARABIC.search(text):
            errors.append(f"non-english-script:{relative}")
        if PRIVATE_IP.search(text):
            errors.append(f"private-ip:{relative}")
        if PRIVATE_PATH.search(text):
            errors.append(f"private-path:{relative}")
        if SECRET.search(text):
            errors.append(f"secret-pattern:{relative}")

    result = {
        "schema": "iot-ai.deep-benchmark-validation.v2",
        "decision": "pass" if not errors else "block",
        "errors": sorted(set(errors)),
        "benchmark_id": benchmark_id,
        "arms": len(matrix.get("arms", [])),
        "tasks": len(tasks),
        "text_files_scanned": scanned,
        "provider_trials_executed": 0,
        "performance_claim_allowed": False,
        "production_claim": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
