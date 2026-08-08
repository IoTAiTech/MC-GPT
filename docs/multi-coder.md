<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->
# Multi-Coder

Multi-Coder is automatically invoked at material planning, implementation, failure-diagnosis and final-review gates.

- all eligible configured coder families, every exact configured cloud-model seat, and exact Ollama local/cloud seats are attempted;
- unavailable seats receive honest outage receipts;
- R2+ requires at least two independent substantive seats;
- one implementer writes; reviewers remain read-only;
- deterministic tests and exact plan-digest reviews are authoritative;
- one green engine never becomes a Multi-Coder pass;
- repair rounds are bounded and Meeting is invoked when convergence fails.

Advanced manual command:

```bash
iot-ai multi-coder run --task-id <task-id> --providers auto

# explicit plan-only inspection
iot-ai multi-coder run --task-id <task-id> --providers auto --plan
```

The natural-language route is preferred because it also performs Task lifecycle, meetings, audit, checkpointing and final reporting.
