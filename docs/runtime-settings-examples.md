# Runtime settings examples

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 1.0.0 | Date: 2026-09-03

## Inspect

```text
iot-ai settings show
iot-ai settings show --effective
iot-ai settings validate
iot-ai settings preset list
iot-ai settings preset show design-quality
iot-ai settings preset diff no-local-ollama
```

## Apply (explicit)

```text
iot-ai settings migrate --apply
iot-ai settings preset apply no-ollama --apply
iot-ai settings rollback <receipt-id> --apply
iot-ai settings set routing.ollama.local_policy never
iot-ai settings role set implementation-engineer --preferred-providers codex --effort xhigh
iot-ai settings role set security-challenger --preferred-providers grok --effort high
```

## Skills

```text
iot-ai settings skills discover
iot-ai settings skills list --goal "redesign the landing page" --role operator-ux-reviewer
iot-ai settings skills explain iot-ai-web-visual-quality
```

Claude, Codex, Gemini and Grok all use this same settings authority and the
same skill router. There is no per-engine skill router.
