# Runtime settings v2 enforcement

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Date: 2026-09-04

The settings schema and skill router from PR #20 are not complete until the
runtime path proves them.

## MNCG

Plan acceptance requires `minimum_change_assessment_valid`. The native
evaluator recomputes selected and rejected rungs, evidence, controls, deltas,
budget exceptions and the verification plan. Writer binding compares the
accepted normalized assessment, including strategy, rejected-rung evidence,
dependency/service/schema/route/agent deltas, controls, budget exceptions,
verification plan, `assessment_sha256`, exact task revision, and
context-manifest digest. Same rung with a different delta is drift.

## Effort

The dispatch receipt is:

Settings → Candidate → Tool decision → Adapter request → Response → Final report

Empty stages fail the receipt. Effort is model-capability specific. OpenAI
GPT-5.6 supports `none` through `max`. Current Claude models use adaptive
thinking plus `output_config.effort` and reject `thinking.budget_tokens`.
Fallback routes do not copy the primary candidate effort.

## Provider catalog

Runtime names `claude`, `codex`, and `grok` map to catalog families
`anthropic`, `openai`, and `xai`. Alias resolution may set
`canonical_target_model` only. `model_served` stays empty until a provider
response. Catalog refresh is an offline-reviewed diff.

## Skills

Skill state is `discovered`, `eligible`, `selected`, `included_in_context`,
`truncated`, `actually_used`, `rejected`. Privacy is inherited from source.
`max_selected = 0` means zero skills. Receipts use opaque `root_id` plus
relative paths. Compatibility is enforced. Garden lock maps by exact skill
ID.

## Visual acceptance

Tool availability is a callable runner that passed a capability probe, not
Chrome-on-PATH. Evidence is real screenshot files whose SHA-256 is recomputed.
Model-authored hashes are rejected. If the runner cannot execute, the runtime
records `VISUAL_ACCEPTANCE_TOOL_UNAVAILABLE` and
`visual_acceptance_claim: false`.
