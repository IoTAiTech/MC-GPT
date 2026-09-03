# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path

from iot_ai.meeting_reporting import collect, write_report, write_report_bundle
from iot_ai.projection import export_workspace
from iot_ai.util import PathSecurityError
from tests.common import IsolatedHomeTestCase, synthetic_personal_path, synthetic_rfc1918_host


SCHEMA = """
CREATE TABLE meetings(
 meeting_id TEXT PRIMARY KEY, topic TEXT NOT NULL, topic_sha256 TEXT NOT NULL,
 privacy_class TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
 seats_json TEXT NOT NULL, quorum INTEGER NOT NULL, max_revision_rounds INTEGER NOT NULL,
 synthesizer_seat TEXT, final_text TEXT NOT NULL DEFAULT '', final_sha256 TEXT,
 user_approved INTEGER NOT NULL DEFAULT 0, task_id TEXT, created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE contributions(
 contribution_id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL, seat_id TEXT NOT NULL,
 provider TEXT NOT NULL, model_requested TEXT, model_served TEXT, stage TEXT NOT NULL,
 round_no INTEGER NOT NULL, status TEXT NOT NULL, decision TEXT NOT NULL,
 content TEXT NOT NULL, content_sha256 TEXT NOT NULL, receipt_id TEXT,
 latency_ms INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE meeting_events(
 event_id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL, event_type TEXT NOT NULL,
 payload_json TEXT NOT NULL, prev_hash TEXT, event_hash TEXT NOT NULL,
 created_at TEXT NOT NULL
);
"""


class MeetingReportingV2Tests(IsolatedHomeTestCase):
    def make_legacy(self, path: Path, *, privacy: str = "D2") -> Path:
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
        topic = "Review host " + synthetic_rfc1918_host() + " and path " + synthetic_personal_path()
        final = "\x1b[31mDECISION: needs-work\x1b[0m\nSynthesis with unresolved evidence."
        conn.execute(
            "INSERT INTO meetings VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "meeting-legacy-1", topic, hashlib.sha256(topic.encode()).hexdigest(),
                privacy, "decision", "running",
                json.dumps([{"seat_id": "claude", "provider": "claude", "model": ""}]),
                1, 1, "claude", final, hashlib.sha256(final.encode()).hexdigest(),
                1, "task-legacy-1", "2026-07-01T00:00:00Z", "2026-07-01T01:00:00Z",
            ),
        )
        content = "\x1b[32mEvidence-backed opinion\x1b[0m"
        conn.execute(
            "INSERT INTO contributions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "contrib-1", "meeting-legacy-1", "claude", "claude", None, None,
                "opinion", 1, "completed", "needs-work", content,
                hashlib.sha256(content.encode()).hexdigest(), None, 25,
                "2026-07-01T00:10:00Z",
            ),
        )
        conn.execute(
            "INSERT INTO meeting_events VALUES(?,?,?,?,?,?,?)",
            ("event-1", "meeting-legacy-1", "meeting.created", "{}", None, "0" * 64, "2026-07-01T00:00:00Z"),
        )
        conn.commit()
        conn.close()
        return path

    def test_legacy_federation_is_read_only_and_reports_lifecycle_gaps(self) -> None:
        legacy = self.make_legacy(self.home / "legacy.sqlite3")
        before = hashlib.sha256(legacy.read_bytes()).hexdigest()
        payload = collect(
            self.home,
            view="full",
            legacy_dbs=[legacy],
            include_current=False,
            classification="restricted",
            stale_after_hours=1,
        )
        self.assertEqual(payload["meeting_count"], 1)
        item = payload["meetings"][0]
        self.assertEqual(item["status"], "stale")
        self.assertIn("legacy-running-session-stale", item["lifecycle_issues"])
        self.assertIn("approval-status-conflict", item["lifecycle_issues"])
        self.assertFalse(item["model_telemetry_complete"])
        self.assertEqual(item["substantive_seats"], 0)
        self.assertNotIn("\x1b", json.dumps(payload))
        self.assertEqual(before, hashlib.sha256(legacy.read_bytes()).hexdigest())

    def test_public_requires_allowlist_and_d0_and_redacts(self) -> None:
        legacy = self.make_legacy(self.home / "legacy.sqlite3", privacy="D0")
        with self.assertRaises(PermissionError):
            collect(self.home, legacy_dbs=[legacy], include_current=False, classification="public")
        payload = collect(
            self.home,
            legacy_dbs=[legacy],
            include_current=False,
            classification="public",
            public_allowlist=["meeting-legacy-1"],
        )
        text = json.dumps(payload)
        self.assertEqual(payload["classification"], "PUBLIC-SANITIZED")
        self.assertNotIn(synthetic_rfc1918_host(), text)
        self.assertNotIn(synthetic_personal_path(), text)
        self.assertNotIn("synthesis_summary", text)
        self.assertNotIn("path", json.dumps(payload["source_manifest"]))

    def test_bundle_contains_machine_and_human_reports(self) -> None:
        legacy = self.make_legacy(self.home / "legacy.sqlite3")
        output = self.home / "meeting-report-bundle.zip"
        result = write_report_bundle(
            self.home,
            output,
            view="brief",
            legacy_dbs=[legacy],
            include_current=False,
            classification="restricted",
            stale_after_hours=1,
        )
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(Path(result["sha256_sidecar"]).read_text().split()[1], output.name)
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertTrue({
                "MEETINGS_INDEX.json", "MEETINGS_SUMMARY.csv", "MEETINGS_REPORT.md",
                "MEETINGS_REPORT.xlsx", "MODEL_PARTICIPATION.csv",
                "DECISIONS_AND_DISSENTS.csv", "LIFECYCLE_ISSUES.csv",
                "PROVENANCE.json", "MANIFEST.json", "SHA256SUMS.txt",
            }.issubset(names))
            joined = b"\n".join(archive.read(name) for name in names if not name.endswith(".xlsx"))
            self.assertNotIn(b"\x1b", joined)

    def test_single_file_writes_basename_only_checksum(self) -> None:
        legacy = self.make_legacy(self.home / "legacy.sqlite3")
        output = self.home / "meetings.json"
        result = write_report(
            self.home, output, output_format="json", view="brief",
            legacy_dbs=[legacy], include_current=False, classification="restricted",
        )
        sidecar = Path(result["sha256_sidecar"]).read_text(encoding="utf-8")
        self.assertIn("  meetings.json", sidecar)
        self.assertNotIn(str(self.home), sidecar)

    def test_legacy_db_outside_trusted_roots_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outside = self.make_legacy(Path(tmp) / "legacy.sqlite3")
            old = os.environ.pop("IOT_AI_ALLOWED_READ_ROOTS", None)
            try:
                with patch("iot_ai.meeting_reporting.trusted_operator_roots", return_value=(self.home.resolve(),)):
                    with self.assertRaises(PathSecurityError):
                        collect(self.home, legacy_dbs=[outside], include_current=False)
            finally:
                if old is not None:
                    os.environ["IOT_AI_ALLOWED_READ_ROOTS"] = old

    def test_bundle_zip_outside_trusted_roots_is_rejected(self) -> None:
        legacy = self.make_legacy(self.home / "legacy.sqlite3")
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "escape.zip"
            old = os.environ.pop("IOT_AI_ALLOWED_READ_ROOTS", None)
            try:
                with patch("iot_ai.meeting_reporting.trusted_operator_roots", return_value=(self.home.resolve(),)):
                    with self.assertRaises(PathSecurityError):
                        write_report_bundle(
                            self.home,
                            outside,
                            view="brief",
                            legacy_dbs=[legacy],
                            include_current=False,
                            classification="restricted",
                        )
                self.assertFalse(outside.exists())
            finally:
                if old is not None:
                    os.environ["IOT_AI_ALLOWED_READ_ROOTS"] = old

    def test_excel_export_outside_trusted_roots_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "pwn" / "out.xlsx"
            old = os.environ.pop("IOT_AI_ALLOWED_READ_ROOTS", None)
            try:
                with patch("iot_ai.projection.trusted_operator_roots", return_value=(self.home.resolve(),)):
                    with self.assertRaises(PathSecurityError):
                        export_workspace(self.home, outside)
                self.assertFalse(outside.exists())
            finally:
                if old is not None:
                    os.environ["IOT_AI_ALLOWED_READ_ROOTS"] = old


if __name__ == "__main__":
    unittest.main()
