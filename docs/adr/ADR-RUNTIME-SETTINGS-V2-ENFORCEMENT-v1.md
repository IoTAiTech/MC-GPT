# ADR: Runtime enforcement for settings v2 and the skill router

Status: Accepted
Date: 2026-09-04
Author: Dr.-Ing. Babak Sorkhpour, with AI assistance

## Decision

PR #20 landed the settings authority and skill router. This change binds those
contracts to the live runtime path:

- Plan acceptance recomputes MNCG with `assess_strategy()`.
- Implementation is hard-bound to the accepted selected rung.
- Provider dispatch uses `candidate.effective_effort` only.
- Skill privacy is inherited from source; truncated skills are not `actually_used`.
- Unknown schemas fail closed. Booleans are not integers. Model and provider
  caps are independent. Migration and rollback are locked, revisioned, and
  read back.
- `design-quality` requires visual evidence or records
  `VISUAL_ACCEPTANCE_TOOL_UNAVAILABLE`.
- Garden-derived skills are verified against `governance/garden-skills.lock.json`
  at load.
- Provider/model aliases, retirements, client floors and ZDR are catalogued.

PR #19 remains untouched. No tag or release is created by this change.
