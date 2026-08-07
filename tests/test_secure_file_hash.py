# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Fail-closed path policy for sha256_file / open_secure (CodeQL path injection)."""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path

from iot_ai.util import (
    DEFAULT_MAX_HASH_BYTES,
    PathSecurityError,
    open_secure,
    resolve_within_allowed_roots,
    sha256_file,
)


class SecureFileHashTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.allowed = self.root / "allowed"
        self.outside = self.root / "outside"
        self.allowed.mkdir()
        self.outside.mkdir()
        self.good = self.allowed / "payload.bin"
        self.good.write_bytes(b"hello-secure-hash")
        self.expected = hashlib.sha256(b"hello-secure-hash").hexdigest()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_allowed_normal_file(self) -> None:
        digest = sha256_file(self.good, allowed_roots=[self.allowed])
        self.assertEqual(digest, self.expected)
        with open_secure(self.good, [self.allowed]) as handle:
            self.assertEqual(handle.read(), b"hello-secure-hash")

    def test_relative_path_traversal_rejected(self) -> None:
        outside = self.outside / "secret.txt"
        outside.write_text("secret", encoding="utf-8")
        # Attempt to escape allowed root via ../outside/secret.txt
        attacker = self.allowed / ".." / "outside" / "secret.txt"
        with self.assertRaises(PathSecurityError):
            sha256_file(attacker, allowed_roots=[self.allowed])

    def test_absolute_external_path_rejected(self) -> None:
        external = self.outside / "passwd-like"
        external.write_text("root:x:0:0", encoding="utf-8")
        with self.assertRaises(PathSecurityError):
            sha256_file(external, allowed_roots=[self.allowed])

    def test_symlink_to_external_file_rejected(self) -> None:
        target = self.outside / "ext.dat"
        target.write_bytes(b"external-bytes")
        link = self.allowed / "link.dat"
        try:
            link.symlink_to(target)
        except OSError as exc:  # pragma: no cover - platform without symlink
            self.skipTest(f"symlink unsupported: {exc}")
        with self.assertRaises(PathSecurityError):
            sha256_file(link, allowed_roots=[self.allowed])

    def test_directory_rejected(self) -> None:
        with self.assertRaises(PathSecurityError):
            sha256_file(self.allowed, allowed_roots=[self.root])

    def test_fifo_rejected(self) -> None:
        fifo = self.allowed / "pipe.fifo"
        try:
            os.mkfifo(fifo)
        except (AttributeError, OSError) as exc:  # pragma: no cover
            self.skipTest(f"fifo unsupported: {exc}")
        with self.assertRaises(PathSecurityError):
            sha256_file(fifo, allowed_roots=[self.allowed])

    def test_missing_file_rejected(self) -> None:
        missing = self.allowed / "gone.bin"
        with self.assertRaises(PathSecurityError):
            sha256_file(missing, allowed_roots=[self.allowed])

    def test_deleted_file_after_resolve_fails_closed(self) -> None:
        # open_secure re-stats via fstat; missing path is rejected up front
        gone = self.allowed / "ephemeral.bin"
        gone.write_bytes(b"x")
        gone.unlink()
        with self.assertRaises(PathSecurityError):
            sha256_file(gone, allowed_roots=[self.allowed])

    def test_max_bytes_limit(self) -> None:
        big = self.allowed / "big.bin"
        big.write_bytes(b"a" * 100)
        with self.assertRaises(PathSecurityError):
            sha256_file(big, allowed_roots=[self.allowed], max_bytes=50)

    def test_empty_allowed_roots_rejected(self) -> None:
        with self.assertRaises(PathSecurityError):
            sha256_file(self.good, allowed_roots=[])  # type: ignore[arg-type]

    def test_windows_drive_and_unc_style_rejection(self) -> None:
        # Portable assertions: absolute path outside roots is always rejected.
        # On Windows, drive-letter and UNC escapes are covered by membership checks.
        other = self.outside / "drive-escape.txt"
        other.write_text("nope", encoding="utf-8")
        with self.assertRaises(PathSecurityError):
            resolve_within_allowed_roots(other, [self.allowed])
        if os.name == "nt":
            unc = Path(r"\\evil-host\share\file.txt")
            with self.assertRaises(PathSecurityError):
                resolve_within_allowed_roots(unc, [self.allowed], must_exist=False)

    def test_hash_matches_fd_contents_not_path_string(self) -> None:
        digest = sha256_file(self.good, allowed_roots=[self.root])
        self.assertEqual(digest, self.expected)
        self.assertNotEqual(digest, hashlib.sha256(str(self.good).encode()).hexdigest())

    def test_default_max_bytes_constant_positive(self) -> None:
        self.assertGreater(DEFAULT_MAX_HASH_BYTES, 0)


if __name__ == "__main__":
    unittest.main()
