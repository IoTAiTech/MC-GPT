# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-06
"""Installed source/data integrity and honest source-adapter verification."""
import base64
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch
import shutil

import pytest
from iot_ai.installer import install, verify
from iot_ai.paths import install_state_path
from iot_ai.runtime_integrity import verify_distribution


@pytest.fixture
def installed(tmp_path):
    base = tmp_path / "site-packages"
    package = base / "iot_ai"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VERSION = '1.0.0'\n")
    (package / "cli.py").write_text("def main(): return 0\n")
    metadata = base / "iot_ai_coder_suite-1.0.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Name: iot-ai-coder-suite\nVersion: 1.0.0\n")
    rows = []
    for path in sorted(package.iterdir()):
        data = path.read_bytes()
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        rows.append([path.relative_to(base).as_posix(), "sha256=" + digest, str(len(data))])
    buffer = io.StringIO(); csv.writer(buffer).writerows(rows)
    record = metadata / "RECORD"; record.write_text(buffer.getvalue())
    return package, metadata, rows


def test_intact_installed_source_is_read_only_and_scope_is_explicit(installed):
    package, metadata, _ = installed
    before = {str(p):p.read_bytes() for p in package.parent.rglob("*") if p.is_file()}
    result = verify_distribution(package, expected_version="1.0.0")
    assert result["decision"] == "pass"
    assert result["checked"] == 2
    assert result["execution_authenticity"] is False
    assert {str(p):p.read_bytes() for p in package.parent.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("mutation", ["change", "delete", "unlisted", "delete-row", "duplicate-row", "bad-path", "bad-hash"])
def test_record_and_runtime_corruption_blocks(installed, mutation):
    package, metadata, rows = installed
    if mutation == "change": (package / "cli.py").write_text("changed")
    elif mutation == "delete": (package / "cli.py").unlink()
    elif mutation == "unlisted": (package / "extra.py").write_text("extra")
    else:
        if mutation == "delete-row": rows.pop()
        elif mutation == "duplicate-row": rows.append(rows[0])
        elif mutation == "bad-path": rows[0][0] = "iot_ai/../outside"
        elif mutation == "bad-hash": rows[0][1] = "sha256=wrong"
        buffer=io.StringIO(); csv.writer(buffer).writerows(rows)
        (metadata / "RECORD").write_text(buffer.getvalue())
    assert verify_distribution(package)["decision"] == "block"


def test_retained_wheel_detects_record_and_source_rewrite(installed, tmp_path):
    package, metadata, rows = installed
    wheel = tmp_path / "fixture.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for path in package.iterdir(): archive.write(path, path.relative_to(package.parent).as_posix())
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (package / "cli.py").write_text("changed")
    for row in rows:
        data=(package.parent / row[0]).read_bytes()
        row[1]="sha256="+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        row[2]=str(len(data))
    buffer=io.StringIO(); csv.writer(buffer).writerows(rows)
    (metadata / "RECORD").write_text(buffer.getvalue())
    assert verify_distribution(package, wheel=wheel, wheel_sha256=digest)["decision"] == "block"


@pytest.mark.parametrize("mutation", ["missing", "ambiguous", "wrong-version", "shadow"])
def test_metadata_and_shadow_roots_cannot_qualify(installed, mutation):
    package, metadata, _ = installed
    if mutation == "missing": (metadata / "RECORD").unlink()
    elif mutation == "ambiguous": (package.parent / "iot_ai_coder_suite-2.0.0.dist-info").mkdir()
    elif mutation == "wrong-version": (metadata / "METADATA").write_text("Name: iot-ai-coder-suite\nVersion: 9.0.0\n")
    else:
        (package / "data" / "skills").mkdir(parents=True)
        (package.parent / "skills").mkdir()
    assert verify_distribution(package, expected_version="1.0.0")["decision"] == "block"


@pytest.mark.parametrize("files", [None, [], {}, ["invalid"]])
def test_incomplete_host_inventory_cannot_pass(tmp_path, files):
    with patch("iot_ai.installer._legacy_observations", return_value={}):
        install(tmp_path, ["codex"])
    path=install_state_path(tmp_path)
    state=json.loads(path.read_text()); state["files"]=files
    path.write_text(json.dumps(state))
    assert verify(tmp_path)["decision"] == "needs-work"


def test_recorded_runtime_takes_precedence_over_same_version_canonical_tree(installed, tmp_path):
    from iot_ai.installer import _runtime_check
    package, metadata, _ = installed
    canonical = tmp_path / "data/suite/1.0.0/venv/lib/python3.14/site-packages"
    shutil.copytree(package.parent, canonical)
    (package / "cli.py").write_text("drift in runtime used by wrappers")
    with patch("iot_ai.installer.data_root", return_value=tmp_path / "data"):
        result = _runtime_check(tmp_path, {"version":"1.0.0", "runtime_package_root":str(package)}, None)
    assert result["decision"] == "block"
    assert "runtime-drift:iot_ai/cli.py" in result["blockers"]


def test_authoritative_external_config_root_is_readable(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    external = tmp_path / "external-config"
    monkeypatch.delenv("IOT_AI_EXPLICIT_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(external))
    monkeypatch.setenv("APPDATA", str(external))
    with patch("pathlib.Path.home", return_value=home):
        with patch("iot_ai.installer._legacy_observations", return_value={}):
            install(home, ["codex"])
        assert install_state_path(home).is_relative_to(external)
        assert verify(home)["decision"] == "pass"
