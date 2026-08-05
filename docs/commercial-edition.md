<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.5.0-beta.2 | Date: 2026-08-05 -->

# Enterprise Edition

Enterprise is private and contract-bound. A signed Ed25519 entitlement binds customer, contract, features, limits, hosts/environments, validity, key ID and revocation state. Vendor private keys never ship. PMD integration occurs through authenticated APIs, not direct database or Excel access.

Enterprise Customer Add-on `1.0.0-alpha.2` additionally supports signed revocation metadata and a hardened PMD HTTPS boundary with optional mTLS/certificate pinning, mutation idempotency, optimistic revision checks and bounded JSON responses.
