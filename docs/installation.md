<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.8.0-beta.1 | Date: 2026-08-28 -->

# Installation, update and rollback

## Release identity

Do not confuse the current source tree with an existing download:

| Surface | Version | Status |
|---|---|---|
| Latest tagged Community download | Suite `6.7.0-beta.6` / MC-GPT `0.8.0-alpha.6` | Available as wheel, sdist and source ZIP |
| Current `main` source snapshot | Suite `6.8.0-beta.1` / MC-GPT `0.8.0-alpha.7` | Unreleased source candidate |
| Windows/macOS public qualification | — | Not currently claimed |
| Production/customer deployment | — | Not claimed |

The latest release is available at:

```text
https://github.com/IoTAiTech/MC-GPT/releases/tag/v6.7.0-beta.6
```

## Recommended isolated installation

### pipx

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install \
  https://github.com/IoTAiTech/MC-GPT/releases/download/v6.7.0-beta.6/iot_ai_coder_suite-6.7.0b6-py3-none-any.whl
```

Upgrade or reinstall the same preview explicitly:

```bash
pipx reinstall iot-ai-coder-suite
```

Remove it:

```bash
pipx uninstall iot-ai-coder-suite
```

### SHA-256-verifying community installer

The repository provides a plan-first Linux/macOS shell installer:

```bash
curl -fsSLo /tmp/install-mc-gpt.sh \
  https://raw.githubusercontent.com/IoTAiTech/MC-GPT/main/installers/install-community-preview.sh

sh /tmp/install-mc-gpt.sh          # plan only
sh /tmp/install-mc-gpt.sh --apply  # install after review
```

Default managed paths:

```text
~/.local/share/iot-ai-tech/mc-gpt-community/versions/<version>/
~/.local/share/iot-ai-tech/mc-gpt-community/current
~/.local/share/iot-ai-tech/mc-gpt-community/archive/
~/.local/bin/iot-ai*
~/.local/state/iot-ai-tech/mc-gpt-community/install/
```

The installer:

1. downloads the exact tagged wheel;
2. verifies SHA-256;
3. creates a new versioned virtual environment;
4. runs the installed CLI version check;
5. atomically switches the managed `current` link;
6. archives the previous managed active version;
7. relinks the public CLI wrappers;
8. prints the install receipt and log path.

Rollback the last managed switch:

```bash
sh /tmp/install-mc-gpt.sh --rollback
```

The script does not use `sudo`, does not modify system Python and does not delete unknown files.

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

The source tree may be ahead of the latest downloadable preview. Always record the exact Git commit SHA in test evidence.

## npm, npx and GitHub Packages

GitHub Releases and GitHub Packages are different systems. The current public, no-account installation path is the tagged Python wheel or verified curl installer.

Do not document an `npx` command as frictionless public installation until all of these are true:

- the package is published from the exact verified tag;
- its visibility and authentication requirements are documented;
- its default download artifact exists in the same release;
- the bootstrap has a live download-back test;
- repeat publication cannot overwrite immutable version identity.

## Provider CLIs

MC-GPT does not silently install or copy provider credentials. Configure Claude Code, Codex CLI, Gemini CLI, Grok CLI or Ollama through their own approved authentication paths.

After configuration:

```bash
iot-ai status
iot-ai meeting seat-plan --seats all-coders+ollama-clouds
```

A provider is counted only when a fresh readiness result and exact requested/served model evidence are available. One working route never qualifies another named provider.

## Windows and macOS

The public repository contains cross-platform code and lifecycle work, but the current public installation claim is intentionally limited. Do not treat a source-level Windows or macOS test as real on-device qualification.

Until an immutable release has current on-device install, update, rollback and provider evidence, use a disposable Linux environment for the public evaluation.

## Logs and diagnostics

For the verified community installer:

```text
~/.local/state/iot-ai-tech/mc-gpt-community/install/
```

For the Suite runtime, resolve the active locations with:

```bash
iot-ai status --logs
```

Public support reports must be sanitised. Never publish raw prompts, tokens, credentials, private IP addresses, internal hostnames, customer data or personal filesystem paths.

## Security and licensing

Read [`SECURITY.md`](../SECURITY.md), [`LICENSE`](../LICENSE), [`LICENSE_POLICY.json`](../LICENSE_POLICY.json) and [`EDITION_BOUNDARY.json`](../EDITION_BOUNDARY.json) before operational use.

The Community Developer Preview is source-available and noncommercial. Commercial evaluation, company-internal operation, production, paid services, hosting, resale and customer deployment require written terms from IoT-AI.Tech.
