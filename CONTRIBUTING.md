# Contributing

This repository is **Source Available — Not Open Source**. The public license does not grant a general right to modify, distribute, fork or create derivative works.

## What anyone may submit

- Sanitized bug reports.
- Reproduction steps using public/example data.
- Feature proposals.
- Security reports through the private vulnerability channel.
- Documentation corrections suggested in an issue.

## Code contributions

Code pull requests are accepted only after written maintainer approval and the required contribution agreement or assignment. Do not create or distribute an unauthorized product fork. A GitHub Fork button is a technical platform feature and does not expand the license grant.

## Approved development flow

1. Open an issue and obtain maintainer approval for the scope.
2. Use an authorized branch or contribution workflow.
3. Preserve unrelated behavior and public/private boundaries.
4. Add happy-path, boundary and failure tests.
5. Run:

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m pytest
python tools/public_boundary_check.py .
python tools/verify_repository.py .
```

6. Use Conventional Commits.
7. Do not include secrets, private infrastructure, customer data, private paths, Enterprise source or private evidence.

Submitting material does not grant commercial, production, redistribution, hosting, resale or derivative-work rights.
