# IOT-AI Coder Suite

<p align="center">
  <img src="assets/brand/MC-GPT-Logo-Master-1024.png" alt="MC-GPT official product logo" width="240" />
</p>

> **Suite v6.6.0-beta.3 · MC-GPT v0.7.0-alpha.3**
> **Community Developer Preview:** personal and noncommercial use, research, modification, forks and redistribution under the repository licence.
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

Meeting, Mesh, Multi-Coder, Tasks, Provider Discovery, Diagnostics and Capability Packs remain available as advanced workflow engines behind the main command. Three compatibility aliases remain visible because they are primary workflows for advanced users:

```text
iot-ai-meeting      governed decision meeting
iot-ai-tasks        task validation and lifecycle
iot-ai-multi-coder  role-bound implementation and verification
```

They do not create a second updater or a second state authority.

## Five-minute installation

### Linux

```bash
sha256sum -c IoT-AI-Tech-iot-ai-Coder-Suite-v6.6.0-beta.3-ALL-IN-ONE.zip.sha256
unzip IoT-AI-Tech-iot-ai-Coder-Suite-v6.6.0-beta.3-ALL-IN-ONE.zip -d iot-ai-suite
cd iot-ai-suite
./installers/install.sh --home "$HOME" --hosts all --apply
iot-ai setup discover
iot-ai status --logs
```

### Windows PowerShell

```powershell
PowerShell -ExecutionPolicy Bypass -File .\installers\Install-IotAiSuite.ps1 `
  -HomePath $HOME -Hosts all -Apply
iot-ai setup discover
iot-ai status --logs
```

Run either installer without its apply flag to see the exact clean-install, managed-version cleanup and rollback plan. The installer preserves settings, databases, customer data and unknown files. See [`docs/installation.md`](docs/installation.md).

## Task validation before claim or execution

A tester report or user request may be correct, incomplete, stale or technically wrong. Before `claim`, `run --execute`, `multi-coder run --task-id`, `solve-all --apply` or equivalent host execution, IOT-AI asks whether the task should be validated and optimized by all required coder families and eligible model-specific Ollama Cloud seats.

```text
Task or user goal
→ validate | use as-is | cancel
→ visual/content/document/log/code review
→ technical, UX, security, performance and EU AI Act challenge
→ optimized task + advanced prompt + KPI/SLA + 10/10/10 cases
→ required roles accept one exact plan digest
→ user approves optimized/original/cancel
→ claim and execution
```

```bash
# show the validation gate and user question
iot-ai tasks prepare --task-id <task-id> --action status

# run the evidence-bound validation with all required coder families and model-specific Ollama Cloud seats
iot-ai tasks prepare --task-id <task-id> --action review \
  --context ./evidence/screenshot.png \
  --context ./evidence/runtime.log \
  --profile ultracode --effort xhigh

# apply the optimised task only after explicit user approval
iot-ai tasks prepare --task-id <task-id> --action approve \
  --validation-id <validation-id> --subject <user-or-founder-subject>
```

No lease is issued while validation or the user's decision is pending. Validation is bound to semantic task content; later edits invalidate it. See [`docs/task-validation.md`](docs/task-validation.md).

### Worktree-native parallel execution

For independent implementation or review lanes, IOT-AI can create one tracked-content-only Git worktree per coder. Untracked files and local secrets are not copied, dirty or unmerged work blocks cleanup, and the system produces a review plan rather than merging automatically.

```bash
iot-ai worktree plan --repo . --goal "Review the release" --agents codex,grok
iot-ai worktree create --repo . --goal "Review the release" --agents codex,grok --apply
iot-ai worktree review <run-id>
```

See `docs/worktree-orchestration.md`.

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
  --package IoT-AI-Tech-iot-ai-Coder-Suite-v6.6.0-beta.3-ALL-IN-ONE.zip \
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

## Supported coders

| Coder family | Main strengths in IOT-AI | Supported access |
|---|---|---|
| Claude Code | architecture, synthesis and review | provider-native subscription or configured API |
| OpenAI Codex CLI | implementation, debugging and code review | ChatGPT subscription or configured API |
| Gemini CLI | large-context and cross-module review | Google subscription or configured API |
| Grok CLI | implementation and adversarial review | Grok subscription or configured API |

IOT-AI does not assign authority by provider name. It first binds an immutable specialist role, mission, read/write scope, tools, evidence contract and expected output; the model selector then chooses a live-ready provider/model and clamps effort to its verified capability and edition limit.

See [`docs/supported-coders-and-ollama.md`](docs/supported-coders-and-ollama.md).

## Ollama Cloud as a first-class provider

Ollama is not a generic last-resort fallback. Each eligible cloud model is treated as a distinct seat and selected by role fit, live readiness, privacy class, exact served-model evidence, supported effort, historical quality, latency and budget. Local Ollama models are disabled by default for governed deep reasoning.

```text
ollama:<exact-model-id>:domain-architect
ollama:<exact-model-id>:security-challenger
ollama:<exact-model-id>:implementation-reviewer
ollama:<exact-model-id>:independent-judge
```

A successful Ollama call can qualify only the Ollama seat or an explicitly generic fallback lane. It can never qualify Grok/xAI, Claude, Codex or Gemini.

### Meeting seat policy

The observed failure mode `--seats claude,codex,gemini,grok` silently omitted Ollama. This release blocks that omission when Ollama Cloud is configured as first-class.

```bash
# inspect the exact seats before spending provider quota
iot-ai meeting seat-plan --seats all-coders+ollama-clouds

# invite every configured coder family and every discovered Ollama Cloud model
iot-ai meeting start \
  --topic "Deeply review this task" \
  --seats all-coders+ollama-clouds \
  --depth ultra --effort xhigh --execute

# equivalent natural-language compatibility command
iot-ai-meeting --max-parallel ask all coder and ollama clouds only deeply review this task
```

`meeting show` reports requested, attempted, substantive and unsatisfied seats, including separate Ollama coverage. Intentional omission requires `--exclude-ollama` and remains visible in the meeting receipt.

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
| Personal/noncommercial use, research and modification | Included | Included under contract |
| Company-internal or production use | Not licensed | Licensed entitlement required |
| Provider effort above `medium` | Limited | Feature/limit entitlement |
| PMD/ProductX connector | Not included | Authenticated API adapter |
| Fleet governance and customer policies | Limited | Contracted feature set |
| Signed entitlement and expiry | No | Ed25519-verified |
| Direct PMD database access | Forbidden | Forbidden; API only |
| Customer deployment qualification | Not claimed | Required per customer/use case |
| Noncommercial modification, forks and redistribution | Permitted with licence/notices | Contract-specific rights |
| Commercial fork, production, hosting, resale | Commercial licence required | Contract-specific rights |

Enterprise licences are signed canonical entitlements bound to customer, contract, features, limits, permitted environments, optional installation IDs and validity dates. Signed revocation records are checked when configured. Customer packages contain public verification keys only; issuer private keys are never distributed.

## Competitive comparison

### Comparison methodology and claim boundary

Comparison date: **2026-08-06**. Only capabilities described in the reviewed official public sources are attributed to competitors. `Not evidenced` means **not evidenced in reviewed public documentation**; it does not prove absence in another edition or later release. IOT-AI values apply only to this build and its attached test evidence. This is not a universal performance benchmark.

Official sources:

- Stably Orca: `https://github.com/stablyai/orca`
- Claude Code Agent Teams: `https://code.claude.com/docs/en/agent-teams`
- GitHub Copilot Fleet: `https://docs.github.com/en/copilot/concepts/agents/copilot-cli/fleet`
- AgentGem: `https://agentgem.ai/`
- ServiceNow AI Control Tower: `https://www.servicenow.com/products/ai-control-tower.html`

The official Orca repository displayed approximately **38.1k stars**, **2.7k forks**, **8,061 commits** and **29 named CLI-agent examples plus arbitrary CLI-agent support** on the comparison date. These are public maturity indicators—not a performance or security benchmark.

The full Orca assessment and machine-readable comparison are in `docs/comparison/ORCA_COMPARISON.md` and `docs/comparison/ORCA_COMPARISON.json`.

### Quantitative product-surface comparison

| Public characteristic | IOT-AI v6.6.0-beta.3 | Stably Orca | Claude Code Agent Teams | GitHub Copilot Fleet | AgentGem | ServiceNow AI Control Tower |
|---|---:|---:|---:|---:|---:|---:|
| Normal-user executables | **5** | Desktop + CLI + mobile surfaces | Claude Code commands | Copilot CLI command | Web/CLI product | Web platform |
| Named coder adapter families in this release | **4** + Ollama model gateway | **29 named examples** plus arbitrary CLI-agent support documented | **1** vendor family | **1** Copilot runtime | Multiple capture/materialisation paths | Vendor-neutral AI inventory |
| First-class model-gateway families | **1** Ollama local/cloud | CLI-agent oriented; model-gateway count not stated | External tools via MCP | Plugins/custom agents | Multiple targets | First/third-party AI inventory |
| Portable protocol projections from one operation contract | **3** REST/MCP/OpenAPI | Not evidenced | Not evidenced | MCP possible; one-contract triple projection not evidenced | **3** REST/MCP/OpenAPI | MCP/A2A integrations documented |
| Physically separated knowledge classes | **3** public/private/customer | Worktree/repository isolation; three knowledge roots not evidenced | Not evidenced | Enterprise/repository scopes | Public/unlisted/private scopes | Enterprise policy model |
| Required decision identity | **One exact plan digest across required roles** | Structured decision gates; exact-digest acceptance not evidenced | Team synthesis; exact-digest gate not evidenced | Parent reconciliation; exact-digest gate not evidenced | Review/versioning | Approval/governance workflows |
| Clean package lifecycle | **Verify → side-by-side install → managed cleanup → normal rollback** | App release lifecycle; equivalent customer package transaction not evidenced | Not comparable | CLI/plugin lifecycle | Versioned packages | SaaS platform lifecycle |

### Qualitative comparison

| Capability | IOT-AI | Stably Orca | Claude Agent Teams / GitHub Fleet | AgentGem | ServiceNow AI Control Tower |
|---|---|---|---|---|---|
| Daily developer experience | CLI-first; desktop dashboard is roadmap | **Current benchmark:** worktrees, terminals, diffs, Design Mode, mobile, SSH | Strong vendor-native execution | Capability packaging focus | Enterprise platform, not coding IDE |
| Parallel isolation | **Governed git worktrees with no untracked-file copy and human promotion** | **Core strength:** worktree-native parallel agents | Parallel tasks; isolation varies by tool | Not primary scope | Not primary scope |
| Agent/provider breadth | Claude, Codex, Gemini, Grok + model-specific Ollama seats | 29 named examples plus arbitrary CLI-agent support | Vendor runtime | Capture/materialisation across tools | Third-party agent inventory |
| Specialist contract before dispatch | **Immutable role, mission, authority, scopes and output schema** | Task/worker orchestration; equivalent immutable contract not evidenced | Custom roles/prompts | Packaged capability | Enterprise identity/governance |
| Provider/model truth | **Installed/auth/quota/live/exact served model/effort separated** | Usage/account visibility documented; exact served-model gate not evidenced | Provider-native status | Usage analysis | Inventory/runtime monitoring |
| Meeting and decision integrity | **Challenge, layered fan-in and same-digest required-role acceptance** | Decision gates documented; same-digest gate not evidenced | Team/parent synthesis | Review/versioning | Approval workflows |
| Transactional task governance | **Task, Work Unit, Assignment/ACK, Lease, Evidence, Audit, Founder decision** | Run/task/dispatch/message/gate model | Shared tasks/subagents | Versioning | **Core strength:** lifecycle/approval/CMDB |
| Public/private/customer release boundary | **Fail-closed allowlist and history scan** | Privacy controls documented; equivalent release boundary not evidenced | Repository/org controls | Secret redaction | Enterprise access controls |
| European technical release evidence | **Article 5/50, AI literacy, incident and claim-boundary gates; no blanket certification** | Not evidenced in reviewed product docs | Not evidenced | Secret safety documented | AI governance/compliance platform |
| Enterprise customer deployment | Signed entitlement, PMD API, on-prem/sovereign design | Developer tool | Developer tool | Capability platform | **Current benchmark:** enterprise AI control tower |

### Honest strengths and weaknesses

**Orca is currently stronger** in desktop/mobile polish, terminal and diff UX, broad CLI-agent support, remote worktrees, GitHub/issue integration, Design Mode and public ecosystem maturity.

**IOT-AI is designed to be stronger** where enterprise evidence and controlled execution matter: immutable specialist roles, exact provider/model truth, model-specific Ollama seats, same-plan-digest acceptance, Task/Assignment/ACK/Lease governance, sanitised diagnostics, customer/public separation, signed Enterprise entitlements and European release controls.

This release adopts Orca's most relevant engineering lesson—worktree-native parallel isolation—without copying its code or claiming its visual product features. The target is not a clone:

```text
Orca-class developer ergonomics (roadmap)
+ stronger role and provider truth
+ evidence-bound decisions and task authority
+ sovereign Ollama/on-prem operation
+ PMD/AIMDB enterprise integration
+ privacy and EU-focused release gates
```

Until the desktop/dashboard roadmap is delivered, Orca remains the stronger benchmark for everyday interactive developer orchestration. IOT-AI's present differentiation is the governed control plane behind the execution.

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

The Community source uses **PolyForm Noncommercial 1.0.0**. Personal use, noncommercial research, study, modification, derivative works, forks and noncommercial redistribution are permitted when the licence and required notices remain with the work.

A written IoT-AI.Tech commercial licence is required for company-internal operational/production use, paid services, managed hosting, resale, commercial distribution, commercial forks, customer deployments and Enterprise features. See [`docs/licensing-and-forks.md`](docs/licensing-and-forks.md).

## Founder and contact

**Dr.-Ing. Babak Sorkhpour** — Founder / Owner
**IoT-AI.Tech · Germany**
**Email:** [info@iot-ai.tech](mailto:info@iot-ai.tech)
**LinkedIn:** [https://www.linkedin.com/company/iot-ai-tech](https://www.linkedin.com/company/iot-ai-tech)

## Repository and GitHub publication

The public repository explains every top-level directory in [`docs/repository-map.md`](docs/repository-map.md). From a complete private delivery, publish only `01_PUBLIC_GITHUB_REPOSITORY/` as Git content and `04_RELEASE_ASSETS/COMMUNITY/` as prerelease assets. Never upload the complete private kit, Enterprise source, vendor licensing tools, private evidence, customer material or internal infrastructure.

See `PUBLIC_REPOSITORY_NOTICE.md`, `COMMERCIAL.md`, `LICENSE`, `SECURITY.md`, `THIRD_PARTY_NOTICES.md` and `docs/`.
