---
name: iot-ai-update
description: Use the single transactional update authority for plan, apply and rollback.
---
# iot-ai-update

Use the installed `iot-ai` CLI as the only public control surface.

Example: `/iot-ai-update status`

Rules:
- Read `iot-ai help` before using a flag.
- Preserve immutable role contracts, task authority, evidence, privacy and public/private boundaries.
- Never count an empty, meta-only, unauthenticated, quota-blocked or model-unverified seat as a contribution.
- Never claim a provider/model without a fresh requested/served receipt.
