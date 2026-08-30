# OpenWiki Assessment for MC-GPT

Reviewed revision: `58a1358e1f7d5b883db7405f56dcbdac3c4d7fe5`  
Package version at the reviewed revision: `0.4.3`  
License: `MIT`  
Runtime requirement: `Node.js >=22`

## Product value

OpenWiki offers a durable repository-documentation lifecycle, page-level jobs, resumable run state, Grounded Claims bound to versioned source evidence, agent integrations, a linked Markdown knowledge graph, and a human visualizer. The strongest reusable pattern is not automatic prose generation. It is the explicit lifecycle:

```text
begin -> submit plan -> next page -> submit sparse claim decisions -> finish
```

Each material claim carries source evidence and can become stale when its evidence changes. This can reduce repeated repository discovery in MC-GPT meetings and improve the quality of the Minimum Necessary Change Gate.

## Recommended MC-GPT integration

OpenWiki should be an optional, read-only knowledge adapter. It must not become task authority, a PMD database client, an acceptance authority, or a mandatory runtime dependency.

```text
Task intake
-> retrieve relevant OpenWiki claims
-> recheck claims against current source
-> compile the MNCG contract
-> run Meeting and independent challenge
-> execute through one writer
-> verify deterministically
-> reconcile only affected documentation claims by pull request
```

## Safe pilot

- Pin commit `58a1358e1f7d5b883db7405f56dcbdac3c4d7fe5` or an immutable package digest.
- Use a disposable clone and a dedicated Node.js 22 environment.
- Set `OPENWIKI_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1`.
- Disable LangSmith and all connectors.
- Use public MC-GPT source and tests only.
- Do not provide PMD data, customer data, private repositories, private paths, credentials, or production logs.
- Preserve all non-managed `AGENTS.md` content byte-for-byte.
- Never auto-merge generated documentation.
- Run claim-staleness, source-reference, secret, privacy, and public-boundary checks before review.

## Risks

- Generated documentation remains fallible and must not outrank source and tests.
- The Node/LangChain dependency graph materially expands supply-chain surface.
- Telemetry is enabled unless explicitly disabled; CI events are also sent unless opted out.
- Connectors can ingest confidential sources and require separate approval.
- The example update workflow has content and pull-request write permissions.
- The visualizer normally loads public CDN assets and is not air-gap-ready without local vendoring.
- A generated wiki can become an accidental second source of truth.

## Decision

Adopt the durable job, Grounded Claim, sparse reconciliation, and evaluation patterns. Run OpenWiki as a benchmark arm and optional adapter pilot. Do not copy OpenWiki into the MC-GPT core, do not make it a task authority, and do not enable private connectors in the initial pilot.

`production_claim: false`
