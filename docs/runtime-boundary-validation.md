# Runtime boundary validation

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 1.0.0
Status: candidate requiring independent review; not a production qualification

## One authority, current values

The agentic path reads the existing Suite task using a read-only connection.
It freezes task ID, revision, title, description, acceptance criteria and risk
class for the run, and compares current values before each graph step. A missing
record is not replaced with an invented revision. A concurrent edit requires
replanning; completion must not overwrite that edit. The final write checks the
same snapshot inside an immediate database transaction.

The native minimum-change evaluator recomputes the complete accepted assessment.
Before writer dispatch, the exact final-plan output is also matched against the
persisted `graph_nodes` hash for that graph. A caller-supplied Boolean, digest or
foreign graph record is insufficient. The hash is an integrity reference, not a
cryptographic signature and not a substitute for execution leases or Founder
approval. A process controlling the authority database is outside this check's
trust boundary.

The planning context digest is recorded by the context compiler, not the model.
It is distinct from the implementation node's context, which legitimately
contains a different set of dependencies. Changing the task or accepted strategy
requires a new review; merely retaining the same solution rung is insufficient.
No new PMD database, issuer, entitlement authority or settings subsystem is added.

## Effort is a constrained intersection

Provider support, entitlement ceilings and role minimums form an intersection.
An empty intersection blocks selection/dispatch; it never falls back to the
provider's broader capability set. `none` is an effort value, not missing data.
A requested value can legitimately differ from the applied value after a clamp.
Only applied values are compared across dispatch, adapter and response receipts;
missing required evidence still fails. Each fallback uses its own model policy.

An optional conditional graph skip is not a failed attempt. Actual repeated
failures continue to consume the configured failure budget.

## Visual evidence from an authorized host adapter

Model JSON is never a trusted visual receipt. `run_goal` accepts an optional
host-owned `visual_runner` object with two callables:

- `source_digest() -> str`: hash the actual authorized source artifact/tree.
- `capture(output_directory, viewports) -> {"browser_version": str}`: execute
  rendering and measurements and write the requested PNG and JSON files.

The adapter is registered by trusted host code, not discovered from a prompt or
third-party skill. Scripts are not auto-downloaded or auto-executed. No optional
browser package is added to the core runtime dependencies.

For each desktop/tablet/mobile viewport, capture writes `<viewport>.png` and
`<viewport>.json`. PNG is restricted to bounded non-interlaced 8-bit grayscale,
RGB, grayscale-alpha or RGBA. The verifier checks dimensions, CRCs, IDAT stream,
scanline size/filter bytes and the final trailer. Reads use the existing
root-constrained `open_secure`; hashes are computed from the same bytes checked.

A measurement report contains:

```json
{
  "viewport": {"width": 390, "height": 844},
  "overflow_count": 0,
  "clipping_count": 0,
  "accessibility": {
    "engine": "approved adapter tool and version",
    "checks_run": 7,
    "violations": []
  },
  "states": {"loading": "pass", "empty": "pass", "error": "pass"}
}
```

The host adapter must execute these measurements, not copy model assertions.
The receipt is issued only after capture, binds the run and source, and uses
opaque in-process authority. Model JSON cannot manufacture it. Receipt, image
and measurement bytes are re-read and verified before acceptance. A source
change during capture or before acceptance is rejected. Restarted processes
must recapture or use a separately reviewed external attestation integration;
serialized JSON alone does not restore authority.

`visual_acceptance_claim` covers the configured measurements only.
`visual_quality_proven` and `full_accessibility_certification` remain false:
automated checks do not prove design quality or complete WCAG compliance.
Without an authorized adapter, return `VISUAL_ACCEPTANCE_TOOL_UNAVAILABLE`.
A browser binary found on PATH is not authorization.

## Compatibility and verification

Existing false-positive tests were corrected, not disabled: incomplete accepted
plans and model-provided image fixtures now assert rejection. Separate positive
tests use a complete accepted assessment and an invoked synthetic host adapter.
Those fixtures are explicitly not live-provider or real-browser evidence.

A private browser harness additionally exercises real Chromium on a local,
synthetic HTML fixture, with external resource requests blocked. Its screenshots
and measurement reports are separate evidence, not production application proof.

Run the focused suite and full regression suite. Store JUnit, raw diagnostics
and screenshots outside public source. Then test the installed distribution
with the separately reviewed packaging correction, outside the source checkout.

Public source changes do not authorize PMD migration, customer deployments,
new paid provider trials, signing-key provisioning, releases or Founder closure.
