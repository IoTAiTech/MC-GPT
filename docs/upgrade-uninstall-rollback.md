# Upgrade, Uninstall and Rollback

```bash
iot-ai-mc-gpt package verify
iot-ai-mc-gpt package repair --hosts all --apply
iot-ai-mc-gpt package upgrade --hosts all --apply
iot-ai-mc-gpt package uninstall --apply
iot-ai-mc-gpt package rollback --apply
```

Managed files are hash checked. User files are backed up before replacement. Uninstall creates a durable recovery snapshot so rollback remains possible after active installation state is removed.

## Full installer uninstall rollback

After `installers/uninstall.sh` removes the private venv, use `installers/rollback-uninstall.sh` to recreate the runtime from bundled wheels and restore the latest sealed managed snapshot. On Windows use `Install-IotAiMcGpt.ps1 -Apply -RollbackUninstall`.
