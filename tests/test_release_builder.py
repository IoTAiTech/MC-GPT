# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


class ReleaseBuilderTests(unittest.TestCase):
    def test_source_archive_has_one_generated_manifest_and_no_duplicates(self) -> None:
        root = Path(__file__).resolve().parents[1]
        module_path = root / "tools" / "build_release.py"
        spec = importlib.util.spec_from_file_location("iot_ai_build_release", module_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="iot-ai-source-build-test-") as temporary:
            result = module.build(root, Path(temporary))
            with zipfile.ZipFile(result["path"]) as archive:
                names = archive.namelist()
                self.assertEqual(len(names), len(set(names)))
                manifests = [name for name in names if name.endswith("/SOURCE_MANIFEST.json")]
                self.assertEqual(len(manifests), 1)


if __name__ == "__main__":
    unittest.main()
