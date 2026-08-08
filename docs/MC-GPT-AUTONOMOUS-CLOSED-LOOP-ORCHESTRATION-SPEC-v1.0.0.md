# MC-GPT Autonomous Closed-Loop Orchestration Specification

**Version:** 1.0.0  
**Date:** 2026-08-08  
**Author:** Dr.-Ing. Babak Sorkhpour, with AI assistance  
**Product:** IoT-AI.Tech MC-GPT / IOT-AI Coder Suite  
**Target release line:** Suite 6.7.0-beta.5 / MC-GPT 0.8.0-alpha.5  
**Production claim:** false

## 1. Purpose

Transform MC-GPT from a collection of low-level commands into an outcome-oriented control plane that understands the operator's natural-language intent, preserves conversational context, selects the authoritative task backend, uses Meeting and Multi-Coder automatically, and continues through bounded repair and verification loops until the work reaches a truthful terminal state.

The operator should be able to say:

```text
Finish all critical PMD tasks. Use all available coders, hold a meeting whenever there is disagreement or a failure, repair and retest until each task is technically complete, then give me one final table.
```

The operator must not need to remember `--task-id`, `--quorum`, `--providers`, `--mode`, `--confirm-critical`, test-profile paths, or intermediate subcommands unless they explicitly request expert/manual control.

## 2. Non-negotiable outcomes

1. One natural-language request produces one persisted `IntentContract`.
2. One task ID has one authoritative backend.
3. A full-run command continues until every selected task is in a terminal state.
4. Meeting and Multi-Coder are internal engines, not separate manual chores.
5. Every material failure automatically triggers diagnosis, consultation and bounded replanning.
6. A zero-eligible run is `noop`, never `pass`.
7. Progress telemetry never changes an `awaiting_founder` task back to `active`.
8. Founder-only decisions remain human-only.
9. Provider outages are visible and never replaced with fake consensus.
10. Final output always contains a complete task table, provider table, iteration table, evidence pointers, blockers and human decisions.

## 3. User-facing command model

### 3.1 Primary UX

The primary surface remains:

```bash
iot-ai "<natural-language goal>"
```

Examples:

```bash
iot-ai "Finish all critical PMD tasks and keep working until they are technically complete."

iot-ai "Continue yesterday's work from the last checkpoint, use all available coders, and only stop for a real external blocker or my approval."

iot-ai "بررسی و اصلاح همه تسک‌های بحرانی PMD را تا پایان ادامه بده، در خطاها جلسه برگزار کن و در آخر یک جدول کامل بده."

iot-ai "Alle kritischen PMD-Aufgaben vollständig bearbeiten, bei Fehlern automatisch ein Multi-Coder-Meeting starten und am Ende einen vollständigen Bericht erstellen."
```

### 3.2 Optional expert escape hatch

Existing commands remain available for diagnostics and exact control, but normal workflows must not require them:

```text
iot-ai tasks ...
iot-ai meeting ...
iot-ai multi-coder ...
iot-ai mesh ...
```

### 3.3 Dry-run versus apply

Natural-language intent determines the default safely:

- review, analyse, inspect, show, report -> plan/read-only
- fix, implement, finish, complete, repair, apply -> execution requested
- destructive, production, release, publish, delete, migrate -> explicit confirmation gate

The compiled intent must show `execution_requested`, `destructive_action`, `human_gate`, and `reason` in the first receipt.

## 4. Conversation-aware intent compiler

Create `src/iot_ai/intent_router.py`.

### 4.1 Required schema

```yaml
schema: iot-ai.intent-contract.v1
intent_id:
raw_text:
language: fa|en|de|mixed
conversation_id:
resolved_references:
  previous_goal:
  selected_project:
  selected_task_ids: []
  pronouns_resolved: []
action: inspect|plan|execute|finish|continue|report|release
scope:
  product:
  backend:
  task_query:
  priorities: []
  task_ids: []
execution:
  requested: true|false
  until_terminal: true|false
  meeting_policy: automatic
  multi_coder_policy: mandatory-at-gates
  max_parallel_tasks:
  max_iterations_per_task:
  max_identical_failures:
  wall_clock_budget_seconds:
  token_budget:
verification:
  deterministic_tests: required
  independent_review: required
  final_audit: required
report:
  view: brief|full
  formats: [json, markdown, csv, xlsx]
assumptions: []
clarifications_required: []
human_gates: []
digest:
```

### 4.2 Conversation state

Persist a minimal state record, never private chain-of-thought:

```yaml
schema: iot-ai.conversation-state.v1
conversation_id:
active_goal_id:
last_intent_id:
active_product:
active_backend:
selected_task_ids: []
last_task_table_digest:
pending_human_decisions: []
external_blockers: []
last_checkpoint:
updated_at:
```

The router must resolve phrases such as:

```text
continue
finish the rest
do all of them
همه‌شان را ادامه بده
بقیه را تمام کن
همان تسک‌های دیروز
```

It may ask a question only when ambiguity changes authority, safety, product boundary, destructive scope, or the measurable definition of done.

## 5. Authoritative backend routing

Create `src/iot_ai/task_backends.py` with a strict protocol.

```python
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
class TaskBackend(Protocol):
    def discover(self, selector: IntentContract) -> list[TaskRecord]: ...
    def snapshot(self, task_id: str) -> TaskRecord: ...
    def validate(self, task_id: str) -> ValidationReceipt: ...
    def claim(self, task_id: str, assignment: Assignment) -> LeaseReceipt: ...
    def record_progress(self, task_id: str, progress: ProgressEvidence) -> Receipt: ...
    def submit_for_review(self, task_id: str, result: TechnicalResult) -> Receipt: ...
```

Rules:

```text
Suite task ID -> Suite backend
PMD-REQ-* / PRCS-* -> authenticated PMD/PRCS API adapter
No adapter -> EXTERNAL_BACKEND_UNAVAILABLE
No direct SQLite/PostgreSQL access to PMD
No copying PRCS rows into Suite as a silent fallback
No task may appear writable in two backends
```

Every task row in the final report must include `backend`, `authority_basis`, and `adapter_receipt`.

## 6. Closed-loop orchestrator

Create `src/iot_ai/autopilot.py`.

### 6.1 Canonical state machine

```text
INTAKE
-> RESOLVE_CONTEXT
-> SELECT_BACKEND
-> DISCOVER_TASKS
-> CLASSIFY_TASKS
-> SCHEDULE_BATCH
-> VALIDATE_AND_OPTIMISE
-> MEETING_PLAN
-> MULTI_CODER_PLAN
-> PLAN_DIGEST_GATE
-> CLAIM_AND_LEASE
-> IMPLEMENT
-> TEST
-> FAILURE_MEETING (conditional)
-> REPAIR (conditional)
-> RETEST
-> MULTI_CODER_FINAL_REVIEW
-> AUDIT
-> SUBMIT_TECHNICAL_RESULT
-> FOUNDER_GATE or COMPLETE
-> FINAL_REPORT
```

### 6.2 Required internal relationship

```text
Task -> IOT-AI Task -> Meeting (hybrid/full) -> Multi-Coder (hybrid)
Task -> Multi-Coder -> Meeting -> IOT-AI Task evidence/submit
Meeting -> Multi-Coder -> Task creation/update
```

These are not three competing entry points. They are one orchestrated lifecycle with shared correlation IDs and task IDs.

### 6.3 WIP control

A command such as `start all` must not convert all queued tasks into `in_progress`.

Default scheduler:

```yaml
critical_wip: 4
high_wip: 2
medium_wip: 1
low_wip: 1
max_total_active: 6
```

Remaining tasks stay queued. New tasks enter the next batch only after a current task reaches a terminal state or releases its lease.

### 6.4 Terminal states

```text
technical_complete_awaiting_founder
completed
externally_blocked
authority_blocked
safety_blocked
budget_exhausted
failed_terminal
cancelled
```

`awaiting_founder` is a valid terminal state for autonomous technical work. The loop must not reopen it or repeatedly call claim/solve/progress.

## 7. Automatic Meeting policy

Meeting is mandatory when any of the following occurs:

1. insufficient substantive provider quorum;
2. contradictory plans or scorecards;
3. deterministic test failure;
4. security, privacy or compliance P0/P1 finding;
5. stale or revision-mismatched verification;
6. repeated identical failure;
7. provider/model identity mismatch;
8. backend authority mismatch;
9. missing acceptance criteria;
10. final reviewer disagreement;
11. operator requested `deep`, `full`, `critical`, or `all coders`;
12. a task remains `needs-work` after one implementation attempt.

Meeting output must contain:

```yaml
meeting_id:
task_id:
round:
requested_seats: []
attempted_seats: []
substantive_seats: []
unsatisfied_seats: []
model_requested:
model_served:
opinions:
critiques:
synthesis:
plan_digest:
acceptance_matrix:
dissent:
hard_gates:
decision:
```

A meeting that does not meet quorum or same-digest acceptance remains `needs-work` or `blocked` and cannot authorize implementation.

## 8. Mandatory Multi-Coder policy

"Always use Multi-Coder" means:

- all eligible configured provider families are attempted at planning;
- at least two independent substantive seats are required for R2+;
- one designated implementer writes;
- all other substantive seats remain read-only reviewers;
- all available substantive seats participate in failure diagnosis;
- at least one non-implementer performs final review;
- every unavailable seat receives an outage receipt;
- one successful model never becomes a multi-coder pass.

Deterministic steps such as hashing, database reads, test execution, status transitions and report rendering do not require model calls.

## 9. Repair and convergence loop

### 9.1 Loop rule

```text
implement
-> deterministic tests
-> if failed: failure meeting
-> classify root cause
-> bounded repair
-> retest
-> independent final review
-> audit
```

### 9.2 Stop conditions

The loop continues until one terminal state is reached. It stops early only for:

- founder-only decision;
- missing authenticated external authority;
- prohibited/high-risk action without required classification;
- two identical failure fingerprints with no new evidence;
- two review rounds with no new material finding;
- exhausted token/wall-clock/budget;
- unrecoverable source ownership conflict;
- required provider quorum unavailable after the configured retry window.

Every stop must include the exact next responsible actor and one executable recovery action.

## 10. Task lifecycle corrections

### 10.1 Progress must preserve founder-gated state

`record_progress` must never force all tasks to `active`.

```text
awaiting_founder + progress heartbeat -> awaiting_founder
completed + progress -> block
cancelled/rejected + progress -> block
active + verified progress -> active
```

Progress requires:

```yaml
basis: manual-estimate|observed-steps|verified-criteria|deterministic-tests
evidence_ids: []
observed_steps:
total_steps:
confidence:
verified:
```

### 10.2 Zero eligible is noop

```json
{
  "decision": "noop",
  "reason": "eligible-count-zero",
  "eligible_count": 0,
  "provider_calls": 0,
  "mutation": false
}
```

### 10.3 Bulk operations

Add natural bulk selection; do not require one CLI invocation per task:

```bash
iot-ai tasks finish "all critical PMD tasks"
iot-ai tasks validate "all open PMD tasks"
iot-ai tasks report "everything waiting for founder"
```

The natural-language primary command should compile to the same internal APIs.

### 10.4 Lease secret handling

Lease tokens remain in memory or a protected secret handle. Redaction occurs only at the serialization/log boundary. A redactor must never replace the runtime token used by submit/release calls.

## 11. Acceptance-criteria and scorecard integrity

A scorecard is invalid if:

- criteria total is zero for executable work;
- any criterion is in more than one of pass/partial/fail;
- any criterion is outside `1..total`;
- `criteria_passed` differs from the pass set size;
- unassessed criteria exist at submit;
- verification does not bind current task revision and criteria digest;
- result summary is empty.

Submit requires:

```text
pass == total
partial == 0
fail == 0
unassessed == 0
trusted verification revision == current revision
criteria digest == verified criteria digest
current_result non-empty
```

## 12. Final reporting contract

Create `src/iot_ai/autopilot_reporting.py`.

Every full run must produce JSON, Markdown, CSV and XLSX.

### 12.1 Executive summary

```yaml
run_id:
intent_id:
conversation_id:
started_at:
finished_at:
decision:
selected_tasks:
technically_completed:
awaiting_founder:
externally_blocked:
failed_terminal:
provider_attempts:
substantive_contributions:
meetings:
repair_rounds:
tests_passed:
tests_failed:
```

### 12.2 Mandatory task table

| # | Task ID | Backend | Priority | Initial state | AC pass/total | Meeting | Multi-Coder | Tests | Repairs | Final state | Blocker / next actor | Evidence |
|---:|---|---|---|---|---:|---|---|---|---:|---|---|---|

### 12.3 Provider table

| Provider/seat | Requested model | Served model | Attempts | Substantive | Failures | Quarantined | Final role |
|---|---|---|---:|---:|---|---|---|

### 12.4 Iteration table

| Task ID | Iteration | Trigger | Meeting ID | Plan digest | Implementation | Test decision | Review decision | Continuation decision |
|---|---:|---|---|---|---|---|---|---|

### 12.5 Human-decision queue

| Task ID | Required human | Decision type | Technical status | Evidence digest | Safe choices |
|---|---|---|---|---|---|

The report must never end with generic text such as "say which option to run" when an autonomous safe continuation remains possible.

## 13. GitHub release gate

Before every package is called complete, the release orchestrator must check:

```text
repository main SHA
working tree / candidate tree
open PRs
stale release/fix/security branches
CI workflow latest run
Security workflow latest run
release workflow latest run
annotated tag target
GitHub Release existence
asset names, sizes and SHA-256
repository description, homepage and topics
README version and image references
public-boundary current tree
public-boundary full history
```

Decision rules:

```text
unknown CI status -> BLOCKED_UNVERIFIED, not PASS
failed CI/security -> no release
Tag without Release assets -> incomplete release
Release assets without matching manifest -> block
README/package/tag version mismatch -> block
```

Branch cleanup occurs only after:

- main contains the accepted commit;
- tag and GitHub Release exist;
- CI and Security are green;
- release assets verify;
- branch is merged;
- no open PR references it;
- explicit Founder confirmation is present.

## 14. Required skill and prompt changes

Update all managed skills:

```text
skills/iot-ai/SKILL.md
skills/iot-ai-help/SKILL.md
skills/iot-ai-status/SKILL.md
skills/iot-ai-update/SKILL.md
skills/iot-ai-tasks/SKILL.md
skills/iot-ai-meeting/SKILL.md
skills/iot-ai-multi-coder/SKILL.md
AGENTS.md managed block
src/iot_ai/data/skills.json
```

Every skill must state:

- natural-language-first UX;
- one authoritative backend;
- automatic Meeting escalation;
- mandatory Multi-Coder gates;
- bounded self-repair;
- founder-only terminal decisions;
- detailed final report;
- no fake pass/noop distinction;
- GitHub release verification requirements.

Update the prompt envelope to `iot-ai.prompt-envelope.v3` with:

```yaml
intent_contract:
conversation_context:
backend_authority:
task_snapshot:
acceptance_scorecard:
meeting_policy:
multi_coder_policy:
repair_policy:
continuation_policy:
release_policy:
final_report_contract:
```

## 15. Required tests

At least the following deterministic tests are required:

1. Persian natural-language finish intent.
2. English and German equivalent intents.
3. Pronoun resolution from previous conversation state.
4. Bulk PMD selector without individual `--task-id` calls.
5. `awaiting_founder` progress preserves status.
6. `solve-all` with zero eligible returns `noop`.
7. WIP limit prevents all queued tasks becoming active.
8. PMD prefix cannot use Suite backend.
9. Missing PMD API adapter blocks without direct DB fallback.
10. Runtime lease token remains valid while logs are redacted.
11. Provider outage triggers Meeting.
12. Failed tests trigger failure Meeting and repair.
13. Repeated identical failure stops safely.
14. Multi-Coder one-seat success is not quorum.
15. Scorecard overlap is blocked.
16. Stale verification is blocked.
17. Full task table appears in final report.
18. Founder-gated tasks are terminal and not reopened.
19. GitHub unknown status blocks package completion.
20. Branch cleanup refuses unmerged/open-PR branches.
21. Resume from checkpoint continues instead of restarting.
22. No new material finding convergence stops review churn.
23. Public report redacts private paths, IPs and tokens.
24. Exact model/provider receipt is present for each substantive contribution.
25. Full workflow simulation: Task -> Meeting -> Multi-Coder -> repair -> verify -> awaiting_founder.

## 16. Release decision

This specification does not authorize a production claim. A beta.5 package may be delivered only after full tests, clean installation, rollback, deterministic dual build, Git history scan, clone-back verification, and independent artifact verification pass on the exact candidate tree.
