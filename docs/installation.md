<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.8.0-beta.1 | Date: 2026-08-29 -->

# Installation and removal

## Release identity

Do not confuse the current source tree with an existing download:

| Surface | Version | Status |
|---|---|---|
| Latest tagged Community download | Suite `6.7.0-beta.6` / MC-GPT `0.8.0-alpha.6` | Available as wheel, sdist and source ZIP |
| Current `main` source snapshot | Suite `6.8.0-beta.1` / MC-GPT `0.8.0-alpha.7` | Unreleased source candidate |
| Windows/macOS public qualification | — | Not currently claimed |
| Production/customer deployment | — | Not claimed |

Latest tagged release:

```text
https://github.com/IoTAiTech/MC-GPT/releases/tag/v6.7.0-beta.6
```

## Recommended isolated installation

### pipx

```bash
python3 -m pip install --user pipx
python3 -m pipx install \
  https://github.com/IoTAiTech/MC-GPT/releases/download/v6.7.0-beta.6/iot_ai_coder_suite-6.7.0b6-py3-none-any.whl
```

Verify:

```bash
iot-ai --version
iot-ai help
iot-ai status
```

Inspect the current pipx environment when the executable is not yet in the shell path:

```bash
python3 -m pipx environment
```

Reinstall the same tagged preview:

```bash
python3 -m pipx reinstall iot-ai-coder-suite
```

Remove it:

```bash
python3 -m pipx uninstall iot-ai-coder-suite
```

### Ordinary virtual environment

```bash
python3 -m venv .mc-gpt-venv
.mc-gpt-venv/bin/python -m pip install --upgrade pip
.mc-gpt-venv/bin/python -m pip install \
  https://github.com/IoTAiTech/MC-GPT/releases/download/v6.7.0-beta.6/iot_ai_coder_suite-6.7.0b6-py3-none-any.whl

.mc-gpt-venv/bin/iot-ai --version
.mc-gpt-venv/bin/iot-ai help
.mc-gpt-venv/bin/iot-ai status
```

Remove that isolated environment only when it contains no unrelated data:

```bash
rm -rf .mc-gpt-venv
```

## Manual digest verification

Published wheel:

```text
iot_ai_coder_suite-6.7.0b6-py3-none-any.whl
```

Expected SHA-256:

```text
18a752eddcfa9336152cfe72e8ab320372e021121f89e68dbe086474f8ab2807
```

Cross-platform Python verification:

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib

path = Path("iot_ai_coder_suite-6.7.0b6-py3-none-any.whl")
expected = "18a752eddcfa9336152cfe72e8ab320372e021121f89e68dbe086474f8ab2807"
actual = hashlib.sha256(path.read_bytes()).hexdigest()
print(actual)
raise SystemExit(0 if actual == expected else 1)
PY
```

## Contributor installation from source

Use this path for development, not as evidence of the tagged release:

```bash
git clone https://github.com/IoTAiTech/MC-GPT.git
cd MC-GPT
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
```

The source tree may be ahead of the latest downloadable preview. Record the exact Git commit SHA in every test report.

## Why there is no custom curl updater in this evaluation

The growth/onboarding change intentionally does not introduce a second installation authority. A transactional installer must prove locking, activation rollback, managed-wrapper ownership, same-version recovery, absolute-path handling and platform lifecycle behaviour before it is offered publicly.

Until that qualification exists, use `pipx`, an ordinary virtual environment, or a source checkout. Do not copy commands from historical documentation that refer to a missing ALL-IN-ONE artifact.

## npm, npx and GitHub Packages

GitHub Releases and GitHub Packages are different systems. The current public, no-account installation path is the tagged Python wheel.

Do not present `npx` as a frictionless public install until:

- the package is published from the exact verified tag;
- visibility and authentication requirements are documented;
- its default artifact exists;
- download-back installation is tested;
- repeat publication cannot overwrite immutable version identity.

## Provider CLIs

MC-GPT does not install, copy or expose provider credentials. Configure Claude Code, Codex CLI, Gemini CLI, Grok CLI or Ollama through their own approved authentication paths.

After configuration:

```bash
iot-ai status
iot-ai meeting seat-plan --seats all-coders+ollama-clouds
```

A provider is counted only when a fresh readiness result and requested/served model evidence are available. One working route never qualifies another named provider.

## Windows and macOS

The public repository contains cross-platform work, but the current installation claim is intentionally Linux-first. Do not treat source-level Windows or macOS tests as on-device qualification.

## Logs, diagnostics and privacy

Resolve active Suite locations with:

```bash
iot-ai status --logs
```

Public reports must be sanitised. Never publish raw prompts, tokens, credentials, private IP addresses, internal hostnames, customer data or personal filesystem paths.

## Security and licensing

Read [`SECURITY.md`](../SECURITY.md), [`LICENSE`](../LICENSE), [`LICENSE_POLICY.json`](../LICENSE_POLICY.json) and [`EDITION_BOUNDARY.json`](../EDITION_BOUNDARY.json) before operational use.

The Community Developer Preview is source-available and noncommercial. Commercial evaluation, company-internal operation, production, paid services, hosting, resale and customer deployment require written terms from IoT-AI.Tech.
