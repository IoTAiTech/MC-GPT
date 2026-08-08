# Public Repository Agent Rules

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 6.7.0-beta.4

1. Read `LICENSE_POLICY.json`, `EDITION_BOUNDARY.json`, `SECURITY.md` and the nearest task scope before writing.
2. Never infer MIT or another license. Resolve the project-specific license or stop.
3. Never add Enterprise source, customer data, secrets, private IPs, internal hostnames, personal paths or private evidence.
4. Use the smallest relevant skills and agents. Do not force full fan-out for routine work.
5. Bind every agent to a role, mission, authority, forbidden actions, evidence requirements, output schema and read/write scope.
6. Use isolated worktrees or exclusive path leases for parallel writers.
7. Deterministic evidence outranks model consensus.
8. Never claim a provider/model seat succeeded without a live, exact requested/served-model receipt.
9. Preserve raw private evidence outside the public repository; public diagnostics must be sanitized.
10. Run tests and `tools/public_boundary_check.py` before proposing a public commit.
