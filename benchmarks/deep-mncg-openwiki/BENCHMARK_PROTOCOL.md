# Benchmark Protocol

## Objective

Determine whether the MC-GPT Minimum Necessary Change Gate preserves correctness and safety while reducing change surface, tokens, cost, or elapsed time. Separately estimate the value and full overhead of pinned OpenWiki repository knowledge.

## Experimental unit

One block is `task x provider slot x exact model x repetition x seed`. Every arm in a block uses the same task, common source commit and tree, fixture commit, model, effort, timeout, resource limits, tool policy, and verifier. Arm order is deterministically counterbalanced.

## Common-source amendment

No provider trial was executed under benchmark `mcgpt-mncg-openwiki-2026-01`. After PR 17 integrated MNCG and benchmark work into `main`, benchmark `mcgpt-mncg-openwiki-2026-02` replaced the source-split design before provider dispatch. Every arm now runs on commit `51cb72e27d013d14ef2e3435ed84a3514b33c170` and tree `81e3b88bb0005cad19b58e016ac3b50b5e8443cd`.

Only the registered treatment bundle may differ. Each trial receipt must bind the common source identity and the treatment-bundle digest.

## Isolation

- Use a fresh worktree or container and a fresh agent home for every trial.
- Keep hidden tests and reference solutions in an offline verifier.
- Never expose a prior-arm patch, conversation, cache, or result to another arm.
- Verify the common commit, common tree, fixture commit, and treatment bundle immediately before provider dispatch.
- Record image, package, CLI, model, source, prompt, treatment, environment, and patch digests.
- Permit an OpenWiki cache only when the task commit, OpenWiki digest, model identity, instruction digest, and integrity manifest all match.

## Treatment integrity

`A_BASELINE` receives only the unchanged task and common source. `B_SIMPLE_YAGNI` receives the registered short control. `C_PONYTAIL_PINNED` receives only the pinned upstream treatment. `D_MNCG` receives the task-bound MNCG contract. `E_OPENWIKI` receives the pinned generated wiki and managed instruction block. `F_MNCG_OPENWIKI` receives both MNCG and OpenWiki.

The baseline harness must suppress MNCG treatment delivery without changing source code, fixtures, tests, verifier, or provider policy. No arm may receive an arm-specific hint about the expected solution.

## OpenWiki accounting

Generate the wiki in an isolated clone. Record generation model identity, tokens, cost, and wall-clock time. Count wiki retrieval overhead separately and include all treatment overhead in total cost and total time.

## Correctness before efficiency

Efficiency is evaluated only on paired trials passing every hard gate. A faster failure is not an improvement. Every failure, timeout, exclusion, and infrastructure fault remains in the all-trials report.

## Public claim threshold

A public efficiency claim requires at least 30 valid paired blocks for the exact stated comparison, correctness noninferiority within the registered margin, no safety regression, exact model identity, full treatment overhead, per-task data, uncertainty, failure counts, exclusions, and independent review of the immutable result bundle.

Benchmark success does not authorize production deployment.
