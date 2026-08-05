<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.5.0-beta.2 | Date: 2026-08-05 -->

# Research Adoption: Agent Internals and Goal-Based Loops

## Source-derived concepts

The Hanako material describes the hidden runtime decisions behind an agent turn: render the prompt, choose and trim context, load/select tools, fill arguments, wait/truncate/retry, evaluate, continue/stop, compact, persist, spawn subagents and select the visible result. The verified core principle is that production systems must own prompt, context, tools and control flow.

The exact Mahaximus X post could not be independently retrieved through the available public mirrors. Related indexed material on goal mode describes autonomous execution from one concrete outcome, bounded scope, tests, measurable success criteria and explicit constraints. This document treats that related material as corroborating context, not a verbatim reconstruction of the unavailable post.

## IOT-AI implementation mapping

| Concept | Implementation |
|---|---|
| One goal, outcome over path | `goal_contract.py` |
| Exact rendered prompt | `prompt_compiler.py` |
| Addressable context and no silent truncation | `context_compiler.py` |
| Explicit route/model/tool decision | `tool_router.py` and `owned_delegate.py` |
| Continue/retry/stop owned by application | `control_flow.py` |
| Five decision receipts | `decision_receipts.py` |
| Pause/resume and durable state | `checkpoints.py` |
| Dependency-aware parallelism | `graph_runtime.py` |
| Specialist identity before provider selection | `roles.py` |
| Meeting and Multi-Coder compatibility | `meeting.py`, `multicoder.py`, `owned_delegate.py` |

## Non-adopted claims

- No claim that autonomous looping is always faster or cheaper.
- No use of open-ended loops without token, time, failure and human-approval limits.
- No assumption that a stronger model is automatically safer.
- No use of all providers or all tools on every task.
- No replacement of deterministic tests, database authority or human responsibility with model consensus.
