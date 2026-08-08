# IOT-AI Coder Suite 6.7.0-beta.4 — Private Release Candidate

This candidate advances the verified private `6.7.0-beta.3` delivery to GitHub `main@11fa3c840744d953cee183c529040ad27ffb7dbc` and closes post-delivery security, Task-UX, Meeting-reporting, packaging and GitHub discoverability gaps.

## Release highlights

- Fail-closed, path-constrained file hashing for operator-selected evidence and package paths; symlinks, root widening, non-regular files and oversized untrusted inputs are rejected.
- Federated read-only Meeting reports across explicitly supplied current and legacy SQLite stores, with stale-session detection, approval/status conflict reporting, ANSI cleanup and legacy-model uncertainty labels.
- One command family for short and complete views plus JSON, CSV, Markdown, XLSX and deterministic report bundles.
- Honest Task semantics: `tasks authorize-execution` is validation only; `tasks run --mode hybrid` is actual Multi-Coder implementation.
- Verified clean install through local HTTP `curl`, `npx` and local `npm install`, with SHA-256 tamper rejection and ordinary rollback.
- Eight Python command entry points in the clean-room wheel, including Meeting, Tasks and Multi-Coder wrappers.
- README badges, improved search terms, corrected CODEOWNERS, richer package metadata and explicit GitHub release hygiene.

## Verification summary

```text
source unittest                  205 / 205 PASS
source pytest                    205 / 205 PASS
pytest warnings-as-errors        205 / 205 PASS
focused security/report tests     27 / 27 PASS
branch-aware coverage                  72%
static security findings                 0
public current-tree findings              0
local Git-history findings                0
black-box release steps             15 PASS
restricted meetings federated           117
clean curl / npx / npm installs          PASS
deterministic dual build                 PASS
```

The real report sample revealed 16 stale `running` sessions, 17 Founder-approval/status conflicts and 112 meetings whose legacy exact served-model telemetry is incomplete. The new reporter exposes these conditions without rewriting the source databases or pretending that missing model identity is verified.

## Release boundary

This is a Community Developer Preview candidate and complete private delivery. It is **not** a stable/production release, legal certification, blanket EU AI Act conformity statement or authorization for fleet/customer deployment.

No beta.4 Git push, public tag or GitHub Release has been performed. Public publication requires explicit Founder approval and a fresh GitHub check. Real GitHub Actions attestation, Windows on-device testing, live exact-provider/model qualification, customer PMD/PostgreSQL qualification and deployment-specific legal review remain external gates.

`6.7.0-beta.2` remains a permanent aborted tombstone and must never be reused.
