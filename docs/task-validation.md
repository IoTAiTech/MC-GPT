<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.6.0-beta.3 | Date: 2026-08-06 -->

# Task Validation Before Claim or Execution

## Why this exists

A tester, operator or user can report a real problem, an incomplete symptom, a stale observation or a technically incorrect assumption. Claiming and implementing such a task immediately can waste provider quota, change the wrong component or create a false fix.

IOT-AI therefore places a user-controlled validation gate before `claim`, `run --execute`, `multi-coder run --task-id`, `solve-all --apply` and equivalent host execution flows.

```text
registered task or user goal
→ ask the user: validate, use as-is, or cancel
→ bind specialist roles before providers/models
→ inspect declared visual/content/document/log/code evidence
→ independent technical, UX, security, performance and compliance reviews
→ Claude, Codex, Gemini, Grok and at least one exact model-specific Ollama Cloud seat must each provide a substantive, receipt-bound contribution
→ synthesize one optimized task and advanced execution prompt
→ independent reviewers accept the same plan digest
→ user chooses optimized task, original task, or cancel
→ only then claim / lease / execution
```

## Default question

```text
Do you want all required coder families and eligible model-specific Ollama Cloud
seats to validate and optimise this task before execution?
```

The default is `validate`. No lease or write is issued while the question or validation result is awaiting a user decision.

## Command flow

### 1. Inspect the task and gate

```bash
iot-ai tasks show <task-id>
iot-ai tasks prepare --task-id <task-id> --action status
```

The status call is read-only and returns the validation policy, the exact user question and next commands.

### 2. Run validation with evidence

```bash
iot-ai tasks prepare \
  --task-id <task-id> \
  --action review \
  --context ./evidence/screenshot.png \
  --context ./evidence/runtime.log \
  --context ./evidence/project-document.md \
  --profile ultracode \
  --effort xhigh
```

The review binds specialist roles before providers, uses the application-owned graph runtime, and requires substantive participation from Claude, Codex, Gemini, Grok and at least one exact Ollama Cloud model seat. Missing, empty, unauthenticated or quota-blocked families remain unsatisfied; the user may cancel or explicitly accept the risk under the applicable policy. It produces:

- current technical validity and corrected problem statement;
- Why / What / How / When / Who;
- visual/content/document/log/code evidence status;
- security, privacy, EU AI Act, tenancy, performance and rollback findings;
- optimized title, description, acceptance criteria and execution prompt;
- KPI/SLA plus 10 use cases, 10 tests and 10 failure cases;
- exact provider/model/token/latency receipts;
- one frozen plan digest and required-role acceptance matrix.

### 3. Approve the optimized task

```bash
iot-ai tasks prepare \
  --task-id <task-id> \
  --action approve \
  --validation-id <validation-id> \
  --subject <user-or-founder-subject> \
  --reason "Reviewed and approved"
```

Other choices:

```bash
# reject the proposal and leave the original task unchanged
iot-ai tasks prepare --task-id <task-id> --action reject \
  --validation-id <validation-id> --subject <subject> --reason "..."

# explicitly use the original task as-is; high-risk bypass needs Founder confirmation
iot-ai tasks prepare --task-id <task-id> --action skip \
  --subject <subject> --reason "..." \
  --founder-confirm FOUNDER_SKIP_TASK_VALIDATION
```

Applying an approved proposal is atomic, increments the task revision and invalidates older validations.

## Claim behavior

Without a current approved validation:

```bash
iot-ai tasks claim --work-unit-id <wu> --owner codex --session-id <session>
```

returns the machine-readable validation question and creates no lease.

To use a low-risk task as originally written, record that choice before claiming:

```bash
iot-ai tasks prepare --task-id <task-id> --action skip \
  --subject <subject> \
  --reason "Trivial local documentation correction"
```

For R2–R4 or mandatory-policy tasks, bypass requires the explicit Founder confirmation token:

```bash
iot-ai tasks prepare --task-id <task-id> --action skip \
  --subject <founder-subject> \
  --reason "Accepted documented risk" \
  --founder-confirm FOUNDER_SKIP_TASK_VALIDATION
```

A waiver never converts unverified work into consensus; it remains visible in Audit and Excel. The subsequent claim still creates the normal Work Unit lease and does not grant Founder acceptance.

## PMD Enterprise mode

The licensed PMD adapter uses authenticated, audience-bound HTTPS API calls. It never opens PMD SQLite, JSONL or Excel files directly.

Canonical route family:

```text
GET  /api/v1/task-control/tasks/{task_id}/validations/latest
POST /api/v1/task-control/tasks/{task_id}/validations
POST /api/v1/task-control/tasks/{task_id}/validations/{validation_id}/decision
```

Every mutation requires an idempotency key and expected revision.

## Database and Excel

The canonical task database contains:

```text
task_validations
task_validation_reviews
```

The sealed workbook contains:

```text
Task Validations
Validation Reviews
```

The database remains authoritative. Excel is a redundant, human-readable projection and is never a concurrent write authority.

## Evidence and privacy

Evidence may include screenshots, project documents, logs, source files and test reports. The validation manifest stores hashes and sanitized excerpts. Secret-bearing text is blocked from provider prompts; private paths and infrastructure identifiers are not exported in public diagnostics. Image bytes remain local unless an approved visual adapter is explicitly configured.
