<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.6.0-beta.3 | Date: 2026-08-06 -->

# Application-Owned Agent Runtime

IOT-AI treats an agent turn as four application-owned parts in a bounded loop:

```text
Prompt → Context → Tool/Provider → Control-flow decision → Checkpoint
```

Framework defaults are not accepted as hidden authority. Every material turn produces hash-bound artifacts for the exact rendered prompt, selected context, route/model decision, validation, continuation and persistence decision.

## Runtime artifacts

| Artifact | Purpose |
|---|---|
| Goal contract | Outcome, why, context, constraints, verification and stop rules |
| Role contract | Specialist identity, mission, authority, forbidden actions and expected output |
| Node contract | Exact graph-node scope, dependencies, evidence, model and effort policy |
| Context manifest | Included/excluded blocks, hashes, privacy, tokens and compaction |
| Prompt artifact | Exact provider-visible prompt, version and SHA-256 |
| Tool decision | Eligible and rejected routes, live readiness and selected exact model |
| Validation decision | Output, schema, evidence and provider/model-binding checks |
| Continuation decision | Continue, stop, pause or bounded revision with reason |
| Persistence decision | What remains protected, public-safe or intentionally absent |
| Checkpoint | Pause/resume/replay state without repeating completed work |

## Five decisions per turn

```yaml
context_decision:
tool_decision:
validation_decision:
continuation_decision:
persistence_decision:
```

These decisions are written under the run correlation ID and validated by digest. Diagnostics exports redact private material while retaining the protected local evidence.

## Safety rules

- Static executable discovery never means live readiness.
- Exact served-model identity is mandatory for substantive provider output.
- A successful Ollama turn cannot qualify Claude, Codex, Gemini or Grok.
- D2/D3 goals or evidence do not enter cloud prompts without an explicit sanitised derivative.
- No context is silently truncated; compacted blocks retain a hash and protected-store pointer.
- Repeated identical failures, no-new-finding rounds, token limits and wall-clock limits stop the loop.
- Required-role failure blocks completion; optional-seat failure remains visible.
