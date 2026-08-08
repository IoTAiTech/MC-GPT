<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->

# Supported Coders and the Role of Ollama

## Supported coder CLI families

| Coder family | Typical role | Access modes | Required truth |
|---|---|---|---|
| Claude Code | architecture, synthesis, review | provider-native subscription or configured API | installed, authenticated, quota-ready, exact served model |
| OpenAI Codex CLI | implementation, debugging, code review | ChatGPT subscription or configured API | same checks |
| Gemini CLI | large-context and cross-module review | Google subscription or configured API | same checks |
| Grok CLI | implementation and adversarial review | Grok subscription or configured API | same checks |

Provider names are not specialist roles. IOT-AI first binds an immutable role contract—such as Domain Architect, Security Challenger, Implementation Engineer or Independent Verifier—and only then selects a suitable provider/model and effective effort.

## Ollama is first-class

Ollama is a local/cloud model gateway. Every exact eligible cloud model can become an independent specialist seat:

```text
ollama@<exact-model-id>
```

The runtime records exact requested and served model, route, tokens, cache usage, latency, retries and failure class. A successful Ollama call qualifies only that Ollama seat or an explicitly generic fallback lane. It never marks Claude, Codex, Gemini or Grok operational.

## Meetings

Use the auditable seat plan:

```bash
iot-ai meeting seat-plan --seats all-coders+ollama-clouds
```

Then run:

```bash
iot-ai meeting start \
  --topic "Review this task" \
  --seats all-coders+ollama-clouds \
  --depth deep --effort high --execute
```

The compatibility command below resolves to the same selector:

```bash
iot-ai-meeting --max-parallel ask all coder and ollama clouds only review this task
```

A meeting that requests all coders but omits Ollama is blocked when Ollama Cloud is configured, unless the user explicitly chooses `--exclude-ollama`.

## Efficient use

- Prefer existing coder subscriptions when they are live-ready; avoid paying for the same provider through an API without a policy reason.
- Use Ollama Cloud for perspective diversity, domain specialists and independent judging.
- Local Ollama models are disabled by default for governed deep reasoning unless explicitly qualified.
- Mechanical hashing, deduplication, schema validation and graph scheduling remain deterministic code.
- Prior validated knowledge is retrieved before a new meeting; unresolved gaps trigger targeted review instead of repeating the full meeting.
