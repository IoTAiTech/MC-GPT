---
name: iot-ai
description: Natural-language, conversation-aware closed-loop engineering through Tasks, Meetings, Multi-Coder, tests, repair, audit and terminal reporting.
id: iot-ai
version: 1.0.0
category: general
license: LicenseRef-PolyForm-Noncommercial-1.0.0
---
# iot-ai

Use one natural-language goal. Do not make the operator translate normal language into internal flags.

Examples:

```text
/iot-ai finish all critical PMD tasks and keep working until each is complete, awaiting Founder, or externally blocked
/iot-ai prüfe die Fehler, repariere sie vollständig und liefere den Abschlussbericht
```

The runtime compiles the conversation into a versioned intent contract, resolves prior task references, selects the authoritative task backend, and runs this loop:

```text
Task intake → validation → full hybrid Meeting → Multi-Coder implementation
→ deterministic tests → failure Meeting → bounded repair → independent review
→ audit → re-plan when evidence is incomplete → terminal report
```

Rules:
- Execution verbs mean “continue to a truthful terminal state” by default.
- Use every eligible required coder/model seat at material planning, review and release gates; record outages honestly.
- One successful model is not Multi-Coder consensus.
- Never silently read PMD/PRCS databases; use the authenticated versioned PMD API adapter.
- Progress is telemetry, not completion authority.
- Never move audit-failing work to `awaiting_founder`.
- Founder Accept/Reject/Rework remains human-only.
- Stop only for a real human, safety, authority, external-service or bounded-budget gate.
- Always produce task, provider, iteration, evidence and blocker tables.
