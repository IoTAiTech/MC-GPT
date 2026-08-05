# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
"""Human and AI-readable help for the minimal public command surface."""
from __future__ import annotations

PUBLIC = {
    "iot-ai": {
        "purpose": "Solve a natural-language goal through knowledge reuse, immutable specialist roles, dependency-aware graph execution, deterministic verification and diagnostics.",
        "examples": [
            "iot-ai deeply investigate this defect, fix verified causes and return a sanitized diagnostics bundle",
            "iot-ai --profile ultracode --execute review and improve this architecture",
        ],
        "boundary": "Writes require the active task and authorization policy. Provider availability is not inferred from installation alone.",
    },
    "status": {
        "purpose": "Show Suite, coder, provider/model readiness, effective effort and evidence-derived workflow scores.",
        "examples": ["iot-ai status", "iot-ai status --live --window 24h"],
        "boundary": "Live probes may spend provider quota; static status never claims live readiness.",
    },
    "settings": {
        "purpose": "Manage platform-independent cloud, Ollama, model, privacy, storage and orchestration settings.",
        "examples": ["iot-ai settings show", "iot-ai settings profile set ultracode --session-only"],
        "boundary": "Credential values are forbidden in settings; use provider-native sessions or secret stores.",
    },
    "update": {
        "purpose": "Single transactional Suite update authority: status, plan, apply and rollback.",
        "examples": ["iot-ai update status", "iot-ai update plan", "iot-ai update apply --package <zip> --expected-sha256 <sha>"],
        "boundary": "No published signed target is reported honestly; no silent apply or in-place overwrite.",
    },
    "diagnostics": {
        "purpose": "Collect, validate, explain and compare sanitized correlation bundles.",
        "examples": ["iot-ai diagnostics collect --correlation-id <id> --output diagnostics.zip"],
        "boundary": "Export removes secrets, tokens, private infrastructure and customer-like identifiers by default.",
    },
    "meeting": {
        "purpose": "Internal graph template for independent roles, challenge, layered fan-in, one frozen plan digest and evidence-bound acceptance.",
        "examples": ["iot-ai meeting start --topic 'Review the design' --seats auto --depth deep"],
        "boundary": "Meeting execution success is not plan acceptance, founder approval or task authorization.",
    },
    "tasks": {
        "purpose": "Internal transactional lifecycle for task, work unit, lease, attempts, evidence, tests and audit.",
        "examples": ["iot-ai tasks open", "iot-ai tasks show <task-id>"],
        "boundary": "SQLite or an enterprise adapter is authoritative; Excel is a sealed human projection only.",
    },
}

QUICKSTART = {
    "title": "IOT-AI Suite five-minute quickstart",
    "steps": [
        "iot-ai help",
        "iot-ai settings show",
        "iot-ai status",
        "iot-ai --profile balanced 'Review this task and produce a verified plan'",
    ],
    "safety": "Cloud egress is privacy-gated. Empty or unverified seats never satisfy required roles.",
}


def list_topics() -> dict:
    return {"decision": "pass", "topics": sorted(PUBLIC), "public_commands": ["iot-ai", "iot-ai-help", "iot-ai-status", "iot-ai-settings", "iot-ai-update"]}


def show(topic: str | None = None) -> dict:
    if not topic or topic in {"quickstart", "start"}:
        return {"decision": "pass", **QUICKSTART}
    key = topic.removeprefix("iot-ai-")
    if key == "help":
        return list_topics()
    value = PUBLIC.get(key)
    if value is None:
        matches = [name for name, row in PUBLIC.items() if key.casefold() in name.casefold() or key.casefold() in row["purpose"].casefold()]
        return {"decision": "needs-work", "topic": topic, "matches": matches}
    return {"decision": "pass", "topic": key, **value}


def search(term: str) -> dict:
    needle = term.casefold()
    matches = [name for name, row in PUBLIC.items() if needle in name.casefold() or needle in row["purpose"].casefold() or any(needle in item.casefold() for item in row["examples"])]
    return {"decision": "pass", "term": term, "matches": matches}
