# Runtime settings v2 and skill router

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 1.0.0 | Date: 2026-09-03

One settings authority (`src/iot_ai/settings.py`) and one skill router.
Schema `iot-ai.settings.v2`. Machine schema: `schemas/iot-ai-settings-v2.schema.json`.

## Precedence

CLI/session override > project `.iot-ai/settings.json` > user settings > built-in defaults.

Environment variables may supply `secret_env` / `endpoint_env` names. Raw secrets
are forbidden in persisted settings and logs.

v1 documents load with in-memory routing/skills defaults. Persistent v1→v2
migration is `iot-ai settings migrate --apply` (backup + source/dest SHA-256 +
rollback receipt).

## Effort resolution

role override > exact-model override > provider override > global default >
immutable role-contract default. Then clamp by edition entitlement,
provider-supported effort, risk policy and route capability.

## Ollama policies

`routing.ollama.local_policy` and `routing.ollama.cloud_policy` are independent:
`never | fallback | prefer | required | only`.

## Presets

`balanced`, `no-ollama`, `no-local-ollama`, `ollama-local-first`,
`ollama-cloud-first`, `sovereign-local`, `cloud-first`, `design-quality`,
`maximum-quality`. Inspect with `settings preset show|diff`. Apply is explicit.

`design-quality` enables visual skill policy for frontend work only.

## Skills

Silent in ordinary user text. Receipts record IDs, versions, licenses, digests,
scores, rejected reasons, router version and effective-settings digest.
Third-party skill text is `bounded-guidance`.
