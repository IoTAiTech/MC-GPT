# IOT-AI and Stably Orca — Evidence-Bounded Comparison

Comparison date: **2026-08-06**.

Official Orca sources reviewed:

- Repository and feature overview: `https://github.com/stablyai/orca`
- Public GitHub snapshot on 2026-08-06: approximately 38.1k stars, 2.7k forks and 8,061 commits. These ecosystem counts are time-sensitive and are not a performance benchmark.
- Worktree-native orchestration source/docs: `https://github.com/stablyai/orca/tree/main/skill-guides`
- Runtime orchestration source: `https://github.com/stablyai/orca/tree/main/src/main/runtime/orchestration`
- Licence: MIT, as declared by the repository.

No Orca source code is copied into IOT-AI. This comparison adopts architectural lessons, not implementation bytes or branding.


## Public maturity indicators

Snapshot from the official repository page on **2026-08-06**:

| Indicator | Stably Orca | IOT-AI v6.6.0-beta.3 | Interpretation |
|---|---:|---:|---|
| GitHub stars | about **38.1k** | first public preview candidate | Orca has materially stronger public adoption and product-market visibility |
| GitHub forks | about **2.7k** | first public preview candidate | Orca has a broader contributor/user experimentation surface |
| Repository commits shown | about **8,061** | deterministic release history begins with this public preview | Commit counts are not a quality benchmark, but indicate project maturity and iteration volume |
| Named CLI agents in public README | **30+** plus arbitrary CLI agents | **4 coder families + model-specific Ollama gateway** | Orca wins breadth; IOT-AI deliberately starts narrower and evidence-bound |

These figures are time-sensitive repository indicators, not performance or security benchmarks.

## Where Orca is stronger today

| Area | Orca evidence | IOT-AI status |
|---|---|---|
| Desktop/mobile experience | Native desktop on macOS/Windows/Linux plus mobile companion | CLI-first; dashboard is roadmap |
| Agent breadth | Public README lists many CLI agents and says arbitrary CLI agents are supported | Four first-party coder adapters plus Ollama model gateway; generic adapter contract is less mature |
| Worktree UX | Worktree-native task creation, terminals, source control and PR-linked workflows | Governed CLI worktree isolation added in v6.6.0-beta.3; no comparable visual IDE |
| Visual review | Built-in diff annotation and Chromium Design Mode | Evidence/diagnostics and deterministic review; no equivalent interactive visual review UI yet |
| GitHub/issue flow | Native PR, issue, Actions and project integrations | Safe public-release scripts and draft-PR handoff; no equivalent integrated UI |
| Remote operator experience | SSH worktrees, headless server and mobile steering | Remote execution is architecture-level; polished operator UX is not yet delivered |
| Community maturity | Public repository, frequent releases and broad adoption | First public Developer Preview candidate |

## Where IOT-AI is deliberately stronger

These capabilities are release-tested in IOT-AI. They are described as `not evidenced` for Orca only when they were not present in the official sources reviewed; this is not proof that an Orca edition or future release cannot provide them.

| Area | IOT-AI v6.6.0-beta.3 | Orca reviewed public evidence |
|---|---|---|
| Specialist identity | Immutable role, mission, authority, read/write scope, output schema and expiry before dispatch | Agent/worktree orchestration documented; equivalent immutable role contract not evidenced |
| Provider truth | Installed, authenticated, quota, live-ready, requested/served model and effort are separate | Usage/account support documented; equivalent exact served-model qualification not evidenced |
| Ollama | Local/cloud models are first-class, model-specific seats; one provider can never qualify another | Arbitrary CLI agents documented; model-specific Ollama governance not evidenced |
| Decision quality | Required roles must accept the same frozen plan digest; empty/meta-only seats never count | Structured orchestration and decision gates documented; same-digest acceptance not evidenced |
| Transactional work | Task → Work Unit → Assignment/ACK → Lease → Evidence → Audit → Founder decision | Task/dispatch/message/gate orchestration documented; full governed lifecycle not evidenced |
| Compliance evidence | Article 5 screening, Article 50 disclosure/provenance, AI literacy and public/private release gates | Privacy/telemetry documentation exists; EU release-control chain not evidenced |
| Customer deployment | Community/Enterprise boundary, signed entitlements, PMD API adapter and customer-specific qualification | Developer IDE focus; comparable customer control-plane licensing not evidenced |
| Diagnostics | Sanitised correlation bundle spanning meeting, model, task, test and audit | Rich app/runtime observability; equivalent portable evidence bundle not evidenced |
| Database/platform independence | Storage, provider and ProductX/PMD ports separate core logic from a database/platform | Desktop/runtime implementation is TypeScript/Electron-oriented |

## Adopted Orca lessons in v6.6.0-beta.3

1. **Worktree-native isolation.** One goal can create several tracked-content-only worktrees. Untracked local files and secrets are not copied.
2. **One run, many workers.** Worktree records include base commit, branch, agent, status and evidence.
3. **Human promotion.** IOT-AI produces a review/promotion plan; it never merges a winner automatically.
4. **Dirty-work protection.** Dirty or committed-but-unmerged workers block cleanup.
5. **GitHub handoff.** The delivery kit contains an allowlist-driven public export, local bare-remote simulation, draft-release instructions and explicit Founder confirmation.
6. **Usage/status visibility.** `iot-ai status` reports coder health, provider/model/effort evidence, workflow scores, logs and worktree runs.


## Additional Orca lessons and our response

| Orca lesson | IOT-AI response in this release | Remaining roadmap |
|---|---|---|
| Worktree-native isolation prevents parallel agents from overwriting one checkout | Governed tracked-content-only worktrees, explicit run registry, dirty/unmerged cleanup blockers and human promotion | Visual multi-worktree control surface |
| Design Mode sends DOM, computed CSS and a cropped screenshot to an agent | Task Validation accepts digest-bound screenshots, HTML/CSS, logs and project documents and records whether a vision adapter actually inspected the image | Optional local browser-capture adapter with explicit privacy classification; no implicit cloud egress |
| Usage/rate-limit visibility reduces stalls | Unified status separates installed/authenticated/quota/live-ready and records provider receipts, model, effort, tokens and latency | Provider-native local usage-window parsers with freshness/source labels |
| Integrated diff annotation and issue/PR workflow tightens the human review loop | Evidence-bound review, promotion plan, GitHub allowlist and Draft/Prerelease handoff | Interactive diff annotation and Jira/Linear front-end connectors |
| Session restore, notifications and mobile steering improve daily operability | Durable checkpoints, pause/resume/replay and diagnostics exist in the control plane | Desktop/mobile/operator UX remains roadmap |

The product strategy is to combine Orca-class daily ergonomics with stricter task validation, specialist identity, provider truth, Ollama governance, transactional authority and customer compliance evidence.

## Explicitly not copied or claimed

- No Orca desktop UI, mobile application, Design Mode or terminal multiplexer is claimed.
- No Orca code, asset, logo, text or internal protocol is bundled.
- IOT-AI does not claim to support Orca's full public list of CLI agents in this release.
- The current advantage claim is **enterprise governance and evidence**, not desktop usability or ecosystem size.

## Product direction

The product goal is not to become a cosmetic clone. The target is:

```text
Orca-class parallel developer experience
+ stronger provider/model truth
+ immutable specialist roles
+ evidence-bound meetings and task authority
+ sovereign Ollama and on-prem deployment
+ PMD/AIMDB enterprise integration
+ EU-focused release and privacy controls
```

Until the desktop/dashboard roadmap ships, Orca remains the stronger benchmark for everyday developer interaction and broad agent UX. IOT-AI's defensible differentiation is the governed execution and customer-control layer behind that experience.
