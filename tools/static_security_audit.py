# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Small deterministic AST security audit used when external scanners are unavailable."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

SKIP = {".git", ".venv", "venv", "build", "dist", "__pycache__", ".pytest_cache"}
DANGEROUS_CALLS = {"eval", "exec", "os.system", "pickle.loads", "pickle.load", "marshal.loads"}


def call_name(node: ast.Call) -> str:
    current = node.func
    values: list[str] = []
    while isinstance(current, ast.Attribute):
        values.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        values.append(current.id)
    return ".".join(reversed(values))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    findings: list[dict[str, object]] = []
    files = 0
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in SKIP or part.endswith(".egg-info") for part in rel.parts):
            continue
        files += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
        except SyntaxError as exc:
            findings.append({"severity": "high", "file": rel.as_posix(), "line": exc.lineno, "rule": "syntax-error"})
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = call_name(node)
            if name in DANGEROUS_CALLS:
                findings.append({"severity": "high", "file": rel.as_posix(), "line": node.lineno, "rule": f"dangerous-call:{name}"})
            if name in {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call", "subprocess.check_output"}:
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        findings.append({"severity": "high", "file": rel.as_posix(), "line": node.lineno, "rule": "subprocess-shell-true"})
            if name in {"yaml.load", "yaml.unsafe_load"}:
                findings.append({"severity": "high", "file": rel.as_posix(), "line": node.lineno, "rule": "unsafe-yaml-load"})
    high = [row for row in findings if row["severity"] == "high"]
    payload = {"schema": "iot-ai.static-security-audit.v1", "decision": "pass" if not high else "block", "files": files, "high_findings": len(high), "findings": findings}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not high else 1


if __name__ == "__main__":
    raise SystemExit(main())
