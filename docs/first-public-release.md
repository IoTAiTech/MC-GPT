<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.6.0-beta.3 | Date: 2026-08-06 -->

# First Public GitHub Release

## Release classification

`Community Developer Preview` · `Source Available — Not Open Source` · personal/noncommercial evaluation only.

## Public repository contents

- Community source, tests, docs and examples.
- GitHub CI/security/release workflows.
- SBOM, notices, checksums and release-verification tools.
- No Enterprise source, PMD private adapter, entitlement issuer, signing private key, private evidence or customer data.

## Maintainer release sequence

1. Start from the allowlist-built public tree.
2. Run unit, pytest, boundary and repository checks.
3. Inspect `git diff --cached` before every commit.
4. Create an annotated tag.
5. Push the branch and tag only after the local release checklist passes.
6. Allow GitHub Actions to build from the tag.
7. Publish as a prerelease, not stable.
8. Verify downloaded assets and checksums.
9. Enable GitHub private vulnerability reporting, secret scanning and push protection where available.

## Required local commands

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m pytest
python tools/eu_ai_act_release_gate.py . --profile developer-preview
python tools/public_boundary_check.py . --git-history
python tools/verify_repository.py . --check-sbom
python tools/build_release.py . dist
```

## Forbidden publication material

- `enterprise/`, `private/`, `customer/`, `evidence-private/`, `secrets/` or private release roots.
- Credentials, tokens, keys, private IPs, internal hostnames and personal paths.
- Raw prompts, raw outputs, unsanitized diagnostics or customer data.
- Private Git history or internal operational evidence.

## EU AI Act publication boundary

The public release may state only that it contains compliance-enabling controls for its declared Developer Preview purpose. It must not claim full EU AI Act compliance, certification, conformity assessment or applicability to customer/high-risk deployments. Publish the system card, intended-purpose limitations, Article 5/50 controls, AI-literacy programme, supplier register, human-oversight policy, post-market/incident process and claim-evidence register.
