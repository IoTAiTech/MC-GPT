# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-05
"""Real child-process assertions over synthetic source; no live providers."""
import sys

from iot_ai.test_execution_evidence import CheckCommand, HostTestRunner, source_digest


def host_runner(home, *, fail=False):
    root = home / "verification-source"
    root.mkdir(exist_ok=True)
    (root / "fixture.txt").write_text("verified\n", encoding="utf-8")
    code = 'from pathlib import Path; assert Path("fixture.txt").read_text() == "verified\\n"'
    if fail:
        code += '; raise AssertionError("deliberate fixture failure")'
    return HostTestRunner(cwd=root, commands=[CheckCommand((sys.executable, "-I", "-c", code))],
                          current_source_digest=lambda: source_digest(root, ["fixture.txt"]))
