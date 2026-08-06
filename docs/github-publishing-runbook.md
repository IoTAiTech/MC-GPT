<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.6.0-beta.3 | Date: 2026-08-06 -->

# GitHub Publishing Runbook

## What the coder is allowed to publish

From the private complete delivery, publish exactly:

```text
01_PUBLIC_GITHUB_REPOSITORY/       → Git repository content
04_RELEASE_ASSETS/COMMUNITY/       → GitHub prerelease assets
```

Never upload the complete delivery ZIP. Never copy Enterprise Customer source, vendor licensing tools, private evidence, customer material, internal infrastructure or credentials into the public Git tree—even in a temporary commit.

## Exact instruction to give a coder

Use `06_CODER_AND_GIT_COMMANDS/CODER_PUBLISH_PUBLIC_GITHUB_PROMPT.md` from the complete private delivery. It is the canonical publication prompt and contains the immutable allowlist, required gates, Founder confirmation and final-response contract.

## Prepare locally—no push

```bash
export GIT_AUTHOR_NAME="Dr.-Ing. Babak Sorkhpour"
export GIT_AUTHOR_EMAIL="<PUBLIC_GITHUB_NOREPLY_EMAIL>"

bash 06_CODER_AND_GIT_COMMANDS/PREPARE_PUBLIC_GITHUB.sh \
  01_PUBLIC_GITHUB_REPOSITORY \
  /tmp/iot-ai-public-v6.6.0-beta.3
```

This creates a fresh Git history, runs unit, pytest, warnings-as-errors, compile, identity, security, licence, public-boundary and repository gates, commits once and creates an annotated prerelease tag. It does not push.

## Publish directly to GitHub

Only after Founder review, set the literal confirmation and exact repository URL:

```bash
export IOT_AI_FOUNDER_CONFIRM="FOUNDER_PUBLISH_DEVELOPER_PREVIEW"

bash 06_CODER_AND_GIT_COMMANDS/PUBLISH_PUBLIC_GITHUB.sh \
  /tmp/iot-ai-public-v6.6.0-beta.3 \
  04_RELEASE_ASSETS/COMMUNITY \
  "https://github.com/<OWNER>/<REPOSITORY>.git"
```

The script refuses non-GitHub remotes, dirty worktrees, lightweight/missing tags, identity failures, public-boundary failures or missing Founder confirmation. It pushes `main`, pushes the annotated tag and uses `gh release create --prerelease --verify-tag` for Community assets.

## Mandatory gate details

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m pytest -q
python3 -W error -m pytest -q
python3 tools/brand_identity_check.py .
python3 tools/eu_ai_act_release_gate.py . --profile developer-preview
python3 tools/static_security_audit.py .
python3 tools/public_boundary_check.py . --git-history
python3 tools/check_license_headers.py .
python3 tools/verify_repository.py . --check-sbom
```

## Clone-back verification

The private delivery tests the same tree against a local bare remote and a fresh clone. The real GitHub Actions run is still an external gate and must attest the exact release assets downloaded from the GitHub prerelease.

## README comparison rules

Competitor claims must use official documentation, carry a comparison date, distinguish measurable facts from interpretation, use `not evidenced in reviewed public documentation`, and avoid universal superiority claims. The Orca comparison explicitly records where Orca is stronger today and where IOT-AI is designed to differentiate.

## Legal and compliance claim boundary

Do not publish a global `EU_AI_ACT_COMPLIANT` flag. The repository provides technical controls and evidence for the declared Developer Preview. Customer, high-risk, safety-critical and materially modified deployments require separate classification, legal review and runtime evidence.
