<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.5.0-beta.2 | Date: 2026-08-05 -->

# Unified Status

```bash
iot-ai status
iot-ai status --live --window 24h
iot-ai compliance status
```

Status separates executable discovery, authentication, quota, live readiness, requested/served model, effective effort and receipt freshness. It reports evidence-based scores for Meeting, Mesh, Multi-Coder, task execution and graph execution; hard gates override numeric scores.

The `eu_ai_act` section reports control states individually:

```text
not_assessed · not_applicable · applicable_missing · implemented_unverified
verified · expired · blocked
```

It never emits a global compliance percentage or certification claim. One literacy receipt or one model dossier cannot make the whole control green. Live-surface coverage, all required literacy roles, supplier coverage, post-market and incident processes require explicit evidence.
