# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Run a disposable end-to-end package, installer, rollback and CLI smoke test."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def run(command: list[str], *, env: dict[str, str], cwd: Path | None = None, timeout: int = 300) -> dict[str, object]:
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    return {
        "argv": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def require(result: dict[str, object], label: str) -> None:
    if result["exit_code"] != 0:
        raise RuntimeError(f"{label} failed: {result['stderr'] or result['stdout']}")


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repository = Path(args.repository).resolve()
    package = Path(args.package).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    package_sha = hashlib.sha256(package.read_bytes()).hexdigest()
    evidence: dict[str, object] = {"schema": "iot-ai.blackbox-release.v2", "package": str(package), "package_sha256": package_sha, "steps": []}

    with tempfile.TemporaryDirectory(prefix="iot-ai-blackbox-") as temporary:
        base = Path(temporary)
        home = base / "home"
        home.mkdir()
        legacy_wrapper = home / ".local" / "bin" / "iot-ai"
        legacy_wrapper.parent.mkdir(parents=True)
        legacy_bytes = b"#!/usr/bin/env sh\necho iot-ai 6.0.0-beta.12\n"
        legacy_wrapper.write_bytes(legacy_bytes)
        legacy_wrapper.chmod(0o700)
        legacy_config = home / ".config" / "iot-ai" / "legacy.json"
        legacy_config.parent.mkdir(parents=True)
        legacy_config.write_text('{"legacy":"preserve"}\n', encoding="utf-8")
        legacy_config_sha = hashlib.sha256(legacy_config.read_bytes()).hexdigest()

        # Seed one recognised older active runtime, one canonical old package,
        # and unrelated/customer material. A clean install must archive only
        # the managed code/package and preserve everything else.
        state_root = home / ".local" / "share" / "iot-ai-tech" / "iot-ai-suite" / "v1"
        old_runtime = state_root / "suite" / "6.4.0-beta.1"
        (old_runtime / "venv" / "bin").mkdir(parents=True)
        (old_runtime / "venv" / "bin" / "iot-ai").write_text("#!/bin/sh\n", encoding="utf-8")
        (old_runtime / "PACKAGE_METADATA.json").write_text(
            json.dumps({
                "schema": "iot-ai.suite-package.v1",
                "product_id": "iot-ai-tech.iot-ai-coder-suite",
                "version": "6.4.0-beta.1",
            }),
            encoding="utf-8",
        )
        old_runtime_sha = hashlib.sha256((old_runtime / "PACKAGE_METADATA.json").read_bytes()).hexdigest()
        customer_state = state_root / "suite" / "customer-data" / "keep.txt"
        customer_state.parent.mkdir(parents=True)
        customer_state.write_text("preserve customer data\n", encoding="utf-8")
        customer_state_sha = hashlib.sha256(customer_state.read_bytes()).hexdigest()

        package_store = base / "package-store"
        package_archive = base / "package-archive"
        package_store.mkdir()
        old_package = package_store / "IoT-AI-Tech-iot-ai-Coder-Suite-v6.4.0-beta.1-ALL-IN-ONE.zip"
        old_package.write_bytes(b"old managed package")
        old_package_sha = hashlib.sha256(old_package.read_bytes()).hexdigest()
        old_package_sidecar = old_package.with_name(old_package.name + ".sha256")
        old_package_sidecar.write_text(f"{old_package_sha}  {old_package.name}\n", encoding="utf-8")
        unrelated_package_file = package_store / "customer-notes.zip"
        unrelated_package_file.write_bytes(b"unrelated customer archive")
        unrelated_package_sha = hashlib.sha256(unrelated_package_file.read_bytes()).hexdigest()

        env = dict(os.environ)
        env.pop("PYTHONHOME", None)
        env.pop("VIRTUAL_ENV", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(repository / "src")
        env["HOME"] = str(home)
        source_cli = ["python3", "-m", "iot_ai.cli", "--home", str(home)]

        install = run(
            source_cli + [
                "update", "apply",
                "--package", str(package),
                "--expected-sha256", package_sha,
                "--package-store", str(package_store),
                "--package-archive", str(package_archive),
                "--apply",
            ],
            env=env,
            timeout=600,
        )
        require(install, "official update apply")
        install_payload = json.loads(str(install["stdout"]))
        clean_result = install_payload.get("clean_install_result") or {}
        active_archived = (clean_result.get("active_versions") or {}).get("archived") or []
        package_archived = (clean_result.get("package_store") or {}).get("archived") or []
        if len(active_archived) != 1 or len(package_archived) != 2:
            raise RuntimeError("clean-install archive evidence is incomplete")
        if old_runtime.exists() or old_package.exists() or old_package_sidecar.exists():
            raise RuntimeError("old managed code/package remained active after clean install")
        if not package_archive.joinpath(old_package.name).is_file():
            raise RuntimeError("old canonical package was not archived")
        if not unrelated_package_file.is_file() or hashlib.sha256(unrelated_package_file.read_bytes()).hexdigest() != unrelated_package_sha:
            raise RuntimeError("unrelated package-store file was changed")
        if not customer_state.is_file() or hashlib.sha256(customer_state.read_bytes()).hexdigest() != customer_state_sha:
            raise RuntimeError("customer runtime data was changed")
        evidence["steps"].append({
            "name": "official-update-apply",
            "exit_code": install["exit_code"],
            "clean_active_versions_archived": len(active_archived),
            "clean_package_members_archived": len(package_archived),
            "unrelated_and_customer_data_preserved": True,
            "logs": install_payload.get("logs"),
        })

        cli = home / ".local" / "bin" / "iot-ai"
        runtime = home / ".local" / "share" / "iot-ai-tech" / "iot-ai-suite" / "v1" / "suite" / "6.6.0-beta.3"
        venv_cli = runtime / "venv" / "bin" / "iot-ai"
        if not cli.is_file() or not venv_cli.is_file():
            raise RuntimeError("installed wrapper/runtime missing")
        if "include-system-site-packages = false" not in (runtime / "venv" / "pyvenv.cfg").read_text(encoding="utf-8").lower():
            raise RuntimeError("isolated venv did not disable system site packages")

        smoke_results: dict[str, dict[str, object]] = {}
        for name, argv in {
            "version": [str(cli), "--version"],
            "help": [str(cli), "help"],
            "status": [str(cli), "status", "--json"],
            "settings": [str(cli), "settings", "show"],
            "package-verify": [str(cli), "package", "verify"],
            "update-status": [str(cli), "update", "status"],
            "graph-compile": [str(cli), "graph", "compile", "--goal", "Review the public release graph"],
            "compliance-status": [str(cli), "compliance", "status"],
            "compliance-release-gate": [str(cli), "compliance", "release-gate", "--root", str(repository), "--profile", "developer-preview"],
        }.items():
            result = run(argv, env={**env, "PYTHONPATH": ""}, timeout=240)
            require(result, name)
            smoke_results[name] = result
            evidence["steps"].append({"name": name, "exit_code": result["exit_code"], "stdout_sha256": hashlib.sha256(str(result["stdout"]).encode()).hexdigest()})

        status_payload = json.loads(str(smoke_results["status"]["stdout"]))
        if status_payload.get("schema") != "iot-ai.status.v4":
            raise RuntimeError("unified status schema missing")
        eu_status = status_payload.get("eu_ai_act") or {}
        if eu_status.get("global_compliance_claim_allowed") is not False or "score" in eu_status:
            raise RuntimeError("status exposed an unsafe blanket compliance claim or score")
        gate_payload = json.loads(str(smoke_results["compliance-release-gate"]["stdout"]))
        if gate_payload.get("decision") != "pass" or gate_payload.get("global_compliance_claim_allowed") is not False:
            raise RuntimeError("developer-preview EU AI Act release gate failed or over-claimed")

        blocked_screen = run(
            [str(cli), "compliance", "screen", "--text", "Build social scoring for citizens"],
            env={**env, "PYTHONPATH": ""},
        )
        require(blocked_screen, "Article 5 prohibited-practice screen")
        blocked_payload = json.loads(str(blocked_screen["stdout"]))
        if blocked_payload.get("decision") != "block" or not blocked_payload.get("findings"):
            raise RuntimeError("Article 5 screen did not fail closed")
        evidence["steps"].append({
            "name": "article-5-fail-closed",
            "exit_code": 0,
            "decision": blocked_payload.get("decision"),
            "finding_categories": [item.get("category") for item in blocked_payload.get("findings", [])],
        })

        marked_file = base / "ai-generated-public-interest.txt"
        marked_file.write_text("AI-assisted public-interest test content.\n", encoding="utf-8")
        mark_result = run(
            [
                str(cli), "compliance", "mark", str(marked_file),
                "--human-reviewed", "--editor", "IoT-AI.Tech", "--public-interest",
                "--provider", "deterministic-test-provider", "--model", "deterministic-test-model",
            ],
            env={**env, "PYTHONPATH": ""},
        )
        require(mark_result, "Article 50 content marking")
        verify_mark = run(
            [str(cli), "compliance", "verify", str(marked_file)],
            env={**env, "PYTHONPATH": ""},
        )
        require(verify_mark, "Article 50 content-mark verification")
        mark_payload = json.loads(str(mark_result["stdout"]))
        verify_payload = json.loads(str(verify_mark["stdout"]))
        if mark_payload.get("decision") != "pass" or verify_payload.get("decision") != "pass":
            raise RuntimeError("Article 50 marking round trip failed")
        if not (marked_file.with_name(marked_file.name + ".ai-provenance.json")).is_file():
            raise RuntimeError("Article 50 provenance sidecar missing")
        evidence["steps"].append({
            "name": "article-50-mark-and-verify",
            "exit_code": 0,
            "embedded": mark_payload.get("receipt", {}).get("embedded"),
            "transparency_profile": verify_payload.get("transparency_profile"),
        })
        if "6.6.0-beta.3" not in str(run([str(cli), "--version"], env={**env, "PYTHONPATH": ""})["stdout"]):
            raise RuntimeError("installed version mismatch")

        for host, root in {
            "claude": home / ".claude" / "skills",
            "codex": home / ".agents" / "skills",
            "gemini": home / ".gemini" / "commands",
            "grok": home / ".grok" / "skills",
        }.items():
            if not root.exists():
                raise RuntimeError(f"host adapter root missing: {host}")

        # The whole-Suite rollback and the component uninstall/rollback are
        # independent lifecycle scenarios.  They must not consume each
        # other's transaction state in one HOME.
        update_rollback = run([str(venv_cli), "--home", str(home), "update", "rollback", "--apply"], env={**env, "PYTHONPATH": ""})
        require(update_rollback, "update rollback")
        if legacy_wrapper.read_bytes() != legacy_bytes:
            raise RuntimeError("legacy wrapper was not restored byte-for-byte")
        if hashlib.sha256(legacy_config.read_bytes()).hexdigest() != legacy_config_sha:
            raise RuntimeError("legacy config changed")
        if runtime.exists():
            raise RuntimeError("candidate runtime remained after rollback")
        if not old_runtime.is_dir() or hashlib.sha256((old_runtime / "PACKAGE_METADATA.json").read_bytes()).hexdigest() != old_runtime_sha:
            raise RuntimeError("old active runtime was not restored by normal rollback")
        if not old_package.is_file() or hashlib.sha256(old_package.read_bytes()).hexdigest() != old_package_sha:
            raise RuntimeError("old canonical package was not restored by normal rollback")
        if not old_package_sidecar.is_file():
            raise RuntimeError("old package sidecar was not restored by normal rollback")
        if not customer_state.is_file() or hashlib.sha256(customer_state.read_bytes()).hexdigest() != customer_state_sha:
            raise RuntimeError("customer runtime data changed during rollback")
        evidence["steps"].append({
            "name": "normal-update-rollback",
            "exit_code": 0,
            "legacy_byte_restore": True,
            "old_managed_version_restored": True,
            "old_package_store_restored": True,
            "customer_data_preserved": True,
        })

        # Exercise component uninstall and its own rollback in a fresh HOME.
        home_component = base / "home-component"
        home_component.mkdir()
        component_env = {**env, "HOME": str(home_component), "PYTHONPATH": str(repository / "src")}
        component_cli = ["python3", "-m", "iot_ai.cli", "--home", str(home_component)]
        component_install = run(
            component_cli + ["update", "apply", "--package", str(package), "--expected-sha256", package_sha, "--apply"],
            env=component_env,
            timeout=600,
        )
        require(component_install, "component lifecycle install")
        component_runtime = home_component / ".local" / "share" / "iot-ai-tech" / "iot-ai-suite" / "v1" / "suite" / "6.6.0-beta.3"
        component_venv_cli = component_runtime / "venv" / "bin" / "iot-ai"
        uninstall = run(
            [str(component_venv_cli), "--home", str(home_component), "package", "uninstall", "--apply"],
            env={**component_env, "PYTHONPATH": ""},
        )
        require(uninstall, "component uninstall")
        adapter_rollback = run(
            [str(component_venv_cli), "--home", str(home_component), "package", "rollback", "--apply"],
            env={**component_env, "PYTHONPATH": ""},
        )
        require(adapter_rollback, "component uninstall rollback")
        component_verify = run(
            [str(component_venv_cli), "--home", str(home_component), "package", "verify"],
            env={**component_env, "PYTHONPATH": ""},
        )
        require(component_verify, "component rollback verification")
        evidence["steps"].append({"name": "component-uninstall-rollback", "exit_code": 0})

        extract = base / "extract"
        with zipfile.ZipFile(package) as archive:
            if any(not safe_name(name) for name in archive.namelist()):
                raise RuntimeError("unsafe archive name")
            archive.extractall(extract)
        home2 = base / "home-shell"
        home2.mkdir()
        shell_env = {**env, "HOME": str(home2), "PYTHONPATH": ""}
        dry = run(["sh", str(extract / "installers" / "install.sh"), "--home", str(home2)], env=shell_env, cwd=extract)
        require(dry, "shell installer dry run")
        applied = run(["sh", str(extract / "installers" / "install.sh"), "--home", str(home2), "--apply"], env=shell_env, cwd=extract, timeout=600)
        require(applied, "shell installer apply")
        shell_cli = home2 / ".local" / "bin" / "iot-ai"
        require(run([str(shell_cli), "--version"], env=shell_env), "shell-installed CLI")
        uninstalled = run(["sh", str(extract / "installers" / "uninstall.sh"), "--home", str(home2)], env=shell_env, cwd=extract, timeout=300)
        require(uninstalled, "shell uninstall")
        last_line = str(uninstalled["stdout"]).strip().splitlines()[-1]
        backup = json.loads(last_line)["backup"]
        restored = run(["sh", str(extract / "installers" / "rollback-uninstall.sh"), backup, "--home", str(home2)], env=shell_env, cwd=extract, timeout=300)
        require(restored, "shell uninstall rollback")
        require(run([str(shell_cli), "--version"], env=shell_env), "restored shell CLI")
        evidence["steps"].append({"name": "shell-install-uninstall-rollback", "exit_code": 0})

    evidence["decision"] = "pass"
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
