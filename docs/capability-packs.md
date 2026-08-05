<!--
Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 6.5.0-beta.2 | Date: 2026-08-05
SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
-->
# Capability packs

A capability pack is a deterministic `.zip` archive containing a secret-safe capability definition, protocol contracts, target materialisers, a manifest and checksums.

```bash
iot-ai knowledge pack --spec capability.json --output capability.iotaicap
iot-ai knowledge verify-pack capability.iotaicap
```

Required properties:

- no embedded credentials;
- safe paths, no symlinks and no duplicate members;
- canonical JSON and fixed archive timestamps;
- independent SHA-256 for every member;
- supported boundaries declared explicitly;
- no direct mutation of PMD/ProductX state;
- customer/private packs never enter public Git history.
