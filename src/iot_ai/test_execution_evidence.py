# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-05
"""Host-selected verification commands, not model-authored test assertions.

This is an in-process evidence boundary, not a sandbox or remote attestation.
A deployment must isolate untrusted code from the host, credentials and ledger.
Only trusted host code configures commands, source coverage and this runner.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
import tempfile
import time
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .exec_pin import pin_executable, test_env
from .util import atomic_json, open_secure, utc_now
from .workspace import connect_read, connect_write, new_id, one

MAX_OUTPUT = 4 * 1024 * 1024
SHA = re.compile(r"[a-f0-9]{64}\Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def execution_binding(run_id: str, task: dict[str, Any]) -> dict[str, Any]:
    revision = task.get("revision")
    if (type(revision) is not int or revision < 0 or not isinstance(run_id, str)
        or not run_id or len(run_id) > 200 or not isinstance(task.get("id"), str)
        or not task["id"] or not isinstance(task.get("acceptance_criteria"), str)):
        raise ValueError("test-execution-binding-invalid")
    return {"run_id": run_id, "task_id": task["id"], "task_revision": revision,
            "acceptance_sha256": hashlib.sha256(task["acceptance_criteria"].encode()).hexdigest()}


def source_digest(root: Path, relative_files: Sequence[str]) -> str:
    """Hash an explicit host-reviewed source inventory, never a model file list.

    Coverage is exactly this inventory. Excluded dependencies are not attested.
    The caller must include all verification-relevant source and test inputs.
    """
    if (not isinstance(relative_files, (list, tuple)) or not relative_files
        or any(type(name) is not str for name in relative_files)
        or len(relative_files) > 10000 or len(set(relative_files)) != len(relative_files)):
        raise ValueError("test-source-inventory-invalid")
    rows = []
    for name in sorted(relative_files):
        if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name or ":" in name:
            raise ValueError("test-source-path-invalid")
        with open_secure(root / name, allowed_roots=[root], max_bytes=16 * 1024 * 1024) as stream:
            data = stream.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise ValueError("test-source-file-too-large")
        rows.append([name, hashlib.sha256(data).hexdigest()])
    return _digest(rows)


@dataclass(frozen=True)
class CheckCommand:
    argv: tuple[str, ...]
    timeout_seconds: int = 120


@dataclass(frozen=True, eq=False)
class TestExecutionHandle:
    root: Path
    receipt_sha256: str


_ISSUED: weakref.WeakKeyDictionary[TestExecutionHandle, tuple[Path, str]] = weakref.WeakKeyDictionary()


def _read(root: Path, name: str) -> bytes:
    with open_secure(root / name, allowed_roots=[root], max_bytes=MAX_OUTPUT) as stream:
        data = stream.read(MAX_OUTPUT + 1)
    if len(data) > MAX_OUTPUT:
        raise ValueError("test-evidence-too-large")
    return data


def _stop(process: subprocess.Popen) -> None:
    if os.name == "posix":
        # The session was created by this runner. Never signal another run.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()
    process.wait(timeout=10)


class HostTestRunner:
    """Prepare immutable, host-selected commands; construction does not run them."""

    def __init__(self, *, cwd: Path, commands: Sequence[CheckCommand],
                 current_source_digest: Callable[[], str]):
        self.cwd = Path(cwd).resolve(strict=True)
        if not self.cwd.is_dir() or self.cwd == self.cwd.parent:
            raise ValueError("test-working-directory-invalid")
        if not commands or len(commands) > 32 or not callable(current_source_digest):
            raise ValueError("test-profile-invalid")
        prepared = []
        for command in commands:
            if (not isinstance(command, CheckCommand) or not isinstance(command.argv, tuple)
                or not command.argv or len(command.argv) > 128
                or any(type(arg) is not str or not arg or "\0" in arg or len(arg) > 8192 for arg in command.argv)
                or type(command.timeout_seconds) is not int or not 1 <= command.timeout_seconds <= 900):
                raise ValueError("test-command-invalid")
            executable = pin_executable(command.argv[0])
            prepared.append((tuple([executable["path"], *command.argv[1:]]), executable["sha256"], command.timeout_seconds))
        self._commands = tuple(prepared)
        self.current_source_digest = current_source_digest
        self.profile_sha256 = _digest(self._commands)

    def run(self, *, user_home: Path, binding: dict[str, Any], evidence_root: Path) -> TestExecutionHandle:
        connection = connect_read(user_home)
        try:
            task = one(connection, "SELECT id,revision,acceptance_criteria FROM tasks WHERE id=?", (binding.get("task_id"),)) if connection else None
            if not task or _digest(execution_binding(binding.get("run_id"), task)) != _digest(binding):
                raise ValueError("test-task-authority-changed")
        finally:
            if connection is not None:
                connection.close()
        before = self.current_source_digest()
        if type(before) is not str or not SHA.fullmatch(before):
            raise ValueError("test-source-digest-invalid")
        evidence_root.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="test-run-", dir=evidence_root))
        os.chmod(root, 0o700)
        environment = test_env()
        sandbox_home = root / "process-home"
        sandbox_home.mkdir(mode=0o700)
        environment.update({"HOME": str(sandbox_home), "USERPROFILE": str(sandbox_home),
            "XDG_CONFIG_HOME": str(sandbox_home / "config"), "XDG_DATA_HOME": str(sandbox_home / "data"),
            "XDG_CACHE_HOME": str(sandbox_home / "cache"), "TMPDIR": str(sandbox_home),
            "TMP": str(sandbox_home), "TEMP": str(sandbox_home), "PYTHONNOUSERSITE": "1"})
        rows = []
        for index, (argv, expected_executable, timeout) in enumerate(self._commands):
            if pin_executable(argv[0])["sha256"] != expected_executable:
                raise ValueError("test-executable-changed")
            filename = f"check-{index + 1:02d}.log"
            started = time.monotonic()
            failure = None
            with (root / filename).open("xb") as output:
                os.chmod(root / filename, 0o600)
                process = subprocess.Popen(list(argv), cwd=self.cwd, stdout=output, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, env=environment, shell=False, start_new_session=os.name == "posix")
                try:
                    while process.poll() is None:
                        if time.monotonic() - started > timeout:
                            failure = "timeout"
                            break
                        if os.fstat(output.fileno()).st_size > MAX_OUTPUT:
                            failure = "output-limit"
                            break
                        time.sleep(0.01)
                    if failure:
                        _stop(process)
                    else:
                        process.wait(timeout=10)
                        if os.name == "posix":
                            _stop(process)  # Remove ordinary descendants still in our session.
                finally:
                    if process.poll() is None:
                        _stop(process)
                code = process.returncode
            # Do not infer test counts from stdout, which a test can print itself.
            if (root / filename).stat().st_size > MAX_OUTPUT:
                raise ValueError("test-output-limit")
            body = _read(root, filename)
            rows.append({"id": new_id("test"), "tier": f"host-check-{index + 1:02d}",
                "command_sha256": _digest(argv), "executable_sha256": expected_executable,
                "exit_code": code, "decision": "pass" if code == 0 and failure is None else "fail",
                "failure_class": failure, "duration_ms": int((time.monotonic() - started) * 1000),
                "output": filename, "output_sha256": hashlib.sha256(body).hexdigest()})
        if self.current_source_digest() != before:
            raise ValueError("test-source-changed-during-execution")
        receipt = {"schema": "iot-ai.host-test-execution.v1", "binding": binding,
            "source_sha256": before, "profile_sha256": self.profile_sha256, "checks": rows,
            "count_unit": "executed-host-commands-not-framework-testcases", "created_at": utc_now()}
        atomic_json(root / "receipt.json", receipt, mode=0o600)
        digest = hashlib.sha256(_read(root, "receipt.json")).hexdigest()
        connection = connect_write(user_home)
        try:
            connection.execute("BEGIN IMMEDIATE")
            task = one(connection, "SELECT id,revision,acceptance_criteria FROM tasks WHERE id=?", (binding["task_id"],))
            if not task or _digest(execution_binding(binding["run_id"], task)) != _digest(binding):
                raise ValueError("test-task-authority-changed")
            for row, (argv, _, _) in zip(rows, self._commands):
                connection.execute("""INSERT INTO test_results(
                    id,task_id,work_unit_id,run_id,tier,argv_json,command_sha256,exit_code,
                    passed,failed,skipped,duration_ms,output_path,output_sha256,decision,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    row["id"], binding["task_id"], None, binding["run_id"], row["tier"], json.dumps(argv),
                    row["command_sha256"], row["exit_code"], int(row["decision"] == "pass"),
                    int(row["decision"] != "pass"), 0, row["duration_ms"], str(root / row["output"]),
                    row["output_sha256"], row["decision"], receipt["created_at"]))
            connection.commit()
        finally:
            connection.close()
        handle = TestExecutionHandle(root, digest)
        _ISSUED[handle] = (root, digest)
        return handle


def verify_test_execution(handle: Any, *, user_home: Path, binding: dict[str, Any],
                          current_source_sha256: str, profile_sha256: str) -> dict[str, Any]:
    """Re-read owned evidence and existing ledger rows. A dict cannot grant trust."""
    blocked = {"decision": "block", "failure_class": "test-execution-evidence-invalid",
               "test_results": [], "hard_gates": {"host_checks_pass": False}, "evidence_refs": []}
    if not isinstance(handle, TestExecutionHandle) or _ISSUED.get(handle) != (handle.root, handle.receipt_sha256):
        return blocked
    connection = None
    try:
        data = _read(handle.root, "receipt.json")
        if hashlib.sha256(data).hexdigest() != handle.receipt_sha256:
            return blocked
        receipt = json.loads(data)
        if receipt["binding"] != binding or receipt["source_sha256"] != current_source_sha256 or receipt["profile_sha256"] != profile_sha256:
            return blocked
        connection = connect_read(user_home)
        if connection is None:
            return blocked
        task = one(connection, "SELECT id,revision,acceptance_criteria FROM tasks WHERE id=?", (binding["task_id"],))
        if not task or _digest(execution_binding(binding["run_id"], task)) != _digest(binding):
            return blocked
        rows = receipt["checks"]
        if not rows:
            return blocked
        for row in rows:
            observed = one(connection, "SELECT task_id,run_id,tier,command_sha256,exit_code,output_sha256,decision FROM test_results WHERE id=?", (row["id"],))
            expected = {"task_id": binding["task_id"], "run_id": binding["run_id"],
                        **{key: row[key] for key in ("tier", "command_sha256", "exit_code", "output_sha256", "decision")}}
            if observed != expected or hashlib.sha256(_read(handle.root, row["output"])).hexdigest() != row["output_sha256"]:
                return blocked
        passed = all(row["exit_code"] == 0 and row["decision"] == "pass" and row["failure_class"] is None for row in rows)
        return {"decision": "pass" if passed else "block", "failure_class": None if passed else "host-test-command-failed",
            "test_results": [{key: row[key] for key in ("id", "tier", "exit_code", "decision", "duration_ms", "output_sha256")} for row in rows],
            "hard_gates": {"host_checks_present": True, "host_checks_pass": passed},
            "evidence_refs": [handle.receipt_sha256], "source_sha256": current_source_sha256,
            "profile_sha256": profile_sha256, "count_unit": receipt["count_unit"],
            "remote_attestation": False, "production_claim": False}
    except (ValueError, TypeError, KeyError, OSError, RecursionError):
        return blocked
    finally:
        if connection is not None:
            connection.close()
