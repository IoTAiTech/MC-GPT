---
name: iot-ai-meeting
description: Automatic, governed full-hybrid meetings for planning, failures, repair decisions and final hard-judge review.
id: iot-ai-meeting
version: 1.0.0
category: general
license: LicenseRef-PolyForm-Noncommercial-1.0.0
---
# iot-ai-meeting

Meetings are an internal problem-solving engine, not an extra chore for the operator.

The orchestrator automatically opens a Meeting when:
- validation cannot converge;
- provider/model routes disagree or fail;
- deterministic tests fail;
- the same plan is not accepted by required seats;
- final audit or acceptance evidence is incomplete;
- a task requires a high-risk or release decision.

Use all configured eligible coder families and model-specific Ollama seats. A required agent seat must prove the semantic capability for its role (`meeting.opinion`, `meeting.critique`, `meeting.synthesis`, `meeting.review`, `meeting.receipt`); handler presence alone is insufficient.

Meeting success requires substantive contributions, exact served-model receipts, cross-critique, a frozen plan digest and required-seat acceptance. Empty, quota-blocked, timed-out, meta-only or model-unverified seats remain explicit failures.

Advanced views:

```text
brief/simple → decision, task table, provider participation, blockers, next actor
full/complete → complete contributions, critiques, digests, receipts, evidence and dissent
```
