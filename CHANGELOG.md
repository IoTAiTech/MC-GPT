# Changelog

All notable changes are documented here. The project follows semantic versioning for the Suite and preserves the independent MC-GPT component version.

## [Unreleased]

## [6.5.0-beta.2] — 2026-08-05

### Added
- Enterprise Customer Edition with Ed25519-signed entitlements, feature/limit/environment/installation binding, trust rotation, signed revocation metadata and strict limit validation.
- Licensed PMD/ProductX connector through authenticated HTTPS APIs only, with optional mTLS/certificate pinning, mutation idempotency, optimistic revision binding and bounded JSON responses; direct PMD database and Excel access remain forbidden.
- Portable capability packs with one typed contract, deterministic neutral archive and REST/MCP/OpenAPI materialisers.
- Central JSONL application/audit/transaction/diagnostics logging with deterministic secret redaction and `iot-ai status --logs`.
- Technical readiness documentation for EU AI Act, GDPR, CRA, NIS2 and AI incident response.
- Official MC-GPT logo and brand manifest in public release assets.
- Evidence-bound quantitative and qualitative competitor comparison in README.

### Changed
- Every official installer and `iot-ai update apply` now performs a clean transactional installation by default.
- Recognised older active Suite/component versions and canonical packages are archived only after the replacement verifies; settings, databases, customer data and unknown files are preserved.
- `iot-ai update` is the only public update authority; older updater names are deprecated aliases or internal modules.
- Embedded MC-GPT component advanced to `0.6.0-alpha.1`; its archive builder now validates and includes the full relative-import dependency closure.

### Security
- Capability capture redacts secret values and secret-named fields before archive creation.
- Clean host-adapter upgrades remove obsolete files only when their recorded managed digest still matches.
- Enterprise customer packages contain only public verification material; issuer private keys remain vendor-only.
- Public GitHub export and history remain physically isolated from Enterprise/customer/vendor licensing material.
- Knowledge-export failures are audit-logged instead of being silently discarded.

## [6.4.0-beta.1] — 2026-08-05

### Added
- Goal-first execution contracts with explicit outcome, context, constraints, verification and stop rules.
- Application-owned PromptCompiler, ContextCompiler, ToolRouter and ControlFlowEngine.
- Five hash-bound decision receipts per material agent turn.
- Durable checkpoint, pause/resume and replay support for execution graphs.
- Platform-neutral AgentRuntimeStore port and agent-runtime status metrics.
- Owned-delegate integration for Meeting and Multi-Coder advanced workflows.

### Changed
- Meeting, Mesh and Multi-Coder provider calls now persist exact prompt/context/tool/control artifacts.
- Provider selection separates installation, authentication, quota, live readiness and served-model identity.
- Ollama Cloud remains a first-class model-specific seat and may not qualify another named adapter.
- MC-GPT component advanced to `0.5.0-alpha.1`.

### Security
- D2/D3 context blocks cannot silently enter cloud prompts.
- No silent context truncation or framework-owned prompt defaults.
- Public/private/customer state and diagnostics remain separated and hash-bound.

## [6.3.0-beta.1] — 2026-08-05

### Added
- Evidence-bound EU AI Act current-obligation controls for Articles 4, 5 and 50, upstream model dossiers, incident records and deployment-specific risk triage.
- First-interaction AI disclosure receipts in English, German and Persian.
- Machine-readable provenance for Markdown, HTML, JSON and PNG with hash-bound sidecars and visible-label gates.
- EU AI Act release gate, system card, compliance matrix, model register, claim-evidence register and lifecycle documentation.
- Immutable EU AI Act compliance reviewer role and provider-call blocking before prohibited or unclassified high-risk execution.

### Changed
- Embedded MC-GPT component advanced to `0.4.0-alpha.1`.
- Meeting acceptance now requires every requested substantive seat to review and accept the same frozen plan digest with an exact served-model receipt.
- Multi-Coder planning and final review now require exact digests, deterministic test evidence and independent acceptance; Ollama cloud models can be addressed as distinct seats.
- Unified status now reports EU AI Act controls individually, never as a legal compliance percentage.

### Security
- Article 5 screening occurs before provider or tool dispatch for agentic, Meeting, Mesh, Task intake and Multi-Coder workflows.
- Public-interest and deepfake exports fail closed without substantive editorial responsibility or visible labelling.
- Public GitHub release gates reject unsupported blanket compliance claims.

## [6.2.0-beta.2] — 2026-08-04

### Added
- Complete GitHub Community surface with pinned CI, security, public-boundary and tag-only release workflows.
- Deterministic source release builder and downloaded-artifact verifier.
- Public repository contract and Git-history privacy scanner.
- Explicit effective orchestration profile in `iot-ai status`.
- Machine-readable Meeting status fields separating command execution, meeting state, plan acceptance, user approval and execution authorization.

### Changed
- Embedded MC-GPT component advanced to `0.3.0-alpha.2`.
- Execution graph edges now explicitly classify approval, control and evidence dependencies in addition to data and resource locks.
- Public export allowlist now includes Git governance, commercial notice and repository build metadata.

### Fixed
- Corrected reconstructed public package console entry points.
- Redacted generic Bearer credentials in diagnostics, not only `Authorization:` headers.
- Added regression tests for agentic execution, Ollama Cloud readiness, Meeting semantics, task/lease lifecycle, diagnostics, knowledge, installer/rollback and public export.

### Security
- Public GitHub export and Git history are fail-closed for Enterprise roots, secrets, private keys, private infrastructure, personal paths and internal hostnames.

## [6.2.0-beta.1] — 2026-08-04

### Added
- First-class Ollama Cloud model candidates with live readiness and exact requested/served receipts.
- Immutable role contracts containing identity, personality, mission, authority, scopes and expected output.
- Dependency/resource-aware execution graph with typed nodes, resource locks and critical-path metrics.
- Knowledge-first planning, versioned Markdown/JSON/Canvas artifacts and separate public/private/customer roots.
- Layered fan-in, contradiction matrix, exact-digest acceptance and convergence-bounded revision.
- Unified status, diagnostics and single update authority.

### Security
- Public export uses an explicit allowlist.
- Required roles reject empty, meta-only, unauthenticated, quota-blocked and model-unverified contributions.
- Diagnostics redact secrets, OAuth/lease tokens, private infrastructure, paths and customer-like identifiers.
