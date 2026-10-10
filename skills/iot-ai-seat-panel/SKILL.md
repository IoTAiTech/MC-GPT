---
name: iot-ai-seat-panel
description: Critique one sanitised description with several cloud models on the gateway. Use for a design panel. Never send code, paths, identifiers, or secrets.
id: iot-ai-seat-panel
version: 1.0.0
category: general
license: LicenseRef-PolyForm-Noncommercial-1.0.0
---
# iot-ai-seat-panel

Author: Dr. Babak Sorkhpour with AI assistance  
Version: 1.0.0 | Date: 2026-10-10

The panel reads a description. It produces candidates. Count only models that answered on topic. An empty or off-topic reply is "did not answer". Two thirds of the answering models must approve before the coordinator counts the panel.

The suite's single Ollama seat stays the largest cloud model. This panel may ask the other served cloud models the same text. Local models are not seats.

Set `GATEWAY` to the configured model-gateway base URL on port `11500`. Never host port `11434`. Never `ollama run`.

```sh
curl -sS "$GATEWAY/api/tags" | python3 -c 'import json,sys; print("\n".join(m["name"] for m in json.load(sys.stdin).get("models", []) if "cloud" in str(m.get("name","")).casefold()))'
```

One model, one request. Hold one lock so parallel callers do not overload the gateway.

```sh
flock /var/lock/model-gateway.lock curl -sS "$GATEWAY/api/chat" -d @"$WORKDIR/request.json" > "$WORKDIR/answer.json"
```

`request.json`:

```json
{"model": "MODEL-NAME", "stream": false, "think": false,
 "options": {"num_predict": 1800, "temperature": 0.2},
 "messages": [{"role": "user", "content": "<the sanitised prompt>"}]}
```

`think: false` with a generous `num_predict`. A model that spends its budget thinking returns an empty answer, and that measures the request. Send the same text to every selected cloud model. Tell them today's date. Before sending, remove file extensions, paths, line numbers, and identifiers.

On Windows, take a named mutex or a lock file instead of `flock`. Use `curl.exe`.

## Design critique

```
Today is <date>. Below is a written description of a planned change. No code is attached and none is needed.
1. Which rule can be satisfied while the stated goal is still missed?
2. Which sequence of two ordinary events breaks a rule?
3. What is unstated that the design depends on?
Answer in at most 200 words. Last line: approve or needs-changes.
CONTEXT ... GOAL ... RULES ... LIMITS (what is bounded, by which mechanism) ...
```

No credential, key, personal data, customer data, or private address in the prompt or the saved answer.
