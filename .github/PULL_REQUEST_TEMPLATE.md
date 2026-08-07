## Summary

## Why this change is needed

## Scope and ownership

- [ ] The change is limited to the declared scope.
- [ ] No private/Enterprise/customer material is included.
- [ ] Existing working behavior was preserved or the change is justified.

## Verification

- [ ] `python -m unittest discover -s tests -p "test_*.py"`
- [ ] `python -m pytest`
- [ ] `python tools/public_boundary_check.py .`
- [ ] `python tools/verify_repository.py .`
- [ ] New or changed behavior has deterministic tests.

## Security and privacy

- [ ] No secret values, private keys, private IPs, internal hostnames, personal paths, customer data, raw prompts, raw outputs, or private diagnostic dumps.
- [ ] Provider/model claims are backed by receipts or explicitly marked unverified.

## License

- [ ] Project-specific SPDX headers are preserved.
- [ ] Third-party notices were updated where required.
