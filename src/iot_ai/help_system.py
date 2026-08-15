# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Human and AI-readable help for the minimal public command surface."""
from __future__ import annotations

PUBLIC = {
    "iot-ai": {
        "purpose": "Describe the outcome in natural language. MC-GPT resolves context, selects the authoritative task backend, runs Task → Meeting → Multi-Coder → test/repair/audit loops and continues to a truthful terminal state.",
        "examples": [
            "iot-ai 'Finish all critical PMD tasks, use all available coders, meet on every failure, and continue until technical completion.'",
            "iot-ai 'Continue, finish the remaining tasks, and give one complete table at the end.'",
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
    "github-analyze": {
        "purpose": "Analyze inbound GitHub repositories for technical fit, commercial terms, license grant, and relevance. Reuse only our own rewrite of a pattern, model, or idea.",
        "examples": [
            "iot-ai github-analyze https://github.com/example/tool",
            "iot-ai github-analyze --offline-json records.json --no-network",
        ],
        "boundary": "Never adds a dependency, never infers MIT, never copies another project's license onto ours, and never vendors copyleft or unlicensed code.",
    },
    "diagnostics": {
        "purpose": "Collect, validate, explain and compare sanitized correlation bundles.",
        "examples": ["iot-ai diagnostics collect --correlation-id <id> --output diagnostics.zip"],
        "boundary": "Export removes secrets, tokens, private infrastructure and customer-like identifiers by default.",
    },
    "meeting": {
        "purpose": "Internal graph template for independent roles, challenge, layered fan-in, one frozen plan digest and evidence-bound acceptance.",
        "examples": [
            "iot-ai meeting seat-plan --seats all-coders+ollama-clouds",
            "iot-ai meeting start --topic 'Review the design' --seats all-coders+ollama-clouds --depth deep",
            "iot-ai-meeting --max-parallel ask all coder and ollama clouds only review this design",
        ],
        "boundary": "Ollama Cloud cannot be silently omitted when first-class policy applies. Meeting execution success is not plan acceptance, founder approval or task authorization.",
    },
    "tasks": {
        "purpose": "Internal transactional lifecycle for task, work unit, lease, attempts, evidence, tests and audit.",
        "examples": ["iot-ai tasks open", "iot-ai tasks show <task-id>"],
        "boundary": "SQLite or an enterprise adapter is authoritative; Excel is a sealed human projection only.",
    },
    "worktree": {
        "purpose": "Create and inspect isolated git worktrees for parallel coders without copying untracked files or auto-merging results.",
        "examples": [
            "iot-ai worktree plan --repo . --goal 'Review auth' --agents codex,grok",
            "iot-ai worktree create --repo . --goal 'Review auth' --agents codex,grok --apply",
        ],
        "boundary": "Dirty or unmerged work blocks cleanup; promotion is an explicit human-reviewed draft-PR flow.",
    },
}

QUICKSTART = {
    "title": "MC-GPT five-minute quickstart — natural-language closed loop",
    "steps": [
        "iot-ai help",
        "iot-ai settings show",
        "iot-ai status",
        "iot-ai 'Finish the selected tasks; use all eligible coders; hold a meeting on failures; verify and report everything.'",
    ],
    "safety": "Cloud egress is privacy-gated. Empty or unverified seats never satisfy required roles.",
}


def list_topics() -> dict:
    return {
        "decision": "pass",
        "topics": sorted(PUBLIC),
        "public_commands": ["iot-ai", "iot-ai-help", "iot-ai-status", "iot-ai-settings", "iot-ai-update"],
        "workflow_aliases": ["iot-ai-meeting", "iot-ai-tasks", "iot-ai-multi-coder"],
    }


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
