<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.5.0-beta.2 | Date: 2026-08-05 -->

# Update and clean-version management

`iot-ai update` is the single public update authority. Legacy updater names are deprecated aliases or internal modules, not independent state machines.

## Status

```bash
iot-ai update status
iot-ai status --logs
```

The output separates:

- installed Suite/component versions;
- staged local candidate;
- published signed target;
- channel integrity and fetchability;
- rollback availability;
- log locations.

An empty URL/hash/signature is reported as `no_published_signed_target`, never as “no newer package”.

## Dry-run and apply

```bash
iot-ai update apply \
  --package ./IoT-AI-Tech-iot-ai-Coder-Suite-v6.5.0-beta.2-ALL-IN-ONE.zip \
  --expected-sha256 <exact-sha256> \
  --package-store "$HOME/ai-iot/Install/MC-GPT" \
  --package-archive "$HOME/ai-iot/Archive/MC-GPT"
```

Add `--apply` only after inspecting the plan.

The transaction installs side-by-side, verifies before activation, archives prior managed versions/packages, preserves non-code state and writes one rollback record.

## Rollback

```bash
iot-ai update rollback
iot-ai update rollback --apply
```

Normal rollback restores the prior wrapper, active runtime, managed adapters, registry, package-store files and qualification/update state without an emergency force flag.

## Repair

Host adapter repair uses the current sealed package and removes only obsolete files that were previously recorded as managed and whose digest still matches the managed state. Unknown or customer-owned files are preserved.

## Internal clean command

`iot-ai package clean` is an installer/internal operation. Normal users should use `iot-ai update apply`; direct cleanup is not a second updater.

## Logs

```text
Linux:  ~/.local/state/iot-ai-tech/iot-ai-suite/v1/logs/
Windows: %LOCALAPPDATA%\IoT-AI.Tech\IOT-AI-Suite\v1\logs\
```

Transaction receipts are under `transactions/`; sanitised diagnostic bundles are under `diagnostics/`.
