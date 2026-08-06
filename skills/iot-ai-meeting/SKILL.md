---
name: iot-ai-meeting
description: Run a governed multi-coder meeting with specialist roles and first-class Ollama Cloud seats.
---
# iot-ai-meeting

Use the installed `iot-ai-meeting` compatibility command or `iot-ai meeting`.

- Natural-language example: `/iot-ai-meeting --max-parallel ask all coder and ollama clouds only review this architecture`.
- The phrase above resolves to `all-coders+ollama-clouds` and cannot silently omit Ollama.
- Run `iot-ai meeting seat-plan --seats all-coders+ollama-clouds` to inspect the exact resolved seats before dispatch.
- Empty, failed, meta-only or model-unverified seats never satisfy quorum.
- Command success is not meeting acceptance.
