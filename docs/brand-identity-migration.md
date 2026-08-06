# Brand and Legal Identity Migration

The canonical company and AI-system operator identity is **IoT-AI.Tech**.

The previously used `AI-IoT.Tech` display identity and `ai-iot-tech` state namespace are superseded. They remain referenced only by the migration implementation, its tests, this operator guide and the machine-readable exception register.

## Dry run

```bash
iot-ai settings migrate-brand
```

The command inventories and hashes legacy config, data and state roots. It blocks if the canonical destination already exists, because two active writers must never be merged implicitly.

## Apply

```bash
iot-ai settings migrate-brand --apply
```

The migration uses atomic same-filesystem renames, writes an audit receipt and preserves settings, databases, customer data and logs byte-for-byte.

## Rollback

```bash
iot-ai settings migrate-brand --rollback
```

Rollback succeeds only when the canonical state still matches the post-migration digest. Any intervening write blocks rollback rather than discarding new data.

## Current release rule

New releases, licences, Article 50 disclosures, provenance records and package names may emit only `IoT-AI.Tech` and `IoT-AI-Tech`. Every residual legacy string must be classified in `LEGACY_IDENTITY_ALLOWLIST.json`.
