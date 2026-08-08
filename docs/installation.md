<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->

# Installation

## Installation contract

Every applied installation is a clean, rollback-backed transaction. A clean install means:

1. verify the exact package SHA-256 and sealed manifest;
2. snapshot the current wrapper, managed host adapters, registry and qualification state;
3. install into a new isolated versioned virtual environment;
4. verify the Suite and selected host adapters;
5. archive recognised older active Suite/component code versions;
6. archive older canonical ALL-IN-ONE packages and checksum/signature sidecars;
7. preserve settings, databases, customer data, evidence, knowledge, unknown directories and non-managed files;
8. atomically activate the new wrapper;
9. emit an auditable receipt, rollback location and exact log locations.

The installer never uses `--break-system-packages`, never patches an installed version in place and never deletes unknown files.

## Linux ALL-IN-ONE

```bash
sha256sum -c IoT-AI-Tech-iot-ai-Coder-Suite-v6.7.0-beta.5-ALL-IN-ONE.zip.sha256
unzip IoT-AI-Tech-iot-ai-Coder-Suite-v6.7.0-beta.5-ALL-IN-ONE.zip -d iot-ai-suite
cd iot-ai-suite

./installers/install.sh \
  --home "$HOME" \
  --package-store "$HOME/ai-iot/Install/MC-GPT" \
  --package-archive "$HOME/ai-iot/Archive/MC-GPT" \
  --apply
```

Run without `--apply` to inspect the exact plan.

## Windows

Extract the same package and run in PowerShell:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\installers\Install-IotAiSuite.ps1 `
  -HomePath $HOME `
  -PackageStore "$HOME\ai-iot\Install\MC-GPT" `
  -PackageArchive "$HOME\ai-iot\Archive\MC-GPT" `
  -Apply
```

Real Windows on-device qualification remains an external release gate for this Developer Preview.

## Prompt-driven installation

A coder or agent must invoke the same transactional entry point. It must not copy files directly:

```text
Verify the package and exact SHA-256, run the official installer in dry-run,
show the clean-install and rollback plan, then run it with --apply only after
explicit approval. Preserve settings/databases/customer data and report the
application, audit, transaction and diagnostics log paths.
```

## Verification

```bash
iot-ai --version
iot-ai status --json
iot-ai status --logs
iot-ai package verify
iot-ai update status
```

## Exact log locations

Linux default:

```text
~/.local/state/iot-ai-tech/iot-ai-suite/v1/logs/iot-ai.jsonl
~/.local/state/iot-ai-tech/iot-ai-suite/v1/logs/audit.jsonl
~/.local/state/iot-ai-tech/iot-ai-suite/v1/logs/transactions/
~/.local/state/iot-ai-tech/iot-ai-suite/v1/logs/diagnostics/
```

`XDG_STATE_HOME` replaces `~/.local/state` when configured.

Windows default:

```text
%LOCALAPPDATA%\IoT-AI.Tech\IOT-AI-Suite\v1\logs\iot-ai.jsonl
%LOCALAPPDATA%\IoT-AI.Tech\IOT-AI-Suite\v1\logs\audit.jsonl
%LOCALAPPDATA%\IoT-AI.Tech\IOT-AI-Suite\v1\logs\transactions\
%LOCALAPPDATA%\IoT-AI.Tech\IOT-AI-Suite\v1\logs\diagnostics\
```

Every install, upgrade, repair, uninstall, rollback and error response reports these resolved paths.
