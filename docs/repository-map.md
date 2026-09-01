<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.6.0-beta.3 | Date: 2026-08-06 -->

# Repository Map and What Goes to GitHub

## Public repository

The public Git repository contains this tree only:

```text
src/                 Community runtime
schemas/             public contracts
installers/          Linux and Windows clean installers
skills/              public iot-ai skills
benchmarks/          MNCG and OpenWiki contract (treatments, not products)
assets/brand/        canonical MC-GPT brand asset
examples/            secret-free examples
scripts/             user-safe helper scripts
docs/                public product, install, use and compliance documentation
tests/               public deterministic tests
tools/               public release/security verifiers
.github/             CI, issue and pull-request templates
```

## Never publish from the private delivery

```text
02_ENTERPRISE_CUSTOMER_PRIVATE/
03_VENDOR_LICENSING_PRIVATE/
private evidence or diagnostics
customer data or contracts
issuer private keys
internal hostnames, IP addresses or personal paths
legacy server snapshots
```

## Exact instruction to a coder

```text
Publish only the contents of 01_PUBLIC_GITHUB_REPOSITORY as the repository,
and only 04_RELEASE_ASSETS/COMMUNITY as GitHub prerelease assets. Run all
public identity, secret, privacy, licence, security, EU-AI-Act technical,
Git-history and clone-back gates. Never upload the complete private delivery
ZIP or any Enterprise/vendor folder. Stop before push unless the Founder gives
FOUNDER_PUBLISH_DEVELOPER_PREVIEW.
```

Use `docs/github-publishing-runbook.md` and the canonical prompt in the complete private delivery.

- `llms.txt` — AI crawler index (llmstxt.org).
- `docs/document-map.md` — human table of public docs.
- `docs/autonomous-closed-loop.md` — natural-language Task → Meeting → Multi-Coder lifecycle and terminal rules.
- `assets/brand/MC-GPT-Control-Plane-Infographic.webp` — public README infographic with provenance sidecar.
