# MC-GPT — Governed Multi-Agent Coding Orchestrator

<p align="center">
  <img src="assets/brand/MC-GPT-Logo-Master-1024.png" alt="MC-GPT by IoT-AI.Tech" width="170" />
</p>

<p align="center">
  Coordinate Claude Code, OpenAI Codex, Gemini CLI, Grok CLI and Ollama from one engineering outcome.<br />
  MC-GPT isolates work, runs post-change tests and independent review, and returns one evidence-backed completion report.
</p>

<p align="center">
  <a href="docs/quickstart.md"><strong>Start the five-minute evaluation</strong></a> ·
  <a href="examples/quickstart-demo/README.md">Open the disposable fixture</a> ·
  <a href="https://iotaitech.github.io/MC-GPT/">Product page</a> ·
  <a href="https://github.com/IoTAiTech/MC-GPT/releases/tag/v6.7.0-beta.6">Latest downloadable preview</a>
</p>

[![CI](https://github.com/IoTAiTech/MC-GPT/actions/workflows/ci.yml/badge.svg)](https://github.com/IoTAiTech/MC-GPT/actions/workflows/ci.yml)
[![Security](https://github.com/IoTAiTech/MC-GPT/actions/workflows/security.yml/badge.svg)](https://github.com/IoTAiTech/MC-GPT/actions/workflows/security.yml)
[![Code scanning](https://img.shields.io/badge/code%20scanning-CodeQL-blue)](https://github.com/IoTAiTech/MC-GPT/security/code-scanning)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Release](https://img.shields.io/github/v/release/IoTAiTech/MC-GPT?include_prereleases)](https://github.com/IoTAiTech/MC-GPT/releases)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial-lightgrey.svg)](LICENSE)

> **Latest downloadable Community Preview:** IOT-AI Suite `6.7.0-beta.6` / MC-GPT `0.8.0-alpha.6`  
> **Current `main` source snapshot after this change:** IOT-AI Suite `6.8.0-beta.1` / MC-GPT `0.8.0-alpha.7` — not yet a tagged download  
> **Claim boundary:** Community Developer Preview · `production_claim: false` · public documentation in English

## The problem

Adding more coding agents often adds more operator work:

- several terminals and branches;
- repeated prompts and inconsistent context;
- uncertain ownership and merge conflicts;
- tests that ran before the final change rather than after it;
- no reliable answer to “what is actually finished?”

MC-GPT treats **Task, Meeting and Multi-Coder as one governed lifecycle**, rather than separate commands the operator must coordinate manually.

## The magic moment

Describe the result once:

```bash
iot-ai "Add rate limiting to the login path, preserve current behaviour, use independent review, repair any failure, rerun the tests and give me one final evidence table."
```

MC-GPT compiles that goal into a bounded workflow:

```text
natural-language outcome
→ acceptance contract
→ authoritative task backend
→ specialist plan and challenge
→ isolated writer worktree
→ independent review seats
→ deterministic post-change tests
→ bounded repair when required
→ source, diff and evidence audit
→ technical completion, exact blocker, or Founder decision gate
→ brief or complete JSON / Markdown / CSV / XLSX report
```

A zero-eligible run is `noop`, one successful provider is never called consensus, progress telemetry cannot manufacture completion, and Founder Accept/Reject/Rework remains human-only.

There is one user-facing coder runtime (`iot-ai`). Benchmark treatments A–F are experimental arms selected only by the benchmark runner; they are not six products, services, commands, or engines.

```text
coder command
→ intake_and_normalization
→ reuse_first_precheck
→ optional_knowledge_context_adapter
→ native_mncg_decision
→ plan_or_execute
→ deterministic_verification_and_evidence
```

<p align="center">
  <img src="assets/brand/MC-GPT-Control-Plane-Infographic.webp" alt="MC-GPT Task, Meeting and Multi-Coder control-plane flow" width="100%" />
</p>

<p align="center"><sub>AI-generated visual supplied by the Founder and reviewed by Dr.-Ing. Babak Sorkhpour. <a href="assets/brand/MC-GPT-Control-Plane-Infographic.provenance.json">Provenance</a>.</sub></p>

## Try it in five minutes

### 1. Install the latest tagged wheel

Use an isolated `pipx` environment:

```bash
python3 -m pip install --user pipx
python3 -m pipx install \
  https://github.com/IoTAiTech/MC-GPT/releases/download/v6.7.0-beta.6/iot_ai_coder_suite-6.7.0b6-py3-none-any.whl
```

Published wheel SHA-256:

```text
18a752eddcfa9336152cfe72e8ab320372e021121f89e68dbe086474f8ab2807
```

### 2. Verify the CLI

```bash
python3 -m pipx runpip iot-ai-coder-suite show iot-ai-coder-suite
iot-ai --version
iot-ai help
iot-ai status
```

If your shell has not yet reloaded the user binary path, run the `iot-ai` executable from the path printed by `python3 -m pipx environment`.

### 3. Run the disposable fixture

```bash
git clone --depth 1 https://github.com/IoTAiTech/MC-GPT.git
cd MC-GPT/examples/quickstart-demo
python3 -m unittest discover -s tests -v

iot-ai \
  "Read TASK.md. Inspect this disposable fixture, produce a complete implementation and test plan, name the writer and independent review roles, but do not execute."
```

When at least one supported provider route is configured, run the governed implementation:

```bash
iot-ai \
  "Implement TASK.md in this disposable fixture. Preserve existing behaviour, use one authorised writer and independent review, run all tests on the post-change tree, repair bounded failures and return one complete evidence table."
```

The fixture contains no customer data, network dependency, database or external framework. See the complete [Quickstart](docs/quickstart.md), [Installation guide](docs/installation.md) and [nine-criterion demo contract](examples/quickstart-demo/TASK.md).

## Usage

The normal interface is the engineering outcome, not a memorised sequence of internal flags:

```bash
iot-ai status

iot-ai \
  "Finish the selected work, use every eligible coder, meet on failures, repair, retest and return one complete evidence table."

iot-ai \
  "Review the remaining work, explain the blockers and do not execute."
```

Advanced Task, Meeting, Multi-Coder, Mesh and Worktree commands remain available for diagnosis and controlled operations. See [USAGE.md](USAGE.md), [goal-first orchestration](docs/goal-first-orchestration.md) and the [autonomous closed-loop contract](docs/autonomous-closed-loop.md).

## What the final report contains

Every terminal run can emit brief or complete reports in JSON, Markdown, CSV and XLSX:

| Task | Authority | Acceptance evidence | Meeting | Models requested/served | Diff | Tests | Repairs | Final state | Remaining work | Next actor | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|

Provider participation is explicit: requested model, served model, authentication/readiness result, outage or fallback status, substantive contribution and latency. Missing identity is reported as **unverified**, never silently upgraded to a successful seat.

## Evidence and claim discipline

The live badges above represent hosted checks for the commit currently displayed by GitHub. Checked-in evidence files such as `FINAL_TEST_SUMMARY.json` apply only to the exact source revision and hashes named inside them; they are historical evidence unless explicitly regenerated for the current commit.

No package checksum, test count, provider installation, API health result or Meeting record is presented as proof of production readiness by itself.

## Supported execution routes

| Family | Typical role | Access path |
|---|---|---|
| Claude Code | architecture, synthesis, critique | provider-native subscription or configured API |
| OpenAI Codex CLI | implementation, debugging, review | ChatGPT subscription or configured API |
| Gemini CLI | large-context and cross-module review | Google subscription or configured API |
| Grok CLI | implementation and adversarial review | Grok subscription or configured API |
| Ollama local/cloud | exact model-specific specialist seats | configured Ollama route and privacy policy |

“Supported route” does not mean a provider participated in a particular run. Each run records requested, attempted, served and substantive seats separately.

## Safety and authority boundaries

- One task has one authoritative backend.
- ProductX/PMD work uses an authenticated, versioned API adapter; direct product-database access is forbidden.
- Parallel writers use isolated Git worktrees or exclusive path leases.
- One designated implementer writes; review seats remain read-only.
- Tests and review evidence must bind to the recorded post-change tree.
- Public export is allowlist-built and scanned for secrets, private infrastructure, personal paths and customer material.
- Public release, history replacement, destructive mutation, production deployment and Founder final acceptance remain explicit gates.
- Repair loops are bounded by failure fingerprints, time/token budgets and no-new-evidence limits.

Read [Security](SECURITY.md), [worktree orchestration](docs/worktree-orchestration.md), [Meeting](docs/meeting.md), [Multi-Coder](docs/multi-coder.md) and [autonomous closed loop](docs/autonomous-closed-loop.md).

## Community and Enterprise

| Capability | Community Developer Preview | Enterprise Customer Edition |
|---|---|---|
| Personal/noncommercial evaluation and research | Included | Included under contract |
| Company-internal operational or production use | Not licensed | Written commercial licence required |
| Standalone file-based tasks and reports | Included | Included |
| PMD/ProductX connector | Not included | Authenticated API adapter |
| Fleet/customer governance | Limited | Contracted feature set |
| Signed entitlement and expiry | No | Ed25519-verified |
| Direct PMD database access | Forbidden | Forbidden; API only |
| Customer deployment qualification | Not claimed | Required per deployment |

## Licence

**SPDX:** `PolyForm-Noncommercial-1.0.0` · **Official text:** [LICENSE](LICENSE) · **Operational guide:** [USAGE.md](USAGE.md)

This repository is source-available, not OSI open source. **GitHub’s Fork button does not grant commercial rights.**

| You may under the Community licence | Written commercial terms are required for |
|---|---|
| Personal use, study, hobby and noncommercial testing | Company-internal operational use |
| Noncommercial research | Production or customer deployment |
| Modify and keep a private noncommercial fork | Paid consulting, integration or support |
| Redistribute noncommercial copies with licence and notices | Hosting, SaaS, resale or commercial redistribution |

Commercial enquiries: [info@iot-ai.tech](mailto:info@iot-ai.tech) · [COMMERCIAL.md](COMMERCIAL.md).

## Competitive comparison

### Comparison methodology

The comparison is evidence-bounded and dated. **Quantitative** repository indicators such as stars, forks or release counts describe public adoption at the recorded date; they are not quality, performance or security benchmarks. **Qualitative** capability statements are limited to reviewed official public documentation. A feature described as **not evidenced in reviewed public documentation** is not claimed to be absent from a private edition or future release.

| Product or public surface | Publicly visible strength reviewed | MC-GPT relationship |
|---|---|---|
| Claude Code Agent Teams | provider-native teamwork and agent collaboration | MC-GPT focuses on cross-provider task authority, review separation and evidence |
| GitHub Copilot Fleet | GitHub-native agent workflow and repository integration | MC-GPT adds vendor-neutral provider/model receipts and local/Enterprise boundaries |
| Stably Orca | mature visual worktree and agent experience | MC-GPT adopts worktree isolation lessons while targeting stricter governed completion |
| AgentGem | portable agent/capability patterns across tool boundaries | MC-GPT uses an independent capability-pack design without copying source or assets |
| ServiceNow AI Control Tower | enterprise AI inventory and governance positioning | MC-GPT targets engineering execution, change proof and PMD/ProductX integration |

The detailed Stably Orca review, including historical ecosystem figures and explicit non-copying boundaries, is in [`docs/comparison/ORCA_COMPARISON.md`](docs/comparison/ORCA_COMPARISON.md). Other comparisons remain dated snapshots and must be refreshed before new marketing claims are made.

## What this `main` snapshot adds (2026-08-31)

Package lockstep is still IOT-AI Suite `6.8.0-beta.1` / MC-GPT `0.8.0-alpha.7`. These capabilities are on `main` and are not a new tagged wheel.

| Area | What operators get |
|---|---|
| GitHub Packages | Each annotated `v*` Release also publishes `ghcr.io/iotaitech/mc-gpt` and npm `@iotaitech/mc-gpt`. Python wheels stay on Releases. An org owner must flip GHCR/npm public once or the Packages tab stays empty. |
| Evaluation | Five-minute fixture in `examples/quickstart-demo/` and a demo-feedback issue form. |
| Minimum necessary change | Reuse-first gate, public schemas, skill `iot-ai-minimum-change`, and deterministic benchmarks. |
| Local Claude, Codex, Grok | Official `iot-ai multi-coder` pins the user-local CLIs, records served models, and returns exit 1 on `decision: blocked`. |
| GitHub analysis | `iot-ai github-analyze` judges technical, commercial, license and relevance. Ideas only; no dependency. |

New expert flags (full examples in [USAGE.md](USAGE.md)): `--quorum` on Multi-Coder and Meeting; `--plan` stays inspection-only; `github-analyze --offline-json` / `--no-network`.

Guides: [GitHub Packages](docs/github-packages.md) · [Minimum change gate](docs/minimum-necessary-change-gate.md) · [Local CLI seats](docs/local-cli-seats.md) · [Changelog](CHANGELOG.md).

## Honest current limitations

- The latest downloadable package is `6.7.0-beta.6`; the current source is ahead and must not be presented as an existing release asset.
- The public evaluation path is Linux-first; Windows and macOS are not currently advertised as qualified installation targets.
- A real Multi-Coder run depends on configured and live provider accounts; unavailable seats remain visible.
- GitHub Packages stay invisible on the public tab until an org owner sets GHCR and npm visibility to public once.
- Enterprise PMD schema recovery, customer PostgreSQL/RLS and fleet rollout are deployment-specific gates.
- The current public experience is CLI-first; a live visual workspace is roadmap work.
- Technical controls mapped to the EU AI Act, GDPR, CRA and NIS2 are not legal certification or a customer-specific conformity assessment.

See [release status](docs/status.md) and [roadmap](ROADMAP.md).

## Feedback and community

The most useful contribution is not a courtesy star—it is a reproducible five-minute evaluation:

1. run the fixture;
2. record where setup became unclear;
3. identify where you stopped trusting the result;
4. attach only sanitised evidence;
5. submit the [demo feedback form](https://github.com/IoTAiTech/MC-GPT/issues/new?template=demo_feedback.yml) or start a [Discussion](https://github.com/IoTAiTech/MC-GPT/discussions).

Security issues belong in [private vulnerability reporting](https://github.com/IoTAiTech/MC-GPT/security/advisories/new), not public Issues.

## Documentation map

- [Five-minute quickstart](docs/quickstart.md)
- [Installation](docs/installation.md)
- [Product guide](docs/PRODUCT_GUIDE.md)
- [Natural-language orchestration](docs/goal-first-orchestration.md)
- [Meeting reporting](docs/meeting-reporting.md)
- [Multi-Coder](docs/multi-coder.md)
- [Local Claude, Codex and Grok seats](docs/local-cli-seats.md)
- [Minimum necessary change gate](docs/minimum-necessary-change-gate.md)
- [GitHub Packages](docs/github-packages.md)
- [Supported coders and Ollama](docs/supported-coders-and-ollama.md)
- [Architecture](docs/architecture.md)
- [Compliance evidence](docs/compliance/README.md)
- [Repository map](docs/repository-map.md)
- [Changelog](CHANGELOG.md)
- [AI-assistant index](llms.txt)

## Founder and contact

**Dr.-Ing. Babak Sorkhpour** — Founder / Owner  
**IoT-AI.Tech**, Aschaffenburg, Bavaria, Germany  
[info@iot-ai.tech](mailto:info@iot-ai.tech) · [Company LinkedIn](https://www.linkedin.com/company/iot-ai-tech) · [Founder LinkedIn](https://www.linkedin.com/in/dr-babakskr) · [Company site](https://iotaitech.github.io/) · [MC-GPT product page](https://iotaitech.github.io/MC-GPT/)

For AI assistants and crawlers, start at [`llms.txt`](llms.txt) and [`docs/document-map.md`](docs/document-map.md). Do not infer private or Enterprise content from the public tree.
