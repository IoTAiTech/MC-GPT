# Runtime correction integration

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 1.1.0 | Date: 2026-09-05
Status: review candidate; not a production or deployment approval

## Concurrent source updates

PR23 was originally based on PR21 commit
`0ce651b32ad5e197db0ee51dc3e48e5db5659ca4`. During qualification,
PR21 advanced to `ef19edaacff4160bd930a849dfc68fe64fce6d6e`.
Four shared files required a deliberate resolution: the agentic caller,
runtime gates, visual acceptance and their corrective tests. Neither the
PR21 branch nor its history was rewritten.

## Resolution by behavior, not by author

- Retain the current-task snapshot and transaction-time comparison before
  completion. Do not fall back to a made-up revision or prior acceptance.
- Use the already persisted graph-node output digest for plan provenance.
  Do not introduce a second `accepted-plans` JSON authority, and do not accept
  a caller-provided object merely because it contains matching digest fields.
- Recompute the complete normalized assessment and compare the current task,
  revision, criteria, risk and planning context. Missing context remains a
  block; repeated pure validation is not evidence of paid-call idempotency.
- Retain the constrained effort intersection and typed failure when no
  permitted value exists. Requested and applied effort are distinct. Settings
  and the public schema accept the same `none` through `max` vocabulary as the
  resolver; exact provider support, entitlement ceilings and role minimums still
  constrain dispatch. Non-text role efforts are rejected rather than treated as
  missing values. An accepted setting never grants a commercial entitlement.
- Keep host-issued, run/source-bound visual evidence. A declared output
  directory, a PNG header, and fields named `runner_*` do not establish
  provenance. Verify complete bounded PNG data and measurements read from
  the same trusted capture. Validate measurement types, not Python's loose
  numeric equality or generic truthiness.
- Preserve the new workflow-trace intent as real calls through `run_goal`,
  the existing task/graph ledger and the actual brief/full report collector.
  A constructed dictionary is not a report-integration test.

The reconciled trace covers read-only inspection, one existing task reaching
`awaiting_founder`, ledger-backed plan evidence, pure binding replay without
provider dispatch, missing-context rejection, corrected effort evidence and
brief/full meeting identity parity. Existing runtime-boundary tests additionally
cover identity/revision/criteria drift, forged plans, strategy drift, empty
effort intersections, report tampering, symlinks, foreign runs and source drift.
No regression is waived because another branch reports green checks.

## Repeatable verification

`runtime-boundary-qualification.yml` runs with read-only repository permissions,
no provider secrets, pinned Actions, and diagnostics outside the source tree.
It records the exact checked Git commit/tree, test totals and raw JUnit digest.
Only the minimal receipt is uploaded: no source archive, raw tracebacks or
absolute environment paths are republished in its artifact. Git commit/tree
identity is the source reproduction reference. No workflow publishes a release,
changes a ref or grants a lease.

The private full-suite simulation can replace unavailable external DNS with an
immediate offline resolver. This is recorded separately from hosted CI and
cannot qualify a live provider. Local numeric/loopback resolution and explicit
DNS mocks used by security tests retain their ordinary behavior.

## Boundaries not expanded

PR22 owns packaging and must be tested in combination without creating a second
asset collector. PR19 owns benchmark and publication-boundary work. No live
PMD operation, private topology, provider benchmark, model-default change,
commercial license, signing key, Release or Founder decision is introduced.

An in-process visual handle is not remote attestation. Its trust boundary
excludes a compromised host process or authority database. The executed DOM
checks are a bounded smoke test, not full accessibility certification or proof
of design quality. Non-author review and verified final provenance remain
separate requirements after technical checks.

## Compound effort and dispatch evidence correction

The continuation audit found that applying a second runtime clamp after settings
resolution could broaden the effective set beyond the current entitlement. A
role minimum could also mask a stricter candidate minimum or risk floor. The
dispatch resolver now intersects every active constraint; it never substitutes
one floor for another. An empty set blocks before the delegate is called.
Malformed present constraints are rejected rather than treated as absent.

First-class runtime families without a reviewed built-in model catalog preserve
their declared effort capabilities, including an explicit empty list. Missing
catalog data does not prove an empty capability set. This preservation does not
grant readiness, credentials, a model identity, a license or execution authority.
Unknown providers remain blocked. No model identifier or default was changed.

The real provider executor now rejects a nominally successful result when
required effort stages are missing, invalid or disagree. It keeps dispatched
and reported effort separate, preserves a valid discrepancy for diagnosis, and
redacts malformed effort objects. The receipt uses the response's served-model
field rather than the pre-dispatch candidate. This proves adapter request and
response-metadata consistency, not a provider's internal reasoning computation.

Verification includes direct calls through the actual executor and tool router
with only the provider delegate simulated, an independent compound-policy set
oracle, and a full installed-distribution combination with the packaging work.
No live provider, license issuer, customer service or PMD store is contacted.
