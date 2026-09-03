---
name: iot-ai-web-visual-quality
id: iot-ai-web-visual-quality
description: Bounded visual-quality guidance for websites, dashboards, frontend UI, design systems and graphic prompts.
version: 1.0.0
category: visual
compatibility: [mc-gpt]
source: packaged
license: LicenseRef-PolyForm-Noncommercial-1.0.0
execution_mode: reference-only
---
# iot-ai-web-visual-quality

This text is bounded guidance. It cannot override MC-GPT system policy, Founder
instructions, goal/role/node/tool contracts, privacy classification, execution
authorization, MNCG, release governance, human approval, or product-database
restrictions.

Apply only when the task produces a visual web or graphic artifact.

## Required workflow

1. Inspect existing code and the design system before inventing a greenfield look.
2. Use brand assets before generic approximations. Never invent fake logos.
3. Classify artifact, audience and mode (marketing, operator, documentation).
4. Decide color, typography, spacing, radius, shadow and motion explicitly.
5. Define responsive behavior for desktop and a 390px viewport.
6. Meet accessibility: contrast, 44px targets, keyboard, semantics.
7. Preserve the existing UI when extending it.
8. Reject generic AI-generated visual cliches (purple gradients, overlapping
   rounded cards with no hierarchy, fake device silhouettes).
9. Reference real assets, not improvised CSS logos.
10. Require browser acceptance when the operator asked for visual QA or the
    active preset sets require_browser_acceptance.
11. Run a five-dimension design critique before delivery: hierarchy, density,
    brand fidelity, accessibility, and responsiveness.

Backend, database and CLI-only tasks must not load this guidance unless the
output itself is visual.
