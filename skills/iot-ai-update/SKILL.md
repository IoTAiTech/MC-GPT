---
name: iot-ai-update
description: Natural-language transactional install/update/rollback authority with package discovery, verification and fleet receipts.
id: iot-ai-update
version: 1.0.0
category: general
license: LicenseRef-PolyForm-Noncommercial-1.0.0
---
# iot-ai-update

A request such as “install the latest verified private delivery on the authorised hosts” must automatically:
1. identify whether the input is COMPLETE delivery or installable ALL-IN-ONE;
2. extract the correct Community/installer payload without treating COMPLETE as an update package;
3. verify SHA-256, manifest, archive safety and version lineage;
4. dry-run, apply, verify wrappers/skills, preserve state, and emit rollback/log paths;
5. report every host/user separately and mark unavailable hosts honestly;
6. record restart/session-reload requirements;
7. never expose credentials or private paths in public artifacts.

Do not ask the operator to discover package internals manually. Public GitHub publication remains separately Founder-gated.
