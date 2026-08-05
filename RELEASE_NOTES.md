# IOT-AI Coder Suite 6.5.0-beta.2 — Enterprise Customer and Clean-Release Preview

This Community Developer Preview embeds MC-GPT `0.6.0-alpha.1` and prepares the first public GitHub release while keeping the paid Enterprise Customer Edition, vendor licence issuer material and customer evidence physically private.

## Added

- Private Enterprise Customer Add-on `1.0.0-alpha.2` with Ed25519-signed entitlements, signed revocation support, feature/limit/host/environment binding and offline verification.
- Authenticated PMD API adapter with HTTPS-only transport, no redirects, optional mTLS/certificate pinning, mutation idempotency, optimistic revision binding and bounded JSON responses.
- Secret-safe capability packs built from one typed operation contract and materialised as REST, MCP and OpenAPI 3.1 surfaces.
- Exact operator-facing application, audit, transaction and diagnostics log locations.
- Technical readiness documentation and release gates for EU AI Act, GDPR, CRA and NIS2-aligned customer controls.
- Source-dated quantitative and qualitative competitor comparison in the public README.
- Canonical MC-GPT brand assets.

## Changed

- Every official command-driven or prompt-driven installer uses the same clean transactional update path.
- Recognised older managed Suite/component versions and canonical packages are archived only after the replacement verifies; settings, databases, customer data, knowledge, evidence and unknown files are preserved.
- `iot-ai update` is the only normal-user update authority. Legacy updater names remain transitional aliases only.
- MC-GPT component builds now resolve and include their complete in-package Python dependency closure.
- Optional knowledge-export failures are written to structured audit logs instead of being silently discarded.

## Research adoption

The exact body of the referenced `marfinxx` X post was not independently retrievable. The associated design patterns were verified against the official AgentGem product and architecture documentation: redact secrets at capture, define an operation once, keep a deterministic neutral archive, and materialise that contract across multiple boundaries. IOT-AI independently implements those patterns and does not copy AgentGem code, branding, hosted marketplace or monetisation claims.

## Verification

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m pytest
python -W error -m pytest
python tools/static_security_audit.py .
python tools/public_boundary_check.py .
python tools/verify_repository.py . --check-sbom
python tools/benchmark_agent_runtime.py --iterations 3000
```

## Limitations

- Developer Preview only; not stable or production-ready.
- Live provider/model qualification requires customer accounts and may consume quota.
- Real Windows-device execution, GitHub-hosted Actions/attestation, Enterprise `cryptography 50.x` target qualification, PostgreSQL 18 forced-RLS/restore drills and deployment-specific legal review remain external gates.
- Technical controls are not a blanket legal certification, CE marking or conformity assessment for every customer deployment.
