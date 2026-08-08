# CODER DIRECTIVE — MC-GPT Beta.5 Autonomous Closed Loop

**Version:** 1.0.0  
**Author:** Dr.-Ing. Babak Sorkhpour, with AI assistance  
**Target:** IOT-AI Suite 6.7.0-beta.5 / MC-GPT 0.8.0-alpha.5  
**Production claim:** false

## Authority

Read and apply:

1. `MC-GPT-AUTONOMOUS-CLOSED-LOOP-ORCHESTRATION-SPEC-v1.0.0.md`
2. Current repository `main` at the exact SHA discovered at execution time.
3. The latest PMD/Suite lifecycle, Meeting, Mesh, install and GitHub publication reports supplied by the Founder.

Do not use narrative reports as proof when runtime evidence is available.

## Mission

Implement a natural-language-first, conversation-aware, bounded autonomous workflow that takes a user goal to a truthful terminal state through Task, Meeting and Multi-Coder without forcing the user to manually discover and invoke every remaining step.

## Mandatory architecture

```text
Natural-language request
-> IntentContract
-> ConversationState
-> BackendAuthority
-> Task scheduler with WIP limits
-> Validation/optimisation
-> Meeting full/hybrid
-> Multi-Coder plan and same-digest gate
-> One authorized writer
-> Deterministic tests
-> Automatic failure meeting
-> Bounded repair/retest
-> Independent final review
-> Audit and technical submit
-> Founder gate or completion
-> Full task/provider/iteration report
```

## Implement

Create or update:

```text
src/iot_ai/intent_router.py
src/iot_ai/conversation_state.py
src/iot_ai/task_backends.py
src/iot_ai/autopilot.py
src/iot_ai/autopilot_reporting.py
src/iot_ai/cli.py
src/iot_ai/tasks.py
src/iot_ai/multicoder.py
src/iot_ai/meeting.py
src/iot_ai/control_flow.py
src/iot_ai/prompt_compiler.py
src/iot_ai/status.py
src/iot_ai/update_manager.py
src/iot_ai/data/skills.json
skills/iot-ai*/SKILL.md
AGENTS.md managed block
README.md
CHANGELOG.md
```

## Binding fixes from real reports

1. Bulk validation/finish must not require one `--task-id` invocation per task.
2. `awaiting_founder` progress must preserve `awaiting_founder`.
3. `eligible_count=0` must return `noop`, never `pass`.
4. `start all` must apply WIP limits rather than promoting the whole backlog.
5. Suite and PRCS must never be silently merged; PMD uses authenticated API only.
6. Lease-token redaction must occur only at output/log boundaries, never inside runtime control flow.
7. Founder validation skip must never be inferred automatically from a general execution request.
8. Missing or stale acceptance criteria/verification must block submit.
9. Provider failures must create outage receipts and trigger Meeting escalation.
10. One available model is not a Multi-Coder pass.
11. Stale `running` Meetings must be reclassified or resumed from checkpoint.
12. Root/iot Meeting stores may be federated read-only but never merged by direct write.
13. Final report must contain complete task, provider and iteration tables.
14. No terminal response may tell the Founder to manually choose another safe internal step when the orchestrator can continue itself.

## Natural-language commands to prove

```text
iot-ai "Finish all critical PMD tasks, use all available coders, hold a meeting on every failure, and continue until technical completion."

iot-ai "Continue the remaining tasks from the last checkpoint and give me one full final table."

iot-ai "همه تسک‌های بحرانی PMD را تا پایان انجام بده، در خطاها جلسه برگزار کن و از مالتی‌کدر استفاده کن."
```

## Safety and terminal rules

Do not auto-accept Founder decisions.
Do not bypass external authentication.
Do not access PMD databases directly.
Do not loop forever.
Do not convert provider outage into consensus.
Do not claim production or legal compliance.

Valid terminal results:

```text
COMPLETE
TECHNICAL_COMPLETE_AWAITING_FOUNDER
EXTERNALLY_BLOCKED
AUTHORITY_BLOCKED
SAFETY_BLOCKED
BUDGET_EXHAUSTED
FAILED_TERMINAL
CANCELLED
```

## GitHub checks before packaging

Check the live repository every time:

```text
https://github.com/IoTAiTech/MC-GPT/actions/workflows/ci.yml
https://github.com/IoTAiTech/MC-GPT/actions/workflows/security.yml
https://github.com/IoTAiTech/MC-GPT/releases
```

If status cannot be retrieved, report `BLOCKED_UNVERIFIED`; do not infer green from local tests.

Rebase/merge the latest accepted `main` changes before final build. Verify README version, release notes, infographic, Table of Contents, repository metadata and SEO topics.

## Required final report

Return a Markdown table with one row per selected task and these columns:

```text
Task ID | Backend | Priority | Initial State | AC Pass/Total | Meeting | Multi-Coder | Tests | Repairs | Final State | Blocker/Next Actor | Evidence
```

Also include provider participation and iteration tables, exact tests, exact changed files, package SHA-256, GitHub SHA, CI/Security/Release status, remaining external gates and branch-cleanup decision.

## Verification

Run full unit/pytest/warnings-as-errors, compileall, static security, public-boundary current tree and full history, repository verification, wheel clean-room, curl/npx/npm clean-room, tamper rejection, normal rollback, deterministic dual build, bare clone-back, manifest verification and independent archive verification.

Do not deliver a package until all applicable internal gates pass.
