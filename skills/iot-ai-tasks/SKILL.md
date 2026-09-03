---
name: iot-ai-tasks
description: Natural-language task lifecycle and authoritative backend routing with validation, WIP control, evidence, audit and Founder handoff.
id: iot-ai-tasks
version: 1.0.0
category: general
license: LicenseRef-PolyForm-Noncommercial-1.0.0
---
# iot-ai-tasks

Prefer a natural request over parameter memorisation:

```text
/iot-ai-tasks finish all high and critical tasks
/iot-ai-tasks continue the remaining tasks from this conversation
```

Internal contract:
- Resolve exactly one authoritative backend per task (`suite` or authenticated `pmd-api`).
- Never merge Suite SQLite and PMD/PRCS state into a synthetic truth.
- Validate before claim or write; optimized/original/cancel decisions are recorded.
- Schedule bounded WIP waves and continue to later waves automatically.
- `authorize-execution` is a gate only; it never implements code.
- `run --mode hybrid --apply` is the explicit advanced equivalent of the natural closed loop.
- `solve-all` with zero eligible tasks returns `noop`, never a fake pass.
- Progress on `awaiting_founder` preserves that state.
- Submission requires disjoint, complete acceptance criteria plus trusted current-revision verification and nonempty results.
- Failed audit returns `needs-work`; only audit-approved technical work enters `awaiting_founder`.
