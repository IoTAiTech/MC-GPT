<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->
# GitHub SEO and Release Readiness

## Recommended repository metadata

**Description**

> Governed multi-agent coding orchestration for Claude, Codex, Gemini, Grok and Ollama — task validation, hybrid execution, meeting reports, deterministic tests and audit.

**Website**

`https://iot-ai.tech`

**Recommended topics**

```text
ai-agents
multi-agent
multi-coder
agentic-coding
claude-code
openai-codex
gemini-cli
grok-cli
ollama
ai-governance
developer-tools
eu-ai-act
on-prem-ai
sovereign-ai
```

Repository topics and description are GitHub settings and must be applied by an authorised repository administrator; packaging scripts must not silently mutate them.

## Why the Releases tab can look stale

GitHub **Releases** lists annotated tags, not `main`. Current public tag: `v6.7.0-beta.6` (2026-08-15). Always compare:

1. https://github.com/IoTAiTech/MC-GPT/commits/main
2. https://github.com/IoTAiTech/MC-GPT/releases
3. [`CHANGELOG.md`](../CHANGELOG.md) Unreleased

## AI and crawler files

| File | Role |
|---|---|
| [`llms.txt`](../llms.txt) | llmstxt.org index for assistants |
| [`docs/document-map.md`](document-map.md) | Human table of public docs |
| [`robots.txt`](../robots.txt) | Allow public indexing |
| [`sitemap.xml`](../sitemap.xml) | Key URL list |
| [`CITATION.cff`](../CITATION.cff) | Citation metadata |

GitHub Pages is enabled from `docs/` on `main`. The home page is static `docs/index.html` (not Markdown, because `.nojekyll` is present) at `https://iotaitech.github.io/MC-GPT/`.

## Modern GitHub automation

| Workflow | Role |
|---|---|
| `.github/workflows/ci.yml` | Compile, public-boundary, EU AI Act gate, repository contract, pytest on Python 3.11–3.13 |
| `.github/workflows/security.yml` | Weekly public-boundary + SBOM |
| `.github/workflows/public-boundary.yml` | Full-history public/Enterprise boundary |
| `.github/workflows/codeql.yml` | Official GitHub CodeQL for Python |
| `.github/workflows/dependency-review.yml` | Official GitHub dependency review on pull requests |
| `.github/workflows/release.yml` | Annotated-tag Developer Preview assets |
| `.github/dependabot.yml` | Weekly pip and Actions updates |

Checkout pins disable persisted credentials. Release jobs do not cancel in-progress runs.


## Administrator application command

After Founder approval, an authorised administrator can apply the public metadata without changing source history:

```bash
gh repo edit IoTAiTech/MC-GPT \
  --description "Governed multi-agent coding orchestration for Claude, Codex, Gemini, Grok and Ollama — task validation, hybrid execution, meeting reports, deterministic tests and audit." \
  --homepage "https://iot-ai.tech" \
  --add-topic ai-agents \
  --add-topic multi-agent \
  --add-topic multi-coder \
  --add-topic agentic-coding \
  --add-topic claude-code \
  --add-topic openai-codex \
  --add-topic gemini-cli \
  --add-topic grok-cli \
  --add-topic ollama \
  --add-topic ai-governance \
  --add-topic developer-tools \
  --add-topic eu-ai-act \
  --add-topic on-prem-ai \
  --add-topic sovereign-ai
```

This command is a Founder-reviewed publication step. The private delivery does not execute it automatically.

## Mandatory pre-package GitHub check

1. Resolve the current default-branch SHA and compare it with the candidate source SHA.
2. Inspect open PRs, unresolved review threads, Dependabot/security alerts and CodeQL findings.
3. Confirm CI and security workflows exist and use reviewed commit-pinned actions.
4. Run current-tree and full Git-history privacy/security scans.
5. Verify README, package metadata, citation metadata, changelog, release notes, tags and artifacts use the same version.
6. Verify Community/Enterprise/customer/private boundaries.
7. Build twice and prove deterministic artifacts.
8. Install from clean Linux and Node bootstrap paths; run normal rollback.
9. Simulate annotated tag, bare remote, clone-back and test replay.
10. Re-check GitHub immediately before final delivery and record the observed SHA.

## Public release assets

Only the allowlist-built Community source and Community release assets may be attached to a public prerelease. The complete private delivery, Enterprise implementation, vendor signing tools, customer data, raw meeting databases, private evidence and diagnostic archives are prohibited.

## Release title and search summary

```text
IOT-AI Suite 6.7.0-beta.6 / MC-GPT 0.8.0-alpha.6 — Natural-Language Multi-Agent Coding Developer Preview
```

The release notes should begin with the exact supported provider families, task-validation/hybrid-execution distinction, federated Meeting reporting, clean installation and claim boundary. Do not claim production readiness, legal certification, universal model availability or fleet-wide compliance.
