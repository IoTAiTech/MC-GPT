<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 1.0.0 | Date: 2026-08-29 -->

# Minimum Necessary Change Gate

## Purpose

The Minimum Necessary Change Gate makes **reuse-first reasoning an auditable engineering control**, not just a style instruction.

Before an implementation writer is allowed to add code, the planning output must identify the first sufficient rung in this order:

1. no change is needed;
2. reuse an existing helper, service, schema, component or pattern;
3. use the language standard library;
4. use a native platform, browser, operating-system, database or framework capability;
5. use an already-approved and installed dependency;
6. make the smallest local change;
7. only then add the minimum new code or dependency.

The gate runs **after** the task and affected flow are understood. It never permits a small but incorrectly scoped patch.

## Why MC-GPT needs this

MC-GPT already performs evidence-bound task validation, specialist planning, independent review, deterministic tests and Founder-gated completion. The missing control was a structured explanation of why new code is necessary.

The gate adds:

- a canonical assessment schema;
- objective repository/native/dependency evidence;
- explicit rejection of higher-cost alternatives;
- safety invariants that may not be optimized away;
- a predicted implementation budget;
- a post-change receipt comparing the approved budget with the actual diff;
- metrics for no-change, reuse, dependency avoidance and complexity drift.

## Safety invariants

The gate must never trade away:

- explicitly requested behaviour;
- validation at trust boundaries;
- controls preventing data loss;
- authentication, authorization and other security controls;
- privacy and tenant isolation;
- accessibility requirements;
- rollback and recovery;
- deterministic post-change verification;
- calibration or operational limits required by real hardware.

An invariant may be marked `not-applicable`, but only with a rationale.

## Assessment contract

Public schema:

```text
schemas/minimum-change-assessment-v1.schema.json
```

Core fields:

```yaml
schema: iot-ai.minimum-change-assessment.v1
decision: reuse-existing
selected_rung: 2
selected_strategy: Reuse the existing tenant-scoped receipt verifier.
requirement_understanding:
  problem: Duplicate verification logic creates inconsistent acceptance state.
  affected_flow:
    - task submission
    - independent verification
    - Founder review
  acceptance_criteria:
    - One authoritative verifier is used by all callers.
evidence:
  - kind: symbol
    reference: src/iot_ai/decision_receipts.py:verify_receipt
    finding: The existing verifier already implements the required binding checks.
alternatives:
  - rung: 1
    strategy: Do nothing
    decision: rejected
    reason: The duplicate path is currently reachable and inconsistent.
  - rung: 2
    strategy: Reuse existing verifier
    decision: selected
    reason: It is the first complete solution.
safety_invariants:
  security_controls:
    status: preserved
    rationale: Existing signature and replay checks remain authoritative.
implementation_budget:
  max_files_added: 0
  max_files_modified: 2
  max_added_lines: 25
  max_new_runtime_dependencies: 0
  required_tests:
    - Existing and duplicate callers produce the same decision.
confidence: 0.92
```

## Runtime behaviour

### Planning

The prompt compiler injects the gate before implementation. Planning outputs are expected to carry the assessment and explain every rejected lower rung before selecting a higher rung.

### Implementation

The writer is bound to:

- the approved strategy;
- the exact write scope;
- the predicted file/line/dependency budget;
- the required post-change tests.

A larger diff is not automatically wrong, but it is a **budget variance** and must return to review with evidence.

### Verification

`build_post_change_receipt()` compares the assessment with actual metrics:

```yaml
files_added
files_modified
added_lines
new_runtime_dependencies
post_change_tests_passed
safety_invariants_preserved
```

Possible decisions:

```text
pass
needs-review
block
```

Any failed deterministic test or lost safety invariant is a hard block.

## Metrics for PMD and ProductX

Recommended dimensions:

```text
product/dashboard
version
topic
risk class
selected rung
provider/model
writer/reviewer
time window
```

Recommended KPIs:

| Metric | Formula |
|---|---|
| No-change resolution rate | tasks resolved at rung 1 / assessed tasks |
| Reuse rate | tasks resolved at rungs 2–5 / assessed tasks |
| New-code rate | tasks resolved at rung 7 / assessed tasks |
| Dependency avoidance rate | assessments considering a new dependency but adding none / applicable assessments |
| Budget adherence | runs within approved file/LOC/dependency budget / completed runs |
| Complexity drift | actual added LOC − approved added-LOC budget |
| Post-change safety pass rate | runs preserving all applicable safety invariants / completed runs |
| Rework after minimality gate | Founder or reviewer rework decisions / decided runs |

These metrics can be ingested by the private PMD Observability plugin through signed receipts. The plugin must not open MC-GPT or PMD stores directly.

## Product use cases

### MC-GPT Community

- evaluate whether a local task needs code;
- reuse existing project functions and dependencies;
- reduce unnecessary files and dependencies;
- keep the decision and post-change receipt in local reports.

### MC-GPT Enterprise / PMD

- make the assessment part of the exact request revision;
- bind it to assignment, ACK, lease, run and reconciliation;
- show planned versus actual complexity in PMD reports;
- require re-review when implementation exceeds the approved budget;
- measure trends across 1d, 7d, 30d, 180d and 365d windows.

### Dashboard services

- prefer an existing dashboard capability or ProductX API before adding a second implementation;
- avoid cross-product database coupling;
- require visual acceptance whenever the selected solution changes a user-visible surface.

### Release engineering

- identify duplicated packaging, installer and workflow logic;
- reject a new installer when an existing qualified lifecycle already covers the requirement;
- report dependency and source growth relative to the previous immutable release.

## Relationship to Ponytail

This MC-GPT feature is an independent, governance-oriented implementation inspired by the public idea demonstrated by [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail): understand the real flow, then stop at the first sufficient YAGNI/reuse/stdlib/native/dependency/minimal-code option.

No Ponytail source code is copied into MC-GPT. Ponytail is MIT-licensed; its public copyright and licence remain with Dietrich Gebert. The upstream project’s published benchmark is treated as external evidence, not as an MC-GPT performance claim.

## Claim boundary

The deterministic semantic benchmark in this repository validates assessment and receipt behaviour. It does **not** prove the upstream 54%/22%/20%/27% reductions for MC-GPT.

MC-GPT may publish its own LOC, token, cost and duration claims only after a controlled paired benchmark using:

- the same tasks;
- the same provider/model versions;
- fresh isolated workspaces;
- multiple runs;
- actual Git diffs;
- post-change functional and adversarial tests;
- full raw receipts and limitations.

`production_claim: false`
