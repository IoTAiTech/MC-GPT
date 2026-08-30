# OpenWiki assessment for MC-GPT and ProductX

**Author:** Dr.-Ing. Babak Sorkhpour, with AI assistance  
**Reviewed repository:** `langchain-ai/openwiki`  
**Reviewed revision:** `05aa586bd945afc1d5c1a1e8af15a4f3d1fae3fe`  
**Reviewed package version:** `0.4.3`  
**Licence:** MIT  
**Production claim:** false

## Executive decision

OpenWiki is highly relevant as a **documentation and evidence-maintenance pattern**, not as a replacement for MC-GPT Task authority, PMD, ProductX Core, or the existing Meeting and Multi-Coder runtime.

Recommended adoption:

```yaml
use_as_external_documentation_worker: pilot
copy_runtime_wholesale: no
replace_pmd_or_task_ledger: no
adopt_grounded_claim_pattern: yes
adopt_resumable_job_pattern: yes
adopt_visualizer_pattern: yes
adopt_okf_export_pattern: evaluate
adopt_telemetry_unchanged: no
```

## Source-derived capabilities

At the reviewed revision, OpenWiki describes and implements:

- a code or personal wiki owned as Markdown;
- coding-agent integrations for Codex, Claude Code, OpenCode, and Cursor;
- Grounded Claims tied to versioned repository evidence;
- a resumable repository lifecycle: `begin → submit_plan → next_page → submit_page → finish`;
- durable run state, ordered page jobs, per-page manifests, and partial progress;
- an interactive graph visualizer and static export;
- OKF v0.2 output;
- scheduled self-updates through CI;
- a broad model/provider and connector surface;
- a test pipeline covering typecheck, build, coverage, formatting, lint, CLI smoke, portability, and dependency audit.

## High-value patterns for MC-GPT

### 1. Grounded Claims → Evidence Claims Registry

MC-GPT reports currently carry facts such as:

- a capability exists;
- a test proves a behaviour;
- a model participated;
- a task is complete;
- a security boundary is preserved.

These should become versioned claims with exact evidence references, source/tree version, verification state, owner, and invalidation reason. When evidence changes, the claim becomes stale and PMD can open a re-verification work unit instead of trusting old prose.

### 2. Durable page jobs → Durable work-unit stages

OpenWiki persists page-level progress before advancing. MC-GPT should apply the same lifecycle discipline to:

```text
Task intake
Meeting plan
provider seat attempt
writer implementation
post-change tests
independent review
reconciliation
final report
```

A stage becomes complete only after its output, evidence, and manifest entry are durable. Retry resumes an existing stage rather than repeating paid provider work.

### 3. Per-page manifests → Per-work-unit evidence manifests

Every MC-GPT work unit should have a manifest that binds:

```text
request/task revision
accepted plan digest
writer worktree and base tree
post tree and diff digest
test profile and results
review receipt
provider/model identity
privacy classification
terminal state
```

### 4. Visualizer → PMD observability plugin

The visualizer concept maps directly to a graph of:

```text
Project → Request → Task → Work Unit → Meeting → Agent Seat → Worktree
→ Attempt → Test → Review → Evidence → Founder decision
```

The graph must read through authenticated APIs and signed projections. It must never open PMD or product databases directly.

### 5. Coding-agent integrations → Versioned host adapters

OpenWiki separates lifecycle ownership from the coding agent's native model and repository tools. MC-GPT can use the same separation:

- MC-GPT owns task authority, stage state, evidence, retries, and completion;
- Codex, Claude Code, Gemini, Grok, or Ollama owns provider-native execution;
- adapters expose versioned capabilities and receipts;
- no provider is called successful without requested/served identity and substantive evidence.

### 6. OKF → Portable knowledge export

OKF should be evaluated as an optional export from ProductX Knowledge Plane. It may improve portability between MC-GPT, documentation, RAG, and external tools, but must not become a second authoritative database.

### 7. Transparent telemetry pattern

OpenWiki's visible telemetry and opt-out pattern is preferable to covert tracking. MC-GPT should independently implement a stricter enterprise telemetry contract:

- off by default for Community unless explicitly enabled;
- contract-bound for Enterprise;
- no prompts, code, paths, credentials, customer IDs, or model outputs;
- purpose limitation, retention, deletion, region, and processor disclosure;
- local inspection/export of every event;
- one stable pseudonymous installation identifier only when legally justified.

## Risks and constraints

1. OpenWiki has a large Node dependency surface and a native SQLite dependency.
2. Node 22 is required.
3. Model and connector credentials create a larger privacy and supply-chain boundary.
4. Generated documentation can expose private paths, names, architecture, or customer facts without strict allowlists and ignore rules.
5. The visualizer uses public CDN resources unless independently bundled.
6. Connector-derived claims are not equivalent to repository-grounded claims.
7. OpenWiki telemetry should not be inherited without a separate GDPR/security assessment.
8. Generated Markdown is not authoritative product state.

## Recommended pilot

1. Run OpenWiki only against a disposable public MC-GPT checkout at the pinned revision.
2. Disable telemetry and all personal/external connectors.
3. Use repository source and tests only.
4. Deny Enterprise, evidence, customer, local-config, build, and secret paths through an explicit allowlist/ignore policy.
5. Generate into an isolated worktree.
6. Scan generated files and Claims before any PR.
7. Measure claim accuracy, stale-claim detection, private-data leakage, update churn, token/cost/time, and human evidence lookup time.
8. Do not auto-merge generated documentation.

## Integration roadmap

### Phase A — Read-only research

- qualify exact OpenWiki source and tests;
- generate no public wiki;
- document dependency, licence, telemetry, credential, and CDN boundaries.

### Phase B — Public disposable pilot

- generate a wiki for the public MC-GPT tree;
- compare every material claim to source and tests;
- run secret/private-path scans;
- human-review the result.

### Phase C — Native MC-GPT pattern adoption

Implement independent, Python-native versions of:

- evidence claims registry;
- stale-claim invalidation;
- durable stage manifests;
- resumable stage queue;
- graph projection.

### Phase D — Private ProductX/PMD plugin

- authenticated API-only ingestion;
- tenant/project/request scoping;
- signed projections;
- role-based access;
- retention and deletion controls;
- PMD KPI dashboard;
- no direct database access.

## Attribution and copying boundary

OpenWiki is MIT-licensed. This document analyses public behaviour and architectural patterns. No OpenWiki source is copied into MC-GPT by this assessment. Any future copied or substantially derived source must preserve the upstream copyright and permission notice.
