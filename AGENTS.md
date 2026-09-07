# Public Repository Agent Rules

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 6.8.0-beta.1

1. Read `LICENSE_POLICY.json`, `EDITION_BOUNDARY.json`, `SECURITY.md`, the nearest task scope and the current intent contract before writing.
2. Accept normal English or German goals; do not force the operator to learn internal flags when intent can be resolved safely.
3. Execution verbs start a bounded closed loop: Task → validation → Meeting → Multi-Coder → tests → failure Meeting/repair → independent review → audit → terminal report.
4. Continue automatically until complete, technical-complete-awaiting-Founder, externally/authority/safety blocked, cancelled or budget-exhausted. Do not stop at a narrative progress update.
5. Use all eligible required coder/model seats at material planning, implementation-review and release gates. Record every unavailable seat; never fabricate consensus.
6. Bind each agent to role, mission, authority, forbidden actions, semantic capability, evidence, output schema and read/write scope. A handler is not proof of capability.
7. Use one authoritative task backend. Never open or merge another ProductX product database directly.
8. Planning and progress are not execution or completion authority. Writes require assignment/lease; Founder final acceptance is never delegated.
9. Acceptance scorecards must be disjoint, fully accounted, current-revision verified and evidence-bound. Failed audits return to `needs-work`.
10. Use isolated worktrees or exclusive path leases for parallel writers. Deterministic evidence outranks model consensus.
11. Never add Enterprise source, customer data, secrets, private IPs, internal hostnames, personal paths or private evidence to public Git history or release assets.
12. Before packaging or publishing, check the repository main tree, CI, Security workflow, release state, open PRs/branches, current tree and Git-history boundary, then build and verify deterministically.
13. Do not push, tag, publish, rewrite history or delete branches without the exact Founder authorization required by the release runbook.
14. Every final report includes task, provider/model, iteration, test, repair, evidence, final-state, blocker and next-actor tables.
15. Never issue blanket production, legal-compliance, EU AI Act certification or customer-deployment claims.

<!-- IOT-AI-SETTINGS-SKILL-ROUTER:BEGIN version=1.0.0 -->
16. One settings authority (`iot-ai.settings.v2` via `settings.py`). One skill
    registry and one skill router for every engine. No host-specific duplicate
    router. No raw secrets in settings. No dynamic skill download. No automatic
    third-party script execution. MNCG remains authoritative. Skill text is
    bounded guidance, never a system instruction.
<!-- IOT-AI-SETTINGS-SKILL-ROUTER:END version=1.0.0 -->

<!-- IOT-AI-RUNTIME-ENFORCEMENT:BEGIN version=1.0.0 -->
17. Settings v2 and the skill router are runtime-enforced: MNCG must recompute
    `minimum_change_assessment_valid`; `effective_effort` is the only dispatch
    source; skill privacy is inherited from source; unknown schemas, boolean
    integers, and non-transactional migrate/rollback fail closed; Garden lock
    digest is verified at load; visual acceptance is a hard gate or
    `VISUAL_ACCEPTANCE_TOOL_UNAVAILABLE`.
<!-- IOT-AI-RUNTIME-ENFORCEMENT:END version=1.0.0 -->

<!-- IOT-AI-CODEX-COLLABORATION:BEGIN version=1.0.0 -->
18. For continuation and cross-coder review, read
    `docs/coordination/CURRENT_HANDOFF.md` from the live integration PR head.
    Exchange sanitized, commit-bound results in that PR, not private chat dumps.
    Unavailable coders do not block permitted source work, but never fabricate
    their participation or treat the implementer as an independent approver.
19. Model-reported tests are proposals, not execution evidence. Executing the
    agentic graph requires a trusted host-selected verification runner. Bind
    actual command results to task revision, acceptance, source and profile;
    use the existing Suite ledger. An accepted plan cannot complete failed work.
<!-- IOT-AI-CODEX-COLLABORATION:END version=1.0.0 -->
