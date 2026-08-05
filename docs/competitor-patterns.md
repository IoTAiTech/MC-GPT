<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.5.0-beta.2 | Date: 2026-08-05 -->

# Industry and Research Patterns Adopted

This release adapts architecture patterns; it does not copy third-party product code. Provider/model branding never grants role authority.

| Pattern | Lesson adopted | IOT-AI implementation | Explicit non-adoption |
|---|---|---|---|
| Agent Skills / progressive disclosure | Load only the capability required for the current node | Five small public skills, modular role/policy contracts, references loaded on demand | No monolithic universal prompt as runtime authority |
| File-over-app knowledge | Keep decisions portable, reviewable and versionable | Markdown/JSON knowledge artifacts and JSON Canvas projections | Files do not replace task/lease transactions |
| Dependency-aware graph engineering | Parallelize only true independent work | Typed data/resource/approval/evidence/control edges | “And then” is not treated as a dependency |
| Layered fan-in | Large fan-outs must be compressed before final synthesis | Deterministic normalization, contradiction matrix and domain summaries | Final synthesizer does not consume every raw transcript blindly |
| Isolated agent work | Parallel writers require separate workspaces or path leases | Read/write scopes, resource locks, Work Units and transactional rollback | Shared uncontrolled working-tree writes are forbidden |
| Shared task/team coordination | Agents need visible responsibilities and status | Immutable role contracts, graph node state and task linkage | Provider names are not roles |
| Bounded termination | Agent loops require explicit stop conditions | Token, wall-clock, model-call and revision limits plus novelty/convergence gates | Infinite “iterate until perfect” loops are forbidden |
| Model tiering | Use the strongest suitable model only where it matters | Per-node effort, capability clamp, role fit and historical quality/latency scoring | Session-wide xhigh is not forced on deterministic work |
| Tool-grounded operations | System facts and writes require typed tools and evidence | Storage/task/provider ports, evidence references and deterministic verification | Narrative claims cannot replace runtime evidence |
| Ollama local/cloud API symmetry | Cloud models can be distinct specialist candidates | Model-specific Ollama Cloud seats, live model identity and telemetry | A successful Ollama call cannot qualify Grok/xAI or another adapter |
| Knowledge-first orchestration | Reuse validated prior work before another full meeting | Coverage analysis and gap-only mini-review graph | Stale or superseded knowledge is not silently trusted |
| Human approval and rollback | Consequential actions require explicit authority | Task/assignment/lease boundaries, founder decision separation and rollback receipts | Founder override cannot rewrite a blocked synthesis into consensus |

## Product differentiation

IOT-AI combines multi-vendor coder subscriptions and Ollama Cloud models with typed specialist identities, dependency/resource-aware scheduling, exact-digest decision convergence, deterministic evidence, portable knowledge, public/private release separation and optional Enterprise task-control adapters.

## Validation rule

A pattern is accepted only when it passes a deterministic or measurable release gate. External articles and product descriptions are design inputs, not proof that the IOT-AI implementation works.
