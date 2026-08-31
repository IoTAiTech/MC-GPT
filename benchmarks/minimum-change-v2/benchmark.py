#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0
"""Paired, evidence-bound Minimum Necessary Change benchmark framework.

The module prepares deterministic run schedules, validates run receipts, and
analyses paired results. It never invokes a provider by itself and never turns
synthetic data into a public savings claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROTOCOL_SCHEMA = "iot-ai.minimum-change-paired-benchmark-protocol.v1"
CORPUS_SCHEMA = "iot-ai.minimum-change-task-corpus.v1"
RESULT_SCHEMA = "iot-ai.minimum-change-paired-result.v1"
SCHEDULE_SCHEMA = "iot-ai.minimum-change-benchmark-schedule.v1"
ANALYSIS_SCHEMA = "iot-ai.minimum-change-benchmark-analysis.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
TERMINAL_STATES = {
    "technical-complete",
    "needs-work",
    "blocked",
    "timeout",
    "cancelled",
    "budget-exhausted",
}
REQUIRED_HARD_GATES = (
    "acceptance_criteria_complete",
    "post_change_tests_passed",
    "security_privacy_controls_passed",
    "independent_review_passed",
    "source_change_bound_to_post_tree",
    "no_secret_or_private_data_disclosure",
    "no_unapproved_runtime_dependency",
    "rollback_or_no_change_rationale_verified",
)
EFFICIENCY_METRICS = (
    "source_lines_added",
    "new_runtime_dependencies",
    "tokens_total",
    "provider_cost",
    "wall_clock_seconds",
    "repair_iterations",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(canonical_json(dict(row)) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line {line_number} is not an object")
        rows.append(value)
    return rows


def validate_protocol(protocol: Mapping[str, Any], corpus: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        errors.append("protocol-schema")
    if corpus.get("schema") != CORPUS_SCHEMA:
        errors.append("corpus-schema")
    if protocol.get("production_claim") is not False or corpus.get("production_claim") is not False:
        errors.append("production-claim")

    arms = list(protocol.get("arms") or [])
    arm_ids = [str(row.get("id") or "") for row in arms if isinstance(row, Mapping)]
    if len(arm_ids) != len(set(arm_ids)) or not arm_ids:
        errors.append("arm-identities")
    if "baseline" not in arm_ids or "mcgpt-minimum-change" not in arm_ids:
        errors.append("required-arms")
    if any(row.get("enabled") is not False and row.get("enabled") is not True for row in arms):
        errors.append("arm-enabled-type")

    providers = list(protocol.get("providers") or [])
    provider_ids = [str(row.get("id") or "") for row in providers if isinstance(row, Mapping)]
    if len(provider_ids) != len(set(provider_ids)) or not provider_ids:
        errors.append("provider-identities")

    hard_gates = tuple(protocol.get("hard_gates") or ())
    if hard_gates != REQUIRED_HARD_GATES:
        errors.append("hard-gates")
    design = protocol.get("design") or {}
    repetitions = design.get("repetitions_per_enabled_arm")
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 2:
        errors.append("repetitions")
    seed = design.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        errors.append("seed")
    if design.get("fresh_workspace_per_run") is not True:
        errors.append("fresh-workspaces")
    if design.get("cross_arm_context_reuse") is not False:
        errors.append("cross-arm-context")

    tasks = list(corpus.get("tasks") or [])
    task_ids = [str(row.get("id") or "") for row in tasks if isinstance(row, Mapping)]
    if len(task_ids) != len(set(task_ids)) or not task_ids:
        errors.append("task-identities")
    valid_rungs = {
        "necessity",
        "existing-capability",
        "standard-library",
        "native-platform",
        "existing-dependency",
        "minimal-local-change",
        "minimum-new-code",
    }
    for row in tasks:
        if not isinstance(row, Mapping):
            errors.append("task-type")
            continue
        if row.get("expected_rung") not in valid_rungs:
            errors.append(f"task-rung:{row.get('id')}")
        criteria = row.get("acceptance_criteria")
        if not isinstance(criteria, list) or not criteria or any(not str(item).strip() for item in criteria):
            errors.append(f"task-acceptance:{row.get('id')}")
        if row.get("public_data_only") is not True:
            errors.append(f"task-public-data:{row.get('id')}")

    return {
        "schema": "iot-ai.minimum-change-benchmark-validation.v1",
        "decision": "pass" if not errors else "block",
        "errors": sorted(set(errors)),
        "protocol_sha256": digest(protocol),
        "corpus_sha256": digest(corpus),
        "enabled_arms": [row["id"] for row in arms if row.get("enabled") is True],
        "provider_ids": provider_ids,
        "task_count": len(tasks),
        "production_claim": False,
    }


def _balanced_order(items: Sequence[str], offset: int) -> list[str]:
    if not items:
        return []
    shift = offset % len(items)
    rotated = [*items[shift:], *items[:shift]]
    return list(reversed(rotated)) if (offset // len(items)) % 2 else rotated


def build_schedule(
    protocol: Mapping[str, Any],
    corpus: Mapping[str, Any],
    *,
    provider_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    validation = validate_protocol(protocol, corpus)
    if validation["decision"] != "pass":
        raise ValueError(f"invalid protocol: {validation['errors']}")

    enabled_arms = list(validation["enabled_arms"])
    available_providers = list(validation["provider_ids"])
    selected_providers = list(provider_ids or available_providers)
    unknown = sorted(set(selected_providers) - set(available_providers))
    if unknown:
        raise ValueError(f"unknown providers: {unknown}")
    repetitions = int(protocol["design"]["repetitions_per_enabled_arm"])
    seed = int(protocol["design"]["seed"])
    tasks = list(corpus["tasks"])
    protocol_sha = validation["protocol_sha256"]
    corpus_sha = validation["corpus_sha256"]

    runs: list[dict[str, Any]] = []
    sequence = 0
    for provider_index, provider_id in enumerate(selected_providers):
        for repetition in range(1, repetitions + 1):
            task_order = _balanced_order(
                [str(row["id"]) for row in tasks],
                seed + provider_index + repetition - 1,
            )
            task_by_id = {str(row["id"]): row for row in tasks}
            for task_index, task_id in enumerate(task_order):
                arm_order = _balanced_order(
                    enabled_arms,
                    seed + provider_index + repetition + task_index,
                )
                for arm_index, arm_id in enumerate(arm_order):
                    sequence += 1
                    identity = {
                        "protocol_sha256": protocol_sha,
                        "corpus_sha256": corpus_sha,
                        "task_id": task_id,
                        "arm_id": arm_id,
                        "provider_id": provider_id,
                        "repetition": repetition,
                    }
                    runs.append(
                        {
                            "run_id": f"run-{digest(identity)[:24]}",
                            "sequence": sequence,
                            "randomization_index": arm_index,
                            **identity,
                            "expected_rung": task_by_id[task_id]["expected_rung"],
                            "risk_class": task_by_id[task_id]["risk_class"],
                            "production_claim": False,
                        }
                    )

    run_ids = [row["run_id"] for row in runs]
    if len(run_ids) != len(set(run_ids)):
        raise RuntimeError("schedule produced duplicate run IDs")
    return {
        "schema": SCHEDULE_SCHEMA,
        "version": "1.0.0",
        "protocol_sha256": protocol_sha,
        "corpus_sha256": corpus_sha,
        "providers": selected_providers,
        "enabled_arms": enabled_arms,
        "repetitions": repetitions,
        "run_count": len(runs),
        "runs": runs,
        "production_claim": False,
    }


def _finite_number(value: Any, *, minimum: float = 0.0) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value)) and float(value) >= minimum


def validate_result(result: Mapping[str, Any], schedule: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if result.get("schema") != RESULT_SCHEMA:
        errors.append("schema")
    if result.get("production_claim") is not False:
        errors.append("production-claim")
    run_id = str(result.get("run_id") or "")
    scheduled = {row["run_id"]: row for row in schedule.get("runs", [])}.get(run_id)
    if scheduled is None:
        errors.append("unknown-run")
        scheduled = {}
    for key in ("protocol_sha256", "corpus_sha256", "task_id", "arm_id", "provider_id", "repetition"):
        if result.get(key) != scheduled.get(key):
            errors.append(f"schedule-binding:{key}")

    terminal_state = result.get("terminal_state")
    if terminal_state not in TERMINAL_STATES:
        errors.append("terminal-state")
    if result.get("data_classification") not in {"real", "synthetic"}:
        errors.append("data-classification")
    if not str(result.get("source_revision") or "").strip():
        errors.append("source-revision")
    if not str(result.get("fixture_revision") or "").strip():
        errors.append("fixture-revision")
    if not str(result.get("model_requested") or "").strip():
        errors.append("model-requested")
    served = result.get("model_served")
    verified = result.get("model_identity_verified")
    if verified is True and not str(served or "").strip():
        errors.append("verified-model-missing")
    if verified not in {True, False}:
        errors.append("model-identity-status")

    gates = result.get("hard_gates")
    if not isinstance(gates, Mapping):
        errors.append("hard-gates-type")
        gates = {}
    if set(gates) != set(REQUIRED_HARD_GATES):
        errors.append("hard-gates-shape")
    if any(value not in {True, False} for value in gates.values()):
        errors.append("hard-gates-value")

    metrics = result.get("metrics")
    if not isinstance(metrics, Mapping):
        errors.append("metrics-type")
        metrics = {}
    required_metrics = {
        "source_lines_added",
        "source_lines_deleted",
        "files_added",
        "files_modified",
        "files_deleted",
        "new_runtime_dependencies",
        "tokens_input",
        "tokens_output",
        "tokens_reasoning",
        "tokens_total",
        "provider_cost",
        "wall_clock_seconds",
        "repair_iterations",
        "tests_passed",
        "tests_failed",
        "review_findings",
    }
    if set(metrics) != required_metrics:
        errors.append("metrics-shape")
    for key, value in metrics.items():
        if value is None and key in {"tokens_input", "tokens_output", "tokens_reasoning", "tokens_total", "provider_cost"}:
            continue
        if not _finite_number(value):
            errors.append(f"metric:{key}")
    if all(metrics.get(key) is not None for key in ("tokens_input", "tokens_output", "tokens_reasoning", "tokens_total")):
        expected_total = sum(float(metrics[key]) for key in ("tokens_input", "tokens_output", "tokens_reasoning"))
        if float(metrics["tokens_total"]) != expected_total:
            errors.append("token-total")

    evidence = result.get("evidence")
    if not isinstance(evidence, Mapping):
        errors.append("evidence-type")
        evidence = {}
    for key in ("pre_tree_sha256", "post_tree_sha256", "diff_sha256", "test_evidence_sha256", "review_evidence_sha256"):
        value = evidence.get(key)
        if value is not None and not _SHA256.fullmatch(str(value)):
            errors.append(f"evidence:{key}")
    if terminal_state == "technical-complete":
        if not all(gates.get(key) is True for key in REQUIRED_HARD_GATES):
            errors.append("complete-with-failed-gate")
        for key in ("pre_tree_sha256", "post_tree_sha256", "test_evidence_sha256", "review_evidence_sha256"):
            if not evidence.get(key):
                errors.append(f"complete-missing-evidence:{key}")

    return {
        "decision": "pass" if not errors else "block",
        "run_id": run_id or None,
        "errors": sorted(set(errors)),
        "hard_gates_passed": bool(gates) and all(gates.get(key) is True for key in REQUIRED_HARD_GATES),
        "efficiency_metrics_complete": all(metrics.get(key) is not None for key in EFFICIENCY_METRICS),
        "production_claim": False,
    }


def validate_results(results: Sequence[Mapping[str, Any]], schedule: Mapping[str, Any]) -> dict[str, Any]:
    checks = [validate_result(row, schedule) for row in results]
    run_ids = [str(row.get("run_id") or "") for row in results]
    errors: list[str] = []
    if len(run_ids) != len(set(run_ids)):
        errors.append("duplicate-run-results")
    errors.extend(f"{row['run_id']}:{item}" for row in checks for item in row["errors"])
    return {
        "schema": "iot-ai.minimum-change-result-set-validation.v1",
        "decision": "pass" if not errors else "block",
        "result_count": len(results),
        "errors": sorted(set(errors)),
        "checks": checks,
        "production_claim": False,
    }


def _quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _bootstrap_ci(values: Sequence[float], iterations: int, confidence: float, seed: int) -> list[float] | None:
    if not values:
        return None
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(iterations):
        sample = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(statistics.median(sample))
    alpha = (1.0 - confidence) / 2.0
    low = _quantile(estimates, alpha)
    high = _quantile(estimates, 1.0 - alpha)
    return [round(float(low), 6), round(float(high), 6)] if low is not None and high is not None else None


def _sign_test_two_sided(deltas: Sequence[float]) -> float | None:
    positive = sum(value > 0 for value in deltas)
    negative = sum(value < 0 for value in deltas)
    n = positive + negative
    if n == 0:
        return None
    k = min(positive, negative)
    probability = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return round(min(1.0, 2.0 * probability), 12)


def analyse_results(
    protocol: Mapping[str, Any],
    corpus: Mapping[str, Any],
    schedule: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    protocol_check = validate_protocol(protocol, corpus)
    result_check = validate_results(results, schedule)
    if protocol_check["decision"] != "pass" or result_check["decision"] != "pass":
        return {
            "schema": ANALYSIS_SCHEMA,
            "decision": "block",
            "protocol_errors": protocol_check["errors"],
            "result_errors": result_check["errors"],
            "production_claim": False,
        }

    run_by_key: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    arm_totals: Counter[str] = Counter()
    arm_gate_passes: Counter[str] = Counter()
    arm_terminal: dict[str, Counter[str]] = defaultdict(Counter)
    all_real = True
    all_verified_models = True
    for row in results:
        key = (row["task_id"], row["provider_id"], row["model_served"], row["repetition"])
        run_by_key[key][str(row["arm_id"])] = row
        arm = str(row["arm_id"])
        arm_totals[arm] += 1
        gates_pass = all(row["hard_gates"].get(gate) is True for gate in REQUIRED_HARD_GATES)
        arm_gate_passes[arm] += int(gates_pass)
        arm_terminal[arm][str(row["terminal_state"])] += 1
        all_real = all_real and row.get("data_classification") == "real"
        all_verified_models = all_verified_models and row.get("model_identity_verified") is True

    enabled_arms = list(protocol_check["enabled_arms"])
    baseline_id = "baseline"
    comparisons: dict[str, Any] = {}
    minimum_pairs = int(protocol["analysis"]["minimum_complete_pairs_per_comparison"])
    iterations = int(protocol["analysis"]["bootstrap_iterations"])
    confidence = float(protocol["analysis"]["bootstrap_confidence"])
    seed = int(protocol["design"]["seed"])

    for arm_id in enabled_arms:
        if arm_id == baseline_id:
            continue
        paired = [(arms[baseline_id], arms[arm_id]) for arms in run_by_key.values() if baseline_id in arms and arm_id in arms]
        hard_gate_inferior = any(
            all(base["hard_gates"].get(gate) is True for gate in REQUIRED_HARD_GATES)
            and not all(candidate["hard_gates"].get(gate) is True for gate in REQUIRED_HARD_GATES)
            for base, candidate in paired
        )
        metrics: dict[str, Any] = {}
        missing_metric = False
        for metric in EFFICIENCY_METRICS:
            deltas: list[float] = []
            for base, candidate in paired:
                base_value = base["metrics"].get(metric)
                candidate_value = candidate["metrics"].get(metric)
                if base_value is None or candidate_value is None or float(base_value) <= 0:
                    missing_metric = True
                    continue
                deltas.append((float(candidate_value) - float(base_value)) / float(base_value) * 100.0)
            metrics[metric] = {
                "pair_count": len(deltas),
                "median_delta_percent": round(float(statistics.median(deltas)), 6) if deltas else None,
                "iqr_delta_percent": [round(float(_quantile(deltas, 0.25)), 6), round(float(_quantile(deltas, 0.75)), 6)] if deltas else None,
                "bootstrap_median_ci": _bootstrap_ci(deltas, iterations, confidence, seed + len(metric) + len(arm_id)),
                "sign_test_p_value": _sign_test_two_sided(deltas),
            }
        complete_pair_count = len(paired)
        claim_allowed = (
            all_real
            and all_verified_models
            and complete_pair_count >= minimum_pairs
            and not hard_gate_inferior
            and not missing_metric
            and all(
                row["terminal_state"] == "technical-complete"
                and all(row["hard_gates"].get(gate) is True for gate in REQUIRED_HARD_GATES)
                for pair in paired for row in pair
            )
        )
        comparisons[arm_id] = {
            "baseline_arm": baseline_id,
            "paired_run_count": complete_pair_count,
            "minimum_pairs_required": minimum_pairs,
            "hard_gate_inferior": hard_gate_inferior,
            "all_data_real": all_real,
            "all_model_identities_verified": all_verified_models,
            "missing_efficiency_metric": missing_metric,
            "savings_claim_allowed": claim_allowed,
            "metrics": metrics,
        }

    arm_summary = {
        arm: {
            "run_count": arm_totals[arm],
            "hard_gate_pass_count": arm_gate_passes[arm],
            "hard_gate_pass_rate": round(arm_gate_passes[arm] / arm_totals[arm], 6) if arm_totals[arm] else None,
            "terminal_states": dict(sorted(arm_terminal[arm].items())),
        }
        for arm in enabled_arms
    }
    any_claim = any(row["savings_claim_allowed"] for row in comparisons.values())
    return {
        "schema": ANALYSIS_SCHEMA,
        "decision": "pass",
        "result_count": len(results),
        "arm_summary": arm_summary,
        "comparisons": comparisons,
        "any_savings_claim_allowed": any_claim,
        "public_claim_status": "measured" if any_claim else "not-measured",
        "production_claim": False,
    }


def synthetic_results(schedule: Mapping[str, Any]) -> list[dict[str, Any]]:
    arm_multiplier = {"baseline": 1.0, "simple-yagni": 0.85, "mcgpt-minimum-change": 0.62, "ponytail-experimental": 0.60}
    rows: list[dict[str, Any]] = []
    for scheduled in schedule["runs"]:
        multiplier = arm_multiplier[scheduled["arm_id"]]
        task_seed = int(digest({"task_id": scheduled["task_id"]})[:8], 16)
        base = 40 + (task_seed % 9) * 10
        metrics = {
            "source_lines_added": round(base * multiplier, 6),
            "source_lines_deleted": 4,
            "files_added": 0,
            "files_modified": 2,
            "files_deleted": 0,
            "new_runtime_dependencies": 0,
            "tokens_input": round(800 * multiplier, 6),
            "tokens_output": round(500 * multiplier, 6),
            "tokens_reasoning": round(300 * multiplier, 6),
            "tokens_total": round(1600 * multiplier, 6),
            "provider_cost": round(0.40 * multiplier, 8),
            "wall_clock_seconds": round(90 * multiplier, 6),
            "repair_iterations": 1 if scheduled["arm_id"] == "baseline" else 0,
            "tests_passed": 8,
            "tests_failed": 0,
            "review_findings": 0,
        }
        fake_sha = digest({"run_id": scheduled["run_id"]})
        rows.append(
            {
                "schema": RESULT_SCHEMA,
                **{key: scheduled[key] for key in ("run_id", "protocol_sha256", "corpus_sha256", "task_id", "arm_id", "provider_id", "repetition")},
                "data_classification": "synthetic",
                "source_revision": "synthetic-source",
                "fixture_revision": "synthetic-fixture",
                "model_requested": "synthetic-model",
                "model_served": "synthetic-model",
                "model_identity_verified": True,
                "terminal_state": "technical-complete",
                "hard_gates": {key: True for key in REQUIRED_HARD_GATES},
                "metrics": metrics,
                "evidence": {
                    "pre_tree_sha256": fake_sha,
                    "post_tree_sha256": digest({"run_id": scheduled["run_id"], "post": True}),
                    "diff_sha256": digest({"run_id": scheduled["run_id"], "diff": True}),
                    "test_evidence_sha256": digest({"run_id": scheduled["run_id"], "test": True}),
                    "review_evidence_sha256": digest({"run_id": scheduled["run_id"], "review": True}),
                },
                "production_claim": False,
            }
        )
    return rows


def paths_from_args(args: argparse.Namespace) -> tuple[Path, Path]:
    root = Path(__file__).resolve().parent
    return Path(args.protocol or root / "protocol.json"), Path(args.corpus or root / "task-corpus.json")


def cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol")
    parser.add_argument("--corpus")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    schedule_parser = sub.add_parser("schedule")
    schedule_parser.add_argument("--providers", nargs="*")
    schedule_parser.add_argument("--output", required=True)
    results_parser = sub.add_parser("validate-results")
    results_parser.add_argument("--schedule", required=True)
    results_parser.add_argument("--results", required=True)
    analyse_parser = sub.add_parser("analyse")
    analyse_parser.add_argument("--schedule", required=True)
    analyse_parser.add_argument("--results", required=True)
    analyse_parser.add_argument("--output", required=True)
    selftest_parser = sub.add_parser("selftest")
    selftest_parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    protocol_path, corpus_path = paths_from_args(args)
    protocol = load_json(protocol_path)
    corpus = load_json(corpus_path)

    if args.command == "validate":
        payload = validate_protocol(protocol, corpus)
    elif args.command == "schedule":
        payload = build_schedule(protocol, corpus, provider_ids=args.providers)
        write_json(Path(args.output), payload)
    elif args.command == "validate-results":
        schedule = load_json(Path(args.schedule))
        payload = validate_results(read_jsonl(Path(args.results)), schedule)
    elif args.command == "analyse":
        schedule = load_json(Path(args.schedule))
        payload = analyse_results(protocol, corpus, schedule, read_jsonl(Path(args.results)))
        write_json(Path(args.output), payload)
    else:
        out = Path(args.output_dir)
        schedule = build_schedule(protocol, corpus, provider_ids=[protocol["providers"][0]["id"]])
        results = synthetic_results(schedule)
        analysis = analyse_results(protocol, corpus, schedule, results)
        write_json(out / "schedule.json", schedule)
        write_jsonl(out / "synthetic-results.jsonl", results)
        write_json(out / "analysis.json", analysis)
        payload = {
            "schema": "iot-ai.minimum-change-benchmark-selftest.v1",
            "decision": "pass" if analysis["decision"] == "pass" and not analysis["any_savings_claim_allowed"] else "block",
            "schedule_runs": schedule["run_count"],
            "result_count": len(results),
            "synthetic_data_cannot_authorize_claim": not analysis["any_savings_claim_allowed"],
            "output_dir": str(out),
            "production_claim": False,
        }
        write_json(out / "selftest.json", payload)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("decision") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(cli())
