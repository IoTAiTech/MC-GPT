<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->
# Autonomous natural-language closed loop

MC-GPT composes Task, Meeting, Mesh and Multi-Coder into one persisted, conversation-aware lifecycle.

## Primary contract

```text
Task → IOT-AI Task → full hybrid Meeting → Multi-Coder hybrid
Task → Multi-Coder → failure/review Meeting → Task evidence and submit
Meeting → Multi-Coder → Task creation/update
```

The user describes an outcome. `IntentContract` resolves language, product, backend, task set, execution versus report-only intent, WIP, budgets, mandatory gates and report format. `ConversationState` stores only operator-visible IDs/checkpoints; no private chain-of-thought is persisted.

## Terminal state machine

```text
INTAKE → CONTEXT → BACKEND → DISCOVER → WIP WAVES
→ VALIDATE/OPTIMISE → PLANNING MEETING → MULTI-CODER
→ IMPLEMENT → TEST → FAILURE MEETING/REPAIR/RETEST
→ INDEPENDENT REVIEW → AUDIT → TECHNICAL SUBMIT
→ COMPLETE | AWAITING_FOUNDER | EXTERNAL/AUTHORITY/SAFETY/BUDGET/FAILED TERMINAL
```

`awaiting_founder` is a valid autonomous terminal state. Progress or status polling must never reopen it.

## Automatic Meeting triggers

Meeting is automatic for planning, test failure, provider/quorum failure, contradictory scorecards, stale verification, security/privacy P0/P1, repeated failures, backend mismatch, missing acceptance criteria, reviewer disagreement and final hard-judge review.

## Convergence

The loop stops only when:

- work is complete;
- technical work awaits Founder decision;
- authenticated external authority is unavailable;
- safety or legal classification blocks execution;
- identical failure repeats without new evidence;
- no-new-evidence or budget limit is reached;
- source ownership cannot be recovered safely.

Every stop records the exact next actor and recovery action.

## Reporting

The terminal bundle contains Tasks, Providers and Iterations sheets/tables plus JSON/Markdown/CSV/XLSX, evidence pointers, human decisions, blockers and a SHA-256 manifest.
