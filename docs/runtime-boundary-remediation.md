# Runtime boundary remediation

Status: tested source candidate; not a release or production qualification.

This correction extends the existing runtime after the settings/skill work and
installed-distribution correction. It introduces no second task authority,
settings store, model selector, skill router, or runtime dependency.

## Current task and accepted plan

The orchestrator reads the current Community task row by exact task and graph
identity before planning and before and after writer dispatch. A missing row,
changed source binding, changed revision, changed acceptance criteria, changed
goal, or changed risk class blocks the old plan. Current fields are never filled
from the plan being checked.

The accepted plan must match the output digest recorded by the orchestrator in
its managed `graph_nodes` store. Its native minimum-change assessment is
recomputed, including the full normalized strategy, all deltas, controls,
verification plan and assessment digest. A hash received in model content does
not create that authority. The planning context is reloaded from the managed
context manifest and rehashed independently; it is not the writer's different
context or merely the plan digest.

This protects against malformed or replayed provider outputs within the managed
runtime. It is not a cryptographic guarantee against an OS administrator who
controls that runtime store. It does not create a PMD lease, tenant permission,
external approval or Founder acceptance. Enterprise task authority remains in
its authenticated, versioned adapter.

## Effort policy

Effective effort is selected only from the intersection of exact provider
support, entitlement ceiling, role minimum and dispatch risk floor. An empty
intersection returns a typed block and no effective effort. There is no fallback
to the provider's unrestricted list. `none` and `max` are configurable values,
not permissions to exceed edition or provider limits.

Receipts preserve the configured and effective values separately. A documented
policy clamp is not itself a dispatch mismatch; an unexplained clamp, missing
request/response stage or differing dispatched effort is not consistent.

Optional graph nodes skipped because the first plan already passed do not count
as identical failures. Real repeated failures and required-node failures still
stop the graph.

## Optional real static visual check

A claimed browser executable, caller booleans and hash-looking strings cannot
approve a visual result. The optional native runner is called only for an
operator-selected local static source scope:

```sh
export IOT_AI_VISUAL_SOURCE_ROOT="${APP_SOURCE_ROOT}"
export IOT_AI_VISUAL_ENTRY="index.html"
```

Provision Playwright and a compatible Chromium outside the ordinary package
installation; MC-GPT does not download them automatically. `IOT_AI_CHROMIUM` can
name the approved browser executable. The default browser sandbox stays enabled.
`IOT_AI_VISUAL_ISOLATED_CONTAINER=1` is only for an independently isolated test
container that cannot start Chromium's nested sandbox, not a recommendation for
normal desktop or production use.

The process receives no provider secrets or arbitrary inherited Python import
path. It renders verified local bytes in an offline browser context, denies
unlisted HTTP resources and WebSockets, captures three real viewport PNGs and
records browser identity, source digest, layout, basic accessible structure and
explicit loading/empty/error interactions. The current static-preview mode uses
`set_content`: it does not navigate to a live application or validate its backend.
Resource routing is not proof of OS network namespace isolation.

For interactive-state checks, the preview supplies one button with
`data-qa-state="loading"` and one panel with `data-qa-panel="loading"`, and the
same pair for `empty` and `error`. Missing hooks are a failed/unproven check, not
an automatically invented pass.

The parent process retains the runner result anchor, reads only fixed artifact
filenames with the existing confined file reader, and rehashes each artifact.
It verifies complete bounded PNG structure, CRC, decompressed pixels and exact
viewport dimensions. Caller-supplied artifact paths and JSON receipts have no
acceptance authority. The three images must be distinct.

The result is explicitly limited to `static-preview-automated-v1`. It is not full
WCAG certification, pixel-perfect design approval, live application end-to-end
acceptance, or a production safety claim. Human design critique remains required.
If the approved browser runtime is unavailable, visual acceptance stays false.
A static synthetic fixture cannot prove a customer's website quality.

## Validation and handoff

The focused regression file exercises real orchestrator caller paths with
injected local providers, persisted task changes, managed plan receipts,
effort intersections, malformed image evidence and valid synthetic receipts.
It does not call paid providers. Separate optional browser execution tests actual
renders and controlled negative pages.

Existing tests that accepted a missing current context, bare approval booleans
or non-image bytes were strengthened. They were not skipped or marked expected
to fail. The unchanged private audit probes are retained separately for red/green
comparison.

Merge requires exact-head checks and independent review. After upstream changes,
repeat the full suite and installed-wheel resource checks outside the checkout.
Do not infer a complete PMD workflow, accepted Founder request, live provider
qualification or benchmark saving from this correction.
