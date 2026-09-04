# ADR: Runtime enforcement for settings v2 and the skill router

Status: Accepted
Date: 2026-09-04
Author: Dr.-Ing. Babak Sorkhpour, with AI assistance

## Decision

PR #20 landed the settings authority and skill router. This change binds those
contracts to the live runtime path:

- Plan acceptance recomputes MNCG with `assess_strategy()`.
- Implementation is hard-bound to the accepted normalized assessment, task
  revision, and context-manifest digest, not only the selected rung.
- Provider dispatch uses `candidate.effective_effort` only. Empty receipt
  stages fail closed. Anthropic current-gen uses adaptive thinking plus effort.
- Skill privacy is inherited from source; truncated skills are not `actually_used`.
- Unknown schemas fail closed. Booleans are not integers. Model and provider
  caps are independent. Migration, preset apply, and rollback are one locked
  transaction with optimistic concurrency and read-back.
- `design-quality` requires a probed visual runner and real screenshot files,
  or records `VISUAL_ACCEPTANCE_TOOL_UNAVAILABLE`.
- Garden-derived skills are verified against `governance/garden-skills.lock.json`
  at load using an exact skill-ID mapping.
- Runtime providers `claude`/`codex`/`grok` normalize to catalog families
  `anthropic`/`openai`/`xai`. Alias resolution sets `canonical_target_model`
  only; `model_served` is unset until a provider response.

PR #19 remains untouched. No tag or release is created by this change.
