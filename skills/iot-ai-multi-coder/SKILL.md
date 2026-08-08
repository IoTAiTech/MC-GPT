---
name: iot-ai-multi-coder
description: Role-bound hybrid implementation with all eligible coders, deterministic tests, failure review, bounded repair and independent final judgment.
---
# iot-ai-multi-coder

Multi-Coder is mandatory at material implementation and verification gates.

Flow:

```text
independent plans → blind critique → synthesis → same-digest acceptance
→ one assigned writer → deterministic tests → failure reviewers → bounded repair
→ independent final reviewers → technical audit
```

Rules:
- Provider names never replace immutable specialist roles.
- Attempt all eligible required seats; do not silently truncate because of concurrency limits.
- Model identity requires `model_requested` and `model_served` evidence.
- Reviewers are read-only; one writer owns each write scope through assignment and lease.
- Repeated identical failure without new evidence terminates with a precise external/task-owner blocker.
- A green implementation from one model is not an independent review.
- Plan mode performs no writes; execution requires an explicit natural execution intent or advanced `--apply`.
