# MC-GPT investor brief — evidence-backed draft

As of 2026-09-06. **Pre-release; not a fundraising representation or sales offer.**
Customer names, paid pilots, revenue, retention, pricing, market size and funding
ask have not been substantiated in this review. They must remain unverified until
the Founder supplies evidence and approves their use.

## Thesis

Engineering teams adopting coding agents need to know which change was tested,
under whose authority, with what independent review, and what is still blocked.
MC-GPT's proposed value is an evidence-first workflow around coding tools the team
already uses: one task contract, controlled implementation, post-change checks,
review and an inspectable completion record.

The investable hypothesis is reduced human coordination and verification effort
per accepted change, without increasing false completion, escaped defects or
data exposure. This is a testable hypothesis, not an established performance claim.

## Initial buyer and product

Start with engineering/platform leads maintaining mixed-provider Linux/Git/CI
tooling, using bounded, non-production maintenance tasks in disposable evaluation
repositories. The intended deliverable is a reviewable change plus exact evidence
and explicit blockers. Exclude safety-critical operation, unattended customer
production mutation and unqualified enterprise connectors from the initial offer.

Community evaluation is governed by [the current licence](../LICENSE). Company
operational use needs [written commercial terms](../LICENSE-COMMERCIAL.md).
Potential paid offerings are deployment qualification, supported governance
integration and contracted support; pricing, packaging and margins are hypotheses.

## Competitive reality

Multi-agent orchestration alone is not a defensible moat.

| Alternative | Publicly documented capability | What MC-GPT must prove |
| --- | --- | --- |
| [Claude Code agent teams](https://code.claude.com/docs/en/agent-teams) | Coordinated sessions, shared tasks and messaging; documented as experimental | Incremental value beyond native coordination |
| [OpenHands Enterprise](https://www.openhands.dev/enterprise/) | Vendor describes model choice, controlled execution, RBAC, budgets, reporting and self-hosting | Easier adoption or measurably stronger evidence economics for a specific buyer |
| [Aider](https://aider.chat/docs/usage/lint-test.html) | Configurable lint/test feedback and repair | Value beyond a simpler test-and-repair workflow |

These are primary-source descriptions, not independent competitor benchmarks.
No competitor code is copied, vendored or made a new dependency by this analysis.
The differentiation candidate is evidence that remains trustworthy across reruns,
repairs, model changes and task revisions—not unsupported superiority claims.

## Proof and limitations

Current engineering work tests stale-evidence rejection, task/source binding,
concurrent-state preservation, bounded output and installation integrity. A
synthetic-provider end-to-end test demonstrates local workflow plumbing, not
customer productivity or cross-provider reliability. [Product readiness](product-readiness.md)
lists the remaining delivery, security and legal gates.

## Validation plan and funding milestones

1. Interview target buyers about existing review effort, failure modes, procurement
   barriers and willingness to pay. Record counterexamples, not just endorsements.
2. Have an unfamiliar operator complete fresh installation and a fixture evaluation
   without maintainer intervention; measure time, errors and comprehension.
3. Pre-register matched tasks against the buyer's current tools. Measure accepted
   changes, reviewer minutes, retries, provider cost, escaped defects and false
   completion. Freeze criteria before the comparison; preserve unsuccessful runs.
4. Exercise stale receipts, unavailable providers, cancellation and recovery. Require
   a second operator to reproduce the result from the evidence bundle.
5. Offer only an authorized paid pilot with a written scope, support/rollback plan,
   privacy terms and acceptance. Expand only after documented repeatability.

A future pitch can present the buyer problem, observed baseline, product demo,
measured improvement, competitive trade-offs, pilot economics, team capacity and
funding use. Until those measurements exist, do not publish invented traction,
TAM, conversion, savings, valuation or guaranteed business outcomes.
