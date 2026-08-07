# First-run setup

IOT-AI can use local subscription-authenticated CLIs, API routes, or both. It never stores API-key values in its configuration.

## 1. Discover installed coder CLIs

```bash
iot-ai-mc-gpt setup discover
```

This reports Claude, Codex, Gemini, Grok and Ollama executable paths and only whether the expected API environment variable is present. It does not claim authentication or model readiness.

## 2. Save a local inventory

```bash
iot-ai-mc-gpt setup init \
  --project-root ~/projects/my-project \
  --server development=http://127.0.0.1:8080 \
  --apply
```

Server URLs are stored only in the user's local configuration. Do not commit the inventory file. Credentials in URLs are rejected.

## 3. Configure providers

Subscription CLIs use their own official login session. API routes reference environment variables:

```text
ANTHROPIC_API_KEY
OPENAI_API_KEY
GEMINI_API_KEY
XAI_API_KEY
OLLAMA_API_KEY
```

Set them in an OS secret store or a protected process environment. Never paste values into `iot-ai-mc-gpt settings`, source files, Excel, issues or receipts.

## 4. Verify readiness

```bash
iot-ai-mc-gpt provider list
iot-ai-mc-gpt provider doctor --provider claude --auth-mode subscription
iot-ai-mc-gpt provider doctor --provider ollama --auth-mode api
```

A live doctor call can consume provider quota. Missing or blocked providers remain honestly unavailable.
