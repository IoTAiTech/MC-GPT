<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.5.0-beta.2 | Date: 2026-08-05 -->

# Release Verification

## Source repository

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m pytest
python tools/public_boundary_check.py . --git-history
python tools/verify_repository.py . --check-sbom
```

## Downloaded artifact

```bash
python tools/verify_release.py <artifact> --sha256 <expected-sha256>
```

## Trust boundaries

A checksum proves byte identity, not publisher identity. Publisher identity additionally requires a trusted Git tag, GitHub release provenance/attestation or another approved signature. This Developer Preview includes the workflows and verification instructions, but local packaging is not a substitute for an attestation produced by the actual public GitHub repository.
