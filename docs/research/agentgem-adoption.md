<!--
Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 6.5.0-beta.2 | Date: 2026-08-05
SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
-->
# AgentGem pattern adoption

## Source confidence

The exact X post body at `marfinxx/status/2084595353060258071` was not reliably retrievable during this release review. Search results associated the topic with AgentGem; architecture decisions below are based on the official product page, not on an inferred quotation from X.

Official source: https://agentgem.ai/

## Adopted patterns

- secret redaction at capture by key and value;
- one neutral, deterministic capability archive;
- one operation contract materialised as REST, MCP and OpenAPI 3.1;
- explicit public, unlisted, private and customer classifications;
- versioned materialisers for Claude, Codex, Gemini, Grok and other targets;
- immutable manifest and SHA-256 verification;
- review-gated publication and public/private separation.

## Not adopted

- hosted marketplace operation;
- pay-per-call monetisation;
- third-party session mining without explicit user consent;
- copying AgentGem implementation code or branding;
- treating a copied skill file as equivalent to an authenticated live service.

## Product use

Capability packs are a portable knowledge/deployment plane. Task state, assignment, ACK, lease, evidence, founder decisions and idempotency remain in the configured transactional store.
