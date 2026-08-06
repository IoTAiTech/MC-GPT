<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.6.0-beta.3 | Date: 2026-08-06 -->

# Goal-First Orchestration and Loop Engineering

The public `iot-ai <goal>` command compiles a user intent into a bounded, verifiable execution contract. The user defines the outcome and constraints; the application decides the next safe step from evidence.

## Goal contract

```yaml
outcome:
why:
context: []
constraints: []
non_goals: []
priorities: []
success_criteria: []
verification: []
stop_rules: []
clarification_policy:
autonomy_policy:
risk_class:
privacy_class:
digest:
```

A goal is rejected when it is too vague to verify. Clarification is requested only when a missing fact changes safety, authority, scope or the measurable definition of done.

## Loop types

| Mode | Trigger | End condition | IOT-AI use |
|---|---|---|---|
| Turn-based | user turn | user review | early exploration |
| Goal-based | explicit goal | verifier passes or budget stops | default engineering workflow |
| Time-based | schedule | one bounded cycle | maintenance and periodic review |
| Proactive | event | policy/goal resolution | Enterprise monitored operations only |

The Community Developer Preview exposes goal-based execution. Time-based and proactive loops require explicit deployment policy, audit, budgets and human escalation.

## Closed-loop execution

```text
Classify
→ retrieve validated knowledge
→ compile missing questions
→ assign specialist roles
→ select live-ready exact models
→ execute independent nodes in parallel
→ deterministic fan-in and contradiction matrix
→ frozen plan digest
→ required-role acceptance
→ authorized implementation
→ tests and independent audit
→ learn and checkpoint
```

The runtime stops when all hard gates pass, a required dependency is unavailable, two rounds add no material finding, or a safety/authorization/token/time boundary is reached.
