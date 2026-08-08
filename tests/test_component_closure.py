# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ComponentClosureTests(unittest.TestCase):
    def test_component_module_closure_contains_every_relative_dependency(self) -> None:
        spec = importlib.util.spec_from_file_location("iot_ai_build_component", ROOT / "tools" / "build_component.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        closure = module._module_closure(ROOT)
        self.assertIn("__init__.py", closure)
        package_root = ROOT / "src" / "iot_ai"
        missing: list[tuple[str, str]] = []
        for name in sorted(closure):
            if name == "__init__.py":
                continue
            tree = ast.parse((package_root / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level and node.module:
                    target = node.module.split(".", 1)[0] + ".py"
                    if (package_root / target).is_file() and target not in closure:
                        missing.append((name, target))
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
