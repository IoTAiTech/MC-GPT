# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.6 | Date: 2026-08-18
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from tests.common import synthetic_openai_env_line


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicBoundaryEnvTests(unittest.TestCase):
    def test_env_file_is_classified_and_blocked(self) -> None:
        tools = Path(__file__).resolve().parents[1] / "tools"
        boundary = _load("iot_ai_public_boundary", tools / "public_boundary_check.py")
        with tempfile.TemporaryDirectory(prefix="iot-ai-boundary-env-") as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "docs" / ".env").write_text(synthetic_openai_env_line(), encoding="utf-8")
            (root / "README.md").write_text("Public documentation\n", encoding="utf-8")
            findings = boundary.scan_tree(root)
        self.assertTrue(any(item["rule"] == "forbidden-env-or-key" for item in findings))

    def test_reconstructed_concatenated_private_literal_is_rejected(self) -> None:
        tools = Path(__file__).resolve().parents[1] / "tools"
        boundary = _load("iot_ai_public_boundary", tools / "public_boundary_check.py")
        q = chr(34)
        host_line = "HOST = " + q + chr(49) + chr(48) + chr(46) + q + " + " + q + chr(48) + chr(46) + chr(48) + chr(46) + chr(49) + q + "\n"
        path_line = "PATH = " + q + chr(47) + "home/" + q + " + " + q + "operator/private" + q + "\n"
        with tempfile.TemporaryDirectory(prefix="iot-ai-boundary-fold-") as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src" / "fold.py").write_text(host_line + path_line, encoding="utf-8")
            (root / "README.md").write_text("Public documentation\n", encoding="utf-8")
            findings = boundary.scan_tree(root)
        rules = {item["rule"] for item in findings}
        self.assertIn("reconstructed:private-ip", rules)
        self.assertIn("reconstructed:personal-path", rules)

    def test_adjacent_string_literals_are_folded(self) -> None:
        tools = Path(__file__).resolve().parents[1] / "tools"
        boundary = _load("iot_ai_public_boundary", tools / "public_boundary_check.py")
        q = chr(34)
        line = "HOST = " + q + chr(49) + chr(48) + chr(46) + q + " " + q + chr(50) + chr(48) + chr(46) + chr(51) + chr(48) + chr(46) + chr(52) + chr(48) + q + "\n"
        with tempfile.TemporaryDirectory(prefix="iot-ai-boundary-adj-") as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src" / "adj.py").write_text(line, encoding="utf-8")
            findings = boundary.scan_tree(root)
        self.assertTrue(any(item["rule"] == "reconstructed:private-ip" for item in findings))

    def test_simple_join_and_static_fstring_are_folded(self) -> None:
        tools = Path(__file__).resolve().parents[1] / "tools"
        boundary = _load("iot_ai_public_boundary", tools / "public_boundary_check.py")
        q = chr(34)
        join_line = "A = " + q + q + ".join([" + q + chr(49) + chr(48) + chr(46) + q + ", " + q + chr(48) + chr(46) + chr(48) + chr(46) + chr(50) + q + "])\n"
        f_line = "B = f" + q + chr(49) + chr(48) + chr(46) + "{0}." + chr(48) + chr(46) + chr(51) + q + "\n"
        with tempfile.TemporaryDirectory(prefix="iot-ai-boundary-join-") as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src" / "join.py").write_text(join_line + f_line, encoding="utf-8")
            findings = boundary.scan_tree(root)
        self.assertTrue(any(item["rule"] == "reconstructed:private-ip" for item in findings))

    def test_reversed_multiply_and_bytes_concat_are_folded(self) -> None:
        tools = Path(__file__).resolve().parents[1] / "tools"
        boundary = _load("iot_ai_public_boundary", tools / "public_boundary_check.py")
        q = chr(34)
        sk = q + chr(115) + chr(107) + chr(45) + q
        fill = q + "A" + q
        reversed_mul = "TOKEN = " + sk + " + (20 * " + fill + ")\n"
        bytes_concat = "TOKEN = b" + sk + " + (b" + fill + " * 20)\n"
        with tempfile.TemporaryDirectory(prefix="iot-ai-boundary-bytes-") as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src" / "mul.py").write_text(reversed_mul, encoding="utf-8")
            (root / "src" / "bytes.py").write_text(bytes_concat, encoding="utf-8")
            findings = boundary.scan_tree(root)
        rules = {item["rule"] for item in findings}
        self.assertIn("reconstructed:token-literal", rules)


if __name__ == "__main__":
    unittest.main()
