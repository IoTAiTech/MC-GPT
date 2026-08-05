# IOT-AI Coder Suite / MC-GPT (Community)

> **Audience:** private individuals for **personal test and noncommercial evaluation** only.  
> **Not** for company production use. **Not Open Source** (PolyForm Strict 1.0.0 — source available).  
> **Legal brand:** IoT-AI.Tech · **Version:** 6.5.0-beta.2 · **Repo:** https://github.com/IoTAiTech/MC-GPT  
> Commercial / company use requires a written license. No warranty. No production claim.

<p align="center">
  <img src="assets/brand/MC-GPT-Logo-Master-1024.png" alt="MC-GPT official product logo" width="240" />
</p>

> **Suite v6.5.0-beta.2 · MC-GPT v0.6.0-alpha.1**  
> **Community Developer Preview:** personal and noncommercial evaluation under the repository licence.  
> **Enterprise Customer Edition:** private, contract-bound, signed-entitlement distribution for licensed organisations.

IOT-AI turns one engineering goal into a privacy-gated, knowledge-first and dependency-aware execution graph. It binds a specialist identity and immutable mission to every agent, chooses live-ready coder or Ollama Cloud models, challenges competing plans, freezes one evidence-bound plan digest, executes only authorised work, verifies deterministic results and exports a sanitised diagnostic trail.

## Overview

Multi-agent tools can create many messages without proving that the right specialists participated, the routes were usable, the plan converged, the implementation was authorised, or the result was safe to publish. IOT-AI separates:

- specialist role from provider and model;
- true dependencies from narrative sequencing;
- planning from execution authority;
- model opinions from deterministic evidence;
- private operational data from public release material;
- portable knowledge from transactional workflow state;
- named-adapter qualification from generic fallback readiness.

```text
Goal
→ privacy + 5W1H intake
→ prior-knowledge coverage check
→ typed role/dependency/resource graph
→ live-ready provider and exact-model selection
→ independent analyses and adversarial challenge
→ layered deterministic fan-in
→ frozen plan digest
→ required-role exact-digest acceptance
→ authorised implementation and tests
→ independent verification and audit
→ database adapter + sealed XLSX projection
→ versioned knowledge + sanitised diagnostics
```

## Public command surface

Normal users need five commands:

```text
iot-ai             natural-language goal and advanced subcommands
iot-ai-help        current commands, purposes and examples
iot-ai-status      Suite, coder, model, workflow, compliance and log health
iot-ai-settings    platform-independent settings and execution profiles
iot-ai-update      one transactional update authority
```

Meeting, Mesh, Multi-Coder, Tasks, Provider Discovery, Diagnostics and Capability Packs remain available as advanced workflow engines behind the main command.

## Clean installation and upgrade

Every applied installation is a **clean transactional installation**:

1. verify the exact package SHA-256 and sealed manifest;
2. snapshot the current wrapper, managed adapters, component registry and qualification state;
3. install into an isolated versioned virtual environment (PEP 668 safe);
4. verify the new Suite and all selected host adapters;
5. move recognised older active Suite/component versions and old canonical packages into the transaction rollback archive;
6. preserve settings, databases, customer data, unknown directories and non-managed files;
7. activate the wrapper atomically;
8. emit a rollback receipt and exact log locations.

```bash
iot-ai update apply \
  --package IoT-AI-Tech-iot-ai-Coder-Suite-v6.5.0-beta.2-ALL-IN-ONE.zip \
  --expected-sha256 <exact-sha256> \
  --package-store "$HOME/ai-iot/Install/MC-GPT" \
  --package-archive "$HOME/ai-iot/Archive/MC-GPT" \
  --apply
```

A prompt-driven installer must invoke the same `iot-ai update apply` transaction. It must not copy files directly, bypass the manifest, use `--break-system-packages`, or patch an installed version in place.

### Logs

```bash
iot-ai status --logs
```

Default Linux locations:

```text
~/.local/state/iot-ai-tech/iot-ai-suite/v1/logs/iot-ai.jsonl
~/.local/state/iot-ai-tech/iot-ai-suite/v1/logs/audit.jsonl
~/.local/state/iot-ai-tech/iot-ai-suite/v1/logs/transactions/
~/.local/state/iot-ai-tech/iot-ai-suite/v1/logs/diagnostics/
```

If `XDG_STATE_HOME` is set, it replaces `~/.local/state`. On Windows, logs are below `%LOCALAPPDATA%\IoT-AI.Tech\IOT-AI-Suite\v1\logs`. Every installer, updater, repair, rollback and error response prints these paths.

## Ollama Cloud as a first-class provider

Ollama is not a generic last-resort fallback. Each eligible cloud model is treated as a distinct seat and selected by role fit, live readiness, privacy class, exact served-model evidence, supported effort, historical quality, latency and budget. Local Ollama models are disabled by default for governed deep reasoning.

```text
ollama:<exact-model-id>:domain-architect
ollama:<exact-model-id>:security-challenger
ollama:<exact-model-id>:implementation-reviewer
ollama:<exact-model-id>:independent-judge
```

A successful Ollama call can qualify only the Ollama seat or an explicitly generic fallback lane. It can never qualify Grok/xAI, Claude, Codex or Gemini.

## Portable capability packs

The Suite can create deterministic, secret-safe capability archives from one operation contract and expose the same contract at three boundaries:

```text
REST · MCP · OpenAPI 3.1
```

```bash
iot-ai knowledge pack --spec capability.json --output capability.iotaicap
iot-ai knowledge verify-pack capability.iotaicap
```

The useful pattern is inspired by the official AgentGem product and architecture documentation: redact secrets at capture, define each operation once, keep a deterministic neutral archive, and materialise the same contract across several boundaries. IOT-AI does **not** copy AgentGem code or claim its hosted marketplace and monetisation features.

## Community and Enterprise Customer editions

| Capability | Community Developer Preview | Enterprise Customer Edition |
|---|---|---|
| Personal/noncommercial evaluation | Included | Included under contract |
| Company-internal or production use | Not licensed | Licensed entitlement required |
| Provider effort above `medium` | Limited | Feature/limit entitlement |
| PMD/ProductX connector | Not included | Authenticated API adapter |
| Fleet governance and customer policies | Limited | Contracted feature set |
| Signed entitlement and expiry | No | Ed25519-verified |
| Direct PMD database access | Forbidden | Forbidden; API only |
| Customer deployment qualification | Not claimed | Required per customer/use case |
| Source redistribution/fork/resale | Not permitted without agreement | Contract-specific rights only |

Enterprise licences are signed canonical entitlements bound to customer, contract, features, limits, permitted environments, optional installation IDs and validity dates. Signed revocation records are checked when configured. Customer packages contain public verification keys only; issuer private keys are never distributed.

## Competitive comparison

### Comparison methodology

Comparison date: **2026-08-05**. Competitor entries below are limited to features explicitly documented on the vendors' public official pages reviewed for this release. `Not evidenced` means **not evidenced in reviewed public documentation**; it does not prove that a product cannot provide the capability through another edition, integration or future release. IOT-AI values are release-specific and reproducible from this repository and its test evidence. The matrix is descriptive and release-specific; it does not assert universal superiority.

Official comparison sources:

- Claude Code Agent Teams: `https://code.claude.com/docs/en/agent-teams`
- GitHub Copilot `/fleet`, custom agents and plugins: `https://docs.github.com/en/copilot/concepts/agents/copilot-cli/fleet`
- AgentGem: `https://agentgem.ai/`
- ServiceNow AI Control Tower: `https://www.servicenow.com/products/ai-control-tower.html`

### Quantitative comparison

| Measurable public characteristic | IOT-AI v6.5 | Claude Code Agent Teams | GitHub Copilot Fleet | AgentGem | ServiceNow AI Control Tower |
|---|---:|---:|---:|---:|---:|
| Normal-user top-level commands | **5** | Not comparable | Not comparable | Not comparable | Web platform |
| Native coder CLI families orchestrated by this release | **4** (Claude, Codex, Gemini, Grok) | **1** vendor family | **1** Copilot runtime | **3** capture sources named publicly (Claude, Codex, Hermes) | Vendor-neutral inventory; count not published |
| Additional first-class model gateway families | **1** (Ollama local/cloud) | External tools via MCP | Custom agents/plugins; cross-subscription routing not evidenced | Multiple materialisation targets | Any first/third-party AI inventory |
| Portable operation protocol boundaries from one contract | **3** (REST/MCP/OpenAPI) | Not evidenced | Plugins may include MCP; one-contract triple exposure not evidenced | **3** (REST/MCP/OpenAPI) | MCP/A2A integrations documented; one-contract triple exposure not evidenced |
| Public/private/customer knowledge roots | **3** physically separate classes | Not evidenced | Enterprise/repository scopes documented; physical three-root model not evidenced | **3** publication scopes (public/unlisted/private) | Enterprise access/governance model; exact root count not published |
| Required consensus identity | **1 exact plan digest across required roles** | Shared task/team synthesis; exact-digest gate not evidenced | Parent orchestration; exact-digest gate not evidenced | Review/versioning; exact-digest gate not evidenced | Governance/approval workflows; exact-digest gate not evidenced |
| Clean install with old managed-version archive and normal rollback | **Required** | Session/worktree features; package clean-install contract not evidenced | CLI rewind/plugins; equivalent Suite transaction not evidenced | Install/merge/versioning; equivalent rollback not evidenced | Platform lifecycle controls; local package transaction not comparable |

### Qualitative comparison

| Capability | IOT-AI | Claude Code Agent Teams | GitHub Copilot Fleet | AgentGem | ServiceNow AI Control Tower |
|---|---|---|---|---|---|
| Cross-provider collaboration using existing CLI subscriptions | **Designed in** | Claude-only team | Copilot subagents | Captures/materialises across agents; live cross-provider meeting not evidenced | Third-party agent integration; developer CLI subscription reuse not evidenced |
| Immutable specialist identity, mission, authority and output contract before dispatch | **Required** | Reusable subagent roles and task prompts | Custom agents with scoped prompts/tools | Composable packaged capability | Agent identity/governance documented; immutable per-task role contract not evidenced |
| Dependency/resource-aware execution graph | **Data and resource edges** | Task dependencies; avoid overlapping files | Parallel independent tasks and parent reconciliation | Composition model | Workflow/CMDB/Agent Fabric integration |
| Evidence-bound same-plan-digest acceptance | **Hard gate** | not evidenced in reviewed public documentation | not evidenced in reviewed public documentation | not evidenced in reviewed public documentation | not evidenced in reviewed public documentation |
| Task, work-unit, assignment/ACK, lease, evidence and audit lifecycle | **Integrated workflow** | Shared task list; leases/evidence contract not evidenced | SQL todo coordination; full governed lifecycle not evidenced | Capability packaging/versioning | Strong enterprise lifecycle/governance, CMDB and compliance |
| Secret-safe portable capability archive | **Included** | Skills/configuration | Plugins/skills | **Core feature** | Enterprise platform assets; neutral local archive not evidenced |
| Sanitised diagnostic ZIP with cross-workflow correlation | **Included** | Logs/session facilities; equivalent bundle not evidenced | Session/task history; equivalent bundle not evidenced | Usage analysis; equivalent bundle not evidenced | Runtime metrics/log traces; export format not evidenced |
| On-prem/offline-first control plane | **Architectural default** | Local CLI with provider service | Local CLI with provider service | Local-first with optional marketplace | ServiceNow cloud platform |
| AI inventory, CMDB mapping and ROI governance | ProductX/AIMDB optional Enterprise integration | Not product scope | Not product scope | Not product scope | **Core strength** |
| EU technical release gates and public/private export boundary | **Included; no blanket conformity claim** | not evidenced in reviewed public documentation | not evidenced in reviewed public documentation | Secret redaction documented | EU AI Act governance content documented |

### Positioning

IOT-AI does not attempt to replace every competitor. Its target intersection is:

```text
multi-provider developer collaboration
+ governed task/evidence lifecycle
+ local/sovereign deployment
+ Ollama Cloud model diversity
+ portable capability packs
+ ProductX/PMD enterprise integration
+ evidence-bound European release controls
```

ServiceNow remains a stronger benchmark for enterprise-wide AI discovery, CMDB mapping, risk and ROI. Claude Agent Teams and GitHub Fleet provide deeply integrated vendor-native parallel execution. AgentGem is a strong benchmark for secret-safe portable capability packaging and marketplace materialisation. IOT-AI's differentiation is the combination of those concerns under a provider-neutral, evidence-first and customer-deployable control plane.

## European regulatory engineering

This Developer Preview includes technical controls and documentation mapped to:

- EU AI Act Articles 4, 5 and 50 for the declared interactive software-engineering purpose;
- Cyber Resilience Act secure-by-default, vulnerability handling, update and reporting readiness;
- GDPR data minimisation, purpose limitation, storage limitation and data-protection-by-design engineering;
- NIS2-aligned risk management, incident evidence, supply-chain and business-continuity controls for customers for whom NIS2 is applicable.

```bash
iot-ai compliance status
iot-ai compliance screen --text "Review the intended use"
iot-ai compliance mark --file report.md --human-reviewed --editor "<responsible party>"
python tools/eu_ai_act_release_gate.py . --profile developer-preview
```

These are technical readiness controls, **not legal certification, CE marking, a conformity assessment, or a blanket statement covering every customer deployment**. Applicability and customer obligations depend on role, intended purpose, sector, deployment and modifications.

## Privacy and public/private boundaries

- Raw prompts and provider outputs are not retained by default.
- Cloud routes are opt-in and classified before egress.
- D3/secret data blocks cloud dispatch.
- Public diagnostics remove credentials, lease tokens, private network identifiers, internal hostnames and personal paths.
- Public, private Enterprise and customer data use separate physical roots and Git histories.
- Public release exports are allowlist-built, secret-scanned and clone-back verified.

## Testing

```bash
python -m unittest discover -s tests -p 'test_*.py'
python -m pytest
python -W error -m pytest
python tools/static_security_audit.py .
python tools/public_boundary_check.py .
python tools/benchmark_agent_runtime.py --iterations 3000
```

Release totals are regenerated during the final deterministic build and recorded in `FINAL_TEST_SUMMARY.json`. Historical numbers are not reused as proof for a changed source tree.

## Release status

This is a Developer Preview, not a stable or production-ready release. External gates include real Windows on-device qualification, live provider-account and exact-served-model qualification, real GitHub Actions provenance/attestation, Enterprise PostgreSQL/RLS/restore validation and deployment-specific German/EU legal review.

## Licence

Community use is governed by the repository licence and notices. Commercial, company-internal, production, derivative, fork, redistribution, hosted-service or resale use requires a written IoT-AI.Tech commercial licence.

See `PUBLIC_REPOSITORY_NOTICE.md`, `COMMERCIAL.md`, `LICENSE`, `SECURITY.md`, `THIRD_PARTY_NOTICES.md` and `docs/`.