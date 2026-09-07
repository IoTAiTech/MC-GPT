<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 1.0.0 | Date: 2026-09-04 -->
# Evaluate the installed product, not just the source checkout

MC-GPT has one coder runtime. Task validation, Meeting, Multi-Coder, settings,
skills and MNCG participate in that runtime; benchmark arms are experiments,
not separate products.

## Distribution contract

A successful source test does not qualify a downloadable package. Both the
setuptools build and the offline wheel builder must include the same reviewed
skills, Garden lock and third-party notices. The wheel metadata must use
`project.version` from `pyproject.toml`, not a historical release constant.

The build-time collector in `tools/package_assets.py` accepts only data files
under the repository's `skills/` tree. It rejects symlinks, oversized files,
unapproved member names, changed Garden digests and inventory mismatches. It
never loads user skills, runs third-party scripts or contacts a provider.

Installed locations are internal package resources:

```text
iot_ai/data/skills/
iot_ai/data/governance/garden-skills.lock.json
iot_ai/data/governance/THIRD_PARTY_NOTICES.md
```

These locations match the existing skill registry. They do not introduce a
second registry, configuration authority or network updater.

## Reproduce the packaging evaluation

From a reviewed source checkout with the documented development dependencies:

```bash
python -m pytest -q tests/test_distribution_asset_parity.py
python tools/build_wheel.py . dist
python -m pip wheel --no-deps --no-build-isolation . --wheel-dir dist-setuptools
```

Install only the candidate selected by an operator into a fresh environment.
Check distribution metadata and CLI version. Run skill discovery from a working
directory outside the source checkout. The tests deliberately use isolated
Python so imports cannot silently fall back to repository files.

The checks cover deterministic offline builds, wheel RECORD integrity, reviewed
asset byte equality, isolated discovery, tampering, missing or unlisted Garden
files, executable files, symlinks and oversized inputs. Full provider workflows,
visual acceptance, upgrades and production deployment need separate evidence.

## Release gate

A candidate build is not a published release. Preserve the current license and
public/private boundary. Do not upload a private package, change an existing
release asset, or tag this work merely because tests pass. Require independent
review and exact-head CI. A later release must be built from its approved tag,
downloaded back, hashed, installed and tested outside the source checkout.

## First user experience

The landing page should offer two honest paths: a no-key package evaluation and
a separately authorized provider run. Do not label an offline fixture as a live
multi-provider demonstration. A final run report should distinguish installed
assets, attempted provider calls, verified served identities, completed tests,
remaining blockers and the human acceptance decision.
