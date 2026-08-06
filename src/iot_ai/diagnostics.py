# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
"""Sanitized, integrity-bound diagnostics for commands, graphs and providers."""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .paths import data_root
from .privacy import sanitize
from .util import atomic_json, atomic_text, utc_now

_SENSITIVE_KEYS = re.compile(
    r"(secret|token|password|api[_-]?key|authorization|cookie|credential|private[_-]?key|lease[_-]?token)",
    re.I,
)
_SENSITIVE_BYTES = (
    b"-----BEGIN " + b"PRIVATE KEY-----",
    b"-----BEGIN OPENSSH " + b"PRIVATE KEY-----",
)
_SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"\bxai-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}"),
)


def run_root(user_home: Path, correlation_id: str) -> Path:
    return data_root(user_home) / "runs" / correlation_id


def _merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + int(value)


def _sanitize_value_with_counts(value: Any, key: str = "") -> tuple[Any, dict[str, int]]:
    counts: dict[str, int] = {}
    if _SENSITIVE_KEYS.search(key):
        return "[REDACTED]", {"sensitive_key": 1}
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for child_key, child_value in value.items():
            clean, child_counts = _sanitize_value_with_counts(child_value, str(child_key))
            output[str(child_key)] = clean
            _merge_counts(counts, child_counts)
        return output, counts
    if isinstance(value, (list, tuple)):
        output_list = []
        for child in value:
            clean, child_counts = _sanitize_value_with_counts(child, key)
            output_list.append(clean)
            _merge_counts(counts, child_counts)
        return output_list, counts
    if isinstance(value, str):
        result = sanitize(value, "strict")
        for finding in result.findings:
            category = str(finding.get("kind") if isinstance(finding, dict) else finding)
            counts[category] = counts.get(category, 0) + 1
        return result.text, counts
    return value, counts


def _sanitize_value(value: Any, key: str = "") -> Any:
    return _sanitize_value_with_counts(value, key)[0]


def _sanitize_argv(argv: list[str]) -> tuple[list[str], dict[str, int]]:
    output: list[str] = []
    counts: dict[str, int] = {}
    redact_next = False
    for value in argv:
        if redact_next:
            output.append("[REDACTED]")
            counts["sensitive_argv_value"] = counts.get("sensitive_argv_value", 0) + 1
            redact_next = False
            continue
        if _SENSITIVE_KEYS.search(value):
            if "=" in value:
                name, _ = value.split("=", 1)
                output.append(f"{name}=[REDACTED]")
            else:
                output.append(value)
                redact_next = value.startswith("-")
            counts["sensitive_argv_key"] = counts.get("sensitive_argv_key", 0) + 1
            continue
        clean = sanitize(value, "strict")
        output.append(clean.text)
        for finding in clean.findings:
            category = str(finding.get("kind") if isinstance(finding, dict) else finding)
            counts[category] = counts.get(category, 0) + 1
    return output, counts


def record_event(user_home: Path, correlation_id: str, event: dict[str, Any]) -> Path:
    root = run_root(user_home, correlation_id)
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    timeline = root / "03_TIMELINE.jsonl"
    clean, redaction_summary = _sanitize_value_with_counts({**event, "recorded_at": utc_now()})
    if redaction_summary:
        clean["redaction_summary"] = redaction_summary
    with timeline.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(clean, ensure_ascii=False, sort_keys=True) + "\n")
    try:
        timeline.chmod(0o600)
    except OSError:
        pass
    return timeline


def persist_graph_contract(user_home: Path, correlation_id: str, graph: dict[str, Any]) -> Path:
    root = run_root(user_home, correlation_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "02_CORRELATION_GRAPH.json"
    atomic_json(path, _sanitize_value(graph))
    return path


def persist_command(
    user_home: Path,
    correlation_id: str,
    *,
    command_id: str,
    argv: list[str],
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = None,
) -> Path:
    root = run_root(user_home, correlation_id) / "04_COMMAND" / command_id
    root.mkdir(parents=True, exist_ok=True)
    safe_argv, argv_counts = _sanitize_argv(argv)
    clean_stdout = sanitize(stdout, "strict")
    clean_stderr = sanitize(stderr, "strict")
    redaction_summary = dict(argv_counts)
    for result in (clean_stdout, clean_stderr):
        for finding in result.findings:
            category = str(finding.get("kind") if isinstance(finding, dict) else finding)
            redaction_summary[category] = redaction_summary.get(category, 0) + 1
    payload = {
        "schema": "iot-ai.command-diagnostic.v1",
        "command_id": command_id,
        "argv": safe_argv,
        "argv_sha256": hashlib.sha256(json.dumps(argv, ensure_ascii=False).encode()).hexdigest(),
        "stdout": clean_stdout.text,
        "stderr": clean_stderr.text,
        "exit_code": exit_code,
        "redaction_summary": redaction_summary,
        "recorded_at": utc_now(),
    }
    atomic_json(root / "command.json", payload)
    return root / "command.json"


def persist_node_result(
    user_home: Path,
    correlation_id: str,
    node_id: str,
    value: dict[str, Any],
) -> Path:
    """Persist a complete sanitized node result and source hashes.

    Secret values are never needed for RCA and are not written. Original text
    hashes are retained so a protected operator can correlate external logs.
    """
    root = run_root(user_home, correlation_id) / "05_NODES" / node_id
    root.mkdir(parents=True, exist_ok=True)
    clean, redaction_summary = _sanitize_value_with_counts(value)
    source_hashes = {}
    for field in ("output", "stdout", "stderr", "request", "response"):
        if field in value:
            raw = value[field]
            source_hashes[field] = hashlib.sha256(
                json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str).encode()
            ).hexdigest()
    payload = {
        "schema": "iot-ai.node-diagnostic.v1",
        "node_id": node_id,
        "recorded_at": utc_now(),
        "source_hashes": source_hashes,
        "redaction_summary": redaction_summary,
        "result": clean,
    }
    path = root / "result.json"
    atomic_json(path, payload)
    return path


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and not name.startswith(("/", "\\"))


def _executive(events: list[dict[str, Any]], correlation_id: str) -> str:
    failures = [
        event
        for event in events
        if event.get("status") in {"failed", "blocked", "needs-work", "needs-review"}
        or event.get("failure_class")
    ]
    lines = [
        "# IOT-AI Diagnostic Executive Summary",
        "",
        f"- Correlation ID: `{correlation_id}`",
        f"- Events: {len(events)}",
        f"- Failures/blockers: {len(failures)}",
        "- Export classification: sanitized diagnostics; no credentials or private paths",
        "",
        "## Failure Timeline",
        "",
    ]
    if not failures:
        lines.append("No failure or blocker event was recorded.")
    else:
        for event in failures[:100]:
            lines.append(
                f"- `{event.get('recorded_at', 'unknown')}` · `{event.get('event', 'event')}` · "
                f"`{event.get('status', 'unknown')}` · `{event.get('failure_class') or 'none'}`"
            )
    return "\n".join(lines) + "\n"


def collect(user_home: Path, correlation_id: str, output: Path) -> dict[str, Any]:
    source = run_root(user_home, correlation_id)
    if not source.exists():
        raise FileNotFoundError(correlation_id)
    events: list[dict[str, Any]] = []
    timeline = source / "03_TIMELINE.jsonl"
    if timeline.exists():
        for line in timeline.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    events.append({"event": "timeline.parse-failure", "status": "failed"})

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="iot-ai-diagnostics-") as temporary:
        staging = Path(temporary)
        file_records: list[dict[str, Any]] = []
        redaction_counts: dict[str, int] = {}
        for source_path in sorted(path for path in source.rglob("*") if path.is_file()):
            relative = source_path.relative_to(source)
            if not _safe_member(relative.as_posix()):
                raise ValueError(f"unsafe diagnostics path: {relative}")
            raw = source_path.read_text(encoding="utf-8", errors="replace")
            clean = sanitize(raw, "strict")
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            atomic_text(destination, clean.text, 0o600)
            for finding in clean.findings:
                category = str(finding.get("kind") if isinstance(finding, dict) else finding)
                redaction_counts[category] = redaction_counts.get(category, 0) + 1
            if source_path.suffix == ".json":
                try:
                    structured = json.loads(raw)
                except json.JSONDecodeError:
                    structured = None
                def collect_summaries(item: Any) -> None:
                    if isinstance(item, dict):
                        summary = item.get("redaction_summary")
                        if isinstance(summary, dict):
                            _merge_counts(redaction_counts, {str(k): int(v) for k, v in summary.items()})
                        for child in item.values():
                            collect_summaries(child)
                    elif isinstance(item, list):
                        for child in item:
                            collect_summaries(child)
                collect_summaries(structured)
            file_records.append(
                {
                    "path": relative.as_posix(),
                    "sha256": hashlib.sha256(clean.text.encode()).hexdigest(),
                    "redactions": clean.findings,
                }
            )

        atomic_text(staging / "01_EXECUTIVE_DIAGNOSIS.md", _executive(events, correlation_id), 0o600)
        redaction_report = {
            "schema": "iot-ai.redaction-report.v1",
            "correlation_id": correlation_id,
            "mode": "strict",
            "counts": redaction_counts,
            "secret_values_exported": False,
            "generated_at": utc_now(),
        }
        atomic_json(staging / "10_REDACTION_REPORT.json", redaction_report)
        manifest = {
            "schema": "iot-ai.diagnostics-manifest.v2",
            "correlation_id": correlation_id,
            "created_at": utc_now(),
            "files": file_records,
            "event_count": len(events),
            "failure_count": sum(
                1
                for event in events
                if event.get("status") in {"failed", "blocked", "needs-work", "needs-review"}
                or event.get("failure_class")
            ),
        }
        atomic_json(staging / "00_MANIFEST.json", manifest)
        checksum_lines: list[str] = []
        for path in sorted(candidate for candidate in staging.rglob("*") if candidate.is_file() and candidate.name != "SHA256SUMS.txt"):
            checksum_lines.append(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(staging).as_posix()}"
            )
        atomic_text(staging / "SHA256SUMS.txt", "\n".join(checksum_lines) + "\n", 0o600)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(candidate for candidate in staging.rglob("*") if candidate.is_file()):
                archive.write(path, path.relative_to(staging).as_posix())

    validation = validate(output)
    if validation["decision"] != "pass":
        raise RuntimeError(f"diagnostics validation failed: {validation['errors']}")
    return {
        "decision": "pass",
        "correlation_id": correlation_id,
        "output": str(output),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "files": validation["files"],
        "redaction": redaction_report,
    }


def validate(bundle: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(bundle) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                errors.append("duplicate ZIP member")
            unsafe = [name for name in names if not _safe_member(name)]
            if unsafe:
                errors.append(f"unsafe ZIP members: {unsafe[:5]}")
            required = {"00_MANIFEST.json", "01_EXECUTIVE_DIAGNOSIS.md", "10_REDACTION_REPORT.json", "SHA256SUMS.txt"}
            missing_required = sorted(required - set(names))
            if missing_required:
                errors.append(f"missing required files: {missing_required}")
            checksums: dict[str, str] = {}
            if "SHA256SUMS.txt" in names:
                for line in archive.read("SHA256SUMS.txt").decode("utf-8").splitlines():
                    if "  " not in line:
                        errors.append("malformed checksum line")
                        continue
                    digest, name = line.split("  ", 1)
                    checksums[name] = digest
                for name, expected in checksums.items():
                    if name not in names:
                        errors.append(f"missing {name}")
                    elif hashlib.sha256(archive.read(name)).hexdigest() != expected:
                        errors.append(f"hash mismatch {name}")
            for name in names:
                if name.endswith("/") or name == "SHA256SUMS.txt":
                    continue
                if name not in checksums:
                    errors.append(f"unsealed member {name}")
            joined = b"\n".join(archive.read(name) for name in names if not name.endswith("/"))
            for marker in _SENSITIVE_BYTES:
                if marker in joined:
                    errors.append(f"sensitive marker found: {marker.decode(errors='ignore')}")
            decoded = joined.decode("utf-8", errors="ignore")
            for pattern in _SENSITIVE_TEXT_PATTERNS:
                if pattern.search(decoded):
                    errors.append(f"sensitive pattern found: {pattern.pattern}")
            manifest = json.loads(archive.read("00_MANIFEST.json")) if "00_MANIFEST.json" in names else {}
            if manifest.get("schema") != "iot-ai.diagnostics-manifest.v2":
                errors.append("invalid diagnostics manifest schema")
    except (zipfile.BadZipFile, OSError, json.JSONDecodeError) as exc:
        errors.append(type(exc).__name__)
    return {
        "decision": "pass" if not errors else "block",
        "bundle": str(bundle),
        "errors": errors,
        "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest() if bundle.is_file() else None,
        "files": len(names) if "names" in locals() else 0,
    }


def explain(bundle: Path) -> dict[str, Any]:
    result = validate(bundle)
    events: list[dict[str, Any]] = []
    correlation_id = None
    if result["decision"] == "pass":
        with zipfile.ZipFile(bundle) as archive:
            manifest = json.loads(archive.read("00_MANIFEST.json"))
            correlation_id = manifest.get("correlation_id")
            if "03_TIMELINE.jsonl" in archive.namelist():
                events = [
                    json.loads(line)
                    for line in archive.read("03_TIMELINE.jsonl").decode("utf-8").splitlines()
                    if line.strip()
                ]
    failures = [
        event
        for event in events
        if event.get("status") in {"failed", "blocked", "needs-work", "needs-review"}
        or event.get("failure_class")
    ]
    return {
        **result,
        "correlation_id": correlation_id,
        "events": len(events),
        "failures": failures[:100],
        "summary": "No failures recorded" if not failures else f"{len(failures)} failure or blocker events recorded",
    }


def compare(bundle_a: Path, bundle_b: Path) -> dict[str, Any]:
    first = explain(bundle_a)
    second = explain(bundle_b)
    return {
        "decision": "pass" if first["decision"] == second["decision"] == "pass" else "block",
        "a": {"sha256": first.get("sha256"), "events": first.get("events"), "failures": len(first.get("failures", []))},
        "b": {"sha256": second.get("sha256"), "events": second.get("events"), "failures": len(second.get("failures", []))},
        "failure_delta": len(second.get("failures", [])) - len(first.get("failures", [])),
    }
