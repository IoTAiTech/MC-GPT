<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->
# Federated Meeting Reporting

## Authority model

The Suite control database remains the only writable canonical state. Historical Meeting stores are optional operator-selected **read-only evidence sources**. Reporting does not migrate records, reconcile identities, mutate old databases, or access PMD/FCC/HID/ACE/customer databases directly.

## Report modes

- `brief` / `simple`: summary, participants, served-model evidence, status, decision, blockers and lifecycle anomalies.
- `full` / `complete`: full stored synthesis and contribution summaries; private/restricted only.
- `public`: brief-only, `D0` only, explicit meeting-ID allowlist only, path-free source manifest and mandatory redaction gate.

## Bundle contents

```text
MEETINGS_INDEX.json
MEETINGS_SUMMARY.csv
MEETINGS_REPORT.md
MEETINGS_REPORT.xlsx
MODEL_PARTICIPATION.csv
DECISIONS_AND_DISSENTS.csv
LIFECYCLE_ISSUES.csv
PROVENANCE.json
REPORT_MANIFEST.json or PUBLIC_REPORT_MANIFEST.json
MANIFEST.json
SHA256SUMS.txt
```

## Integrity and honesty controls

- Legacy SQLite databases are opened with `mode=ro` and `PRAGMA query_only=ON`.
- `PRAGMA integrity_check` must pass.
- Input paths must stay within explicit trusted roots; symlinks and filesystem-root trust are rejected.
- ANSI terminal escapes and NUL characters are removed from human-readable exports.
- Long-lived `running` sessions are reclassified as `stale` in the report only; source bytes remain unchanged.
- `user_approved=true` with a non-final status is reported as an approval/status conflict, not rewritten.
- Empty or missing `model_served` telemetry is reported as unverified and does not qualify a substantive seat.
- SHA-256 sidecars contain basenames only; private absolute paths are never written to public sidecars.

## Examples

```bash
export IOT_AI_ALLOWED_READ_ROOTS=/srv/approved-meeting-evidence

iot-ai meeting report \
  --legacy-db /srv/approved-meeting-evidence/root.sqlite3 \
  --legacy-db /srv/approved-meeting-evidence/iot.sqlite3 \
  --classification restricted --view full --format bundle \
  --stale-after-hours 24 --output meetings-private.zip
```

```bash
iot-ai meeting report \
  --classification public --view brief \
  --public-meeting-id meeting-approved-d0 \
  --format bundle --output meetings-public.zip
```

Public and private bundles are different products. Never publish a private/restricted bundle or the raw legacy databases.
