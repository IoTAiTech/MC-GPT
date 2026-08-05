# Security Policy

## Supported versions

Only the latest tagged Developer Preview receives security fixes until a stable support policy is published.

## Reporting

Use GitHub private vulnerability reporting. Do not disclose credentials, customer data or exploit details in public issues.

## Security defaults

- No secret values in settings or telemetry.
- Raw prompts/outputs disabled by default.
- Public release scans block private IPs, user-home paths, keys and tokens.
- Cloud egress passes through the local privacy gate.

## AI safety and compliance security controls

- Operational Article 5 matches fail closed before any provider or tool call.
- Defensive audits remain review-only and cannot authorize implementation.
- Compliance evidence is redacted, hash-chained, file-locked and stored with private permissions.
- A tampered evidence chain blocks further append operations.
- Provider/model identity must be proven by fresh requested/served receipts; a fallback provider cannot qualify another named adapter.
- Human-facing generated outputs must pass the applicable disclosure/marking gate before public export.

These controls are defense-in-depth. They do not replace deployment-specific legal classification, secure provider configuration or independent penetration testing.
