# Changelog

All notable changes are documented here. The project follows semantic versioning for the Suite and preserves the independent MC-GPT component version.

## [Unreleased]

### Fixed
- Meeting knowledge-export failure logging no longer crashes a completed meeting: `logging_config.append_event` is imported under an unambiguous name so it cannot be shadowed by `workspace.append_event`, and the handler cannot raise.
- Mesh CLI delegation now avoids Linux `E2BIG` when a synthesis prompt exceeds `MAX_ARG_STRLEN` by moving the prompt to stdin, records `failure_detail` beside `failure_class`, and retries once via stdin after an argv-side `OSError`.
- Multi-Coder work-unit claim now returns the validation-gate decision instead of `KeyError: 'lease_id'`. A first-run revision bump is labeled as a stale skip only when the gate itself was skip-bound; an approved validation that went stale tells the operator to re-validate, not to skip.
- Mesh E2BIG handling measures UTF-8 bytes, removes only `{prompt}` slots (keeping deny/policy flags), preserves Gemini headless `-p` and Grok `--prompt-file /dev/stdin`, records `OSError` errno/detail, and retries once via stdin.
- Cross-meeting report tests now assert files in the managed `meeting-reports` store. `write_report` remaps the caller path to that store; checking the original home path was a false CI failure.
- Path confinement for meeting reports, Excel projection, and export-gate files now uses `os.path.realpath` plus `os.path.commonpath` before any write or hash. User-supplied output parents are not added as trust roots.

## [6.7.0-beta.5] — 2026-08-08

### Added
- Conversation-aware natural-language `IntentContract` and minimal persisted `ConversationState` for English, German, Persian and mixed requests.
- Closed-loop Autopilot composing authoritative Tasks, full hybrid Meetings, Multi-Coder implementation, deterministic tests, failure meetings, bounded repair/retest, independent review, audit and terminal reporting.
- Strict Suite versus authenticated PMD/PRCS API backend routing with no silent dual-store merge or direct product-database fallback.
- Evidence-bound acceptance-scorecard validator detecting overlaps, duplicates, out-of-range/unassessed criteria and stale verification revisions/digests.
- Semantic dashboard-agent capability validation, alias handling and capability-attested Meeting responses.
- JSON, Markdown, CSV and XLSX autonomous-run reports containing complete Task, Provider and Iteration tables plus a hash manifest.
- README infographic, Table of Contents, natural-language examples and GitHub metadata/social-preview assets.

### Changed
- Execution verbs now request a bounded run to a truthful terminal state by default; parameter-heavy Task/Meeting/Multi-Coder commands remain expert escape hatches.
- All eligible configured coder families, every exact configured cloud-model seat, and exact Ollama local/cloud seats are attempted at material gates; one successful provider never counts as Multi-Coder consensus.
- Bulk tasks run in bounded WIP waves so every selected task is eventually scheduled without promoting the whole backlog at once.
- `tasks run --mode hybrid` and `multi-coder run` execute by default because the `run` verb is explicit; `--plan` is the non-mutating inspection mode and `--apply` remains a compatibility flag.
- Prompt envelope advanced to v2 with execution authority, closed-loop, scorecard, provider-truth and release/privacy contracts.

### Fixed
- Progress telemetry preserves `awaiting_founder` instead of reopening technical-complete work.
- Zero-eligible `solve-all` and bulk authorization return `noop`, never a fake pass; `awaiting_founder` tasks are reported and skipped rather than re-authorized.
- Technical submit enters the Founder queue only after a passing audit; failed audit returns `needs-work`, and the legacy direct `complete()` compatibility path is fail-closed.
- Scorecard pass/partial/fail overlap and stale trusted receipts are rejected.
- Natural-language continuation resolves the prior selected task set and checkpoint without storing private chain-of-thought.
- Current GitHub CI non-root/path-boundary fixes from `main@8b5f60616636e63d8310d4ace3057a28db46c1d3` are retained.

### Security
- Founder final acceptance, public release, history replacement, production deployment and destructive operations remain explicit human gates.
- Provider outages, exact model identity and fallback status remain visible in all Meeting/Multi-Coder reports.
- PMD/PRCS authority remains authenticated API-only; direct SQLite/PostgreSQL access is forbidden.
- Public infographic provenance and human editorial responsibility are hash-bound in a sidecar.

## [6.7.0-beta.4] — 2026-08-08

### Added
- Federated read-only Meeting reporting across explicitly selected canonical/legacy stores with JSON, CSV, Markdown, XLSX and deterministic ZIP bundles.
- Stale-session detection, approval/status conflict reporting, ANSI cleanup, source manifests and explicit legacy model-telemetry uncertainty.
- `iot-ai tasks authorize-execution` for the validation-only gate and `iot-ai tasks run --mode hybrid` for actual Multi-Coder implementation.
- GitHub SEO/release guidance, corrected CODEOWNERS, expanded package keywords and repository metadata.
- Adversarial tests for trusted-root file hashing, legacy meeting federation, public D0 allowlisting and report-bundle integrity.

### Changed
- Public Meeting reports are brief-only, D0-only and require an explicit meeting-ID allowlist; private/restricted reports retain evidence under a separate classification.
- Historical `running` sessions older than the configured threshold are shown as `stale` in reports without modifying source databases.
- Missing legacy `model_requested`/`model_served` fields are labelled unverified rather than inferred from seat/provider names.
- Release baseline advanced to GitHub `main@11fa3c840744d953cee183c529040ad27ffb7dbc` plus the verified private `6.7.0-beta.3` delivery.

### Fixed
- Closed the CodeQL path-injection class by requiring explicit allowed roots, rejecting symlinks/non-regular files and hashing through a no-follow file descriptor where available.
- Prevented operator-selected package paths from widening trust to their own parent directory.
- Restored secure worktree creation when the managed run directory does not yet exist.
- Removed ambiguity between task validation and task implementation commands.
- Corrected the public GitHub CODEOWNERS organisation handle.

### Security
- Legacy Meeting databases are opened read-only with `PRAGMA query_only=ON` and integrity checks; PMD/ProductX/customer databases remain API-only and outside the reporting boundary.
- SHA-256 sidecars contain basenames only; public source manifests omit private absolute paths.
- Public history, release assets and report exports remain allowlist-built and fail closed on secret/private-infrastructure findings.
- Production, blanket EU AI Act compliance and live-provider availability claims remain false.

## [6.7.0-beta.3] — 2026-08-07

### Added
- Canonical cross-meeting reports in JSON, CSV, Markdown and XLSX.
- Authenticated loopback Meeting API, calendar records and read-only dashboard-agent seats.
- Exact `provider@model` admission for all fresh qualified cloud-model receipts.
- SHA-bound curl and npx/npm bootstraps that invoke the canonical installer.
- Gated sanitized-history preparation and force-with-lease replacement tooling.

### Fixed
- Removed real private-path/IP literals from public test fixtures.
- Reconciled installer documentation with `--package-archive` and current-package handling.
- Installed Meeting, Tasks and Multi-Coder host commands on all supported coder hosts.
- Separated command completion from honest meeting acceptance and improved brief participant summaries.

### Security
- PMD/dashboard integration remains API-only; direct cross-product database access is rejected.
- Dashboard-agent seats are read-only and fail on any reported write.
- Public history replacement requires explicit Founder confirmation and remote-SHA lease matching.

## [6.6.0-beta.3] — 2026-08-06

### Added
- One complete private delivery with a physically isolated public GitHub tree, Community release assets, Enterprise customer source, vendor-only licensing tools, test evidence, Git publication prompts and a delivery verifier.
- Exact GitHub publication prompt and fail-closed scripts that publish only the public repository and Community assets after literal Founder confirmation.
- Evidence-bounded Orca maturity indicators and product lessons for worktrees, usage visibility, visual task context and human review.

### Changed
- Strengthened pre-execution task validation so Claude, Codex, Gemini, Grok and an exact Ollama Cloud model seat must each provide a substantive receipt before an optimized task can be accepted.
- Updated public installation, supported-coder, licensing, Founder/contact and GitHub release documentation for the first Community Developer Preview; noncommercial modification, forks and redistribution are stated consistently across all notices.
- Embedded MC-GPT component advanced to `0.7.0-alpha.3`; Enterprise Customer Add-on advanced to `1.1.0-alpha.2`.

### Fixed
- Eliminated same-version multi-build ambiguity by issuing a new immutable revision rather than republishing beta.2 bytes.
- Corrected release notes and manifests so every public, Enterprise and vendor artifact resolves to one versioned source snapshot.

### Security
- Public GitHub publication remains allowlist-only and rejects Enterprise/vendor/private evidence, secrets, private infrastructure, personal paths and customer data.
- Task execution remains blocked until task validation is approved or a policy-compliant, audited risk-acceptance receipt exists.
- Full-council meetings and task validation cannot silently omit Ollama Cloud or another required provider family when the governed all-provider policy is enabled.

## [6.6.0-beta.2] — 2026-08-06

### Added
- Auditable meeting seat plans with selectors `auto`, `all-coders`, `ollama-clouds` and `all-coders+ollama-clouds`.
- Natural-language compatibility for `/iot-ai-meeting --max-parallel ask all coder and ollama clouds only <topic>`.
- Workflow compatibility skills and wrappers for `iot-ai-meeting`, `iot-ai-tasks` and `iot-ai-multi-coder` while retaining one updater authority.
- Machine-readable meeting coverage showing requested, attempted, substantive, unsatisfied and Ollama-specific seats.
- Task-validation gate before claim, run, go, execute and solve-all with evidence-bound task optimisation and user approval.

### Changed
- Ollama Cloud is required whenever first-class Ollama policy is enabled and a meeting would otherwise silently omit it.
- `auto` meeting selection reserves at least one Ollama Cloud seat when configured; explicit all-coder meetings must include Ollama or record an explicit exclusion.
- Community documentation now clearly permits personal/noncommercial use, study, research, modification, forks and noncommercial redistribution under the licence and notices.
- GitHub README now includes supported coders, Ollama operating guidance, five-minute installation, task validation, repository map, Founder/contact and publication boundaries.
- Embedded MC-GPT component advanced to `0.7.0-alpha.2`.

### Fixed
- Prevented the observed `--seats claude,codex,gemini,grok` omission from being treated as an all-provider meeting when Ollama Cloud is configured.
- Prevented meeting summaries from hiding whether Ollama was requested, attempted or substantive.
- Restored compatibility slash-command discovery for Meeting, Tasks and Multi-Coder after clean installation.

### Security
- Missing Ollama Cloud is recorded as an explicit seat-plan blocker rather than a silent fallback or false quorum.
- Intentional Ollama exclusion requires a visible command flag and remains auditable.
- No provider success may qualify another named adapter.

## [6.6.0-beta.1] — 2026-08-06

### Added
- Canonical legal/operator identity `IoT-AI.Tech` across licences, Article 50 disclosures, provenance, package metadata and customer-facing documentation.
- Transactional migration from the superseded company/state namespace with dry-run, hash inventory, conflict blocking and digest-bound rollback.
- Worktree-native parallel coder isolation with tracked-content-only workers, run registry, review/promotion plans and dirty/unmerged cleanup protection.
- Source-grounded Stably Orca comparison, including explicit strengths, weaknesses, adopted patterns and non-claims.
- Allowlist-driven public GitHub preparation and publication directives with local tests, history scanning, annotated tag and explicit Founder confirmation.
- Machine-readable legacy-identity exception register and release-blocking identity scanner.

### Changed
- Canonical package prefix is `IoT-AI-Tech`; legacy prefixes may be read only by migration compatibility code and are never emitted by a new release.
- Canonical Linux state namespace is `iot-ai-tech/iot-ai-suite/v1`; canonical Windows vendor path is `IoT-AI.Tech`.
- `iot-ai status` now reports governed worktree runs and brand-migration state in addition to provider/model/workflow evidence.
- Clean installation remains the single update path and removes recognised stale active versions only after successful verification while preserving one transactional rollback path.
- Embedded MC-GPT component advanced to `0.7.0-alpha.1`; Enterprise Customer Add-on advanced to `1.1.0-alpha.2`.

### Fixed
- Corrected the legal/licensor/operator identity in Article 50 disclosures and all English, German and Persian transparency payloads.
- Removed invented GitHub organisation URLs from package metadata; the actual public repository URL is supplied only at publication time.
- Prevented worktree cleanup from deleting dirty or committed-but-unmerged agent work.

### Security
- Public publication remains physically limited to the public repository and Community assets; the complete delivery kit, Enterprise source, vendor signing tools and private evidence are forbidden.
- Worktree creation never copies untracked files, local credentials or ad-hoc workspace state.
- Every residual superseded brand string must have a machine-readable migration classification or the release is blocked.

## [6.5.0-beta.1] — 2026-08-06 — Quarantined / not published

### Added
- Enterprise Customer Edition with Ed25519-signed entitlements, feature/limit/environment/installation binding, trust rotation, signed revocation metadata and strict limit validation.
- Licensed PMD/ProductX connector through authenticated HTTPS APIs only, with optional mTLS/certificate pinning, mutation idempotency, optimistic revision binding and bounded JSON responses; direct PMD database and Excel access remain forbidden.
- Portable capability packs with one typed contract, deterministic neutral archive and REST/MCP/OpenAPI materialisers.
- Central JSONL application/audit/transaction/diagnostics logging with deterministic secret redaction and exact log discovery.
- Technical readiness documentation for EU AI Act, GDPR, CRA, NIS2 and AI incident response.
- Official MC-GPT logo and evidence-bound competitor comparison.

### Changed
- Every official installer and update path performs a clean transactional installation by default.
- Recognised older active Suite/component versions and canonical packages are archived only after replacement verification; settings, databases, customer data and unknown files are preserved.

### Security
- Capability capture redacts secret values before archive creation.
- Public GitHub export and history are physically isolated from Enterprise/customer/vendor licensing material.

### Known release blocker
- The candidate used the superseded `AI-IoT.Tech` legal/operator identity and was therefore quarantined rather than published.

## [6.4.0-beta.1] — 2026-08-06

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

## [6.3.0-beta.1] — 2026-08-06

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
