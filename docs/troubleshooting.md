<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.5.0-beta.2 | Date: 2026-08-05 -->

# Troubleshooting

- Installed but not live-ready: refresh provider authentication/readiness; do not trust `--version` alone.
- Empty seat: inspect the diagnostics bundle and mark the role unsatisfied.
- Quota: open a circuit breaker; do not burn quota on repeated probes.
- Update unavailable: distinguish staged candidate from published signed target.
- Rollback mismatch: stop and preserve the transaction diagnostics; do not force normal rollback.
