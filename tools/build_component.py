# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Build the public MC-GPT component archive deterministically."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import zipfile
from pathlib import Path

FIXED_TIME = (2026, 8, 8, 0, 0, 0)
COMPONENT_VERSION = "0.8.0-alpha.5"
SUITE_VERSION = "6.7.0-beta.5"
SEED_MODULES = {
    "acceptance_scorecard.py", "agent_contract_validation.py", "agent_seats.py", "agentic.py",
    "autopilot.py", "autopilot_reporting.py", "capability_pack.py", "checkpoints.py",
    "context_compiler.py", "conversation_state.py", "control_flow.py", "intent_router.py",
    "task_backends.py",
    "decision_receipts.py", "diagnostics.py", "eu_ai_act.py", "european_compliance.py", "goal_contract.py",
    "graph_runtime.py", "knowledge_plane.py", "meeting.py", "meeting_api.py", "meeting_integration.py", "meeting_reporting.py", "agent_seats.py", "mesh.py", "model_policy.py",
    "multicoder.py", "owned_delegate.py", "privacy.py", "projection.py", "prompt_compiler.py",
    "plugin_api.py", "quality.py", "readiness.py", "report.py", "roles.py", "settings.py", "status.py",
    "storage.py", "tasks.py", "telemetry.py", "tool_router.py", "transparency.py",
    "workspace.py",
}
DOCS = {
    "agent-runtime.md", "architecture.md", "autonomous-closed-loop.md", "bootstrap-installation.md",
    "capability-packs.md", "competitor-patterns.md", "context-engineering.md", "diagnostics.md",
    "goal-first-orchestration.md", "knowledge-and-rag.md", "meeting.md", "meeting-integration.md",
    "meeting-reporting.md", "multi-coder.md", "privacy-and-cloud.md", "providers.md",
    "reporting.md", "task-validation.md", "tasks.md",
}


def _module_closure(root: Path) -> set[str]:
    """Resolve every in-package relative import required by the MC-GPT seed modules."""
    package_root = root / "src" / "iot_ai"
    modules = set(SEED_MODULES)
    modules.add("__init__.py")
    pending = list(modules)
    while pending:
        name = pending.pop()
        path = package_root / name
        if not path.is_file() or name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level < 1 or not node.module:
                continue
            target = node.module.split(".", 1)[0] + ".py"
            if (package_root / target).is_file() and target not in modules:
                modules.add(target)
                pending.append(target)
    return modules


def _write(archive: zipfile.ZipFile, name: str, data: bytes, mode: int = 0o644) -> None:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (mode & 0xFFFF) << 16
    archive.writestr(info, data)


def build(root: Path, output_dir: Path) -> dict[str, object]:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"IOT-AI-MC-GPT-v{COMPONENT_VERSION}-COMPONENT.zip"
    files: dict[str, bytes] = {}
    modules = _module_closure(root)
    for name in sorted(modules):
        path = root / "src" / "iot_ai" / name
        files[f"src/iot_ai/{name}"] = path.read_bytes()
    for name in sorted(DOCS):
        path = root / "docs" / name
        files[f"docs/{name}"] = path.read_bytes()
    for subtree in ("compliance", "research"):
        base = root / "docs" / subtree
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.is_symlink():
                files[f"docs/{subtree}/{path.relative_to(base).as_posix()}"] = path.read_bytes()
    for path in sorted((root / "schemas").rglob("*.json")):
        files[f"schemas/{path.relative_to(root / 'schemas').as_posix()}"] = path.read_bytes()
    files["skills/iot-ai/SKILL.md"] = (root / "skills" / "iot-ai" / "SKILL.md").read_bytes()
    component = {
        "schema": "iot-ai.component.v2",
        "component_id": "iot-ai-mc-gpt",
        "product_id": "iot-ai-tech.iot-ai-mc-gpt",
        "version": COMPONENT_VERSION,
        "suite_compatibility": {"minimum": SUITE_VERSION, "maximum_exclusive": "7.0.0"},
        "classification": "community-source-component-not-standalone-installer",
        "entrypoint": "iot-ai",
        "state_namespace": "iot-ai-tech/iot-ai-suite/v1",
    }
    files["component.json"] = (json.dumps(component, indent=2, sort_keys=True) + "\n").encode()
    manifest = {
        "schema": "iot-ai.component-manifest.v2",
        "component_id": "iot-ai-mc-gpt",
        "version": COMPONENT_VERSION,
        "files": [
            {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in sorted(files.items())
        ],
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items()))
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            _write(archive, name, data)
        _write(archive, "MANIFEST.json", manifest_bytes)
        _write(archive, "SHA256SUMS.txt", sums.encode())
    return {
        "schema": "iot-ai.component-build.v2",
        "decision": "pass",
        "path": str(output),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "files": len(files),
        "modules": len(modules),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("output", nargs="?", default="dist")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.root), Path(args.output)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
