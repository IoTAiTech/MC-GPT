# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-30
"""Cross-platform contention contracts for the exclusive lock helper."""
from __future__ import annotations

import errno
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from iot_ai.util import exclusive_lock


class ExclusiveLockTests(unittest.TestCase):
    def test_existing_lock_permission_error_is_treated_as_contention(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "state.lock"
            lock.write_text("stale", encoding="utf-8")
            stale_time = time.time() - 10
            os.utime(lock, (stale_time, stale_time))
            original_open = os.open
            injected = False

            def open_once_as_windows_contention(
                path: os.PathLike[str] | str,
                flags: int,
                mode: int = 0o777,
                *args: object,
                **kwargs: object,
            ) -> int:
                nonlocal injected
                if Path(path) == lock and not injected:
                    injected = True
                    raise PermissionError(
                        errno.EACCES, "simulated sharing violation", str(path)
                    )
                return original_open(path, flags, mode, *args, **kwargs)

            with patch(
                "iot_ai.util.os.open", side_effect=open_once_as_windows_contention
            ):
                with exclusive_lock(
                    lock, timeout_seconds=1.0, stale_seconds=0.1
                ):
                    self.assertTrue(lock.exists())

            self.assertTrue(injected)
            self.assertFalse(lock.exists())

    def test_permission_error_without_existing_lock_is_not_masked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "state.lock"
            denied = PermissionError(
                errno.EACCES, "simulated access denial", str(lock)
            )
            with patch("iot_ai.util.os.open", side_effect=denied):
                with self.assertRaises(PermissionError):
                    with exclusive_lock(lock, timeout_seconds=0.05):
                        self.fail("lock must not be acquired")


if __name__ == "__main__":
    unittest.main()
