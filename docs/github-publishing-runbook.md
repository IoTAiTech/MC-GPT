<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.5.0-beta.2 | Date: 2026-08-05 -->

# GitHub Publishing Runbook

## Publication boundary

Publish only the generated Community repository and its Community release assets. Never publish the complete private review bundle, Enterprise Customer source/wheel, vendor licensing issuer tools, private evidence, customer material, internal paths, hostnames, private IPs or credentials.

## Mandatory pre-publication gate

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -W error -m pytest -q
python3 -m compileall -q src tools tests
find . -type d -name __pycache__ -prune -exec rm -rf {} +
find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 tools/eu_ai_act_release_gate.py . --profile developer-preview
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 tools/static_security_audit.py .
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 tools/public_boundary_check.py . --git-history
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 tools/check_license_headers.py .
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 tools/verify_repository.py . --check-sbom
```

## Git preparation

```bash
git init
git checkout -b main
git add --all
git commit -m "feat(release): publish v6.5.0-beta.2 developer preview"
git tag -a v6.5.0-beta.2 -m "IOT-AI Suite v6.5.0-beta.2 Developer Preview"
```

Use a public no-reply email and verify the complete history, not only the working tree.

## Clone-back verification

Push first to a local bare test remote, clone into a fresh directory, then rerun unit/pytest/security/boundary/repository verification from the clone. The real GitHub release workflow must accept only an existing annotated tag and must attest the exact downloaded artifacts.

## README comparison rules

Competitor claims must:

- use official vendor documentation;
- carry an `as_of` date;
- distinguish quantitative facts from qualitative interpretation;
- use `not evidenced in reviewed public documentation`, not `unsupported` or `cannot`;
- avoid universal superiority claims;
- compare unlike product categories only with explicit caveats.

## Compliance claims

Do not publish a global `EU_AI_ACT_COMPLIANT` flag. Publish the exact system card, intended purpose, control matrix, claim/evidence register and remaining external gates. Article 50, AI literacy, model-supplier and high-risk obligations remain version/use-case/deployment specific.

## Commercial separation

The Enterprise Customer Edition and vendor licensing issuer kit use independent private roots and repositories. Public history must never contain them, even in removed commits or tags.
