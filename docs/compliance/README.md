# EU AI Act technical compliance pack

This directory binds technical controls to the exact IOT-AI Suite version and declared Community Developer Preview purpose. It is **not** a legal certificate, CE marking, conformity assessment, or statement that every ProductX/customer deployment complies.

## Binding principles

1. Classify the exact system, version, operator role, intended purpose and deployment.
2. Block Article 5 operational requests before any model or tool call.
3. Inform natural persons at first direct AI interaction.
4. Mark human-exposed generated content using embedded provenance where supported and a hash-bound sidecar for every file.
5. Preserve human review, editorial responsibility and visible labels for public-interest or deepfake content.
6. Treat upstream model documentation as supplier evidence, never inherited compliance.
7. Block high-risk candidates until a documented deployment-specific legal-technical assessment exists.
8. Report controls individually; never publish a global compliance percentage.

Run:

```bash
python tools/eu_ai_act_release_gate.py .
iot-ai compliance status
iot-ai compliance release-gate --root . --profile developer-preview
```

## Release evidence

- `EVIDENCE_INDEX.json` binds the public-safe technical test results to their external evidence digests.
- `RELEASE_GATE_DECISION.md` states the exact technical pass and the legal claim boundary.
