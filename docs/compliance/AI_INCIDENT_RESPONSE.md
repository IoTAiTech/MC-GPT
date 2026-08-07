<!--
Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 6.7.0-beta.3 | Date: 2026-08-06
SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
-->
# AI and product-security incident response

## Trigger classes

- unsafe or prohibited AI behaviour;
- incorrect high-impact recommendation/action;
- secret or customer-data exposure;
- cross-tenant access;
- compromised model/tool/provider route;
- prompt injection or tool-authority bypass;
- actively exploited vulnerability or severe product incident;
- evidence-chain, update or rollback failure.

## Procedure

1. stop or isolate the affected route/component;
2. freeze original evidence and generate a sanitised diagnostic copy;
3. record system/version/deployment/model/tool/actor and impact;
4. classify AI Act, CRA, GDPR, NIS2 and contractual reportability separately;
5. calculate applicable deadlines only after qualified reportability determination;
6. notify the authorised incident owner and customer contact;
7. correct, verify, rollback or withdraw;
8. retain a hash-bound timeline, communications and closure receipt;
9. reassess intended purpose, risk class and substantial modification.

The built-in CRA helper provides 24-hour early-warning and 72-hour notification targets after a human/legal `reportable=true` determination. It does not decide legal reportability or the competent authority.
