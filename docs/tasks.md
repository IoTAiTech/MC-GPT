<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->
# Tasks

The Task engine owns task identity, validation, work units, assignments, leases, progress evidence, audits and technical submit. The natural-language autopilot is the normal user-facing workflow.

Rules:

- bulk work is scheduled in bounded WIP waves;
- zero eligible is `noop`;
- progress is evidence telemetry and never execution authority;
- progress preserves `awaiting_founder`;
- submit requires non-empty result, current trusted verification, non-overlapping complete scorecard and passing audit;
- Founder final decision is human-only;
- Suite and PMD/PRCS authorities are never silently merged.

```bash
iot-ai "Finish all critical Suite tasks until technical completion."
```

PMD task IDs require the authenticated Enterprise API adapter; direct product DB access is forbidden.

Advanced direct execution is explicit by the verb itself:

```bash
iot-ai tasks run --all --mode hybrid
# no provider calls / no writes
iot-ai tasks run --all --mode hybrid --plan
```
