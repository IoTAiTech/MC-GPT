# Runtime settings v2 enforcement

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Date: 2026-09-04

The settings schema and skill router from PR #20 are not complete until the
runtime path proves them.

## MNCG

Plan acceptance requires `minimum_change_assessment_valid`. The native
evaluator recomputes selected and rejected rungs, evidence, controls, deltas,
budget exceptions and the verification plan. Implementation cannot select a
later rung than the accepted plan.

## Effort

The dispatch receipt is:

Settings → Candidate → Tool decision → Adapter request → Response → Final report

All stages must record the same `effective_effort`.

## Skills

Skill state is `discovered`, `eligible`, `selected`, `included_in_context`,
`truncated`, `actually_used`, `rejected`. Privacy is inherited from source.
`max_selected = 0` means zero skills.

## Visual acceptance

When `require_browser_acceptance` is set and the task is visual, the runtime
either collects viewport screenshots, overflow/clip, accessibility, loading
/empty/error states and a critique, or it records
`VISUAL_ACCEPTANCE_TOOL_UNAVAILABLE` and `visual_acceptance_claim: false`.
