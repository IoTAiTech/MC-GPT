<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.6.0-beta.3 | Date: 2026-08-06 -->

# Architecture

## Public control surface

```text
iot-ai            natural-language agentic execution
iot-ai-help       current, version-bound help
iot-ai-status     health, versions, models, efforts and workflow scores
iot-ai-settings   portable policy and provider controls
iot-ai-update     the single transactional update authority
```

Meeting, Mesh, Multi-Coder, tasks, graph, knowledge and diagnostics remain advanced subcommands or internal engines behind `iot-ai`.

There is one user-facing coder runtime. Benchmark treatments A–F are experimental arms used only by the benchmark runner. They are not six products, services, commands, or installable modules.

```text
coder command
→ intake and normalization
→ reuse / YAGNI precheck
→ optional knowledge-context adapter behind policy and feature flag
→ native MNCG decision
→ plan or execute
→ deterministic verification and evidence
```

MNCG is the native authoritative change gate and is production-eligible as that internal gate. OpenWiki, when present, is an optional default-off context adapter without task authority and without direct product-database access; it is production-eligible only when policy-gated. Ponytail is an external comparator only. Overall `production_claim` remains false until founder acceptance. Only the benchmark runner may select treatments A–F.

## Application-owned runtime

Every material model turn owns and records four parts: **prompt, context, tools/provider selection and control flow**. The exact prompt and context are hash-bound; route eligibility distinguishes installation from live readiness; continuation and persistence decisions are deterministic; checkpoints support pause/resume/replay. Meeting and Multi-Coder advanced commands use the same owned runtime through `owned_delegate.py`.

```text
Goal contract
→ PromptCompiler + ContextCompiler
→ ToolRouter
→ Provider call
→ Validation + Continue/Stop
→ Five-decision receipt + checkpoint
```

## Planes

| Plane | Authority | Purpose |
|---|---|---|
| Control | SQLite or Enterprise adapter | tasks, assignments, ACKs, leases, attempts, tests, audit and founder decisions |
| Execution graph | deterministic runtime | dependencies, resource locks, node state, budgets and critical path |
| Provider/model | live-readiness receipts | exact route/model eligibility, effort and fallback accounting |
| Knowledge | versioned files | plans, decisions, lessons, runbooks and explainability |
| Evidence | filesystem/object adapter | immutable artifacts, hashes and diagnostics |
| Search/RAG | rebuildable adapter | semantic retrieval only |
| Projection | XLSX/JSON/CLI | sealed human and integration views |

## Request-to-result flow

```text
Natural-language goal
  → privacy and 5W1H intake
  → validated knowledge coverage
  → missing-question analysis
  → typed role/dependency/resource graph
  → live-ready provider/model selection
  → independent specialist nodes
  → challenge and contradiction analysis
  → layered deterministic fan-in
  → frozen plan digest
  → required-role exact-digest acceptance
  → authorized Work Unit and lease
  → implementation and deterministic test tiers
  → independent verifier and audit
  → control store + sealed XLSX + knowledge + diagnostics
```

## Graph discipline

Edges are explicit `data`, `resource_lock`, `approval`, `evidence` or `control` dependencies. Independent nodes run concurrently; nodes sharing a write path, task lease, quota-constrained route or other exclusive resource are serialized. Cycles stop on convergence, repeated findings, token budget, wall-clock budget or revision limit.

## Agent identity contract

Every agent node is bound before dispatch to an immutable contract containing identity, personality, mission, responsibilities, authority, forbidden actions, evidence requirements, output schema, read/write scopes, model policy, effort and independent-review status. Provider and model are execution resources, not identities.

## Decision integrity

A command may complete while a meeting remains blocked. A plan is accepted only when every required role returns a substantive response for the same frozen plan digest and all hard gates pass. Empty, meta-only, unauthenticated, quota-blocked or model-unverified seats remain unsatisfied.

## Ollama

Ollama Cloud is a first-class provider family. Each exact cloud model is a separate candidate. Selection is based on role fit, live readiness, privacy, model identity, effort support, latency, quality and budget. Local Ollama is disabled by default for governed reasoning and must be enabled explicitly.

## Knowledge and RAG

Transactional truth remains in the control plane. Knowledge artifacts are open, versioned and portable Markdown/JSON/Canvas files. They are treated as untrusted content when fed to models. RAG indexes are rebuildable derivatives, never workflow authority.

## Public/private separation

Community, private Enterprise and customer knowledge use separate physical roots and independent Git histories. Public exports are allowlist-built and scanned for secrets, private infrastructure, personal paths, customer identifiers and Enterprise source.
