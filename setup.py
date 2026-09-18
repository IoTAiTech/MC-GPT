# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-04
"""Package reviewed data without introducing runtime or network dependencies."""
from pathlib import Path
import runpy
import shutil
from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent


class ReviewedDataBuild(build_py):
    def run(self):
        collector = runpy.run_path(str(ROOT / "tools/package_assets.py"))
        assets = collector["collect_public_assets"](ROOT)
        super().run()
        # These two directories are owned build outputs, not operator state.
        # Remove stale assets from earlier builds rather than shipping them.
        for relative in ("iot_ai/data/skills", "iot_ai/data/governance"):
            managed = Path(self.build_lib) / relative
            if managed.is_symlink():
                raise ValueError("symlink-build-output")
            if managed.exists():
                shutil.rmtree(managed)
        for name, data in assets:
            destination = Path(self.build_lib) / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)


setup(cmdclass={"build_py": ReviewedDataBuild})
