# IOT-AI Coder Suite 6.6.0-beta.3 — First Public Developer Preview Candidate

This immutable revision consolidates the corrected IoT-AI.Tech identity, task validation before execution, first-class Ollama Cloud meeting policy, governed worktree isolation, source-grounded Orca comparison, personal/noncommercial research licensing, and a fail-closed GitHub publication workflow into one authoritative release lineage.

## Core workflow changes

- `claim`, `execute`, `run`, `go`, `solve-all` and Multi-Coder task execution are guarded by an evidence-bound **Task Validation** decision.
- The user may validate and optimise the task, explicitly use the original task, or cancel. High-risk bypass requires a Founder-scoped risk-acceptance receipt.
- Validation reviews screenshots, documents, logs, code and prior evidence; produces 5W1H, KPI/SLA, ten use cases, ten tests, ten failure cases and one frozen plan digest.
- Full-council Meeting selection automatically includes eligible model-specific Ollama Cloud seats. Omission is blocked or must be explicitly recorded.

## Community licensing

The public source uses PolyForm Noncommercial 1.0.0. Personal use, noncommercial research, study, modification, forks and noncommercial redistribution are permitted under the licence and notices. Company-internal production, paid services, hosting, resale and commercial forks require a written commercial licence from IoT-AI.Tech.

## Supported execution families

- Claude Code
- OpenAI Codex CLI
- Gemini CLI
- Grok CLI
- Ollama local/cloud as a first-class, model-specific gateway

Provider names are not roles. Specialist identity, mission, authority, read/write scope and expected output are bound before selecting a provider/model.

## Honest Orca comparison

Orca is currently the stronger benchmark for desktop/mobile experience, terminals, diff UX, Design Mode, remote worktrees, GitHub/issue integration and broad CLI-agent support. IOT-AI adopts worktree isolation and usage visibility patterns while differentiating on immutable specialist contracts, exact provider/model truth, mandatory Ollama governance, digest-bound decisions, Task/Assignment/ACK/Lease evidence, Enterprise entitlements, privacy boundaries and EU-focused release controls. No Orca source, assets, protocols or branding are copied.

See `docs/comparison/ORCA_COMPARISON.md`.

## GitHub publication boundary

Publish only:

```text
01_PUBLIC_GITHUB_REPOSITORY/
04_RELEASE_ASSETS/COMMUNITY/
```

Never publish the complete private delivery, Enterprise source, vendor licensing issuer, private evidence or customer material. Use the canonical prompt and scripts in `06_CODER_AND_GIT_COMMANDS/`.

## Verification

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m pytest -q
python -W error -m pytest -q
python tools/brand_identity_check.py .
python tools/eu_ai_act_release_gate.py . --profile developer-preview
python tools/static_security_audit.py .
python tools/public_boundary_check.py . --git-history
python tools/check_license_headers.py .
python tools/verify_repository.py . --check-sbom
```

## Claim boundary

This is a Community Developer Preview candidate—not stable, not production-ready, not a legal certification and not a blanket EU AI Act conformity claim. Windows on-device, live provider/model receipts, GitHub-hosted attestation, Enterprise cryptography/PostgreSQL qualification and deployment-specific German legal review remain external gates.
